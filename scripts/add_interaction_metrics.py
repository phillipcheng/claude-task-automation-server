"""
Migration script to add token usage and time tracking columns to claude_interactions table.

This adds support for tracking token usage and cost metrics from Claude CLI result events.
"""
import mysql.connector
import os

# Database configuration
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "sitebuilder")
DB_NAME = os.getenv("DB_NAME", "claudesys")

def add_interaction_metrics_columns():
    """Add token usage and time tracking columns to claude_interactions table."""
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
            ("input_tokens", "INT NULL"),
            ("output_tokens", "INT NULL"),
            ("cache_creation_tokens", "INT NULL"),
            ("cache_read_tokens", "INT NULL"),
            ("duration_ms", "INT NULL"),
            ("cost_usd", "FLOAT NULL"),
        ]

        for column_name, column_def in columns_to_add:
            # Check if column already exists
            cursor.execute("""
                SELECT COUNT(*)
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = %s
                AND TABLE_NAME = 'claude_interactions'
                AND COLUMN_NAME = %s
            """, (DB_NAME, column_name))

            if cursor.fetchone()[0] > 0:
                print(f"Column '{column_name}' already exists in claude_interactions table.")
            else:
                # Add the column
                print(f"Adding '{column_name}' column to claude_interactions table...")
                cursor.execute(f"""
                    ALTER TABLE claude_interactions
                    ADD COLUMN {column_name} {column_def}
                    AFTER created_at
                """)
                conn.commit()
                print(f"Successfully added '{column_name}' column.")

        cursor.close()
        conn.close()
        print("\nAll columns added successfully!")

    except mysql.connector.Error as e:
        print(f"Error: {e}")
        raise

if __name__ == "__main__":
    add_interaction_metrics_columns()
