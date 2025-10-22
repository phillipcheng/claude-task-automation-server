# Task Status API - Latest Claude Response

## Overview

The task status API now includes **Claude's latest response** and a flag indicating if the task is **waiting for input**.

This allows you to:
- ✅ See what Claude is currently working on
- ✅ Monitor Claude's questions or requests
- ✅ Know when Claude is paused and waiting
- ✅ Get real-time visibility into task execution

## API Response Fields

### New Fields in TaskStatusResponse

```json
{
  "id": "task-uuid",
  "task_name": "add-login",
  "root_folder": "/Users/me/myapp",
  "branch_name": "task/add-login",
  "status": "running",
  "summary": null,
  "error_message": null,
  "progress": "Task is running - 5 interactions so far",
  "test_summary": {
    "total": 0,
    "passed": 0,
    "failed": 0,
    "pending": 0
  },
  "latest_claude_response": "I've analyzed the project structure...",  // NEW
  "waiting_for_input": false  // NEW
}
```

### Field Descriptions

| Field | Type | Description |
|-------|------|-------------|
| `latest_claude_response` | `string` or `null` | The most recent response from Claude CLI. Contains what Claude said last. |
| `waiting_for_input` | `boolean` | `true` if task status is `PAUSED` (waiting for continuation), `false` otherwise. |

## Usage Examples

### Example 1: Task Running Normally

```bash
curl http://localhost:8000/api/v1/tasks/by-name/add-login/status
```

**Response:**
```json
{
  "status": "running",
  "progress": "Task is running - 3 interactions so far",
  "latest_claude_response": "I'm implementing the login form component. I've created the LoginForm.tsx file with email and password fields. Next, I'll add form validation...",
  "waiting_for_input": false
}
```

**Interpretation:**
- Task is actively running
- Claude is working on the login form
- Not waiting for any input
- You can continue to poll for updates

### Example 2: Task Paused (Waiting for Input)

```bash
curl http://localhost:8000/api/v1/tasks/by-name/fix-bug/status
```

**Response:**
```json
{
  "status": "paused",
  "progress": "Task is paused, waiting for continuation",
  "latest_claude_response": "I've found the bug in the authentication logic. The JWT token validation is missing the expiration check. Should I:\n1. Add token expiration validation\n2. Implement token refresh mechanism\n3. Both of the above\n\nWhich approach would you prefer?",
  "waiting_for_input": true
}
```

**Interpretation:**
- Task is **paused**
- Claude has asked a question about the approach
- `waiting_for_input: true` indicates Claude needs guidance
- The latest response shows the question Claude asked

### Example 3: Task in Testing Phase

```bash
curl http://localhost:8000/api/v1/tasks/by-name/add-api/status
```

**Response:**
```json
{
  "status": "testing",
  "progress": "Running tests: 2/3 passed",
  "latest_claude_response": "Implementation complete. I've created the REST API endpoints with proper error handling and validation. Running tests now...",
  "waiting_for_input": false,
  "test_summary": {
    "total": 3,
    "passed": 2,
    "failed": 1,
    "pending": 0
  }
}
```

**Interpretation:**
- Task is in testing phase
- Claude completed implementation
- Tests are running (2 passed, 1 failed)
- Not waiting for input

### Example 4: Task Completed

```bash
curl http://localhost:8000/api/v1/tasks/by-name/refactor-code/status
```

**Response:**
```json
{
  "status": "completed",
  "progress": "Task completed successfully - all 5 tests passed",
  "summary": "Refactored authentication module to use dependency injection...",
  "latest_claude_response": "Refactoring complete! All tests passing. Summary: Extracted authentication logic into injectable services, added comprehensive unit tests, improved error handling.",
  "waiting_for_input": false
}
```

**Interpretation:**
- Task successfully completed
- All tests passed
- Claude provided final summary
- No further action needed

## Monitoring Task Progress

### Polling Strategy

```python
import time
import requests

def monitor_task(task_name: str):
    """Monitor task progress and show Claude's responses."""
    while True:
        response = requests.get(
            f"http://localhost:8000/api/v1/tasks/by-name/{task_name}/status"
        )
        data = response.json()

        print(f"Status: {data['status']}")
        print(f"Progress: {data['progress']}")

        if data['latest_claude_response']:
            print(f"\nClaude says:")
            print(data['latest_claude_response'][:200])  # First 200 chars

        if data['waiting_for_input']:
            print("\n⚠️  Task is paused - Claude is waiting for input!")
            print("Review the latest response and provide guidance.")
            break

        if data['status'] in ['completed', 'failed']:
            print(f"\n✅ Task {data['status']}")
            break

        time.sleep(10)  # Check every 10 seconds

# Usage
monitor_task("add-login")
```

