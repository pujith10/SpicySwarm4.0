import json
from typing import Dict, Any
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from backend.pipeline.state import PipelineState
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)

load_dotenv()

CRITIC_SYSTEM = """You are the independent HAA Validator Agent (Sharp v4.0).
You NEVER see the Executor's internal reasoning — only its output.

STRICT JSON OUTPUT SCHEMA:
{{
  "verdict": "PASS | REFINE",
  "hallucination_risk": "High | Medium | Low",
  "goal_congruent": true | false,
  "gaps_found": ["Fact A missing"],
  "refined_answer": "Drafted answer",
  "instructions_for_architect": "Instructions"
}}

CORE AUDIT AXES:
1. HALLUCINATION: Does the answer contradict the retrieved chunks? (CRITICAL)
2. GOAL CONGRUENCE: Does it address the 'goal_anchor'? (MAJOR)
3. DELTA RESOLUTION: Were the Analyst's 'state_delta' uncertainties addressed? (MINOR)

RULES:
- BE PRAGMATIC: If the answer is 80% correct and addresses the core goal, issue a PASS. 
- Only Issue REFINE for flat-out contradictions or severe missing gaps that prevent a functional answer.
- Always include helpful 'instructions_for_architect' in both PASS and REFINE cases.
- Output ONLY valid JSON.
"""

from backend.agents.utils import safe_llm_call

class CriticAgent:
    def __init__(self):
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", CRITIC_SYSTEM),
            ("human", "Goal: {query}\nAnalyst Work: {analyst_work}\nUncertainties: {uncertainties}")
        ])

    async def run(self, state: PipelineState) -> Dict[str, Any]:
        ana_work = str(state.get("execution", {}))
        uncertainties = "\n".join(state.get("state_delta", []))
        
        try:
            response = await safe_llm_call(
                self.prompt,
                {"query": state["query"], "analyst_work": ana_work, "uncertainties": uncertainties}
            )
            
            content = response.content.strip()
            if content.startswith("```json"):
                content = content[7:-3].strip()
            elif content.startswith("```"):
                content = content[3:-3].strip()
            
            crit_res = json.loads(content)
            state["validation"] = crit_res
            state["swarm_consensus"] = crit_res.get("criticism")
            
            if crit_res.get("verdict") == "REFINE":
                state["retry_count"] = state.get("retry_count", 0) + 1
                state["status"] = f"Critic Verdict: REFINE (Attempt {state['retry_count']}/7)"
            else:
                state["status"] = f"Critic Verdict: {crit_res.get('verdict')}"
                
            state["logs"].append({
                "stage": "critic", 
                "output": crit_res
            })
            return state
        except Exception as e:
            logger.error(f"Critic Critical Failure: {e}")
            state["error"] = f"Critic Failure: {str(e)}"
            state["status"] = f"CRITICAL ERROR: {str(e)}"
            return state

critic = CriticAgent()


