from fastapi import FastAPI, HTTPException, Header, Response, BackgroundTasks
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from pydantic import BaseModel
from typing import Optional
import base64
import os
import logging
from dotenv import load_dotenv
import httplib2
from google_auth_httplib2 import AuthorizedHttp
import json

from agent_manager import run_agent

load_dotenv()

logger = logging.getLogger(__name__)
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
GMAIL_TOKEN_JSON = os.getenv('GMAIL_TOKEN_JSON')

if GMAIL_TOKEN_JSON:
    try:
        decoded = base64.b64decode(GMAIL_TOKEN_JSON)
        token_dict = json.loads(decoded)
    except:
        token_dict = json.loads(GMAIL_TOKEN_JSON)
    creds = Credentials.from_authorized_user_info(token_dict, SCOPES)
else:
    creds = Credentials.from_authorized_user_file('token.json', SCOPES)

http = httplib2.Http(timeout=10)
authorized_http = AuthorizedHttp(creds, http=http)
gmail_service = build('gmail', 'v1', http=authorized_http)

# Get PaymentNotifications label ID
labels_response = gmail_service.users().labels().list(userId='me').execute()
PAYMENT_LABEL_ID = None
for label in labels_response.get('labels', []):
    if label['name'] == 'PaymentNotifications':
        PAYMENT_LABEL_ID = label['id']
        logger.info(f"PaymentNotifications label ID: {PAYMENT_LABEL_ID}")
        break

if not PAYMENT_LABEL_ID:
    logger.warning("PaymentNotifications label not found, will use INBOX")

# Track processed messages and last historyId
processed_messages = set()
last_history_id = None

# Pydantic models
class PubSubMessage(BaseModel):
    data: Optional[str] = None
    messageId: Optional[str] = None
    message_id: Optional[str] = None
    publishTime: Optional[str] = None

class PubSubEnvelope(BaseModel):
    message: PubSubMessage
    subscription: Optional[str] = None

app = FastAPI(title="Gmail Payment Notification Listener")

def get_email_details(message_id: str):
    """Fetch email subject, sender, and body."""
    try:
        msg = gmail_service.users().messages().get(
            userId='me', id=message_id, format='full'
        ).execute()

        headers = msg['payload']['headers']
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
        sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown')

        # Extract body
        body = ''
        if 'parts' in msg['payload']:
            for part in msg['payload']['parts']:
                if part['mimeType'] in ['text/plain', 'text/html'] and 'data' in part['body']:
                    body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                    break
                elif 'parts' in part:
                    for subpart in part['parts']:
                        if subpart['mimeType'] in ['text/plain', 'text/html'] and 'data' in subpart['body']:
                            body = base64.urlsafe_b64decode(subpart['body']['data']).decode('utf-8')
                            break
                    if body:
                        break
        elif 'body' in msg['payload'] and 'data' in msg['payload']['body']:
            body = base64.urlsafe_b64decode(msg['payload']['body']['data']).decode('utf-8')

        return subject, sender, body
    except Exception as e:
        logger.error(f"Error fetching email {message_id}: {e}")
        return None, None, None

async def process_payment_email(message_id: str, user_id: str):
    """Process payment email and send to agent."""
    subject, sender, body = get_email_details(message_id)

    if not subject:
        return

    # Simple instruction for agent
    agent_message = (
        f"[SYSTEM: Email notification received. Tell user you got this invoice email and add it to the sheet. "
        f"If anything is unclear, ask for clarification.]\n\n"
        f"From: {sender}\n"
        f"Subject: {subject}\n\n"
        f"{body}"
    )

    logger.info(f"Processing email from {sender}: {subject[:50]}...")

    try:
        response = await run_agent(user_id, agent_message)
        logger.info(f"Agent processed email, sent {len(response)} messages")
    except Exception as e:
        logger.error(f"Error processing email: {e}")

