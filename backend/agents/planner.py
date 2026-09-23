import json
import logging
import re
from typing import Dict, Any, List
from langchain_core.prompts import ChatPromptTemplate
from backend.pipeline.state import PipelineState
from backend.pipeline.goal_state import GoalState, plan_drift_detector
from backend.agents.utils import safe_llm_call
from backend.config import config
from dotenv import load_dotenv

logger = logging.getLogger(__name__)
load_dotenv()

PLANNER_SYSTEM = """You are the HAA Strategic Architect & Planner Agent (v4.0 Research Edition).
Your mission is to perform deep cognitive decomposition of the user's objective and generate an actionable, high-precision execution plan for the Analyst agent.

CORE RESPONSIBILITIES:
1. GOAL DECONSTRUCTION:
   Analyze the user's root objective. Determine what factual information, data points, or calculations are required to completely, accurately, and unambiguously satisfy the user's request.

2. SEARCH QUERY ENGINEERING (CRUCIAL FOR DUCKDUCKGO):
   For any task requiring web research, you must NEVER output vague conversational sentences as search queries.
   Instead, engineer specific, high-intent keyword queries optimized for DuckDuckGo.
   Include relevant location, date/time terms (e.g., 'today', '2026', current year/month), domain terms, or metrics.
   Example:
     Bad query: "What is the weather like in Delhi"
     Engineered query: "Delhi weather forecast today current temperature Celsius IMD AccuWeather"

3. PROMPT GENERATION FOR ANALYST:
   For each subtask, generate a detailed directive ('analyst_prompt') instructing the Analyst:
   - Exactly what DuckDuckGo query to run.
   - What specific data points to extract from the returned snippets.
   - What uncertainties or conflicting reports to flag.

4. MULTI-LOOP NOVELTY CONSTRAINT (CRITICAL MANDATORY RULE - NO DUPLICATE PROMPTS):
   This system executes up to 7 refinement loops. In EACH loop, you MUST generate NEW, DISTINCT search queries and analyst prompts.
   UNDER NO CIRCUMSTANCES should any query or prompt in the current loop match or duplicate any query from previous loops!
   Every new loop must uncover NEW facets, deeper layers, or unexplored angles of the goal:
   - For factual or weather queries:
     * Loop 1: Core real-time values (current temperature, basic condition).
     * Loop 2: Hourly progression, diurnal temperature range (highs/lows), humidity and dew point curves.
     * Loop 3: Environmental and atmospheric metrics (Air Quality Index / AQI, PM2.5, PM10, smog/fog).
     * Loop 4: Precipitation probability, cloud cover percentages, radar and satellite trends.
     * Loop 5: Official meteorological alerts, severe weather warnings (IMD/AccuWeather/Govt advisories).
     * Loop 6: Microclimate and regional variations across different districts/neighborhoods.
     * Loop 7: Climatological context, historical records, or departure from seasonal normal temperatures.
   - For general research queries:
     * Loop 1: Direct definitions and core answer.
     * Loop 2: Methodologies, technical specifications, and quantitative benchmarks.
     * Loop 3: Real-world case studies and operational deployments.
     * Loop 4: Counterarguments, limitations, and edge cases.
     * Loop 5: Security, compliance, and risk assessments.
     * Loop 6: Comparative analysis against alternatives.
     * Loop 7: Future roadmaps, recent breakthroughs, and authoritative consensus.

5. ADAPTIVE RE-PLANNING (CRITIC REFINEMENT):
   If previous Critic feedback is present, rigorously inspect the reported gaps, hallucinations, or unverified claims.
   Refactor your subtasks and engineer new, targeted search queries to specifically locate the missing evidence while maintaining 100% novelty!

STRICT JSON OUTPUT FORMAT:
{{
  "plan_id": "plan_unique_string",
  "goal_anchor": "Exact original user query",
  "loop_number": 1,
  "exploration_dimension": "Name of the new dimension being investigated in this loop",
  "strategic_rationale": "Clear explanation of how this plan satisfies the user's goal and what new information it acquires",
  "subtasks": [
    {{
      "id": "t1",
      "task": "High-level description of this subtask",
      "tool": "web_search",
      "search_query": "Optimized, keyword-rich search query to be directly executed on DuckDuckGo",
      "analyst_prompt": "Detailed instructions to the Analyst on what specific data points, facts, and figures to extract from the search results",
      "target_data": ["metric1", "metric2"],
      "priority": "HIGH",
      "depends_on": []
    }}
  ]
}}

RULES:
- Limit subtasks to 2-3 high-impact tasks. Keep descriptions and queries concise and keyword-dense.
- 'tool' MUST be either 'web_search' (for real-time facts, weather, news, current events) or 'python_sandbox' (for math/logic computations).
- Output ONLY valid JSON, starting with {{ and ending with }}. No conversation before or after.
"""

