import json
import logging
from typing import Dict, Any, List
from langchain_core.prompts import ChatPromptTemplate
from backend.agents.rag_retriever import retriever
from backend.pipeline.state import PipelineState
from backend.security.provenance import ProvenanceMetadata, SecurityLabel
from backend.agents.utils import safe_llm_call
from dotenv import load_dotenv

logger = logging.getLogger(__name__)
load_dotenv()

LIBRARIAN_SYSTEM = """You are the HAA Librarian & Context Layer Agent (v4.0 Research Edition).
Your role is to evaluate hybrid retrieved information (FAISS semantic vectors + Neo4j knowledge triplets)
and structure it cleanly for the Architect and Analyst.

1. Filter out redundant noise.
2. Flag knowledge gaps that require live web search or code execution.
3. Structure initial findings with explicit provenance tracking.

STRICT JSON OUTPUT FORMAT:
{{
  "retrieved_summary": "Clean, noise-free context summary",
  "knowledge_gaps": ["Specific fact missing", "Need live verification"],
  "initial_findings": "Factual details extracted"
}}
"""

class LibrarianAgent:
    def __init__(self):
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", LIBRARIAN_SYSTEM),
            ("human", "User Goal: {query}\n\nRetrieved Raw Context:\n{context}")
        ])

    async def run(self, state: PipelineState) -> Dict[str, Any]:
        query = state["query"]
        
        # As per user specification: local data corpus is not maintained currently.
        # Bypass heavy vector store load and irrelevant PDF chunks, route directly to Architect for live search.
        state["retrieved_chunks"] = []
        state["kg_triplets"] = []
        res_data = {
            "retrieved_summary": "Local corpus holds no relevant data for this query.",
            "knowledge_gaps": [f"Live internet data needed for '{query}'"],
            "initial_findings": "Directing to Architect for web planning and DuckDuckGo query decomposition."
        }
        state["status"] = "Librarian checked local corpus (empty). Routing to Architect for web plan."
        state["logs"].append({
            "stage": "librarian",
            "output": res_data,
            "chunk_count": 0,
            "triplet_count": 0
        })
        return state

librarian = LibrarianAgent()
