import json
import logging
import re
from typing import Dict, Any, List
from urllib.parse import urlparse
from langchain_core.prompts import ChatPromptTemplate
from backend.pipeline.state import PipelineState
from backend.agents.utils import safe_llm_call
from dotenv import load_dotenv

logger = logging.getLogger(__name__)
load_dotenv()

SYNTHESIZER_SYSTEM = """You are an expert AI intelligence assistant providing a direct, comprehensive, and conversational answer in the style of ChatGPT and Perplexity.

CORE RESPONSE PRINCIPLES:
1. DIRECT, CONVERSATIONAL ANSWER:
   - Do NOT write a rigid academic report (do NOT use "1. Executive Summary", "2. In-Depth Thematic Analysis", "Research Title", or "Verification Matrix").
   - Answer the user's prompt directly, clearly, and authoritatively from the very first sentence.
   - Structure your response naturally using conversational markdown: clear thematic subheadings (e.g. `### Key Announcements`, `### Technical Breakdown`, `### Comparison & Impact`), structured bullet points, and clean explanations.

2. INLINE CITATIONS:
   - Cite verified information from the provided sources using inline bracket citations like `[1]`, `[2]`, `[3]` next to relevant facts, releases, statistics, or quotes.
   - Match the citation numbers directly to the provided sources list.

3. PERFECT COMPARISON TABLES:
   - If comparing companies, models, features, benchmarks, or specs, include a clean, standard Markdown table with 3-5 vertical columns (e.g. `| Category / Feature | Company A | Company B | Company C |`).
   - Keep table cells concise, readable, and well-proportioned. Never dump large raw text blocks into table cells.

4. SOURCES & REFERENCES:
   - Conclude your answer with a clean `### Sources & References` list referencing the numbered sources with Markdown links: `[1] [Title](url) - domain.com`.

5. ZERO SYSTEM NOISE:
   - Output ONLY the clean answer in Markdown. Do not include JSON wrappers, system debug logs, or internal agent labels."""

class SynthesizerAgent:
    def __init__(self):
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", SYNTHESIZER_SYSTEM),
            ("human", (
                "User Question: {query}\n\n"
                "Verified Sources Visited & Scraped Content:\n{sources_context}\n\n"
                "Preliminary Findings:\n{preliminary_answer}\n\n"
                "Synthesize a clear, direct, ChatGPT-style answer with inline citations [1], [2], clean tables if comparing items, and a sources list at the end."
            ))
        ])

    async def run(self, state: PipelineState) -> Dict[str, Any]:
        scraped_articles = state.get("scraped_articles", [])
        execution = state.get("execution", {})
        prelim_ans = execution.get("preliminary_answer", "")

        # Build clean unique sources list with indices [1], [2], ...
        seen_urls = set()
        unique_sources = []
        sources_context_lines = []

        for a in scraped_articles:
            url = (a.get("url") or "").strip()
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            
            try:
                domain = urlparse(url).netloc.replace("www.", "")
            except Exception:
                domain = "web"

            idx = len(unique_sources) + 1
            title = a.get("title") or domain
            raw_content = a.get("content", "").replace("\r", " ").strip()
            snippet = re.sub(r"\s+", " ", raw_content)[:1200]

            source_item = {
                "id": idx,
                "url": url,
                "domain": domain,
                "title": title,
                "snippet": snippet[:200]
            }
            unique_sources.append(source_item)
            sources_context_lines.append(f"[{idx}] {title} ({domain})\nURL: {url}\nContent: {snippet}\n")

        sources_context = "\n".join(sources_context_lines) if sources_context_lines else "No specific web sources retrieved."
        state["sources"] = unique_sources

        try:
            response = await safe_llm_call(
                self.prompt,
                {
                    "query": state["query"],
                    "sources_context": sources_context[:5000],
                    "preliminary_answer": prelim_ans or "Analysis compiled from live web intelligence."
                },
                agent_name="synthesizer"
            )

            content = (response.content or "").strip()

            # Clean code fences if wrapped
            if content.startswith("```markdown") and content.endswith("```"):
                content = content[len("```markdown"): -3].strip()
            elif content.startswith("```") and content.endswith("```"):
                content = content[3:-3].strip()

            # Clean JSON envelopes if any model wrapped it
            if content.startswith("{") and ("answer" in content or "response" in content):
                try:
                    clean_json = re.sub(r'\\([^"\\/bfnrtu])', r'\1', content)
                    parsed = json.loads(clean_json, strict=False)
                    content = parsed.get("answer") or parsed.get("response") or parsed.get("research_report") or content
                except Exception:
                    pass

            # Extract first paragraph as concise final_answer summary
            first_para = content.split("\n\n")[0].replace("#", "").strip()
            if len(first_para) > 300:
                first_para = first_para[:297] + "..."
            final_ans = first_para if first_para else (prelim_ans or "Answer synthesized from verified sources.")

            state["final_answer"] = final_ans
            state["human_resolution"] = content
            state["status"] = f"Answer synthesized across {len(unique_sources)} live sources."
            state["logs"].append({
                "stage": "synthesizer",
                "output": {
                    "final_answer": final_ans,
                    "sources_count": len(unique_sources),
                    "response_length": len(content)
                }
            })
            return state

        except Exception as e:
            logger.error(f"Synthesizer error: {e}")
            # Build direct response from preliminary findings without synthetic templates or raw table dumps
            lines = [f"{prelim_ans}\n"]
            if unique_sources:
                lines.append("\n### Sources & References")
                for s in unique_sources:
                    lines.append(f"[{s['id']}] [{s['title']}]({s['url']}) - {s['domain']}")

            direct_ans = "\n".join(lines)
            state["final_answer"] = prelim_ans or "Synthesized from live web intelligence."
            state["human_resolution"] = direct_ans
            state["status"] = "Answer synthesized from verified web findings."
            state["logs"].append({
                "stage": "synthesizer",
                "output": {"final_answer": state["final_answer"]}
            })
            return state

synthesizer = SynthesizerAgent()

