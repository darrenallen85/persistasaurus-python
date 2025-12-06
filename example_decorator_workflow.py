"""Example using the high-level decorator-based workflow API."""
import asyncio
import random
import sys
from pathlib import Path

from persistasaurus import (
    Database,
    DatabaseConfig,
    durable_workflow,
    start_workflow,
    WorkflowContext,
)
from persistasaurus.migrations import apply_migrations


# Simulated external functions that can fail
async def validate_order(data: dict) -> dict:
    """Validate order data."""
    print("    → Validating order...")
    await asyncio.sleep(0.5)
    
    if not data.get("order_id"):
        raise ValueError("Missing order_id")
    
    return {"validation": "passed", "items": 3}


async def fetch_inventory(data: dict) -> dict:
    """Fetch inventory from external system (can fail)."""
    print("    → Fetching inventory...")
    await asyncio.sleep(0.5)
    
    # Simulate random failure (30% chance)
    if random.random() < 0.3:
        raise ConnectionError("Inventory service timeout")
    
    return {"inventory_status": "available", "warehouse": "WH-01"}


async def charge_payment(data: dict) -> dict:
    """Charge customer payment."""
    print("    → Charging payment...")
    await asyncio.sleep(0.5)
    
    # Simulate random failure (20% chance)
    if random.random() < 0.2:
        raise IOError("Payment gateway error")
    
    return {"payment_id": "pay_12345", "amount": 99.99}


async def ship_order(data: dict) -> dict:
    """Ship the order."""
    print("    → Shipping order...")
    await asyncio.sleep(0.5)
    
    return {"tracking_number": "TRK-98765", "carrier": "FedEx"}


async def send_confirmation(data: dict) -> dict:
    """Send confirmation email."""
    print("    → Sending confirmation...")
    await asyncio.sleep(0.3)
    
    return {"email_sent": True, "timestamp": "2025-12-06T12:00:00Z"}


async def main():
    """Run the order processing workflow."""
    
    # Set up database
    db = Database(DatabaseConfig(sqlite_path="workflow_example.db"))
    await db.connect()
    
    migrations_dir = Path(__file__).parent / "migrations"
    await apply_migrations(db, migrations_dir)
    print("✓ Database initialized\n")
    
    # Define the workflow using the decorator
    @durable_workflow(db)
    async def process_order(ctx: WorkflowContext):
        """Order processing workflow with automatic step tracking."""
        
        async with ctx.step("validate_order"):
            result = await validate_order(ctx.state)
            ctx.state.update(result)
        
        async with ctx.step("fetch_inventory"):
            inventory = await fetch_inventory(ctx.state)
            ctx.state.update(inventory)
        
        async with ctx.step("charge_payment"):
            payment = await charge_payment(ctx.state)
            ctx.state.update(payment)
        
        async with ctx.step("ship_order"):
            shipping = await ship_order(ctx.state)
            ctx.state.update(shipping)
        
        async with ctx.step("send_confirmation"):
            confirmation = await send_confirmation(ctx.state)
            ctx.state.update(confirmation)
        
        return ctx.state
    
    # Check if resuming or starting new
    if len(sys.argv) > 1:
        execution_id = sys.argv[1]
        print("=" * 60)
        print(f"Resuming workflow: {execution_id}")
        print("=" * 60)
        print()
        
        try:
            await start_workflow(
                db,
                process_order,
                {"order_id": "ORD-001", "customer": "Alice"},
                execution_id=execution_id
            )
            print("\n✅ Workflow completed successfully!")
            
        except Exception as e:
            print(f"\n❌ Workflow failed: {e}")
            print(f"💡 Resume with: python example_decorator_workflow.py {execution_id}")
    
    else:
        print("=" * 60)
        print("Starting new order processing workflow")
        print("=" * 60)
        print()
        
        initial_state = {
            "order_id": "ORD-001",
            "customer": "Alice",
            "email": "alice@example.com"
        }
        
        try:
            execution_id = await start_workflow(db, process_order, initial_state)
            print("\n✅ Workflow completed successfully!")
            
        except Exception as e:
            print(f"\n❌ Workflow failed: {e}")
    
    await db.close()
    print("\n✓ Database connection closed")


if __name__ == "__main__":
    asyncio.run(main())
