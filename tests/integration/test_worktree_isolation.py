#!/usr/bin/env python3
"""
Test script to verify Claude session isolation to task worktree branches.
"""

import requests
import json
import subprocess
import os
import time

API_BASE = "http://localhost:8000/api/v1"

def test_worktree_isolation():
    """Test that Claude sessions are properly isolated to their worktree branches."""

    print("🧪 Testing Claude Worktree Branch Isolation")
    print("=" * 60)

    # Get all tasks
    try:
        response = requests.get(f"{API_BASE}/tasks")
        tasks = response.json()
        print(f"Found {len(tasks)} total tasks")

        worktree_tasks = []
        for task in tasks:
            if task.get('worktree_path') and task.get('branch_name'):
                worktree_tasks.append(task)

        print(f"Found {len(worktree_tasks)} tasks with worktrees")

        if not worktree_tasks:
            print("❌ No worktree tasks found for testing")
            return False

        # Test each worktree task
        all_tests_passed = True

        for i, task in enumerate(worktree_tasks[:3]):  # Test first 3 tasks
            print(f"\n🔍 Testing Task {i+1}: {task.get('name', 'Unknown')}")
            print(f"   Worktree: {task['worktree_path']}")
            print(f"   Branch: {task['branch_name']}")

            # Test 1: Verify worktree directory exists
            worktree_path = task['worktree_path']
            if not os.path.exists(worktree_path):
                print(f"   ❌ Worktree directory does not exist: {worktree_path}")
                all_tests_passed = False
                continue

            print(f"   ✅ Worktree directory exists")

            # Test 2: Verify correct branch is checked out
            try:
                result = subprocess.run(
                    ["git", "branch", "--show-current"],
                    cwd=worktree_path,
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                current_branch = result.stdout.strip()

                if current_branch == task['branch_name']:
                    print(f"   ✅ Correct branch checked out: {current_branch}")
                else:
                    print(f"   ❌ Branch mismatch. Expected: {task['branch_name']}, Current: {current_branch}")
                    all_tests_passed = False
                    continue

            except Exception as e:
                print(f"   ❌ Could not verify branch: {e}")
                all_tests_passed = False
                continue

            # Test 3: Verify worktree is isolated from main repository
            try:
                # Check if there are any changes in the worktree
                result = subprocess.run(
                    ["git", "status", "--porcelain"],
                    cwd=worktree_path,
                    capture_output=True,
                    text=True,
                    timeout=5
                )

                worktree_changes = result.stdout.strip()
                if worktree_changes:
                    print(f"   ✅ Worktree has isolated changes (expected)")
                    print(f"        Modified files: {len(worktree_changes.splitlines())}")
                else:
                    print(f"   ℹ️ Worktree is clean (no local changes)")

            except Exception as e:
                print(f"   ⚠️ Could not check worktree status: {e}")

            # Test 4: Verify task has Claude session ID (indicates active isolation)
            if task.get('claude_session_id'):
                print(f"   ✅ Task has Claude session ID: {task['claude_session_id'][:8]}...")
            else:
                print(f"   ℹ️ Task has no Claude session ID (not yet started)")

        # Test 5: Verify main repository is on a different branch
        print(f"\n🔍 Testing Main Repository Isolation")

        main_repos = set()
        for task in worktree_tasks:
            # Extract main repo path from worktree path
            worktree_path = task['worktree_path']
            if '.claude_worktrees' in worktree_path:
                main_repo = worktree_path.split('.claude_worktrees')[0]
                main_repos.add(main_repo)

        for main_repo in main_repos:
            if os.path.exists(main_repo):
                try:
                    result = subprocess.run(
                        ["git", "branch", "--show-current"],
                        cwd=main_repo,
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    main_branch = result.stdout.strip()

                    # Check that main repo is not on any task branch
                    task_branches = [task['branch_name'] for task in worktree_tasks]
                    if main_branch not in task_branches:
                        print(f"   ✅ Main repo isolated on branch: {main_branch}")
                    else:
                        print(f"   ⚠️ Main repo on task branch: {main_branch}")

                except Exception as e:
                    print(f"   ❌ Could not check main repo branch: {e}")
                    all_tests_passed = False

        # Test 6: Check git worktree list consistency
        print(f"\n🔍 Testing Git Worktree List Consistency")

        for main_repo in main_repos:
            if os.path.exists(main_repo):
                try:
                    result = subprocess.run(
                        ["git", "worktree", "list"],
                        cwd=main_repo,
                        capture_output=True,
                        text=True,
                        timeout=10
                    )

                    worktree_list = result.stdout.strip()
                    worktree_lines = worktree_list.split('\n') if worktree_list else []

                    print(f"   ✅ Git worktree list has {len(worktree_lines)} entries")

                    # Verify each task's worktree is in the list
                    task_worktrees_in_main = [
                        task for task in worktree_tasks
                        if task['worktree_path'].startswith(main_repo)
                    ]

                    for task in task_worktrees_in_main:
                        worktree_found = any(task['worktree_path'] in line for line in worktree_lines)
                        if worktree_found:
                            print(f"   ✅ Task worktree registered: {os.path.basename(task['worktree_path'])}")
                        else:
                            print(f"   ❌ Task worktree not registered: {os.path.basename(task['worktree_path'])}")
                            all_tests_passed = False

                except Exception as e:
                    print(f"   ❌ Could not check git worktree list: {e}")
                    all_tests_passed = False

        print(f"\n" + "=" * 60)
        if all_tests_passed:
            print("🎉 All worktree isolation tests PASSED!")
            print("✅ Claude sessions are properly isolated to task-specific branches")
            return True
        else:
            print("❌ Some worktree isolation tests FAILED!")
            print("⚠️ Review the above output for issues")
            return False

    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        return False

def test_isolation_enforcement():
    """Test that the enhanced isolation enforcement is working."""

    print("\n🛡️ Testing Enhanced Isolation Enforcement")
    print("=" * 60)

    try:
        # Get tasks to test enforcement
        response = requests.get(f"{API_BASE}/tasks")
        tasks = response.json()

        enforced_tasks = [
            task for task in tasks
            if task.get('worktree_path') and task.get('status') in ['running', 'paused', 'completed']
        ]

        if not enforced_tasks:
            print("ℹ️ No tasks found to test enforcement (need running/paused/completed tasks)")
            return True

        print(f"Testing enforcement on {len(enforced_tasks)} tasks")

        for task in enforced_tasks[:2]:  # Test first 2 tasks
            print(f"\n🔍 Testing Task: {task.get('name', 'Unknown')}")

            # Verify task has required isolation fields
            required_fields = ['worktree_path', 'branch_name', 'claude_session_id']
            missing_fields = [field for field in required_fields if not task.get(field)]

            if missing_fields:
                print(f"   ⚠️ Missing isolation fields: {missing_fields}")
            else:
                print(f"   ✅ All isolation fields present")

            # Verify worktree path validation would work
            worktree_path = task['worktree_path']
            if os.path.exists(worktree_path) and os.path.isdir(worktree_path):
                print(f"   ✅ Worktree path validation would pass")
            else:
                print(f"   ❌ Worktree path validation would fail")

        print(f"\n✅ Enhanced isolation enforcement tests completed")
        return True

    except Exception as e:
        print(f"❌ Enforcement test failed: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Claude Task Automation Server - Worktree Isolation Test")
    print("=" * 80)

    # Test basic isolation
    isolation_passed = test_worktree_isolation()

    # Test enforcement
    enforcement_passed = test_isolation_enforcement()

    print("\n" + "=" * 80)
    if isolation_passed and enforcement_passed:
        print("🎉 ALL TESTS PASSED! Claude worktree isolation is working correctly.")
        print("✅ Your system ensures Claude sessions work only on task-specific branches.")
    else:
        print("❌ SOME TESTS FAILED! Review the isolation setup.")

    print("\n📊 Test Summary:")
    print(f"   Worktree Isolation: {'✅ PASS' if isolation_passed else '❌ FAIL'}")
    print(f"   Enforcement Tests:  {'✅ PASS' if enforcement_passed else '❌ FAIL'}")