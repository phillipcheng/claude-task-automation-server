"""
Test script for ending criteria extraction and checking functionality.
"""

import asyncio
import sys
from app.services.criteria_analyzer import CriteriaAnalyzer


async def test_criteria_extraction():
    """Test extracting ending criteria from task descriptions."""
    analyzer = CriteriaAnalyzer()

    test_cases = [
        {
            "description": "Add a login button to the homepage that opens a login modal when clicked",
            "expected_clear": True,
        },
        {
            "description": "Make the application better and improve performance",
            "expected_clear": False,
        },
        {
            "description": "Fix all TypeScript type errors in the build so it compiles successfully with zero errors",
            "expected_clear": True,
        },
        {
            "description": "Refactor the code",
            "expected_clear": False,
        },
        {
            "description": "Add unit tests for the UserService class with at least 80% code coverage",
            "expected_clear": True,
        },
    ]

    print("=" * 80)
    print("TESTING ENDING CRITERIA EXTRACTION")
    print("=" * 80)

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n[Test {i}] Task Description:")
        print(f"  {test_case['description']}")
        print(f"  Expected: {'Clear criteria' if test_case['expected_clear'] else 'Unclear criteria'}")

        try:
            criteria, is_clear = await analyzer.extract_ending_criteria(test_case['description'])

            print(f"  Result: {'Clear ✓' if is_clear else 'Unclear ✗'}")
            if criteria:
                print(f"  Extracted Criteria: {criteria}")
            else:
                print(f"  No criteria extracted")

            # Verify expectation
            if is_clear == test_case['expected_clear']:
                print(f"  ✅ PASS")
            else:
                print(f"  ❌ FAIL - Expected {test_case['expected_clear']}, got {is_clear}")

        except Exception as e:
            print(f"  ❌ ERROR: {e}")

    print("\n" + "=" * 80)


async def test_criteria_checking():
    """Test checking if task has met its ending criteria."""
    analyzer = CriteriaAnalyzer()

    print("\n" + "=" * 80)
    print("TESTING ENDING CRITERIA CHECKING")
    print("=" * 80)

    # Test case 1: Criteria met
    print("\n[Test 1] Criteria Met Scenario")
    print("  Task: Add login button to homepage")
    print("  Criteria: Login button is visible on homepage and functional")
    print("  Latest Response: I've added the login button to the homepage. It's now visible in the header and clicking it opens the login modal.")

    is_complete, reasoning = await analyzer.check_task_completion(
        ending_criteria="Login button is visible on homepage and functional",
        task_description="Add login button to homepage",
        conversation_history="",
        latest_response="I've added the login button to the homepage. It's now visible in the header and clicking it opens the login modal."
    )

    print(f"  Result: {'Complete ✓' if is_complete else 'Incomplete ✗'}")
    print(f"  Reasoning: {reasoning}")

    # Test case 2: Criteria not met
    print("\n[Test 2] Criteria Not Met Scenario")
    print("  Task: Fix all type errors")
    print("  Criteria: Build runs successfully with zero type errors")
    print("  Latest Response: I've started fixing the type errors. Fixed 5 so far, but there are still 3 remaining errors.")

    is_complete, reasoning = await analyzer.check_task_completion(
        ending_criteria="Build runs successfully with zero type errors",
        task_description="Fix all type errors in the build",
        conversation_history="",
        latest_response="I've started fixing the type errors. Fixed 5 so far, but there are still 3 remaining errors."
    )

    print(f"  Result: {'Complete ✓' if is_complete else 'Incomplete ✗'}")
    print(f"  Reasoning: {reasoning}")

    print("\n" + "=" * 80)


async def main():
    """Run all tests."""
    print("\n🧪 Starting Ending Criteria System Tests\n")

    try:
        await test_criteria_extraction()
        await test_criteria_checking()

        print("\n✅ All tests completed!")
        print("\nNote: These tests use the actual Claude CLI, so results may vary.")
        print("The system is designed to be conservative - it may mark criteria as")
        print("'unclear' to avoid false positives.\n")

    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Test suite failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
