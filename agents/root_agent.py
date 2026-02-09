import os
from google.adk.agents.llm_agent import Agent
from google.adk.tools import load_memory
from tools import check_today_date_tool
from .model_config import get_model
from .expense_agent import expense_sub_agent
from .search_agent import search_sub_agent


async def auto_save_to_memory(callback_context):
    """Automatically save session to memory after each agent turn."""
    await callback_context._invocation_context.memory_service.add_session_to_memory(
        callback_context._invocation_context.session
    )


AGENT_INSTRUCTION = os.getenv('AGENT_INSTRUCTION', '')

ROOT_INSTRUCTION = f"""{AGENT_INSTRUCTION}

## Routing
- For expense-related requests (add, update, delete, search, or analyze transactions), delegate to the expense_agent.
- For internet search, general knowledge, news, or any question beyond expense tracking, delegate to the search_agent.
- Use check_today_date_tool when the user or a sub-agent needs to know today's date.
- Use load_memory to recall context from previous conversations when relevant.
"""

root_agent = Agent(
    model=get_model(),
    name='root_agent',
    description='Coordinator that routes to the right specialist agent.',
    instruction=ROOT_INSTRUCTION,
    sub_agents=[expense_sub_agent, search_sub_agent],
    tools=[check_today_date_tool, load_memory],
    after_agent_callback=auto_save_to_memory,
)
