from fastapi import FastAPI, Request, HTTPException, Header
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, ContextTypes, filters
import logging
import os
from dotenv import load_dotenv
from functools import wraps
import secrets

from agent_manager import run_agent
from config import ALLOWED_TELEGRAM_USER_IDS

load_dotenv()

logger = logging.getLogger(__name__)

# FastAPI app for webhook
app = FastAPI(title="Telegram Bot Webhook")

def authorized_users_only(func):
    """Decorator to restrict access to authorized users only."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = str(update.effective_user.id)

        if user_id not in ALLOWED_TELEGRAM_USER_IDS:
            username = update.effective_user.username or "Unknown"
            first_name = update.effective_user.first_name or "Unknown"
            logger.warning(
                f"Unauthorized access attempt blocked - "
                f"user_id: {user_id}, username: @{username}, name: {first_name}"
            )
            await update.message.reply_text(
                "Maaf, kamu ga punya akses ke bot ini. "
                "Ini bot pribadi buat tracking expense."
            )
            return

        return await func(update, context, *args, **kwargs)

    return wrapper

# Telegram bot token and webhook configuration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
WEBHOOK_URL = os.getenv('TELEGRAM_WEBHOOK_URL', '')
TELEGRAM_WEBHOOK_SECRET = os.getenv('TELEGRAM_WEBHOOK_SECRET')

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN not found in environment variables!")

if not TELEGRAM_WEBHOOK_SECRET:
    logger.warning(
        "TELEGRAM_WEBHOOK_SECRET not set! Webhook will accept requests without verification. "
        "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
    )

# Create the Application
telegram_app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

# Handle /start command
@authorized_users_only
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    await update.message.reply_text(
        f"Halo {user.first_name}! Saya Quina, asisten expense tracker kamu.\n\n"
        "Kamu bisa:\n"
        "- Tambah transaksi: 'tambah pengeluaran makan 50 ribu'\n"
        "- Update transaksi: 'ubah harga sabun kemarin jadi 20 ribu'\n"
        "- Hapus transaksi: 'hapus transaksi bubur ayam tadi pagi'\n"
        "- Cek pengeluaran: 'total pengeluaran bulan ini'\n\n"
        "Langsung chat aja!"
    )

# Handle /help command
@authorized_users_only
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    await update.message.reply_text(
        "Saya bisa bantu kamu:\n"
        "- Catat pengeluaran harian\n"
        "- Update atau hapus transaksi\n"
        "- Analisis pengeluaran\n\n"
        "Tinggal chat aja!"
    )

# Handle messages
@authorized_users_only
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle user messages and generate responses using Expense Agent."""
    user_message = update.message.text
    user_id = str(update.effective_user.id)  # Use Telegram user ID
    chat_id = str(update.effective_chat.id)  # Get chat ID for replies

    logger.info(f"Received message from user_id: {user_id}, chat_id: {chat_id}")

    try:
        # Run agent with chat_id for direct HTTP replies
        await run_agent(user_id, user_message)
    except Exception as e:
        await update.message.reply_text("Waduh, ada error nih. Coba lagi ya!")
        logger.error(f"Error: {e}")

# Error handler
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log Errors caused by Updates."""
    logger.warning(f'Update "{update}" caused error "{context.error}"')

# Register handlers
telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(CommandHandler("help", help_command))
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
telegram_app.add_error_handler(error_handler)

@app.on_event("startup")
async def on_startup():
    """Set webhook on startup with secret token for security."""
    await telegram_app.initialize()
    await telegram_app.bot.initialize()

    if WEBHOOK_URL:
        webhook_info = await telegram_app.bot.get_webhook_info()
        if webhook_info.url != WEBHOOK_URL:
            logger.info(f"Setting webhook to {WEBHOOK_URL}")

            # Set webhook WITH secret token for security
            if TELEGRAM_WEBHOOK_SECRET:
                await telegram_app.bot.set_webhook(
                    url=WEBHOOK_URL,
                    secret_token=TELEGRAM_WEBHOOK_SECRET
                )
                logger.info("Webhook configured with secret token verification enabled")
            else:
                await telegram_app.bot.set_webhook(url=WEBHOOK_URL)
                logger.warning("Webhook configured WITHOUT secret token - not secure!")
        else:
            logger.info(f"Webhook already set to {WEBHOOK_URL}")
    else:
        logger.warning("TELEGRAM_WEBHOOK_URL not set, webhook not configured!")

@app.on_event("shutdown")
async def on_shutdown():
    """Cleanup on shutdown."""
    await telegram_app.shutdown()

@app.post("/webhook")
async def webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str = Header(None)
):
    """Handle incoming webhook updates from Telegram with signature verification."""
    
    # Verify the secret token to ensure request is from Telegram
    if TELEGRAM_WEBHOOK_SECRET:
        if not x_telegram_bot_api_secret_token:
            logger.warning("Webhook request missing X-Telegram-Bot-Api-Secret-Token header")
            raise HTTPException(
                status_code=401,
                detail="Missing authentication header"
            )

        # Use constant-time comparison to prevent timing attacks
        if not secrets.compare_digest(
            x_telegram_bot_api_secret_token,
            TELEGRAM_WEBHOOK_SECRET
        ):
            logger.warning(
                f"Invalid webhook secret token received. "
                f"Possible unauthorized access attempt from IP: {request.client.host}"
            )
            raise HTTPException(
                status_code=403,
                detail="Invalid authentication token"
            )

        logger.debug("Webhook signature verified successfully")
    else:
        logger.warning(
            "Webhook secret not configured - accepting request without verification! "
            "This is NOT SECURE for production."
        )

    try:
        # Get the update data
        data = await request.json()
        logger.debug(f"Received webhook data: {data}")

        # Create Update object
        update = Update.de_json(data, telegram_app.bot)

        # Process the update
        await telegram_app.process_update(update)

        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}

@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "service": "Telegram Bot Webhook",
        "status": "running",
        "endpoints": {
            "/webhook": "POST - Receive Telegram webhook updates",
            "/health": "GET - Health check"
        }
    }