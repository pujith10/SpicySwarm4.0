from langchain_community.tools import DuckDuckGoSearchRun
import asyncio

async def test_search():
    try:
        search = DuckDuckGoSearchRun()
        print("Running search for 'weather in Delhi'...")
        result = await asyncio.to_thread(search.run, "weather in Delhi")
        print(f"Result length: {len(result)}")
        print(f"Result snippet: {result[:200]}")
    except Exception as e:
        print(f"Search failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_search())
