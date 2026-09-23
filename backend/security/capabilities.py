from enum import Enum
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
import time
import uuid

class RiskLevel(str, Enum):
    LOW = "LOW"           # Read-only information retrieval, internal calculations
    MEDIUM = "MEDIUM"     # Public search queries, standard API read calls
    HIGH = "HIGH"         # Arbitrary code execution, state modification, message sending
    CRITICAL = "CRITICAL" # Credential access, filesystem deletion, financial/external actions


class CapabilityToken(BaseModel):
    capability_id: str = Field(default_factory=lambda: f"cap_{uuid.uuid4().hex[:12]}")
    tool: str                                  # E.g. "web_search", "python_sandbox", "kg_search"
    allowed_action: str                        # E.g. "search", "execute_code", "query_triplets"
    allowed_parameters: List[str] = Field(default_factory=list) # List of permissible parameter keys
    requesting_agent: str                      # Agent authorized to use this token
    origin: str                                # Goal or parent task ID
    expiration: float                          # Epoch expiration timestamp
    scope: str                                 # Task scope / query domain
    risk_level: RiskLevel = RiskLevel.LOW
    is_revoked: bool = False

    def is_valid(self, agent: str, tool: str, action: str) -> bool:
        if self.is_revoked:
            return False
        if time.time() > self.expiration:
            return False
        if self.requesting_agent != agent:
            return False
        if self.tool != tool:
            return False
        if self.allowed_action != action and self.allowed_action != "*":
            return False
        return True


class CapabilityManager:
    """
    Central Capability Authority.
    Issues least-privilege capability tokens to agents before tool execution.
    """
    def __init__(self):
        self._active_tokens: Dict[str, CapabilityToken] = {}
        
        # Tool risk matrix
        self.tool_risk_matrix: Dict[str, RiskLevel] = {
            "web_search": RiskLevel.LOW,
            "kg_search": RiskLevel.LOW,
            "rag_search": RiskLevel.LOW,
            "calculator": RiskLevel.LOW,
            "python_sandbox": RiskLevel.HIGH, # Code execution is high risk
            "file_modify": RiskLevel.HIGH,
            "credential_access": RiskLevel.CRITICAL
        }

    def issue_capability(
        self,
        agent: str,
        tool: str,
        action: str,
        allowed_params: List[str],
        scope: str,
        ttl_seconds: int = 120
    ) -> CapabilityToken:
        risk = self.tool_risk_matrix.get(tool, RiskLevel.MEDIUM)
        
        token = CapabilityToken(
            tool=tool,
            allowed_action=action,
            allowed_parameters=allowed_params,
            requesting_agent=agent,
            origin=scope,
            expiration=time.time() + ttl_seconds,
            scope=scope,
            risk_level=risk
        )
        self._active_tokens[token.capability_id] = token
        return token

    def verify_capability(
        self,
        token_id: str,
        agent: str,
        tool: str,
        action: str
    ) -> bool:
        token = self._active_tokens.get(token_id)
        if not token:
            return False
        return token.is_valid(agent, tool, action)

    def revoke_capability(self, token_id: str) -> None:
        if token_id in self._active_tokens:
            self._active_tokens[token_id].is_revoked = True

capability_manager = CapabilityManager()
