from dotenv import load_dotenv
import os

# Load environment variables once at module import time
load_dotenv()

# Google Sheets configuration
SHEET_ID = os.getenv("SHEET_ID")
SHEET_NAME = os.getenv("SHEET_NAME")

# Google Genai configuration
GOOGLE_GENAI_USE_VERTEXAI = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "FALSE")

# Telegram bot authorization
# Comma-separated list of allowed Telegram user IDs
ALLOWED_TELEGRAM_USER_IDS = set(
    filter(None, os.getenv('ALLOWED_TELEGRAM_USER_IDS', os.getenv('TELEGRAM_USER_ID', '')).split(','))
)
