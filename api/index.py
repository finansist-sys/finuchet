"""Vercel entry point: exposes the FastAPI app (API + Telegram webhook) as one Python function.

All requests to /api/* and /tg/* are rewritten here by vercel.json; the Mini App itself is served
as static files from webapp/dist. Configuration comes from Vercel environment variables.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
os.environ.setdefault("BOT_MODE", "serverless")
os.environ.setdefault("ENV", "prod")

from app.main import create_app  # noqa: E402

app = create_app()
