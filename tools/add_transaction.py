from datetime import date, datetime
from typing import Optional
import json
import re
import logging

from tools.sheets_utils import sheet, VALID_CATEGORIES

logger = logging.getLogger(__name__)

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


def add_transactions_tool(transactions_json: str):
    """
    Batch-add multiple transactions to the Google Sheet in a single API call.

    Args:
        transactions_json: A JSON string containing an array of transaction objects.
            Each object must have:
            - name (str, required): Item name
            - amount (float, required): Amount in IDR (positive, max 100M)
            - category (str, required): Must be one of the valid categories
            - date_str (str, optional): Date in MM/DD/YYYY format (default = today)
            - notes (str, optional): Note for the transaction

            Example: '[{"name": "Coffee", "amount": 25000, "category": "Food"}, {"name": "Bus ticket", "amount": 5000, "category": "Transport"}]'
    """
    try:
        transactions = json.loads(transactions_json)
    except (json.JSONDecodeError, TypeError):
        return {"status": "error", "message": "transactions_json must be a valid JSON array string"}

    if not isinstance(transactions, list) or not transactions:
        return {"status": "error", "message": "transactions_json must contain a non-empty JSON array"}

    if len(transactions) > 50:
        return {"status": "error", "message": "Maximum 50 transactions per batch"}

    rows_to_add = []
    errors = []
    today_str = date.today().strftime("%m/%d/%Y")
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for idx, txn in enumerate(transactions):
        if not isinstance(txn, dict):
            errors.append({"index": idx, "message": "Item must be a dict"})
            continue

        t_name = txn.get("name", "")
        t_amount = txn.get("amount")
        t_category = txn.get("category", "")
        t_date_str = txn.get("date_str", "")
        t_notes = txn.get("notes", "")

        # Validate name
        if not t_name or not isinstance(t_name, str):
            errors.append({"index": idx, "message": "Name is required and must be text"})
            continue
        if len(t_name) > 100:
            errors.append({"index": idx, "message": "Name must be 100 characters or less"})
            continue
        t_name = re.sub(r'[<>\"\'=;]', '', t_name).strip()
        if not t_name:
            errors.append({"index": idx, "message": "Name contains only invalid characters"})
            continue

        # Validate amount
        if not isinstance(t_amount, (int, float)):
            errors.append({"index": idx, "message": f"Amount must be a number, got {type(t_amount).__name__}"})
            continue
        if t_amount <= 0:
            errors.append({"index": idx, "message": "Amount must be positive"})
            continue
        if t_amount > 100_000_000:
            errors.append({"index": idx, "message": "Amount exceeds maximum limit (100,000,000 IDR)"})
            continue

        # Validate category
        t_category = str(t_category).strip()
        if t_category not in VALID_CATEGORIES:
            errors.append({"index": idx, "message": f"Invalid category '{t_category}'"})
            continue

        # Validate date
        if t_date_str:
            try:
                parsed = datetime.strptime(t_date_str, "%m/%d/%Y")
                if parsed.year < 2020 or parsed.year > 2030:
                    errors.append({"index": idx, "message": "Date must be between 2020 and 2030"})
                    continue
                t_date_str = parsed.strftime("%m/%d/%Y")
            except ValueError:
                errors.append({"index": idx, "message": "Date must be in MM/DD/YYYY format"})
                continue
        else:
            t_date_str = today_str

        # Validate notes
        if len(t_notes) > 500:
            errors.append({"index": idx, "message": "Notes must be 500 characters or less"})
            continue
        t_notes = re.sub(r'[<>\"\'=;]', '', t_notes).strip()

        rows_to_add.append([t_name, float(t_amount), t_category, created_at, t_date_str, t_notes])

    if not rows_to_add:
        return {
            "status": "error",
            "message": "No valid transactions to add",
            "added_count": 0,
            "error_count": len(errors),
            "errors": errors,
        }

    try:
        sheet.append_rows(rows_to_add, value_input_option="USER_ENTERED")
    except Exception as e:
        logger.error(f"Error batch-adding transactions: {e}")
        return {"status": "error", "message": "Failed to add transactions. Please try again."}

    return {
        "status": "success",
        "message": f"Added {len(rows_to_add)} transaction(s)",
        "added_count": len(rows_to_add),
        "error_count": len(errors),
        "errors": errors,
    }