# Web UI Guide

The Claude Task Automation Server now includes a modern web interface for managing tasks visually, eliminating the need for command-line API calls.

## Accessing the Web UI

Once the server is running, open your browser and navigate to:

```
http://localhost:8000/
```

The API documentation is still available at:
```
http://localhost:8000/docs
```

## Features

### 1. Create New Task

Fill out the form at the top of the page:

- **Task Name** (required): A unique identifier for the task (e.g., "add-login-feature")
- **Description** (required): What Claude should implement
- **Project Root Folder** (required): Path to your project
- **Branch Name** (optional): Leave empty for auto-generation
- **Use Git Worktree**: Checked by default (recommended for parallel tasks)
- **Auto-start task immediately**: Check to start task right after creation

Click "Create Task" to submit.

### 2. Monitor Active Tasks

The task list shows all tasks with real-time updates (refreshes every 5 seconds):

**Task Information Displayed:**
- Task name and status badge (color-coded)
- Progress information
- Latest message from Claude (truncated to 200 characters)
- Test results (passed/failed/pending counts)
- Error messages (if any)

**Status Colors:**
- **Yellow (Pending)**: Task created but not started
- **Blue (Running)**: Claude is actively working
- **Orange (Paused)**: Temporarily paused (auto-handling)
- **Red (Stopped)**: Manually stopped by user
- **Purple (Testing)**: Running test cases
- **Green (Completed)**: Successfully finished
- **Red (Failed)**: Failed with errors

### 3. Control Tasks

Action buttons appear based on the current status:

- **Start**: Available for pending tasks
- **Stop**: Available for running/paused/testing tasks
- **Resume**: Available for stopped tasks
- **Delete**: Always available (removes task from database)

### 4. Filter Tasks

Use the filter buttons to show specific task types:
- **Show All**: Display all tasks
- **Show Running**: Only running tasks
- **Show Pending**: Only pending tasks
- **Refresh**: Manually refresh the task list

## Example Workflows

### Workflow 1: Create and Auto-Start

1. Fill in task details
2. Check "Auto-start task immediately"
3. Click "Create Task"
4. Watch the task progress in real-time
5. See Claude's responses as they appear
6. Monitor test results when testing phase begins

### Workflow 2: Create, Review, Then Start

1. Fill in task details
2. Leave "Auto-start task immediately" **unchecked**
3. Click "Create Task"
4. Task appears with status "PENDING"
5. Review the task details
6. Click "Start" button when ready
7. Monitor progress as it runs

### Workflow 3: Stop and Resume

1. While task is running, click "Stop"
2. Task status changes to "STOPPED"
3. Perform any needed maintenance
4. Click "Resume" to continue from where it left off

## Technical Details

### Auto-Refresh

The UI automatically refreshes task information every 5 seconds to show:
- Status changes
- Latest Claude responses
- Test progress
- Error messages

### API Integration

The web UI uses the same REST API endpoints:
- `POST /api/v1/tasks` - Create task
- `GET /api/v1/tasks` - List tasks
- `GET /api/v1/tasks/by-name/{task_name}/status` - Get status
- `POST /api/v1/tasks/by-name/{task_name}/start` - Start task
- `POST /api/v1/tasks/by-name/{task_name}/stop` - Stop task
- `POST /api/v1/tasks/by-name/{task_name}/resume` - Resume task
- `DELETE /api/v1/tasks/by-name/{task_name}` - Delete task

### Browser Compatibility

The UI uses modern JavaScript (fetch API, ES6 features) and should work in:
- Chrome/Edge (latest)
- Firefox (latest)
- Safari (latest)

### Mobile Responsive

The interface is fully responsive and works on mobile devices, tablets, and desktops.

## Screenshots

### Creating a Task
The top section contains a form with all task creation options.

### Active Tasks List
Below the form, all tasks are displayed as cards showing:
- Task name and status
- Progress indicator
- Claude's latest response
- Test summary (when applicable)
- Action buttons

### Real-Time Updates
Watch as:
- Status changes from PENDING → RUNNING → TESTING → COMPLETED
- Claude's responses appear in real-time
- Test results update (passed/failed counts)
- Error messages appear if something goes wrong

## Troubleshooting

### UI Not Loading

**Issue**: Browser shows JSON response instead of UI

**Solution**:
1. Ensure you're accessing the root URL: `http://localhost:8000/`
2. Check that `static/index.html` exists
3. Restart the server: `python -m app.main`

### API Errors

**Issue**: "Failed to create task" or other API errors

**Solution**:
1. Check server logs for errors
2. Verify database is running (MySQL)
3. Ensure Claude CLI is accessible
4. Check that the project path exists

### Tasks Not Appearing

**Issue**: Task list shows "No tasks found"

**Solution**:
1. Create a new task using the form
2. Click "Refresh" button
3. Try "Show All" filter
4. Check server logs for database issues

### Auto-Refresh Not Working

**Issue**: Task status not updating automatically

**Solution**:
1. Manually click "Refresh" button
2. Check browser console for JavaScript errors
3. Verify API endpoints are responding
4. Disable browser extensions that might block requests

## Comparison: Web UI vs Command Line

### Web UI Advantages
- Visual task monitoring
- Real-time updates without polling
- No need to remember API endpoints
- Color-coded status indicators
- Easy task lifecycle control
- Test progress visualization

### Command Line Advantages
- Scriptable automation
- Integration with CI/CD pipelines
- Bulk operations
- Remote server management
- Lower resource usage

## Next Steps

After using the web UI:

1. **View Full Details**: Use the API docs at `/docs` to access complete task information including all interactions
2. **Integrate with Scripts**: Use the same API endpoints in automation scripts
3. **Monitor Logs**: Check server logs for detailed execution information
4. **Review Code**: Inspect Claude's generated code in your project directory

## Related Documentation

- [README.md](README.md) - Main documentation
- [QUICKSTART.md](QUICKSTART.md) - 5-minute setup guide
- [TASK_LIFECYCLE.md](TASK_LIFECYCLE.md) - Task lifecycle management
- [API_USAGE_GUIDE.md](API_USAGE_GUIDE.md) - Complete API reference
- [TASK_STATUS_API.md](TASK_STATUS_API.md) - Real-time status monitoring
