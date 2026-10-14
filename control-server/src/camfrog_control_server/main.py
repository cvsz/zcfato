"""Uvicorn entry point. Environment configuration is required at import time."""

from .app import create_app
from .config import Settings

app = create_app(Settings.from_env())
