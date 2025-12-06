# Persistasaurus Python

An async durable execution library for Python, inspired by the Java [persistasaurus](https://github.com/gunnarmorling/persistasaurus) project.

## Overview

Persistasaurus-python provides a lightweight framework for building durable, fault-tolerant workflows that persist their execution state to a database. It uses raw SQL with SQLite for development (PostgreSQL support planned) and provides an async API built on `aiosqlite`.

## Features

- **Async-first**: Built with `asyncio` and `aiosqlite` for high-performance async workflows
- **Durable execution**: All execution state and steps are persisted to the database
- **Simple API**: Clean, minimal API without heavy ORM abstractions
- **SQLite for dev**: Easy local development with SQLite
- **Raw SQL**: Transparent database operations with no ORM magic
- **Migration system**: Simple SQL-file-based migrations

## Installation

1. Clone the repository:
```bash
git clone https://github.com/darrenallen85/persistasaurus-python.git
cd persistasaurus-python
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Running the Demo API

The demo Quart application provides a REST API for creating and managing durable executions.

```bash
# Set PYTHONPATH to include the project root
export PYTHONPATH=.

# Run the Quart app
quart run --app demo_quart_app.app:app --reload
```

Or simply:
```bash
python demo_quart_app/app.py
```

The API will be available at `http://localhost:8000`.

### API Endpoints

#### Create an execution
```bash
curl -X POST http://localhost:8000/executions \
  -H "Content-Type: application/json" \
  -d '{"workflow": "example", "input": "test data"}'
```

Response:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000"
}
```

#### List executions
```bash
curl http://localhost:8000/executions
```

Response:
```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "running",
    "created_at": "2025-12-06T10:30:00+00:00",
    "updated_at": "2025-12-06T10:30:00+00:00",
    "result": null,
    "error": null
  }
]
```

#### Get a specific execution
```bash
curl http://localhost:8000/executions/550e8400-e29b-41d4-a716-446655440000
```

#### Append a step to an execution
```bash
curl -X POST http://localhost:8000/executions/550e8400-e29b-41d4-a716-446655440000/steps \
  -H "Content-Type: application/json" \
  -d '{"step": "process", "data": "processing..."}'
```

Response:
```json
{
  "status": "step added"
}
```

#### Mark execution as completed
```bash
curl -X POST http://localhost:8000/executions/550e8400-e29b-41d4-a716-446655440000/complete \
  -H "Content-Type: application/json" \
  -d '{"result": {"status": "success", "output": "completed successfully"}}'
```

Response:
```json
{
  "status": "completed"
}
```

### Using the Library Directly

**Simple example (low-level API):**

```python
import asyncio
from pathlib import Path
from persistasaurus import (
    Database,
    DatabaseConfig,
    create_execution,
    get_execution,
    append_step,
    mark_execution_completed,
)
from persistasaurus.migrations import apply_migrations


async def main():
    # Initialize database
    db = Database(DatabaseConfig(sqlite_path="my_app.db"))
    await db.connect()
    
    # Run migrations
    migrations_dir = Path("migrations")
    await apply_migrations(db, migrations_dir)
    
    # Create an execution
    execution_id = await create_execution(db, {"workflow": "example"})
    print(f"Created execution: {execution_id}")
    
    # Add steps as you complete them
    await append_step(db, execution_id, {"step": "initialize"}, status="completed")
    await append_step(db, execution_id, {"step": "process"}, status="completed")
    await append_step(db, execution_id, {"step": "finalize"}, status="completed")
    
    # Mark as completed
    await mark_execution_completed(db, execution_id, {"status": "success"})
    
    # Retrieve execution
    execution = await get_execution(db, execution_id)
    print(f"Execution status: {execution.status}")
    
    await db.close()


if __name__ == "__main__":
    asyncio.run(main())
```

**High-level decorator API (recommended):**

```python
from persistasaurus import Database, DatabaseConfig, durable_workflow, start_workflow, WorkflowContext

db = Database(DatabaseConfig(sqlite_path="my_app.db"))
await db.connect()

@durable_workflow(db)
async def process_order(ctx: WorkflowContext):
    """Order processing workflow with automatic step tracking."""
    
    async with ctx.step("validate_order"):
        result = await validate_order(ctx.state)
        ctx.state.update(result)
    
    async with ctx.step("charge_payment"):
        payment = await charge_payment(ctx.state)
        ctx.state.update(payment)
    
    async with ctx.step("ship_order"):
        shipping = await ship_order(ctx.state)
        ctx.state.update(shipping)
    
    return ctx.state

# Start the workflow
execution_id = await start_workflow(db, process_order, {"order_id": "ORD-001"})

# Resume a failed workflow
await start_workflow(db, process_order, {"order_id": "ORD-001"}, execution_id=execution_id)
```

**Features of the decorator API:**
- ✅ Automatic step tracking and persistence
- ✅ Automatic state management via `ctx.state`
- ✅ Automatic skip of completed steps on resume
- ✅ Cleaner, more declarative syntax
- ✅ Similar to Java persistasaurus `@DurableTask`

**Complete examples:**

For complete working examples, see:
- [`example_decorator_workflow.py`](example_decorator_workflow.py) - High-level decorator API (recommended)
- [`example_resumable_workflow.py`](example_resumable_workflow.py) - Low-level explicit API

Both examples demonstrate:
- Multi-step workflow execution
- Automatic/manual retry with backoff
- Resuming from the last successful step
- Proper error tracking in the database
- Complete audit trail of all attempts

Run them with:
```bash
# Decorator-based (high-level)
python example_decorator_workflow.py

# Explicit API (low-level)
python example_resumable_workflow.py
```

## Configuration

Environment variables (optional `.env` file):

- `SQLITE_PATH`: Path to SQLite database file (default: `persistasaurus.db`)
- `DATABASE_URL`: Database URL (default: constructed from `SQLITE_PATH`)

## Database Schema

### executions
- `id` (TEXT, PRIMARY KEY): UUID of the execution
- `status` (TEXT): Current status (e.g., "running", "completed")
- `created_at` (TEXT): ISO8601 timestamp
- `updated_at` (TEXT): ISO8601 timestamp
- `result` (TEXT): JSON-encoded result (nullable)
- `error` (TEXT): Error message if failed (nullable)

### steps
- `id` (INTEGER, PRIMARY KEY): Auto-increment ID
- `execution_id` (TEXT): Foreign key to executions
- `step_index` (INTEGER): Step sequence number
- `status` (TEXT): Step status
- `payload` (TEXT): JSON-encoded step data
- `created_at` (TEXT): ISO8601 timestamp
- `updated_at` (TEXT): ISO8601 timestamp

## Project Structure

```
persistasaurus-python/
  requirements.txt          # Python dependencies
  README.md                 # This file
  
  persistasaurus/           # Core library
    __init__.py
    config.py               # Configuration and env variables
    db.py                   # Database abstraction layer
    migrations.py           # Migration runner
    engine.py               # Core execution engine
    models.py               # Data models
    errors.py               # Custom exceptions
  
  migrations/               # SQL migration files
    001_init.sql
  
  demo_quart_app/           # Demo REST API
    app.py
  
  tests/                    # Tests (to be added)
```

## Inspiration

This project is inspired by [Gunnar Morling's persistasaurus](https://github.com/gunnarmorling/persistasaurus), a Java-based durable execution framework. The Python version adapts the core concepts for async Python workflows.

## License

MIT

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
