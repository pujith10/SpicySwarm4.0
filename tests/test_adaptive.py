import pytest
from backend.agents.critic_rubric import CriticDimensions, StructuredCriticResult
from backend.pipeline.adaptive_loop import adaptive_stopping_engine

def test_critic_rubric_weighted_overall():
    dims = CriticDimensions(
        correctness=0.90,
        completeness=0.80,
        requirement_satisfaction=0.90,
        factual_grounding=0.85,
        logical_consistency=0.95,
        tool_use_correctness=0.90,
        security_compliance=1.0,
        hallucination_resistance=0.90,
        output_quality=0.85
    )
    score = dims.compute_weighted_overall()
    assert 0.85 <= score <= 0.95

def test_adaptive_stopping_on_semantic_convergence():
    draft1 = "The population of Delhi is estimated around 33 million residents in 2024."
    draft2 = "The population of Delhi is estimated around 33 million residents in 2024 according to recent records."
    
    stop, reason, telemetry = adaptive_stopping_engine.evaluate_stopping(
        cycle_number=3,
        current_score=0.91,
        previous_score=0.90,
        current_draft=draft2,
        previous_draft=draft1,
        critical_errors=[],
        requirement_coverage=0.95
    )
    assert stop is True
    assert "ADAPTIVE_STOP" in reason
    assert telemetry.critic_verdict == "PASS"

def test_adaptive_stopping_distinguishes_convergence_from_correctness():
    # Model repeats same bad answer (score 0.50)
    draft1 = "The answer is definitely 42 based on nothing."
    draft2 = "The answer is definitely 42 based on nothing."
    
    stop, reason, telemetry = adaptive_stopping_engine.evaluate_stopping(
        cycle_number=3,
        current_score=0.50, # Low quality
        previous_score=0.50,
        current_draft=draft2,
        previous_draft=draft1,
        critical_errors=[],
        requirement_coverage=0.60
    )
    assert stop is True
    assert "STOP_WITH_LIMITATION" in reason # Halts without claiming successful pass

def test_adaptive_stopping_enforces_budget_limit():
    stop, reason, telemetry = adaptive_stopping_engine.evaluate_stopping(
        cycle_number=2,
        current_score=0.80,
        previous_score=0.75,
        current_draft="Incomplete draft",
        previous_draft="Draft",
        critical_errors=[],
        requirement_coverage=0.70,
        total_latency_ms=50000 # 50s exceeds 45s budget
    )
    assert stop is True
    assert "BUDGET_EXCEEDED" in reason
