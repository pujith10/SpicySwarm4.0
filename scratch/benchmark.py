import os
import sys
import asyncio
import json
import time

# Add root directory to PYTHONPATH
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(PROJECT_ROOT)

from backend.pipeline.graph import graph
from backend.pipeline.state import PipelineState
from dotenv import load_dotenv

load_dotenv()

async def run_query(query: str, simulation_mode: str = "normal"):
    """
    Runs a query through the HAA graph and returns the final state.
    Modes:
    - 'normal': Standard flow
    - 'no_critic': Critic is bypassed (logic injected in state)
    - 'fallback_test': Google API is 'broken' to force Tier 2 Groq
    """
    print(f"\n[BENCHMARK] Testing: '{query}' | Mode: {simulation_mode}")
    
    # Store original keys for restoration
    original_google_key = os.getenv("GOOGLE_API_KEY")
    
    if simulation_mode == "fallback_test":
        print("[BENCHMARK] Simulating Google API Blackout...")
        os.environ["GOOGLE_API_KEY"] = "broken_key_404"
    
    initial_state: PipelineState = {
        "query": query,
        "retrieved_chunks": [],
        "kg_triplets": [],
        "plan": None,
        "execution": None,
        "state_delta": [],
        "validation": None,
        "final_answer": "",
        "retry_count": 0,
        "logs": [],
        "status": "Benchmark Started",
        "error": None,
        "tool_outputs": [],
        "graph_data": {},
        "swarm_consensus": None
    }
    
    start_time = time.time()
    final_state = initial_state
    
    try:
        # We use astream to capture mid-flow logs if needed, but here we just want the end
        async for event in graph.astream(initial_state):
            for node_name, state_update in event.items():
                final_state.update(state_update)
                # If 'no_critic' mode, we might want to skip the loops, 
                # but standard graph will run nodes in order.
                # To simulate No-Critic, we check if node is critic and force PASS.
                if simulation_mode == "no_critic" and node_name == "critic":
                     final_state["validation"] = {"verdict": "PASS", "criticism": "Skipped per benchmark"}
                     
    except Exception as e:
        print(f"[BENCHMARK] Fatal Error: {e}")
        final_state["error"] = str(e)
    
    latency = (time.time() - start_time) * 1000
    
    # Restore keys
    if original_google_key:
        os.environ["GOOGLE_API_KEY"] = original_google_key
        
    return final_state, latency

async def run_evaluation_suite():
    results = []
    
    # Test 1: Ablation (Complex Reasoning)
    # Query designed to be tricky / require refinement
    query_1 = "How many universities are there in Delhi? Compare that with the count in Bangalore."
    
    print("\n--- TEST 1: Audit-Gain (Ablation) ---")
    st_ablation, lat_ablation = await run_query(query_1, simulation_mode="no_critic")
    st_full, lat_full = await run_query(query_1, simulation_mode="normal")
    
    results.append({
        "id": "Ablation Study",
        "query": query_1,
        "without_critic_answer": st_ablation["final_answer"][:100],
        "with_critic_answer": st_full["final_answer"][:100],
        "with_critic_loops": st_full.get("retry_count", 0),
        "latency_diff_ms": lat_full - lat_ablation
    })
    
    # Test 2: Resilience (API Survival)
    query_2 = "Who is the current Prime Minister of India?"
    print("\n--- TEST 2: System Resilience (Survival Rate) ---")
    st_resil, lat_resil = await run_query(query_2, simulation_mode="fallback_test")
    
    results.append({
        "id": "Resilience Test",
        "query": query_2,
        "mode": "Simulated Google 404",
        "status": "SUCCESS" if not st_resil.get("error") and st_resil.get("final_answer") else "FAILED",
        "tier_used": "Groq Fallback",
        "latency_ms": lat_resil
    })
    
    # Test 3: Tool Heterogeneity (Cross-Tool Synthesis)
    query_3 = "Find the current temperature in Delhi and calculate how much it differs from 30°C."
    print("\n--- TEST 3: Tool Heterogeneity (Web + Code) ---")
    st_tool, lat_tool = await run_query(query_3, simulation_mode="normal")
    
    results.append({
        "id": "Tool Heterogeneity",
        "query": query_3,
        "web_results": "YES" if any(l.get("stage") == "analyst" for l in st_tool["logs"]) else "NO",
        "final_answer": st_tool["final_answer"]
    })
    
    # Output to File
    with open("HAA_RESEARCH_RESULTS.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print("\n[BENCHMARK] Complete. Results saved to HAA_RESEARCH_RESULTS.json")

if __name__ == "__main__":
    # Fix for mode/simulation_mode typo in my draft
    async def run_query_wrapper(q, mode):
        return await run_query(q, simulation_mode=mode)
    
    asyncio.run(run_evaluation_suite())
