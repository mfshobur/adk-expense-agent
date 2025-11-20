from typing import List, Dict
from datetime import datetime, timedelta
from difflib import get_close_matches

import pandas as pd

from tools.sheets_utils import sheet

# Helpers
def _gs_serial_to_datetime(serial: float) -> datetime:
    """
    Convert Google Sheets serial (days since 1899-12-30) to datetime.
    """
    base = datetime(1899, 12, 30)
    return base + timedelta(days=float(serial))

def _parse_date_mmddyyyy(date_str: str) -> datetime:
    """
    Parse MM/DD/YYYY (e.g. '11/04/2025').
    """
    return datetime.strptime(date_str, "%m/%d/%Y")

def _to_datetime(val) -> datetime:
    """
    Robust converter: accepts
      - float/int (Google serial)
      - 'MM/DD/YYYY' string
      - datetime already
    Returns datetime or raises Exception.
    """
    if isinstance(val, datetime):
        return val
    if isinstance(val, (float, int)):
        return _gs_serial_to_datetime(float(val))
    s = str(val).strip()
    if not s:
        raise ValueError("Empty date")
    # try MM/DD/YYYY first
    try:
        return _parse_date_mmddyyyy(s)
    except Exception:
        # try ISO-ish fallback
        try:
            return datetime.fromisoformat(s)
        except Exception:
            raise

