import subprocess
import os
import tempfile
from typing import Tuple, List
from pathlib import Path


class TestRunner:
    """Runs pytest test cases and returns results."""

    @staticmethod
    async def run_test(test_code: str, project_path: str) -> Tuple[bool, str]:
        """
        Run a single test case.

        Args:
            test_code: The pytest test code
            project_path: Path to the project

        Returns:
            Tuple of (success: bool, output: str)
        """
        try:
            # Create temporary test file
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix="_test.py",
                delete=False,
                dir=project_path if os.path.exists(project_path) else None,
            ) as f:
                f.write(test_code)
                test_file = f.name

            try:
                # Run pytest on the test file
                result = subprocess.run(
                    ["pytest", test_file, "-v", "--tb=short"],
                    capture_output=True,
                    text=True,
                    timeout=60,
                    cwd=project_path if os.path.exists(project_path) else None,
                )

                output = f"STDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}"
                success = result.returncode == 0

                return success, output

            finally:
                # Clean up temporary file
                if os.path.exists(test_file):
                    os.unlink(test_file)

        except subprocess.TimeoutExpired:
            return False, "Test execution timed out after 60 seconds"
        except Exception as e:
            return False, f"Error running test: {str(e)}"

    @staticmethod
    async def run_regression_tests(project_path: str) -> Tuple[bool, str, List[dict]]:
        """
        Run regression tests for the project.

        Args:
            project_path: Path to the project

        Returns:
            Tuple of (all_passed: bool, output: str, test_results: List[dict])
        """
        try:
            # Look for tests directory
            tests_dir = os.path.join(project_path, "tests")
            if not os.path.exists(tests_dir):
                return True, "No regression tests found", []

            # Run all tests in the tests directory
            result = subprocess.run(
                ["pytest", tests_dir, "-v", "--tb=short", "--json-report", "--json-report-file=/tmp/test_report.json"],
                capture_output=True,
                text=True,
                timeout=300,
                cwd=project_path,
            )

            output = f"STDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}"
            all_passed = result.returncode == 0

            # Parse test results (simplified)
            test_results = []
            if "passed" in result.stdout.lower():
                test_results.append({"status": "passed", "output": result.stdout})
            elif "failed" in result.stdout.lower():
                test_results.append({"status": "failed", "output": result.stdout})

            return all_passed, output, test_results

        except subprocess.TimeoutExpired:
            return False, "Regression tests timed out after 300 seconds", []
        except Exception as e:
            return False, f"Error running regression tests: {str(e)}", []

    @staticmethod
    async def validate_test_code(test_code: str) -> Tuple[bool, str]:
        """
        Validate that test code is syntactically correct.

        Args:
            test_code: The test code to validate

        Returns:
            Tuple of (valid: bool, error_message: str)
        """
        try:
            compile(test_code, "<string>", "exec")
            return True, ""
        except SyntaxError as e:
            return False, f"Syntax error in test code: {str(e)}"
        except Exception as e:
            return False, f"Error validating test code: {str(e)}"
