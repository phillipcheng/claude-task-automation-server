#!/usr/bin/env python3
"""
Create and Start Task Example - Demonstrates manual lifecycle control.

Shows the new workflow:
1. Create task (doesn't auto-start)
2. Explicitly start when ready
3. Monitor until completion
4. Stop/resume if needed

Usage:
    python create_and_start.py "task-name" "description" /path/to/project
"""

import sys
import time
import requests

API_BASE = "http://localhost:8000/api/v1"


def create_task(task_name: str, description: str, root_folder: str) -> dict:
    """Create task without auto-starting."""
    print(f"📝 Creating task: {task_name}")
    print(f"   Description: {description}")
    print(f"   Project: {root_folder}")
    print(f"   Auto-start: No\n")

    response = requests.post(
        f"{API_BASE}/tasks",
        json={
            "task_name": task_name,
            "description": description,
            "root_folder": root_folder,
            "auto_start": False,  # Don't start automatically
        },
    )

    if response.status_code != 200:
        print(f"❌ Error creating task: {response.text}")
        sys.exit(1)

    task = response.json()
    print(f"✅ Task created!")
    print(f"   Status: {task['status']}")  # Should be 'pending'
    print(f"   Branch: {task.get('branch_name', 'N/A')}")
    print(f"   Worktree: {task.get('worktree_path', 'N/A')}\n")

    return task


def start_task(task_name: str):
    """Start a pending task."""
    print(f"▶️  Starting task: {task_name}")

    response = requests.post(f"{API_BASE}/tasks/by-name/{task_name}/start")

    if response.status_code != 200:
        print(f"❌ Error starting task: {response.text}")
        sys.exit(1)

    result = response.json()
    print(f"✅ Task started!")
    print(f"   {result['message']}\n")


def stop_task(task_name: str):
    """Stop a running task."""
    print(f"⏸️  Stopping task: {task_name}")

    response = requests.post(f"{API_BASE}/tasks/by-name/{task_name}/stop")

    if response.status_code != 200:
        print(f"❌ Error stopping task: {response.text}")
        return False

    result = response.json()
    print(f"✅ Task stopped!")
    print(f"   {result['message']}\n")
    return True


def resume_task(task_name: str):
    """Resume a stopped task."""
    print(f"▶️  Resuming task: {task_name}")

    response = requests.post(f"{API_BASE}/tasks/by-name/{task_name}/resume")

    if response.status_code != 200:
        print(f"❌ Error resuming task: {response.text}")
        return False

    result = response.json()
    print(f"✅ Task resumed!")
    print(f"   {result['message']}\n")
    return True


def get_task_status(task_name: str) -> dict:
    """Get current task status."""
    response = requests.get(f"{API_BASE}/tasks/by-name/{task_name}/status")

    if response.status_code != 200:
        print(f"❌ Error getting status: {response.text}")
        sys.exit(1)

    return response.json()


def monitor_task(task_name: str, iterations: int = 5):
    """Monitor task for a few iterations."""
    print(f"👀 Monitoring task: {task_name} (showing {iterations} updates)\n")
    print("=" * 80)

    for i in range(1, iterations + 1):
        status = get_task_status(task_name)

        print(f"\n[{i}] Status: {status['status'].upper()}")
        print(f"    Progress: {status['progress']}")

        if status.get('latest_claude_response'):
            claude_msg = status['latest_claude_response'][:150]
            print(f"    Claude: {claude_msg}...")

        if status.get('waiting_for_input'):
            print(f"    ⏸️  PAUSED - Waiting for input")

        # Check if finished
        if status['status'] in ['completed', 'failed', 'stopped']:
            print("\n" + "=" * 80)
            if status['status'] == 'completed':
                print(f"✅ Task COMPLETED!")
            elif status['status'] == 'failed':
                print(f"❌ Task FAILED!")
            elif status['status'] == 'stopped':
                print(f"⏸️  Task STOPPED by user")
            return status['status']

        time.sleep(5)

    print("\n" + "=" * 80)
    return status['status']


def main():
    """Main workflow demonstration."""
    if len(sys.argv) < 4:
        print("Usage: python create_and_start.py <task_name> <description> <root_folder>")
        print("\nExample:")
        print('  python create_and_start.py "add-login" "Implement login" /Users/me/myapp')
        sys.exit(1)

    task_name = sys.argv[1]
    description = sys.argv[2]
    root_folder = sys.argv[3]

    # Step 1: Create task (doesn't start)
    task = create_task(task_name, description, root_folder)

    # Verify it's pending
    if task['status'] != 'pending':
        print(f"⚠️  Warning: Expected 'pending', got '{task['status']}'")

    # Step 2: Wait a moment (simulating "when you're ready")
    print("⏳ Waiting 3 seconds before starting...\n")
    time.sleep(3)

    # Step 3: Explicitly start the task
    start_task(task_name)

    # Step 4: Monitor for a bit
    final_status = monitor_task(task_name, iterations=5)

    # Demonstration: Stop and resume
    if final_status == 'running':
        print("\n📚 Demonstrating stop/resume...")
        print()

        # Stop the task
        stop_task(task_name)

        # Verify it's stopped
        status = get_task_status(task_name)
        print(f"Status after stop: {status['status']}")

        # Wait a bit
        print("\n⏳ Waiting 3 seconds before resuming...\n")
        time.sleep(3)

        # Resume
        resume_task(task_name)

        # Monitor a bit more
        print()
        final_status = monitor_task(task_name, iterations=3)

    # Final status
    print(f"\nFinal status: {final_status}")
    sys.exit(0 if final_status == 'completed' else 1)


if __name__ == "__main__":
    main()
