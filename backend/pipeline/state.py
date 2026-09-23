from typing import TypedDict, List, Dict, Optional, Any
from backend.pipeline.goal_state import GoalState
from backend.pipeline.state_machine import PipelineStatus

class PipelineState(TypedDict, total=False):
    # Core Goal Anchoring
    query: str                               # Raw input query
    goal_state: Optional[Dict[str, Any]]     # Serialized GoalState (pinned immutable anchor)
    
    # RAG & Knowledge Layer
    retrieved_chunks: List[Dict[str, Any]]   # Structured chunks with provenance
    kg_triplets: List[str]                   # Knowledge Graph output
    
    # Agent Stage Data
    plan: Optional[Dict[str, Any]]           # Architect's decomposed sub-tasks
    execution: Optional[Dict[str, Any]]      # Analyst's tool execution results
    scraped_articles: List[Dict[str, Any]]   # Cumulative full content of visited websites across loops
    sources: List[Dict[str, Any]]            # Formatted list of unique visited sources with id, url, domain, title
    critic_table: Optional[str]              # Critic's 2-row table (Row 1: URLs, Row 2: Full website contents)
    state_delta: List[str]                   # Analyst's explicit uncertainties
    validation: Optional[Dict[str, Any]]     # Critic's structured 9D rubric evaluation
    final_answer: str                        # Verified final answer
    human_resolution: Optional[str]          # Synthesizer's human-readable narrative
    
    # Refinement & Performance Tracking
    retry_count: int                         # Refinement cycle counter
    prior_search_queries: List[str]          # Cumulative list of all DuckDuckGo search queries across loops
    prior_subtasks: List[Dict[str, Any]]     # Cumulative historical subtasks to prevent duplicate prompts
    cycle_metrics: List[Dict[str, Any]]      # Per-cycle telemetry (score, delta, similarity, latency, cost)
    is_converged: bool                       # Adaptive stopping flag
    stopping_reason: Optional[str]           # Explicit reason for stopping loop
    
    # Security & Mediation Layer
    capabilities: List[Dict[str, Any]]       # Active authorized capabilities
    security_events: List[Dict[str, Any]]    # Blocked actions, policy decisions
    provenance_records: List[Dict[str, Any]] # Data provenance ledger
    audit_trail: List[Dict[str, Any]]        # Audit log entries
    
    # Resilience & Diagnostics
    status: str                              # Human-readable status message
    state_machine_status: str                # PipelineStatus enum value
    checkpoints: List[Dict[str, Any]]        # Checkpoint history
    error: Optional[str]                     # Fatal or captured error description
    root_cause: Optional[Dict[str, Any]]     # RootCauseAnalysis breakdown
    
    # UI / Graph Display
    logs: List[Dict[str, Any]]               # Stage event logs for UI
    tool_outputs: List[Dict[str, Any]]       # Structured tool logs
    graph_data: Optional[Dict[str, Any]]     # Nodes/edges for visualization
    swarm_consensus: Optional[str]           # Summary consensus
