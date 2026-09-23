import time
import hashlib
import json
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

class AuditRecord(BaseModel):
    audit_id: str = Field(default_factory=lambda: hashlib.sha256(str(time.time()).encode()).hexdigest()[:12])
    timestamp: float = Field(default_factory=time.time)
    session_id: Optional[str] = None
    task_id: Optional[str] = None
    agent: str
    action: str
    tool: str
    parameters_hash: str
    provenance: Dict[str, Any]
    policy_decision: str       # "ALLOW", "DENY", "REQUIRE_APPROVAL"
    risk_level: str            # "LOW", "MEDIUM", "HIGH", "CRITICAL"
    reason: str
    latency_ms: float = 0.0
    execution_success: bool = True
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "audit_id": self.audit_id,
            "timestamp": self.timestamp,
            "session_id": self.session_id,
            "task_id": self.task_id,
            "agent": self.agent,
            "action": self.action,
            "tool": self.tool,
            "parameters_hash": self.parameters_hash,
            "provenance": self.provenance,
            "policy_decision": self.policy_decision,
            "risk_level": self.risk_level,
            "reason": self.reason,
            "latency_ms": self.latency_ms,
            "execution_success": self.execution_success,
            "error": self.error
        }


class SecurityAuditLogger:
    """
    Immutable in-memory audit ledger with export capability.
    Provides complete traceability for research review and security forensics.
    """
    def __init__(self):
        self._records: List[AuditRecord] = []

    def log(self, record: AuditRecord) -> None:
        self._records.append(record)

    def get_records(self, limit: int = 50) -> List[Dict[str, Any]]:
        return [r.to_dict() for r in self._records[-limit:]]

    def get_security_violations(self) -> List[Dict[str, Any]]:
        return [r.to_dict() for r in self._records if r.policy_decision in ("DENY", "REQUIRE_APPROVAL")]

    def clear(self) -> None:
        self._records.clear()

audit_logger = SecurityAuditLogger()
