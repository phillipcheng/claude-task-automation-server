from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.schemas import (
    SessionCreate,
    SessionResponse,
    TaskCreate,
    TaskResponse,
    TaskStatusResponse,
    PromptCreate,
    PromptUpdate,
    PromptResponse,
)
from app.models import (
    Session as DBSession,
    Task,
    TaskStatus,
    TestCaseStatus,
    InteractionType,
)
from app.services.task_executor import TaskExecutor
from app.services.git_worktree import GitWorktreeManager
import os
import subprocess

router = APIRouter()

# Default session management
DEFAULT_SESSION_NAME = "default"
DEFAULT_PROJECT_PATH = os.getenv("DEFAULT_PROJECT_PATH", "/tmp/claude_projects")


def get_or_create_default_session(db: Session) -> DBSession:
    """Get or create the default session."""
    # Try to find existing default session
    db_session = db.query(DBSession).filter(
        DBSession.project_path == DEFAULT_PROJECT_PATH
    ).first()

    if not db_session:
        # Create default session
        db_session = DBSession(project_path=DEFAULT_PROJECT_PATH)
        db.add(db_session)
        db.commit()
        db.refresh(db_session)

    return db_session


def get_or_create_session_for_project(db: Session, project_path: str) -> DBSession:
    """Get or create a session for a specific project path."""
    db_session = db.query(DBSession).filter(
        DBSession.project_path == project_path
    ).first()

    if not db_session:
        db_session = DBSession(project_path=project_path)
        db.add(db_session)
        db.commit()
        db.refresh(db_session)

    return db_session


def get_git_info(root_folder: str) -> tuple[Optional[str], Optional[str]]:
    """
    Get git branch and repository URL from a folder.

    Returns: (branch_name, git_repo_url)
    """
    if not root_folder or not os.path.exists(root_folder):
        return None, None

    try:
        # Get current branch
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=root_folder,
            capture_output=True,
            text=True,
            timeout=5
        )
        branch_name = result.stdout.strip() if result.returncode == 0 else None

        # Get remote URL
        result = subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],
            cwd=root_folder,
            capture_output=True,
            text=True,
            timeout=5
        )
        git_repo = result.stdout.strip() if result.returncode == 0 else None

        return branch_name, git_repo
    except Exception:
        return None, None


