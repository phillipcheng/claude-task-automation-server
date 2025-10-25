# Ending Criteria & Resource Limits Feature

## Overview

The Claude Task Automation Server now includes an intelligent ending criteria system that:
1. **Automatically extracts success criteria** from task descriptions
2. **Checks task completion** against defined criteria at each iteration
3. **Enforces resource limits** (max iterations and tokens)
4. **Marks tasks as EXHAUSTED** when limits are reached without completion
5. **Allows retry** with increased limits for exhausted tasks

## Key Features

### 1. Automatic Criteria Extraction

When creating a task, if no explicit ending criteria is provided, the system uses LLM to analyze the task description and extract success criteria.

**Example:**
- Task: "Add a login button to the homepage"
- Auto-extracted criteria: "A functional login button is visible on the homepage and clicking it triggers login flow"

If no clear criteria can be extracted, the system warns the user that the task may run until hitting resource limits.

### 2. Intelligent Completion Checking

At each iteration, the system:
- Checks if the defined ending criteria has been met
- Analyzes Claude's latest responses against the criteria
- Requires high confidence (>0.7) before marking as complete
- Falls back to heuristic-based completion detection if no criteria defined

### 3. Resource Limits

**Max Iterations:**
- Default: 20 iterations
- Prevents infinite loops in task execution
- Configurable per task

**Max Output Tokens:**
- Optional limit on cumulative output tokens
- Tracks token usage across all Claude responses
- Useful for cost control

### 4. Task Status: EXHAUSTED

When a task hits max iterations or max tokens without meeting its ending criteria:
- Status changes to `EXHAUSTED`
- Error message shows which limit was reached
- Task can be retried with increased limits

### 5. Retry with Increased Limits

For EXHAUSTED tasks, users can:
- Add more iterations (default: +10)
- Add more token allowance
- Resume execution from where it stopped

## Database Schema

### Tasks Table Updates

```sql
-- Ending criteria configuration (JSON)
end_criteria_config JSON NULL
-- Format: {
--   "criteria": "success description",
--   "max_iterations": 20,
--   "max_tokens": 100000,
--   "warning": "optional warning message"
-- }

-- Token usage tracking
total_tokens_used INT DEFAULT 0
```

## API Usage

### Creating a Task with Ending Criteria

```bash
POST /api/v1/tasks
{
  "task_name": "fix-build-errors",
  "description": "Fix all TypeScript type errors so the build runs successfully",
  "root_folder": "/path/to/project",
  "end_criteria": "Build runs successfully with zero type errors",
  "max_iterations": 30,
  "max_tokens": 50000,
  "auto_start": true
}
```

### Creating a Task (Auto-Extract Criteria)

```bash
POST /api/v1/tasks
{
  "task_name": "add-login-button",
  "description": "Add a login button to the homepage that opens a login modal when clicked",
  "root_folder": "/path/to/project",
  "max_iterations": 20,
  "auto_start": true
}
# System will auto-extract: "Login button is visible on homepage and clicking it opens login modal"
```

### Retrying an EXHAUSTED Task

```bash
POST /api/v1/tasks/by-name/fix-build-errors/retry?additional_iterations=10&additional_tokens=20000
```

Response:
```json
{
  "message": "Task 'fix-build-errors' retrying with increased limits",
  "status": "running",
  "new_limits": {
    "max_iterations": 40,
    "max_tokens": 70000
  }
}
```

## Task Lifecycle with Ending Criteria

```
PENDING
   ↓ (start)
RUNNING
   ↓ (each iteration)
   ├─→ Check ending criteria met? → FINISHED ✅
   ├─→ Max iterations reached? → EXHAUSTED ⚠️
   ├─→ Max tokens reached? → EXHAUSTED ⚠️
   └─→ Continue...
      ↓ (after all iterations)
   TESTING
      ↓
   COMPLETED / FAILED
```

**New Statuses:**
- `FINISHED`: Task completed by meeting ending criteria
- `EXHAUSTED`: Task hit resource limits without completing

## Web UI Updates

### Task Creation Form

New fields added:
- **Ending Criteria** (textarea): Define success criteria or leave empty for auto-extraction
- **Max Iterations** (number): Maximum conversation iterations (default: 20)
- **Max Output Tokens** (number): Optional token limit

### Task Display

Shows:
- 🎯 Success Criteria
- 🔄 Max Iterations (with current progress)
- 🎫 Max Tokens (if set)
- 📊 Tokens Used (cumulative)
- ⚠️ Warning (if criteria unclear)

### EXHAUSTED Tasks

