import os
import asyncio
from typing import List, Dict
try:
    from langchain_community.vectorstores import FAISS
except ImportError:
    FAISS = None

try:
    from langchain_huggingface import HuggingFaceEmbeddings  # type: ignore
except ImportError:
    try:
        from langchain_community.embeddings import HuggingFaceEmbeddings  # type: ignore
    except ImportError:
        class HuggingFaceEmbeddings:
            def __init__(self, *args, **kwargs):
                pass
            def embed_documents(self, texts):
                return [[0.1] * 128 for _ in texts]
            def embed_query(self, text):
                return [0.1] * 128

from dotenv import load_dotenv

load_dotenv()

try:
    from neo4j import GraphDatabase
except ImportError:
    GraphDatabase = None

class HAA_Retriever:
    def __init__(self):
        self._embeddings = None
        self.index_path = os.getenv("FAISS_INDEX_PATH", "./data/faiss.index")
        self.vectorstore = None
        
        # Neo4j Settings
        self.neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.neo4j_user = os.getenv("NEO4J_USER", "neo4j")
        self.neo4j_pwd = os.getenv("NEO4J_PASSWORD", "password")
        self.driver = None

    @property
    def embeddings(self):
        if self._embeddings is None:
            try:
                self._embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
            except Exception:
                class DummyEmbeddings:
                    def embed_documents(self, texts):
                        return [[0.1] * 128 for _ in texts]
                    def embed_query(self, text):
                        return [0.1] * 128
                self._embeddings = DummyEmbeddings()
        return self._embeddings

    def _is_neo4j_reachable(self) -> bool:
        import socket
        try:
            uri = self.neo4j_uri.replace("bolt://", "").replace("neo4j://", "")
            host, port_str = uri.split(":") if ":" in uri else (uri, 7687)
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.15)
            s.connect((host, int(port_str)))
            s.close()
            return True
        except Exception:
            return False

    async def init_neo4j(self):
        if not self._is_neo4j_reachable():
            self.driver = None
            return

        if not self.driver and GraphDatabase:
            try:
                self.driver = GraphDatabase.driver(
                    self.neo4j_uri, 
                    auth=(self.neo4j_user, self.neo4j_pwd)
                )
            except Exception:
                self.driver = None

    async def load_index(self):
        if FAISS and os.path.exists(self.index_path):
            try:
                self.vectorstore = FAISS.load_local(self.index_path, self.embeddings, allow_dangerous_deserialization=True)
                return True
            except Exception:
                return False
        return False

    async def vector_search(self, query: str, k: int = 5) -> List[Dict]:
        if not os.path.exists(self.index_path):
            return []
        if not self.vectorstore:
            await self.load_index()
        if not self.vectorstore:
            return []
        docs = await asyncio.to_thread(self.vectorstore.similarity_search, query, k=k)
        return [{"content": d.page_content, "rank": i + 1} for i, d in enumerate(docs)]

    async def kg_search(self, query: str) -> List[str]:
        # Fast fail if Neo4j is offline
        if not self._is_neo4j_reachable():
            return ["[System] Neo4j Offline - No local graph triplets"]

        await self.init_neo4j()
        if not self.driver:
            return ["[System] Neo4j Offline - No local graph triplets"]
        
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
