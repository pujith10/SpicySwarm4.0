import os
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

class SwarmConfig(BaseModel):
    # System identification
    SYSTEM_NAME: str = "Spicy Swarm 4.0 (HAA Research Edition)"
    VERSION: str = "4.0.0"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    
    # Adaptive Refinement Hyperparameters
    MAX_CYCLES: int = int(os.getenv("MAX_CYCLES", "7"))
    MIN_CYCLES: int = int(os.getenv("MIN_CYCLES", "1"))
    QUALITY_DELTA_THRESHOLD: float = float(os.getenv("QUALITY_DELTA_THRESHOLD", "0.03"))  # Stop if score improves by < 3%
    SEMANTIC_CONVERGENCE_THRESHOLD: float = float(os.getenv("SEMANTIC_CONVERGENCE_THRESHOLD", "0.92")) # Stop if output draft is 92%+ identical
    MIN_ACCEPTABLE_QUALITY: float = float(os.getenv("MIN_ACCEPTABLE_QUALITY", "0.82")) # Critic quality threshold
    
    # Resource Budgets
    MAX_COST_USD: float = float(os.getenv("MAX_COST_USD", "0.50"))
    MAX_LATENCY_MS: float = float(os.getenv("MAX_LATENCY_MS", "45000")) # 45s hard budget
    MAX_TOOL_CALLS_PER_TASK: int = int(os.getenv("MAX_TOOL_CALLS_PER_TASK", "10"))
    
    # Security Configuration
    SECURITY_LEVEL: str = os.getenv("SECURITY_LEVEL", "HIGH") # LOW, MEDIUM, HIGH, STRICT
    REQUIRE_APPROVAL_FOR_HIGH_RISK: bool = os.getenv("REQUIRE_APPROVAL_FOR_HIGH_RISK", "true").lower() == "true"
    UNTRUSTED_CONTENT_TOOL_EXECUTION: bool = False # Absolute policy: untrusted data cannot authorize tool execution
    ALLOW_PYTHON_REPL: bool = os.getenv("ALLOW_PYTHON_REPL", "true").lower() == "true"
    PYTHON_EXECUTION_TIMEOUT_SECS: int = 5
    SCRUBBING_ENABLED: bool = os.getenv("SCRUBBING_ENABLED", "true").lower() == "true"
    
    # Resilience & Circuit Breaker Settings
    CIRCUIT_BREAKER_FAILURE_THRESHOLD: int = 3
    CIRCUIT_BREAKER_RECOVERY_TIMEOUT_SECS: int = 30
    HEALTH_CHECK_INTERVAL_SECS: int = 60
    
    # Models & Providers
    OPENROUTER_API_KEY: Optional[str] = os.getenv("OPENROUTER_API_KEY")
    OPENROUTER_BASE_URL: str = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    DEFAULT_PRIMARY_MODEL: str = os.getenv("PRIMARY_MODEL", "gemini-1.5-flash")
    DEFAULT_SECONDARY_MODEL: str = os.getenv("SECONDARY_MODEL", "llama-3.3-70b-versatile")
    DEFAULT_TERTIARY_MODEL: str = os.getenv("TERTIARY_MODEL", "llama-3.1-8b-instant")
    
    # Denied Domains for Web Navigation/Search
    DENIED_DOMAINS: List[str] = Field(default_factory=lambda: [
        "malicious.test", "phishing.test", "internal.corp", "localhost", "127.0.0.1", "0.0.0.0",
        "metadata.google.internal", "169.254.169.254"
    ])

config = SwarmConfig()
