#!/usr/bin/env python3

import requests
import json
import time

def test_edit_save_load_cycle():
    base_url = "http://localhost:8000"

    # Create a unique task name
    task_name = f"test_edit_cycle_{int(time.time())}"

    print("=== Step 1: Create task with 1 project ===")
    # Create a task with 1 project initially
    task_data = {
        "task_name": task_name,
        "description": "Test task for edit/save/load cycle",
        "root_folder": "/Users/bytedance/python/claudeserver",
        "use_worktree": True,
        "auto_start": False,
        "projects": [
            {
                "path": "/Users/bytedance/python/claudeserver",
                "access": "write",
                "context": "Main project",
                "name": "Claude Server"
            }
        ],
        "project_context": "Test project context"
    }

    # Create the task
    response = requests.post(f"{base_url}/api/v1/tasks", json=task_data)
    if response.status_code != 200:
        print(f"Failed to create task: {response.status_code}")
        print(response.text)
        return

    print(f"✓ Created task: {task_name}")

    print("\n=== Step 2: Verify initial state - should have 1 project ===")
    # Get task to verify initial state
    response = requests.get(f"{base_url}/api/v1/tasks/by-name/{task_name}")
    if response.status_code != 200:
        print(f"Failed to fetch task: {response.status_code}")
        return

    task = response.json()
    print(f"Initial projects count: {len(task.get('projects', []))}")
    if task.get('projects'):
        for i, project in enumerate(task['projects']):
            print(f"  Project {i+1}: {project.get('name', 'Unnamed')} - {project.get('path')}")

    print("\n=== Step 3: Update task with 2 projects via PUT ===")
    # Add a second project via PUT request
    updated_projects = [
        {
            "path": "/Users/bytedance/python/claudeserver",
            "access": "write",
            "context": "Main project",
            "name": "Claude Server"
        },
        {
            "path": "/tmp",
            "access": "read",
            "context": "Temporary files",
            "name": "Temp Directory"
        }
    ]

    update_data = {
        "projects": updated_projects,
        "project_context": "Updated project context with 2 projects"
    }

    # Update via PUT
    response = requests.put(f"{base_url}/api/v1/tasks/by-name/{task_name}", json=update_data)
    if response.status_code != 200:
        print(f"Failed to update task: {response.status_code}")
        print(response.text)
        return

    print("✓ Updated task with 2 projects")

    print("\n=== Step 4: Verify updated state - should have 2 projects ===")
    # Get task again to verify the update worked
    response = requests.get(f"{base_url}/api/v1/tasks/by-name/{task_name}")
    if response.status_code != 200:
        print(f"Failed to fetch task after update: {response.status_code}")
        return

    task = response.json()
    print(f"After update projects count: {len(task.get('projects', []))}")
    if task.get('projects'):
        for i, project in enumerate(task['projects']):
            print(f"  Project {i+1}: {project.get('name', 'Unnamed')} - {project.get('path')}")

    print(f"Project context: {task.get('project_context', 'None')}")

    print("\n=== Step 5: Test status endpoint as well ===")
    # Also test the status endpoint
    response = requests.get(f"{base_url}/api/v1/tasks/by-name/{task_name}/status")
    if response.status_code == 200:
        status_data = response.json()
        print(f"Status endpoint projects count: {len(status_data.get('projects', []))}")
        if status_data.get('projects'):
            for i, project in enumerate(status_data['projects']):
                print(f"  Status Project {i+1}: {project.get('name', 'Unnamed')} - {project.get('path')}")
    else:
        print(f"Status endpoint failed: {response.status_code}")

    print("\n=== Step 6: Test adding a 3rd project ===")
    # Add a third project
    updated_projects.append({
        "path": "/Users/bytedance",
        "access": "read",
        "context": "Home directory",
        "name": "Home Directory"
    })

    update_data = {
        "projects": updated_projects,
        "project_context": "Final test with 3 projects"
    }

    response = requests.put(f"{base_url}/api/v1/tasks/by-name/{task_name}", json=update_data)
    if response.status_code != 200:
        print(f"Failed to add 3rd project: {response.status_code}")
        print(response.text)
        return

    print("✓ Added 3rd project")

    print("\n=== Step 7: Final verification - should have 3 projects ===")
    # Final verification
    response = requests.get(f"{base_url}/api/v1/tasks/by-name/{task_name}")
    if response.status_code != 200:
        print(f"Failed to fetch task for final verification: {response.status_code}")
        return

    task = response.json()
    final_count = len(task.get('projects', []))
    print(f"Final projects count: {final_count}")
    if task.get('projects'):
        for i, project in enumerate(task['projects']):
            print(f"  Project {i+1}: {project.get('name', 'Unnamed')} - {project.get('path')}")

    print(f"Final project context: {task.get('project_context', 'None')}")

    # Check if the test passed
    if final_count == 3:
        print(f"\n🎉 TEST PASSED! Save/load cycle works correctly.")
        print("The edit modal should now show all 3 projects when opened.")
    else:
        print(f"\n❌ TEST FAILED! Expected 3 projects, got {final_count}")

    print(f"\nTask created: {task_name}")
    print("You can now test the edit modal in the UI to confirm it shows all projects.")

if __name__ == "__main__":
    test_edit_save_load_cycle()