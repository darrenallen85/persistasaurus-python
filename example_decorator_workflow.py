"""Example using the high-level decorator-based workflow API.

This example demonstrates different error handling strategies:

1. Automatic error persistence - The @durable_workflow decorator automatically
   catches and persists errors, allowing workflows to be resumed.

2. In-step retry logic - For transient errors, you can add retry logic within
   a step using try/except.

3. Critical vs non-critical steps - Critical steps (like payment) should fail
   the workflow, while non-critical steps (like email) can log errors and continue.

4. Validation errors - Check preconditions and raise clear errors for bad data.

5. Exception categorization - Different error types should be handled differently:
   - ValueError: Bad input data, don't retry
   - ConnectionError/IOError: Transient, safe to retry
   - Generic Exception: Unexpected, log and investigate
"""
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
    
    if not data.get("customer"):
        raise ValueError("Missing customer information")
    
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
        
        # Step 1: Validate order
        # Errors here will be caught and persisted automatically by the decorator
        async with ctx.step("validate_order"):
            result = await validate_order(ctx.state)
            ctx.state.update(result)
        
        # Step 2: Fetch inventory (can fail due to external service)
        async with ctx.step("fetch_inventory"):
            try:
                inventory = await fetch_inventory(ctx.state)
                ctx.state.update(inventory)
            except ConnectionError as e:
                # Option 1: Add retry logic within the step
                print(f"      ⚠️  Retrying after error: {e}")
                await asyncio.sleep(1)
                inventory = await fetch_inventory(ctx.state)
                ctx.state.update(inventory)
        
        # Step 3: Charge payment (critical step - let it fail and be retried by caller)
        async with ctx.step("charge_payment"):
            payment = await charge_payment(ctx.state)
            ctx.state.update(payment)
        
        # Step 4: Ship order (validate state before proceeding)
        async with ctx.step("ship_order"):
            # Ensure payment was successful before shipping
            if not ctx.state.get("payment_id"):
                raise ValueError("Cannot ship order without payment confirmation")
            
            shipping = await ship_order(ctx.state)
            ctx.state.update(shipping)
        
        # Step 5: Send confirmation (non-critical - catch and log errors)
        async with ctx.step("send_confirmation"):
            try:
                confirmation = await send_confirmation(ctx.state)
                ctx.state.update(confirmation)
            except Exception as e:
                # Non-critical step - log error but don't fail workflow
                print(f"      ⚠️  Failed to send confirmation: {e}")
                ctx.state["email_sent"] = False
                ctx.state["email_error"] = str(e)
        
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
            
        except ValueError as e:
            # Validation errors - these indicate bad data, don't retry
            print(f"\n❌ Validation error: {e}")
            print("⚠️  Fix the data issue before retrying")
            
        except (ConnectionError, IOError) as e:
            # Transient errors - safe to retry
            print(f"\n❌ Transient error: {e}")
            print(f"💡 Resume with: python example_decorator_workflow.py {execution_id}")
            print("   The workflow will retry from the failed step")
            
        except Exception as e:
            # Unexpected errors
            print(f"\n❌ Unexpected error: {type(e).__name__}: {e}")
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
            
        except ValueError as e:
            # Validation errors - bad input data
            print(f"\n❌ Validation error: {e}")
            print("⚠️  Check your input data")
            
        except (ConnectionError, IOError) as e:
            # Transient errors - retry possible
            print(f"\n❌ Transient error: {e}")
            print(f"💡 The execution was saved. Resume with:")
            print(f"   python example_decorator_workflow.py <execution-id>")
            
        except Exception as e:
            # Catch-all for unexpected errors
            print(f"\n❌ Unexpected error: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
    
    await db.close()
    print("\n✓ Database connection closed")


if __name__ == "__main__":
    asyncio.run(main())
