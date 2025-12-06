"""Configuration module for persistasaurus."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()


def get_sqlite_path() -> str:
    """Get SQLite database path from environment or use default."""
    return os.getenv("SQLITE_PATH", "persistasaurus.db")


def get_database_url() -> str:
    """Get database URL from environment or construct from SQLITE_PATH."""
    if db_url := os.getenv("DATABASE_URL"):
        return db_url
    sqlite_path = get_sqlite_path()
    return f"sqlite:///{sqlite_path}"


# Default configuration
SQLITE_PATH = get_sqlite_path()
DATABASE_URL = get_database_url()
