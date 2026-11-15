import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def _list(name: str, default: str) -> list[str]:
    return [v.strip() for v in os.getenv(name, default).split(",") if v.strip()]


ALLOWED_MODELS = _list("ALLOWED_MODELS", "claude-opus-5-5,claude-sonnet-5-5,claude-haiku-5-5")
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", ALLOWED_MODELS[0])
if DEFAULT_MODEL not in ALLOWED_MODELS:
    raise RuntimeError(f"DEFAULT_MODEL {DEFAULT_MODEL!r} is not in ALLOWED_MODELS")

# USD per million tokens (input, output); used only for the daily spend cap.
PRICES = {
    "claude-opus-5-5": (4.00, 20.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),
}
EFFORTS = ["low", "medium", "high"]
DEFAULT_EFFORT = {"claude-opus-5-5": "medium", "claude-sonnet-5-5": "high", "claude-haiku-5-5": "medium"}

EMBED_MODEL = os.getenv("EMBED_MODEL", "BAAI/bge-small-en-v1.5")
TOP_K = int(os.getenv("TOP_K", "6"))
MAX_DISTANCE = float(os.getenv("MAX_DISTANCE", "0.85"))  # L2 on normalized vectors; on-topic ~0.6-0.7, off-topic >0.9
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "8000"))
DAILY_SPEND_CAP_USD = float(os.getenv("DAILY_SPEND_CAP_USD", "5"))
ENABLE_FALLBACKS = os.getenv("ENABLE_FALLBACKS", "1") == "1"

DB_PATH = Path(os.getenv("DB_PATH", ROOT / "data" / "burn.db"))
MAX_MESSAGE_CHARS = 2000
MAX_HISTORY_TURNS = 10
