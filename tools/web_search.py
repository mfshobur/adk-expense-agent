from ddgs import DDGS


def web_search_tool(query: str, max_results: int = 8):
    """
    Search the internet using DuckDuckGo. Returns instant answers (if available)
    and web search results with full snippets.

    Args:
        query: The search query string.
        max_results: Maximum number of web results to return (1-10, default 8).
    """
    max_results = max(1, min(max_results, 10))

    try:
        with DDGS() as ddgs:
            # Try instant answers first (direct factual answers)
            instant_answers = []
            try:
                for answer in ddgs.answers(query):
                    instant_answers.append({
                        "text": answer.get("text", ""),
                        "url": answer.get("url", ""),
                    })
            except Exception:
                pass

            # Web search results
            raw_results = list(ddgs.text(query, max_results=max_results))

        web_results = [
            {
                "title": r.get("title", ""),
                "url": r.get("href", ""),
                "snippet": r.get("body", ""),
            }
            for r in raw_results
        ]

        return {
            "status": "success",
            "query": query,
            "instant_answers": instant_answers,
            "results": web_results,
        }

    except Exception as e:
        return {"status": "error", "error": str(e)}
