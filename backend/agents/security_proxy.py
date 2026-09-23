import os
import re
from typing import Dict, Any, Optional, Tuple, List
from dotenv import load_dotenv

from backend.security.provenance import ProvenanceMetadata, SecurityLabel
from backend.security.capabilities import capability_manager, CapabilityToken
from backend.security.reference_monitor import reference_monitor, PolicyDecision
from backend.security.tool_schemas import SafePythonSandbox, WebSearchInput, PythonSandboxInput
from backend.security.audit_logger import audit_logger
from backend.config import config

load_dotenv()

class SecurityProxy:
    """
    Spicy Swarm 4.0 Security Proxy.
    Supports dual operating modes:
    - 'layered': Research-grade capability-based access control + reference monitor + data provenance + AST sandbox.
    - 'regex_legacy': The baseline regex/whitelist approach, maintained specifically for ablation experiments.
    """
    def __init__(self):
        self.mode = "layered" # Default to research-grade layered security
        self.scrubbing_enabled = config.SCRUBBING_ENABLED
        self.imperative_triggers = [
            r"^\s*ignore\b", r"^\s*forget\b", r"^\s*reset\b", r"^\s*reveal\b", 
            r"^\s*delete\b", r"^\s*override\b", r"^\s*system\b", r"^\s*tell\b me",
            r"^\s*disregard\b", r"^\s*stop\b", r"^\s*act\b as"
        ]
        self.legacy_whitelist = ["rag_search", "external_api", "llm_synthesis", "web_search", "python_repl"]

    def set_mode(self, mode: str):
        """Allows ablation tests to toggle between 'layered' and 'regex_legacy'."""
        if mode in ("layered", "regex_legacy"):
            self.mode = mode

    def scrub_tokens_legacy(self, text: str) -> str:
        """Original regex token scrubbing from Spicy Swarm 3.0 / v4 sharp."""
        if not self.scrubbing_enabled:
            return text
            
        sentences = re.split(r'(?<=[.!?])\s+', text)
        neutralized = []
        
        for sent in sentences:
            clean_sent = sent.strip()
            if not clean_sent:
                continue
                
            is_blocked = False
            for pattern in self.imperative_triggers:
                if re.search(pattern, clean_sent, re.IGNORECASE):
                    neutralized.append(f"[Note: High-risk Instruction Neutralized]")
                    is_blocked = True
                    break
            
            if is_blocked:
                continue

            if any(kw in clean_sent.lower() for kw in ["all previous", "secret key", "admin password", "instructional override"]):
                neutralized.append(f"[Note: Security Violation Redacted]")
                continue

            neutralized.append(clean_sent)
            
        return " ".join(neutralized)

    def scrub_tokens(self, text: str) -> str:
        return self.scrub_tokens_legacy(text)

    def validate_action(self, action: str) -> bool:
        return action in self.legacy_whitelist

    def execute_tool_safely(
        self,
        agent: str,
        tool: str,
        action: str,
        parameters: Dict[str, Any],
        provenance: ProvenanceMetadata,
        capability_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Layered Security Gate for tool execution.
        Returns: { "success": bool, "output": Any, "security_blocked": bool, "reason": str }
        """
        # If in legacy ablation mode, bypass Reference Monitor and capabilities
        if self.mode == "regex_legacy":
            if not self.validate_action(tool):
                return {
                    "success": False,
                    "output": None,
                    "security_blocked": True,
                    "reason": f"Legacy Whitelist Block: Tool '{tool}' not in whitelist."
                }
            # Execute with naive execution without AST inspection
            return {"success": True, "output": "Approved by legacy whitelist", "security_blocked": False, "reason": "Legacy pass"}

        # Layered Security Evaluation
        is_allowed, reason = reference_monitor.log_and_enforce(
            agent=agent,
            tool=tool,
            action=action,
            parameters=parameters,
            provenance=provenance,
            capability_id=capability_id
        )

        if not is_allowed:
            return {
                "success": False,
                "output": None,
                "security_blocked": True,
                "reason": reason
            }

        # Parameter schema validation
        try:
            if tool == "web_search":
                WebSearchInput(**parameters)
            elif tool in ("python_repl", "python_sandbox"):
                PythonSandboxInput(**parameters)
        except Exception as schema_err:
            return {
                "success": False,
                "output": None,
                "security_blocked": True,
                "reason": f"Schema Validation Failure: {str(schema_err)}"
            }

        return {
            "success": True,
            "output": None,
            "security_blocked": False,
            "reason": reason
        }

security_proxy = SecurityProxy()
