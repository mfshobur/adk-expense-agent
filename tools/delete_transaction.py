from typing import Optional
from difflib import get_close_matches

from tools.sheets_utils import sheet, to_datetime, parse_date_mmddyyyy


def delete_transaction_tool(
    name: str,
    date_str: Optional[str] = None,
    category: Optional[str] = None,
    fuzzy_threshold: float = 0.6,
    delete_all_matches: bool = False
):
    """
    Delete one or more transaction rows from the Google Sheet with fuzzy matching.

    Args:
        name: Item name or partial phrase to search for (e.g. 'yogurt', 'plane ticket')
        date_str: Optional date filter (MM/DD/YYYY) for additional safety
        category: Optional category filter for additional safety
        fuzzy_threshold: Similarity cutoff (0-1, default 0.6)
        delete_all_matches: If True, delete all matches. If False, only delete if single match found.

    Returns:
        Dict with status, message, deleted_count, and deleted_items

    Examples:
        # Delete single match
        delete_transaction_tool(name="yogurt")

        # Delete with date filter for safety
        delete_transaction_tool(name="coffee", date_str="11/15/2025")

        # Delete all matches
        delete_transaction_tool(name="snack", delete_all_matches=True)
    """

    try:
        # Get all records
        records = sheet.get_all_records(value_render_option="UNFORMATTED_VALUE")

        if not records:
            return {
                "status": "error",
                "message": "No data found in sheet",
                "deleted_count": 0,
                "deleted_items": []
            }

        name_lower = name.lower().strip()

        # Build list of all names for fuzzy matching
        all_names = [r["Name"].strip() for r in records]

        # Combine fuzzy and substring matches
        fuzzy_matches = set(get_close_matches(name, all_names, n=10, cutoff=fuzzy_threshold))
        substring_matches = {n for n in all_names if name_lower in n.lower()}
        matched_names = list(fuzzy_matches.union(substring_matches))

        if not matched_names:
            return {
                "status": "not_found",
                "message": f"No transactions found matching '{name}'",
                "deleted_count": 0,
                "deleted_items": []
            }

        # Find rows to delete (with additional filters if provided)
        rows_to_delete = []
        deleted_items = []

        for i, record in enumerate(records, start=2):  # Start at 2 (row 1 is header)
            rec_name = record["Name"].strip()

            # Check if name matches
            if rec_name not in matched_names:
                continue

            # Apply optional date filter
            if date_str:
                try:
                    record_date = to_datetime(record["Date"])
                    filter_date = parse_date_mmddyyyy(date_str)
                    if record_date.date() != filter_date.date():
                        continue
                except Exception:
                    continue  # Skip if date parsing fails

            # Apply optional category filter
            if category:
                if record.get("Category", "").lower().strip() != category.lower().strip():
                    continue

            # This row matches all criteria
            rows_to_delete.append(i)
            deleted_items.append({
                "name": rec_name,
                "amount": record.get("Amount"),
                "category": record.get("Category"),
                "date": record.get("Date"),
                "notes": record.get("Notes", "")
            })

        if not rows_to_delete:
            filter_msg = []
            if date_str:
                filter_msg.append(f"date={date_str}")
            if category:
                filter_msg.append(f"category={category}")

            filters = f" with filters: {', '.join(filter_msg)}" if filter_msg else ""

            return {
                "status": "not_found",
                "message": f"Found similar names {matched_names} but no matches{filters}",
                "deleted_count": 0,
                "deleted_items": []
            }

        # Safety check: if multiple matches and delete_all_matches is False
        if len(rows_to_delete) > 1 and not delete_all_matches:
            return {
                "status": "multiple_matches",
                "message": f"Found {len(rows_to_delete)} matches. Set delete_all_matches=True to delete all, or add date/category filters to narrow down.",
                "deleted_count": 0,
                "deleted_items": deleted_items,
                "matches_found": len(rows_to_delete)
            }

        # Group sorted row numbers into contiguous (start, end) ranges,
        # then delete in reverse order to avoid row-index shifting.
        sorted_rows = sorted(rows_to_delete)
        ranges = []
        start = end = sorted_rows[0]
        for r in sorted_rows[1:]:
            if r == end + 1:
                end = r
            else:
                ranges.append((start, end))
                start = end = r
        ranges.append((start, end))

        for start, end in reversed(ranges):
            sheet.delete_rows(start, end)

        return {
            "status": "success",
            "message": f"Successfully deleted {len(rows_to_delete)} transaction(s)",
            "deleted_count": len(rows_to_delete),
            "deleted_items": deleted_items
        }

    except Exception as e:
        return {
            "status": "error",
            "message": f"Error deleting transaction: {str(e)}",
            "deleted_count": 0,
            "deleted_items": []
        }
