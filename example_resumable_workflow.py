"""Example of a resumable workflow with error handling and recovery."""
import asyncio
import random
from pathlib import Path
from typing import Optional

from persistasaurus import (
    Database,
    DatabaseConfig,
    create_execution,
    get_execution,
    append_step,
    mark_execution_completed,
    NotFoundError,
)
from persistasaurus.migrations import apply_migrations


class DataPipelineWorkflow:
    """Example workflow that can fail and resume from where it left off."""
    
    def __init__(self, db: Database):
        self.db = db
        self.steps = [
            ("validate_input", self._validate_input),
            ("fetch_external_data", self._fetch_external_data),
            ("transform_data", self._transform_data),
            ("load_to_warehouse", self._load_to_warehouse),
            ("send_notifications", self._send_notifications),
        ]
    
    async def _validate_input(self, execution_id: str, payload: dict) -> dict:
        """Validate input data."""
        print("  → Validating input...")
        await asyncio.sleep(0.5)  # Simulate work
        
        if not payload.get("input_file"):
            raise ValueError("Missing input_file")
        
        return {"validation": "passed", "records": 1000}
    
    async def _fetch_external_data(self, execution_id: str, payload: dict) -> dict:
        """Fetch data from external API (can fail)."""
        print("  → Fetching external data...")
        await asyncio.sleep(0.5)
        
        # Simulate random failure (30% chance)
        if random.random() < 0.3:
            raise ConnectionError("External API timeout")
        
        return {"external_data": "fetched", "api_records": 500}
    
    async def _transform_data(self, execution_id: str, payload: dict) -> dict:
        """Transform the data."""
        print("  → Transforming data...")
        await asyncio.sleep(0.5)
        
        return {"transformed_records": 1500}
    
    async def _load_to_warehouse(self, execution_id: str, payload: dict) -> dict:
        """Load data to warehouse."""
        print("  → Loading to warehouse...")
        await asyncio.sleep(0.5)
        
        # Simulate another potential failure point
        if random.random() < 0.2:
            raise IOError("Warehouse connection failed")
        
        return {"loaded_records": 1500, "warehouse_id": "wh_12345"}
    
    async def _send_notifications(self, execution_id: str, payload: dict) -> dict:
        """Send completion notifications."""
        print("  → Sending notifications...")
        await asyncio.sleep(0.3)
        
        return {"notifications_sent": 3}
    
    async def execute(self, execution_id: str) -> bool:
        """
        Execute the workflow, resuming from the last successful step.
        
        Returns True if completed, False if failed (can be retried).
        """
        execution = await get_execution(self.db, execution_id)
        if not execution:
            raise NotFoundError(f"Execution {execution_id} not found")
        
        # Get the payload from the execution
        import json
        initial_payload = json.loads(execution.result) if execution.result else {}
        
        # Find which steps are already completed
        completed_steps = await self._get_completed_steps(execution_id)
        start_from = len(completed_steps)
        
        if start_from > 0:
            print(f"\n📦 Resuming from step {start_from + 1}/{len(self.steps)}")
        
        # Execute remaining steps
        accumulated_data = initial_payload.copy()
        
        for idx in range(start_from, len(self.steps)):
            step_name, step_func = self.steps[idx]
            
            print(f"\n[Step {idx + 1}/{len(self.steps)}] {step_name}")
            
            # Record step as pending
            await append_step(
                self.db,
                execution_id,
                {"step": step_name, "status": "pending"},
                status="pending"
            )
            
            try:
                # Execute the step
                result = await step_func(execution_id, accumulated_data)
                
                # Update step as completed with result
                await append_step(
                    self.db,
                    execution_id,
                    {"step": step_name, "status": "completed", "result": result},
                    status="completed"
                )
                
                # Accumulate data for next step
                accumulated_data.update(result)
                print(f"  ✓ Completed: {step_name}")
                
            except Exception as e:
                # Record the failure
                error_msg = f"{type(e).__name__}: {str(e)}"
                print(f"  ✗ Failed: {error_msg}")
                
                await append_step(
                    self.db,
                    execution_id,
                    {"step": step_name, "status": "failed", "error": error_msg},
                    status="failed"
                )
                
                # Update execution with error (but keep it in 'running' state for retry)
                await self.db.execute(
                    """
                    UPDATE executions 
                    SET error = ?, updated_at = datetime('now')
                    WHERE id = ?
                    """,
                    (error_msg, execution_id)
                )
                
                return False  # Workflow can be retried
        
        # All steps completed successfully
        await mark_execution_completed(self.db, execution_id, accumulated_data)
        print(f"\n✅ Workflow completed successfully!")
        return True
    
    async def _get_completed_steps(self, execution_id: str) -> list:
        """Get list of completed steps for this execution."""
        rows = await self.db.fetch_all(
            """
            SELECT step_index, status, payload
            FROM steps
            WHERE execution_id = ? AND status = 'completed'
            ORDER BY step_index
            """,
            (execution_id,)
        )
        return rows


