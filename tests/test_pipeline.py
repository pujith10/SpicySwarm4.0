import pytest
import asyncio
from backend.pipeline.graph import graph
from backend.pipeline.state import PipelineState
from backend.pipeline.goal_state import GoalState
from backend.pipeline.state_machine import PipelineStatus

@pytest.mark.asyncio
async def test_end_to_end_graph_execution():
    query = "Calculate compound interest for $10,000 at 5% for 3 years"
    goal_obj = GoalState(
        goal_id="test_g1",
        original_goal=query
    )
    initial_state: PipelineState = {
        "query": query,
        "goal_state": goal_obj.model_dump(),
        "retrieved_chunks": [],
        "kg_triplets": [],
        "plan": None,
        "execution": None,
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

    final_state = await graph.ainvoke(initial_state)

    assert final_state is not None
    assert final_state["final_answer"] != ""
    assert final_state["validation"] is not None
    assert "dimensions" in final_state["validation"]
    assert final_state["retry_count"] >= 1
    # Check that logs were populated
    stages = [l["stage"] for l in final_state.get("logs", [])]
    assert "librarian" in stages
    assert "architect" in stages
    assert "analyst" in stages
    assert "critic" in stages
    assert "synthesizer" in stages
