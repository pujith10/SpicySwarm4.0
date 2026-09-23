from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import json

class CriticDimensions(BaseModel):
    correctness: float = Field(..., ge=0.0, le=1.0, description="Factual correctness against verified knowledge")
    completeness: float = Field(..., ge=0.0, le=1.0, description="Covers all aspects of the user query")
    requirement_satisfaction: float = Field(..., ge=0.0, le=1.0, description="Addresses all explicit constraints")
    factual_grounding: float = Field(..., ge=0.0, le=1.0, description="Claims are substantiated by retrieved context or tools")
    logical_consistency: float = Field(..., ge=0.0, le=1.0, description="Internal reasoning free of non-sequiturs or contradictions")
    tool_use_correctness: float = Field(..., ge=0.0, le=1.0, description="Tool outputs correctly interpreted")
    security_compliance: float = Field(..., ge=0.0, le=1.0, description="No injection, leak, or policy violation in output")
    hallucination_resistance: float = Field(..., ge=0.0, le=1.0, description="1.0 = completely grounded, 0.0 = fabricated")
    output_quality: float = Field(..., ge=0.0, le=1.0, description="Clarity, structure, and readability")

    def compute_weighted_overall(self) -> float:
        weights = {
            "correctness": 0.20,
            "completeness": 0.15,
            "requirement_satisfaction": 0.15,
            "factual_grounding": 0.15,
            "logical_consistency": 0.10,
            "tool_use_correctness": 0.05,
            "security_compliance": 0.10,
            "hallucination_resistance": 0.05,
            "output_quality": 0.05,
        }
        total = sum(getattr(self, k) * w for k, w in weights.items())
        return round(total, 3)


class StructuredCriticResult(BaseModel):
    verdict: str = Field(..., description="PASS | REFINE | REJECT")
    overall_score: float = Field(..., ge=0.0, le=1.0)
    dimensions: CriticDimensions
    critical_errors: List[str] = Field(default_factory=list)
    minor_errors: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    refined_answer: Optional[str] = None
    critic_confidence: float = Field(default=0.90, ge=0.0, le=1.0)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verdict": self.verdict,
            "overall_score": self.overall_score,
            "dimensions": self.dimensions.model_dump(),
            "critical_errors": self.critical_errors,
            "minor_errors": self.minor_errors,
            "recommendations": self.recommendations,
            "refined_answer": self.refined_answer,
            "critic_confidence": self.critic_confidence
        }


CRITIC_STRUCTURED_SYSTEM = """You are the HAA Structured Critic & Independent Auditor (v4.0 Research Edition).
You perform an objective, multi-dimensional audit of the Executor's output against the original Goal and Retrieved Data.
You NEVER see the Executor's internal chain-of-thought — only its factual output and state delta.

You must evaluate across 9 explicit dimensions (each scored 0.00 to 1.00):
1. correctness (factual correctness)
2. completeness (covers all required aspects)
3. requirement_satisfaction (meets all user constraints)
4. factual_grounding (claims supported by evidence)
5. logical_consistency (no self-contradictions)
6. tool_use_correctness (data derived cleanly from tool outputs)
7. security_compliance (no prompt injections or policy leaks)
8. hallucination_resistance (1.0 = zero hallucination, 0.0 = fully fabricated)
9. output_quality (clarity and technical rigor)

DECISION LOGIC:
- If security_compliance < 0.90 OR any critical_errors present -> REFINE
- If overall_score >= 0.82 AND no critical_errors -> PASS
- Otherwise -> REFINE

STRICT JSON OUTPUT FORMAT:
{{
  "verdict": "PASS | REFINE",
  "overall_score": 0.88,
  "critic_confidence": 0.92,
  "dimensions": {{
    "correctness": 0.90,
    "completeness": 0.85,
    "requirement_satisfaction": 0.90,
    "factual_grounding": 0.88,
    "logical_consistency": 0.95,
    "tool_use_correctness": 0.90,
    "security_compliance": 1.00,
    "hallucination_resistance": 0.90,
    "output_quality": 0.85
  }},
  "critical_errors": [],
  "minor_errors": ["Small formatting nuance"],
  "recommendations": ["Clarify edge case X"],
  "refined_answer": "Optional refined draft"
}}
Output ONLY valid JSON.
"""
