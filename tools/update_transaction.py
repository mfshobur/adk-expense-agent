from typing import Optional
from difflib import get_close_matches
from datetime import datetime
import re
import logging

from tools.sheets_utils import sheet, gs_serial_to_datetime, VALID_CATEGORIES

logger = logging.getLogger(__name__)

def update_transaction_tool(
    name: str,
    field: str,
    new_value: str,
    date_str: Optional[str] = None,
    fuzzy_threshold: float = 0.6,
):
    """
    Update one or more transaction rows in the Google Sheet, with fuzzy or partial matching for names.

    Args:
        name: Item name or partial phrase (e.g. 'mom', 'plane ticket')
        field: Column to update ('Amount', 'Category', 'Notes', etc.)
        new_value: The new value to set
        date_str: Optional date filter (MM/DD/YYYY)
        fuzzy_threshold: Similarity cutoff (0-1)
    """

    valid_fields = ["Name", "Amount", "Category", "Created", "Date", "Notes"]
    if field.capitalize() not in valid_fields:
        return {
            "status": "error",
            "message": f"Invalid field '{field}'. Must be one of {valid_fields}"
        }

    field_cap = field.capitalize()

    if field_cap == "Amount":
        try:
            amount_val = float(new_value)
            if amount_val <= 0:
                return {"status": "error", "message": "Amount must be positive"}
            if amount_val > 100_000_000:
                return {"status": "error", "message": "Amount exceeds maximum limit (100,000,000 IDR)"}
        except ValueError:
            return {"status": "error", "message": "Amount must be a valid number"}

    elif field_cap == "Category":
        new_value = new_value.strip()
        if new_value not in VALID_CATEGORIES:
            return {
                "status": "error",
                "message": f"Invalid category. Must be one of: {', '.join(sorted(VALID_CATEGORIES))}"
            }

    elif field_cap == "Name":
        if len(new_value) > 100:
            return {"status": "error", "message": "Name must be 100 characters or less"}
        new_value = re.sub(r'[<>\"\'=;]', '', new_value).strip()
        if not new_value:
            return {"status": "error", "message": "Name contains only invalid characters"}

    elif field_cap == "Notes":
        if len(new_value) > 500:
            return {"status": "error", "message": "Notes must be 500 characters or less"}
        new_value = re.sub(r'[<>\"\'=;]', '', new_value).strip()

    elif field_cap == "Date":
        try:
            parsed_date = datetime.strptime(new_value, "%m/%d/%Y")
            if parsed_date.year < 2020 or parsed_date.year > 2030:
                return {"status": "error", "message": "Date must be between 2020 and 2030"}
            new_value = parsed_date.strftime("%m/%d/%Y")
        except ValueError:
            return {"status": "error", "message": "Date must be in MM/DD/YYYY format"}

    if not name or len(name) > 100:
        return {"status": "error", "message": "Search name must be between 1-100 characters"}

    records = sheet.get_all_records(value_render_option="UNFORMATTED_VALUE")
    target_col_index = valid_fields.index(field.capitalize()) + 1
    updated_rows = 0
    name_lower = name.lower().strip()

    names = [r["Name"].strip() for r in records]

    fuzzy_matches = set(get_close_matches(name, names, n=5, cutoff=fuzzy_threshold))
    substring_matches = {n for n in names if name_lower in n.lower()}
    matches = list(fuzzy_matches.union(substring_matches))

    if not matches:
        return {"status": "not_found", "message": f"No match found similar to '{name}'"}

    # Collect cell references for batch update
    col_letter = chr(ord('A') + target_col_index - 1)
    cells_to_update = []

    for i, record in enumerate(records, start=2):
        rec_name = record["Name"].strip()
        if rec_name in matches:
            if not date_str:
                cells_to_update.append(f"{col_letter}{i}")
                updated_rows += 1
            else:
                record_date_raw = record["Date"]
                date_match = False

                if isinstance(record_date_raw, (int, float)):
                    dt = gs_serial_to_datetime(record_date_raw)
                    if dt and dt.strftime("%m/%d/%Y") == date_str:
                        date_match = True
                else:
                    record_date = str(record_date_raw).strip()
                    if record_date == date_str:
                        date_match = True
                    else:
                        try:
                            dt = datetime.strptime(record_date, "%m/%d/%Y")
                            if dt.strftime("%m/%d/%Y") == date_str:
                                date_match = True
                        except:
                            pass

                if date_match:
                    cells_to_update.append(f"{col_letter}{i}")
                    updated_rows += 1

    if cells_to_update:
        sheet.batch_update([{
            'range': cell_ref,
            'values': [[new_value]],
        } for cell_ref in cells_to_update], value_input_option="USER_ENTERED")

    if updated_rows == 0:
        return {
            "status": "not_found",
            "message": f"Found similar name(s): {matches}, but no matching date ({date_str})"
        }

    return {
        "status": "success",
        "message": f"Updated {updated_rows} row(s): {matches} → {field} = {new_value}"
    }