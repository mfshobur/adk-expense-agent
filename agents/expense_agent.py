from google.adk.agents.llm_agent import Agent
from tools import (
    add_transaction_tool, add_transactions_tool,
    update_transaction_tool, delete_transaction_tool,
    check_data_exists_tool, analyze_expenses_tool,
)
from .model_config import get_model

EXPENSE_INSTRUCTION = """You are an expense tracking specialist. You manage transactions in Google Sheets.

## Rules
- Date format is always MM/DD/YYYY (e.g. 01/15/2025).
- Before adding a transaction, always use check_data_exists_tool to check if a similar transaction already exists to avoid duplicates.
- Valid categories: Food, Health & Wellness, Snack, Bills & Utilities, Entertainment, Transport, Education, Charity, Shopping.
- Amounts are in IDR (Indonesian Rupiah). Maximum 100,000,000 per transaction.
- When the user wants to add multiple items at once, use add_transactions_tool for batch adding.
- When updating or deleting, confirm the target transaction with the user if ambiguous.
- When analyzing expenses, use analyze_expenses_tool for date-range queries and summaries.
"""

expense_sub_agent = Agent(
    model=get_model(),
    name='expense_agent',
    description='Manages expense tracking: add, update, delete, search, and analyze transactions in Google Sheets.',
    instruction=EXPENSE_INSTRUCTION,
    tools=[
        add_transaction_tool,
        add_transactions_tool,
        update_transaction_tool,
        delete_transaction_tool,
        check_data_exists_tool,
        analyze_expenses_tool,
    ],
)
