# Human-in-the-Loop Guide

This guide shows you how to monitor and control Claude's task execution in real-time, providing your own input when needed.

## Overview

The Human-in-the-Loop feature allows you to:
- **Monitor**: View the full conversation between Claude and the system
- **Inspect**: See exactly what Claude is doing and what responses it's receiving
- **Intervene**: Pause tasks and provide your own instructions
- **Override**: Replace auto-generated responses with your expert judgment
- **Resume**: Continue task execution with your custom input

This transforms fully autonomous execution into **supervised autonomous** mode.

## Prerequisites

1. Server is running: `python -m app.main`
2. Web UI is accessible at: `http://localhost:8000/`
3. Database migration applied:
   ```sql
   ALTER TABLE tasks ADD COLUMN custom_human_input TEXT NULL;
   ```

## Step-by-Step Tutorial

### Step 1: Create a Test Task

1. Open your browser to `http://localhost:8000/`
2. Fill in the create task form:
   - **Task Name**: `test-human-loop`
   - **Description**: `Create a simple greeting function that says hello to a user by name`
   - **Project Root Folder**: `/tmp/test-project` (or your test directory)
   - **Branch Name**: (leave empty)
   - ✅ Check "Use Git Worktree"
   - ✅ Check "Auto-start task immediately"
3. Click "Create Task"

The task will start running immediately.

### Step 2: View the Conversation

1. Find your task in the "Active Tasks" list
2. Click the **"💬 View Conversation"** button
3. A modal window opens showing the conversation

**What you'll see:**
- 🤖 **Blue messages**: Claude's responses
- 🎭 **Yellow messages**: Simulated human responses (auto-generated)
- Each message has a timestamp
- Messages are displayed in chronological order

### Step 3: Monitor Claude's Work

Watch the conversation in real-time:

1. Click the **"🔄 Refresh"** button to see new messages
2. Scroll through to see what Claude has done:
   - Initial task request
   - Claude's analysis and implementation
   - Auto-generated confirmations
   - Claude's follow-up questions

**Example conversation you might see:**
```
👤 Human: Create a simple greeting function...
🤖 Claude: I'll create a greeting function. Let me implement this...
🎭 Simulated: Yes, that looks good. Please continue.
🤖 Claude: I've created greeting.py with a hello() function...
```

### Step 4: Stop the Task

When you want to intervene:

1. Close the conversation modal (click outside or "Close" button)
2. Find the task in the list
3. Click the **"Stop"** button
4. Task status changes to "STOPPED"

### Step 5: Review and Decide to Intervene

1. Click **"💬 View Conversation"** again
2. Read through Claude's latest responses
3. Decide if you want to provide custom guidance

**Example scenario:**
- Claude asks: "Should I add input validation?"
- Auto-response said: "Yes, proceed"
- You want to say: "Add validation but also include error logging"

### Step 6: Edit Custom Input

1. In the conversation modal, click **"✍️ Edit Input"**
2. A text editor appears at the bottom
3. Type your custom message:

**Example custom inputs:**

```
Good progress! For the greeting function, please also:
1. Add type hints
2. Include a docstring with examples
3. Handle empty string inputs gracefully
4. Add a test case in tests/test_greeting.py
```

Or:

```
I reviewed your implementation. Instead of using a simple string,
please return a dictionary with:
{
  "message": "Hello, {name}!",
  "timestamp": <current_time>,
  "user": name
}
```

### Step 7: Send Custom Input

1. After typing your message, click **"Send Input"**
2. You'll see an alert: "Custom input set! The task will use this when resumed."
3. The input editor closes automatically
4. Your message is saved (but not sent to Claude yet)

### Step 8: Resume the Task

1. Close the conversation modal
2. Click the **"Resume"** button on the task
3. Task status changes to "RUNNING"
4. Claude receives YOUR message instead of auto-generated response

### Step 9: Verify Your Input Was Used

1. Wait a few seconds for Claude to process
2. Click **"💬 View Conversation"** again
3. Click **"🔄 Refresh"** to see the latest messages
4. You should see:
   - Your message marked as **👤 Human** (purple background)
   - Claude's response to YOUR instructions
   - Task continuing based on your guidance

### Step 10: Continue Monitoring or Intervening

You can repeat this process as many times as needed:
- Let task run autonomously (auto-responses)
- Stop and inspect when you want
- Provide custom input for critical decisions
- Resume and continue

## Real-World Example Walkthrough

### Scenario: Implementing a User Login System

**Initial Task:**
```
Task: Implement user login with authentication
```

**Conversation Flow:**

```
[Auto-generated conversation]
👤 Human: Implement user login with authentication
🤖 Claude: I'll create a login system. Should I use JWT tokens or sessions?
🎭 Simulated: Yes, proceed with JWT tokens.
🤖 Claude: Implementing JWT-based authentication...
```

**You notice this and want to intervene:**

1. **Stop** the task
2. **View Conversation** - review what Claude is doing
3. **Edit Input** and type:
```
Actually, let's use session-based authentication with Redis for this project.
JWT is overkill for our use case. Please:
1. Use Flask-Session with Redis backend
2. Store sessions for 24 hours
3. Include CSRF protection
4. Add remember-me functionality
```
4. **Send Input**
5. **Resume** task
6. **Refresh Conversation** - see Claude switch to session-based approach

**Result:** Task continues with your architectural decision instead of the auto-generated choice.

## Use Cases

### 1. Quality Assurance
**When:** Task is running well, but you want to review progress

