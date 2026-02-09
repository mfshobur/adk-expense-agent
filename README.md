![alt text](image.png)

# Expense Agent

An automated expense tracking system that monitors QRIS payment notifications from Gmail and logs them via Telegram bot. Built with Google's Agent Development Kit (ADK) and FastAPI.

## Features

- **Multi-Agent Architecture**: Root coordinator delegates to specialized sub-agents (expense tracking, internet search)
- **Gmail Integration**: Monitors payment notification emails via Pub/Sub push notifications
- **Telegram Bot**: Interactive expense tracking through natural language commands
- **Internet Search**: Real-time web search via DuckDuckGo for general questions
- **Smart Processing**: Uses Gmail History API to filter only new messages, preventing duplicates
- **Persistent Sessions**: PostgreSQL-backed session storage shared between services
- **Multi-LLM Support**: Switch between Gemini, OpenAI, and Anthropic models via env vars
- **Single Container**: Combined Gmail and Telegram webhooks in one FastAPI app

## Architecture

```
                         ┌─────────────────┐
                         │   root_agent    │
                         │  (coordinator)  │
                         └────┬───────┬────┘
                              │       │
                    ┌─────────┘       └─────────┐
                    ▼                           ▼
          ┌─────────────────┐         ┌─────────────────┐
          │  expense_agent  │         │  search_agent   │
          │  (Google Sheets)│         │  (DuckDuckGo)   │
          └─────────────────┘         └─────────────────┘
```

The root agent uses ADK's `sub_agents` parameter for automatic LLM-driven routing — each sub-agent's `description` tells the LLM when to delegate.

```
agents/
├── __init__.py          # Re-exports root_agent
├── root_agent.py        # Coordinator — routes to sub-agents
├── expense_agent.py     # Expense sub-agent
├── search_agent.py      # Internet search sub-agent
└── model_config.py      # Shared model-switching logic

tools/
├── add_transaction.py   # Add single/batch transactions
├── update_transaction.py
├── delete_transaction.py
├── check_data_exists.py
├── analyze_expenses.py
├── check_today_date.py
├── web_search.py        # DuckDuckGo search
└── sheets_utils.py      # Shared Google Sheets helpers
```

The app runs two webhooks in a single container:
- `/pubsub/push` - Receives Gmail Pub/Sub notifications
- `/telegram/webhook` - Handles Telegram bot messages

Both services share the same agent session via PostgreSQL (Supabase).

## Local Development

### Prerequisites

- Python 3.11+
- Google Cloud Project with Gmail API and Pub/Sub enabled
- Telegram Bot Token
- Supabase PostgreSQL database (or local PostgreSQL)

### Installation

```bash
# Clone the repository
git clone <your-repo-url>
cd mcp-qris-automation

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env
```

### Environment Variables

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

| Variable | Required | Description |
|---|---|---|
| `LLM_PROVIDER` | No | `gemini` (default), `openai`, or `anthropic` |
| `LLM_MODEL` | No | Model name (default: `gemini-2.5-flash`) |
| `GOOGLE_API_KEY` | Yes* | Google API key (*required for Gemini provider) |
| `GOOGLE_GENAI_USE_VERTEXAI` | No | Set to `TRUE` to use Vertex AI (default: `FALSE`) |
| `OPENAI_API_KEY` | Yes* | OpenAI API key (*required for OpenAI provider) |
| `ANTHROPIC_API_KEY` | Yes* | Anthropic API key (*required for Anthropic provider) |
| `SHEET_ID` | Yes | Google Sheet ID for expense tracking |
| `SHEET_NAME` | Yes | Worksheet name (e.g. `Transactions`) |
| `SERVICE_ACCOUNT_JSON` | Yes* | Base64-encoded service account JSON (*production only) |
| `TELEGRAM_BOT_TOKEN` | Yes | Telegram bot token from BotFather |
| `TELEGRAM_USER_ID` | Yes | Your Telegram user ID |
| `TELEGRAM_WEBHOOK_URL` | Yes | Public HTTPS URL for Telegram webhook |
| `TELEGRAM_WEBHOOK_SECRET` | Yes | Secret token for webhook verification |
| `ALLOWED_TELEGRAM_USER_IDS` | No | Comma-separated allowed user IDs (defaults to `TELEGRAM_USER_ID`) |
| `AGENT_INSTRUCTION` | No | Agent personality and behavior rules |
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `GMAIL_TOKEN_JSON` | Yes* | Base64-encoded Gmail OAuth token (*for email monitoring) |
| `PUBSUB_AUTH_TOKEN` | No | Auth token for Pub/Sub push verification |
| `PORT` | No | Server port (default: `8080`) |

### Run Locally

```bash
python combined_app.py
```

The server starts on port 8080 by default.

