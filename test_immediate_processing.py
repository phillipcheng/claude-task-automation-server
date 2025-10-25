#!/usr/bin/env python3
"""
Test script for immediate processing with session fixes.

This script tests the immediate processing functionality, specifically:
1. Creating a task
2. Starting the task execution
3. Sending immediate user input while task is running
4. Verifying session continuity and response handling
"""

import asyncio
import time
import requests
import json
from typing import Dict, Any

# Server configuration
BASE_URL = "http://localhost:8000"
API_BASE = f"{BASE_URL}/api/v1"

def create_test_task() -> tuple[str, str]:
    """Create a test task that will run for a while."""
    task_name = f"immediate_test_{int(time.time())}"
    task_data = {
        "task_name": task_name,
        "description": "Test task for immediate processing - please create a simple Python script that counts from 1 to 10 with 2 second delays between each number",
        "project_context": "Test project for immediate processing",
        "root_folder": "/tmp/immediate_test"
    }

    print(f"🔧 Creating task: {task_data['task_name']}")
    response = requests.post(f"{API_BASE}/tasks", json=task_data)

    if response.status_code == 200:
        task_id = response.json()["id"]
        print(f"✅ Task created successfully: {task_id} (name: {task_name})")
        return task_id, task_name
    else:
        raise Exception(f"Failed to create task: {response.text}")

def start_task(task_name: str) -> bool:
    """Start the task execution."""
    print(f"🚀 Starting task: {task_name}")
    response = requests.post(f"{API_BASE}/tasks/by-name/{task_name}/start")

    if response.status_code == 200:
        print("✅ Task started successfully")
        return True
    else:
        print(f"❌ Failed to start task: {response.text}")
        return False

def get_task_status(task_id: str) -> Dict[str, Any]:
    """Get current task status."""
    response = requests.get(f"{API_BASE}/tasks/{task_id}/status")
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Failed to get task status: {response.text}")

def send_user_input(task_name: str, user_input: str) -> bool:
    """Send user input to a running task."""
    print(f"💬 Sending user input: {user_input}")

    data = {"input": user_input}
    response = requests.post(f"{API_BASE}/tasks/by-name/{task_name}/user-input", json=data)

    if response.status_code == 200:
        result = response.json()
        print(f"✅ User input sent successfully")
        print(f"   Response: {result}")
        return True
    else:
        print(f"❌ Failed to send user input: {response.text}")
        return False

def get_task_interactions(task_id: str) -> list:
    """Get all interactions for a task."""
    response = requests.get(f"{API_BASE}/tasks/{task_id}/interactions")
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Failed to get interactions: {response.text}")

def wait_for_task_to_be_running(task_id: str, timeout: int = 30) -> bool:
    """Wait for task to reach RUNNING status."""
    print(f"⏳ Waiting for task to start running...")

    start_time = time.time()
    while time.time() - start_time < timeout:
        status = get_task_status(task_id)
        current_status = status.get("status")
        print(f"   Current status: {current_status}")

        if current_status == "RUNNING":
            print("✅ Task is now running!")
            return True
        elif current_status in ["FAILED", "COMPLETED"]:
            print(f"❌ Task ended with status: {current_status}")
            return False

        time.sleep(2)

    print(f"❌ Timeout waiting for task to start running")
    return False

def test_immediate_processing():
    """Main test function for immediate processing."""
    print("🧪 Starting immediate processing test...")
    print("=" * 60)

    try:
        # Step 1: Create task
        task_id, task_name = create_test_task()

        # Step 2: Start task
        if not start_task(task_name):
            return False

        # Step 3: Wait for task to be running
        if not wait_for_task_to_be_running(task_id):
            return False

        # Step 4: Get initial status to see session info
        status = get_task_status(task_id)
        claude_session_id = status.get("claude_session_id")
        print(f"📊 Task status: {status.get('status')}")
        print(f"🔗 Claude session ID: {claude_session_id}")

        # Step 5: Send immediate user input while task is running
        test_inputs = [
            "Please add a print statement that says 'Hello from immediate processing!'",
            "Can you also make the delay shorter, like 1 second instead of 2?",
            "Actually, let's make it count to 5 instead of 10"
        ]

        for i, user_input in enumerate(test_inputs, 1):
            print(f"\n📝 Test input {i}:")
            success = send_user_input(task_name, user_input)

            if success:
                # Wait a bit and check if response was received
                time.sleep(3)
                interactions = get_task_interactions(task_id)
                recent_interactions = interactions[-5:]  # Get last 5 interactions

                print(f"   Recent interactions ({len(recent_interactions)}):")
                for interaction in recent_interactions:
                    interaction_type = interaction.get("interaction_type")
                    content_preview = interaction.get("content", "")[:100] + "..." if len(interaction.get("content", "")) > 100 else interaction.get("content", "")
                    timestamp = interaction.get("created_at")
                    print(f"     [{timestamp}] {interaction_type}: {content_preview}")

            # Wait before next input
            time.sleep(5)

        # Step 6: Final status check
        print(f"\n📊 Final task status:")
        final_status = get_task_status(task_id)
        print(f"   Status: {final_status.get('status')}")
        print(f"   Claude session ID: {final_status.get('claude_session_id')}")
        print(f"   Total tokens: {final_status.get('total_tokens_used', 0)}")

        # Step 7: Show all interactions
        print(f"\n💬 All task interactions:")
        all_interactions = get_task_interactions(task_id)
        print(f"   Total interactions: {len(all_interactions)}")

        for i, interaction in enumerate(all_interactions):
            interaction_type = interaction.get("interaction_type")
            content = interaction.get("content", "")
            timestamp = interaction.get("created_at")
            print(f"   {i+1}. [{timestamp}] {interaction_type}")
            if len(content) > 200:
                print(f"      {content[:200]}...")
            else:
                print(f"      {content}")
            print()

        print("✅ Immediate processing test completed successfully!")
        return True

    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_immediate_processing()
    if success:
        print("\n🎉 All tests passed!")
    else:
        print("\n💥 Tests failed!")

    exit(0 if success else 1)