@router.post("/tasks", response_model=TaskResponse)
async def create_task(
    task_data: TaskCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Create a new task by task name and start execution asynchronously.

    Supports:
    - root_folder: Project root directory
    - branch_name: Git branch to work on (optional, auto-detected if not provided)
    - project_path: Legacy support, use root_folder instead
    """
    # Check if task name already exists
    existing_task = db.query(Task).filter(Task.task_name == task_data.task_name).first()
    if existing_task:
        raise HTTPException(
            status_code=400,
            detail=f"Task with name '{task_data.task_name}' already exists. Use a different name or query the existing task."
        )

    # Determine root folder (root_folder takes precedence over project_path)
    root_folder = task_data.root_folder or task_data.project_path

    # Get or create session based on root_folder
    if root_folder:
        db_session = get_or_create_session_for_project(db, root_folder)
    else:
        db_session = get_or_create_default_session(db)
        root_folder = DEFAULT_PROJECT_PATH

    # Auto-detect git info if not provided
    branch_name = task_data.branch_name
    base_branch = task_data.base_branch
    git_repo = None
    worktree_path = None
    actual_working_dir = root_folder

    if root_folder and os.path.exists(root_folder):
        detected_branch, detected_repo = get_git_info(root_folder)
        git_repo = detected_repo

        # If base_branch not provided, use detected current branch
        if not base_branch:
            base_branch = detected_branch

        # For git repos, validate branch requirements
        if git_repo:
            # Check if other tasks exist on same root_folder
            existing_tasks = db.query(Task).filter(
                Task.root_folder == root_folder,
                Task.status.in_([TaskStatus.PENDING, TaskStatus.RUNNING, TaskStatus.PAUSED])
            ).all()

            # If branch_name not specified, auto-generate unique branch
            if not branch_name:
                # Create unique branch name for this task
                branch_name = f"task/{task_data.task_name.replace('/', '_').replace(' ', '_')}"

            # Validate branch uniqueness if multiple tasks on same project
            if existing_tasks:
                # Check if branch is already used by another active task
                used_branches = [t.branch_name for t in existing_tasks if t.branch_name]
                if branch_name in used_branches:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Branch '{branch_name}' is already being used by another active task on this project. "
                               f"Please specify a different branch_name or wait for the other task to complete."
                    )

                # Enforce worktree usage for parallel tasks
                if not task_data.use_worktree:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Multiple tasks detected on project '{root_folder}'. "
                               f"You must use worktrees (use_worktree=true) for parallel task execution."
                    )

        # Use git worktree if enabled and it's a git repo
        if task_data.use_worktree and git_repo:
            worktree_manager = GitWorktreeManager(root_folder)

            # Check if git worktree is supported
            if GitWorktreeManager.is_worktree_supported(root_folder):
                success, wt_path, message = worktree_manager.create_worktree(
                    task_data.task_name,
                    branch_name,
                    base_branch
                )

                if success:
                    worktree_path = wt_path
                    actual_working_dir = wt_path
                else:
                    # Worktree creation failed - this is critical for parallel tasks
                    raise HTTPException(
                        status_code=500,
                        detail=f"Failed to create worktree: {message}. Cannot proceed with task creation."
                    )
            else:
                # Git worktree not supported
                raise HTTPException(
                    status_code=400,
                    detail="Git worktree is not supported (requires git 2.5+). Please upgrade git or disable worktree usage."
                )
        elif not branch_name:
            # Not using worktree, fall back to detected branch
            branch_name = detected_branch

    # Create task
    db_task = Task(
        task_name=task_data.task_name,
        session_id=db_session.id,
        description=task_data.description,
        root_folder=root_folder,
        branch_name=branch_name,
        base_branch=base_branch,
        git_repo=git_repo,
        worktree_path=worktree_path,
        status=TaskStatus.PENDING,
    )
    db.add(db_task)
    db.commit()
    db.refresh(db_task)

    # Start task execution in background only if auto_start is True
    if task_data.auto_start:
        executor = TaskExecutor()
        background_tasks.add_task(executor.execute_task, db_task.id)

    return db_task


@router.get("/tasks/by-name/{task_name}", response_model=TaskResponse)
async def get_task_by_name(task_name: str, db: Session = Depends(get_db)):
    """Get full task details by task name."""
    task = db.query(Task).filter(Task.task_name == task_name).first()
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_name}' not found")
    return task


@router.get("/tasks/by-name/{task_name}/status", response_model=TaskStatusResponse)
async def get_task_status_by_name(task_name: str, db: Session = Depends(get_db)):
    """Get task status by task name."""
    task = db.query(Task).filter(Task.task_name == task_name).first()
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_name}' not found")

    # Calculate test summary
    total_tests = len(task.test_cases)
    passed_tests = len([tc for tc in task.test_cases if tc.status == TestCaseStatus.PASSED])
    failed_tests = len([tc for tc in task.test_cases if tc.status == TestCaseStatus.FAILED])
    pending_tests = len([tc for tc in task.test_cases if tc.status == TestCaseStatus.PENDING])

    # Get latest Claude response
    latest_claude_response = None
    claude_responses = [
        i for i in task.interactions
        if i.interaction_type == InteractionType.CLAUDE_RESPONSE
    ]
    if claude_responses:
        latest_claude_response = claude_responses[-1].content

    # Check if waiting for input (PAUSED status means waiting)
    waiting_for_input = task.status == TaskStatus.PAUSED

    # Generate progress message
    progress_messages = {
        TaskStatus.PENDING: "Task created, waiting to be started",
        TaskStatus.RUNNING: f"Task is running - {len(task.interactions)} interactions so far",
        TaskStatus.PAUSED: "Task is paused, waiting for continuation",
        TaskStatus.STOPPED: "Task has been stopped",
        TaskStatus.TESTING: f"Running tests: {passed_tests}/{total_tests} passed",
        TaskStatus.COMPLETED: f"Task completed successfully - all {total_tests} tests passed",
        TaskStatus.FAILED: f"Task failed - {failed_tests} tests failed",
    }

    return TaskStatusResponse(
        id=task.id,
        task_name=task.task_name,
        root_folder=task.root_folder,
        branch_name=task.branch_name,
        base_branch=task.base_branch,
        status=task.status,
        summary=task.summary,
        error_message=task.error_message,
        progress=progress_messages.get(task.status, "Unknown status"),
        test_summary={
            "total": total_tests,
            "passed": passed_tests,
            "failed": failed_tests,
            "pending": pending_tests,
        },
        latest_claude_response=latest_claude_response,
        waiting_for_input=waiting_for_input,
    )


@router.get("/tasks", response_model=List[TaskResponse])
async def list_all_tasks(
    status: Optional[str] = None,
    root_folder: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    List all tasks, optionally filtered by status and/or root_folder.

    Args:
        status: Filter by task status (pending, running, paused, testing, completed, failed)
        root_folder: Filter by project root folder path
        limit: Maximum number of tasks to return (default: 100)
    """
    query = db.query(Task)

    if status:
        try:
            task_status = TaskStatus(status)
            query = query.filter(Task.status == task_status)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status. Valid values: {[s.value for s in TaskStatus]}"
            )

    if root_folder:
        query = query.filter(Task.root_folder == root_folder)

    tasks = query.order_by(Task.created_at.desc()).limit(limit).all()
    return tasks


