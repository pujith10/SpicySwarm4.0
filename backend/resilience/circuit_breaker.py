from enum import Enum
import time
from typing import Dict, Any, Optional
import logging
from backend.config import config

logger = logging.getLogger(__name__)

class CircuitState(str, Enum):
    CLOSED = "CLOSED"       # Normal operational state, requests pass through
    OPEN = "OPEN"           # Tripped due to failures, requests immediately short-circuit to fallback
    HALF_OPEN = "HALF_OPEN" # Cooldown elapsed, testing recovery with single probe request


class CircuitBreaker:
    """
    Finite State Circuit Breaker protecting the Swarm from cascading API outages.
    Tracks failure bursts and coordinates automatic self-healing transitions.
    """
    def __init__(
        self,
        name: str,
        failure_threshold: int = config.CIRCUIT_BREAKER_FAILURE_THRESHOLD,
        recovery_timeout_secs: int = config.CIRCUIT_BREAKER_RECOVERY_TIMEOUT_SECS
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout_secs = recovery_timeout_secs
        
        self.state: CircuitState = CircuitState.CLOSED
        self.failure_count: int = 0
        self.last_failure_time: Optional[float] = None
        self.last_state_change: float = time.time()
        self.trip_count: int = 0

    def can_execute(self) -> bool:
        """Determines whether a call to this provider is permitted."""
        if self.state == CircuitState.CLOSED:
            return True
            
        if self.state == CircuitState.OPEN:
            # Check if cooldown has elapsed to enter HALF_OPEN probe state
            if self.last_failure_time and (time.time() - self.last_failure_time) >= self.recovery_timeout_secs:
                logger.info(f"CircuitBreaker [{self.name}]: Cooldown elapsed. Transitioning OPEN -> HALF_OPEN.")
                self.state = CircuitState.HALF_OPEN
                self.last_state_change = time.time()
                return True
            return False # Still tripped, short-circuit
            
        if self.state == CircuitState.HALF_OPEN:
            return True # Allow trial probe request

        return True

    def record_success(self) -> None:
        """Called when a request to the provider succeeds."""
        if self.state == CircuitState.HALF_OPEN:
            logger.info(f"CircuitBreaker [{self.name}]: Trial probe succeeded. Transitioning HALF_OPEN -> CLOSED (Recovered).")
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.last_state_change = time.time()
        elif self.state == CircuitState.CLOSED:
            self.failure_count = 0

    def record_failure(self, error: Optional[Exception] = None) -> None:
        """Called when a request to the provider fails."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.state == CircuitState.HALF_OPEN:
            logger.warning(f"CircuitBreaker [{self.name}]: Probe failed in HALF_OPEN. Re-tripping to OPEN.")
            self.state = CircuitState.OPEN
            self.trip_count += 1
            self.last_state_change = time.time()
            
        elif self.state == CircuitState.CLOSED and self.failure_count >= self.failure_threshold:
            logger.critical(f"CircuitBreaker [{self.name}]: Failure threshold ({self.failure_threshold}) exceeded. Tripping CLOSED -> OPEN.")
            self.state = CircuitState.OPEN
            self.trip_count += 1
            self.last_state_change = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "trip_count": self.trip_count,
            "last_failure_ago_secs": round(time.time() - self.last_failure_time, 1) if self.last_failure_time else None
        }


class CircuitBreakerRegistry:
    """Registry managing circuit breakers across all supported model providers."""
    def __init__(self):
        self._breakers: Dict[str, CircuitBreaker] = {
            "google_gemini": CircuitBreaker("google_gemini"),
            "groq_70b": CircuitBreaker("groq_70b"),
            "groq_8b": CircuitBreaker("groq_8b")
        }

    def get(self, name: str) -> CircuitBreaker:
        if name not in self._breakers:
            self._breakers[name] = CircuitBreaker(name)
        return self._breakers[name]

    def get_all_states(self) -> Dict[str, Dict[str, Any]]:
        return {name: cb.to_dict() for name, cb in self._breakers.items()}

circuit_registry = CircuitBreakerRegistry()
