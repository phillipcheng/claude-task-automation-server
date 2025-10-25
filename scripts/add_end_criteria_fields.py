"""
Migration script to add end criteria, max iterations, and max tokens fields to tasks table.

This adds support for user-defined end criteria and automatic task termination based on limits.
"""
import mysql.connector
import os

# Database configuration
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "sitebuilder")
DB_NAME = os.getenv("DB_NAME", "claudesys")

def add_end_criteria_fields():
    """Add end criteria and limit tracking fields to tasks table."""
    try:
        # Connect to database
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        cursor = conn.cursor()

        # Define columns to add
        columns_to_add = [
            ("end_criteria", "TEXT NULL", "error_message"),
            ("max_iterations", "INT NOT NULL DEFAULT 20", "end_criteria"),
            ("max_tokens", "INT NULL", "max_iterations"),
            ("total_tokens_used", "INT NOT NULL DEFAULT 0", "max_tokens"),
        ]

        for column_name, column_def, after_column in columns_to_add:
            # Check if column already exists
            cursor.execute("""
                SELECT COUNT(*)
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = %s
                AND TABLE_NAME = 'tasks'
                AND COLUMN_NAME = %s
            """, (DB_NAME, column_name))

            if cursor.fetchone()[0] > 0:
                print(f"Column '{column_name}' already exists in tasks table.")
            else:
                # Add the column
                print(f"Adding '{column_name}' column to tasks table...")
                cursor.execute(f"""
                    ALTER TABLE tasks
                    ADD COLUMN {column_name} {column_def}
                    AFTER {after_column}
                """)
                conn.commit()
                print(f"Successfully added '{column_name}' column.")

        # Update TaskStatus enum to add FINISHED and EXHAUSTED
        print("\nUpdating TaskStatus enum to add FINISHED and EXHAUSTED statuses...")
        cursor.execute("""
            ALTER TABLE tasks
            MODIFY COLUMN status ENUM('pending', 'running', 'paused', 'stopped', 'testing', 'completed', 'failed', 'finished', 'exhausted')
            NOT NULL DEFAULT 'pending'
        """)
        conn.commit()
        print("Successfully updated TaskStatus enum.")

        cursor.close()
        conn.close()
        print("\nAll fields added successfully!")
        print("\nNew fields:")
        print("  - end_criteria: User-defined success criteria (TEXT)")
        print("  - max_iterations: Maximum conversation iterations (INT, default 20)")
        print("  - max_tokens: Maximum total output tokens (INT, optional)")
        print("  - total_tokens_used: Track cumulative output tokens (INT, default 0)")
        print("\nNew statuses:")
        print("  - FINISHED: Task met end criteria successfully")
        print("  - EXHAUSTED: Task hit max iterations or max tokens")

    except mysql.connector.Error as e:
        print(f"Error: {e}")
        raise

if __name__ == "__main__":
    add_end_criteria_fields()
