"""Data models for persistasaurus."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Execution:
    """Represents a durable execution."""
    id: str
    status: str
    created_at: datetime
    updated_at: datetime
    result: Optional[str] = None
    error: Optional[str] = None


@dataclass
class Step:
    """Represents a step in an execution."""
    id: int
    execution_id: str
    step_index: int
    status: str
    payload: Optional[str]
    created_at: datetime
    updated_at: datetime