@router.post("/tasks/by-name/{task_name}/start")
async def start_task(
    task_name: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Start a pending task."""
    task = db.query(Task).filter(Task.task_name == task_name).first()
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_name}' not found")

    if task.status != TaskStatus.PENDING:
        raise HTTPException(
            status_code=400,
            detail=f"Task can only be started from PENDING status. Current status: {task.status}"
        )

    # Start task execution in background
    executor = TaskExecutor()
    background_tasks.add_task(executor.execute_task, task.id)

    return {"message": f"Task '{task_name}' started", "status": "running"}


@router.post("/tasks/by-name/{task_name}/stop")
async def stop_task(task_name: str, db: Session = Depends(get_db)):
    """Stop a running or paused task."""
    task = db.query(Task).filter(Task.task_name == task_name).first()
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_name}' not found")

    if task.status not in [TaskStatus.RUNNING, TaskStatus.PAUSED, TaskStatus.TESTING]:
        raise HTTPException(
            status_code=400,
            detail=f"Task can only be stopped from RUNNING/PAUSED/TESTING status. Current status: {task.status}"
        )

    # Update status to STOPPED
    task.status = TaskStatus.STOPPED
    db.commit()

    return {"message": f"Task '{task_name}' stopped", "status": "stopped"}


@router.post("/tasks/by-name/{task_name}/resume")
async def resume_task(
    task_name: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Resume a stopped task."""
    task = db.query(Task).filter(Task.task_name == task_name).first()
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_name}' not found")

    if task.status != TaskStatus.STOPPED:
        raise HTTPException(
            status_code=400,
            detail=f"Task can only be resumed from STOPPED status. Current status: {task.status}"
        )

    # Resume task execution in background
    executor = TaskExecutor()
    background_tasks.add_task(executor.execute_task, task.id)

    return {"message": f"Task '{task_name}' resumed", "status": "running"}


