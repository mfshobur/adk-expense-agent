from google.adk.sessions import DatabaseSessionService
from google.adk.memory import InMemoryMemoryService
from google.adk.runners import Runner
from google.adk.apps.app import App, EventsCompactionConfig
from agents.root_agent import root_agent
from google.genai import types
import os
from dotenv import load_dotenv
import logging
import httpx
load_dotenv()

logger = logging.getLogger(__name__)

# Telegram credentials
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
telegram_chat_id = os.getenv('TELEGRAM_USER_ID')

# Shared httpx client for Telegram API
_telegram_client = None

def get_telegram_client():
    """Get or create shared httpx client for Telegram API."""
    global _telegram_client
    if _telegram_client is None:
        _telegram_client = httpx.AsyncClient(timeout=30.0)
    return _telegram_client

async def send_telegram_message(text: str, chat_id: str = None):
    """Send message to Telegram using direct HTTP API call.

    This avoids event loop issues by using httpx instead of python-telegram-bot.
    """
    if not TELEGRAM_BOT_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN not set, cannot send message")
        return False

    target_chat_id = chat_id or telegram_chat_id
    if not target_chat_id:
        logger.warning("No chat_id specified and TELEGRAM_USER_ID not set")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": target_chat_id,
        "text": text
        # No parse_mode - send as plain text to avoid parsing errors
    }

    try:
        client = get_telegram_client()
        response = await client.post(url, json=payload)
        response.raise_for_status()
        logger.debug(f"Sent message to Telegram chat {target_chat_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to send Telegram message: {e}")

        # Log error details if available
        if hasattr(e, 'response'):
            try:
                error_detail = e.response.json()
                logger.error(f"Telegram API error: {error_detail}")
            except:
                logger.error(f"Response text: {e.response.text}")

        return False

# Database configuration
db_url = os.getenv('DATABASE_URL')

if not db_url:
    raise ValueError("DATABASE_URL environment variable is required")

# Normalize postgres:// to postgresql:// for SQLAlchemy
if db_url.startswith('postgres://'):
    db_url = db_url.replace('postgres://', 'postgresql://', 1)

logger.info("Connected to PostgreSQL database")

session_service = DatabaseSessionService(db_url=db_url)
memory_service = InMemoryMemoryService()

app = App(
    name='expense_app',
    root_agent=root_agent
    # BUG: EventsCompactionConfig causes 'dict' object has no attribute 'start_timestamp'
    # events_compaction_config=EventsCompactionConfig(
    #     compaction_interval=30,
    #     overlap_size=3
    # )
)

runner = Runner(
    app=app,
    session_service=session_service,
    memory_service=memory_service
)

async def get_or_create_session(user_id: str):
    """Get existing session or create new one for user.

    Looks up sessions from database to share across processes.
    Returns the session object/dict, not just the ID.
    """
    session = await session_service.get_session(
        app_name='expense_app',
        user_id=user_id,
        session_id=user_id
    )
    if session is None:
        session = await session_service.create_session(
            app_name='expense_app',
            user_id=user_id,
            session_id=user_id
        )
    return session

async def run_agent(user_id: str, new_message: str, telegram_update=None):
    """Run agent and handle responses.

    Args:
        user_id: User ID
        new_message: Message to send to agent
        telegram_update: Optional Telegram Update object for real-time replies

    Returns:
        List of response strings
    """
    session = await get_or_create_session(user_id)

    content = types.Content(
        role='user', parts=[types.Part.from_text(text=new_message)]
    )

    responses = []

    async for event in runner.run_async(
        user_id=user_id,
        session_id=session.id,
        new_message=content,
    ):
        for part in event.content.parts:
            # Handle tool calls
            if part.function_call:
                tool_name = part.function_call.name
                tool_args = dict(part.function_call.args) if part.function_call.args else {}
                tool_msg = f"🔧 Using tool: {tool_name}\nParameters: {tool_args}"
                responses.append(tool_msg)

                if telegram_update:
                    await telegram_update.message.reply_text(tool_msg)
                else:
                    await send_telegram_message(tool_msg)

            # Handle text responses
            elif part.text:
                responses.append(part.text)

                if telegram_update:
                    await telegram_update.message.reply_text(part.text)
                else:
                    await send_telegram_message(part.text)

    return responses