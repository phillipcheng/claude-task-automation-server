#!/usr/bin/env python3
"""
Migration script to add user_id column to tasks table.
"""
import os
import sys
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError, ProgrammingError

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./tasks.db")


def run_migration():
    """Add user_id column to tasks table if it doesn't exist."""
    print(f"Connecting to database: {DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else DATABASE_URL}")

    engine = create_engine(DATABASE_URL)

    # Check if column already exists
    check_column_sql = """
    SELECT COUNT(*)
    FROM information_schema.columns
    WHERE table_name = 'tasks' AND column_name = 'user_id'
    """ if "mysql" in DATABASE_URL else """
    SELECT COUNT(*) FROM pragma_table_info('tasks') WHERE name='user_id'
    """

    with engine.connect() as conn:
        result = conn.execute(text(check_column_sql))
        column_exists = result.scalar() > 0

        if column_exists:
            print("Column 'user_id' already exists in 'tasks' table. No migration needed.")
            return

        # Add user_id column
        print("Adding 'user_id' column to 'tasks' table...")

        if "mysql" in DATABASE_URL:
            alter_sql = """
            ALTER TABLE tasks
            ADD COLUMN user_id VARCHAR(100) NULL,
            ADD INDEX idx_tasks_user_id (user_id)
            """
        else:
            # SQLite
            alter_sql = "ALTER TABLE tasks ADD COLUMN user_id VARCHAR(100)"

        try:
            conn.execute(text(alter_sql))
            conn.commit()
            print("Migration completed successfully!")
            print("- Added column: user_id VARCHAR(100)")
            if "mysql" in DATABASE_URL:
                print("- Added index: idx_tasks_user_id")
        except (OperationalError, ProgrammingError) as e:
            print(f"Migration failed: {e}")
            raise


if __name__ == "__main__":
    run_migration()
