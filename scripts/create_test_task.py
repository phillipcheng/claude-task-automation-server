#!/usr/bin/env python3
"""
Create a test task to generate conversation data for testing enhanced collapsing.
"""

import requests
import json

def create_test_task():
    """Create a simple test task."""

    task_data = {
        "task_name": "test_collapsing_hello_world",
        "description": "Create a simple hello world Python script that prints 'Hello, World!' and test it",
        "root_folder": "/tmp/test_claude_collapsing",
        "project_name": "test_collapsing",
        "end_criteria_config": {
            "criteria": "Task is complete when a hello world script is created and working",
            "max_iterations": 3,
            "max_tokens": 5000
        }
    }

    # Create the task
    response = requests.post("http://localhost:8000/api/v1/tasks", json=task_data)

    if response.status_code == 200:
        task = response.json()
        task_id = task['id']
        print(f"✅ Created test task: {task_id}")
        print(f"Task name: {task.get('name', 'No name')}")
        print(f"Description: {task['description']}")
        return task_id
    else:
        print(f"❌ Failed to create task: {response.status_code}")
        print(response.text)
        return None

if __name__ == "__main__":
    task_id = create_test_task()
    if task_id:
        print(f"\nYou can monitor this task at: http://localhost:8000/?task_id={task_id}")
        print("Once it runs for a bit, you can test the enhanced collapsing functionality!")