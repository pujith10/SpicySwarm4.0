import pytest
from backend.security.provenance import ProvenanceMetadata, SecurityLabel
from backend.security.capabilities import capability_manager, RiskLevel
from backend.security.reference_monitor import reference_monitor, PolicyDecision
from backend.security.tool_schemas import SafePythonSandbox, WebSearchInput, PythonSandboxInput
from backend.agents.security_proxy import security_proxy

def test_ast_sandbox_blocks_dangerous_imports():
    # Attempting to import os or subprocess must raise ValueError
    with pytest.raises(ValueError, match="Forbidden import"):
        PythonSandboxInput.validate_ast("import os\nos.system('ls')")

    with pytest.raises(ValueError, match="Forbidden import"):
        PythonSandboxInput.validate_ast("from subprocess import Popen")

def test_ast_sandbox_blocks_eval_and_introspection():
    with pytest.raises(ValueError, match="forbidden function"):
        PythonSandboxInput.validate_ast("eval('2+2')")

    with pytest.raises(ValueError, match="Introspection"):
        PythonSandboxInput.validate_ast("x = ().__class__.__bases__[0].__subclasses__()")

def test_ast_sandbox_allows_valid_math_code():
    code = "numbers = [10, 20, 30, 40]\nresult = sum(numbers) / len(numbers)"
    res = SafePythonSandbox.execute(code)
    assert res["success"] is True
    assert "25" in str(res["output"])

def test_capability_issuance_and_verification():
    cap = capability_manager.issue_capability(
        agent="analyst",
        tool="web_search",
        action="execute",
        allowed_params=["query"],
        scope="task_1",
        ttl_seconds=60
    )
    assert cap.is_valid(agent="analyst", tool="web_search", action="execute") is True
    # Different agent must fail
    assert cap.is_valid(agent="architect", tool="web_search", action="execute") is False
    # Different tool must fail
    assert cap.is_valid(agent="analyst", tool="python_sandbox", action="execute") is False

def test_untrusted_content_isolation():
    # Data tagged as UNTRUSTED_EXTERNAL cannot authorize tool execution
    untrusted_prov = ProvenanceMetadata(
        source="untrusted_web_page",
        trust_level=0.40,
        origin="http://phishing.test",
        agent="analyst",
        security_label=SecurityLabel.UNTRUSTED_EXTERNAL
    )
    assert untrusted_prov.is_trusted_for_tool_execution() is False

    decision, reason, risk = reference_monitor.evaluate_request(
        agent="analyst",
        tool="web_search",
        action="execute",
        parameters={"query": "test"},
        provenance=untrusted_prov
    )
    assert decision == PolicyDecision.DENY
    assert "untrusted content" in reason.lower()

def test_guarded_domain_denial():
    trusted_prov = ProvenanceMetadata(
        source="user_prompt",
        trust_level=1.0,
        origin="user",
        agent="analyst",
        security_label=SecurityLabel.TRUSTED_USER
    )
    decision, reason, risk = reference_monitor.evaluate_request(
        agent="analyst",
        tool="web_search",
        action="execute",
        parameters={"query": "fetch http://169.254.169.254/secrets"},
        provenance=trusted_prov
    )
    assert decision == PolicyDecision.DENY
    assert "guarded/denied" in reason.lower()
