from dotenv import load_dotenv
import os

# Load environment variables once at module import time
load_dotenv()

# Google Sheets configuration
SHEET_ID = os.getenv("SHEET_ID")
SHEET_NAME = os.getenv("SHEET_NAME")

# API keys (if needed by tools)
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")

# Google Genai configuration
GOOGLE_GENAI_USE_VERTEXAI = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "FALSE")
USER_ID = os.getenv("TELEGRAM_USER_ID")

# Telegram bot authorization
# Comma-separated list of allowed Telegram user IDs
ALLOWED_TELEGRAM_USER_IDS = set(
    filter(None, os.getenv('ALLOWED_TELEGRAM_USER_IDS', os.getenv('TELEGRAM_USER_ID', '')).split(','))
)