@router.get("/tasks/by-name/{task_name}/conversation")
async def get_task_conversation(task_name: str, db: Session = Depends(get_db)):
    """Get the full conversation history for a task (all interactions)."""
    task = db.query(Task).filter(Task.task_name == task_name).first()
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_name}' not found")

    # Get all interactions ordered by creation time
    interactions = sorted(task.interactions, key=lambda x: x.created_at)

    return {
        "task_name": task.task_name,
        "status": task.status,
        "conversation": [
            {
                "id": interaction.id,
                "type": interaction.interaction_type.value,
                "content": interaction.content,
                "timestamp": interaction.created_at.isoformat()
            }
            for interaction in interactions
        ]
    }


@router.post("/tasks/by-name/{task_name}/set-input")
async def set_custom_human_input(
    task_name: str,
    request: dict,
    db: Session = Depends(get_db)
):
    """
    Set custom human input for the next interaction.
    The task will use this instead of auto-generated response when resumed.
    """
    task = db.query(Task).filter(Task.task_name == task_name).first()
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_name}' not found")

    if "input" not in request:
        raise HTTPException(status_code=400, detail="Missing 'input' field in request body")

    # Store the custom input
    task.custom_human_input = request["input"]
    db.commit()

    return {
        "message": "Custom input set successfully",
        "task_name": task_name,
        "input_preview": request["input"][:100] + "..." if len(request["input"]) > 100 else request["input"]
    }


@router.get("/browse-directories")
async def browse_directories(path: str = None):
    """Browse directories on the server filesystem."""
    import os
    from pathlib import Path

    # Start from home directory if no path provided
    if not path:
        path = str(Path.home())

    # Security: ensure path exists and is a directory
    if not os.path.exists(path) or not os.path.isdir(path):
        raise HTTPException(status_code=400, detail="Invalid directory path")

    try:
        # Get parent directory
        parent = str(Path(path).parent) if path != "/" else None

        # List directories only (not files)
        items = []
        for item in sorted(os.listdir(path)):
            item_path = os.path.join(path, item)
            if os.path.isdir(item_path) and not item.startswith('.'):
                try:
                    # Check if readable
                    os.listdir(item_path)
                    items.append({
                        "name": item,
                        "path": item_path,
                        "accessible": True
                    })
                except PermissionError:
                    items.append({
                        "name": item,
                        "path": item_path,
                        "accessible": False
                    })

        return {
            "current_path": path,
            "parent_path": parent,
            "directories": items
        }
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/tasks/by-name/{task_name}")
async def delete_task_by_name(task_name: str, cleanup_worktree: bool = True, db: Session = Depends(get_db)):
    """Delete a task by name and optionally cleanup its worktree."""
    task = db.query(Task).filter(Task.task_name == task_name).first()
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_name}' not found")

    worktree_cleaned = False
    worktree_message = None

    # Cleanup worktree if it exists
    if cleanup_worktree and task.worktree_path and task.root_folder:
        worktree_manager = GitWorktreeManager(task.root_folder)
        success, message = worktree_manager.remove_worktree(task_name, force=True)
        worktree_cleaned = success
        worktree_message = message

    db.delete(task)
    db.commit()

    response = {"message": f"Task '{task_name}' deleted successfully"}
    if worktree_cleaned:
        response["worktree_cleanup"] = worktree_message

    return response


