"""
Step-by-step task execution test.
Shows each iteration, human simulation, criteria checking, and resource tracking.
"""

import asyncio
import requests
import time
import json
from datetime import datetime

API_BASE = "http://localhost:8000/api/v1"


def print_separator(char="=", length=80):
    print(char * length)


def print_header(text):
    print_separator("=")
    print(f"  {text}")
    print_separator("=")


def print_step(step_num, title):
    print(f"\n{'─' * 80}")
    print(f"📍 STEP {step_num}: {title}")
    print(f"{'─' * 80}")


def print_interaction(interaction_type, content, metadata=None):
    """Print an interaction with formatting."""
    icons = {
        "user_request": "👤 USER",
        "simulated_human": "🤖 AUTO",
        "claude_response": "🧠 CLAUDE"
    }

    icon = icons.get(interaction_type, f"📝 {interaction_type.upper()}")

    print(f"\n{icon}:")
    print(f"{'─' * 40}")

    # Truncate long content
    if len(content) > 300:
        print(content[:300] + "...")
        print(f"[... {len(content) - 300} more characters]")
    else:
        print(content)

    if metadata:
        print(f"\n📊 Metadata:")
        for key, value in metadata.items():
            print(f"  • {key}: {value}")


def get_task_status(task_name):
    """Get detailed task status."""
    try:
        response = requests.get(f"{API_BASE}/tasks/by-name/{task_name}/status")
        return response.json() if response.ok else None
    except Exception as e:
        print(f"❌ Error getting task status: {e}")
        return None


def get_task_conversation(task_name):
    """Get full conversation history."""
    try:
        response = requests.get(f"{API_BASE}/tasks/by-name/{task_name}/conversation")
        return response.json() if response.ok else None
    except Exception as e:
        print(f"❌ Error getting conversation: {e}")
        return None


def display_task_info(task_data):
    """Display task configuration and status."""
    print("\n📋 Task Configuration:")
    print(f"  • Name: {task_data.get('task_name')}")
    print(f"  • Status: {task_data.get('status')}")
    print(f"  • Description: {task_data.get('description')[:100]}...")

    config = task_data.get('end_criteria_config', {})
    if config:
        print(f"\n🎯 Ending Criteria:")
        if config.get('criteria'):
            print(f"  • Success Criteria: {config['criteria']}")
        print(f"  • Max Iterations: {config.get('max_iterations', 'N/A')}")
        print(f"  • Max Tokens: {config.get('max_tokens', 'No limit')}")
        if config.get('warning'):
            print(f"  ⚠️  Warning: {config['warning']}")

    tokens_used = task_data.get('total_tokens_used', 0)
    print(f"\n📊 Resource Usage:")
    print(f"  • Tokens Used: {tokens_used:,}")


def monitor_task_execution(task_name, max_wait_seconds=300):
    """Monitor task execution and show each iteration."""
    print_header(f"MONITORING TASK: {task_name}")

    start_time = time.time()
    last_interaction_count = 0
    iteration_number = 0

    # Initial status
    status = get_task_status(task_name)
    if status:
        display_task_info(status)

    print(f"\n⏱️  Started monitoring at {datetime.now().strftime('%H:%M:%S')}")
    print(f"⏳ Will timeout after {max_wait_seconds} seconds")
    print_separator("-")

    while True:
        elapsed = time.time() - start_time

        if elapsed > max_wait_seconds:
            print(f"\n⏰ Timeout reached ({max_wait_seconds}s)")
            break

        # Get conversation
        conv_data = get_task_conversation(task_name)
        if not conv_data:
            time.sleep(2)
            continue

        conversation = conv_data.get('conversation', [])
        current_count = len(conversation)

        # Check for new interactions
        if current_count > last_interaction_count:
            new_interactions = conversation[last_interaction_count:]

            for interaction in new_interactions:
                interaction_type = interaction['type']
                content = interaction['content']

                # Count iterations based on user/simulated inputs
                if interaction_type in ['user_request', 'simulated_human']:
                    if interaction_type == 'simulated_human':
                        iteration_number += 1
                        print_step(iteration_number, "ITERATION")

                # Print the interaction
                metadata = {
                    'Timestamp': interaction['timestamp'],
                    'Type': interaction_type
                }
                print_interaction(interaction_type, content, metadata)

            last_interaction_count = current_count

        # Get current status
        status = get_task_status(task_name)
        current_status = status.get('status') if status else 'unknown'

        # Check if task finished
        if current_status in ['completed', 'failed', 'finished', 'exhausted']:
            print_step("FINAL", f"TASK {current_status.upper()}")

            if status:
                print(f"\n📊 Final Status: {current_status.upper()}")

                if status.get('summary'):
                    print(f"\n📝 Summary:")
                    print(f"  {status['summary']}")

                if status.get('error_message'):
                    print(f"\n❌ Error:")
                    print(f"  {status['error_message']}")

                config = status.get('end_criteria_config', {})
                tokens_used = status.get('total_tokens_used', 0)

                print(f"\n📊 Final Resource Usage:")
                print(f"  • Total Iterations: {iteration_number}")
                print(f"  • Tokens Used: {tokens_used:,}")
                if config.get('max_iterations'):
                    print(f"  • Max Iterations: {config['max_iterations']}")
                if config.get('max_tokens'):
                    print(f"  • Max Tokens: {config['max_tokens']:,}")

                # Test summary
                test_summary = status.get('test_summary', {})
                if test_summary.get('total', 0) > 0:
                    print(f"\n🧪 Test Results:")
                    print(f"  • Total: {test_summary['total']}")
                    print(f"  • Passed: {test_summary['passed']}")
                    print(f"  • Failed: {test_summary['failed']}")
                    print(f"  • Pending: {test_summary['pending']}")

            break

        # Show progress
        print(f"\r⏳ Status: {current_status.upper()} | Iterations: {iteration_number} | Elapsed: {int(elapsed)}s", end='', flush=True)

        time.sleep(2)

    print(f"\n\n✅ Monitoring completed in {int(time.time() - start_time)} seconds")
    print_separator("=")


