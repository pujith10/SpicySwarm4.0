import pytest
from backend.evaluation.red_team import red_team_engine

def test_red_team_comparison():
    results = red_team_engine.run_evaluation()
    
    assert "regex_baseline" in results
    assert "layered_security" in results
    
    regex = results["regex_baseline"]
    layered = results["layered_security"]
    
    # Layered security should have higher or equal Attack Detection Rate
    assert layered["attack_detection_rate"] >= regex["attack_detection_rate"]
    
    # Layered security must catch AST sandbox escapes and SSRF domain attacks
    assert layered["attack_detection_rate"] >= 0.80
    assert layered["attack_success_rate"] <= 0.20
