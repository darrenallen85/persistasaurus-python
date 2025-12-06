"""Core execution engine for durable workflows."""

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from persistasaurus.db import Database
from persistasaurus.errors import NotFoundError
from persistasaurus.models import Execution


def _now_utc() -> str:
    """Get current UTC timestamp as ISO8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _parse_datetime(dt_str: str) -> datetime:
    """Parse ISO8601 datetime string."""
    return datetime.fromisoformat(dt_str)


async def create_execution(db: Database, payload: Dict[str, Any]) -> str:
    """Create a new execution.
    
    Args:
        db: Database instance
        payload: Initial execution data
        
    Returns:
        Execution ID (UUID)
    """
    execution_id = str(uuid.uuid4())
    now = _now_utc()
    
    await db.execute(
        """
        INSERT INTO executions (id, status, created_at, updated_at)
        VALUES (?, ?, ?, ?)
        """,
        (execution_id, "running", now, now)
    )
    
    # Create initial step with payload
    if payload:
        await append_step(db, execution_id, payload, status="completed")
    
    return execution_id


async def get_execution(db: Database, execution_id: str) -> Optional[Execution]:
    """Get execution by ID.
    
    Args:
        db: Database instance
        execution_id: Execution ID
        
    Returns:
        Execution object or None if not found
    """
    row = await db.fetch_one(
        "SELECT * FROM executions WHERE id = ?",
        (execution_id,)
    )
    
    if not row:
        return None
    
    return Execution(
        id=row["id"],
        status=row["status"],
        created_at=_parse_datetime(row["created_at"]),
        updated_at=_parse_datetime(row["updated_at"]),
        result=row["result"],
        error=row["error"],
    )


async def list_executions(db: Database, limit: int = 50) -> List[Execution]:
    """List recent executions.
    
    Args:
        db: Database instance
        limit: Maximum number of executions to return
        
    Returns:
        List of Execution objects
    """
    rows = await db.fetch_all(
        "SELECT * FROM executions ORDER BY created_at DESC LIMIT ?",
        (limit,)
    )
    
    return [
        Execution(
            id=row["id"],
            status=row["status"],
            created_at=_parse_datetime(row["created_at"]),
            updated_at=_parse_datetime(row["updated_at"]),
            result=row["result"],
            error=row["error"],
        )
        for row in rows
    ]


async def append_step(
    db: Database,
    execution_id: str,
    payload: Dict[str, Any],
    status: str = "pending"
) -> None:
    """Append a step to an execution.
    
    Args:
        db: Database instance
        execution_id: Execution ID
        payload: Step data
        status: Step status (default: "pending")
        
    Raises:
        NotFoundError: If execution doesn't exist
    """
    # Verify execution exists
    execution = await get_execution(db, execution_id)
    if not execution:
        raise NotFoundError(f"Execution {execution_id} not found")
    
    # Get next step index
    result = await db.fetch_one(
        "SELECT COALESCE(MAX(step_index), -1) + 1 as next_index FROM steps WHERE execution_id = ?",
        (execution_id,)
    )
    next_index = result["next_index"]
    
    now = _now_utc()
    payload_json = json.dumps(payload) if payload else None
    
    await db.execute(
        """
        INSERT INTO steps (execution_id, step_index, status, payload, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (execution_id, next_index, status, payload_json, now, now)
    )
    
    # Update execution timestamp
    await db.execute(
        "UPDATE executions SET updated_at = ? WHERE id = ?",
        (now, execution_id)
    )


async def mark_execution_completed(db: Database, execution_id: str, result: Any) -> None:
    """Mark an execution as completed.
    
    Args:
        db: Database instance
        execution_id: Execution ID
        result: Execution result (will be JSON-encoded)
        
    Raises:
        NotFoundError: If execution doesn't exist
    """
    # Verify execution exists
    execution = await get_execution(db, execution_id)
    if not execution:
        raise NotFoundError(f"Execution {execution_id} not found")
    
    now = _now_utc()
    result_json = json.dumps(result) if result is not None else None
    
    await db.execute(
        """
        UPDATE executions
        SET status = ?, result = ?, updated_at = ?
        WHERE id = ?
        """,
        ("completed", result_json, now, execution_id)
    )
