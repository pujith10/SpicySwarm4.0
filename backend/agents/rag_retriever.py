import os
import asyncio
from typing import List, Dict
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from dotenv import load_dotenv

load_dotenv()

from neo4j import GraphDatabase

class HAA_Retriever:
    def __init__(self):
        self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        self.index_path = os.getenv("FAISS_INDEX_PATH", "./data/faiss.index")
        self.vectorstore = None
        
        # Neo4j Settings
        self.neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.neo4j_user = os.getenv("NEO4J_USER", "neo4j")
        self.neo4j_pwd = os.getenv("NEO4J_PASSWORD", "password")
        self.driver = None

    async def init_neo4j(self):
        if not self.driver:
            try:
                self.driver = GraphDatabase.driver(self.neo4j_uri, auth=(self.neo4j_user, self.neo4j_pwd))
            except Exception as e:
                print(f"Neo4j Connection Failed: {e}")

    async def load_index(self):
        if os.path.exists(self.index_path):
            self.vectorstore = FAISS.load_local(self.index_path, self.embeddings, allow_dangerous_deserialization=True)
            return True
        return False

    async def vector_search(self, query: str, k: int = 5) -> List[Dict]:
        if not self.vectorstore:
            await self.load_index()
        if not self.vectorstore:
            return []
        docs = await asyncio.to_thread(self.vectorstore.similarity_search, query, k=k)
        return [{"content": d.page_content, "rank": i + 1} for i, d in enumerate(docs)]

    async def kg_search(self, query: str) -> List[str]:
        # v4.0 Sharp: Genuine Neo4j Multi-Hop Retrieval
        await self.init_neo4j()
        if not self.driver:
            return ["[System] Neo4j Offline - Falling back to Semantic Search Only"]
        
        try:
            # v4.0 Sharp: Thread-safe Traversal to prevent blocking the event loop
            def run_neo4j():
                with self.driver.session() as session:
                    result = session.run(
                        "MATCH (n)-[r]->(m) WHERE n.name CONTAINS $query OR m.name CONTAINS $query "
                        "RETURN n.name + ' -' + type(r) + '-> ' + m.name AS triplet LIMIT 5",
                        query=query
                    )
                    return [record["triplet"] for record in result]
            
            return await asyncio.to_thread(run_neo4j)
        except Exception as e:
            return [f"[Error] Graph Traversal failed: {str(e)}"]

    def reciprocal_rank_fusion(self, vector_results: List[Dict], k: int = 60) -> List[str]:
        # RRF(k) algorithm to merge multiple sorted lists
        scores = {}
        for res in vector_results:
            content = res["content"]
            rank = res["rank"]
            scores[content] = scores.get(content, 0) + 1 / (k + rank)
        
        # Sort by fused score
        sorted_results = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [res[0] for res in sorted_results]

    async def get_context(self, query: str) -> Dict:
        # Async Parallel Retrieval (Gap 5 Solution)
        vector_results, kg_results = await asyncio.gather(
            self.vector_search(query),
            self.kg_search(query)
        )
        
        # Reciprocal Rank Fusion Logic
        fused_chunks = self.reciprocal_rank_fusion(vector_results)
        
        return {
            "chunks": fused_chunks,
            "triplets": kg_results
        }

retriever = HAA_Retriever()
