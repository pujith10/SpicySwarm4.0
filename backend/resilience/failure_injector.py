import random
import time
import asyncio
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

class FailureInjector:
    """
    Controlled Fault Injection Framework for Chaos & Resilience Experiments.
    Allows testing system survival rates, circuit breakers, and recovery latencies under realistic network chaos.
    """
    def __init__(self):
        self.enabled: bool = False
        self.target_provider: Optional[str] = None # None means all providers
        self.failure_type: str = "timeout"          # "timeout", "rate_limit", "malformed_json", "outage"
        self.probability: float = 0.50             # 50% chance of fault when active
        self.injected_events_count: int = 0

    def configure(
        self,
        enabled: bool,
        failure_type: str = "timeout",
        target_provider: Optional[str] = None,
        probability: float = 0.50
    ) -> Dict[str, Any]:
        self.enabled = enabled
        self.failure_type = failure_type
        self.target_provider = target_provider
        self.probability = probability
        logger.info(f"FailureInjector configured: enabled={self.enabled}, type={self.failure_type}, target={self.target_provider}, prob={self.probability}")
        return self.get_status()

    def get_status(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "failure_type": self.failure_type,
            "target_provider": self.target_provider,
            "probability": self.probability,
            "injected_events_count": self.injected_events_count
        }

    async def maybe_inject_fault(self, provider_key: str) -> None:
        """
        Conditionally throws synthetic failures if active.
        """
        if not self.enabled:
            return

        if self.target_provider and self.target_provider.lower() not in provider_key.lower():
            return

        if random.random() > self.probability:
            return

        self.injected_events_count += 1
        logger.warning(f"[CHAOS INJECTION] Simulating '{self.failure_type}' on provider '{provider_key}'!")

        if self.failure_type == "timeout":
            await asyncio.sleep(0.5)
            raise TimeoutError(f"Simulated Network Timeout on provider '{provider_key}' (Chaos Engine)")
            
        elif self.failure_type == "rate_limit":
            raise RuntimeError(f"HTTP 429 Too Many Requests: Rate Limit Reached for provider '{provider_key}' (Chaos Engine)")
            
        elif self.failure_type == "outage":
            raise ConnectionError(f"HTTP 503 Service Unavailable: Provider '{provider_key}' is experiencing an outage (Chaos Engine)")
            
        elif self.failure_type == "malformed_json":
            # Will cause JSON parser to fail in downstream nodes
            class MalformedResponse:
                content = "INTERNAL_SERVER_ERROR: <<<UNPARSABLE_NON_JSON_CORRUPTION>>>"
            return MalformedResponse()

failure_injector = FailureInjector()
