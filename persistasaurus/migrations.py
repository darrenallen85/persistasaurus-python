"""Database migration management."""

from pathlib import Path
from persistasaurus.db import Database


async def apply_migrations(db: Database, migrations_dir: Path) -> None:
    """Apply database migrations from SQL files.
    
    Args:
        db: Database instance
        migrations_dir: Directory containing migration SQL files
    """
    # Ensure schema_migrations table exists
    await db.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            name TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    
    # Get already applied migrations
    applied = await db.fetch_all("SELECT name FROM schema_migrations")
    applied_names = {row["name"] for row in applied}
    
    # Get all migration files, sorted
    migration_files = sorted(migrations_dir.glob("*.sql"))
    
    for migration_file in migration_files:
        migration_name = migration_file.name
        
        if migration_name not in applied_names:
            print(f"Applying migration: {migration_name}")
            
            # Read migration SQL and split into individual statements
            sql = migration_file.read_text()
            # Split by semicolon and filter out empty statements
            statements = [s.strip() for s in sql.split(';') if s.strip()]
            
            # Execute each statement separately
            for statement in statements:
                await db.execute(statement)
            
            # Record migration as applied
            await db.execute(
                "INSERT INTO schema_migrations (name) VALUES (?)",
                (migration_name,)
            )
            
            print(f"✓ Applied {migration_name}")
