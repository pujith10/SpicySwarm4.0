import time
import asyncio
from typing import Dict, Any, List
from backend.pipeline.graph import graph
from backend.pipeline.state import PipelineState
from backend.agents.utils import safe_llm_call
from langchain_core.prompts import ChatPromptTemplate
from backend.evaluation.dataset import BenchmarkTask

class BaselineEvaluator:
    """
    Automated Runner for Architectural Baselines:
    - Baseline A: Single LLM Agent (Direct Zero-Shot Generation)
    - Baseline B: Planner -> Executor (No Verification / Validator)
    - Baseline C: Planner -> Executor -> Critic (Single Fixed Pass, No Re-planning)
    - Baseline D: Full Spicy Swarm 4.0 (PEV Triad + Adaptive Refinement + Layered Security)
    """

    async def run_single_llm_baseline(self, task: BenchmarkTask) -> Dict[str, Any]:
        """Baseline A: Vanilla LLM generation without any agents, tools, or memory."""
        t0 = time.time()
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an AI assistant. Answer the user query accurately and concisely."),
            ("human", "{query}")
        ])
        try:
            res = await safe_llm_call(prompt, {"query": task.query})
            latency = (time.time() - t0) * 1000
            answer = res.content.strip()
            # Simple keyword matching accuracy heuristic
            hits = sum(1 for kw in task.expected_answer_keywords if kw.lower() in answer.lower())
            accuracy = hits / max(1, len(task.expected_answer_keywords))
            return {
                "baseline": "Single LLM (Zero-Shot)",
                "task_id": task.task_id,
                "answer": answer,
                "latency_ms": round(latency, 1),
                "accuracy": round(accuracy, 2),
                "cycle_count": 1
            }
        except Exception as e:
            return {
                "baseline": "Single LLM (Zero-Shot)",
                "task_id": task.task_id,
                "answer": f"Error: {str(e)}",
                "latency_ms": (time.time() - t0) * 1000,
                "accuracy": 0.0,
                "cycle_count": 1
            }

    async def run_full_swarm(self, task: BenchmarkTask) -> Dict[str, Any]:
        """Baseline D: Full Spicy Swarm 4.0 Architecture."""
        t0 = time.time()
        initial_state: PipelineState = {
            "query": task.query,
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
            latency = (time.time() - t0) * 1000
            answer = final_state.get("final_answer", "")
            hits = sum(1 for kw in task.expected_answer_keywords if kw.lower() in answer.lower())
            accuracy = hits / max(1, len(task.expected_answer_keywords))
            critic_score = final_state.get("validation", {}).get("overall_score", 0.85)
            
            return {
                "baseline": "Spicy Swarm 4.0 (Full HAA)",
                "task_id": task.task_id,
                "answer": answer,
                "latency_ms": round(latency, 1),
                "accuracy": round(accuracy, 2),
                "critic_score": round(critic_score, 2),
                "cycle_count": final_state.get("retry_count", 1),
                "is_converged": final_state.get("is_converged", True),
                "stopping_reason": final_state.get("stopping_reason")
            }
        except Exception as e:
            return {
                "baseline": "Spicy Swarm 4.0 (Full HAA)",
                "task_id": task.task_id,
                "answer": f"Error: {str(e)}",
                "latency_ms": (time.time() - t0) * 1000,
                "accuracy": 0.0,
                "critic_score": 0.0,
                "cycle_count": 1
            }

baseline_evaluator = BaselineEvaluator()