async def main():
    """Demonstrate resumable workflow with error handling."""
    
    # Set up database
    db = Database(DatabaseConfig(sqlite_path="resumable_example.db"))
    await db.connect()
    
    migrations_dir = Path(__file__).parent / "migrations"
    await apply_migrations(db, migrations_dir)
    print("✓ Database initialized\n")
    
    # Create initial execution
    print("=" * 60)
    print("Creating new data pipeline execution...")
    print("=" * 60)
    
    execution_id = await create_execution(db, {
        "input_file": "data/sales_2024.csv",
        "config": {"batch_size": 100, "retry_count": 3}
    })
    print(f"✓ Created execution: {execution_id}\n")
    
    # Create workflow instance
    workflow = DataPipelineWorkflow(db)
    
    # Attempt to execute (may fail and need retry)
    max_retries = 5
    attempt = 1
    
    while attempt <= max_retries:
        print(f"\n{'=' * 60}")
        print(f"Attempt {attempt}/{max_retries}")
        print("=" * 60)
        
        success = await workflow.execute(execution_id)
        
        if success:
            break
        
        # If failed, wait and retry
        if attempt < max_retries:
            wait_time = 2 * attempt  # Exponential backoff
            print(f"\n⏳ Waiting {wait_time}s before retry...")
            await asyncio.sleep(wait_time)
            attempt += 1
        else:
            print(f"\n❌ Failed after {max_retries} attempts")
            break
    
    # Show final state
    print(f"\n{'=' * 60}")
    print("Final Execution State")
    print("=" * 60)
    
    final_execution = await get_execution(db, execution_id)
    if final_execution:
        print(f"Status: {final_execution.status}")
        print(f"Created: {final_execution.created_at}")
        print(f"Updated: {final_execution.updated_at}")
        
        if final_execution.result:
            print(f"Result: {final_execution.result}")
        
        if final_execution.error:
            print(f"Last Error: {final_execution.error}")
    
    # Show all steps
    print(f"\n{'=' * 60}")
    print("Step History")
    print("=" * 60)
    
    steps = await db.fetch_all(
        """
        SELECT step_index, status, payload, created_at
        FROM steps
        WHERE execution_id = ?
        ORDER BY step_index, created_at
        """,
        (execution_id,)
    )
    
    for step in steps:
        import json
        payload = json.loads(step['payload'])
        step_name = payload.get('step', 'unknown')
        status = step['status']
        status_icon = "✓" if status == "completed" else "✗" if status == "failed" else "⏳"
        print(f"  {status_icon} Step {step['step_index']}: {step_name} [{status}]")
    
    await db.close()
    print("\n✓ Database connection closed")


if __name__ == "__main__":
    # Set random seed for reproducibility (remove to see different failures)
    # random.seed(42)
    
    asyncio.run(main())
