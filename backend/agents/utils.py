import asyncio
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
import logging
import os

logger = logging.getLogger(__name__)

async def safe_llm_call(prompt, variables, primary_model="gemini-1.5-flash", secondary_model="llama-3.3-70b-versatile", tertiary_model="llama-3.1-8b-instant", temperature=0):
    """
    Triple-Tier Fallback:
    1. Google Gemini (High limits)
    2. Groq 70B (High reasoning)
    3. Groq 8B (Emergency speed)
    """
    # Tier 1: Google
    try:
        if os.getenv("GOOGLE_API_KEY"):
            llm = ChatGoogleGenerativeAI(model=primary_model, temperature=temperature)
            chain = prompt | llm
            return await chain.ainvoke(variables)
    except Exception as e:
        error_msg = str(e)
        if "404" in error_msg or "NOT_FOUND" in error_msg:
            logger.error(f"Tier 1 (Google) Model NOT FOUND: {primary_model}. Bypassing to Tier 2.")
        else:
            logger.warning(f"Tier 1 (Google) failed: {e}. Falling back to Tier 2 (Groq 70B)...")

    # Tier 2: Groq 70B
    try:
        llm = ChatGroq(model=secondary_model, temperature=temperature)
        chain = prompt | llm
        return await chain.ainvoke(variables)
    except Exception as e:
        if "429" in str(e) or "rate_limit" in str(e).lower():
            logger.warning(f"Tier 2 (Groq 70B) Rate Limit hit. Falling back to Tier 3 (Groq 8B)...")
            try:
                # Tier 3: Groq 8B
                llm_fallback = ChatGroq(model=tertiary_model, temperature=temperature)
                chain_fallback = prompt | llm_fallback
                return await chain_fallback.ainvoke(variables)
            except Exception as e_inner:
                logger.error(f"All LLM Tiers failed: {e_inner}")
                raise e_inner
        else:
            logger.error(f"Non-rate limit error in Tier 2: {e}")
            raise e
