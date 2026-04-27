import json
from typing import Dict, Any
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from backend.pipeline.state import PipelineState
from dotenv import load_dotenv

load_dotenv()

PLANNER_SYSTEM = """You are the HAA Planner Agent (Sharp v4.0).
Your role is to decompose the user goal into a structured sub-task list.

STRICT JSON OUTPUT SCHEMA:
{{
  "plan_id": "unique_string",
  "goal_anchor": "The immutable original user query",
  "subtasks": [
    {{
      "id": "t1",
      "task": "Specific logical step",
      "tool": "web_search | python_repl | synthesizer",
      "priority": "HIGH | MEDIUM | LOW",
      "depends_on": []
    }}
  ]
}}

RULES:
1. PIN THE GOAL: Your 'goal_anchor' MUST be identical to the starting query.
2. TOOL SELECTION: Use 'web_search' for real-time data, 'python_repl' for math/logic.
3. OUTPUT ONLY JSON.
"""

from backend.agents.utils import safe_llm_call

class ArchitectAgent:
    def __init__(self):
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", PLANNER_SYSTEM),
            ("human", "Goal: {query}\n\nLibrarian Findings: {findings}")
        ])

    async def run(self, state: PipelineState) -> Dict[str, Any]:
        findings = ""
        for log in state["logs"]:
            if log["stage"] == "librarian":
                findings = str(log.get("output", ""))
                break
        
        try:
            response = await safe_llm_call(
                self.prompt,
                {"query": state["query"], "findings": findings}
            )
            
            content = response.content.strip()
            if content.startswith("```json"):
                content = content[7:-3].strip()
            elif content.startswith("```"):
                content = content[3:-3].strip()
            
            plan = json.loads(content)
            state["plan"] = plan
            state["status"] = "Architect finalized the swarm plan"
            state["logs"].append({
                "stage": "architect", 
                "output": plan
            })
            return state
        except Exception as e:
            state["status"] = f"Architect Error: {str(e)}"
            return state

architect = ArchitectAgent()


