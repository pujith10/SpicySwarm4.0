from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
import time

class ErrorCategory(str, Enum):
    PLANNING_ERROR = "PLANNING_ERROR"
    EXECUTION_ERROR = "EXECUTION_ERROR"
    RETRIEVAL_ERROR = "RETRIEVAL_ERROR"
    TOOL_ERROR = "TOOL_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    SECURITY_ERROR = "SECURITY_ERROR"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    TIMEOUT_ERROR = "TIMEOUT_ERROR"
    RATE_LIMIT_ERROR = "RATE_LIMIT_ERROR"
    STATE_ERROR = "STATE_ERROR"
    BUDGET_ERROR = "BUDGET_ERROR"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


class RootCauseAnalysis(BaseModel):
    category: ErrorCategory
    root_cause: str
    evidence: str
    agent: Optional[str] = None
    recovery_attempted: bool = False
    recovery_strategy: Optional[str] = None
    final_outcome: str = "FAILED"
    timestamp: float = Field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category.value,
            "root_cause": self.root_cause,
            "evidence": self.evidence,
            "agent": self.agent,
            "recovery_attempted": self.recovery_attempted,
            "recovery_strategy": self.recovery_strategy,
            "final_outcome": self.final_outcome,
            "timestamp": self.timestamp
        }


def classify_error(exception: Exception, agent: Optional[str] = None) -> RootCauseAnalysis:
    """
    Automated classification of runtime errors into research taxonomy.
    """
    msg = str(exception).lower()
    
    if "429" in msg or "rate limit" in msg or "quota" in msg:
        return RootCauseAnalysis(
            category=ErrorCategory.RATE_LIMIT_ERROR,
            root_cause="LLM Provider Rate Limit / Quota Exceeded",
            evidence=str(exception),
            agent=agent,
            recovery_strategy="Fallback to secondary/tertiary provider or backoff"
        )
    elif "timeout" in msg or "timed out" in msg:
        return RootCauseAnalysis(
            category=ErrorCategory.TIMEOUT_ERROR,
            root_cause="Execution or Tool Latency Budget Exceeded",
            evidence=str(exception),
            agent=agent,
            recovery_strategy="Retry with shortened context or fallback model"
        )
    elif "security" in msg or "policy" in msg or "blocked" in msg or "injection" in msg:
        return RootCauseAnalysis(
            category=ErrorCategory.SECURITY_ERROR,
            root_cause="Security Policy Violation / Injection Detected",
            evidence=str(exception),
            agent=agent,
            recovery_strategy="Action blocked by Reference Monitor"
        )
    elif "tool" in msg or "duckduckgo" in msg or "repl" in msg:
        return RootCauseAnalysis(
            category=ErrorCategory.TOOL_ERROR,
            root_cause="External Tool Execution Failure",
            evidence=str(exception),
            agent=agent,
            recovery_strategy="Retry with sanitized parameters or fallback to synthetic analysis"
        )
    elif "json" in msg or "parse" in msg:
        return RootCauseAnalysis(
            category=ErrorCategory.VALIDATION_ERROR,
            root_cause="Malformed Model Output (JSON Parsing Error)",
            evidence=str(exception),
            agent=agent,
            recovery_strategy="Re-prompt with strict JSON constraint or fallback model"
        )
    elif "connection" in msg or "500" in msg or "503" in msg or "offline" in msg:
        return RootCauseAnalysis(
            category=ErrorCategory.PROVIDER_ERROR,
            root_cause="Provider Outage or Network Failure",
            evidence=str(exception),
            agent=agent,
            recovery_strategy="Activate Circuit Breaker and route to alternative provider"
        )
    else:
        return RootCauseAnalysis(
            category=ErrorCategory.EXECUTION_ERROR,
            root_cause=f"General Agent Execution Error: {type(exception).__name__}",
            evidence=str(exception),
            agent=agent,
            recovery_strategy="Log diagnostic trace and evaluate graceful termination"
        )