@app.post("/pubsub/push")
async def pubsub_push(
    envelope: PubSubEnvelope,
    background_tasks: BackgroundTasks,
    x_pubsub_auth_token: str = Header(None, alias="X-PubSub-Auth-Token"),
):
    """Handle Pub/Sub push notifications.

    CRITICAL: MUST acknowledge (return 204) IMMEDIATELY, then process in background.
    If don't acknowledge fast enough, Pub/Sub will retry the same message forever.
    """

    # Simple auth token check
    PUBSUB_AUTH_TOKEN = os.getenv('PUBSUB_AUTH_TOKEN')
    if PUBSUB_AUTH_TOKEN and x_pubsub_auth_token != PUBSUB_AUTH_TOKEN:
        logger.warning("Invalid auth token")
        raise HTTPException(status_code=403, detail="Invalid token")

    # Decode Pub/Sub data to get historyId
    try:
        if envelope.message.data:
            decoded_data = base64.b64decode(envelope.message.data).decode('utf-8')
            notification_data = json.loads(decoded_data)
            history_id = notification_data.get('historyId')
            email_address = notification_data.get('emailAddress')

            logger.info(f"Pub/Sub notification for {email_address}, historyId: {history_id}")

            # Add background task to process this specific notification
            background_tasks.add_task(process_notification, history_id)
    except Exception as e:
        logger.error(f"Could not decode Pub/Sub data: {e}")

    # Return 204 IMMEDIATELY to acknowledge Pub/Sub
    return Response(status_code=204)


async def process_notification(history_id: str):
    """Background task to process a specific Pub/Sub notification.

    Uses Gmail History API to detect only NEW messages, not deletions or other events.
    """
    global last_history_id

    # On first run, just initialize
    if last_history_id is None:
        last_history_id = history_id
        logger.info(f"Initialized last_history_id to {history_id}")

        # On first notification after server restart, no baseline provided
        # So can't use History API. Just get the latest message.
        try:
            response = gmail_service.users().messages().list(
                userId='me',
                labelIds=[PAYMENT_LABEL_ID] if PAYMENT_LABEL_ID else ['INBOX'],
                maxResults=1
            ).execute()

            messages = response.get('messages', [])
            if messages:
                message_id = messages[0]['id']

                if message_id not in processed_messages:
                    logger.info(f"New email: {message_id}")
                    processed_messages.add(message_id)

                    user_id = os.getenv('TELEGRAM_USER_ID')
                    await process_payment_email(message_id, user_id)
        except Exception as e:
            logger.error(f"Error: {e}")

        return

    # Skip if older historyId
    try:
        if int(history_id) <= int(last_history_id):
            return
    except:
        pass

    try:
        # Use History API to check what changed since last_history_id
        # Only process messageAdded events (not messagesDeleted, labelsAdded, etc)
        history_response = gmail_service.users().history().list(
            userId='me',
            startHistoryId=last_history_id,
            labelId=PAYMENT_LABEL_ID,
            historyTypes=['messageAdded']  # Only new messages, ignore deletions
        ).execute()

        # Update last_history_id
        last_history_id = history_id

        history_records = history_response.get('history', [])

        if not history_records:
            logger.info("No new messages")
            return

        # Process each new message
        user_id = os.getenv('TELEGRAM_USER_ID')

        for record in history_records:
            messages_added = record.get('messagesAdded', [])

            for msg_record in messages_added:
                message_id = msg_record['message']['id']

                # Check if message has the PaymentNotifications label
                labels = msg_record['message'].get('labelIds', [])
                if PAYMENT_LABEL_ID and PAYMENT_LABEL_ID not in labels:
                    continue

                # Skip if already processed
                if message_id in processed_messages:
                    continue

                logger.info(f"New email: {message_id}")

                # Mark as processed
                processed_messages.add(message_id)

                # Limit cache size
                if len(processed_messages) > 500:
                    old_messages = list(processed_messages)[:250]
                    for old_msg in old_messages:
                        processed_messages.remove(old_msg)

                # Process the email
                await process_payment_email(message_id, user_id)

    except Exception as e:
        logger.error(f"Error: {e}")
        last_history_id = history_id

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.get("/")
async def root():
    return {
        "service": "Gmail Payment Notification Listener",
        "status": "running",
        "processed_count": len(processed_messages)
    }