from google.adk.agents.llm_agent import Agent
from google.adk.models import Gemini
from google.genai import types
from google.adk.tools import load_memory
import os
from tools import (
    add_transaction_tool, update_transaction_tool, delete_transaction_tool,
    check_today_date_tool, check_data_exists_tool,
    analyze_expenses_tool,
)

async def auto_save_to_memory(callback_context):
    """Automatically save session to memory after each agent turn."""
    await callback_context._invocation_context.memory_service.add_session_to_memory(
        callback_context._invocation_context.session
    )

retry_config = types.HttpRetryOptions(
    attempts=5,
    exp_base=7,
    initial_delay=1,
    http_status_codes=[429, 500, 503, 504]
)

# Load instruction from environment variable or use default
AGENT_INSTRUCTION = os.getenv('AGENT_INSTRUCTION')

expense_agent = Agent(
    model=Gemini(
        model='gemini-2.5-flash',
        retry_options=retry_config
    ),
    name='expense_agent',
    description='An agent that helps manage and track expenses using Google Sheets.',
    instruction=AGENT_INSTRUCTION,
    tools=[
        add_transaction_tool,
        update_transaction_tool,
        delete_transaction_tool,
        check_today_date_tool,
        check_data_exists_tool,
        analyze_expenses_tool,
        load_memory
    ],
    after_agent_callback=auto_save_to_memory
)