@router.get("/git-branches")
async def list_git_branches(path: str, branch_type: str = "local"):
    """
    List git branches from a repository.

    Args:
        path: Path to the git repository
        branch_type: Type of branches to list - "local", "remote", or "all" (default: "local")

    Returns:
        List of branch names and current branch
    """
    if not path or not os.path.exists(path):
        raise HTTPException(status_code=400, detail="Invalid repository path")

    if not os.path.isdir(path):
        raise HTTPException(status_code=400, detail="Path is not a directory")

    # Check if it's a git repository
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=path,
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode != 0:
            raise HTTPException(status_code=400, detail="Not a git repository")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Not a git repository: {str(e)}")

    try:
        # Get current branch
        current_result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=path,
            capture_output=True,
            text=True,
            timeout=5
        )
        current_branch = current_result.stdout.strip() if current_result.returncode == 0 else None

        # Get branches based on type
        if branch_type == "local":
            git_command = ["git", "branch"]
        elif branch_type == "remote":
            git_command = ["git", "branch", "-r"]
        else:  # "all"
            git_command = ["git", "branch", "-a"]

        branches_result = subprocess.run(
            git_command,
            cwd=path,
            capture_output=True,
            text=True,
            timeout=10
        )

        if branches_result.returncode != 0:
            raise HTTPException(status_code=500, detail="Failed to list branches")

        # Parse branch names
        branches = []
        for line in branches_result.stdout.split('\n'):
            line = line.strip()
            if not line:
                continue

            # Remove the * marker for current branch
            if line.startswith('*'):
                line = line[1:].strip()

            # Skip HEAD references
            if '-> ' in line or line.startswith('remotes/origin/HEAD') or line.startswith('origin/HEAD'):
                continue

            # Clean up branch names based on type
            if branch_type == "remote" or branch_type == "all":
                if line.startswith('remotes/origin/'):
                    branch_name = line.replace('remotes/origin/', '')
                elif line.startswith('origin/'):
                    branch_name = line.replace('origin/', '')
                else:
                    branch_name = line
            else:
                branch_name = line

            if branch_name and branch_name not in branches:
                branches.append(branch_name)

        return {
            "current_branch": current_branch,
            "branches": sorted(branches)
        }

    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="Git command timed out")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Legacy endpoints (for backward compatibility)

@router.post("/sessions", response_model=SessionResponse)
async def create_session(session_data: SessionCreate, db: Session = Depends(get_db)):
    """Create a new session for a project (legacy endpoint)."""
    db_session = get_or_create_session_for_project(db, session_data.project_path)
    return db_session


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str, db: Session = Depends(get_db)):
    """Get session details (legacy endpoint)."""
    db_session = db.query(DBSession).filter(DBSession.id == session_id).first()
    if not db_session:
        raise HTTPException(status_code=404, detail="Session not found")
    return db_session


@router.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str, db: Session = Depends(get_db)):
    """Get full task details by ID (legacy endpoint)."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.get("/tasks/{task_id}/status", response_model=TaskStatusResponse)
async def get_task_status(task_id: str, db: Session = Depends(get_db)):
    """Get task status by ID (legacy endpoint)."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Calculate test summary
    total_tests = len(task.test_cases)
    passed_tests = len([tc for tc in task.test_cases if tc.status == TestCaseStatus.PASSED])
    failed_tests = len([tc for tc in task.test_cases if tc.status == TestCaseStatus.FAILED])
    pending_tests = len([tc for tc in task.test_cases if tc.status == TestCaseStatus.PENDING])

    # Get latest Claude response
    latest_claude_response = None
    claude_responses = [
        i for i in task.interactions
        if i.interaction_type == InteractionType.CLAUDE_RESPONSE
    ]
    if claude_responses:
        latest_claude_response = claude_responses[-1].content

    # Check if waiting for input (PAUSED status means waiting)
    waiting_for_input = task.status == TaskStatus.PAUSED

    # Generate progress message
    progress_messages = {
        TaskStatus.PENDING: "Task created, waiting to be started",
        TaskStatus.RUNNING: f"Task is running - {len(task.interactions)} interactions so far",
        TaskStatus.PAUSED: "Task is paused, waiting for continuation",
        TaskStatus.STOPPED: "Task has been stopped",
        TaskStatus.TESTING: f"Running tests: {passed_tests}/{total_tests} passed",
        TaskStatus.COMPLETED: f"Task completed successfully - all {total_tests} tests passed",
        TaskStatus.FAILED: f"Task failed - {failed_tests} tests failed",
    }

    return TaskStatusResponse(
        id=task.id,
        task_name=task.task_name,
        root_folder=task.root_folder,
        branch_name=task.branch_name,
        base_branch=task.base_branch,
        status=task.status,
        summary=task.summary,
        error_message=task.error_message,
        progress=progress_messages.get(task.status, "Unknown status"),
        test_summary={
            "total": total_tests,
            "passed": passed_tests,
            "failed": failed_tests,
            "pending": pending_tests,
        },
        latest_claude_response=latest_claude_response,
        waiting_for_input=waiting_for_input,
    )


