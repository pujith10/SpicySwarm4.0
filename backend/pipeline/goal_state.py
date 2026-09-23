from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import time
import re

class GoalState(BaseModel):
    """
    Immutable representation of the user's root objective.
    Pinned as a permanent constraint across all agent iterations.
    """
    goal_id: str
    original_goal: str
    required_outputs: List[str] = Field(default_factory=list)
    constraints: List[str] = Field(default_factory=list)
    success_conditions: List[str] = Field(default_factory=list)
    forbidden_actions: List[str] = Field(default_factory=list)
    user_preferences: Dict[str, Any] = Field(default_factory=dict)
    security_requirements: List[str] = Field(default_factory=lambda: [
        "no_credential_leakage", "no_unauthorized_tools", "data_provenance_enforced"
    ])
    created_at: float = Field(default_factory=time.time)

    def is_action_forbidden(self, action_name: str) -> bool:
        return any(f.lower() in action_name.lower() for f in self.forbidden_actions)


class PlanDriftDetector:
    """
    Detects semantic and intent divergence between the pinned GoalState,
    the Architect's plan, and the Analyst's current actions.
    """
    def __init__(self, drift_threshold: float = 0.45):
        self.drift_threshold = drift_threshold

    def compute_coverage(self, goal_text: str, target_text: str) -> float:
        words_goal = set(re.findall(r'\b[a-zA-Z]{3,}\b', goal_text.lower()))
        # Filter common stop words from goal
        stop_words = {"what", "the", "and", "for", "with", "how", "can", "why", "are", "was", "like"}
        key_goal_words = words_goal - stop_words
        if not key_goal_words:
            key_goal_words = words_goal
        if not key_goal_words:
            return 1.0
        words_target = set(re.findall(r'\b[a-zA-Z]{3,}\b', target_text.lower()))
        matched = key_goal_words.intersection(words_target)
        return len(matched) / len(key_goal_words)

    def evaluate_drift(self, goal: GoalState, plan_summary: str, action_summary: str) -> Dict[str, Any]:
        """
        Returns drift analysis dict:
        { "drift_detected": bool, "drift_score": float, "reason": str }
        """
        cov_plan = self.compute_coverage(goal.original_goal, plan_summary)
        cov_action = self.compute_coverage(goal.original_goal, action_summary) if action_summary.strip() else cov_plan
        
        # Combined alignment score based on keyword coverage
        alignment_score = 0.6 * cov_plan + 0.4 * cov_action
        drift_score = 1.0 - alignment_score
        
        # Check forbidden keywords
        forbidden_hits = [f for f in goal.forbidden_actions if f.lower() in (plan_summary + " " + action_summary).lower()]
        
        if forbidden_hits:
            return {
                "drift_detected": True,
                "drift_score": 1.0,
                "reason": f"Violation of forbidden constraints: {', '.join(forbidden_hits)}",
                "alignment_score": 0.0
            }

        # If similarity is too low (and query was non-trivial), flag drift
        if len(goal.original_goal.split()) > 4 and drift_score > (1.0 - self.drift_threshold):
            return {
                "drift_detected": True,
                "drift_score": round(drift_score, 3),
                "reason": f"Plan execution diverged from GoalState anchor (alignment: {alignment_score:.2f})",
                "alignment_score": round(alignment_score, 3)
            }

        return {
            "drift_detected": False,
            "drift_score": round(drift_score, 3),
            "reason": "Execution remains aligned with pinned GoalState",
            "alignment_score": round(alignment_score, 3)
        }

plan_drift_detector = PlanDriftDetector()