### Output Example:
```
Status: running
Progress: Task is running - 2 interactions so far

Claude says:
I'm analyzing the existing authentication code. I see you're using JWT tokens...

Status: running
Progress: Task is running - 4 interactions so far

Claude says:
I've implemented the login form with validation. Now adding the API integration...

Status: paused
Progress: Task is paused, waiting for continuation

Claude says:
I've completed the login functionality. Should I also implement:\n1. Password reset\n2. Remember me functionality\n3. OAuth integration\n\nWhat would you like me to add?

⚠️  Task is paused - Claude is waiting for input!
Review the latest response and provide guidance.
```

## When `waiting_for_input` is True

The `waiting_for_input` flag is set to `true` when:

1. **Task Status is PAUSED**
   - Claude has encountered a decision point
   - Needs clarification on requirements
   - Asking for user preference

2. **System Behavior**
   - Task execution is temporarily halted
   - Simulated human will provide continuation prompt (automatic)
   - You can also manually intervene if needed

3. **What to Do**
   - Review the `latest_claude_response` for context
   - Check what Claude is asking about
   - Optionally provide guidance (future feature)
   - System will auto-continue with simulated responses

## Integration with Full Task Details

For more detailed information, use the full task endpoint:

```bash
# Get complete task details including all interactions
curl http://localhost:8000/api/v1/tasks/by-name/add-login
```

**Response includes:**
```json
{
  "id": "...",
  "task_name": "add-login",
  "status": "running",
  "interactions": [
    {
      "id": "...",
      "interaction_type": "user_request",
      "content": "Implement login functionality...",
      "created_at": "2025-01-20T10:00:00"
    },
    {
      "id": "...",
      "interaction_type": "claude_response",
      "content": "I'll implement the login feature...",
      "created_at": "2025-01-20T10:00:15"
    },
    {
      "id": "...",
      "interaction_type": "simulated_human",
      "content": "Continue with the implementation",
      "created_at": "2025-01-20T10:05:00"
    }
  ],
  "test_cases": [...],
  ...
}
```

## Use Cases

### 1. Real-Time Dashboard

Display Claude's current activity:
```javascript
// Frontend polling
setInterval(async () => {
  const status = await fetchTaskStatus(taskName);

  document.getElementById('status').textContent = status.status;
  document.getElementById('progress').textContent = status.progress;

  if (status.latest_claude_response) {
    document.getElementById('claude-response').textContent =
      status.latest_claude_response;
  }

  if (status.waiting_for_input) {
    showPausedAlert();
  }
}, 5000);
```

### 2. CI/CD Integration

Monitor task in deployment pipeline:
```bash
#!/bin/bash
TASK_NAME="deploy-feature"

while true; do
  STATUS=$(curl -s http://localhost:8000/api/v1/tasks/by-name/$TASK_NAME/status | jq -r '.status')

  if [ "$STATUS" == "completed" ]; then
    echo "✅ Deployment successful"
    exit 0
  elif [ "$STATUS" == "failed" ]; then
    ERROR=$(curl -s http://localhost:8000/api/v1/tasks/by-name/$TASK_NAME/status | jq -r '.error_message')
    echo "❌ Deployment failed: $ERROR"
    exit 1
  fi

  sleep 15
done
```

### 3. Notification System

Send alerts when Claude pauses:
```python
def check_and_notify(task_name: str):
    """Send notification if Claude is waiting."""
    status = get_task_status(task_name)

    if status['waiting_for_input']:
        send_slack_message(
            f"🤖 Task '{task_name}' is paused\n"
            f"Claude says: {status['latest_claude_response'][:200]}...\n"
            f"Review and provide guidance."
        )
```

## Task Status Lifecycle

```
CREATE → PENDING → RUNNING → PAUSED? → RUNNING → TESTING → COMPLETED/FAILED
   ↓        ↓         ↓         ↓         ↓          ↓            ↓
waiting: false    false     TRUE      false      false        false
```

## API Endpoints

### Get Task Status by Name
```
GET /api/v1/tasks/by-name/{task_name}/status
```

### Get Task Status by ID (Legacy)
```
GET /api/v1/tasks/{task_id}/status
```

Both endpoints return the same response format with `latest_claude_response` and `waiting_for_input`.

## Summary

The enhanced status API provides:

✅ **Real-time visibility** - See what Claude is doing right now
✅ **Question detection** - Know when Claude has questions
✅ **Pause awareness** - Detect when task is waiting
✅ **Progress tracking** - Monitor implementation progress
✅ **Better UX** - Build responsive dashboards and alerts

Use `latest_claude_response` to display Claude's current work and `waiting_for_input` to detect pauses!
