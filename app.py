from fastapi import FastAPI, Request, Header, BackgroundTasks
import logging
import os

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from gmail_listener import pubsub_push
from telegram_bot.telegram_webhook import webhook as telegram_webhook_handler, on_startup, on_shutdown

app = FastAPI(title="QRIS Payment Automation")

# Mount Gmail routes
@app.post("/pubsub/push")
async def gmail_pubsub(
    envelope: dict,
    background_tasks: BackgroundTasks,
    x_pubsub_auth_token: str = Header(None, alias="X-PubSub-Auth-Token")
):
    """Gmail Pub/Sub endpoint."""
    from gmail_listener import PubSubEnvelope
    envelope_obj = PubSubEnvelope(**envelope)
    return await pubsub_push(envelope_obj, background_tasks, x_pubsub_auth_token)

# Mount Telegram routes
@app.post("/telegram/webhook")
async def telegram_hook(
    request: Request,
    x_telegram_bot_api_secret_token: str = Header(None)
):
    """Telegram webhook endpoint."""
    return await telegram_webhook_handler(request, x_telegram_bot_api_secret_token)

# Health check
@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "services": {
            "gmail": "running",
            "telegram": "running"
        }
    }

# Root endpoint
@app.get("/")
async def root():
    return {
        "service": "QRIS Payment Automation",
        "version": "1.0",
        "endpoints": {
            "/pubsub/push": "POST - Gmail Pub/Sub notifications",
            "/telegram/webhook": "POST - Telegram bot webhook",
            "/health": "GET - Health check"
        }
    }

@app.on_event("startup")
async def startup():
    await on_startup()
    logger.info("Service started")

@app.on_event("shutdown")
async def shutdown():
    await on_shutdown()

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv('PORT', 8080))
    logger.info(f"Starting combined service on port {port}...")
    uvicorn.run(app, host='0.0.0.0', port=port, log_level='info')
