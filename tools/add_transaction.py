from datetime import date, datetime
from typing import Optional
import re
import logging

from tools.sheets_utils import sheet

logger = logging.getLogger(__name__)

# Valid category whitelist
VALID_CATEGORIES = {
    'Food', 'Health & Wellness', 'Snack', 'Bills & Utilities',
    'Entertainment', 'Transport', 'Education', 'Charity', 'Shopping'
}

def add_transaction_tool(
    name: str,
    amount: float,
    category: str,
    date_str: Optional[str] = None,
    notes: str = "",
):
    """
    Add a new transaction row to the Google Sheet with input validation.

    Args:
        name: Item name (e.g. 'Yogurt')
        amount: Amount in IDR (numeric, positive, max 100M)
        category: Category name ('Food', 'Health & Wellness', 'Snack', 'Bills & Utilities', 'Entertainment', 'Transport', 'Education', 'Charity', 'Shopping')
        date_str: Optional date in (MM/DD/YYYY) (default = today)
        notes: Optional note for the transaction
    """
    try:
        # Validate name
        if not name or not isinstance(name, str):
            return {"status": "error", "message": "Name is required and must be text"}

        if len(name) > 100:
            return {"status": "error", "message": "Name must be 100 characters or less"}

        # Sanitize name - remove potential injection characters
        name = re.sub(r'[<>\"\'=;]', '', name).strip()
        if not name:
            return {"status": "error", "message": "Name contains only invalid characters"}

        # Validate amount
        if not isinstance(amount, (int, float)):
            return {"status": "error", "message": "Amount must be a number"}

        if amount <= 0:
            return {"status": "error", "message": "Amount must be positive"}

        if amount > 100_000_000:
            return {"status": "error", "message": "Amount exceeds maximum limit (100,000,000 IDR)"}

        # Validate category
        category = category.strip()
        if category not in VALID_CATEGORIES:
            return {
                "status": "error",
                "message": f"Invalid category. Must be one of: {', '.join(sorted(VALID_CATEGORIES))}"
            }

        # Validate and parse date
        if date_str:
            try:
                # Try parsing MM/DD/YYYY format
                parsed_date = datetime.strptime(date_str, "%m/%d/%Y")

                # Ensure reasonable date range (2020-2030)
                if parsed_date.year < 2020 or parsed_date.year > 2030:
                    return {"status": "error", "message": "Date must be between 2020 and 2030"}

                # Use the validated date string
                date_str = parsed_date.strftime("%m/%d/%Y")
            except ValueError:
                return {"status": "error", "message": "Date must be in MM/DD/YYYY format (e.g., 01/15/2025)"}
        else:
            # Default to today
            date_str = date.today().strftime("%m/%d/%Y")

        # Validate notes
        if len(notes) > 500:
            return {"status": "error", "message": "Notes must be 500 characters or less"}

        # Sanitize notes
        notes = re.sub(r'[<>\"\'=;]', '', notes).strip()

        # Created timestamp
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Append row data
        sheet.append_row(
            [name, amount, category, created_at, date_str, notes],
            value_input_option="USER_ENTERED",
        )

        return {
            "status": "success",
            "message": f"Transaction added: {name} (Rp{amount:,.0f} on {date_str})"
        }

    except Exception as e:
        logger.error(f"Error adding transaction: {e}")
        return {"status": "error", "message": "Failed to add transaction. Please try again."}