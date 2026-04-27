from typing import TypedDict, List, Dict, Optional, Any

class PipelineState(TypedDict):
    query: str                    # Original user goal (Goal Anchor)
    retrieved_chunks: List[str]   # RAG output
    kg_triplets: List[str]        # Knowledge Graph output
    plan: Optional[Dict[str, Any]] # Planner output
    execution: Optional[Dict[str, Any]] # Executor output
    state_delta: List[str]        # Executor uncertainty log
    validation: Optional[Dict[str, Any]] # Validator output
    final_answer: str             # Final answer to return
    retry_count: int              # Re-planning counter
    logs: List[Dict[str, Any]]    # Execution logs for UI
    status: str                   # Current status
    # New Swarm v2.0 fields
    tool_outputs: List[Dict[str, Any]] # Results from Search/Python
    graph_data: Dict[str, Any]         # Nodes/Edges for React Flow
    swarm_consensus: Optional[str]     # Critic's consensus notes
    error: Optional[str]               # Fatal API or logic errors
