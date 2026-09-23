import re
import time
from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel, Field
from backend.config import config

class CycleTelemetry(BaseModel):
    cycle_number: int
    timestamp: float = Field(default_factory=time.time)
    latency_ms: float = 0.0
    critic_score: float = 0.0
    quality_delta: float = 0.0
    semantic_similarity: float = 0.0
    error_count: int = 0
    requirement_coverage: float = 0.0
    critic_verdict: str = "PASS"
    stopping_signal: Optional[str] = None
    estimated_cost_usd: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cycle_number": self.cycle_number,
            "timestamp": self.timestamp,
            "latency_ms": round(self.latency_ms, 1),
            "critic_score": round(self.critic_score, 3),
            "quality_delta": round(self.quality_delta, 3),
            "semantic_similarity": round(self.semantic_similarity, 3),
            "error_count": self.error_count,
            "requirement_coverage": round(self.requirement_coverage, 3),
            "critic_verdict": self.critic_verdict,
            "stopping_signal": self.stopping_signal,
            "estimated_cost_usd": round(self.estimated_cost_usd, 4)
        }


class AdaptiveStoppingEngine:
    """
    Evaluates multi-signal stopping criteria across refinement cycles.
    Prevents both premature exits and wasteful infinite loops.
    """
    def __init__(
        self,
        max_cycles: int = config.MAX_CYCLES,
        min_cycles: int = config.MIN_CYCLES,
        quality_delta_threshold: float = config.QUALITY_DELTA_THRESHOLD,
        semantic_convergence_threshold: float = config.SEMANTIC_CONVERGENCE_THRESHOLD,
        min_acceptable_quality: float = config.MIN_ACCEPTABLE_QUALITY
    ):
        self.max_cycles = max_cycles
        self.min_cycles = min_cycles
        self.quality_delta_threshold = quality_delta_threshold
        self.semantic_convergence_threshold = semantic_convergence_threshold
        self.min_acceptable_quality = min_acceptable_quality

    def compute_jaccard_similarity(self, text_a: str, text_b: str) -> float:
        """Token-level semantic overlap between consecutive cycle outputs."""
        if not text_a or not text_b:
            return 0.0
        words_a = set(re.findall(r'\b\w+\b', text_a.lower()))
        words_b = set(re.findall(r'\b\w+\b', text_b.lower()))
        if not words_a or not words_b:
            return 1.0 if text_a == text_b else 0.0
        intersection = words_a.intersection(words_b)
        union = words_a.union(words_b)
        return len(intersection) / len(union)

    def evaluate_stopping(
        self,
        cycle_number: int,
        current_score: float,
        previous_score: Optional[float],
        current_draft: str,
        previous_draft: Optional[str],
        critical_errors: List[str],
        requirement_coverage: float,
        total_latency_ms: float = 0.0,
        total_cost_usd: float = 0.0
    ) -> Tuple[bool, str, CycleTelemetry]:
        """
        Returns: (should_stop: bool, reason: str, telemetry: CycleTelemetry)
        """
        # Calculate Delta & Convergence
        delta = 0.0
        if previous_score is not None:
            delta = current_score - previous_score
            
        similarity = 0.0
        if previous_draft is not None:
            similarity = self.compute_jaccard_similarity(current_draft, previous_draft)

        error_count = len(critical_errors)
        
        telemetry = CycleTelemetry(
            cycle_number=cycle_number,
            critic_score=current_score,
            quality_delta=delta,
            semantic_similarity=similarity,
            error_count=error_count,
            requirement_coverage=requirement_coverage,
            critic_verdict="PASS" if (current_score >= self.min_acceptable_quality and error_count == 0) else "REFINE",
            estimated_cost_usd=total_cost_usd
        )

        # Budget Guard 1: Hard Latency Budget Exceeded
        if total_latency_ms > config.MAX_LATENCY_MS:
            reason = f"BUDGET_EXCEEDED: Execution reached maximum latency budget ({total_latency_ms/1000:.1f}s)"
            telemetry.stopping_signal = reason
            return True, reason, telemetry

        # Budget Guard 2: Hard Cost Budget Exceeded
        if total_cost_usd > config.MAX_COST_USD:
            reason = f"BUDGET_EXCEEDED: Token expenditure reached cost budget (${total_cost_usd:.3f})"
            telemetry.stopping_signal = reason
            return True, reason, telemetry

        # Hard Cycle Cap
        if cycle_number >= self.max_cycles:
            reason = f"MAX_CYCLES_REACHED: System completed upper limit of {self.max_cycles} refinement cycles"
            telemetry.stopping_signal = reason
            return True, reason, telemetry

        # Minimum cycles enforced
        if cycle_number < self.min_cycles:
            return False, "CONTINUE: Minimum cycle requirement not yet satisfied", telemetry

        # Critical errors must be resolved unless capped
        if error_count > 0:
            return False, f"CONTINUE: Unresolved critical errors ({error_count}) detected by auditor", telemetry

        # Condition 1: High Quality + Critic Pass
        if current_score >= self.min_acceptable_quality and requirement_coverage >= 0.85:
            # Fast completion on clean first-pass verification
            if cycle_number == 1 and current_score >= 0.82:
                reason = f"ADAPTIVE_STOP (FIRST_PASS_VERIFIED): Verified with high quality ({current_score:.2f}) and 0 critical errors."
                telemetry.stopping_signal = reason
                return True, reason, telemetry

            # Check convergence
            if similarity >= self.semantic_convergence_threshold:
                reason = (
                    f"ADAPTIVE_STOP (CONVERGED): Output converged (sim: {similarity:.2f}) "
                    f"with high quality ({current_score:.2f}) and 0 critical errors."
                )
                telemetry.stopping_signal = reason
                return True, reason, telemetry
            
            # Check negligible marginal return
            if previous_score is not None and abs(delta) < self.quality_delta_threshold:
                reason = (
                    f"ADAPTIVE_STOP (MARGINAL_GAIN): Score improvement delta ({delta:+.3f}) "
                    f"is below threshold ({self.quality_delta_threshold}) with quality {current_score:.2f}."
                )
                telemetry.stopping_signal = reason
                return True, reason, telemetry

        # Condition 2: Convergence on Low Quality (Distinguish Convergence from Correctness)
        if similarity >= self.semantic_convergence_threshold and previous_score is not None and abs(delta) < 0.01:
            if current_score < self.min_acceptable_quality:
                reason = (
                    f"STOP_WITH_LIMITATION: Reasoning converged at suboptimal score ({current_score:.2f} < {self.min_acceptable_quality}). "
                    "Halting to prevent looping on stagnant hypothesis."
                )
                telemetry.stopping_signal = reason
                return True, reason, telemetry

        return False, f"CONTINUE: Refinement active (score: {current_score:.2f}, delta: {delta:+.2f})", telemetry

adaptive_stopping_engine = AdaptiveStoppingEngine()
