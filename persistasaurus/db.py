"""Database abstraction layer using aiosqlite."""

import asyncio
import aiosqlite
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


@dataclass
class DatabaseConfig:
    """Configuration for database connection."""
    sqlite_path: str


class Database:
    """Async database wrapper using aiosqlite."""

    def __init__(self, config: DatabaseConfig):
        self.config = config
        self._conn: Optional[aiosqlite.Connection] = None
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        """Establish database connection."""
        self._conn = await aiosqlite.connect(self.config.sqlite_path)
        self._conn.row_factory = aiosqlite.Row

    async def close(self) -> None:
        """Close database connection."""
        if self._conn:
            await self._conn.close()
            self._conn = None

    async def execute(self, sql: str, params: Iterable[Any] = ()) -> None:
        """Execute a SQL statement."""
        if not self._conn:
            raise RuntimeError("Database not connected")
        
        async with self._lock:
            await self._conn.execute(sql, params)
            await self._conn.commit()

    async def fetch_one(self, sql: str, params: Iterable[Any] = ()) -> Optional[Dict[str, Any]]:
        """Fetch a single row as a dictionary."""
        if not self._conn:
            raise RuntimeError("Database not connected")
        
        cursor = await self._conn.execute(sql, params)
        row = await cursor.fetchone()
        await cursor.close()
        
        if row:
            return dict(row)
        return None

    async def fetch_all(self, sql: str, params: Iterable[Any] = ()) -> List[Dict[str, Any]]:
        """Fetch all rows as a list of dictionaries."""
        if not self._conn:
            raise RuntimeError("Database not connected")
        
        cursor = await self._conn.execute(sql, params)
        rows = await cursor.fetchall()
        await cursor.close()
        
        return [dict(row) for row in rows]
