#!/usr/bin/env python3
"""
Simple Task Monitor - Create a task and monitor it until completion.

Usage:
    python simple_task_monitor.py "add-login" "Implement user login feature" /path/to/project
"""

import sys
import time
import requests
from typing import Optional

API_BASE = "http://localhost:8000/api/v1"


def create_task(task_name: str, description: str, root_folder: str) -> dict:
    """Create a new task."""
    print(f"📝 Creating task: {task_name}")
    print(f"   Description: {description}")
    print(f"   Project: {root_folder}\n")

    response = requests.post(
        f"{API_BASE}/tasks",
        json={
            "task_name": task_name,
            "description": description,
            "root_folder": root_folder,
        },
    )

    if response.status_code != 200:
        print(f"❌ Error creating task: {response.text}")
        sys.exit(1)

    task = response.json()
    print(f"✅ Task created!")
    print(f"   Branch: {task.get('branch_name', 'N/A')}")
    print(f"   Worktree: {task.get('worktree_path', 'N/A')}\n")

    return task


def get_task_status(task_name: str) -> dict:
    """Get current task status."""
    response = requests.get(f"{API_BASE}/tasks/by-name/{task_name}/status")

    if response.status_code != 200:
        print(f"❌ Error getting status: {response.text}")
        sys.exit(1)

    return response.json()


def monitor_task(task_name: str, poll_interval: int = 10):
    """Monitor task until it completes or fails."""
    print(f"👀 Monitoring task: {task_name}")
    print(f"   Checking every {poll_interval} seconds\n")
    print("=" * 80)

    iteration = 0

    while True:
        iteration += 1
        status = get_task_status(task_name)

        # Print status update
        print(f"\n[{iteration}] Status: {status['status'].upper()}")
        print(f"    Progress: {status['progress']}")

        # Show latest Claude response if available
        if status.get('latest_claude_response'):
            claude_msg = status['latest_claude_response']
            # Truncate long messages
            if len(claude_msg) > 200:
                claude_msg = claude_msg[:200] + "..."
            print(f"    Claude: {claude_msg}")

        # Show if waiting for input
        if status.get('waiting_for_input'):
            print(f"    ⏸️  PAUSED - Waiting for input")

        # Show test status
        test_summary = status.get('test_summary', {})
        if test_summary.get('total', 0) > 0:
            print(
                f"    Tests: {test_summary['passed']}/{test_summary['total']} passed"
            )

        # Check if finished
        if status['status'] in ['completed', 'failed']:
            print("\n" + "=" * 80)

            if status['status'] == 'completed':
                print(f"✅ Task COMPLETED!")
                if status.get('summary'):
                    print(f"\nSummary:")
                    print(status['summary'])
                return True
            else:
                print(f"❌ Task FAILED!")
                if status.get('error_message'):
                    print(f"\nError:")
                    print(status['error_message'])
                return False

        # Wait before next poll
        time.sleep(poll_interval)


def main():
    """Main entry point."""
    if len(sys.argv) < 4:
        print("Usage: python simple_task_monitor.py <task_name> <description> <root_folder>")
        print("\nExample:")
        print('  python simple_task_monitor.py "add-login" "Implement login feature" /Users/me/myapp')
        sys.exit(1)

    task_name = sys.argv[1]
    description = sys.argv[2]
    root_folder = sys.argv[3]

    # Create task
    task = create_task(task_name, description, root_folder)

    # Monitor until completion
    success = monitor_task(task_name)

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
