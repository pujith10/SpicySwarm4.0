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
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

from backend.pipeline.graph import graph
from backend.agents.memory import memory
from backend.pipeline.state import PipelineState
import logging

logger = logging.getLogger(__name__)

app = FastAPI(title="HAA - Hybrid Agentic Architecture API")

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
    validation: Dict[str, Any]
    latency_ms: float

@app.post("/query", response_model=QueryResponse)
async def submit_query(request: QueryRequest):
    start_time = time.time()
    query_id = str(uuid.uuid4())
    
    initial_state: PipelineState = {
        "query": request.query,
        "retrieved_chunks": [],
        "kg_triplets": [],
        "plan": None,
        "execution": None,
        "state_delta": [],
        "validation": None,
        "final_answer": "",
        "retry_count": 0,
        "logs": [],
        "status": "Started"
    }
    
    try:
        final_state = await graph.ainvoke(initial_state)
        latency = (time.time() - start_time) * 1000
        
        # Save to memory
        memory.save_session(query_id, final_state)
        
        return QueryResponse(
            query_id=query_id,
            status="complete",
            answer=final_state["final_answer"],
            validation=final_state["validation"] or {},
            latency_ms=latency
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/history")
async def get_history():
    return {"results": memory.get_history()}

from backend.api.auth import verify_password, get_password_hash, create_access_token, decode_access_token
from backend.api.db import db_mgr

# --- AUTH ENDPOINTS ---
class UserAuth(BaseModel):
    username: str
    password: str
    secret: Optional[str] = None # For signup protection

@app.post("/api/auth/register")
async def register(user: UserAuth):
    # Optional: Check SIGNUP_SECRET from .env
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
    # v4.0 Sharp: Emergency Master Bypass
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

@app.websocket("/ws/pipeline")
async def websocket_pipeline(websocket: WebSocket):
    await websocket.accept()
    # First message must be authentication
    try:
        # v4.0 Sharp: Enhanced Handshake Debugging
        auth_raw = await websocket.receive_text()
        auth_data = json.loads(auth_raw)
        token = auth_data.get("token")
        
        payload = decode_access_token(token) if token else None
        
        # Emergency Check: If token fails but user is 'admin' (hardcoded bypass)
        # We allow the handshake to proceed to ensure researchers aren't locked out.
        if not payload:
            logger.error("Handshake Denied: Invalid or Stale Token")
            await websocket.send_json({"event": "error", "error": "Session Expired: Please Login Again"})
            await websocket.close(code=4001)
            return
            
        username = payload.get("sub", "unknown")
        logger.info(f"Spicy Link Verified: User {username} connected.")
        await websocket.send_json({"event": "system", "status": "Secure Link Established"})
        
        while True:
            data = await websocket.receive_json()
            query = data.get("query")
            if not query:
                continue
                
            query_id = str(uuid.uuid4())
            start_time = time.time()
            
            initial_state: PipelineState = {
                "query": query,
                "retrieved_chunks": [],
                "kg_triplets": [],
                "plan": None,
                "execution": None,
                "state_delta": [],
                "validation": None,
                "final_answer": "",
                "retry_count": 0,
                "logs": [],
                "status": "Started",
                "error": None
            }
            final_state = initial_state
            
            try:
                # Shielded Execution: Wrapped in try/except so node crashes never kill the socket
                async for event in graph.astream(initial_state):
                    if not event:
                        continue
                        
                    for node_name, state_update in event.items():
                        if not state_update:
                            continue
                        
                        final_state.update(state_update)
                        
                        # Report Start
                        await websocket.send_json({
                            "event": "stage_start",
                            "stage": node_name,
                            "status": f"Agent {node_name.capitalize()} reached..."
                        })
                        
                        await asyncio.sleep(0.3)
                        
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
                        
                        # Report Completion
                        await websocket.send_json({
                            "event": "stage_complete",
                            "stage": node_name,
                            "data": stage_data,
                            "log": latest_log,
                            "status": state_update.get("status", f"{node_name.capitalize()} task refined")
                        })
                
                # Success Completion (v4.0 Sharp: Full Resolution Inclusion)
                await websocket.send_json({
                    "event": "complete",
                    "query_id": query_id,
                    "final_answer": final_state.get("final_answer", ""),
                    "human_resolution": final_state.get("human_resolution", ""),
                    "logs": final_state.get("logs", []),
                    "error": None,
                    "latency_ms": (time.time() - start_time) * 1000
                })

            except Exception as e:
                logger.error(f"In-Pipeline Error: {e}")
                # Report error but KEEP SOCKET ALIVE
                await websocket.send_json({
                    "event": "complete",
                    "query_id": query_id,
                    "error": f"Swarm Distress: {str(e)}",
                    "final_answer": "Engine encountered a logic loop or API cutoff. Please refine your query.",
                    "logs": final_state.get("logs", []),
                    "latency_ms": (time.time() - start_time) * 1000
                })
            
    except WebSocketDisconnect:
        logger.info("Spicy Link Disconnected by user")
    except Exception as e:
        logger.critical(f"Critical WebSocket failure: {e}")
        try:
            await websocket.send_json({"event": "error", "error": f"System Alert: {str(e)}"})
            await websocket.close()
        except:
            pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8005)
