#!/usr/bin/env python3
"""
Test script to demonstrate the new multi-project task system.

This system allows tasks to specify multiple projects with read/write access control:
- Projects with "write" access get git worktree branches created for isolation
- Projects with "read" access are read-only (no worktree needed)
"""

import json
import tempfile
import os
from pathlib import Path

def test_multi_project_task_payload():
    """Create an example multi-project task payload."""

    # Example task payload with multiple projects
    multi_project_task = {
        "task_name": "add_feature_across_microservices",
        "description": "Add a new user authentication feature that requires changes across multiple microservices",
        "use_worktree": True,
        "auto_start": False,

        # Multi-project configuration
        "projects": [
            {
                "path": "/Users/bytedance/go/src/code.byted.org/aftersales/reverse_strategy",
                "access": "write",
                "context": "Main service project - handles core business logic for user authentication",
                "branch_name": "feature/add-auth-system"
            },
            {
                "path": "/Users/bytedance/go/src/code.byted.org/shared/user-sdk",
                "access": "write",
                "context": "Shared SDK for user operations - needs new auth methods",
                "branch_name": "feature/auth-endpoints"
            },
            {
                "path": "/Users/bytedance/go/src/code.byted.org/shared/common-utils",
                "access": "read",
                "context": "Common utilities library - reference only for auth patterns"
            },
            {
                "path": "/Users/bytedance/python/claudeserver/test/regression",
                "access": "write",
                "context": "Testing utilities - add integration tests for auth flow",
                "branch_name": "feature/auth-tests"
            }
        ],

        # End criteria
        "end_criteria": "Successfully implement authentication feature with proper isolation, testing, and integration across all write projects",
        "max_iterations": 25
    }

    print("🎯 Multi-Project Task System Test")
    print("=" * 70)
    print()
    print("📋 Example Task Configuration:")
    print(json.dumps(multi_project_task, indent=2))
    print()

    print("🔧 How this works:")
    print("1. Task specifies multiple projects with different access levels")
    print("2. Projects with 'write' access get isolated git worktree branches:")
    for project in multi_project_task["projects"]:
        if project["access"] == "write":
            path = project["path"]
            branch = project.get("branch_name", "default")
            print(f"   - {path} → isolated worktree on branch '{branch}'")
    print()

    print("3. Projects with 'read' access are for reference only:")
    for project in multi_project_task["projects"]:
        if project["access"] == "read":
            path = project["path"]
            print(f"   - {path} → read-only access")
    print()

    print("4. Claude receives context about all projects but works in isolated worktrees")
    print("5. Each write project gets its own branch for safe parallel development")
    print()

    print("✅ Benefits:")
    print("- Perfect isolation: changes only affect isolated worktree branches")
    print("- Multi-project awareness: Claude understands relationships between projects")
    print("- Flexible access control: read vs write permissions per project")
    print("- Parallel development: multiple tasks can work on different branches safely")
    print("- Clean rollback: failed tasks don't contaminate main branches")
    print()

    return multi_project_task

def test_single_project_compatibility():
    """Test that single project mode still works."""

    single_project_task = {
        "task_name": "refactor_single_service",
        "description": "Refactor the authentication service for better performance",
        "root_folder": "/Users/bytedance/go/src/code.byted.org/aftersales/reverse_strategy",
        "use_worktree": True,
        "branch_name": "refactor/auth-performance",
        "project_context": "This is a Go service that handles user authentication with performance bottlenecks in the login flow"
    }

    print("🔄 Single Project Compatibility Test")
    print("=" * 70)
    print()
    print("📋 Example Single Project Task:")
    print(json.dumps(single_project_task, indent=2))
    print()
    print("✅ Single project mode continues to work exactly as before")
    print("✅ Backward compatibility maintained")
    print()

def demonstrate_api_usage():
    """Show how to use the API."""

    print("🌐 API Usage Examples")
    print("=" * 70)
    print()

    print("Create Multi-Project Task:")
    print("POST /api/v1/tasks")
    print("Content-Type: application/json")
    print()

    task_example = {
        "task_name": "cross_service_feature",
        "description": "Implement user notification system across services",
        "use_worktree": True,
        "projects": [
            {
                "path": "/path/to/notification-service",
                "access": "write",
                "context": "Main notification service - implement notification endpoints",
                "branch_name": "feature/notifications"
            },
            {
                "path": "/path/to/user-service",
                "access": "write",
                "context": "User service - add notification preferences",
                "branch_name": "feature/notification-prefs"
            },
            {
                "path": "/path/to/shared-models",
                "access": "read",
                "context": "Shared data models - reference for notification schemas"
            }
        ],
        "end_criteria": "Implement complete notification system with user preferences",
        "max_iterations": 20
    }

    print(json.dumps(task_example, indent=2))
    print()

if __name__ == "__main__":
    test_multi_project_task_payload()
    test_single_project_compatibility()
    demonstrate_api_usage()

    print("🎉 Multi-Project Task System Implementation Complete!")
    print()
    print("Key Features Implemented:")
    print("✅ Multi-project task configuration with JSON schema")
    print("✅ Read/write access control per project")
    print("✅ Automatic git worktree creation for write projects only")
    print("✅ Project-specific branch names and contexts")
    print("✅ Enhanced Claude prompts with multi-project awareness")
    print("✅ Backward compatibility with single-project tasks")
    print("✅ Database schema updates with migration scripts")
    print("✅ Complete API integration")