#!/bin/bash
# Simple Task Monitor - Bash version
# Usage: ./monitor_task.sh <task_name> <description> <root_folder>

set -e

API_BASE="http://localhost:8000/api/v1"

# Check arguments
if [ $# -lt 3 ]; then
    echo "Usage: $0 <task_name> <description> <root_folder>"
    echo ""
    echo "Example:"
    echo "  $0 add-login 'Implement login feature' /Users/me/myapp"
    exit 1
fi

TASK_NAME="$1"
DESCRIPTION="$2"
ROOT_FOLDER="$3"

# Create task
echo "📝 Creating task: $TASK_NAME"
echo "   Description: $DESCRIPTION"
echo "   Project: $ROOT_FOLDER"
echo ""

CREATE_RESPONSE=$(curl -s -X POST "$API_BASE/tasks" \
    -H "Content-Type: application/json" \
    -d "{
        \"task_name\": \"$TASK_NAME\",
        \"description\": \"$DESCRIPTION\",
        \"root_folder\": \"$ROOT_FOLDER\"
    }")

# Check if task created successfully
if echo "$CREATE_RESPONSE" | jq -e '.id' > /dev/null 2>&1; then
    echo "✅ Task created!"
    echo ""
else
    echo "❌ Error creating task:"
    echo "$CREATE_RESPONSE" | jq '.'
    exit 1
fi

# Monitor task
echo "👀 Monitoring task: $TASK_NAME"
echo "   Checking every 10 seconds"
echo ""
echo "================================================================================"

ITERATION=0

while true; do
    ((ITERATION++))

    # Get task status
    STATUS_RESPONSE=$(curl -s "$API_BASE/tasks/by-name/$TASK_NAME/status")

    # Extract fields using jq
    TASK_STATUS=$(echo "$STATUS_RESPONSE" | jq -r '.status')
    PROGRESS=$(echo "$STATUS_RESPONSE" | jq -r '.progress')
    WAITING=$(echo "$STATUS_RESPONSE" | jq -r '.waiting_for_input')
    CLAUDE_RESPONSE=$(echo "$STATUS_RESPONSE" | jq -r '.latest_claude_response // ""')

    # Print status update
    echo ""
    echo "[$ITERATION] Status: $TASK_STATUS"
    echo "    Progress: $PROGRESS"

    # Show Claude's latest response (truncated)
    if [ -n "$CLAUDE_RESPONSE" ] && [ "$CLAUDE_RESPONSE" != "null" ]; then
        TRUNCATED=$(echo "$CLAUDE_RESPONSE" | cut -c1-150)
        echo "    Claude: $TRUNCATED..."
    fi

    # Show if waiting
    if [ "$WAITING" == "true" ]; then
        echo "    ⏸️  PAUSED - Waiting for input"
    fi

    # Show test status
    TOTAL_TESTS=$(echo "$STATUS_RESPONSE" | jq -r '.test_summary.total // 0')
    if [ "$TOTAL_TESTS" -gt 0 ]; then
        PASSED_TESTS=$(echo "$STATUS_RESPONSE" | jq -r '.test_summary.passed')
        echo "    Tests: $PASSED_TESTS/$TOTAL_TESTS passed"
    fi

    # Check if finished
    if [ "$TASK_STATUS" == "completed" ] || [ "$TASK_STATUS" == "failed" ]; then
        echo ""
        echo "================================================================================"

        if [ "$TASK_STATUS" == "completed" ]; then
            echo "✅ Task COMPLETED!"
            SUMMARY=$(echo "$STATUS_RESPONSE" | jq -r '.summary // ""')
            if [ -n "$SUMMARY" ] && [ "$SUMMARY" != "null" ]; then
                echo ""
                echo "Summary:"
                echo "$SUMMARY"
            fi
            exit 0
        else
            echo "❌ Task FAILED!"
            ERROR=$(echo "$STATUS_RESPONSE" | jq -r '.error_message // ""')
            if [ -n "$ERROR" ] && [ "$ERROR" != "null" ]; then
                echo ""
                echo "Error:"
                echo "$ERROR"
            fi
            exit 1
        fi
    fi

    # Wait before next poll
    sleep 10
done
