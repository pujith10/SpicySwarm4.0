from langgraph.graph import StateGraph, END
from backend.pipeline.state import PipelineState
from backend.agents.librarian import librarian
from backend.agents.planner import architect
from backend.agents.executor import analyst
from backend.agents.validator import critic
from backend.agents.synthesizer import synthesizer

async def librarian_node(state: PipelineState):
    return await librarian.run(state)

async def architect_node(state: PipelineState):
    return await architect.run(state)

async def analyst_node(state: PipelineState):
    return await analyst.run(state)

async def critic_node(state: PipelineState):
    return await critic.run(state)

async def synthesizer_node(state: PipelineState):
    return await synthesizer.run(state)

def should_loop(state: PipelineState):
    # Break immediately if a fatal error (like Rate Limit) occurred
    if state.get("error"):
        return "synthesizer"
        
    validation = state.get("validation", {})
    verdict = validation.get("verdict", "PASS")
    
    if verdict == "REFINE" and state.get("retry_count", 0) < 7:
        # Note: retry_count is now incremented inside the Critic node
        return "architect"
    return "synthesizer"

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
