from langgraph.graph import StateGraph, END
from backend.pipeline.state import PipelineState
from backend.pipeline.state_machine import state_machine, PipelineStatus
from backend.agents.librarian import librarian
from backend.agents.planner import architect
from backend.agents.executor import analyst
from backend.agents.validator import critic
from backend.agents.synthesizer import synthesizer
from backend.config import config
import logging

logger = logging.getLogger(__name__)

async def librarian_node(state: PipelineState):
    print(">>> [GRAPH] Node: LIBRARIAN starting...", flush=True)
    state["state_machine_status"] = PipelineStatus.RETRIEVING.value
    res = await librarian.run(state)
    print(">>> [GRAPH] Node: LIBRARIAN done.", flush=True)
    return res

async def architect_node(state: PipelineState):
    print(">>> [GRAPH] Node: ARCHITECT starting...", flush=True)
    state["state_machine_status"] = PipelineStatus.PLANNING.value
    res = await architect.run(state)
    print(">>> [GRAPH] Node: ARCHITECT done.", flush=True)
    return res

async def analyst_node(state: PipelineState):
    print(">>> [GRAPH] Node: ANALYST starting...", flush=True)
    state["state_machine_status"] = PipelineStatus.EXECUTING.value
    res = await analyst.run(state)
    print(">>> [GRAPH] Node: ANALYST done.", flush=True)
    return res

async def critic_node(state: PipelineState):
    print(">>> [GRAPH] Node: CRITIC starting...", flush=True)
    state["state_machine_status"] = PipelineStatus.VERIFYING.value
    res = await critic.run(state)
    print(f">>> [GRAPH] Node: CRITIC done (converged={res.get('is_converged')}, score={res.get('validation', {}).get('overall_score')}).", flush=True)
    return res

async def synthesizer_node(state: PipelineState):
    print(">>> [GRAPH] Node: SYNTHESIZER starting...", flush=True)
    state["state_machine_status"] = PipelineStatus.COMPLETED.value
    res = await synthesizer.run(state)
    print(">>> [GRAPH] Node: SYNTHESIZER done.", flush=True)
    return res

def should_loop(state: PipelineState) -> str:
    """
    Adaptive stopping condition router.
    Evaluates:
    - Fatal errors -> synthesize immediate diagnostic report
    - is_converged flag from AdaptiveStoppingEngine -> synthesize final consensus
    - Otherwise, if cycles remain -> loop back to architect
    """
    # Fatal error branch
    if state.get("error"):
        logger.warning(f"Routing to Synthesizer due to captured error: {state.get('error')}")
        return "synthesizer"

    # Check adaptive stopping flag computed by Critic
    if state.get("is_converged", False):
        logger.info(f"Adaptive Stopping triggered: {state.get('stopping_reason', 'Converged')}. Finalizing.")
        return "synthesizer"

    # Check cycle cap
    current_cycles = state.get("retry_count", 0)
    if current_cycles >= config.MAX_CYCLES:
        logger.info(f"Upper cycle limit reached ({current_cycles}/{config.MAX_CYCLES}). Finalizing.")
        return "synthesizer"

    # Otherwise, loop back to architect for adaptive refinement
    logger.info(f"Triggering refinement cycle {current_cycles + 1} (routing to Architect)")
    state["state_machine_status"] = PipelineStatus.REFINING.value
    return "architect"

def build_graph():
    workflow = StateGraph(PipelineState)
    
    workflow.add_node("librarian", librarian_node)
    workflow.add_node("architect", architect_node)
    workflow.add_node("analyst", analyst_node)
    workflow.add_node("critic", critic_node)
    workflow.add_node("synthesizer", synthesizer_node)
    
    workflow.set_entry_point("librarian")
    
    workflow.add_edge("librarian", "architect")
    workflow.add_edge("architect", "analyst")
    workflow.add_edge("analyst", "critic")
    
    workflow.add_conditional_edges(
        "critic",
        should_loop,
        {
            "architect": "architect",
            "synthesizer": "synthesizer"
        }
    )
    
    workflow.add_edge("synthesizer", END)
    
    return workflow.compile()

graph = build_graph()
