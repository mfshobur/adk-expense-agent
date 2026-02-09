import gspread
from google.oauth2.service_account import Credentials
import os
import json
import base64
from datetime import datetime, timedelta

from config import SHEET_ID, SHEET_NAME

# ── Shared constants ──────────────────────────────────────────────
VALID_CATEGORIES = {
    'Food', 'Health & Wellness', 'Snack', 'Bills & Utilities',
    'Entertainment', 'Transport', 'Education', 'Charity', 'Shopping'
}

# ── Date-parsing helpers ──────────────────────────────────────────
def gs_serial_to_datetime(serial: float) -> datetime:
    """Convert Google Sheets serial (days since 1899-12-30) to datetime."""
    base = datetime(1899, 12, 30)
    return base + timedelta(days=float(serial))


def parse_date_mmddyyyy(date_str: str) -> datetime:
    """Parse MM/DD/YYYY (e.g. '11/04/2025')."""
    return datetime.strptime(date_str, "%m/%d/%Y")


def to_datetime(val) -> datetime:
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
        return gs_serial_to_datetime(float(val))
    s = str(val).strip()
    if not s:
        raise ValueError("Empty date")
    try:
        return parse_date_mmddyyyy(s)
    except Exception:
        try:
            return datetime.fromisoformat(s)
        except Exception:
            raise

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

# Load credentials from environment variable or file
SERVICE_ACCOUNT_JSON = os.getenv('SERVICE_ACCOUNT_JSON')

if SERVICE_ACCOUNT_JSON:
    # Production: Load from environment variable (base64 encoded or raw JSON)
    try:
        # Try base64 decode first
        decoded = base64.b64decode(SERVICE_ACCOUNT_JSON)
        creds_dict = json.loads(decoded)
    except:
        # If not base64, treat as raw JSON string
        creds_dict = json.loads(SERVICE_ACCOUNT_JSON)

    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
else:
    # Local development: Load from file
    creds = Credentials.from_service_account_file(
        './expenses-agent.json',
        scopes=SCOPES
    )

gc = gspread.authorize(creds)
sheet = gc.open_by_key(SHEET_ID).worksheet(SHEET_NAME)