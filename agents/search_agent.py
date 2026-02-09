from google.adk.agents.llm_agent import Agent
from tools import web_search_tool
from .model_config import get_model

SEARCH_INSTRUCTION = """You are an internet search specialist. You help users find real-time information, news, and general knowledge.

## Rules
- Use web_search_tool to search the internet for the user's query.
- Summarize the results clearly and concisely.
- Always cite the source URL when providing information from search results.
- If the search returns no results, let the user know and suggest alternative search terms.
- Be factual — do not make up information beyond what the search results provide.
"""

search_sub_agent = Agent(
    model=get_model(),
    name='search_agent',
    description='Searches the internet for real-time information, news, general knowledge, and answers questions beyond expense tracking.',
    instruction=SEARCH_INSTRUCTION,
    tools=[web_search_tool],
)
