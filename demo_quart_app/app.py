"""Quart-based demo API for persistasaurus."""

import json
from pathlib import Path
from quart import Quart, request, jsonify

from persistasaurus import (
    Database,
    DatabaseConfig,
    create_execution,
    get_execution,
    list_executions,
    append_step,
    mark_execution_completed,
    NotFoundError,
)
from persistasaurus.config import SQLITE_PATH
from persistasaurus.migrations import apply_migrations


def create_app() -> Quart:
    """Create and configure the Quart application."""
    app = Quart(__name__)
    
    # Database instance
    db = Database(DatabaseConfig(sqlite_path=SQLITE_PATH))
    
    @app.before_serving
    async def startup():
        """Initialize database and run migrations on startup."""
        await db.connect()
        migrations_dir = Path(__file__).parent.parent / "migrations"
        await apply_migrations(db, migrations_dir)
        print(f"✓ Database initialized at {SQLITE_PATH}")
    
    @app.after_serving
    async def shutdown():
        """Close database connection on shutdown."""
        await db.close()
        print("✓ Database connection closed")
    
    @app.route("/executions", methods=["POST"])
    async def create_execution_endpoint():
        """Create a new execution.
        
        POST /executions
        Body: JSON payload as initial data
        Returns: {"id": "<execution-id>"}
        """
        data = await request.get_json()
        execution_id = await create_execution(db, data or {})
        return jsonify({"id": execution_id}), 201
    
    @app.route("/executions", methods=["GET"])
    async def list_executions_endpoint():
        """List recent executions.
        
        GET /executions
        Returns: Array of execution objects
        """
        executions = await list_executions(db)
        return jsonify([
            {
                "id": e.id,
                "status": e.status,
                "created_at": e.created_at.isoformat(),
                "updated_at": e.updated_at.isoformat(),
                "result": e.result,
                "error": e.error,
            }
            for e in executions
        ])
    
    @app.route("/executions/<execution_id>", methods=["GET"])
    async def get_execution_endpoint(execution_id: str):
        """Get a specific execution.
        
        GET /executions/<execution_id>
        Returns: Execution object or 404
        """
        execution = await get_execution(db, execution_id)
        if not execution:
            return jsonify({"error": "Execution not found"}), 404
        
        return jsonify({
            "id": execution.id,
            "status": execution.status,
            "created_at": execution.created_at.isoformat(),
            "updated_at": execution.updated_at.isoformat(),
            "result": execution.result,
            "error": execution.error,
        })
    
    @app.route("/executions/<execution_id>/steps", methods=["POST"])
    async def append_step_endpoint(execution_id: str):
        """Append a step to an execution.
        
        POST /executions/<execution_id>/steps
        Body: JSON payload
        Returns: 201 with acknowledgment
        """
        try:
            data = await request.get_json()
            await append_step(db, execution_id, data or {})
            return jsonify({"status": "step added"}), 201
        except NotFoundError:
            return jsonify({"error": "Execution not found"}), 404
    
    @app.route("/executions/<execution_id>/complete", methods=["POST"])
    async def complete_execution_endpoint(execution_id: str):
        """Mark an execution as completed.
        
        POST /executions/<execution_id>/complete
        Body: {"result": ...} or any JSON
        Returns: {"status": "completed"}
        """
        try:
            data = await request.get_json()
            result = data.get("result") if data else None
            await mark_execution_completed(db, execution_id, result)
            return jsonify({"status": "completed"})
        except NotFoundError:
            return jsonify({"error": "Execution not found"}), 404
    
    return app


# Create app instance
app = create_app()


if __name__ == "__main__":
    app.run(debug=True, port=8000)
