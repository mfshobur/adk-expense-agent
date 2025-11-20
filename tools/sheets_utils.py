import gspread
from google.oauth2.service_account import Credentials
import os
import json
import base64

from config import SHEET_ID, SHEET_NAME

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