- Orange status badge
- "🔄 Retry with More Limits" button
- Prompts for additional iterations/tokens
- Shows updated limits after retry

## Implementation Details

### CriteriaAnalyzer Service

**Location:** `app/services/criteria_analyzer.py`

**Methods:**
- `extract_ending_criteria(task_description)`: Extracts criteria from description
- `check_task_completion(criteria, conversation, latest_response)`: Checks if criteria met

**Uses:** Claude CLI via StreamingCLIClient for analysis

### Task Executor Updates

**Location:** `app/services/task_executor.py`

**Key Changes:**
- Reads `end_criteria_config` from task
- Tracks cumulative `total_tokens_used`
- Checks criteria completion each iteration
- Marks as EXHAUSTED when limits reached
- Updates task status to FINISHED when criteria met

### API Endpoints

**New Endpoint:**
- `POST /api/v1/tasks/by-name/{task_name}/retry` - Retry exhausted tasks

**Updated Endpoints:**
- `POST /api/v1/tasks` - Accepts `end_criteria`, `max_iterations`, `max_tokens`
- All task endpoints return `end_criteria_config` and `total_tokens_used`

## Testing

Run the test suite:

```bash
python test_ending_criteria.py
```

This tests:
1. Criteria extraction from various task descriptions
2. Completion checking against defined criteria
3. Edge cases (unclear descriptions, partial completion)

**Note:** Tests use actual Claude CLI, results may vary.

## Best Practices

### When to Define Explicit Criteria

✅ **Define criteria when:**
- Task has specific measurable outcomes
- You want precise control over completion
- Success is binary (pass/fail, works/doesn't work)

Examples:
- "All tests pass"
- "Build succeeds with zero errors"
- "API returns 200 status code"
- "File exists at path X with content Y"

❌ **Auto-extract when:**
- Task description is already clear and specific
- Outcome is obvious from description
- You want the system to infer criteria

### Setting Resource Limits

**Max Iterations:**
- Simple tasks: 10-15 iterations
- Medium tasks: 20-30 iterations
- Complex tasks: 30-50 iterations

**Max Tokens:**
- Only set if cost is a concern
- Consider: ~500-2000 tokens per response
- 20 iterations ≈ 10,000-40,000 tokens

### Handling EXHAUSTED Tasks

1. **Review conversation** to understand why limits were hit
2. **Check if close to completion** - maybe just needs a few more iterations
3. **Adjust limits accordingly**:
   - Near completion? Add 5-10 iterations
   - Making progress? Add 20-30 iterations
   - Stuck/confused? Review task description, may need to restart

## Examples

### Example 1: Clear Ending Criteria

```json
{
  "task_name": "fix-login-bug",
  "description": "The login button doesn't redirect to /dashboard after successful login. Fix this bug.",
  "end_criteria": "Login button redirects to /dashboard after successful authentication",
  "max_iterations": 15
}
```

### Example 2: Auto-Extracted Criteria

```json
{
  "task_name": "add-search-feature",
  "description": "Add a search bar to the navbar that filters products in real-time as user types",
  "max_iterations": 25,
  "max_tokens": 30000
}
```
Auto-extracted: "Search bar in navbar filters products in real-time as user types"

### Example 3: Retry Exhausted Task

Task hits max iterations (20) without completing.

```bash
# Check why it's exhausted
curl http://localhost:8000/api/v1/tasks/by-name/add-search-feature/conversation

# Task is close, just needs a few more iterations
curl -X POST "http://localhost:8000/api/v1/tasks/by-name/add-search-feature/retry?additional_iterations=10"
```

## Troubleshooting

### Criteria Not Being Auto-Extracted

**Problem:** System warns "No clear ending criteria found"

**Solutions:**
- Make task description more specific
- Include measurable outcomes in description
- Manually provide ending criteria

### Task Marked FINISHED Prematurely

**Problem:** Task marked as complete before actually done

**Solutions:**
- Make criteria more specific and strict
- Use measurable/testable criteria
- Review conversation to see why system thought it was done

### Task Always Hits Max Iterations

**Problem:** Task consistently reaches EXHAUSTED status

**Solutions:**
- Increase max_iterations
- Check if task is too broad - break into smaller tasks
- Review if criteria is achievable
- Check conversation for repeated errors/confusion

## Future Enhancements

Potential improvements:
- User-adjustable confidence threshold for completion
- Criteria templates for common task types
- Historical analysis of iteration/token usage by task type
- Automatic limit adjustment based on task complexity
- Mid-execution criteria refinement
