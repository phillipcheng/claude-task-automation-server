#!/usr/bin/env python3
"""
Test the enhanced tool collapsing functionality.
"""

import requests
import json

def test_enhanced_collapsing():
    """Test if the enhanced collapsing logic is working."""

    # Get tasks
    response = requests.get("http://localhost:8000/api/v1/tasks")
    tasks = response.json()

    print(f"Found {len(tasks)} total tasks")

    # Find a task with conversations
    for task in tasks:
        task_id = task['id']

        # Get conversation without collapsing
        response_no_collapse = requests.get(f"http://localhost:8000/api/v1/tasks/{task_id}/conversation?collapse_tools=false")
        conversation_no_collapse = response_no_collapse.json().get('conversation', [])

        # Get conversation with collapsing
        response_collapse = requests.get(f"http://localhost:8000/api/v1/tasks/{task_id}/conversation?collapse_tools=true")
        conversation_collapse = response_collapse.json().get('conversation', [])

        if len(conversation_no_collapse) > 0:
            print(f"\nTask {task_id}:")
            print(f"  Status: {task.get('status')}")
            print(f"  Description: {task.get('description', 'No description')[:100]}...")
            print(f"  Original conversation length: {len(conversation_no_collapse)}")
            print(f"  Collapsed conversation length: {len(conversation_collapse)}")

            if len(conversation_collapse) < len(conversation_no_collapse):
                compression_ratio = (len(conversation_no_collapse) - len(conversation_collapse)) / len(conversation_no_collapse) * 100
                print(f"  Compression: {compression_ratio:.1f}% reduction")

                # Check for tool_group entries
                tool_groups = [msg for msg in conversation_collapse if msg.get('type') == 'tool_group']
                print(f"  Tool groups created: {len(tool_groups)}")

                # Show some sample collapsed entries
                if tool_groups:
                    print(f"  Sample tool group: {tool_groups[0].get('summary', 'No summary')[:80]}...")

                # Show message types in collapsed conversation
                message_types = {}
                for msg in conversation_collapse:
                    msg_type = msg.get('type', 'unknown')
                    message_types[msg_type] = message_types.get(msg_type, 0) + 1
                print(f"  Message types in collapsed conversation: {message_types}")

                return True
            else:
                print(f"  No compression achieved")

    print("\nNo tasks with substantial conversations found to test collapsing")
    return False

if __name__ == "__main__":
    success = test_enhanced_collapsing()
    if success:
        print("\n✅ Enhanced collapsing functionality is working!")
    else:
        print("\n❌ Could not test enhanced collapsing - no suitable conversations found")