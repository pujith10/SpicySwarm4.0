# Hybrid Agentic Architecture (HAA)

HAA is a research-grade multi-agent AI system that bridges Generative AI and Agentic AI autonomy using a Planner–Executor–Validator (PEV) architecture.

## Features
- **PEV Triad Agent Pipeline**: Independent verification using Planner, Executor, and Validator agents.
- **Hybrid Retrieval**: ASynchronous RAG (FAISS) + Knowledge Graph placeholders.
- **Security Layer**: spaCy-based token scrubbing for prompt injection defense.
- **Real-time Visualization**: WebSocket-driven dashboard for observing agent reasoning.
- **Dockerized Deployment**: Complete orchestration with Neo4j, Redis, FastAPI, and React.

## Getting Started

### Prerequisites
- Docker & Docker Compose
- Anthropic API Key (Claude-3.5-Sonnet)

### Setup
1. Clone the repository.
2. Characterize the `.env` file with your `ANTHROPIC_API_KEY`.
3. Start the services:
   ```bash
   docker-compose up --build
   ```
4. Ingest the initial documentation (one-time setup):
   ```bash
   docker-compose exec backend python data/ingest.py
   ```
5. Open [http://localhost:3000](http://localhost:3000) in your browser.

## Architecture
- **Planner**: Decomposes user goals into structured subtasks.
- **Executor**: Executes tasks and records uncertainties (state_delta).
- **Validator**: Audits Executor's output for hallucinations and goal misalignment.
- **LangGraph**: Orchestrates the stateful feedback loop between agents.

## Evaluation Metrics
The dashboard displays:
- Hallucination Rate
- Goal Congruence
- Latency (ms)
- Re-planning Frequency
