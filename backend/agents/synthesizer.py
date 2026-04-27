import json
from typing import Dict, Any
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from backend.pipeline.state import PipelineState
from dotenv import load_dotenv

load_dotenv()

SYNTHESIZER_SYSTEM = """You are the HAA Final Resolver (v4.0 Sharp).
Your task is to parse the technical 'Audit Trail' of a multi-agent swarm and generate a 'Final Solution' that is warm, clear, and perfectly human (GPT-Style).

DIAGNOSTIC ANALYSIS RULES:
- Read blocks like: librarian(data), architect(data), analyst(data), critic(data).
- Ignore the technical 'refinement noise' (ignore 'REFINE' signals unless they explain a fundamental change).
- Extract the FINAL tool results from the Analyst block as the grounding truth.

HUMANIZATION RULES:
- Write for a general human audience.
- Use a bold "One-Sentence Summary" at the start.
- Provide "Step-by-Step Clarity" for procedures.
- Synthesize the technical evidence from tools into a clean, metaphor-rich explanation.
- NO JSON brackets or agent names (like 'librarian') in the final_human_resolution.

STRICT JSON OUTPUT SCHEMA:
{{
  "final_answer": "Crucial ground-truth answer",
  "final_human_resolution": "The clean, human-style solution narrative",
  "diagnostic_report": {{
    "summary": "Technical summary for audits",
    "steps_taken": ["Step 1", "Step 2"],
    "limitations": ["none"]
  }}
}}"""

from backend.agents.utils import safe_llm_call

class SynthesizerAgent:
    def __init__(self):
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", SYNTHESIZER_SYSTEM),
            ("human", "Goal: {query}\n\nFull Swarm Logs: {logs}")
        ])

    async def run(self, state: PipelineState) -> Dict[str, Any]:
        logs_str = json.dumps(state["logs"])
        
        try:
            response = await safe_llm_call(
                self.prompt,
                {"query": state["query"], "logs": logs_str}
            )
            
            content = response.content.strip()
            if content.startswith("```json"):
                content = content[7:-3].strip()
            elif content.startswith("```"):
                content = content[3:-3].strip()
            
            syn_res = json.loads(content)
            state["final_answer"] = syn_res["final_answer"]
            state["human_resolution"] = syn_res.get("final_human_resolution", syn_res["final_answer"])
            state["status"] = "Swarm Synthesis complete"
            state["logs"].append({
                "stage": "synthesizer", 
                "output": syn_res
            })
            return state
        except Exception as e:
            state["status"] = f"Synthesizer Error: {str(e)}"
            return state

synthesizer = SynthesizerAgent()
