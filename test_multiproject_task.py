#!/usr/bin/env python3

import requests
import json

def test_multiproject_task():
    base_url = "http://localhost:8000"

    # Create a task with multiple projects
    task_data = {
        "task_name": "test_multiproject_schema",
        "description": "Test task with multiple projects",
        "root_folder": "/Users/bytedance/python/claudeserver",
        "use_worktree": True,
        "auto_start": False,
        "projects": [
            {
                "path": "/Users/bytedance/python/claudeserver",
                "access": "write",
                "context": "Main Claude server project",
                "name": "Claude Server"
            },
            {
                "path": "/tmp",
                "access": "read",
                "context": "Temporary directory for testing",
                "name": "Temp Directory"
            }
        ],
        "project_context": "Multi-project test scenario"
    }

    # Create the task
    print("Creating task with multiple projects...")
    response = requests.post(f"{base_url}/api/v1/tasks", json=task_data)
    if response.status_code != 200:
        print(f"Failed to create task: {response.status_code}")
        print(response.text)
        return

    task_response = response.json()
    print(f"Created task: {task_response['task_name']}")

    # Get task by name to test the API response
    print("\nFetching task to test API response...")
    response = requests.get(f"{base_url}/api/v1/tasks/by-name/{task_data['task_name']}")
    if response.status_code != 200:
        print(f"Failed to fetch task: {response.status_code}")
        return

    fetched_task = response.json()

    # Check if projects and project_context are included in response
    print(f"projects field present: {'projects' in fetched_task}")
    print(f"project_context field present: {'project_context' in fetched_task}")

    if 'projects' in fetched_task and fetched_task['projects']:
        print(f"Number of projects: {len(fetched_task['projects'])}")
        print("Projects data:")
        for i, project in enumerate(fetched_task['projects']):
            print(f"  {i+1}. {project.get('name', 'Unnamed')}: {project.get('path')}")
    else:
        print("No projects data in response")

    if 'project_context' in fetched_task:
        print(f"Project context: {fetched_task['project_context']}")

    # Also test the status endpoint
    print("\nTesting status endpoint...")
    response = requests.get(f"{base_url}/api/v1/tasks/by-name/{task_data['task_name']}/status")
    if response.status_code == 200:
        status_data = response.json()
        print(f"Status endpoint - projects field present: {'projects' in status_data}")
        print(f"Status endpoint - project_context field present: {'project_context' in status_data}")
    else:
        print(f"Status endpoint failed: {response.status_code}")

if __name__ == "__main__":
    test_multiproject_task()