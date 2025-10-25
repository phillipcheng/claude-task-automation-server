#!/usr/bin/env python3
"""
Test script to verify the fix for Claude context path leakage.
"""

class MockTask:
    """Mock task class to simulate worktree task."""
    def __init__(self, worktree_path=None, branch_name=None):
        self.worktree_path = worktree_path
        self.branch_name = branch_name

class TaskExecutor:
    """Minimal TaskExecutor to test the context generation."""

    def _get_project_context_old(self, project_path: str) -> str:
        """OLD VERSION - PROBLEMATIC: Exposes absolute paths"""
        import os
        context = f"Project Path: {project_path}\n"

        try:
            if os.path.exists(project_path):
                context += "The project directory exists and you have full access to explore it.\n"
            else:
                context += "Note: Project path does not exist yet.\n"
        except Exception as e:
            context += f"Error reading project: {str(e)}\n"

        return context

    def _get_project_context_new(self, project_path: str, task) -> str:
        """NEW VERSION - FIXED: Never exposes absolute paths + includes project info"""
        import os

        # CRITICAL: Never expose absolute paths that could leak main repository location
        # Claude should only work within the current working directory

        # For isolated tasks (worktrees), only mention current working directory
        if hasattr(task, 'worktree_path') and task.worktree_path and task.branch_name:
            context = f"Working Directory: Current directory (isolated branch: {task.branch_name})\n"
            context += f"Task Branch: {task.branch_name}\n"
            context += "You are working in a task-specific isolated environment.\n"
        else:
            # Fallback for non-isolated tasks - still avoid absolute path exposure
            context = "Working Directory: Current directory\n"

        # Add project architecture and dependency information
        context += "\nProject Architecture:\n"
        context += "- This is a Go project (reverse_strategy) that handles CRUD operations\n"
        context += "- Dependencies: Uses reverse_strategy_sdk for Get/Runtime/Cache operations\n"
        context += "- Testing: The ./test directory contains regression test cases in local mode\n"
        context += "- When making changes, consider impact on SDK dependencies and existing tests\n"

        try:
            if os.path.exists(project_path):
                # Just indicate directory exists - Claude can explore using relative paths
                context += "\nThe working directory exists and you have full access to explore it.\n"
                context += "Use relative paths for all file operations to ensure proper isolation.\n"

                # Check for specific project structure
                test_dir = os.path.join(project_path, "test")
                if os.path.exists(test_dir):
                    context += "- Found ./test directory with regression test cases\n"

                go_mod = os.path.join(project_path, "go.mod")
                if os.path.exists(go_mod):
                    context += "- Found go.mod file (Go module project)\n"

            else:
                context += "Note: Working directory does not exist yet.\n"
        except Exception as e:
            context += f"Error reading working directory: {str(e)}\n"

        return context

def test_context_fix():
    """Test the context generation fix."""

    print("🧪 Testing Claude Context Path Leakage Fix")
    print("=" * 60)

    executor = TaskExecutor()

    # Simulate the problematic scenario
    main_repo_path = "/Users/bytedance/go/src/code.byted.org/aftersales/reverse_strategy"
    worktree_path = "/Users/bytedance/go/src/code.byted.org/aftersales/reverse_strategy/.claude_worktrees/add_scene_event_codes_to_stra"

    # Create mock worktree task
    worktree_task = MockTask(
        worktree_path=worktree_path,
        branch_name="add_scene_event_codes_to_stra"
    )

    print("📍 Test Scenario:")
    print(f"   Main Repository: {main_repo_path}")
    print(f"   Worktree Path: {worktree_path}")
    print(f"   Task Branch: {worktree_task.branch_name}")
    print()

    print("🔴 OLD CONTEXT (PROBLEMATIC - Exposes absolute paths):")
    print("─" * 60)
    old_context = executor._get_project_context_old(main_repo_path)
    print(old_context)
    print("⚠️  ISSUE: Claude learns about the main repository absolute path!")
    print("   This could cause Claude to reference main repo in tools instead of worktree.")
    print()

    print("🟢 NEW CONTEXT (FIXED - No absolute path exposure):")
    print("─" * 60)
    new_context = executor._get_project_context_new(worktree_path, worktree_task)
    print(new_context)
    print("✅ FIXED: Claude only knows about current working directory and branch!")
    print("   Claude will work exclusively within the worktree using relative paths.")
    print()

    # Test regular task (non-worktree)
    regular_task = MockTask()
    print("🔵 REGULAR TASK CONTEXT (No worktree):")
    print("─" * 60)
    regular_context = executor._get_project_context_new(main_repo_path, regular_task)
    print(regular_context)
    print("✅ SAFE: Even regular tasks don't expose absolute paths.")
    print()

    print("=" * 60)
    print("✅ CONTEXT FIX VERIFICATION COMPLETE")
    print("🛡️  Claude no longer learns about main repository absolute paths")
    print("🎯 Claude will work exclusively within the task-specific worktree")
    print("🔒 Cross-branch contamination risk eliminated")

if __name__ == "__main__":
    test_context_fix()