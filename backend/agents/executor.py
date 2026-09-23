import json
import asyncio
import logging
import os
from typing import Dict, Any, List
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from backend.pipeline.state import PipelineState
from backend.security.provenance import ProvenanceMetadata, SecurityLabel
from backend.security.capabilities import capability_manager, RiskLevel
from backend.security.reference_monitor import reference_monitor
from backend.security.tool_schemas import SafePythonSandbox, WebSearchInput, PythonSandboxInput
from backend.agents.security_proxy import security_proxy
from backend.agents.utils import safe_llm_call
from dotenv import load_dotenv

logger = logging.getLogger(__name__)
load_dotenv()

import urllib.request
import re
from bs4 import BeautifulSoup

def _clean_query(query: str) -> str:
    skip = {"observation", "official", "metrics", "parameters", "dimension", "breakdown", "analysis"}
    words = [w for w in query.split() if w.lower() not in skip]
    return " ".join(words[:5])

def _fetch_openrouter_knowledge_fallback(query: str) -> str:
    """
    Auxiliary LLM Knowledge Fallback for Web Scraper Blocking:
    When web scraping or anti-bot protections (Cloudflare, CAPTCHA) block external
    site extraction, queries a distinct free model on OpenRouter
    ('meta-llama/llama-3.3-70b-instruct:free') which is NOT assigned to any of the 5 agents.
    Synthesizes empirical and factual knowledge across general research topics.
    """
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        return ""
    base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    
    # Free OpenRouter models completely distinct from the primary 5 agents (which use nvidia/nemotron-3-ultra-550b-a55b:free)
    fallback_models = [
        "meta-llama/llama-3.3-70b-instruct:free",
        "qwen/qwen-2.5-72b-instruct:free",
        "meta-llama/llama-3.1-8b-instruct:free",
    ]
    for model_id in fallback_models:
        try:
            llm = ChatOpenAI(
                model=model_id,
                api_key=api_key,
                base_url=base_url,
                temperature=0.1,
                timeout=15,
                max_tokens=1500,
                default_headers={
                    "HTTP-Referer": "http://localhost:5173",
                    "X-Title": "Spicy Swarm 4.0 - Scraper Fallback",
                }
            )
            prompt = (
                f"You are an auxiliary research knowledge fallback agent. "
                f"Candidate web scrapers were blocked by anti-bot protections while researching: '{query}'. "
                f"Provide a comprehensive, factual, objective summary and verified empirical data points answering this query "
                f"so the research pipeline has reliable empirical information to analyze."
            )
            response = llm.invoke(prompt)
            content = response.content if hasattr(response, "content") else str(response)
            if content and len(content.strip()) > 30:
                logger.info(f"Scraper fallback successfully synthesized knowledge via OpenRouter [{model_id}]")
                return content.strip()
        except Exception as e:
            logger.warning(f"OpenRouter scraper fallback error for [{model_id}]: {e}")
            continue
    return ""

def _sync_scrape_website(url: str, timeout: float = 4.0) -> str:
    """Visits the website directly and extracts full clean text content."""
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9"
            }
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content_type = resp.headers.get("Content-Type", "")
            if "text/html" not in content_type and "text/plain" not in content_type:
                return ""
            raw_html = resp.read().decode("utf-8", errors="ignore")
            
            soup = BeautifulSoup(raw_html, "html.parser")
            for elem in soup(["script", "style", "nav", "footer", "header", "noscript", "aside", "svg", "button", "form"]):
                elem.decompose()

            article = soup.find("article") or soup.find("main") or soup.find("body")
            target = article if article else soup
            
            paragraphs = [p.get_text(separator=" ", strip=True) for p in target.find_all(["p", "h1", "h2", "h3", "li"])]
            text = " ".join([p for p in paragraphs if len(p) > 20])
            
            if not text or len(text) < 100:
                text = " ".join(target.stripped_strings)
            
            text = re.sub(r"\s+", " ", text).strip()
            return text[:2500]
    except Exception as e:
        logger.debug(f"Direct scrape failed for {url}: {e}")
        return ""

