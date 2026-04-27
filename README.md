# Spicy Swarm 4.0: Hybrid Agentic Architecture (HAA)

> A research-grade multi-agent AI system that bridges Generative AI and Agentic AI autonomy using a Planner–Executor–Validator (PEV) architecture.

## Overview

Artificial Intelligence is shifting from machines that wait for instructions to agents that can independently pursue complex goals. **Spicy Swarm 4.0** is an implementation of a **Hybrid Agentic Architecture (HAA)** designed to prove that the quality of an agentic system relies more on its surrounding structure than the sheer size of its driving model.

Built heavily on **LangGraph**, the system addresses five critical gaps in modern AI research:
1. **Self-Verification Bias** (Resolved via an independent Critic loop)
2. **Contextual Drift** (Resolved via goal-pinned State dictionaries and a Redis Memory Module)
3. **Latency-Reasoning Tradeoff** (Managed via Asynchronous Parallel Retrieval)
4. **Single-Provider Fragility** (Resolved via Triple-Tier LLM Fallback)
5. **The Security Paradox** (Resolved via Token Scrubbing Middleware & Action Whitelists)

## 🧠 Core Architecture (The PEV Triad)

The swarm exposes five discrete, stateful agents communicating exclusively through a shared, typed `PipelineState` object. This eliminates implicit coupling and pins the original user goal as a global constant visible to every node.

*   **Librarian (Planner - Retrieve):** Employs hybrid `asyncio.gather()` retrieval. It merges FAISS semantic search chunks with Neo4j Knowledge Graph triplets using Reciprocal Rank Fusion (RRF). *(Note: Neo4j is currently stubbed for structural validation).*
*   **Architect (Planner - Decompose):** Receives the context and produces a Directed Acyclic Graph (DAG) of executable subtasks.
*   **Analyst (Executor):** Acts as the engine, assigning tools (Search, Python REPL, etc.) to the DAG subtasks and executing them in a sandboxed environment.
*   **Critic (Validator):** An independent auditor with no shared state with the Analyst. If the Analyst hallucinates or deviates from the goal, the Critic issues a `REFINE` signal, forcing up to 7 loops of redecomposition.
*   **Synthesizer (Reporter):** Synthesizes the final diagnostic report once the Critic issues a `PASS`.

### 🛡️ Security & Resilience Features

*   **Triple-Tier LLM Fallback:** Single-provider dependency is a massive operational risk. Spicy Swarm wraps all API calls in a hierarchy:
    *   *Tier 1:* Google Gemini 1.5 Pro (Primary)
    *   *Tier 2:* Groq Llama-3.3-70B (Failover on 404/500)
    *   *Tier 3:* Groq Llama-3.1-8B (Emergency speed tier on HTTP 429)
*   **Token Scrubbing Middleware:** Uses NLP to detect imperative constructs (e.g., "ignore", "delete") hidden inside retrieved data, converting them to passive annotations to prevent indirect prompt injections.

---

## 🚀 Getting Started

The entire architecture (Backend API, Frontend Dashboard, Neo4j, and Redis) is fully containerized using Docker Compose.

### Prerequisites
*   [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running.
*   API Keys for **Groq** and **Google Gemini**.

### Installation & Deployment

1. **Clone the repository:**
   ```bash
   git clone https://github.com/pujith10/SpicySwarm4.0.git
   cd SpicySwarm4.0
   ```

2. **Configure Environment Variables:**
   Create a `.env` file in the root directory (based on `.env.example`) and add your API keys. Make sure your internal Docker URLs are set correctly:
   ```env
   GROQ_API_KEY=your_groq_key
   GOOGLE_API_KEY=your_gemini_key
   NEO4J_URI=bolt://neo4j:7687
   NEO4J_USER=neo4j
   NEO4J_PASSWORD=password
   REDIS_URL=redis://redis:6379
   FAISS_INDEX_PATH=backend/data/faiss.index
   MAX_RETRY_COUNT=7
   SCRUBBING_ENABLED=true
   ```

3. **Deploy the Stack:**
   Run the following command to build and start the containers:
   ```bash
   docker-compose up -d --build
   ```

4. **Verify the Deployment:**
   *   **Frontend UI:** Navigate to `http://localhost:3000`
   *   **Backend API:** Running on `http://localhost:8000`
   *   **Neo4j Database:** Navigate to `http://localhost:7474`

### Stopping the Swarm
```bash
docker-compose down
```

## 📊 Evaluation & Research Results

During ablation studies and live validation:
*   The **Critic-driven refinement loop** intercepted generic data and safely executed 7 refinement cycles to ensure high-precision answers.
*   The **Triple-Tier Fallback** successfully absorbed a simulated Google API outage, pivoting to Llama-3 in just 6.6 seconds without dropping the WebSocket session.
*   The **Architect** successfully mapped compound queries to heterogeneous tools (e.g., routing weather data to DuckDuckGo and math to a Python REPL).

---
*Developed as part of research into autonomous Hybrid Agentic Architectures.*