## Setup Guides

### 1. Gmail Setup

#### Enable Gmail API

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a new project or select existing one
3. Enable Gmail API and Pub/Sub API
4. Create OAuth 2.0 credentials (Desktop app)
5. Download and save as `credentials.json`
6. Generate OAuth token by running this script locally:
   ```python
   from google.oauth2.credentials import Credentials
   from google_auth_oauthlib.flow import InstalledAppFlow

   SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
   flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
   creds = flow.run_local_server(port=0)

   # Save token
   with open('token.json', 'w') as token:
       token.write(creds.to_json())
   ```

**For production**: Set `GMAIL_TOKEN_JSON` environment variable with base64-encoded content:
```bash
cat token.json | base64
```

#### Configure Pub/Sub

1. Create a Pub/Sub topic:
```bash
gcloud pubsub topics create gmail-notifications
```

2. Create a push subscription:
```bash
gcloud pubsub subscriptions create gmail-push-sub \
  --topic gmail-notifications \
  --push-endpoint https://your-domain.com/pubsub/push \
  --push-auth-service-account your-service-account@project.iam.gserviceaccount.com
```

3. Set up Gmail watch:
```bash
# The app automatically sets this up on first run
# Or manually via Gmail API:
POST https://gmail.googleapis.com/gmail/v1/users/me/watch
{
  "topicName": "projects/your-project/topics/gmail-notifications",
  "labelIds": ["Label_123"]  # Your payment label ID
}
```

#### Get Label ID

Run this script to find your label ID:

```python
from tools.gmail_utils import get_gmail_service

service = get_gmail_service()
labels = service.users().labels().list(userId='me').execute()
for label in labels['labels']:
    print(f"{label['name']}: {label['id']}")
```

### 2. Telegram Bot Setup

1. Message [@BotFather](https://t.me/botfather) on Telegram
2. Create a new bot with `/newbot`
3. Copy the bot token to `TELEGRAM_BOT_TOKEN`
4. Set webhook (automatically done on app startup):
```bash
curl -X POST https://api.telegram.org/bot<TOKEN>/setWebhook \
  -H "Content-Type: application/json" \
  -d '{"url": "https://your-domain.com/telegram/webhook", "secret_token": "your_secret"}'
```

5. Get your Telegram user ID:
   - Message [@userinfobot](https://t.me/userinfobot)
   - Add your ID to `ALLOWED_TELEGRAM_USER_IDS`

### 3. Google Sheets Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a service account in your project
3. Download the service account JSON file and save as `expenses-agent.json`
4. Create a Google Sheet for expense tracking
5. Copy the Sheet ID from the URL:
   ```
   https://docs.google.com/spreadsheets/d/SHEET_ID_HERE/edit
   ```
6. Share the sheet with your service account email (found in `expenses-agent.json`)
7. Add `SHEET_ID` and `SHEET_NAME` to your `.env`

**For production**: Set `SERVICE_ACCOUNT_JSON` environment variable with base64-encoded content of `expenses-agent.json`

### 4. Database Setup (Supabase)

1. Create a [Supabase](https://supabase.com) project
2. Get your PostgreSQL connection string from Settings > Database
3. Add to `DATABASE_URL` in your `.env`

The required table will be created automatically by the agent.


## Usage

### Telegram Commands

```
/start - Initialize the bot
/help - Show available commands
```

### Natural Language Examples

```
i just bought fried rice for 50 IDR
change yesterday's soap price to 20,000 IDR
delete this morning's chicken porridge transaction
total expenses for this month
what's the latest news about AI?
search for best budgeting tips
```

### How It Works

1. Payment email arrives in Gmail with payment label
2. Gmail Pub/Sub sends notification to `/pubsub/push`
3. App processes email using Gmail History API
4. Expense Agent extracts payment details
5. Agent sends summary to your Telegram
6. You can chat with the bot to manage expenses or ask general questions

## Security

- Webhook endpoints use secret tokens for authentication
- Only authorized Telegram user IDs can access the bot
- Gmail Pub/Sub uses service account authentication
- Database credentials stored in environment variables
- Runs as non-root user in Docker container

## Troubleshooting

**Pub/Sub notifications not arriving:**
- Check Gmail watch is active (expires after 7 days)
- Verify push endpoint is publicly accessible
- Check `PUBSUB_AUTH_TOKEN` matches subscription auth token

**Telegram webhook not working:**
- Verify `TELEGRAM_WEBHOOK_SECRET` matches bot webhook configuration
- Check Railway logs for incoming requests
- Ensure webhook URL is HTTPS

**Database connection errors:**
- Verify `DATABASE_URL` format: `postgresql://user:pass@host:port/db`
- Check Supabase connection pooling settings
- Ensure database allows external connections

## License

MIT
