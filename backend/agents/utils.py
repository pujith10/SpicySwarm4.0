import asyncio
import time
import logging
import os
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI

from backend.resilience.health_tracker import health_tracker
from backend.resilience.circuit_breaker import circuit_registry
from backend.resilience.failure_injector import failure_injector
from backend.config import config

load_dotenv()
logger = logging.getLogger(__name__)

# Precedence hierarchy:
# Critic (1) > Architect (2) > Synthesizer (3) > Analyst (4) > Librarian (5)
# Verified ultra-fast free models on OpenRouter:
AGENT_PRIMARY_MODELS: Dict[str, str] = {
    "critic": "nvidia/nemotron-3-ultra-550b-a55b:free",
    "architect": "nvidia/nemotron-3-ultra-550b-a55b:free",
    "planner": "nvidia/nemotron-3-ultra-550b-a55b:free",
    "synthesizer": "nvidia/nemotron-3-ultra-550b-a55b:free",
    "analyst": "nvidia/nemotron-3-ultra-550b-a55b:free",
    "executor": "nvidia/nemotron-3-ultra-550b-a55b:free",
    "librarian": "nvidia/nemotron-3-ultra-550b-a55b:free",
}

# Remaining OpenRouter free models in descending order of power for fallbacks:
OPENROUTER_FALLBACK_MODELS: List[str] = [
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "nex-agi/nex-n2.5-pro:free",
    "nex-agi/nex-n2.5-mini:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "cohere/north-mini-code:free",
    "inclusionai/ling-3.0-flash-sante:free",
]

_openrouter_daily_limit_exhausted: bool = False

def _create_openrouter_llm(model_id: str, temperature: float = 0.0) -> ChatOpenAI:
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    return ChatOpenAI(
        model=model_id,
        api_key=api_key,
        base_url=base_url,
        temperature=temperature,
        timeout=25,
        max_tokens=4000,
        default_headers={
            "HTTP-Referer": "http://localhost:5173",
            "X-Title": "Spicy Swarm 4.0 - HAA",
        }
    )

