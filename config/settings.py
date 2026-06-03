"""
config/settings.py
Master settings — loaded from .env at startup.
Frozen dataclass: immutable after construction.
Any module needing config calls get_settings() — never os.getenv() directly.
"""

from __future__ import annotations
import os
from dataclasses import dataclass
from functools import lru_cache
from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    # ── Telegram ──────────────────────────────────────────────
    telegram_token: str
    telegram_chat_id: str

    # ── MT5 / Broker ──────────────────────────────────────────
    mt5_login: int
    mt5_password: str
    mt5_server: str
    pipe_path: str  # Named Pipe path, e.g. r"\\.\pipe\ghostgrid"

    # ── Runtime ───────────────────────────────────────────────
    paper_trading: bool  # True = paper DB, signals to Telegram only
    log_level: str  # "DEBUG" | "INFO" | "WARNING" | "ERROR"
    vps_timezone: str  # Always "UTC"
    historical_data_dir: str  # Path to historical tick CSVs

    # ── Derived ───────────────────────────────────────────────
    @property
    def db_path(self) -> str:
        """WHY: separate DB path for paper vs live prevents live DB contamination."""
        suffix = "_paper" if self.paper_trading else ""
        return f"./data_store/ghost_grid{suffix}.db"

    @classmethod
    def from_env(cls) -> "Settings":
        """Load and validate all required environment variables."""
        load_dotenv()

        missing = []
        required = [
            "TELEGRAM_TOKEN",
            "TELEGRAM_CHAT_ID",
            "MT5_LOGIN",
            "MT5_PASSWORD",
            "MT5_SERVER",
        ]
        for key in required:
            if not os.getenv(key):
                missing.append(key)
        if missing:
            raise EnvironmentError(
                f"Missing required environment variables: {', '.join(missing)}\n"
                f"Copy .env.example to .env and fill in all values."
            )

        return cls(
            telegram_token=os.environ["TELEGRAM_TOKEN"],
            telegram_chat_id=os.environ["TELEGRAM_CHAT_ID"],
            mt5_login=int(os.environ["MT5_LOGIN"]),
            mt5_password=os.environ["MT5_PASSWORD"],
            mt5_server=os.environ["MT5_SERVER"],
            pipe_path=os.getenv("PIPE_PATH", r"\\.\pipe\ghostgrid"),
            paper_trading=os.getenv("PAPER_TRADING", "true").lower() == "true",
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
            vps_timezone=os.getenv("VPS_TIMEZONE", "UTC"),
            historical_data_dir=os.getenv(
                "HISTORICAL_DATA_DIR", "./data_store/historical"
            ),
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    WHY: lru_cache ensures Settings is constructed exactly once.
    Subsequent calls return the same frozen instance — no re-parsing .env.
    """
    return Settings.from_env()
