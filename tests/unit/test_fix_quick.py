#!/usr/bin/env python3
"""Quick test of the shell=True fix."""
import requests
import time

# Create task
response = requests.post(
    "http://localhost:8000/api/v1/tasks",
    json={
        "task_name": "test_shell_fix",
        "description": "Create /tmp/test_fix.txt with Hello World",
        "auto_start": True
    }
)
task = response.json()
print(f"Task created: {task['task_name']}, Status: {task['status']}")

# Wait 15 seconds and check status
time.sleep(15)

status_resp = requests.get(f"http://localhost:8000/api/v1/tasks/by-name/test_shell_fix/status")
status = status_resp.json()
print(f"\nAfter 15s:")
print(f"  Status: {status['status']}")
print(f"  Session ID: {status.get('claude_session_id', 'None')}")
print(f"  PID: {status.get('process_pid', 'None')}")

# Check interactions
conv_resp = requests.get(f"http://localhost:8000/api/v1/tasks/by-name/test_shell_fix/conversation")
conv = conv_resp.json()
print(f"  Interactions: {len(conv['conversation'])}")
for i, inter in enumerate(conv['conversation'][:5]):
    print(f"    {i+1}. [{inter['type']}]: {inter['content'][:60]}...")

# Check if file was created
import os
if os.path.exists("/tmp/test_fix.txt"):
    with open("/tmp/test_fix.txt") as f:
        print(f"\n✅ File created! Content: {f.read()}")
else:
    print("\n❌ File not created yet")
