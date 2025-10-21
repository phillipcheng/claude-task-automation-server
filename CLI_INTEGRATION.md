# Claude CLI Integration

This document explains how the system integrates with the Claude Code command-line interface.

## Why CLI Instead of API?

The system uses the **Claude Code CLI** instead of the Anthropic API because:

1. **No API Key Required**: You already have a Claude subscription
2. **Uses Your Subscription**: Leverages your existing Claude Code access
3. **Simpler Setup**: No need to manage API keys
4. **Same Capabilities**: Full access to Claude's coding abilities
5. **Local Integration**: Works directly with your local environment

## How It Works

### Architecture

```
┌─────────────────┐
│  HTTP API       │
│  (FastAPI)      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Task Executor   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Claude CLI      │
│ Client          │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Claude CLI      │
│ (subprocess)    │
└─────────────────┘
         │
         ▼
    Claude AI
```

### ClaudeCLIClient

The `ClaudeCLIClient` class (`app/services/claude_cli_client.py`) handles all interactions with the Claude CLI:

#### Key Methods

1. **send_message(message, project_path)**
   - Sends a message to Claude CLI
   - Runs in the project directory context
   - Returns Claude's response

2. **generate_code(task_description, project_context, project_path)**
   - Formats the task as a code generation request
   - Sends to Claude with project context
   - Returns implementation response

3. **generate_test_cases(task_description, implementation_summary, project_path)**
   - Asks Claude to generate pytest tests
   - Context-aware based on implementation
   - Returns test code

4. **get_project_context(project_path)**
   - Asks Claude to analyze the project structure
   - Provides context for task execution
   - Fallback to basic directory listing

### Subprocess Execution

The CLI client uses Python's `subprocess` module to run Claude:

```python
result = subprocess.run(
    ["claude", message],
    capture_output=True,
    text=True,
    timeout=300,
    cwd=project_path,
)
```

**Parameters:**
- Command: `claude` (configurable via `CLAUDE_CLI_COMMAND`)
- Message: User's request to Claude
- Working Directory: Project path for context
- Timeout: 5 minutes (configurable)

### Conversation Flow

Unlike the API which maintains conversation history, CLI interactions are more stateless:

1. **Initial Request**: Send task description with full context
2. **Claude Works**: Claude executes the task
3. **Simulated Continuation**: If needed, send encouragement prompts
4. **Test Generation**: Separate request to generate tests

The system handles "conversation" by:
- Storing all interactions in the database
- Providing full context in each request
- Using simulated human prompts to encourage continuation

## Configuration

### Environment Variables

```bash
# .env file
CLAUDE_CLI_COMMAND=claude  # Default, or set custom path
```

### Custom CLI Path

If Claude is installed in a non-standard location:

```bash
# In .env
CLAUDE_CLI_COMMAND=/usr/local/bin/claude
```

Or set at runtime:

```python
executor = TaskExecutor(cli_command="/custom/path/to/claude")
```

## Error Handling

### CLI Not Found

```python
try:
    result = subprocess.run([self.cli_command, "--version"], ...)
except FileNotFoundError:
    raise Exception("Claude CLI command not found")
```

### CLI Errors

```python
if result.returncode != 0:
    error_msg = result.stderr or "Unknown error"
    raise Exception(f"Claude CLI error: {error_msg}")
```

### Timeouts

```python
try:
    result = subprocess.run(..., timeout=300)
except subprocess.TimeoutExpired:
    raise Exception("Claude CLI request timed out")
```

## Advantages of CLI Approach

### For Users

1. **No API Key Management**: Use your existing subscription
2. **Familiar Tool**: Same Claude you use in terminal
3. **Consistent Experience**: Same behavior as interactive use
4. **Subscription Benefits**: Unlimited usage with subscription

### For System

1. **Simpler Authentication**: No key storage or rotation
2. **Better Context**: CLI works in project directory
3. **File Operations**: Claude can directly read/write files
4. **Tool Access**: Full access to Claude's file tools

## Limitations

### vs. API Approach

1. **No Streaming**: Full response only (no token streaming)
2. **Less Control**: Can't customize system prompts as easily
3. **Context Continuity**: Each call is more independent
4. **Output Parsing**: Need to parse text output

### Workarounds

1. **Context Continuity**: Store and replay interactions
2. **Output Parsing**: Use regex and pattern matching
3. **System Prompts**: Include instructions in user message
4. **Progress**: Check database for interaction history

## Testing

### Verify CLI Available

```bash
# Check Claude CLI is installed
claude --version

# Test basic command
claude "Hello, please respond with 'OK'"
```

### Test Client

```python
from app.services.claude_cli_client import ClaudeCLIClient

client = ClaudeCLIClient()
response = await client.send_message(
    "Create a simple hello world function",
    project_path="/tmp/test"
)
print(response)
```

## Debugging

### Enable Verbose Logging

```python
# In task_executor.py
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Check CLI Output

```bash
# Test CLI directly
cd /path/to/project
claude "Analyze this project structure"
```

### Inspect Database

```python
# Check stored interactions
from app.database import SessionLocal
from app.models import ClaudeInteraction

db = SessionLocal()
interactions = db.query(ClaudeInteraction).all()
for i in interactions:
    print(f"{i.interaction_type}: {i.content[:100]}")
```

## Future Enhancements

### Potential Improvements

1. **Session Persistence**: Maintain CLI session across calls
2. **Streaming Support**: Parse output as it arrives
3. **Better Context**: Include recent git history
4. **Tool Observability**: Log all file operations
5. **Multi-Model**: Support different Claude models via CLI flags

### Advanced Features

1. **Interactive Mode**: Allow human intervention mid-task
2. **Code Review**: Have Claude review its own code
3. **Iterative Refinement**: Multiple passes until tests pass
4. **Parallel Tasks**: Run multiple independent tasks

## Comparison: API vs CLI

| Feature | API Approach | CLI Approach |
|---------|-------------|--------------|
| Authentication | API Key required | Uses subscription |
| Setup | Complex | Simple |
| Streaming | Yes | No |
| File Access | Via API | Direct |
| Context | Manual | Automatic |
| Cost | Pay-per-token | Subscription |
| Rate Limits | Yes | Subscription limits |
| Customization | High | Medium |

## Conclusion

The CLI-based approach provides a **simpler, more integrated** way to use Claude for task automation. It leverages your existing subscription and provides direct file access, making it ideal for local development automation.

The trade-offs (no streaming, less control) are acceptable for this use case where we're automating complete tasks rather than building a conversational interface.
