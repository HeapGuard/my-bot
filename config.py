import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
BRAND_HANDLE = os.getenv("BRAND_HANDLE", "@intstg_stories")
BRAND_NAME = os.getenv("BRAND_NAME", "StoriesHub")

OUTPUT_DIR = BASE_DIR / os.getenv("OUTPUT_DIR", "output")
OUTPUT_DIR.mkdir(exist_ok=True, parents=True)

TEMPLATES_DIR = BASE_DIR / "core" / "templates"
HTTP_PROXY = os.getenv("HTTP_PROXY", "")
TELEGRAM_API_URL = os.getenv("TELEGRAM_API_URL", "https://api.tlgrm.app")
