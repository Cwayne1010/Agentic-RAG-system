import asyncio
from ddgs import DDGS


async def web_search(query: str, max_results: int = 5) -> list[dict]:
    """
    Search the web using DuckDuckGo. Returns a list of result dicts:
    [{"title": str, "url": str, "body": str}]

    DuckDuckGo's DDGS().text() is blocking — run in thread pool.
    """
    def _search():
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "body": r.get("body", ""),
                })
        return results

    return await asyncio.to_thread(_search)