async def safe_llm_call(
    prompt,
    variables: Dict[str, Any],
    agent_name: str = "general",
    primary_model: str = config.DEFAULT_PRIMARY_MODEL,
    secondary_model: str = config.DEFAULT_SECONDARY_MODEL,
    tertiary_model: str = config.DEFAULT_TERTIARY_MODEL,
    temperature: float = 0.0
):
    """
    Tiered LLM Cascading Engine:
    1. OpenRouter Primary Model for the specific agent (Critic -> Architect -> Synthesizer -> Analyst -> Librarian)
    2. OpenRouter Free Fallback Models (pool of models in descending power order)
    3. Fallback Tier A: Google Gemini (gemini-1.5-flash)
    4. Fallback Tier B: Groq Llama-3.3-70B (Failover on 404/500/trip)
    5. Fallback Tier C: Groq Llama-3.1-8B (Emergency speed tier on 429)
    6. Synthetic Diagnostic Fallback
    """
    global _openrouter_daily_limit_exhausted
    openrouter_key = os.getenv("OPENROUTER_API_KEY")

    # =========================================================================
    # STEP 1 & 2: OPENROUTER TIER (Agent Primary + OpenRouter Fallbacks)
    # =========================================================================
    if openrouter_key:
        normalized_agent = agent_name.lower().strip()
        primary_openrouter_model = AGENT_PRIMARY_MODELS.get(
            normalized_agent,
            "deepseek/deepseek-v4-flash-0731:free"
        )

        # Build prioritized sequence of models to attempt
        models_to_try = [primary_openrouter_model]
        for fb_model in OPENROUTER_FALLBACK_MODELS:
            if fb_model not in models_to_try:
                models_to_try.append(fb_model)

        for model_id in models_to_try:
            breaker_key = f"or_{model_id.replace('/', '_').replace(':', '_')}"
            cb = circuit_registry.get(breaker_key)
            metrics = health_tracker.get_provider(breaker_key)

            if not cb.can_execute():
                logger.info(f"OpenRouter [{model_id}] circuit is OPEN. Skipping to next model.")
                continue

            t0 = time.time()
            try:
                # Check fault injection hook if enabled
                fault_res = await failure_injector.maybe_inject_fault(breaker_key)
                if fault_res is not None:
                    return fault_res

                logger.info(f"Executing OpenRouter model [{model_id}] for agent [{agent_name}]...")
                llm = _create_openrouter_llm(model_id, temperature=temperature)
                chain = prompt | llm
                result = await chain.ainvoke(variables)

                latency = (time.time() - t0) * 1000
                metrics.record_success(latency)
                cb.record_success()
                logger.info(f"OpenRouter model [{model_id}] succeeded for [{agent_name}] in {latency:.1f}ms")
                return result

            except Exception as e:
                err_str = str(e)
                logger.warning(f"OpenRouter model [{model_id}] failed for agent [{agent_name}]: {err_str}")
                metrics.record_failure(err_str)
                cb.record_failure(e)

                # Check if this is an account-level daily limit on free models
                if "free-models-per-day" in err_str or "daily reset" in err_str:
                    logger.warning("OpenRouter free tier daily limit (50/day) detected. Halting attempts for shared free pool.")
                    _openrouter_daily_limit_exhausted = True
                    # If this wasn't deepseek, try deepseek once before giving up
                    if "deepseek" not in model_id:
                        continue
                    else:
                        break

        logger.warning(f"All OpenRouter models exhausted or rate-limited for [{agent_name}]. Proceeding to Google Gemini fallback.")

    # =========================================================================
    # STEP 3: FALLBACK TIER A - Google Gemini
    # =========================================================================
    gemini_breaker = circuit_registry.get("google_gemini")
    gemini_metrics = health_tracker.get_provider("google_gemini")

    if gemini_breaker.can_execute() and os.getenv("GOOGLE_API_KEY"):
        t0 = time.time()
        try:
            fault_res = await failure_injector.maybe_inject_fault("google_gemini")
            if fault_res is not None:
                return fault_res

            logger.info(f"Executing Fallback Tier A (Google Gemini: {primary_model}) for agent [{agent_name}]...")
            llm = ChatGoogleGenerativeAI(model=primary_model, temperature=temperature)
            chain = prompt | llm
            result = await chain.ainvoke(variables)

            latency = (time.time() - t0) * 1000
            gemini_metrics.record_success(latency)
            gemini_breaker.record_success()
            return result

        except Exception as e:
            err_str = str(e)
            logger.warning(f"Fallback Tier A (Google Gemini) failed: {err_str}. Cascading to Tier B (Groq 70B)...")
            gemini_metrics.record_failure(err_str)
            gemini_breaker.record_failure(e)
    else:
        logger.info("Fallback Tier A (Google Gemini) circuit OPEN or missing key. Fast-routing to Tier B (Groq 70B).")

    # =========================================================================
    # STEP 4: FALLBACK TIER B - Groq Llama-3.3-70B
    # =========================================================================
    groq70_breaker = circuit_registry.get("groq_70b")
    groq70_metrics = health_tracker.get_provider("groq_70b")

    if groq70_breaker.can_execute() and os.getenv("GROQ_API_KEY"):
        t0 = time.time()
        try:
            fault_res = await failure_injector.maybe_inject_fault("groq_70b")
            if fault_res is not None:
                return fault_res

            logger.info(f"Executing Fallback Tier B (Groq 70B: {secondary_model}) for agent [{agent_name}]...")
            llm = ChatGroq(model=secondary_model, temperature=temperature)
            chain = prompt | llm
            result = await chain.ainvoke(variables)

            latency = (time.time() - t0) * 1000
            groq70_metrics.record_success(latency)
            groq70_breaker.record_success()
            return result

        except Exception as e:
            err_str = str(e)
            groq70_metrics.record_failure(err_str)
            groq70_breaker.record_failure(e)

            if "429" in err_str or "rate limit" in err_str.lower():
                logger.warning("Fallback Tier B (Groq 70B) Rate Limit hit. Failing over to Tier C (Groq 8B)...")
            else:
                logger.error(f"Fallback Tier B error: {err_str}. Attempting Tier C failover...")

    # =========================================================================
    # STEP 5: FALLBACK TIER C - Groq Llama-3.1-8B (Emergency Speed Tier)
    # =========================================================================
    groq8_breaker = circuit_registry.get("groq_8b")
    groq8_metrics = health_tracker.get_provider("groq_8b")

    if groq8_breaker.can_execute() and os.getenv("GROQ_API_KEY"):
        t0 = time.time()
        try:
            fault_res = await failure_injector.maybe_inject_fault("groq_8b")
            if fault_res is not None:
                return fault_res

            logger.info(f"Executing Fallback Tier C (Groq 8B: {tertiary_model}) for agent [{agent_name}]...")
            llm_fallback = ChatGroq(model=tertiary_model, temperature=temperature)
            chain_fallback = prompt | llm_fallback
            result = await chain_fallback.ainvoke(variables)

            latency = (time.time() - t0) * 1000
            groq8_metrics.record_success(latency)
            groq8_breaker.record_success()
            return result

        except Exception as e_inner:
            groq8_metrics.record_failure(str(e_inner))
            groq8_breaker.record_failure(e_inner)
            logger.critical(f"All LLM tiers exhausted: {e_inner}")

    # Raise clear error if all tiers fail - no synthetic fallback
    err_msg = f"All LLM tiers exhausted for agent [{agent_name}]. No synthetic fallback allowed."
    logger.critical(err_msg)
    raise RuntimeError(err_msg)