class ArchitectAgent:
    def __init__(self):
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", PLANNER_SYSTEM),
            ("human", (
                "User Goal: {query}\n"
                "Current Refinement Loop: Cycle {current_cycle} of {max_cycles}\n"
                "Librarian Context & Knowledge Gaps:\n{findings}\n"
                "Critic Feedback from Prior Cycle:\n{critic_feedback}\n\n"
                "QUERIES ALREADY EXECUTED IN PREVIOUS LOOPS (DO NOT DUPLICATE ANY OF THESE):\n{executed_queries}\n\n"
                "Remember: This loop MUST explore a completely new angle or deeper layer not covered above."
            ))
        ])

    async def run(self, state: PipelineState) -> Dict[str, Any]:
        # Step 1: Initialize or verify GoalState
        if not state.get("goal_state"):
            goal_obj = GoalState(
                goal_id=f"g_{state.get('query', '')[:10]}",
                original_goal=state["query"]
            )
            state["goal_state"] = goal_obj.model_dump()
        else:
            goal_obj = GoalState(**state["goal_state"])

        # Determine current cycle number
        current_cycle = state.get("retry_count", 0) + 1
        max_cycles = config.MAX_CYCLES

        # Gather cumulative history of all executed search queries
        prior_queries = list(state.get("prior_search_queries", []))
        for log in state.get("logs", []):
            if log.get("stage") == "architect":
                out = log.get("output", {})
                if isinstance(out, dict):
                    for st in out.get("subtasks", []):
                        sq = st.get("search_query")
                        if sq and sq not in prior_queries:
                            prior_queries.append(sq)

        state["prior_search_queries"] = prior_queries

        if prior_queries:
            executed_queries_text = "\n".join([f"- Loop query: \"{q}\"" for q in prior_queries])
        else:
            executed_queries_text = "None (This is the first loop)."

        # Gather librarian context
        findings = ""
        for log in state.get("logs", []):
            if log.get("stage") == "librarian":
                out = log.get("output", {})
                if isinstance(out, dict):
                    gaps = out.get("knowledge_gaps", [])
                    summary = out.get("retrieved_summary", "")
                    findings = f"Summary: {summary}\nKnowledge Gaps: {gaps}"
                else:
                    findings = str(out)
                break

        critic_feedback = ""
        val = state.get("validation")
        if val:
            critic_feedback = (
                f"Critic Verdict: {val.get('verdict')}\n"
                f"Recommendations: {val.get('recommendations')}\n"
                f"Critical Errors: {val.get('critical_errors')}\n"
                f"Score: {val.get('overall_score')}"
            )

        try:
            response = await safe_llm_call(
                self.prompt,
                {
                    "query": goal_obj.original_goal,
                    "current_cycle": current_cycle,
                    "max_cycles": max_cycles,
                    "findings": findings or "No local data available; requires live search.",
                    "critic_feedback": critic_feedback or "First planning cycle.",
                    "executed_queries": executed_queries_text
                },
                agent_name="architect"
            )

            content = response.content.strip()

            # Robust multi-pass JSON extraction
            plan = None
            if "```json" in content:
                sub = content.split("```json")[1].split("```")[0].strip()
                try:
                    plan = json.loads(sub)
                except Exception:
                    pass
            if not plan:
                start = content.find("{")
                end = content.rfind("}")
                if start != -1 and end != -1 and end > start:
                    cand = content[start:end+1].strip()
                    try:
                        plan = json.loads(cand)
                    except Exception:
                        cleaned = re.sub(r',\s*([\}\]])', r'\1', cand)
                        try:
                            plan = json.loads(cleaned)
                        except Exception:
                            pass
            if not plan:
                start = content.find("{")
                if start != -1:
                    cand = content[start:].strip()
                    unescaped_quotes = len(re.findall(r'(?<!\\)"', cand))
                    if unescaped_quotes % 2 != 0:
                        cand += '"'
                    cand += "]" * max(0, cand.count("[") - cand.count("]"))
                    cand += "}" * max(0, cand.count("{") - cand.count("}"))
                    cleaned = re.sub(r',\s*([\}\]])', r'\1', cand)
                    try:
                        plan = json.loads(cleaned)
                    except Exception:
                        pass
            if not plan:
                try:
                    plan = json.loads(content)
                except Exception:
                    cleaned = re.sub(r',\s*([\}\]])', r'\1', content)
                    plan = json.loads(cleaned)

            # Step 2: Enforce Goal Pinning (Prevent Contextual Drift)
            plan["goal_anchor"] = goal_obj.original_goal
            plan["loop_number"] = current_cycle

            # Step 3: Enforce Query Novelty & Programmatic Deduplication
            subtasks = plan.get("subtasks", [])
            seen_in_current_batch = set()

            loop_themes = {
                1: "current core conditions and metrics",
                2: "hourly timeline progression and high low forecast",
                3: "air quality index AQI PM2.5 pollution levels",
                4: "precipitation probability cloud radar satellite",
                5: "official IMD alerts and severe weather warnings",
                6: "regional microclimate district variations",
                7: "historical climatology and seasonal temperature departure"
            }

            for i, st in enumerate(subtasks):
                raw_sq = st.get("search_query") or st.get("task", goal_obj.original_goal)
                clean_sq = raw_sq.strip().lower()

                # Check if this query duplicates any query from a prior loop or this batch
                is_duplicate = False
                for pq in prior_queries:
                    pq_clean = pq.strip().lower()
                    if clean_sq == pq_clean or (len(clean_sq) > 15 and clean_sq in pq_clean):
                        is_duplicate = True
                        break

                if clean_sq in seen_in_current_batch:
                    is_duplicate = True

                if is_duplicate:
                    theme = loop_themes.get(current_cycle, f"deep dimension {current_cycle}")
                    specialized_sq = f"{goal_obj.original_goal} {theme} 2026 latest"
                    logger.info(f"Architect duplicate query detected: '{raw_sq}'. Transformed to novel loop {current_cycle} query: '{specialized_sq}'")
                    st["search_query"] = specialized_sq
                    st["analyst_prompt"] = f"Explore new dimension for loop {current_cycle}: search DuckDuckGo for '{specialized_sq}' and extract {theme}."
                    st["target_data"] = [theme, f"loop_{current_cycle}_metrics"]
                else:
                    st["search_query"] = raw_sq
                    if not st.get("analyst_prompt"):
                        st["analyst_prompt"] = f"Extract factual answers for: {st.get('task')}"

                seen_in_current_batch.add(st["search_query"].strip().lower())
                # Add to cumulative tracking
                if st["search_query"] not in prior_queries:
                    prior_queries.append(st["search_query"])

            state["prior_search_queries"] = prior_queries

            # Step 4: Plan Drift Evaluation
            plan_summary = " ".join([t.get("task", "") + " " + t.get("search_query", "") for t in subtasks])
            drift_res = plan_drift_detector.evaluate_drift(goal_obj, plan_summary, "")

            if drift_res.get("drift_detected"):
                logger.warning(f"Plan drift detected: {drift_res['reason']}. Enforcing realignment.")
                plan["drift_warning"] = drift_res["reason"]

            state["plan"] = plan
            state["status"] = f"Architect produced Loop {current_cycle} plan ({len(subtasks)} novel subtasks)"
            state["logs"].append({
                "stage": "architect",
                "loop": current_cycle,
                "output": plan,
                "prior_queries_count": len(prior_queries),
                "drift_evaluation": drift_res
            })
            return state

        except Exception as e:
            logger.error(f"Architect planning failure: {e}")
            theme = f"dimension_{current_cycle}"
            novel_fallback_query = f"{goal_obj.original_goal} loop {current_cycle} breakdown 2026"
            prior_queries.append(novel_fallback_query)
            state["prior_search_queries"] = prior_queries

            fallback_plan = {
                "plan_id": f"fallback_plan_loop_{current_cycle}",
                "goal_anchor": goal_obj.original_goal,
                "loop_number": current_cycle,
                "exploration_dimension": f"Refinement loop {current_cycle}",
                "strategic_rationale": f"Loop {current_cycle} novel exploration fallback plan.",
                "subtasks": [
                    {
                        "id": f"t_{current_cycle}_1",
                        "task": f"Investigate loop {current_cycle} details for: {goal_obj.original_goal}",
                        "tool": "web_search",
                        "search_query": novel_fallback_query,
                        "analyst_prompt": f"Search DuckDuckGo and extract loop {current_cycle} new facts for '{goal_obj.original_goal}'",
                        "target_data": [f"loop_{current_cycle}_data"],
                        "priority": "HIGH",
                        "depends_on": []
                    }
                ],
                "plan_rationale": "Fallback decomposition deployed due to parsing error."
            }
            state["plan"] = fallback_plan
            state["status"] = f"Architect fallback plan deployed for Loop {current_cycle}"
            state["logs"].append({"stage": "architect", "loop": current_cycle, "output": fallback_plan})
            return state

architect = ArchitectAgent()
