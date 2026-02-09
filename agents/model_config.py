import os
from google.adk.models import Gemini
from google.adk.models.lite_llm import LiteLlm
from google.genai import types

retry_config = types.HttpRetryOptions(
    attempts=5,
    exp_base=7,
    initial_delay=1,
    http_status_codes=[429, 500, 503, 504]
)

LLM_PROVIDER = os.getenv('LLM_PROVIDER', 'gemini').lower()
LLM_MODEL = os.getenv('LLM_MODEL', 'gemini-2.5-flash')


def get_model():
    """Return configured LLM model based on LLM_PROVIDER / LLM_MODEL env vars."""
    if LLM_PROVIDER == 'openai':
        return LiteLlm(model=f"openai/{LLM_MODEL}")
    elif LLM_PROVIDER == 'anthropic':
        return LiteLlm(model=f"anthropic/{LLM_MODEL}")
    else:
        return Gemini(model=LLM_MODEL, retry_options=retry_config)