**Action:**
- View conversation periodically
- Verify Claude is on the right track
- Let it continue if everything looks good

### 2. Course Correction
**When:** Claude is going in the wrong direction

**Action:**
- Stop immediately
- Provide specific guidance
- Resume with your corrections

### 3. Complex Decisions
**When:** Auto-responder can't make the right call

**Action:**
- Stop when Claude asks important questions
- Provide expert judgment
- Resume with your decision

### 4. Adding Requirements
**When:** You realize something is missing

**Action:**
- Stop the task
- Add new requirements via custom input
- Resume to incorporate changes

### 5. Debugging
**When:** Task fails or behaves unexpectedly

**Action:**
- View full conversation
- Identify where things went wrong
- Provide corrective instructions

## API Usage (Command Line)

If you prefer command-line instead of web UI:

### View Conversation
```bash
curl http://localhost:8000/api/v1/tasks/by-name/my-task/conversation | jq
```

### Set Custom Input
```bash
curl -X POST http://localhost:8000/api/v1/tasks/by-name/my-task/set-input \
  -H "Content-Type: application/json" \
  -d '{
    "input": "Your custom message to Claude here"
  }'
```

### Complete CLI Workflow
```bash
# 1. Create task
curl -X POST http://localhost:8000/api/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "task_name": "my-task",
    "description": "Task description",
    "root_folder": "/path/to/project",
    "auto_start": true
  }'

# 2. Monitor conversation
watch -n 5 'curl -s http://localhost:8000/api/v1/tasks/by-name/my-task/conversation | jq ".conversation[-5:]"'

# 3. Stop task
curl -X POST http://localhost:8000/api/v1/tasks/by-name/my-task/stop

# 4. Set custom input
curl -X POST http://localhost:8000/api/v1/tasks/by-name/my-task/set-input \
  -H "Content-Type: application/json" \
  -d '{
    "input": "Please add error handling to all database operations"
  }'

# 5. Resume
curl -X POST http://localhost:8000/api/v1/tasks/by-name/my-task/resume

# 6. Verify custom input was used
curl -s http://localhost:8000/api/v1/tasks/by-name/my-task/conversation | jq '.conversation[-3:]'
```

## Tips and Best Practices

### 1. When to Intervene
✅ **Do intervene when:**
- Claude asks important architectural questions
- You notice the approach is suboptimal
- Requirements change mid-task
- Auto-response makes wrong assumptions
- You want to add specific constraints

❌ **Don't intervene when:**
- Task is progressing well
- Claude is handling things correctly
- Auto-responses are appropriate
- Minor stylistic differences

### 2. Writing Effective Custom Input

**Good custom input:**
```
Great progress on the API! For the next steps:
1. Add input validation using Pydantic models
2. Include rate limiting (100 req/min per user)
3. Add API documentation with example requests
4. Create integration tests covering happy path and errors
```

**Less effective:**
```
Make it better
```

**Why?** Specific, actionable instructions help Claude understand exactly what you want.

### 3. Monitoring Frequency

- **High-stakes tasks**: Check every 2-3 interactions
- **Routine tasks**: Check once or twice total
- **Experimental tasks**: Monitor continuously

### 4. Combining with Stop/Resume

Strategy:
1. Let task run with auto-responses (autonomous mode)
2. Stop at checkpoints (e.g., after major milestones)
3. Review conversation
4. Provide input if needed
5. Resume

This balances automation with control.

## Troubleshooting

### Issue: Can't see conversation
**Solution:**
- Ensure task has started (not pending)
- Refresh the page
- Check browser console for errors

### Issue: Custom input not being used
**Solution:**
- Verify you clicked "Send Input"
- Check alert confirmed "Custom input set"
- Ensure you clicked "Resume" after setting input
- Wait a few seconds, then refresh conversation

### Issue: Task stops after custom input
**Solution:**
- Check task status (might be completed)
- Review conversation for errors
- Verify your input was clear and actionable

### Issue: Messages not updating
**Solution:**
- Click "Refresh" button in modal
- Close and reopen conversation modal
- Check server is still running

## Architecture

### How It Works

1. **Normal Flow (Auto-Response):**
```
Claude responds → System pauses → Generates auto-response → Sends to Claude
```

2. **Human-in-the-Loop Flow:**
```
Claude responds → User stops task → User views conversation
→ User edits input → User sends custom input → User resumes task
→ System uses custom input instead of auto-response → Sends to Claude
```

### Data Flow

```
Web UI → API Endpoint → Database (custom_human_input column)
→ Task Executor checks for custom input → Uses custom if available
→ Otherwise generates auto-response → Sends to Claude
→ Saves interaction to database → Web UI refreshes conversation
```

### Message Types

- **`user_request`**: Initial task or user's custom input (purple)
- **`claude_response`**: Claude's responses (blue)
- **`simulated_human`**: Auto-generated responses (yellow)

## Next Steps

Now that you understand human-in-the-loop:

1. **Try it out** with the step-by-step tutorial above
2. **Experiment** with different types of tasks
3. **Find your workflow** - balance between autonomous and supervised
4. **Share feedback** - what works, what could be better

## Related Documentation

- [WEB_UI_GUIDE.md](WEB_UI_GUIDE.md) - Complete web interface guide
- [TASK_LIFECYCLE.md](TASK_LIFECYCLE.md) - Understanding task states
- [INTELLIGENT_AUTO_ANSWER.md](INTELLIGENT_AUTO_ANSWER.md) - How auto-responses work
- [API_USAGE_GUIDE.md](API_USAGE_GUIDE.md) - API reference
