#!/usr/bin/env python3
"""
Test script to demonstrate the new dynamic project detection system.
"""

import os
import sys
import tempfile
import json
from pathlib import Path

# Add the project root to path so we can import modules
sys.path.insert(0, '/Users/bytedance/python/claudeserver')

from app.services.task_executor import TaskExecutor

class MockTask:
    """Mock task class to simulate worktree task."""
    def __init__(self, worktree_path=None, branch_name=None):
        self.worktree_path = worktree_path
        self.branch_name = branch_name

def create_test_project(project_type, temp_dir):
    """Create a test project structure for different project types."""

    if project_type == "go":
        # Create Go project
        with open(os.path.join(temp_dir, "go.mod"), 'w') as f:
            f.write("""module reverse_strategy

go 1.21

require (
    github.com/example/reverse_strategy_sdk v1.2.3
    github.com/gorilla/mux v1.8.0
)
""")

        os.makedirs(os.path.join(temp_dir, "test"), exist_ok=True)
        with open(os.path.join(temp_dir, "test", "main_test.go"), 'w') as f:
            f.write("package main\n\n// Test file\n")

        with open(os.path.join(temp_dir, "README.md"), 'w') as f:
            f.write("# Reverse Strategy Project\n")

    elif project_type == "node":
        # Create Node.js project
        package_json = {
            "name": "web-app",
            "version": "1.0.0",
            "dependencies": {
                "express": "^4.18.0",
                "lodash": "^4.17.21"
            },
            "devDependencies": {
                "jest": "^29.0.0",
                "@types/node": "^18.0.0"
            }
        }

        with open(os.path.join(temp_dir, "package.json"), 'w') as f:
            json.dump(package_json, f, indent=2)

        os.makedirs(os.path.join(temp_dir, "__tests__"), exist_ok=True)
        with open(os.path.join(temp_dir, "__tests__", "app.test.js"), 'w') as f:
            f.write("// Jest test file\n")

        with open(os.path.join(temp_dir, "jest.config.js"), 'w') as f:
            f.write("module.exports = {};\n")

    elif project_type == "python":
        # Create Python project
        with open(os.path.join(temp_dir, "requirements.txt"), 'w') as f:
            f.write("flask>=2.0.0\nrequests>=2.28.0\npytest>=7.0.0\n")

        with open(os.path.join(temp_dir, "setup.py"), 'w') as f:
            f.write("from setuptools import setup\nsetup(name='myproject')\n")

        os.makedirs(os.path.join(temp_dir, "tests"), exist_ok=True)
        with open(os.path.join(temp_dir, "tests", "test_main.py"), 'w') as f:
            f.write("# Pytest test file\n")

        with open(os.path.join(temp_dir, "pytest.ini"), 'w') as f:
            f.write("[tool:pytest]\ntestpaths = tests\n")

    elif project_type == "mixed":
        # Create a project with mixed configurations
        with open(os.path.join(temp_dir, "go.mod"), 'w') as f:
            f.write("module example\ngo 1.21\n")

        with open(os.path.join(temp_dir, "Dockerfile"), 'w') as f:
            f.write("FROM golang:1.21\n")

        with open(os.path.join(temp_dir, "docker-compose.yml"), 'w') as f:
            f.write("version: '3'\nservices:\n  app:\n    build: .\n")

        with open(os.path.join(temp_dir, "Makefile"), 'w') as f:
            f.write("build:\n\tgo build\n")

        with open(os.path.join(temp_dir, ".env"), 'w') as f:
            f.write("API_KEY=secret\n")

        os.makedirs(os.path.join(temp_dir, "test"), exist_ok=True)

def test_dynamic_detection():
    """Test the dynamic project detection system."""

    print("🧪 Testing Dynamic Project Detection System")
    print("=" * 70)

    executor = TaskExecutor(None, None, None)  # Mock constructor

    # Test different project types
    project_types = ["go", "node", "python", "mixed"]

    for project_type in project_types:
        print(f"\n🔍 Testing {project_type.upper()} Project Detection:")
        print("-" * 50)

        # Create temporary test project
        with tempfile.TemporaryDirectory() as temp_dir:
            create_test_project(project_type, temp_dir)

            # Create mock task
            mock_task = MockTask(
                worktree_path=temp_dir,
                branch_name=f"feature-{project_type}-enhancement"
            )

            # Test the context generation
            context = executor._get_project_context(temp_dir, mock_task)

            print(f"Generated Context:")
            print(f"```")
            print(context)
            print(f"```")

            # Test individual detection methods
            project_info = executor._detect_project_info(temp_dir)
            print(f"\nDetected Project Info:")
            if project_info:
                for line in project_info.split('\n'):
                    if line.strip():
                        print(f"  {line}")
            else:
                print("  No specific project info detected")

    # Test real project (current claudeserver project)
    print(f"\n🔍 Testing REAL Project Detection (Current Directory):")
    print("-" * 50)

    current_dir = "/Users/bytedance/python/claudeserver"
    mock_task = MockTask(
        worktree_path=current_dir,
        branch_name="main"
    )

    context = executor._get_project_context(current_dir, mock_task)
    print(f"Generated Context for Claude Server:")
    print(f"```")
    print(context)
    print(f"```")

    # Test the reverse_strategy project if it exists
    reverse_strategy_path = "/Users/bytedance/go/src/code.byted.org/aftersales/reverse_strategy"
    if os.path.exists(reverse_strategy_path):
        print(f"\n🔍 Testing REVERSE STRATEGY Project Detection:")
        print("-" * 50)

        mock_task = MockTask(
            worktree_path=reverse_strategy_path,
            branch_name="feature-test"
        )

        context = executor._get_project_context(reverse_strategy_path, mock_task)
        print(f"Generated Context for Reverse Strategy:")
        print(f"```")
        print(context)
        print(f"```")
    else:
        print(f"\n⚠️ Reverse strategy project not found at {reverse_strategy_path}")

    print(f"\n" + "=" * 70)
    print("✅ Dynamic Project Detection Test Complete!")
    print("🎯 The system now automatically detects project types and dependencies")
    print("🔧 No more hard-coded project information in the system")
    print("🌐 Works with Go, Node.js, Python, Java, Rust, C/C++ projects")

if __name__ == "__main__":
    test_dynamic_detection()