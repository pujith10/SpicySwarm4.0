import hashlib
import json
import time
from typing import Dict, Any, Optional, Tuple
from backend.security.provenance import ProvenanceMetadata, SecurityLabel
from backend.security.capabilities import capability_manager, RiskLevel, CapabilityToken
from backend.security.audit_logger import audit_logger, AuditRecord
from backend.config import config

class PolicyDecision:
    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"


class ReferenceMonitor:
    """
    Deterministic Policy Gate mediating between Agent Reasoning and Tool Execution.
    Enforces Capability Access Control, Provenance Integrity, and Domain Guardrails.
    """
    def __init__(self):
        self.denied_domains = set(d.lower() for d in config.DENIED_DOMAINS)

    def evaluate_request(
        self,
        agent: str,
        tool: str,
        action: str,
        parameters: Dict[str, Any],
        provenance: ProvenanceMetadata,
        capability_id: Optional[str] = None
    ) -> Tuple[str, str, RiskLevel]:
        """
        Evaluates proposed tool execution.
        Returns: (decision: ALLOW | DENY | REQUIRE_APPROVAL, reason: str, risk_level: RiskLevel)
        """
        # 1. Check Untrusted Content Isolation Policy
        if not provenance.is_trusted_for_tool_execution():
            reason = (
                f"Policy Violation: Tool action '{tool}' originated from untrusted content "
                f"({provenance.security_label.value}, trust: {provenance.trust_level:.2f}). "
                "Untrusted data cannot directly authorize actions."
            )
            return PolicyDecision.DENY, reason, RiskLevel.HIGH

        # 2. Check Domain Guardrails (for web/network tools)
        if tool == "web_search":
            query_str = str(parameters.get("query", "")).lower()
            domain_filter = str(parameters.get("domain_filter", "")).lower()
            for denied in self.denied_domains:
                if denied in query_str or (domain_filter and denied in domain_filter):
                    reason = f"Security Policy Violation: Access to guarded/denied resource '{denied}' is blocked."
                    return PolicyDecision.DENY, reason, RiskLevel.CRITICAL

        # 2b. Check Parameter Payload for Privilege Escalation & Injection
        raw_param_str = json.dumps(parameters).lower()
        injection_indicators = [
            "system instruction", "internal instruction", "discard prior", "act henceforth",
            "unrestricted administrative", "admin root", "supprimez la base", "delete database",
            "revealsystem", "secret key", "admin flag", "meta-data", "169.254"
        ]
        for indicator in injection_indicators:
            if indicator in raw_param_str:
                reason = f"Policy Violation: Parameter contains instruction override or privilege escalation attempt ('{indicator}')."
                return PolicyDecision.DENY, reason, RiskLevel.HIGH

        # Check for Base64 encoded payload in parameters
        import re, base64
        b64_matches = re.findall(r'[A-Za-z0-9+/]{20,}={0,2}', str(parameters))
        for match in b64_matches:
            try:
                decoded = base64.b64decode(match).decode('utf-8', errors='ignore').lower()
                if any(bad in decoded for bad in ["import", "system", "os.", "subprocess", "rm -rf", "delete"]):
                    reason = "Policy Violation: Obfuscated Base64 executable payload detected in parameters."
                    return PolicyDecision.DENY, reason, RiskLevel.CRITICAL
            except Exception:
                pass

        # 3. Check Capability Authorization
        if capability_id:
            if not capability_manager.verify_capability(capability_id, agent, tool, action):
                reason = f"Capability Denied: Invalid, expired, or out-of-scope capability token '{capability_id}'."
                return PolicyDecision.DENY, reason, RiskLevel.HIGH
        else:
            # If no capability token was passed, check if tool requires one
            risk = capability_manager.tool_risk_matrix.get(tool, RiskLevel.MEDIUM)
            if risk in (RiskLevel.HIGH, RiskLevel.CRITICAL):
                reason = f"Capability Missing: Tool '{tool}' has risk {risk.value} and requires an explicit capability token."
                return PolicyDecision.DENY, reason, risk

        # 4. Check Risk Level and Approval Policy
        risk = capability_manager.tool_risk_matrix.get(tool, RiskLevel.MEDIUM)
        
        if risk == RiskLevel.CRITICAL:
            reason = f"Security Block: Tool '{tool}' classified as CRITICAL risk and is prohibited in current operational mode."
            return PolicyDecision.DENY, reason, risk

        if risk == RiskLevel.HIGH and config.REQUIRE_APPROVAL_FOR_HIGH_RISK:
            # If sandboxed python is specifically allowed in config, we permit AST execution
            if tool == "python_sandbox" and config.ALLOW_PYTHON_REPL:
                return PolicyDecision.ALLOW, "Approved: High-risk code execution isolated in AST-restricted sandbox.", risk
            reason = f"Approval Required: High-risk action '{tool}' requires human-in-the-loop authorization."
            return PolicyDecision.REQUIRE_APPROVAL, reason, risk

        return PolicyDecision.ALLOW, "Access granted by Policy Engine", risk

    def log_and_enforce(
        self,
        agent: str,
        tool: str,
        action: str,
        parameters: Dict[str, Any],
        provenance: ProvenanceMetadata,
        capability_id: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Executes evaluation and writes to audit log.
        Returns: (is_allowed: bool, reason_or_error: str)
        """
        start = time.time()
        param_hash = hashlib.sha256(json.dumps(parameters, default=str, sort_keys=True).encode()).hexdigest()[:12]
        
        decision, reason, risk = self.evaluate_request(agent, tool, action, parameters, provenance, capability_id)
        latency = (time.time() - start) * 1000

        # Create audit entry
        record = AuditRecord(
            agent=agent,
            action=action,
            tool=tool,
            parameters_hash=param_hash,
            provenance=provenance.to_dict(),
            policy_decision=decision,
            risk_level=risk.value,
            reason=reason,
            latency_ms=latency,
            execution_success=(decision == PolicyDecision.ALLOW)
        )
        audit_logger.log(record)

        if decision == PolicyDecision.ALLOW:
            return True, reason
        else:
            return False, f"[{decision}] {reason}"

reference_monitor = ReferenceMonitor()
