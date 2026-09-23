import pytest
import time
from backend.resilience.circuit_breaker import CircuitBreaker, CircuitState
from backend.resilience.health_tracker import ProviderHealthTracker

def test_circuit_breaker_state_transitions():
    cb = CircuitBreaker("test_provider", failure_threshold=3, recovery_timeout_secs=1)
    assert cb.state == CircuitState.CLOSED
    assert cb.can_execute() is True

    # 1st failure
    cb.record_failure()
    assert cb.state == CircuitState.CLOSED

    # 2nd failure
    cb.record_failure()
    assert cb.state == CircuitState.CLOSED

    # 3rd failure -> trips to OPEN
    cb.record_failure()
    assert cb.state == CircuitState.OPEN
    assert cb.can_execute() is False

    # Wait for recovery timeout (1 sec)
    time.sleep(1.1)
    
    # Next call should transition to HALF_OPEN
    assert cb.can_execute() is True
    assert cb.state == CircuitState.HALF_OPEN

    # Success in HALF_OPEN recovers to CLOSED
    cb.record_success()
    assert cb.state == CircuitState.CLOSED
    assert cb.failure_count == 0

def test_health_tracker_ranking():
    tracker = ProviderHealthTracker()
    p_good = tracker.get_provider("provider_a")
    p_bad = tracker.get_provider("provider_b")

    for _ in range(10):
        p_good.record_success(latency_ms=120)

    for _ in range(5):
        p_bad.record_failure("HTTP 500")

    assert p_good.health_score > p_bad.health_score
    best = tracker.get_healthiest_provider(["provider_a", "provider_b"])
    assert best == "provider_a"
