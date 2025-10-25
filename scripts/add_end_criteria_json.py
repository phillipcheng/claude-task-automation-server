"""
Migration script to add end criteria JSON config and token tracking to tasks table.
"""
import mysql.connector
import os

# Database configuration
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "sitebuilder")
DB_NAME = os.getenv("DB_NAME", "claudesys")

def add_end_criteria_json():
    """Add end_criteria_config JSON field and total_tokens_used to tasks table."""
    try:
        # Connect to database
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        cursor = conn.cursor()

        print("Adding end_criteria_config JSON column...")
        try:
            cursor.execute("""
                ALTER TABLE tasks
                ADD COLUMN end_criteria_config JSON NULL
                AFTER error_message
            """)
            conn.commit()
            print("✓ Successfully added end_criteria_config column")
        except mysql.connector.Error as e:
            if "Duplicate column name" in str(e):
                print("✓ Column 'end_criteria_config' already exists")
            else:
                raise

        print("\nAdding total_tokens_used column...")
        try:
            cursor.execute("""
                ALTER TABLE tasks
                ADD COLUMN total_tokens_used INT NOT NULL DEFAULT 0
                AFTER end_criteria_config
            """)
            conn.commit()
            print("✓ Successfully added total_tokens_used column")
        except mysql.connector.Error as e:
            if "Duplicate column name" in str(e):
                print("✓ Column 'total_tokens_used' already exists")
            else:
                raise

        print("\nUpdating TaskStatus enum to add FINISHED and EXHAUSTED...")
        cursor.execute("""
            ALTER TABLE tasks
            MODIFY COLUMN status ENUM('pending', 'running', 'paused', 'stopped', 'testing', 'completed', 'failed', 'finished', 'exhausted')
            NOT NULL DEFAULT 'pending'
        """)
        conn.commit()
        print("✓ Successfully updated TaskStatus enum")

        cursor.close()
        conn.close()

        print("\n" + "="*60)
        print("Migration completed successfully!")
        print("="*60)
        print("\nAdded fields:")
        print("  - end_criteria_config: JSON field for end criteria configuration")
        print("     Format: {'criteria': '...', 'max_iterations': 20, 'max_tokens': 100000}")
        print("  - total_tokens_used: Track cumulative output tokens (INT, default 0)")
        print("\nNew statuses:")
        print("  - FINISHED: Task met end criteria successfully")
        print("  - EXHAUSTED: Task hit max iterations or max tokens")

    except mysql.connector.Error as e:
        print(f"❌ Error: {e}")
        raise

if __name__ == "__main__":
    add_end_criteria_json()
