from enum import Enum
from typing import Set, Dict, Optional
import logging

logger = logging.getLogger(__name__)

class PipelineStatus(str, Enum):
    INITIALIZED = "INITIALIZED"
    PLANNING = "PLANNING"
    RETRIEVING = "RETRIEVING"
    EXECUTING = "EXECUTING"
    VERIFYING = "VERIFYING"
    REFINING = "REFINING"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    RECOVERING = "RECOVERING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"


class WorkflowStateMachine:
    """
    Formal State Machine governing valid transitions across the multi-agent swarm.
    Prevents illegal agent jumps, race conditions, or unverified task completion.
    """
    _VALID_TRANSITIONS: Dict[PipelineStatus, Set[PipelineStatus]] = {
        PipelineStatus.INITIALIZED: {
            PipelineStatus.RETRIEVING, PipelineStatus.PLANNING, PipelineStatus.FAILED, PipelineStatus.BLOCKED
        },
        PipelineStatus.RETRIEVING: {
            PipelineStatus.PLANNING, PipelineStatus.RECOVERING, PipelineStatus.FAILED, PipelineStatus.BLOCKED
        },
        PipelineStatus.PLANNING: {
            PipelineStatus.EXECUTING, PipelineStatus.RECOVERING, PipelineStatus.FAILED, PipelineStatus.BLOCKED
        },
        PipelineStatus.EXECUTING: {
            PipelineStatus.VERIFYING, PipelineStatus.WAITING_FOR_APPROVAL, PipelineStatus.RECOVERING, PipelineStatus.FAILED, PipelineStatus.BLOCKED
        },
        PipelineStatus.WAITING_FOR_APPROVAL: {
            PipelineStatus.EXECUTING, PipelineStatus.BLOCKED, PipelineStatus.FAILED
        },
        PipelineStatus.VERIFYING: {
            PipelineStatus.REFINING, PipelineStatus.COMPLETED, PipelineStatus.RECOVERING, PipelineStatus.FAILED, PipelineStatus.BLOCKED
        },
        PipelineStatus.REFINING: {
            PipelineStatus.PLANNING, PipelineStatus.EXECUTING, PipelineStatus.RECOVERING, PipelineStatus.FAILED, PipelineStatus.BLOCKED
        },
        PipelineStatus.RECOVERING: {
            PipelineStatus.PLANNING, PipelineStatus.EXECUTING, PipelineStatus.VERIFYING, PipelineStatus.FAILED
        },
        PipelineStatus.COMPLETED: set(), # Terminal
        PipelineStatus.FAILED: set(),    # Terminal
        PipelineStatus.BLOCKED: set(),   # Terminal
    }

    @classmethod
    def can_transition(cls, current: PipelineStatus, target: PipelineStatus) -> bool:
        if current == target:
            return True
        allowed = cls._VALID_TRANSITIONS.get(current, set())
        return target in allowed

    @classmethod
    def transition(cls, current: PipelineStatus, target: PipelineStatus, context: Optional[str] = None) -> PipelineStatus:
        if cls.can_transition(current, target):
            logger.info(f"State transition: {current.value} -> {target.value} ({context or 'normal'})")
            return target
        else:
            msg = f"Illegal State Transition Attempted: {current.value} -> {target.value}"
            logger.error(msg)
            raise ValueError(msg)

state_machine = WorkflowStateMachine()
