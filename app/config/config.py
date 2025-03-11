import os

APP_NAME="DhandhoAIBot"

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN is not Found.")

OPEN_ROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
OPEN_ROUTER_API_KEY = os.getenv("OPEN_ROUTER_API_KEY")
if not OPEN_ROUTER_API_KEY:
    raise ValueError("OPEN_ROUTER_API_KEY is not Found.")