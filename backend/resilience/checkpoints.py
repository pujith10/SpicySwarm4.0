import copy
import time
from typing import Dict, Any, List, Optional
from backend.pipeline.state import PipelineState
import logging

logger = logging.getLogger(__name__)

class CheckpointManager:
    """
    Saves state checkpoints at critical stage boundaries.
    Enables atomic rollback and recovery if an intermediate node encounters unrecoverable corruption.
    """
    def __init__(self, max_checkpoints: int = 10):
        self.max_checkpoints = max_checkpoints
        self._checkpoints: Dict[str, List[Dict[str, Any]]] = {}

    def save_checkpoint(self, session_id: str, stage_name: str, state: PipelineState) -> Dict[str, Any]:
        if session_id not in self._checkpoints:
            self._checkpoints[session_id] = []

        snapshot = {
            "checkpoint_id": f"ckpt_{len(self._checkpoints[session_id]) + 1}",
            "timestamp": time.time(),
            "stage": stage_name,
            "state_snapshot": copy.deepcopy({
                "query": state.get("query"),
                "goal_state": state.get("goal_state"),
                "plan": state.get("plan"),
                "execution": state.get("execution"),
                "retry_count": state.get("retry_count"),
                "cycle_metrics": state.get("cycle_metrics"),
                "status": state.get("status")
            })
        }
        self._checkpoints[session_id].append(snapshot)
        if len(self._checkpoints[session_id]) > self.max_checkpoints:
            self._checkpoints[session_id].pop(0)

        logger.info(f"Checkpoint saved for session {session_id[:8]} at stage '{stage_name}'")
        return snapshot

    def get_latest_checkpoint(self, session_id: str) -> Optional[Dict[str, Any]]:
        history = self._checkpoints.get(session_id, [])
        return history[-1] if history else None

    def restore_latest_checkpoint(self, session_id: str, target_state: PipelineState) -> bool:
        ckpt = self.get_latest_checkpoint(session_id)
        if not ckpt:
            return False
        snap = ckpt["state_snapshot"]
        target_state.update(snap)
        logger.warning(f"State rolled back to checkpoint from stage '{ckpt['stage']}'")
        return True

checkpoint_manager = CheckpointManager()