# Main tool
def check_data_exists_tool(
    name: str = "",
    category: str = "",
    date: str = "",
    start_date: str = "",
    end_date: str = "",
    days_ago: str = "",
    fuzzy_threshold: float = 0.6,
) -> Dict:
    """
    Search transactions in sheet using pandas for fast queries.

    Parameters (Google-AI-friendly types):
    - name: single string, or comma-separated list ("yogurt,coffee")
    - category: exact category name (case-insensitive)
    - date: MM/DD/YYYY
    - start_date, end_date: MM/DD/YYYY
    - days_ago: integer as string (e.g. "2" means today - 2 days)
    - fuzzy_threshold: 0..1 for get_close_matches

    Returns:
    {
      "exists": bool,
      "match_count": int,
      "matches": [unique matched names],
      "details": [list of row dicts],
      "filters_used": {...}
    }
    """
    # Load records into DataFrame
    records = sheet.get_all_records(value_render_option="UNFORMATTED_VALUE")
    if not records:
        return {
            "exists": False,
            "match_count": 0,
            "matches": [],
            "details": [],
            "filters_used": {
                "name": name,
                "category": category,
                "date": date,
                "start_date": start_date,
                "end_date": end_date,
                "days_ago": days_ago,
            },
        }

    df = pd.DataFrame(records)

    # ensure expected columns exist
    expected_cols = {"Name", "Amount", "Category", "Created", "Date", "Notes"}
    missing = expected_cols - set(df.columns)
    if missing:
        #if Date column missing, return no results
        return {
            "exists": False,
            "match_count": 0,
            "matches": [],
            "details": [],
            "message": f"Missing columns in sheet: {sorted(list(missing))}",
            "filters_used": {
                "name": name,
                "category": category,
                "date": date,
                "start_date": start_date,
                "end_date": end_date,
                "days_ago": days_ago,
            },
        }

    # Normalize and parse date column into datetime
    def safe_to_dt(x):
        try:
            return _to_datetime(x)
        except Exception:
            return pd.NaT

    df["__parsed_date"] = df["Date"].apply(safe_to_dt)
    # drop rows without valid date
    df = df[~df["__parsed_date"].isna()].copy()
    if df.empty:
        return {
            "exists": False,
            "match_count": 0,
            "matches": [],
            "details": [],
            "message": "No rows with parseable Date values",
            "filters_used": {
                "name": name,
                "category": category,
                "date": date,
                "start_date": start_date,
                "end_date": end_date,
                "days_ago": days_ago,
            },
        }

    # convert to date only for comparisons
    df["__date_only"] = df["__parsed_date"].dt.date

    # Resolve date filters (single / range / days_ago)
    today = datetime.today().date()

    start_dt = None
    end_dt = None
    single_date = None

    # If days_ago is provided, treat as RANGE: (today - days_ago), today
    if days_ago.strip():
        try:
            offset = int(days_ago)
            start_dt = today - timedelta(days=offset)
            end_dt = today
        except ValueError:
            start_dt = end_dt = None

    # Otherwise if user explicitly provides a single date
    elif date.strip():
        try:
            single_date = _parse_date_mmddyyyy(date).date()
        except Exception:
            single_date = None

    # Or if user provides explicit range
    elif start_date.strip() and end_date.strip():
        try:
            start_dt = _parse_date_mmddyyyy(start_date).date()
            end_dt = _parse_date_mmddyyyy(end_date).date()
        except Exception:
            start_dt = end_dt = None

    # Apply date filters
    mask = pd.Series([True] * len(df), index=df.index)

    if single_date:
        mask &= (df["__date_only"] == single_date)

    if start_dt and end_dt:
        mask &= (df["__date_only"] >= start_dt) & (df["__date_only"] <= end_dt)

    df = df[mask]
    if df.empty:
        return {
            "exists": False,
            "match_count": 0,
            "matches": [],
            "details": [],
            "filters_used": {
                "name": name,
                "category": category,
                "date": date,
                "start_date": start_date,
                "end_date": end_date,
                "days_ago": days_ago,
            },
        }

    # Category filter (case insensitive exact match)
    if category.strip():
        cat = category.strip().lower()
        df = df[df["Category"].astype(str).str.strip().str.lower() == cat]
        if df.empty:
            return {
                "exists": False,
                "match_count": 0,
                "matches": [],
                "details": [],
                "filters_used": {
                    "name": name,
                    "category": category,
                    "date": date,
                    "start_date": start_date,
                    "end_date": end_date,
                    "days_ago": days_ago,
                },
            }

    # Name / fuzzy matching
    # build canonical list of names present (strip)
    df["__name_clean"] = df["Name"].astype(str).str.strip()
    all_names = df["__name_clean"].unique().tolist()

    names_to_check: List[str] = (
        [n.strip() for n in name.split(",") if n.strip()] if name.strip() else []
    )

    if names_to_check:
        # find possible name matches from available names
        matched_name_set = set()
        for n in names_to_check:
            lower_n = n.lower()
            fuzzy = set(get_close_matches(n, all_names, n=5, cutoff=fuzzy_threshold))
            substr = {x for x in all_names if lower_n in x.lower()}
            possibles = fuzzy.union(substr)
            matched_name_set.update(possibles)
        # filter df to only rows whose cleaned name is in matched_name_set
        df = df[df["__name_clean"].isin(matched_name_set)]
        if df.empty:
            return {
                "exists": False,
                "match_count": 0,
                "matches": [],
                "details": [],
                "filters_used": {
                    "name": name,
                    "category": category,
                    "date": date,
                    "start_date": start_date,
                    "end_date": end_date,
                    "days_ago": days_ago,
                },
            }

    # Prepare results
    # convert DataFrame rows to list of dicts (original column names)
    df_result = df.drop(columns=["__parsed_date", "__date_only", "__name_clean"], errors="ignore")
    details = []
    for row in df_result.to_dict(orient="records"):
        d = row.get("Date")

        # Convert Google serial or string to formatted MM/DD/YYYY
        try:
            dt = _to_datetime(d)
            row["Date"] = dt.strftime("%m/%d/%Y")
        except:
            # leave as original if totally unparseable
            row["Date"] = str(d)

        details.append(row)
    matches = sorted(set([r["Name"].strip() for r in details if r.get("Name")]))
    match_count = len(details)

    return {
        "exists": match_count > 0,
        "match_count": match_count,
        "matches": matches,
        "details": details,
        "filters_used": {
            "name": names_to_check,
            "category": category,
            "date": date,
            "start_date": start_date,
            "end_date": end_date,
            "days_ago": days_ago,
        },
    }
