from duckduckgo_search import DDGS


def web_search_tool(query: str, max_results: int = 5) -> dict:
    """
    Search the internet using DuckDuckGo.

    Args:
        query: The search query string.
        max_results: Maximum number of results to return (1-10, default 5).

    Returns:
        A dict with status and list of search results (title, url, snippet).
    """
    max_results = max(1, min(max_results, 10))

    try:
        with DDGS() as ddgs:
            raw_results = list(ddgs.text(query, max_results=max_results))

        results = [
            {
                "title": r.get("title", ""),
                "url": r.get("href", ""),
                "snippet": (r.get("body", "")[:300] + "...")
                if len(r.get("body", "")) > 300
                else r.get("body", ""),
            }
            for r in raw_results
        ]

        return {"status": "success", "query": query, "results": results}

    except Exception as e:
        return {"status": "error", "error": str(e)}
