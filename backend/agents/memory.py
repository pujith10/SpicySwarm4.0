import os
import redis
import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Any
from dotenv import load_dotenv

load_dotenv()

class HAAMemory:
    def __init__(self):
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        try:
            self.redis_client = redis.from_url(self.redis_url, decode_responses=True)
            self.redis_client.ping()
            self.use_redis = True
        except:
            self.use_redis = False
            self.db_path = "haa_history.db"
            self._init_sqlite()

    def _init_sqlite(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS history (
                id TEXT PRIMARY KEY,
                query TEXT,
                answer TEXT,
                validation TEXT,
                state_delta TEXT,
                timestamp DATETIME
            )
        ''')
        conn.commit()
        conn.close()

    def save_session(self, query_id: str, state: Dict[str, Any]):
        data = {
            "id": query_id,
            "query": state.get("query"),
            "answer": state.get("final_answer"),
            "validation": json.dumps(state.get("validation")),
            "state_delta": json.dumps(state.get("state_delta", [])),
            "timestamp": datetime.now().isoformat()
        }
        
        if self.use_redis:
            self.redis_client.set(f"session:{query_id}", json.dumps(data))
            self.redis_client.lpush("sessions", query_id)
        else:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO history (id, query, answer, validation, state_delta, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (data["id"], data["query"], data["answer"], data["validation"], data["state_delta"], data["timestamp"]))
            conn.commit()
            conn.close()

    def get_history(self, limit: int = 10) -> List[Dict]:
        if self.use_redis:
            ids = self.redis_client.lrange("sessions", 0, limit - 1)
            results = []
            for qid in ids:
                data = self.redis_client.get(f"session:{qid}")
                if data:
                    results.append(json.loads(data))
            return results
        else:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM history ORDER BY timestamp DESC LIMIT ?', (limit,))
            rows = cursor.fetchall()
            conn.close()
            return [dict(row) for row in rows]

memory = HAAMemory()
