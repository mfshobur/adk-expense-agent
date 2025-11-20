from datetime import datetime, timedelta
import pandas as pd

from tools.sheets_utils import sheet
from tools.check_data_exists import _to_datetime, _parse_date_mmddyyyy

def _clean_json(obj):
    """Recursively convert datetime/date to string for safe JSON serialization."""
    if isinstance(obj, datetime):
        return obj.strftime("%m/%d/%Y")
    if hasattr(obj, "isoformat"):  # catches date
        try:
            return obj.strftime("%m/%d/%Y")
        except:
            return obj.isoformat()
    if isinstance(obj, list):
        return [_clean_json(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _clean_json(v) for k, v in obj.items()}
    return obj


def analyze_expenses_tool(
    metric: str,
    category: str = "",
    name: str = "",
    start_date: str = "",
    end_date: str = "",
    days: str = ""
):
    """
    Analyze expense data from a Google Sheet with flexible filtering and aggregation options.

    This function retrieves expense records from a Google Sheet, applies various filters,
    and calculates metrics based on the filtered data. It's designed to help AI agents
    understand and analyze spending patterns.

    Args:
        metric (str): The type of calculation to perform. Must be one of:
            - "sum": Calculate the total amount of expenses
            - "count": Count the number of expense records
            - "average": Calculate the average expense amount
        category (str, optional): Filter expenses by exact category match (case-insensitive).
            Examples: "Food", "Transport", "Entertainment". Defaults to "" (no filter).
        name (str, optional): Filter expenses by partial name match (case-insensitive).
            Searches for expenses where the Name field contains this string.
            Defaults to "" (no filter).
        start_date (str, optional): Filter start date in MM/DD/YYYY format.
            Must be used together with end_date to create a date range filter.
            Defaults to "" (no filter).
        end_date (str, optional): Filter end date in MM/DD/YYYY format.
            Must be used together with start_date to create a date range filter.
            Defaults to "" (no filter).
        days (str, optional): Filter expenses from the last N days.
            Provide as a string number (e.g., "7", "30", "90").
            This filter takes precedence over start_date/end_date if both are provided.
            Defaults to "" (no filter).

    Returns:
        dict: A dictionary containing the analysis results with the following structure:
            - If metric is unsupported:
                {"error": str} - Error message explaining the unsupported metric
            
            - If no records match the filters:
                {"exists": False, "value": 0, "details": []}
            
            - If records are found:
                {
                    "metric": str,        # The metric that was calculated
                    "value": float/int,   # The calculated result (sum/count/average)
                    "row_count": int,     # Number of records matching the filters
                    "details": list       # List of matching expense records with Date formatted as MM/DD/YYYY

    Examples:
        # Get total spending in the last 30 days
        analyze_expenses_tool(metric="sum", days="30")
        
        # Count food expenses in January 2024
        analyze_expenses_tool(metric="count", category="Food", 
                             start_date="01/01/2024", end_date="01/31/2024")
        
        # Get average spending on items containing "coffee"
        analyze_expenses_tool(metric="average", name="coffee")
        
        # Get sum of transport expenses in last 7 days
        analyze_expenses_tool(metric="sum", category="Transport", days="7")

    Note:
        - All string filters are case-insensitive
        - Date filters require valid MM/DD/YYYY format
        - The 'days' filter overrides start_date/end_date if both are provided
        - Records with invalid dates are automatically excluded from analysis
        - The function requires 'sheet', 'pd', '_to_datetime', '_parse_date_mmddyyyy', 
          and '_clean_json' to be available in the scope
    """

    metric = metric.lower().strip()
    if metric not in {"sum", "count", "average"}:
        return {"error": f"Unsupported metric '{metric}'"}

    # Load data
    records = sheet.get_all_records(value_render_option="UNFORMATTED_VALUE")
    df = pd.DataFrame(records)

    # Parse dates
    def safe_date(x):
        try:
            return _to_datetime(x)
        except:
            return pd.NaT

    df["__parsed_date"] = df["Date"].apply(safe_date)
    df = df.dropna(subset=["__parsed_date"])
    df["__date_only"] = df["__parsed_date"].dt.date

    today = datetime.today().date()

    # Filter: last N days
    if days.strip():
        try:
            d = int(days)
            start = today - timedelta(days=d)
            df = df[df["__date_only"] >= start]
        except:
            pass

    # Filter: date range
    if start_date and end_date:
        try:
            s = _parse_date_mmddyyyy(start_date).date()
            e = _parse_date_mmddyyyy(end_date).date()
            df = df[(df["__date_only"] >= s) & (df["__date_only"] <= e)]
        except:
            pass

    # Category filter
    if category.strip():
        df = df[df["Category"].astype(str).str.strip().str.lower() ==
                category.lower().strip()]

    # Name filter
    if name.strip():
        df = df[df["Name"].astype(str).str.lower().str.contains(
            name.lower().strip())]

    if df.empty:
        return {"exists": False, "value": 0, "details": []}

    # Perform calculation
    amount_series = df["Amount"].astype(float)

    if metric == "sum":
        value = float(amount_series.sum())
    elif metric == "count":
        value = int(amount_series.count())
    elif metric == "average":
        value = float(amount_series.mean())

    # Format dates for output
    details = []
    for row in df.to_dict(orient="records"):
        try:
            dt = _to_datetime(row["Date"])
            row["Date"] = dt.strftime("%m/%d/%Y")
        except:
            pass
        details.append(row)

    result = {
        "exists": True,
        "metric": metric,
        "value": value,
        "row_count": len(details),
        "details": details,
    }

    return _clean_json(result)
