"""Wspólne ustawienia testów: bez sieci, bez rozgrzewki przykładów demo przy starcie aplikacji."""

import os

os.environ["DEMO_WARMUP"] = "false"

from app.core.config import settings  # noqa: E402

settings.demo_warmup = False