def _sync_ddgs_get_candidates(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """Builds search request body and fetches 3-5 candidate URLs from DuckDuckGo."""
    from ddgs import DDGS
    cleaned = _clean_query(query)
    candidates = []
    try:
        with DDGS(timeout=3.0) as ddgs:
            results = list(ddgs.text(cleaned, max_results=max_results, backend="api"))
            if not results:
                results = list(ddgs.text(cleaned, max_results=max_results, backend="lite"))
            for r in results:
                href = r.get("href")
                if href and href.startswith("http") and not any(d in href for d in ["youtube.com", "facebook.com", "instagram.com"]):
                    candidates.append({
                        "title": r.get("title", "Web Source"),
                        "url": href,
                        "snippet": r.get("body", "")
                    })
    except Exception as e:
        logger.debug(f"DDGS candidate retrieval error: {e}")
    return candidates

async def run_resilient_web_scrape(
    query: str,
    current_loop: int,
    existing_urls: set,
    max_results: int = 4
) -> List[Dict[str, Any]]:
    """
    DuckDuckGo search + direct website visitation:
    Visits the candidate websites, scrapes full text, and returns 3-5 url/content pairs.
    """
    candidates = await asyncio.to_thread(_sync_ddgs_get_candidates, query, max_results=max_results + 3)
    novel_candidates = [c for c in candidates if c["url"] not in existing_urls][:max_results]

    if not novel_candidates and candidates:
        novel_candidates = candidates[:max_results]

    scrape_tasks = [
        asyncio.to_thread(_sync_scrape_website, c["url"])
        for c in novel_candidates
    ]
    scraped_texts = await asyncio.gather(*scrape_tasks)

    seen_in_batch = set(existing_urls)
    results = []
    for c, text in zip(novel_candidates, scraped_texts):
        # Prefer full scraped text from the visited website; fall back to snippet if blocked
        content = text if text and len(text) > 80 else c.get("snippet", "")
        if content and c["url"] not in seen_in_batch:
            results.append({
                "url": c["url"],
                "title": c.get("title", "Web Source"),
                "content": content,
                "loop": current_loop
            })
            seen_in_batch.add(c["url"])

    # Universal fallback if all candidate websites blocked scrapers or returned empty results:
    if not results:
        logger.info(f"Scrapers blocked or 0 results for '{query}'. Invoking OpenRouter auxiliary knowledge fallback...")
        fallback_content = await asyncio.to_thread(_fetch_openrouter_knowledge_fallback, query)
        if fallback_content:
            results.append({
                "url": "https://openrouter.ai/models/meta-llama/llama-3.3-70b-instruct:free?fallback=scraper_blocked",
                "title": f"Auxiliary Knowledge Synthesis (LLM Fallback: {query[:40]})",
                "content": fallback_content,
                "loop": current_loop
            })

    return results

ANALYST_SYSTEM = """You are the HAA Analyst & Executor (v4.0 Research Edition).
Your role is to execute the Architect's decomposed sub-tasks using capability-governed tools.
Tools available: 
- web_search: Search the live internet for verified external information.
- python_sandbox: Execute safe Python code for math, statistical calculations, and algorithmic verification.

OUTPUT ONLY JSON:
{{
  "task_results": [
    {{"id": "t1", "tool": "web_search", "output": "verified data", "provenance": "external"}}
  ],
  "preliminary_answer": "Drafted answer grounded in tool outputs and verified facts",
  "state_delta": ["Uncertainty 1 to audit", "Uncertainty 2 to audit"]
}}
"""

REPL_TRANSLATOR_SYSTEM = """You are the HAA Python Code Generator.
Convert the natural language task into safe, self-contained Python code for the math/analysis sandbox.
- Output ONLY the raw executable Python code.
- Do NOT import os, sys, subprocess, or network modules.
- NO markdown backticks or explanations.
"""

class AnalystAgent:
    def __init__(self):
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", ANALYST_SYSTEM),
            ("human", "User Goal: {query}\nPlan: {plan}\nLibrarian Retrieved Data: {context}\nPrevious State Deltas: {history}")
        ])

    async def run(self, state: PipelineState) -> Dict[str, Any]:
        plan = state.get("plan", {})
        subtasks = plan.get("subtasks") or plan.get("tasks", [])
        
        if not subtasks:
            logger.warning("Analyst received empty plan subtasks. Synthesizing directly from retrieved context.")
            subtasks = [{"id": "fallback_1", "task": state["query"], "tool": "web_search"}]

        current_cycle = state.get("retry_count", 0) + 1
        existing_articles = list(state.get("scraped_articles", []))
        existing_urls = {a["url"] for a in existing_articles}

        state["status"] = f"Analyst executing {len(subtasks)} capability-gated tasks (Loop {current_cycle}, {len(existing_urls)} sources visited)..."

        # Base provenance for Analyst operations
        analyst_provenance = ProvenanceMetadata(
            source="analyst_agent",
            trust_level=0.95,
            origin=state.get("query", "user_goal"),
            agent="analyst",
            content_type="task_execution",
            security_label=SecurityLabel.MODEL_GENERATED
        )

        async def execute_task(task: Dict[str, Any]) -> Dict[str, Any]:
            task_id = task.get("id", "t_unknown")
            raw_tool = task.get("tool", "web_search")
            desc = task.get("task") or task.get("description", "Execute research")
            
            # Use Architect's engineered search query and directive
            search_query = task.get("search_query") or desc
            analyst_prompt = task.get("analyst_prompt") or desc
            target_data = task.get("target_data", [])
            
            tool_name = "python_sandbox" if "python" in raw_tool or "repl" in raw_tool else "web_search"
            
            # Step 1: Request Capability Token
            cap_token = capability_manager.issue_capability(
                agent="analyst",
                tool=tool_name,
                action="execute",
                allowed_params=["query", "code", "max_results"],
                scope=f"task_{task_id}"
            )

            result_entry = {
                "id": task_id,
                "tool": tool_name,
                "task": desc,
                "search_query": search_query,
                "analyst_prompt": analyst_prompt,
                "target_data": target_data,
                "output": "",
                "security_status": "ALLOW",
                "provenance": None
            }

            try:
                if tool_name == "web_search":
                    params = {"query": search_query, "max_results": 5}
                    
                    # Step 2: Policy & Security Gate via SecurityProxy
                    sec_eval = security_proxy.execute_tool_safely(
                        agent="analyst",
                        tool="web_search",
                        action="execute",
                        parameters=params,
                        provenance=analyst_provenance,
                        capability_id=cap_token.capability_id
                    )

                    if sec_eval["security_blocked"]:
                        result_entry["output"] = f"[SECURITY BLOCK] {sec_eval['reason']}"
                        result_entry["security_status"] = "BLOCKED"
                    else:
                        # Step 3: Tool Execution using Architect's engineered DuckDuckGo query & deep site scraping
                        scraped_items = await run_resilient_web_scrape(
                            search_query,
                            current_loop=current_cycle,
                            existing_urls=existing_urls,
                            max_results=4
                        )
                        result_entry["scraped_items"] = scraped_items
                        
                        outputs = []
                        for it in scraped_items:
                            outputs.append(f"[{it.get('title', 'Web Source')}] ({it['url']}):\n{it['content'][:500]}...")
                        result_entry["output"] = "\n\n".join(outputs) if outputs else "Website search completed."
                        result_entry["security_status"] = "VERIFIED_ALLOW"
                        
                        # Provenance Tagging on External Data
                        result_entry["provenance"] = ProvenanceMetadata(
                            source="duckduckgo_deep_scraper",
                            trust_level=0.85,
                            origin=search_query,
                            agent="analyst",
                            content_type="scraped_web_content",
                            security_label=SecurityLabel.UNTRUSTED_EXTERNAL
                        ).to_dict()

                elif tool_name == "python_sandbox":
                    # Generate safe code via LLM
                    translation_res = await safe_llm_call(
                        ChatPromptTemplate.from_messages([
                            ("system", REPL_TRANSLATOR_SYSTEM),
                            ("human", "{input}")
                        ]),
                        {"input": desc},
                        agent_name="analyst"
                    )
                    code = translation_res.content.strip()
                    if code.startswith("```"):
                        code = "\n".join(code.split("\n")[1:-1])

                    params = {"code": code, "timeout_seconds": 5}
                    
                    # Policy & Security Gate
                    sec_eval = security_proxy.execute_tool_safely(
                        agent="analyst",
                        tool="python_sandbox",
                        action="execute",
                        parameters=params,
                        provenance=analyst_provenance,
                        capability_id=cap_token.capability_id
                    )

                    if sec_eval["security_blocked"]:
                        result_entry["output"] = f"[SECURITY BLOCK] {sec_eval['reason']}"
                        result_entry["security_status"] = "BLOCKED"
                    else:
                        sandbox_res = SafePythonSandbox.execute(code)
                        result_entry["output"] = sandbox_res["output"] if sandbox_res["success"] else sandbox_res["error"]
                        result_entry["code_executed"] = code
                        result_entry["security_status"] = "SANDBOXED_OK" if sandbox_res["success"] else "SANDBOX_RUNTIME_ERROR"
                        result_entry["provenance"] = ProvenanceMetadata(
                            source="ast_python_sandbox",
                            trust_level=0.90,
                            origin="code_execution",
                            agent="analyst",
                            content_type="computation",
                            security_label=SecurityLabel.TOOL_OUTPUT
                        ).to_dict()

            except Exception as tool_err:
                logger.error(f"Analyst tool execution error on task {task_id}: {tool_err}")
                result_entry["output"] = f"Tool Failure: {str(tool_err)}"
                result_entry["security_status"] = "TOOL_ERROR"

            return result_entry

        # Execute all subtasks concurrently for speed
        task_results = await asyncio.gather(*[execute_task(t) for t in subtasks])

        # Step 4: Accumulate novel scraped websites into cumulative state ledger
        seen_urls = set()
        final_articles = []
        for a in existing_articles:
            u = a.get("url")
            if u and u not in seen_urls:
                seen_urls.add(u)
                final_articles.append(a)

        for r in task_results:
            for it in r.get("scraped_items", []):
                u = it.get("url")
                if u and u not in seen_urls:
                    seen_urls.add(u)
                    final_articles.append(it)
        
        state["scraped_articles"] = final_articles

        # Fast-synthesize preliminary answer directly from tool findings (saves 30s LLM queue stall)
        valid_findings = [str(r.get("output", "")).strip() for r in task_results if r.get("output")]
        if valid_findings:
            prelim_answer = " | ".join(valid_findings)
            state_delta = [f"Direct content extracted from {len(final_articles)} visited websites"]
        else:
            prelim_answer = "Initial findings extracted from executed tools."
            state_delta = ["Awaiting Critic verification of external tool outputs"]

        state["execution"] = {
            "task_results": task_results,
            "preliminary_answer": prelim_answer,
            "state_delta": state_delta,
            "total_websites_visited": len(final_articles)
        }
        state["state_delta"] = state_delta
        state["tool_outputs"] = task_results
        state["status"] = f"Analyst scraped {len(final_articles)} websites across loops ({len(task_results)} tasks executed in Loop {current_cycle})"
        
        state["logs"].append({
            "stage": "analyst",
            "output": state["execution"]
        })
        return state

analyst = AnalystAgent()
