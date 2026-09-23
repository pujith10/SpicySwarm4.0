import time
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

class ProviderMetrics(BaseModel):
    provider_name: str
    model_name: str
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    timeout_calls: int = 0
    rate_limit_calls: int = 0
    recent_latencies: List[float] = Field(default_factory=list) # Last 20 calls in ms
    last_failure_timestamp: Optional[float] = None
    last_success_timestamp: Optional[float] = None

    @property
    def error_rate(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return self.failed_calls / self.total_calls

    @property
    def average_latency_ms(self) -> float:
        if not self.recent_latencies:
            return 0.0
        return sum(self.recent_latencies) / len(self.recent_latencies)

    @property
    def health_score(self) -> float:
        """
        Computed score from 0.00 to 1.00 combining availability, recent error rate, and timeouts.
        """
        if self.total_calls == 0:
            return 1.0 # Untested assumed healthy
        
        # Penalties for errors and rate limits
        rate_limit_penalty = min(0.4, (self.rate_limit_calls / max(1, self.total_calls)) * 0.8)
        error_penalty = min(0.5, self.error_rate * 0.7)
        
        score = 1.0 - (rate_limit_penalty + error_penalty)
        return round(max(0.0, min(1.0, score)), 3)

    def record_success(self, latency_ms: float) -> None:
        self.total_calls += 1
        self.successful_calls += 1
        self.last_success_timestamp = time.time()
        self.recent_latencies.append(latency_ms)
        if len(self.recent_latencies) > 20:
            self.recent_latencies.pop(0)

    def record_failure(self, error_type: str = "general") -> None:
        self.total_calls += 1
        self.failed_calls += 1
        self.last_failure_timestamp = time.time()
        if "timeout" in error_type.lower():
            self.timeout_calls += 1
        elif "rate_limit" in error_type.lower() or "429" in error_type:
            self.rate_limit_calls += 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider_name": self.provider_name,
            "model_name": self.model_name,
            "health_score": self.health_score,
            "error_rate": round(self.error_rate, 3),
            "avg_latency_ms": round(self.average_latency_ms, 1),
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "rate_limit_calls": self.rate_limit_calls
        }


class ProviderHealthTracker:
    """
    Maintains real-time telemetry on all LLM providers and models.
    Enables health-aware routing rather than blind static fallbacks.
    """
    def __init__(self):
        self._providers: Dict[str, ProviderMetrics] = {
            "google_gemini": ProviderMetrics(provider_name="google", model_name="gemini-1.5-flash"),
            "groq_70b": ProviderMetrics(provider_name="groq", model_name="llama-3.3-70b-versatile"),
            "groq_8b": ProviderMetrics(provider_name="groq", model_name="llama-3.1-8b-instant")
        }

    def get_provider(self, key: str) -> ProviderMetrics:
        if key not in self._providers:
            self._providers[key] = ProviderMetrics(provider_name=key.split("_")[0], model_name=key)
        return self._providers[key]

    def get_all_status(self) -> Dict[str, Dict[str, Any]]:
        return {k: v.to_dict() for k, v in self._providers.items()}

    def get_healthiest_provider(self, candidates: Optional[List[str]] = None) -> str:
        if not candidates:
            candidates = list(self._providers.keys())
        
        ranked = sorted(
            candidates,
            key=lambda k: (self.get_provider(k).health_score, -self.get_provider(k).average_latency_ms),
            reverse=True
        )
        return ranked[0]

health_tracker = ProviderHealthTracker()
