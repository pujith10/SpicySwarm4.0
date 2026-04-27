import json
import asyncio
from typing import Dict, Any
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from backend.pipeline.state import PipelineState
from dotenv import load_dotenv
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_experimental.utilities import PythonREPL
import logging

logger = logging.getLogger(__name__)

load_dotenv()

ANALYST_SYSTEM = """You are the HAA Analyst.
Your role is to execute the Architect's plan using your tools.
Tools available: 
- web_search: Search the live internet for data gaps.
- python_repl: Execute Python code for math, data processing, or logic verification.

Process the tasks one by one. Capture the output of each tool.
Output JSON:
{{
  "task_results": [
    {{"id": "t1", "tool": "web_search", "output": "result-1"}},
    {{"id": "t2", "tool": "python_repl", "output": "result-2"}}
  ],
  "preliminary_answer": "Drafted answer based on tools",
  "uncertainties": ["What still needs checking?"]
}}"""

REPL_TRANSLATOR_SYSTEM = """You are the HAA Python Translator (Sharp v4.0).
Convert the natural language research task into EXECUTABLE Python code.
- Output ONLY the raw code string.
- NO introductory text.
- NO markdown code blocks or backticks.
- Ensure all variables are defined or calculated directly.
Example Input: 'Calculate the product of 5 and 10'
Example Output: 5 * 10
"""

from backend.agents.utils import safe_llm_call

class AnalystAgent:
    def __init__(self):
        self.search = DuckDuckGoSearchRun()
        self.repl = PythonREPL()
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", ANALYST_SYSTEM),
            ("human", "Goal: {query}\nPlan: {plan}\nLibrarian Summary: {context}\n\nPREVIOUS ATTEMPTS (DO NOT REPEAT):\n{history}")
        ])

    async def run(self, state: PipelineState) -> Dict[str, Any]:
        plan = state.get("plan", {})
        # v4.0 Sharp uses 'subtasks' instead of 'tasks'
        tasks = plan.get("subtasks") or plan.get("tasks", [])
        
        if not tasks:
            logger.warning("Analyst (v4.0) received no subtasks. Skipping.")
            state["status"] = "Analyst skipped: No tasks"
            return state

        task_results = []
        state["status"] = f"v4.0 Analyst executing {len(tasks)} items..."

        for task in tasks:
            task_id = task.get("id")
            tool_type = task.get("tool")
            # v4.0 uses 'task' description field
            desc = task.get("task") or task.get("description", "Research")
            
            result = {"id": task_id, "tool": tool_type, "task": desc, "output": ""}
            
            try:
                if tool_type == "web_search":
                    output = await asyncio.to_thread(self.search.run, desc)
                    result["output"] = output
                elif tool_type == "python_repl":
                    # v4.0 Sharp: Translate natural language 'desc' to pure Python
                    translation_res = await safe_llm_call(
                        ChatPromptTemplate.from_messages([("system", REPL_TRANSLATOR_SYSTEM), ("human", "{input}")]),
                        {"input": desc}
                    )
                    code = translation_res.content.strip()
                    # Clean any accidental backticks
                    if code.startswith("```"):
                        code = code.split("\n")[1:-1]
                        code = "\n".join(code)
                    
                    logger.info(f"Analyst translating: '{desc}' -> '{code}'")
                    output = await asyncio.to_thread(self.repl.run, code)
                    result["output"] = output
                    result["code_executed"] = code
                else:
                    result["output"] = "Unsupported tool type"
            except Exception as e:
                result["output"] = f"Tool Error: {str(e)}"
            
            task_results.append(result)

        # v4.0 Sharp: Implementation of 'State Delta' (Uncertainty Analysis)
        # Prevent repetitive hallucinations by using a JSON schema for uncertainty tracking
        delta_prompt = f"""Analyze these results for goal: '{state['query']}'
Results: {json.dumps(task_results)}

Identify exactly 2 unique gaps or uncertainties.
Output JSON:
{{
  "delta": ["gap 1", "gap 2"]
}}"""
        
        try:
            delta_response = await safe_llm_call(
                ChatPromptTemplate.from_messages([("system", "You are the HAA State Delta Auditor. Output ONLY JSON."), ("human", "{input}")]),
                {"input": delta_prompt}
            )
            delta_json = delta_response.content.strip()
            # v4.0 Sharp: Universal JSON cleaning
            if "```" in delta_json:
                delta_json = delta_json.split("```")[-2].replace("json", "").strip()
            state_delta = json.loads(delta_json).get("delta", ["Review tools results"])
        except:
            state_delta = ["State analysis pending further verification"]

        state["execution"] = {
            "task_results": task_results,
            "state_delta": state_delta
        }
        state["state_delta"] = state_delta # Now a list, not a massive string
        state["status"] = "Analyst v4.0: Task results + State Delta generated"
        
        state["logs"].append({
            "stage": "analyst",
            "output": state["execution"]
        })
        
        return state

analyst = AnalystAgent()