def create_test_task():
    """Create a simple test task."""
    print_header("CREATING TEST TASK")

    task_data = {
        "task_name": f"test_step_by_step_{int(time.time())}",
        "description": "Create a simple Python function called greet(name) that returns 'Hello, {name}!'. Save it to greet.py in /tmp/test_greeting.",
        "root_folder": "/tmp/test_greeting",
        "end_criteria": "File greet.py exists with a working greet(name) function that returns the correct greeting",
        "max_iterations": 10,
        "max_tokens": 20000,
        "use_worktree": False,
        "auto_start": True
    }

    print("\n📝 Task Details:")
    print(f"  • Name: {task_data['task_name']}")
    print(f"  • Description: {task_data['description']}")
    print(f"  • Ending Criteria: {task_data['end_criteria']}")
    print(f"  • Max Iterations: {task_data['max_iterations']}")
    print(f"  • Max Tokens: {task_data['max_tokens']:,}")
    print(f"  • Auto Start: {task_data['auto_start']}")

    try:
        print("\n🚀 Creating task...")
        response = requests.post(f"{API_BASE}/tasks", json=task_data)

        if response.ok:
            result = response.json()
            print(f"✅ Task created successfully!")
            print(f"  • Task ID: {result['id']}")
            return task_data['task_name']
        else:
            error = response.json()
            print(f"❌ Failed to create task: {error.get('detail', 'Unknown error')}")
            return None

    except Exception as e:
        print(f"❌ Error creating task: {e}")
        return None


def main():
    """Run the step-by-step test."""
    print("\n" + "=" * 80)
    print("  STEP-BY-STEP TASK EXECUTION TEST")
    print("  Monitoring each iteration until completion or exhaustion")
    print("=" * 80)

    # Check if server is running
    try:
        response = requests.get(f"{API_BASE.replace('/api/v1', '')}/")
        print(f"\n✅ Server is running at {API_BASE}")
    except:
        print(f"\n❌ Server is not running at {API_BASE}")
        print("Please start the server with: python -m app.main")
        return

    # Create task
    task_name = create_test_task()
    if not task_name:
        print("\n❌ Failed to create task. Exiting.")
        return

    # Wait a moment for task to start
    print("\n⏳ Waiting 3 seconds for task to start...")
    time.sleep(3)

    # Monitor execution
    try:
        monitor_task_execution(task_name, max_wait_seconds=180)
    except KeyboardInterrupt:
        print("\n\n⚠️  Monitoring interrupted by user")
        status = get_task_status(task_name)
        if status:
            print(f"Current status: {status.get('status')}")

    print("\n" + "=" * 80)
    print("  TEST COMPLETED")
    print("=" * 80)
    print(f"\nYou can view the full conversation at:")
    print(f"  http://localhost:8000/api/v1/tasks/by-name/{task_name}/conversation")
    print(f"\nOr in the web UI at:")
    print(f"  http://localhost:8000/")
    print()


if __name__ == "__main__":
    main()
