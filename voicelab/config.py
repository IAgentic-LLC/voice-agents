"""Settings read from the environment, with defaults for the local server.

The Gemini key comes from GEMINI_API_KEY, either in the environment or in a
.env file at the repository root. It is never printed or written to a run.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

# A local LiveKit server started with --dev accepts this key and secret.
os.environ.setdefault("LIVEKIT_URL", "ws://127.0.0.1:7880")
os.environ.setdefault("LIVEKIT_API_KEY", "devkey")
os.environ.setdefault("LIVEKIT_API_SECRET", "secret")

LIVEKIT_URL = os.environ["LIVEKIT_URL"]
LIVEKIT_API_KEY = os.environ["LIVEKIT_API_KEY"]
LIVEKIT_API_SECRET = os.environ["LIVEKIT_API_SECRET"]


def gemini_key() -> str:
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        raise SystemExit(
            "GEMINI_API_KEY is not set. Put it in .env at the repository "
            "root (see .env.example)."
        )
    return key
