#!/usr/bin/env python3
"""
Example client for the Claude Task Automation Server.

This script demonstrates how to interact with the API to create sessions,
submit tasks, and monitor their progress.
"""

import requests
import time
import json
import sys


BASE_URL = "http://localhost:8000/api/v1"


def create_session(project_path: str) -> str:
    """Create a new session."""
    response = requests.post(
        f"{BASE_URL}/sessions",
        json={"project_path": project_path}
    )
    response.raise_for_status()
    session_data = response.json()
    print(f"✓ Created session: {session_data['id']}")
    return session_data['id']


def create_task(session_id: str, description: str) -> str:
    """Create a new task."""
    response = requests.post(
        f"{BASE_URL}/tasks",
        json={
            "session_id": session_id,
            "description": description
        }
    )
    response.raise_for_status()
    task_data = response.json()
    print(f"✓ Created task: {task_data['id']}")
    print(f"  Description: {description}")
    return task_data['id']


def get_task_status(task_id: str) -> dict:
    """Get task status."""
    response = requests.get(f"{BASE_URL}/tasks/{task_id}/status")
    response.raise_for_status()
    return response.json()


def get_task_details(task_id: str) -> dict:
    """Get full task details."""
    response = requests.get(f"{BASE_URL}/tasks/{task_id}")
    response.raise_for_status()
    return response.json()


def monitor_task(task_id: str, interval: int = 5):
    """Monitor task progress until completion."""
    print(f"\nMonitoring task {task_id}...")
    print("-" * 60)

    while True:
        status = get_task_status(task_id)

        print(f"\nStatus: {status['status']}")
        print(f"Progress: {status['progress']}")

        if status.get('summary'):
            print(f"Summary: {status['summary'][:100]}...")

        test_summary = status['test_summary']
        if test_summary['total'] > 0:
            print(f"Tests: {test_summary['passed']}/{test_summary['total']} passed")

        # Check if task is complete or failed
        if status['status'] in ['completed', 'failed']:
            print("\n" + "=" * 60)
            if status['status'] == 'completed':
                print("✓ Task completed successfully!")
            else:
                print("✗ Task failed!")
                if status.get('error_message'):
                    print(f"Error: {status['error_message']}")
            break

        # Wait before checking again
        time.sleep(interval)


def main():
    """Main function."""
    # Check if server is running
    try:
        response = requests.get("http://localhost:8000/health")
        response.raise_for_status()
    except requests.exceptions.ConnectionError:
        print("Error: Server is not running. Start it with: python -m app.main")
        sys.exit(1)

    print("Claude Task Automation Server - Example Client")
    print("=" * 60)

    # Example 1: Simple task
    print("\nExample 1: Create a simple calculator function")
    print("-" * 60)

    session_id = create_session("/tmp/test_project")
    task_id = create_task(
        session_id,
        "Create a Python calculator module with functions for add, subtract, multiply, and divide. Include proper error handling for division by zero."
    )

    # Monitor the task
    monitor_task(task_id)

    # Get final details
    print("\nFetching final task details...")
    details = get_task_details(task_id)

    print(f"\nInteractions: {len(details.get('interactions', []))}")
    print(f"Test Cases: {len(details.get('test_cases', []))}")

    if details.get('summary'):
        print(f"\nSummary:\n{details['summary']}")


if __name__ == "__main__":
    main()
