#!/usr/bin/env python3
"""
Script to set up MySQL database for Claude Task Automation Server.

This script will:
1. Connect to MySQL server
2. Create the 'claudesys' database if it doesn't exist
3. Initialize all tables
"""

import pymysql
import sys
from dotenv import load_dotenv
import os

load_dotenv()

# MySQL connection details
MYSQL_HOST = "localhost"
MYSQL_USER = "root"
MYSQL_PASSWORD = "sitebuilder"
DATABASE_NAME = "claudesys"


def create_database():
    """Create the claudesys database if it doesn't exist."""
    try:
        # Connect to MySQL server (without specifying database)
        connection = pymysql.connect(
            host=MYSQL_HOST,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
        )

        cursor = connection.cursor()

        # Create database
        print(f"Creating database '{DATABASE_NAME}'...")
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DATABASE_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        print(f"✓ Database '{DATABASE_NAME}' created/verified")

        # Show databases
        cursor.execute("SHOW DATABASES")
        databases = cursor.fetchall()
        print("\nAvailable databases:")
        for db in databases:
            print(f"  - {db[0]}")

        cursor.close()
        connection.close()

        return True

    except pymysql.Error as e:
        print(f"✗ Error creating database: {e}")
        return False


def initialize_tables():
    """Initialize database tables using SQLAlchemy."""
    try:
        print(f"\nInitializing tables in '{DATABASE_NAME}'...")

        # Import after database is created
        from app.database import init_db, engine

        # Initialize tables
        init_db()

        # Verify tables were created
        from sqlalchemy import inspect
        inspector = inspect(engine)
        tables = inspector.get_table_names()

        print(f"\n✓ Tables created successfully:")
        for table in tables:
            print(f"  - {table}")

        return True

    except Exception as e:
        print(f"✗ Error initializing tables: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_connection():
    """Verify we can connect to the database."""
    try:
        connection = pymysql.connect(
            host=MYSQL_HOST,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=DATABASE_NAME,
        )

        cursor = connection.cursor()
        cursor.execute("SELECT DATABASE()")
        current_db = cursor.fetchone()

        print(f"\n✓ Successfully connected to database: {current_db[0]}")

        # Show table count
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        print(f"✓ Found {len(tables)} tables")

        cursor.close()
        connection.close()

        return True

    except pymysql.Error as e:
        print(f"✗ Error connecting to database: {e}")
        return False


def main():
    """Main setup function."""
    print("=" * 60)
    print("Claude Task Automation Server - MySQL Setup")
    print("=" * 60)

    # Step 1: Create database
    if not create_database():
        print("\n✗ Failed to create database. Please check your MySQL connection.")
        sys.exit(1)

    # Step 2: Initialize tables
    if not initialize_tables():
        print("\n✗ Failed to initialize tables.")
        sys.exit(1)

    # Step 3: Verify connection
    if not verify_connection():
        print("\n✗ Failed to verify database connection.")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("✓ MySQL setup complete!")
    print("=" * 60)
    print("\nDatabase connection string:")
    print(f"  mysql+pymysql://{MYSQL_USER}:****@{MYSQL_HOST}/{DATABASE_NAME}")
    print("\nAdd this to your .env file:")
    print(f"  DATABASE_URL=mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}/{DATABASE_NAME}")
    print("\nYou can now start the server:")
    print("  python -m app.main")


if __name__ == "__main__":
    main()