@router.get("/sessions/{session_id}/tasks", response_model=List[TaskResponse])
async def get_session_tasks(session_id: str, db: Session = Depends(get_db)):
    """Get all tasks for a session (legacy endpoint)."""
    db_session = db.query(DBSession).filter(DBSession.id == session_id).first()
    if not db_session:
        raise HTTPException(status_code=404, detail="Session not found")

    tasks = db.query(Task).filter(Task.session_id == session_id).all()
    return tasks


# ============================================================================
# Prompt Management Endpoints
# ============================================================================

@router.post("/prompts", response_model=PromptResponse, status_code=201)
async def create_prompt(prompt_data: PromptCreate, db: Session = Depends(get_db)):
    """Create a new prompt template."""
    from app.models.prompt import Prompt

    prompt = Prompt(
        title=prompt_data.title,
        content=prompt_data.content,
        category=prompt_data.category,
        tags=prompt_data.tags,
    )

    db.add(prompt)
    db.commit()
    db.refresh(prompt)

    return prompt


@router.get("/prompts", response_model=List[PromptResponse])
async def list_prompts(
    category: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """
    List all prompts with optional filtering.

    - category: Filter by category
    - search: Search in title, content, and tags
    - limit: Maximum number of results (default: 50)
    """
    from app.models.prompt import Prompt

    query = db.query(Prompt)

    if category:
        query = query.filter(Prompt.category == category)

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (Prompt.title.like(search_term)) |
            (Prompt.content.like(search_term)) |
            (Prompt.tags.like(search_term))
        )

    # Order by usage: NULL last_used_at values will naturally go to the end in MySQL
    prompts = query.order_by(Prompt.usage_count.desc(),
                             Prompt.last_used_at.desc()).limit(limit).all()

    return prompts


@router.get("/prompts/{prompt_id}", response_model=PromptResponse)
async def get_prompt(prompt_id: str, db: Session = Depends(get_db)):
    """Get a specific prompt by ID."""
    from app.models.prompt import Prompt

    prompt = db.query(Prompt).filter(Prompt.id == prompt_id).first()
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")

    return prompt


@router.put("/prompts/{prompt_id}", response_model=PromptResponse)
async def update_prompt(
    prompt_id: str,
    prompt_data: PromptUpdate,
    db: Session = Depends(get_db)
):
    """Update an existing prompt."""
    from app.models.prompt import Prompt
    from datetime import datetime

    prompt = db.query(Prompt).filter(Prompt.id == prompt_id).first()
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")

    # Update only provided fields
    if prompt_data.title is not None:
        prompt.title = prompt_data.title
    if prompt_data.content is not None:
        prompt.content = prompt_data.content
    if prompt_data.category is not None:
        prompt.category = prompt_data.category
    if prompt_data.tags is not None:
        prompt.tags = prompt_data.tags

    prompt.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(prompt)

    return prompt


@router.delete("/prompts/{prompt_id}")
async def delete_prompt(prompt_id: str, db: Session = Depends(get_db)):
    """Delete a prompt."""
    from app.models.prompt import Prompt

    prompt = db.query(Prompt).filter(Prompt.id == prompt_id).first()
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")

    db.delete(prompt)
    db.commit()

    return {"message": f"Prompt '{prompt.title}' deleted successfully"}


@router.post("/prompts/{prompt_id}/use")
async def use_prompt(prompt_id: str, db: Session = Depends(get_db)):
    """Mark a prompt as used (increments usage count and updates last_used_at)."""
    from app.models.prompt import Prompt
    from datetime import datetime

    prompt = db.query(Prompt).filter(Prompt.id == prompt_id).first()
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")

    prompt.usage_count += 1
    prompt.last_used_at = datetime.utcnow()

    db.commit()
    db.refresh(prompt)

    return prompt
