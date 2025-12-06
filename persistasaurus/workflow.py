"""Decorator-based workflow API for durable execution."""

import asyncio
import functools
import json
from contextlib import asynccontextmanager
from typing import Any, Callable, Dict, Optional

from persistasaurus.db import Database
from persistasaurus.engine import (
    create_execution,
    get_execution,
    append_step,
    mark_execution_completed,
)


class WorkflowContext:
    """Context object for workflow execution with automatic state management."""
    
    def __init__(self, db: Database, execution_id: str, initial_state: Optional[Dict[str, Any]] = None):
        self.db = db
        self.execution_id = execution_id
        self.state: Dict[str, Any] = initial_state or {}
        self._current_step_index = 0
        self._completed_steps: set[int] = set()
    
    async def _load_completed_steps(self) -> None:
        """Load which steps have already been completed."""
        rows = await self.db.fetch_all(
            """
            SELECT step_index, payload
            FROM steps
            WHERE execution_id = ? AND status = 'completed'
            ORDER BY step_index
            """,
            (self.execution_id,)
        )
        
        # Track completed step indices
        self._completed_steps = {row['step_index'] for row in rows}
        
        # Restore state from completed steps
        for row in rows:
            payload = json.loads(row['payload'])
            if 'state' in payload:
                self.state.update(payload['state'])
    
    @asynccontextmanager
    async def step(self, name: str):
        """
        Context manager for defining a workflow step.
        
        Usage:
            async with ctx.step("validate_input"):
                result = await validate(ctx.state)
                ctx.state['validated'] = result
        """
        step_index = self._current_step_index
        self._current_step_index += 1
        
        # Check if this step was already completed
        if step_index in self._completed_steps:
            print(f"  ⏭️  Skipping completed step {step_index}: {name}")
            yield  # Skip execution but yield control
            return
        
        print(f"  ▶️  Executing step {step_index}: {name}")
        
        # Record step as pending
        await append_step(
            self.db,
            self.execution_id,
            {"step": name, "step_index": step_index},
            status="pending"
        )
        
        try:
            # Execute the step
            yield
            
            # Mark as completed with current state
            await append_step(
                self.db,
                self.execution_id,
                {"step": name, "step_index": step_index, "state": self.state},
                status="completed"
            )
            
            self._completed_steps.add(step_index)
            print(f"  ✓ Completed step {step_index}: {name}")
            
        except Exception as e:
            # Record failure
            error_msg = f"{type(e).__name__}: {str(e)}"
            print(f"  ✗ Failed step {step_index}: {name} - {error_msg}")
            
            await append_step(
                self.db,
                self.execution_id,
                {"step": name, "step_index": step_index, "error": error_msg},
                status="failed"
            )
            
            # Update execution with error
            await self.db.execute(
                """
                UPDATE executions 
                SET error = ?, updated_at = datetime('now')
                WHERE id = ?
                """,
                (error_msg, self.execution_id)
            )
            
            raise  # Re-raise to stop workflow


def durable_workflow(db: Database):
    """
    Decorator for creating durable workflows.
    
    Usage:
        @durable_workflow(db)
        async def my_workflow(ctx: WorkflowContext):
            async with ctx.step("step1"):
                ctx.state['result'] = await do_work()
            
            async with ctx.step("step2"):
                await do_more_work(ctx.state['result'])
            
            return ctx.state
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(execution_id: str, initial_state: Optional[Dict[str, Any]] = None) -> Any:
            # Create context
            ctx = WorkflowContext(db, execution_id, initial_state)
            
            # Load previously completed steps
            await ctx._load_completed_steps()
            
            if ctx._completed_steps:
                print(f"\n📦 Resuming workflow with {len(ctx._completed_steps)} completed step(s)\n")
            
            try:
                # Execute the workflow function
                result = await func(ctx)
                
                # Mark execution as completed
                await mark_execution_completed(db, execution_id, result or ctx.state)
                
                return result
                
            except Exception as e:
                # Workflow failed, but state is already saved
                print(f"\n❌ Workflow failed: {e}")
                print(f"💡 Resume with: workflow('{execution_id}')")
                raise
        
        return wrapper
    
    return decorator


async def start_workflow(
    db: Database,
    workflow_func: Callable,
    initial_state: Dict[str, Any],
    execution_id: Optional[str] = None
) -> str:
    """
    Start a new workflow or resume an existing one.
    
    Args:
        db: Database instance
        workflow_func: Decorated workflow function
        initial_state: Initial workflow state
        execution_id: Optional execution ID to resume
    
    Returns:
        Execution ID
    """
    if execution_id:
        # Resume existing workflow
        execution = await get_execution(db, execution_id)
        if not execution:
            raise ValueError(f"Execution {execution_id} not found")
        
        print(f"Resuming execution: {execution_id}")
        await workflow_func(execution_id, initial_state)
        return execution_id
    else:
        # Create new workflow
        new_execution_id = await create_execution(db, initial_state)
        print(f"Created execution: {new_execution_id}")
        
        try:
            await workflow_func(new_execution_id, initial_state)
        except Exception:
            print(f"\n💡 To resume, use: start_workflow(db, workflow_func, initial_state, '{new_execution_id}')")
            raise
        
        return new_execution_id
