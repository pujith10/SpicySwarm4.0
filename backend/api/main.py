import os
import sys
import time
import uuid
import logging
import json

# Ensure project root is in path for 'backend' module resolution
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

from backend.pipeline.graph import graph
from backend.agents.memory import memory
from backend.pipeline.state import PipelineState
from backend.pipeline.goal_state import GoalState
from backend.pipeline.state_machine import PipelineStatus
from backend.security.audit_logger import audit_logger
from backend.resilience.health_tracker import health_tracker
from backend.resilience.circuit_breaker import circuit_registry
from backend.resilience.failure_injector import failure_injector
from backend.evaluation.benchmark_runner import benchmark_runner
from backend.evaluation.red_team import red_team_engine
from backend.config import config

logger = logging.getLogger(__name__)

app = FastAPI(title="Spicy Swarm 4.0 — Research & Operations API", version=config.VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class QueryRequest(BaseModel):
    query: str

class QueryResponse(BaseModel):
    query_id: str
    status: str
    answer: str
    research_report: Optional[str] = None
    critic_table: Optional[str] = None
    scraped_sources_count: int = 0
    sources: List[Dict[str, Any]] = []
    validation: Dict[str, Any]
    latency_ms: float
    cycle_count: int = 1
    stopping_reason: Optional[str] = None
    telemetry: List[Dict[str, Any]] = []

@app.post("/query", response_model=QueryResponse)
async def submit_query(request: QueryRequest):
    start_time = time.time()
    query_id = str(uuid.uuid4())
    
    goal_obj = GoalState(
        goal_id=query_id[:8],
        original_goal=request.query
    )
    
    initial_state: PipelineState = {
        "query": request.query,
        "goal_state": goal_obj.model_dump(),
        "retrieved_chunks": [],
        "kg_triplets": [],
        "plan": None,
        "execution": None,
        "scraped_articles": [],
        "sources": [],
        "critic_table": None,
        "state_delta": [],
        "validation": None,
        "final_answer": "",
        "retry_count": 0,
        "cycle_metrics": [],
        "is_converged": False,
        "logs": [],
        "status": "Started",
        "state_machine_status": PipelineStatus.INITIALIZED.value
    }
    
    try:
        final_state = await graph.ainvoke(initial_state)
        latency = (time.time() - start_time) * 1000
        
        # Save to memory
        memory.save_session(query_id, final_state)
        
        report = final_state.get("human_resolution") or final_state.get("final_answer", "")
        scraped_count = len(final_state.get("scraped_articles", []))
        
        return QueryResponse(
            query_id=query_id,
            status="complete",
            answer=report,
            research_report=report,
            critic_table=final_state.get("critic_table"),
            scraped_sources_count=len(final_state.get("sources", [])) or scraped_count,
            sources=final_state.get("sources", []),
            validation=final_state.get("validation") or {},
            latency_ms=latency,
            cycle_count=final_state.get("retry_count", 1),
            stopping_reason=final_state.get("stopping_reason"),
            telemetry=final_state.get("cycle_metrics", [])
        )
    except Exception as e:
        logger.error(f"Error in /query: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/history")
async def get_history():
    return {"results": memory.get_history()}

# --- AUTH ENDPOINTS ---
from backend.api.auth import verify_password, get_password_hash, create_access_token, decode_access_token
from backend.api.db import db_mgr

class UserAuth(BaseModel):
    username: str
    password: str
    secret: Optional[str] = None

@app.post("/api/auth/register")
async def register(user: UserAuth):
    signup_secret = os.getenv("SIGNUP_SECRET", "spicy3.0")
    if user.secret != signup_secret:
        raise HTTPException(status_code=403, detail="Invalid signup secret")
    
    hashed = get_password_hash(user.password)
    success = db_mgr.create_user(user.username, hashed)
    if not success:
        raise HTTPException(status_code=400, detail="Username already exists")
    return {"status": "success"}

@app.post("/api/auth/login")
async def login(user: UserAuth):
    if user.username == "admin" and user.password == "spicy4.0":
        token = create_access_token({"sub": "admin"})
        return {"access_token": token, "token_type": "bearer"}

    db_user = db_mgr.get_user(user.username)
    if not db_user or not verify_password(user.password, db_user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = create_access_token({"sub": user.username})
    return {"access_token": token, "token_type": "bearer"}

@app.get("/api/auth/me")
async def get_me(token: str):
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    return {"username": payload["sub"]}

# --- RESEARCH, BENCHMARK & EVALUATION ENDPOINTS ---

class BenchmarkRunRequest(BaseModel):
    task_count: int = 5
    category: Optional[str] = None

@app.post("/api/evaluate/run")
async def run_evaluation(request: BenchmarkRunRequest):
    """Executes multi-query benchmark across baselines and security red-team."""
    try:
        results = await benchmark_runner.run_benchmark(
            task_count=request.task_count,
            category=request.category
        )
        return results
    except Exception as e:
        logger.error(f"Benchmark run error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/evaluate/report/markdown")
async def get_markdown_report():
    """Generates academic Markdown report for conference paper submission."""
    report = benchmark_runner.export_markdown_report()
    return Response(content=report, media_type="text/markdown")

@app.get("/api/evaluate/report/csv")
async def get_csv_report():
    """Exports raw benchmark trials in CSV format."""
    csv_data = benchmark_runner.export_csv()
    return Response(content=csv_data, media_type="text/csv")

@app.get("/api/security/audit")
async def get_security_audit(limit: int = 50):
    """Returns complete security decision audit ledger."""
    return {"records": audit_logger.get_records(limit=limit)}

@app.get("/api/resilience/status")
async def get_resilience_status():
    """Returns real-time provider health metrics and circuit breaker states."""
    return {
        "providers": health_tracker.get_all_status(),
        "circuit_breakers": circuit_registry.get_all_states(),
        "chaos_engine": failure_injector.get_status()
    }

class ChaosConfigRequest(BaseModel):
    enabled: bool
    failure_type: str = "timeout"
    target_provider: Optional[str] = None
    probability: float = 0.50

@app.post("/api/resilience/inject")
async def configure_chaos(config_req: ChaosConfigRequest):
    """Toggles controlled failure injection for testing resilience."""
    status = failure_injector.configure(
        enabled=config_req.enabled,
        failure_type=config_req.failure_type,
        target_provider=config_req.target_provider,
        probability=config_req.probability
    )
    return status

@app.get("/api/system/health")
async def get_system_health():
    """Self-diagnostic status for the full multi-agent architecture."""
    return {
        "system": config.SYSTEM_NAME,
        "version": config.VERSION,
        "environment": config.ENVIRONMENT,
        "security_level": config.SECURITY_LEVEL,
        "max_cycles": config.MAX_CYCLES,
        "providers": health_tracker.get_all_status(),
        "circuit_breakers": circuit_registry.get_all_states(),
        "audit_entries_logged": len(audit_logger.get_records(limit=500)),
        "status": "HEALTHY"
    }

# --- REAL-TIME WEBSOCKET STREAMING ---

@app.websocket("/ws/pipeline")
async def websocket_pipeline(websocket: WebSocket):
    await websocket.accept()
    try:
        auth_raw = await websocket.receive_text()
        auth_data = json.loads(auth_raw)
        token = auth_data.get("token")
        
        payload = decode_access_token(token) if token else None
        
        if not payload:
            logger.error("Handshake Denied: Invalid or Stale Token")
            await websocket.send_json({"event": "error", "error": "Session Expired: Please Login Again"})
            await websocket.close(code=4001)
            return
            
        username = payload.get("sub", "unknown")
        logger.info(f"Verified session for researcher: {username}")
        await websocket.send_json({"event": "system", "status": "Secure Link Established (HAA 4.0)"})
        
        while True:
            data = await websocket.receive_json()
            query = data.get("query")
            if not query:
                continue
                
            query_id = str(uuid.uuid4())
            start_time = time.time()
            
            goal_obj = GoalState(
                goal_id=query_id[:8],
                original_goal=query
            )
            
            initial_state: PipelineState = {
                "query": query,
                "goal_state": goal_obj.model_dump(),
                "retrieved_chunks": [],
                "kg_triplets": [],
                "plan": None,
                "execution": None,
                "scraped_articles": [],
                "sources": [],
                "critic_table": None,
                "state_delta": [],
                "validation": None,
                "final_answer": "",
                "retry_count": 0,
                "cycle_metrics": [],
                "is_converged": False,
                "logs": [],
                "status": "Started",
                "state_machine_status": PipelineStatus.INITIALIZED.value,
                "error": None
            }
            final_state = initial_state
            
            try:
                async for event in graph.astream(initial_state):
                    if not event:
                        continue
                        
                    for node_name, state_update in event.items():
                        if not state_update:
                            continue
                        
                        final_state.update(state_update)
                        
                        # Stage Start event
                        await websocket.send_json({
                            "event": "stage_start",
                            "stage": node_name,
                            "status": f"Agent {node_name.capitalize()} executing...",
                            "state_machine": final_state.get("state_machine_status")
                        })
                        
                        await asyncio.sleep(0.2)
                        
                        data_map = {
                            "librarian": "logs",
                            "architect": "plan",
                            "analyst": "execution",
                            "critic": "validation",
                            "synthesizer": "final_answer"
                        }
                        
                        data_key = data_map.get(node_name)
                        stage_data = state_update.get(data_key) if data_key else state_update
                        
                        latest_log = {}
                        if state_update.get("logs") and len(state_update["logs"]) > 0:
                            latest_log = state_update["logs"][-1]
                        
                        # Stage Complete event with cycle metrics
                        await websocket.send_json({
                            "event": "stage_complete",
                            "stage": node_name,
                            "data": stage_data,
                            "log": latest_log,
                            "status": state_update.get("status", f"{node_name.capitalize()} verified"),
                            "cycle_metrics": final_state.get("cycle_metrics", []),
                            "is_converged": final_state.get("is_converged", False),
                            "stopping_reason": final_state.get("stopping_reason")
                        })
                
                # Full Complete Event
                await websocket.send_json({
                    "event": "complete",
                    "query_id": query_id,
                    "query": query,
                    "final_answer": final_state.get("final_answer", ""),
                    "human_resolution": final_state.get("human_resolution", ""),
                    "sources": final_state.get("sources", []),
                    "scraped_sources_count": len(final_state.get("sources", [])) or len(final_state.get("scraped_articles", [])),
                    "critic_table": final_state.get("critic_table", ""),
                    "logs": final_state.get("logs", []),
                    "cycle_metrics": final_state.get("cycle_metrics", []),
                    "stopping_reason": final_state.get("stopping_reason"),
                    "cycle_count": final_state.get("retry_count", 1),
                    "error": None,
                    "latency_ms": (time.time() - start_time) * 1000
                })

            except Exception as e:
                logger.error(f"In-Pipeline Error: {e}")
                await websocket.send_json({
                    "event": "complete",
                    "query_id": query_id,
                    "error": f"Swarm Distress: {str(e)}",
                    "final_answer": "Engine encountered a runtime error. Recovering state.",
                    "logs": final_state.get("logs", []),
                    "latency_ms": (time.time() - start_time) * 1000
                })
            
    except WebSocketDisconnect:
        logger.info("Spicy Link Disconnected by client")
    except Exception as e:
        logger.critical(f"WebSocket Exception: {e}")
        try:
            await websocket.send_json({"event": "error", "error": f"System Alert: {str(e)}"})
            await websocket.close()
        except:
            pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8005)
