"""
Migration script to add claude_session_id column to tasks table.

This adds support for session-based conversations with Claude CLI using the -r flag.
"""
import mysql.connector
import os

# Database configuration
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "sitebuilder")
DB_NAME = os.getenv("DB_NAME", "claudesys")

def add_claude_session_id_column():
    """Add claude_session_id column to tasks table."""
    try:
        # Connect to database
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        cursor = conn.cursor()

        # Check if column already exists
        cursor.execute("""
            SELECT COUNT(*)
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = %s
            AND TABLE_NAME = 'tasks'
            AND COLUMN_NAME = 'claude_session_id'
        """, (DB_NAME,))

        if cursor.fetchone()[0] > 0:
            print("Column 'claude_session_id' already exists in tasks table.")
            return

        # Add the column
        print("Adding 'claude_session_id' column to tasks table...")
        cursor.execute("""
            ALTER TABLE tasks
            ADD COLUMN claude_session_id VARCHAR(100) NULL
            AFTER process_pid
        """)

        conn.commit()
        print("Successfully added 'claude_session_id' column to tasks table.")

        cursor.close()
        conn.close()

    except mysql.connector.Error as e:
        print(f"Error: {e}")
        raise

if __name__ == "__main__":
    add_claude_session_id_column()
