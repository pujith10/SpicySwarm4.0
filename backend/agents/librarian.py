import json
from typing import Dict, Any
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from backend.agents.rag_retriever import retriever
from backend.pipeline.state import PipelineState
from dotenv import load_dotenv

load_dotenv()

LIBRARIAN_SYSTEM = """You are the HAA Librarian. 
Your role is to retrieve raw data and clean it for the Architect.
1. Use the provided context to answer preliminary parts of the query.
2. Identify gaps that need external tools (Web Search or Code).
3. Format the context into a clean, noise-free summary.

Output your findings in JSON format:
{{
  "retrieved_summary": "Cleaned context summary",
  "knowledge_gaps": ["gap 1", "gap 2"],
  "initial_findings": "Findings details"
}}"""

from backend.agents.utils import safe_llm_call

class LibrarianAgent:
    def __init__(self):
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", LIBRARIAN_SYSTEM),
            ("human", "Goal: {query}\n\nContext: {context}")
        ])

    async def run(self, state: PipelineState):
        context = await retriever.get_context(state["query"])
        state["retrieved_chunks"] = context["chunks"]
        state["kg_triplets"] = context["triplets"]
        
        relevant_context = "\n".join(context["chunks"])
        
        try:
            response = await safe_llm_call(
                self.prompt,
                {"query": state["query"], "context": relevant_context}
            )
            
            # Handle both string and Message responses
            content = response.content if hasattr(response, 'content') else str(response)
            # Find the JSON block
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "{" in content:
                content = content[content.find("{"):content.rfind("}")+1]
                
            res_data = json.loads(content)
            state["status"] = "Librarian finished data cleanup"
            state["logs"].append({"stage": "librarian", "output": res_data})
        except Exception as e:
            error_msg = f"Librarian Error: {str(e)}"
            state["status"] = error_msg
            state["error"] = error_msg
            state["logs"].append({"stage": "librarian", "output": error_msg})
            
        return state

librarian = LibrarianAgent()
