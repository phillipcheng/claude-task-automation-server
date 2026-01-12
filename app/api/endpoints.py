from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from typing import List, Optional, Tuple
import asyncio
import json
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
    ProjectCreate,
    ProjectUpdate,
    ProjectResponse,
    BatchDeleteRequest,
    BatchDeleteResult,
    BatchDeleteResponse,
    ProjectBatchDeleteRequest,
    ProjectBatchDeleteResult,
    ProjectBatchDeleteResponse,
)
from app.models import (
    Session as DBSession,
    Task,
    TaskStatus,
    TestCaseStatus,
    InteractionType,
    Project,
)
from app.services.task_executor import TaskExecutor
from app.services.git_worktree import GitWorktreeManager
from app.services.criteria_analyzer import CriteriaAnalyzer
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


def get_git_info(root_folder: str) -> Tuple[Optional[str], Optional[str]]:
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
    print(f"📝 Creating task: {task_data.task_name}, chat_mode={task_data.chat_mode}")

    # Check if task name already exists
    existing_task = db.query(Task).filter(Task.task_name == task_data.task_name).first()
    if existing_task:
        print(f"❌ Task '{task_data.task_name}' already exists")
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

            # If branch_name not specified, auto-generate from task name
            if not branch_name:
                # Sanitize task name for git branch: replace invalid chars with underscore
                import re
                sanitized_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', task_data.task_name)
                # Remove consecutive underscores and trim
                sanitized_name = re.sub(r'_+', '_', sanitized_name).strip('_')
                branch_name = f"task/{sanitized_name}"

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

                # Note: Worktree creation is now handled dynamically in _execute_with_claude
                # based on planning phase results. No need to enforce here.
                pass

        # Worktree creation is now handled dynamically during task execution
        # The planning phase in _execute_with_claude determines if write access is needed
        # and creates worktrees on-demand. This allows:
        # 1. Read-only tasks to run without worktrees
        # 2. Tasks that start as read-only but need write later to get worktrees dynamically
        # 3. Multi-project tasks to only create worktrees for projects that actually need modification

        # Validate project paths exist (if provided)
        if task_data.projects:
            for project in task_data.projects:
                project_path = project.get("path")
                if project_path and not os.path.exists(project_path):
                    raise HTTPException(
                        status_code=400,
                        detail=f"Project path '{project_path}' does not exist."
                    )

        if not branch_name:
            # Not using worktree, fall back to detected branch
            branch_name = detected_branch

    # Extract or use provided ending criteria
    end_criteria_text = task_data.end_criteria
    criteria_warning = None

    if not end_criteria_text:
        # Try to extract ending criteria from task description using LLM
        # Skip extraction to avoid blocking task creation - can be slow
        # Users should provide explicit criteria for best results
        criteria_warning = "INFO: No ending criteria provided. Task will use default completion detection (max iterations: 20)."

        # Optionally enable LLM extraction (disabled by default for performance)
        # try:
        #     analyzer = CriteriaAnalyzer()
        #     extracted_criteria, is_clear = await analyzer.extract_ending_criteria(task_data.description)
        #     if is_clear and extracted_criteria:
        #         end_criteria_text = extracted_criteria
        # except Exception as e:
        #     print(f"Failed to extract ending criteria: {e}")

    # Build end criteria configuration JSON
    end_criteria_config = None
    if end_criteria_text or task_data.max_iterations or task_data.max_tokens:
        end_criteria_config = {}
        if end_criteria_text:
            end_criteria_config["criteria"] = end_criteria_text
        if task_data.max_iterations is not None:
            end_criteria_config["max_iterations"] = task_data.max_iterations
        else:
            # Default max iterations
            end_criteria_config["max_iterations"] = 20
        if task_data.max_tokens is not None:
            end_criteria_config["max_tokens"] = task_data.max_tokens
        if criteria_warning:
            end_criteria_config["warning"] = criteria_warning

    # Create task
    db_task = Task(
        task_name=task_data.task_name,
        session_id=db_session.id,
        description=task_data.description,
        user_id=task_data.user_id,  # User identifier for multi-user support
        root_folder=root_folder,
        branch_name=branch_name,
        base_branch=base_branch,
        git_repo=git_repo,
        worktree_path=worktree_path,
        status=TaskStatus.PENDING,
        end_criteria_config=end_criteria_config,
        project_context=task_data.project_context,
        projects=task_data.projects,
        chat_mode=task_data.chat_mode,  # Chat mode: respond once and wait for user input
        mcp_servers=task_data.mcp_servers,  # Custom MCP tools
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
    task = db.query(Task).options(
        joinedload(Task.test_cases),
        joinedload(Task.interactions)
    ).filter(Task.task_name == task_name).first()
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_name}' not found")

    # Calculate test summary
    total_tests = len(task.test_cases)
    passed_tests = len([tc for tc in task.test_cases if tc.status == TestCaseStatus.PASSED])
    failed_tests = len([tc for tc in task.test_cases if tc.status == TestCaseStatus.FAILED])
    pending_tests = len([tc for tc in task.test_cases if tc.status == TestCaseStatus.PENDING])

    # Calculate interaction count (Claude responses)
    interaction_count = len([
        i for i in task.interactions
        if i.interaction_type == InteractionType.CLAUDE_RESPONSE
    ])

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

    # Check if there's an active process running
    process_running = False
    if task.process_pid:
        try:
            import os
            os.kill(task.process_pid, 0)  # Signal 0 checks if process exists
            process_running = True
        except (OSError, ProcessLookupError):
            # Process not found or we don't have permission - it's not running
            # Clear the stale PID from the database
            task.process_pid = None
            db.commit()
            process_running = False

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
        user_id=task.user_id,
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
        projects=task.projects,
        project_context=task.project_context,
        end_criteria_config=task.end_criteria_config,
        total_tokens_used=task.total_tokens_used,
        interaction_count=interaction_count,
        chat_mode=task.chat_mode,
        process_running=process_running,
        process_pid=task.process_pid,
    )


@router.get("/tasks", response_model=List[TaskResponse])
async def list_all_tasks(
    status: Optional[str] = None,
    root_folder: Optional[str] = None,
    user_id: Optional[str] = None,
    name_filter: Optional[str] = None,
    sort_by: str = "updated_at",
    sort_order: str = "desc",
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """
    List all tasks, optionally filtered by status, root_folder, and/or user_id.

    Args:
        status: Filter by task status (pending, running, paused, testing, completed, failed)
        root_folder: Filter by project root folder path
        user_id: Filter by user identifier (for multi-user support)
        name_filter: Filter by task name (case-insensitive substring match)
        sort_by: Field to sort by (created_at, updated_at, task_name). Default: updated_at
        sort_order: Sort order (asc, desc). Default: desc
        limit: Maximum number of tasks to return (default: 100)
        offset: Number of tasks to skip for pagination (default: 0)
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

    if user_id:
        query = query.filter(Task.user_id == user_id)

    if name_filter:
        query = query.filter(Task.task_name.ilike(f"%{name_filter}%"))

    # Determine sort field
    sort_field = Task.updated_at
    if sort_by == "created_at":
        sort_field = Task.created_at
    elif sort_by == "task_name":
        sort_field = Task.task_name

    # Apply sort order
    if sort_order == "asc":
        query = query.order_by(sort_field.asc())
    else:
        query = query.order_by(sort_field.desc())

    tasks = query.offset(offset).limit(limit).all()
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
    print(f"🚀 Starting task executor for task: {task.id} ({task_name})")
    executor = TaskExecutor()
    background_tasks.add_task(executor.execute_task, task.id)

    return {"message": f"Task '{task_name}' started", "status": "running"}


@router.post("/tasks/by-name/{task_name}/clone")
async def clone_task(
    task_name: str,
    new_name: Optional[str] = None,
    continue_session: bool = False,
    db: Session = Depends(get_db)
):
    """Clone an existing task with all its settings but without conversation history.

    Args:
        task_name: Name of the task to clone
        new_name: Optional new name for the cloned task. Defaults to "{original_name}_copy"
        continue_session: If True, the new task will continue Claude's conversation context
                          from the original task (shares the same claude_session_id)
    """
    import uuid
    from datetime import datetime

    task = db.query(Task).filter(Task.task_name == task_name).first()
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_name}' not found")

    # Generate new name if not provided
    if not new_name:
        base_name = f"{task_name}_copy"
        new_name = base_name
        counter = 1
        while db.query(Task).filter(Task.task_name == new_name).first():
            new_name = f"{base_name}_{counter}"
            counter += 1
    else:
        # Check if new name already exists
        if db.query(Task).filter(Task.task_name == new_name).first():
            raise HTTPException(status_code=400, detail=f"Task with name '{new_name}' already exists")

    # Create new task with same settings
    new_task = Task(
        id=str(uuid.uuid4()),
        session_id=str(uuid.uuid4()),
        task_name=new_name,
        description=task.description,
        user_id=task.user_id,
        root_folder=task.root_folder,
        git_repo=task.git_repo,
        base_branch=task.base_branch,
        status=TaskStatus.PENDING,
        chat_mode=task.chat_mode,
        project_context=task.project_context,
        projects=task.projects,
        mcp_servers=task.mcp_servers,
        end_criteria_config=task.end_criteria_config,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        # Copy Claude session ID if continue_session is True
        claude_session_id=task.claude_session_id if continue_session else None,
    )

    db.add(new_task)
    db.commit()
    db.refresh(new_task)

    return {
        "message": f"Task '{task_name}' cloned successfully",
        "original_task": task_name,
        "new_task": new_name,
        "new_task_id": new_task.id,
        "session_continued": continue_session and task.claude_session_id is not None,
    }


@router.post("/tasks/by-name/{task_name}/stop")
async def stop_task(task_name: str, db: Session = Depends(get_db)):
    """Stop a running or paused task and force-kill its subprocess immediately."""
    import os
    import signal
    import time
    import asyncio

    task = db.query(Task).filter(Task.task_name == task_name).first()
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_name}' not found")

    if task.status not in [TaskStatus.RUNNING, TaskStatus.PAUSED, TaskStatus.TESTING]:
        raise HTTPException(
            status_code=400,
            detail=f"Task can only be stopped from RUNNING/PAUSED/TESTING status. Current status: {task.status}"
        )

    # Force-kill the subprocess immediately if PID is available
    killed_process = False
    termination_method = "none"

    if task.process_pid:
        try:
            # First check if process exists
            try:
                os.kill(task.process_pid, 0)  # Signal 0 checks if process exists
                process_exists = True
            except ProcessLookupError:
                process_exists = False

            if process_exists:
                # Try to kill all child processes first
                try:
                    # On macOS, use ps and grep to find child processes
                    import subprocess
                    # Find all child processes of the parent PID
                    ps_cmd = f"ps -o pid,ppid -ax | grep {task.process_pid}"
                    result = subprocess.run(ps_cmd, shell=True, capture_output=True, text=True)
                    
                    # Parse the output to find child PIDs
                    child_pids = []
                    for line in result.stdout.splitlines():
                        parts = line.strip().split()
                        if len(parts) >= 2:
                            try:
                                pid, ppid = int(parts[0]), int(parts[1])
                                # If this process's parent is our target process
                                if ppid == task.process_pid:
                                    child_pids.append(pid)
                            except ValueError:
                                continue
                    
                    # Kill all child processes with SIGTERM first
                    for child_pid in child_pids:
                        try:
                            print(f"Terminating child process {child_pid}")
                            os.kill(child_pid, signal.SIGTERM)
                        except ProcessLookupError:
                            pass  # Child already gone
                        except Exception as e:
                            print(f"Error terminating child process {child_pid}: {e}")
                
                except Exception as e:
                    print(f"Error finding child processes: {e}")
                
                # Try SIGTERM first for graceful shutdown of the parent
                try:
                    os.kill(task.process_pid, signal.SIGTERM)
                    termination_method = "SIGTERM"

                    # Wait briefly for graceful shutdown
                    for _ in range(5):  # Wait up to 0.5 seconds
                        try:
                            os.kill(task.process_pid, 0)  # Check if still exists
                            await asyncio.sleep(0.1)
                        except ProcessLookupError:
                            # Process terminated gracefully
                            killed_process = True
                            break

                    # If still exists, force kill with SIGKILL
                    if not killed_process:
                        try:
                            os.kill(task.process_pid, signal.SIGKILL)
                            termination_method = "SIGKILL"
                            killed_process = True

                            # Give SIGKILL a moment to take effect
                            await asyncio.sleep(0.1)
                            
                            # Also kill any remaining child processes with SIGKILL
                            for child_pid in child_pids:
                                try:
                                    os.kill(child_pid, signal.SIGKILL)
                                except ProcessLookupError:
                                    pass  # Child already gone
                                except Exception as e:
                                    print(f"Error force-killing child process {child_pid}: {e}")
                                    
                        except ProcessLookupError:
                            killed_process = True  # Process already gone

                except ProcessLookupError:
                    # Process already terminated during SIGTERM
                    killed_process = True

            else:
                # Process already terminated
                killed_process = True
                termination_method = "already_gone"

        except Exception as e:
            # Log error but continue with status update
            print(f"Error killing process {task.process_pid}: {e}")
            termination_method = f"error: {str(e)}"

    # Cleanup multi-project worktrees if needed
    cleanup_messages = []

    # Check if this is a multi-project task
    if task.projects:
        try:
            import json
            from app.services.git_worktree import GitWorktreeManager

            # Parse projects from JSON if needed
            projects = task.projects if isinstance(task.projects, list) else json.loads(task.projects)

            # Use the main project (task.root_folder) as the base for multi-project operations
            if task.root_folder:
                git_manager = GitWorktreeManager(task.root_folder)

                # Clean up multi-project worktrees
                cleanup_success, cleanup_msg = git_manager.cleanup_multi_project_worktrees(
                    task.task_name, projects, force=True
                )

                if cleanup_success:
                    cleanup_messages.append(f"Multi-project cleanup: {cleanup_msg}")
                else:
                    cleanup_messages.append(f"Multi-project cleanup failed: {cleanup_msg}")

        except Exception as e:
            cleanup_messages.append(f"Multi-project cleanup error: {str(e)}")

    # Also cleanup single project worktree if it exists
    elif task.worktree_path and task.root_folder:
        try:
            from app.services.git_worktree import GitWorktreeManager
            git_manager = GitWorktreeManager(task.root_folder)

            cleanup_success, cleanup_msg = git_manager.cleanup_task_worktree_and_branch(task.task_name, force=True)

            if cleanup_success:
                cleanup_messages.append(f"Single-project cleanup: {cleanup_msg}")
            else:
                cleanup_messages.append(f"Single-project cleanup failed: {cleanup_msg}")

        except Exception as e:
            cleanup_messages.append(f"Single-project cleanup error: {str(e)}")

    # Update status to STOPPED immediately
    task.status = TaskStatus.STOPPED
    task.process_pid = None  # Clear the PID
    db.commit()

    # Prepare response message
    base_message = f"Task '{task_name}' stopped immediately"
    if cleanup_messages:
        full_message = f"{base_message}. Git operations: {'; '.join(cleanup_messages)}"
    else:
        full_message = base_message

    return {
        "message": full_message,
        "status": "stopped",
        "process_killed": killed_process,
        "termination_method": termination_method,
        "cleanup_performed": len(cleanup_messages) > 0
    }


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


@router.post("/tasks/by-name/{task_name}/recover")
async def recover_task(
    task_name: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Recover a failed task by starting a fresh Claude session while preserving conversation history.

    This endpoint:
    1. Clears the invalid Claude session ID
    2. Clears the error message
    3. Builds a recovery context from conversation history
    4. Restarts the task with a new Claude session

    The conversation history is summarized and injected as context so Claude
    understands what was done before the failure.
    """
    from app.models.interaction import ClaudeInteraction, InteractionType

    task = db.query(Task).filter(Task.task_name == task_name).first()
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_name}' not found")

    if task.status not in [TaskStatus.FAILED, TaskStatus.EXHAUSTED, TaskStatus.STOPPED]:
        raise HTTPException(
            status_code=400,
            detail=f"Task can only be recovered from FAILED/EXHAUSTED/STOPPED status. Current status: {task.status}"
        )

    # Get conversation history for context
    interactions = db.query(ClaudeInteraction).filter(
        ClaudeInteraction.task_id == task.id
    ).order_by(ClaudeInteraction.created_at).all()

    # Build recovery context from conversation history
    recovery_context_parts = []
    for interaction in interactions[-10:]:  # Last 10 interactions for context
        role = "User" if interaction.interaction_type == InteractionType.USER_REQUEST else \
               "Assistant" if interaction.interaction_type == InteractionType.CLAUDE_RESPONSE else \
               "System"
        # Truncate long content
        content = interaction.content[:500] + "..." if len(interaction.content) > 500 else interaction.content
        recovery_context_parts.append(f"[{role}]: {content}")

    recovery_context = "\n\n".join(recovery_context_parts) if recovery_context_parts else ""

    # Store recovery context as a system message so Claude gets it
    if recovery_context:
        recovery_message = f"""=== RECOVERY MODE ===
The previous session was interrupted. Here is a summary of the conversation so far:

{recovery_context}

=== END OF RECOVERY CONTEXT ===

Please continue from where we left off. If you were in the middle of a task, please resume it."""

        # Save recovery context as system message
        from app.models.interaction import ClaudeInteraction
        recovery_interaction = ClaudeInteraction(
            task_id=task.id,
            interaction_type=InteractionType.SYSTEM_MESSAGE,
            content=recovery_message
        )
        db.add(recovery_interaction)

    # Clear invalid session and error
    old_session_id = task.claude_session_id
    task.claude_session_id = None  # Force new session
    task.error_message = None
    task.status = TaskStatus.RUNNING
    task.user_input_pending = False
    db.commit()

    # Start task execution in background
    executor = TaskExecutor()
    background_tasks.add_task(executor.execute_task, task.id)

    return {
        "message": f"Task '{task_name}' is recovering with fresh Claude session",
        "status": "running",
        "previous_session_cleared": old_session_id is not None,
        "conversation_preserved": len(interactions) > 0,
        "interactions_count": len(interactions)
    }


@router.post("/tasks/by-name/{task_name}/merge-to-test")
async def merge_task_to_test(
    task_name: str,
    db: Session = Depends(get_db)
):
    """
    Merge the task's worktree branch to the project's default branch for integration testing.

    This prepares the code for release to test environment.
    """
    import subprocess

    task = db.query(Task).filter(Task.task_name == task_name).first()
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_name}' not found")

    # Check task has a worktree with changes
    if not task.worktree_path or not task.branch_name:
        raise HTTPException(
            status_code=400,
            detail="Task has no worktree branch. Nothing to merge."
        )

    if not os.path.exists(task.worktree_path):
        raise HTTPException(
            status_code=400,
            detail=f"Worktree path no longer exists: {task.worktree_path}"
        )

    # Determine the target branch (default_branch from project)
    target_branch = None

    # Try to get from task's projects config
    if task.projects:
        for project in task.projects:
            if project.get('default_branch'):
                target_branch = project.get('default_branch')
                break

    # Fallback to base_branch if set
    if not target_branch and task.base_branch:
        target_branch = task.base_branch

    # Fallback to common defaults
    if not target_branch:
        target_branch = "main"  # Default fallback

    # Get the main repo path (not worktree)
    main_repo_path = task.root_folder
    if not main_repo_path or not os.path.exists(main_repo_path):
        raise HTTPException(
            status_code=400,
            detail="Cannot find main repository path"
        )

    try:
        # Step 1: Fetch latest from remote in main repo
        subprocess.run(
            ["git", "fetch", "origin"],
            cwd=main_repo_path,
            capture_output=True,
            text=True,
            timeout=30
        )

        # Step 2: Checkout the target branch in main repo
        checkout_result = subprocess.run(
            ["git", "checkout", target_branch],
            cwd=main_repo_path,
            capture_output=True,
            text=True,
            timeout=30
        )

        if checkout_result.returncode != 0:
            # Try to create from remote if doesn't exist locally
            checkout_result = subprocess.run(
                ["git", "checkout", "-b", target_branch, f"origin/{target_branch}"],
                cwd=main_repo_path,
                capture_output=True,
                text=True,
                timeout=30
            )

            if checkout_result.returncode != 0:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to checkout target branch '{target_branch}': {checkout_result.stderr}"
                )

        # Step 3: Pull latest changes on target branch
        pull_result = subprocess.run(
            ["git", "pull", "origin", target_branch],
            cwd=main_repo_path,
            capture_output=True,
            text=True,
            timeout=60
        )

        # Step 4: Merge the task branch into target branch
        merge_result = subprocess.run(
            ["git", "merge", task.branch_name, "--no-edit", "-m", f"Merge {task.branch_name} for testing (task: {task.task_name})"],
            cwd=main_repo_path,
            capture_output=True,
            text=True,
            timeout=60
        )

        if merge_result.returncode != 0:
            # Check for merge conflicts
            if "CONFLICT" in merge_result.stdout or "CONFLICT" in merge_result.stderr:
                # Abort the merge
                subprocess.run(["git", "merge", "--abort"], cwd=main_repo_path, capture_output=True)
                raise HTTPException(
                    status_code=409,
                    detail=f"Merge conflict detected. Please resolve manually. Details: {merge_result.stderr}"
                )
            raise HTTPException(
                status_code=500,
                detail=f"Merge failed: {merge_result.stderr}"
            )

        # Step 5: Push to remote (optional - can be configured)
        push_result = subprocess.run(
            ["git", "push", "origin", target_branch],
            cwd=main_repo_path,
            capture_output=True,
            text=True,
            timeout=60
        )

        push_success = push_result.returncode == 0

        return {
            "message": f"Successfully merged '{task.branch_name}' into '{target_branch}'",
            "source_branch": task.branch_name,
            "target_branch": target_branch,
            "pushed": push_success,
            "push_message": push_result.stdout if push_success else push_result.stderr
        }

    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Git operation timed out")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Merge operation failed: {str(e)}")


@router.post("/tasks/by-name/{task_name}/clear-and-restart")
async def clear_and_restart_task(
    task_name: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Clear all conversation history and restart the task from scratch."""
    from app.models.interaction import ClaudeInteraction

    task = db.query(Task).filter(Task.task_name == task_name).first()
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_name}' not found")

    # Stop the task if it's running
    if task.status == TaskStatus.RUNNING:
        # Kill the process if exists
        if task.process_pid:
            try:
                import signal
                os.kill(task.process_pid, signal.SIGTERM)
            except (ProcessLookupError, OSError):
                pass  # Process already terminated
            task.process_pid = None

    # Delete all interactions for this task
    deleted_count = db.query(ClaudeInteraction).filter(
        ClaudeInteraction.task_id == task.id
    ).delete()

    # Clear user input queue to ensure fresh start
    task.user_input_queue = None
    task.user_input_pending = False
    task.custom_human_input = None  # Clear legacy user input field

    # Clear Claude session ID to force a new conversation session
    task.claude_session_id = None

    # Clean up and reinitiate git worktree and branch
    cleanup_messages = []

    # Handle multi-project tasks
    if task.projects:
        try:
            from app.services.git_worktree import GitWorktreeManager

            # Parse projects from JSON if needed
            projects = task.projects if isinstance(task.projects, list) else json.loads(task.projects)

            # Use the main project (task.root_folder) as the base for multi-project operations
            if task.root_folder:
                git_manager = GitWorktreeManager(task.root_folder)
                main_project_path = task.root_folder

                # Clean up multi-project worktrees
                cleanup_success, cleanup_msg = git_manager.cleanup_multi_project_worktrees(
                    task.task_name, projects, force=True
                )
                if cleanup_msg and cleanup_msg != "No worktrees to clean up":
                    cleanup_messages.append(f"Cleanup: {cleanup_msg}")

                # Recreate multi-project worktrees
                create_success, project_paths, create_msg = git_manager.create_multi_project_worktrees(
                    task.task_name, projects, task.base_branch
                )

                if create_success and create_msg and create_msg != "No worktrees needed":
                    cleanup_messages.append(f"Reinitiated: {create_msg}")
                    # Update task.worktree_path to the main project's worktree path for compatibility
                    task.worktree_path = project_paths.get(main_project_path)
                else:
                    if create_msg:
                        cleanup_messages.append(f"Reinitiation: {create_msg}")
                    task.worktree_path = None
            else:
                cleanup_messages.append("Multi-project git cleanup/reinitiation skipped: No root_folder specified")

        except Exception as e:
            cleanup_messages.append(f"Multi-project git cleanup/reinitiation error: {str(e)}")
            task.worktree_path = None

    # Handle single-project tasks
    elif task.root_folder:  # Only need root_folder to recreate worktree
        try:
            from app.services.git_worktree import GitWorktreeManager
            git_manager = GitWorktreeManager(task.root_folder)

            # First, clean up any existing worktree and branch
            if task.worktree_path:
                cleanup_success, cleanup_msg = git_manager.cleanup_task_worktree_and_branch(task.task_name, force=True)
                cleanup_messages.append(f"Cleanup: {cleanup_msg}")

            # Then, reinitiate (recreate) worktree and branch for fresh start
            create_success, new_worktree_path, create_msg = git_manager.create_worktree(
                task_name=task.task_name,
                branch_name=task.branch_name,
                base_branch=task.base_branch
            )

            if create_success:
                task.worktree_path = new_worktree_path
                cleanup_messages.append(f"Reinitiated: {create_msg}")
            else:
                cleanup_messages.append(f"Reinitiation failed: {create_msg}")
                task.worktree_path = None

        except Exception as e:
            cleanup_messages.append(f"Git cleanup/reinitiation error: {str(e)}")
            task.worktree_path = None

    # Reset task state
    task.status = TaskStatus.PENDING
    task.current_iteration = 0
    task.total_tokens_used = 0
    task.latest_claude_response = None
    task.claude_session_id = None  # Reset session for fresh start
    task.error_message = None  # Clear any previous error messages on restart

    db.commit()

    # Add a brief delay to ensure database changes are visible to new sessions
    import asyncio
    await asyncio.sleep(0.1)  # 100ms delay

    # Start the task in background
    executor = TaskExecutor()
    background_tasks.add_task(executor.execute_task, task.id)

    # Prepare response message
    base_message = f"Task '{task_name}' conversation cleared ({deleted_count} interactions deleted) and restarted"
    if cleanup_messages:
        full_message = f"{base_message}. Git operations: {'; '.join(cleanup_messages)}"
    else:
        full_message = base_message

    return {
        "message": full_message,
        "deleted_interactions": deleted_count,
        "git_cleanup": cleanup_messages,
        "status": "running"
    }


@router.post("/tasks/by-name/{task_name}/retry")
async def retry_exhausted_task(
    task_name: str,
    background_tasks: BackgroundTasks,
    additional_iterations: Optional[int] = 10,
    additional_tokens: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """
    Retry an EXHAUSTED task with increased limits.

    Args:
        task_name: Name of the task to retry
        additional_iterations: Additional iterations to add (default: 10)
        additional_tokens: Additional tokens to add (default: None - no token limit)
    """
    task = db.query(Task).filter(Task.task_name == task_name).first()
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_name}' not found")

    if task.status != TaskStatus.EXHAUSTED:
        raise HTTPException(
            status_code=400,
            detail=f"Task can only be retried from EXHAUSTED status. Current status: {task.status}"
        )

    # Update limits in end_criteria_config
    end_criteria_config = task.end_criteria_config or {}

    # Increase max iterations
    current_max_iterations = end_criteria_config.get("max_iterations", 20)
    end_criteria_config["max_iterations"] = current_max_iterations + additional_iterations

    # Increase max tokens if specified
    if additional_tokens:
        current_max_tokens = end_criteria_config.get("max_tokens", 0)
        end_criteria_config["max_tokens"] = current_max_tokens + additional_tokens

    # Update task
    task.end_criteria_config = end_criteria_config
    task.status = TaskStatus.RUNNING
    task.error_message = None  # Clear previous exhaustion error
    db.commit()

    # Resume task execution in background
    executor = TaskExecutor()
    background_tasks.add_task(executor.execute_task, task.id)

    return {
        "message": f"Task '{task_name}' retrying with increased limits",
        "status": "running",
        "new_limits": {
            "max_iterations": end_criteria_config["max_iterations"],
            "max_tokens": end_criteria_config.get("max_tokens")
        }
    }


@router.put("/interactions/{interaction_id}")
async def update_interaction(
    interaction_id: str,
    request: dict,
    db: Session = Depends(get_db)
):
    """Update an interaction's content. Used for editing user messages."""
    from app.models.interaction import ClaudeInteraction

    content = request.get('content')
    if not content:
        raise HTTPException(status_code=400, detail="Content is required")

    interaction = db.query(ClaudeInteraction).filter(ClaudeInteraction.id == interaction_id).first()
    if not interaction:
        raise HTTPException(status_code=404, detail=f"Interaction '{interaction_id}' not found")

    # Only allow editing USER_REQUEST messages
    if interaction.interaction_type != InteractionType.USER_REQUEST:
        raise HTTPException(
            status_code=400,
            detail=f"Can only edit user request messages, not {interaction.interaction_type.value}"
        )

    # Get the task to check status
    task = db.query(Task).filter(Task.id == interaction.task_id).first()
    if task.status == TaskStatus.RUNNING:
        raise HTTPException(
            status_code=400,
            detail="Cannot edit interaction while task is running. Stop the task first."
        )

    # Update the interaction content
    interaction.content = content
    db.commit()
    db.refresh(interaction)

    return {
        "message": "Interaction updated successfully",
        "interaction": {
            "id": interaction.id,
            "type": interaction.interaction_type.value,
            "content": interaction.content,
            "timestamp": interaction.created_at.isoformat()
        }
    }


@router.get("/tasks/by-name/{task_name}/conversation")
async def get_task_conversation(task_name: str, collapse_tools: bool = True, db: Session = Depends(get_db)):
    """Get the full conversation history for a task (all interactions)."""
    task = db.query(Task).filter(Task.task_name == task_name).first()
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_name}' not found")

    # Get all interactions ordered by creation time
    interactions = sorted(task.interactions, key=lambda x: x.created_at)

    # Use shared utility for consistent formatting
    from app.utils.conversation_formatter import collapse_consecutive_tool_results
    conversation = collapse_consecutive_tool_results(interactions, collapse_tools)

    return {
        "task_name": task.task_name,
        "status": task.status,
        "conversation": conversation
    }


@router.get("/tasks/by-name/{task_name}/stream")
async def stream_task_conversation(task_name: str, db: Session = Depends(get_db)):
    """Stream task conversation updates in real-time using Server-Sent Events (SSE)."""
    task = db.query(Task).filter(Task.task_name == task_name).first()
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_name}' not found")

    async def event_generator():
        """Generate SSE events with new interactions."""
        last_interaction_count = 0
        is_initial_connection = True  # Flag to send existing messages on first connection

        while True:
            # Get current task status efficiently (single field query)
            current_task = db.query(Task.status, Task.id).filter(Task.id == task.id).first()
            if not current_task:
                break
            current_status = current_task.status

            # Get count of interactions efficiently
            from app.models.interaction import ClaudeInteraction
            current_count = db.query(ClaudeInteraction).filter(
                ClaudeInteraction.task_id == task.id
            ).count()

            # Send interactions: all existing on first connection, then only new ones
            if current_count > last_interaction_count or is_initial_connection:
                from app.utils.conversation_formatter import collapse_consecutive_tool_results

                if is_initial_connection and current_count > 0:
                    # Send ALL existing interactions on first connection with tool grouping
                    all_interactions = db.query(ClaudeInteraction).filter(
                        ClaudeInteraction.task_id == task.id
                    ).order_by(ClaudeInteraction.created_at).all()

                    # Apply the same tool grouping logic as conversation API
                    formatted_interactions = collapse_consecutive_tool_results(all_interactions, collapse_tools=True)

                    for data in formatted_interactions:
                        yield f"data: {json.dumps(data)}\n\n"

                    is_initial_connection = False
                    last_interaction_count = current_count

                elif current_count > last_interaction_count:
                    # Get all interactions and format them, then compare with what we sent before
                    all_interactions = db.query(ClaudeInteraction).filter(
                        ClaudeInteraction.task_id == task.id
                    ).order_by(ClaudeInteraction.created_at).all()

                    # Apply the same tool grouping logic as conversation API
                    formatted_interactions = collapse_consecutive_tool_results(all_interactions, collapse_tools=True)

                    # For real-time streaming, we need to send ALL formatted messages
                    # Frontend will handle deduplication by ID
                    for data in formatted_interactions:
                        yield f"data: {json.dumps(data)}\n\n"

                    last_interaction_count = current_count

            # Send status update
            status_data = {
                "type": "status",
                "status": current_status.value,
                "total_interactions": current_count
            }
            yield f"data: {json.dumps(status_data)}\n\n"

            # If task is in terminal state, stop streaming
            if current_status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.STOPPED]:
                break

            # Wait before next check (reduced for better responsiveness)
            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@router.post("/tasks/by-name/{task_name}/set-input")
async def set_custom_human_input(
    task_name: str,
    request: dict,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Set custom human input for the next interaction.
    Uses high-priority queue system to ensure user input is never overlooked.
    Supports optional images field for multimodal input.
    """
    from app.services.user_input_manager import UserInputManager

    task = db.query(Task).filter(Task.task_name == task_name).first()
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_name}' not found")

    if "input" not in request:
        raise HTTPException(status_code=400, detail="Missing 'input' field in request body")

    user_input = request["input"]
    # Handle images (optional) - format: [{"base64": "...", "media_type": "image/png"}, ...]
    images = request.get("images", [])

    # Check for recent duplicate messages to prevent spam/repeated submissions
    import time
    from datetime import datetime, timedelta

    # Get current queue to check for recent duplicates
    current_queue = task.user_input_queue or []
    recent_cutoff = datetime.utcnow() - timedelta(seconds=30)  # 30 second window

    for entry in current_queue:
        entry_time = datetime.fromisoformat(entry.get("timestamp", "1970-01-01T00:00:00"))
        entry_input = entry.get("input", "")
        if entry_time > recent_cutoff and entry_input == user_input:
            print(f"🚫 DUPLICATE MESSAGE BLOCKED: '{user_input[:50]}...' was already sent within 30 seconds")
            return {
                "message": "Duplicate message blocked - same message was recently sent",
                "task_name": task_name,
                "input_preview": user_input[:100] + "..." if len(user_input) > 100 else user_input,
                "blocked_reason": "DUPLICATE_MESSAGE_WITHIN_30_SECONDS"
            }

    # Use new high-priority user input queue system
    # Use separate session to avoid transaction conflicts with endpoint session
    print(f"🔍 DEBUG: Adding user input to queue for task {task.id} ({task_name}): '{user_input[:50]}...'")
    if images:
        print(f"🖼️ DEBUG: Including {len(images)} images with user input")
    success = UserInputManager.add_user_input(db, task.id, user_input, auto_commit=True, use_separate_session=True, images=images if images else None)
    print(f"🔍 DEBUG: UserInputManager.add_user_input() returned: {success}")

    if not success:
        print(f"❌ DEBUG: Failed to add user input to queue for task {task.id}")
        raise HTTPException(status_code=500, detail="Failed to add user input to queue")
    else:
        print(f"✅ DEBUG: Successfully added user input to queue for task {task.id} with separate session")

    # ROOT CAUSE FIX: Ensure task executor is running to process user input
    task_executor_restarted = False
    if task.status.value == "RUNNING":
        # Check if task has an active process
        process_running = False
        if task.process_pid:
            try:
                import os
                os.kill(task.process_pid, 0)  # Signal 0 checks if process exists
                process_running = True
            except (OSError, ProcessLookupError):
                # Process not found - clear stale PID
                task.process_pid = None
                # Don't commit here - we'll commit everything together at the end
                process_running = False

        # REAL-TIME INTERRUPTION: Kill active process and send user input immediately
        if process_running:
            print(f"⚡ REAL-TIME INTERRUPT: Killing active Claude process {task.process_pid} to send user input immediately")
            try:
                import signal
                os.kill(task.process_pid, signal.SIGTERM)  # Graceful termination
                print(f"✅ Process {task.process_pid} terminated for immediate user input processing")
                task.process_pid = None
                db.commit()
            except (OSError, ProcessLookupError):
                print(f"⚠️  Process {task.process_pid} already terminated")
                task.process_pid = None
                db.commit()

            # Send user input immediately with session continuity
            immediate_success = UserInputManager.trigger_immediate_processing(db, task.id, user_input)
            print(f"🚀 Immediate processing triggered: {immediate_success}")
            task_executor_restarted = False

            # The message is already marked as "sent" by the immediate processing function
            # so no additional deduplication is needed here
            if immediate_success:
                print(f"✅ Message successfully processed via immediate processing path")

        else:
            # No active process - restart executor as before
            print(f"🔄 Task {task_name} is RUNNING but no active process - restarting task executor to process user input")
            print(f"🔍 DEBUG: Before task executor restart - task.user_input_queue = {task.user_input_queue}")
            from app.services.task_executor import TaskExecutor
            executor = TaskExecutor()
            background_tasks.add_task(executor.execute_task, task.id)
            task_executor_restarted = True
            immediate_success = False
            print(f"✅ Task executor restarted for {task_name} - user input will be processed by task executor")
            print(f"🔍 DEBUG: After task executor restart - task.user_input_queue = {task.user_input_queue}")

            # Mark the message as processed since it's being sent to Claude
            # This implements the rule: "as long as it is sent to Claude, it is processed"
            processed_input = UserInputManager.get_next_user_input(db, task.id)
            if processed_input:
                print(f"✅ Marked message as processed: {processed_input[:50]}...")

    elif task.status.value == "PAUSED":
        # Task is paused (waiting for input) - auto-resume to process user input
        print(f"🔄 Task {task_name} is PAUSED (waiting for input) - auto-resuming to process user input")
        from app.services.task_executor import TaskExecutor
        task.status = TaskStatus.RUNNING
        db.commit()
        executor = TaskExecutor()
        background_tasks.add_task(executor.execute_task, task.id)
        task_executor_restarted = True
        immediate_success = False
        print(f"✅ Task {task_name} auto-resumed with user input")

        # Mark the message as processed since it's being sent to Claude
        processed_input = UserInputManager.get_next_user_input(db, task.id)
        if processed_input:
            print(f"✅ Marked message as processed: {processed_input[:50]}...")
    else:
        # Task not running (STOPPED, COMPLETED, FAILED, etc.) - no immediate processing
        immediate_success = False
        task_executor_restarted = False
        print(f"⚠️ Task {task_name} status is {task.status.value} - input queued but task not running")

    # CRITICAL FIX: Use fresh session to see UserInputManager's committed changes
    from app.database import SessionLocal
    fresh_db = SessionLocal()
    try:
        fresh_task = fresh_db.query(Task).filter(Task.id == task.id).first()
        print(f"🔍 DEBUG: After UserInputManager commit - fresh query shows task.user_input_queue = {fresh_task.user_input_queue if fresh_task else 'Task not found'}")
        # Update our task object with the fresh data
        if fresh_task:
            task.user_input_queue = fresh_task.user_input_queue
            task.user_input_pending = fresh_task.user_input_pending
    finally:
        fresh_db.close()

    # Set legacy field for backward compatibility
    task.custom_human_input = user_input
    print(f"🔍 DEBUG: About to commit legacy field for task {task.id}")
    db.commit()
    print(f"✅ DEBUG: Legacy field commit completed for task {task.id}")

    response = {
        "message": "User input processed successfully",
        "task_name": task_name,
        "input_preview": user_input[:100] + "..." if len(user_input) > 100 else user_input,
        "queue_priority": "HIGH",
        "guaranteed_processing": True,
        "immediate_processing": immediate_success,
        "task_executor_restarted": task_executor_restarted
    }

    if immediate_success:
        response["message"] = "⚡ REAL-TIME INTERRUPT: Claude process interrupted - your message sent immediately"
        response["processing_type"] = "REAL_TIME_INTERRUPT"
    elif task_executor_restarted:
        response["message"] = "Task executor restarted - your message will be processed by the active task conversation"
        response["processing_type"] = "EXECUTOR_RESTART"
    else:
        response["message"] = "User input added to queue - will be processed by task executor"
        response["processing_type"] = "QUEUED_FOR_EXECUTOR"

    return response


@router.get("/tasks/by-name/{task_name}/input-queue-status")
async def get_input_queue_status(
    task_name: str,
    db: Session = Depends(get_db)
):
    """
    Get the status of the user input queue for a task.
    """
    from app.services.user_input_manager import UserInputManager

    task = db.query(Task).filter(Task.task_name == task_name).first()
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_name}' not found")

    status = UserInputManager.get_queue_status(db, task.id)
    status["task_name"] = task_name

    return status


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


@router.post("/tasks/batch-delete", response_model=BatchDeleteResponse)
async def batch_delete_tasks(request: BatchDeleteRequest, db: Session = Depends(get_db)):
    """Delete multiple tasks by name in a single request.

    This is more efficient than calling the single delete endpoint multiple times.
    Returns detailed results for each task deletion attempt.
    """
    results = []
    successful = 0
    failed = 0

    for task_name in request.task_names:
        try:
            task = db.query(Task).filter(Task.task_name == task_name).first()
            if not task:
                results.append(BatchDeleteResult(
                    task_name=task_name,
                    success=False,
                    error=f"Task '{task_name}' not found"
                ))
                failed += 1
                continue

            worktree_message = None

            # Cleanup worktree if it exists
            if request.cleanup_worktree and task.worktree_path and task.root_folder:
                worktree_manager = GitWorktreeManager(task.root_folder)
                success, message = worktree_manager.remove_worktree(task_name, force=True)
                if success:
                    worktree_message = message

            db.delete(task)
            db.commit()

            message = f"Task '{task_name}' deleted successfully"
            if worktree_message:
                message += f" (worktree: {worktree_message})"

            results.append(BatchDeleteResult(
                task_name=task_name,
                success=True,
                message=message
            ))
            successful += 1

        except Exception as e:
            db.rollback()
            results.append(BatchDeleteResult(
                task_name=task_name,
                success=False,
                error=str(e)
            ))
            failed += 1

    return BatchDeleteResponse(
        total=len(request.task_names),
        successful=successful,
        failed=failed,
        results=results
    )


def _is_task_running(task: Task, db: Session) -> bool:
    """Check if a task has an active process running."""
    if not task.process_pid:
        return False

    try:
        import os
        os.kill(task.process_pid, 0)  # Signal 0 checks if process exists
        return True
    except (OSError, ProcessLookupError):
        # Process not found or we don't have permission - it's not running
        # Clear the stale PID from the database
        task.process_pid = None
        db.commit()
        return False


@router.delete("/tasks/by-name/{task_name}/worktree")
async def delete_task_worktree(task_name: str, auto_stop: bool = False, db: Session = Depends(get_db)):
    """Delete only the worktree for a task, keeping the task and conversation history intact.

    Args:
        task_name: Name of the task
        auto_stop: If True, automatically stop the task first if it's running (default: False)

    IMPORTANT: By default, the task must be stopped completely before worktree deletion is allowed.
    This enforces the correct workflow: stop task → delete worktree → restart if needed.
    Use auto_stop=True to automatically stop the task first.
    """
    task = db.query(Task).filter(Task.task_name == task_name).first()
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_name}' not found")

    stop_messages = []

    # Handle running task - either auto-stop or error
    is_task_active = _is_task_running(task, db) or task.status in [TaskStatus.RUNNING, TaskStatus.PAUSED, TaskStatus.TESTING]

    if is_task_active:
        if auto_stop:
            # Auto-stop the task first
            import os
            import signal
            import asyncio

            # Force-kill the subprocess if PID is available
            if task.process_pid:
                try:
                    # Check if process exists and kill it
                    try:
                        os.kill(task.process_pid, 0)  # Check if process exists
                        os.kill(task.process_pid, signal.SIGTERM)

                        # Wait briefly for graceful shutdown
                        for _ in range(5):
                            try:
                                os.kill(task.process_pid, 0)
                                await asyncio.sleep(0.1)
                            except ProcessLookupError:
                                break

                        # Force kill if still running
                        try:
                            os.kill(task.process_pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass  # Already dead

                        stop_messages.append(f"Auto-stopped running process (PID: {task.process_pid})")
                    except ProcessLookupError:
                        stop_messages.append(f"Process already terminated (PID: {task.process_pid})")
                except Exception as e:
                    stop_messages.append(f"Warning: Could not stop process {task.process_pid}: {e}")

            # Update task status to STOPPED
            task.status = TaskStatus.STOPPED
            task.process_pid = None
            task.error_message = None
            db.commit()
            stop_messages.append(f"Task status updated to STOPPED")

        else:
            # Traditional error approach when auto_stop=False
            if _is_task_running(task, db):
                raise HTTPException(
                    status_code=400,
                    detail=f"Task '{task_name}' is currently running. Please stop the task first before deleting its worktree. "
                           f"Use the stop endpoint, then delete worktree, then restart if needed. "
                           f"Or use auto_stop=true query parameter to automatically stop the task first."
                )

            if task.status in [TaskStatus.RUNNING, TaskStatus.PAUSED, TaskStatus.TESTING]:
                raise HTTPException(
                    status_code=400,
                    detail=f"Task '{task_name}' has status '{task.status.value}' indicating it may still be active. "
                           f"Please stop the task completely first before deleting its worktree. "
                           f"Or use auto_stop=true query parameter to automatically stop the task first."
                )

    cleanup_messages = []

    # Check if this is a multi-project task
    if task.projects:
        try:
            import json
            from app.services.git_worktree import GitWorktreeManager

            # Parse projects from JSON if needed
            projects = task.projects if isinstance(task.projects, list) else json.loads(task.projects)

            # Use the main project (task.root_folder) as the base for multi-project operations
            if task.root_folder:
                git_manager = GitWorktreeManager(task.root_folder)

                # Clean up multi-project worktrees
                cleanup_success, cleanup_msg = git_manager.cleanup_multi_project_worktrees(
                    task.task_name, projects, force=True
                )

                if cleanup_success:
                    cleanup_messages.append(f"Multi-project worktree cleanup: {cleanup_msg}")
                else:
                    cleanup_messages.append(f"Multi-project worktree cleanup failed: {cleanup_msg}")

        except Exception as e:
            cleanup_messages.append(f"Multi-project worktree cleanup error: {str(e)}")

    # Also cleanup single project worktree if it exists and no multi-project config
    elif task.worktree_path and task.root_folder:
        try:
            from app.services.git_worktree import GitWorktreeManager
            worktree_manager = GitWorktreeManager(task.root_folder)
            success, message = worktree_manager.remove_worktree(task_name, force=True)

            if success:
                cleanup_messages.append(f"Single-project worktree cleanup: {message}")
            else:
                cleanup_messages.append(f"Single-project worktree cleanup failed: {message}")

        except Exception as e:
            cleanup_messages.append(f"Single-project worktree cleanup error: {str(e)}")

    # Check if any cleanup was performed
    if not cleanup_messages:
        if not task.worktree_path and not task.projects:
            raise HTTPException(status_code=400, detail=f"Task '{task_name}' has no worktree")
        if not task.root_folder:
            raise HTTPException(status_code=400, detail=f"Task '{task_name}' has no root_folder configured")

    # Clear worktree_path in database but keep the task
    task.worktree_path = None
    db.commit()

    # Prepare response message
    base_message = f"Worktree for task '{task_name}' removed successfully"
    all_messages = []

    if stop_messages:
        all_messages.extend(stop_messages)
    if cleanup_messages:
        all_messages.extend(cleanup_messages)

    if all_messages:
        full_message = f"{base_message}. Details: {'; '.join(all_messages)}"
    else:
        full_message = base_message

    return {
        "message": full_message,
        "task_preserved": True,
        "auto_stopped": len(stop_messages) > 0,
        "cleanup_performed": len(cleanup_messages) > 0
    }


@router.put("/tasks/by-name/{task_name}", response_model=TaskResponse)
async def update_task(task_name: str, task_update: dict, db: Session = Depends(get_db)):
    """Update task details (description, root_folder, branch_name, base_branch, custom_human_input)."""
    task = db.query(Task).filter(Task.task_name == task_name).first()
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_name}' not found")

    # Update allowed fields
    if "description" in task_update and task_update["description"]:
        task.description = task_update["description"]

    if "root_folder" in task_update:
        task.root_folder = task_update["root_folder"]

    if "branch_name" in task_update:
        task.branch_name = task_update["branch_name"]

    if "base_branch" in task_update:
        task.base_branch = task_update["base_branch"]

    if "git_repo" in task_update:
        task.git_repo = task_update["git_repo"]

    if "end_criteria_config" in task_update:
        task.end_criteria_config = task_update["end_criteria_config"]

    if "custom_human_input" in task_update:
        task.custom_human_input = task_update["custom_human_input"]

    if "projects" in task_update:
        task.projects = task_update["projects"]

    if "project_context" in task_update:
        task.project_context = task_update["project_context"]

    if "mcp_servers" in task_update:
        task.mcp_servers = task_update["mcp_servers"]

    db.commit()
    db.refresh(task)

    return TaskResponse(
        id=task.id,
        task_name=task.task_name,
        session_id=task.session_id,
        description=task.description,
        status=task.status,
        root_folder=task.root_folder,
        branch_name=task.branch_name,
        base_branch=task.base_branch,
        git_repo=task.git_repo,
        worktree_path=task.worktree_path,
        summary=task.summary,
        error_message=task.error_message,
        end_criteria_config=task.end_criteria_config,
        total_tokens_used=task.total_tokens_used,
        created_at=task.created_at,
        updated_at=task.updated_at,
        completed_at=task.completed_at,
        test_cases=[],
        interactions=[],
        projects=task.projects,
        project_context=task.project_context,
        mcp_servers=task.mcp_servers
    )


@router.post("/tasks/by-name/{task_name}/clone")
async def clone_task(task_name: str, db: Session = Depends(get_db)):
    """Clone an existing task with a new name, preserving all parameters."""
    from app.models.session import Session as SessionModel

    # Find the original task
    original_task = db.query(Task).filter(Task.task_name == task_name).first()
    if not original_task:
        raise HTTPException(status_code=404, detail=f"Task '{task_name}' not found")

    # Generate new task name
    import time
    new_task_name = f"{task_name}_clone_{int(time.time())}"

    # Create a new session for the cloned task
    new_session = SessionModel(
        project_path=original_task.root_folder or ""
    )
    db.add(new_session)
    db.flush()  # Get the session ID without committing

    # Create new task with same parameters
    new_task = Task(
        task_name=new_task_name,
        session_id=new_session.id,  # Use new session
        description=original_task.description,
        root_folder=original_task.root_folder,
        branch_name=None,  # Will be auto-generated
        base_branch=original_task.base_branch,
        status=TaskStatus.PENDING,
        summary=None,
        error_message=None,
        worktree_path=None,
        custom_human_input=None,
        # Copy multi-project and additional fields
        projects=original_task.projects,
        project_context=original_task.project_context,
        end_criteria_config=original_task.end_criteria_config,
        mcp_servers=original_task.mcp_servers,  # Copy MCP tools config
    )

    db.add(new_task)
    db.commit()
    db.refresh(new_task)

    return {
        "message": f"Task cloned successfully",
        "original_task": task_name,
        "new_task": new_task_name,
        "task": TaskResponse.model_validate(new_task)
    }


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

    # Calculate interaction count (Claude responses)
    interaction_count = len([
        i for i in task.interactions
        if i.interaction_type == InteractionType.CLAUDE_RESPONSE
    ])

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

    # Check if there's an active process running
    process_running = False
    if task.process_pid:
        try:
            import os
            os.kill(task.process_pid, 0)  # Signal 0 checks if process exists
            process_running = True
        except (OSError, ProcessLookupError):
            # Process not found or we don't have permission - it's not running
            # Clear the stale PID from the database
            task.process_pid = None
            db.commit()
            process_running = False

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
        user_id=task.user_id,
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
        projects=task.projects,
        project_context=task.project_context,
        end_criteria_config=task.end_criteria_config,
        total_tokens_used=task.total_tokens_used,
        interaction_count=interaction_count,
        chat_mode=task.chat_mode,
        process_running=process_running,
        process_pid=task.process_pid,
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
        criteria_config=prompt_data.criteria_config,
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
    if prompt_data.criteria_config is not None:
        prompt.criteria_config = prompt_data.criteria_config

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


# ============================================================================
# Project Management Endpoints
# ============================================================================

@router.post("/projects", response_model=ProjectResponse, status_code=201)
async def create_project(project_data: ProjectCreate, db: Session = Depends(get_db)):
    """
    Create a new saved project configuration.

    Projects are reusable configurations that can be added to tasks.
    Each project has a name, path, default access level, branch, and context.
    Path can be comma-separated list of folders or files. Supports ~ expansion.
    """
    # Parse and validate paths (comma-separated, with ~ expansion)
    raw_paths = [p.strip() for p in project_data.path.split(',') if p.strip()]
    if not raw_paths:
        raise HTTPException(
            status_code=400,
            detail="At least one path is required"
        )

    # Expand ~ and validate each path
    expanded_paths = []
    invalid_paths = []
    for p in raw_paths:
        expanded = os.path.expanduser(p)
        if os.path.exists(expanded):
            expanded_paths.append(expanded)
        else:
            invalid_paths.append(p)

    if invalid_paths:
        raise HTTPException(
            status_code=400,
            detail=f"Path(s) do not exist: {', '.join(invalid_paths)}"
        )

    # Store the expanded, validated paths (comma-separated)
    validated_path = ', '.join(expanded_paths)

    # Check for duplicate project (same user + same name)
    existing = db.query(Project).filter(
        Project.user_id == project_data.user_id,
        Project.name == project_data.name
    ).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"A project named '{project_data.name}' already exists for this user"
        )

    # Build config dict from the config schema
    config_dict = None
    if project_data.config:
        config_dict = project_data.config.dict(exclude_none=True)

    project = Project(
        user_id=project_data.user_id,
        name=project_data.name,
        path=validated_path,
        project_type=project_data.project_type or "other",
        default_branch=project_data.default_branch,
        config=config_dict,
    )

    db.add(project)
    db.commit()
    db.refresh(project)

    return ProjectResponse(
        id=project.id,
        user_id=project.user_id,
        name=project.name,
        path=project.path,
        project_type=project.project_type,
        default_branch=project.default_branch,
        config=project.config,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


@router.get("/projects", response_model=List[ProjectResponse])
async def list_projects(
    user_id: str,
    name_filter: Optional[str] = None,
    sort_by: str = "updated_at",
    sort_order: str = "desc",
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """
    List all saved projects for a user.

    Args:
        user_id: User identifier (required)
        name_filter: Filter by project name (case-insensitive substring match)
        sort_by: Field to sort by (name, created_at, updated_at). Default: updated_at
        sort_order: Sort order (asc, desc). Default: desc
        limit: Maximum number of results (default: 50)
        offset: Number of projects to skip for pagination (default: 0)
    """
    query = db.query(Project).filter(Project.user_id == user_id)

    if name_filter:
        query = query.filter(Project.name.ilike(f"%{name_filter}%"))

    # Determine sort field
    sort_field = Project.updated_at
    if sort_by == "name":
        sort_field = Project.name
    elif sort_by == "created_at":
        sort_field = Project.created_at

    # Apply sort order
    if sort_order == "asc":
        query = query.order_by(sort_field.asc())
    else:
        query = query.order_by(sort_field.desc())

    projects = query.offset(offset).limit(limit).all()

    def build_config(p):
        """Build config from JSON config field or legacy fields for backward compatibility."""
        if p.config:
            return p.config
        # Backward compatibility: build config from legacy fields
        config = {}
        if p.default_context:
            config["context"] = p.default_context
        if p.idl_repo:
            config["idl_repo"] = p.idl_repo
        if p.idl_file:
            config["idl_file"] = p.idl_file
        if p.psm:
            config["psm"] = p.psm
        if p.test_dir:
            config["test_dir"] = p.test_dir
        if p.test_tags:
            config["test_tags"] = p.test_tags
        return config if config else None

    return [
        ProjectResponse(
            id=p.id,
            user_id=p.user_id,
            name=p.name,
            path=p.path,
            project_type=p.project_type,
            default_branch=p.default_branch,
            config=build_config(p),
            created_at=p.created_at,
            updated_at=p.updated_at,
        )
        for p in projects
    ]


@router.post("/projects/batch-delete", response_model=ProjectBatchDeleteResponse)
async def batch_delete_projects(request: ProjectBatchDeleteRequest, db: Session = Depends(get_db)):
    """Delete multiple projects by ID in a single request.

    Returns detailed results for each project deletion attempt.
    """
    results = []
    successful = 0
    failed = 0

    for project_id in request.project_ids:
        try:
            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                results.append(ProjectBatchDeleteResult(
                    project_id=project_id,
                    success=False,
                    error=f"Project with ID '{project_id}' not found"
                ))
                failed += 1
                continue

            project_name = project.name
            db.delete(project)
            db.commit()

            results.append(ProjectBatchDeleteResult(
                project_id=project_id,
                project_name=project_name,
                success=True,
                message=f"Project '{project_name}' deleted successfully"
            ))
            successful += 1

        except Exception as e:
            results.append(ProjectBatchDeleteResult(
                project_id=project_id,
                success=False,
                error=str(e)
            ))
            failed += 1

    return ProjectBatchDeleteResponse(
        total=len(request.project_ids),
        successful=successful,
        failed=failed,
        results=results
    )


@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: str, db: Session = Depends(get_db)):
    """Get a specific saved project by ID."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Build config for response (merge config with legacy fields)
    def build_config(p):
        if p.config:
            return p.config
        config = {}
        if p.default_context:
            config["context"] = p.default_context
        if p.idl_repo:
            config["idl_repo"] = p.idl_repo
        if p.idl_file:
            config["idl_file"] = p.idl_file
        if p.psm:
            config["psm"] = p.psm
        if p.test_dir:
            config["test_dir"] = p.test_dir
        if p.test_tags:
            config["test_tags"] = p.test_tags
        return config if config else None

    return ProjectResponse(
        id=project.id,
        user_id=project.user_id,
        name=project.name,
        path=project.path,
        project_type=project.project_type,
        default_branch=project.default_branch,
        config=build_config(project),
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


@router.put("/projects/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    project_data: ProjectUpdate,
    db: Session = Depends(get_db)
):
    """Update an existing saved project."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Update only provided fields
    if project_data.name is not None:
        project.name = project_data.name

    if project_data.path is not None:
        # Parse and validate paths (comma-separated, with ~ expansion)
        raw_paths = [p.strip() for p in project_data.path.split(',') if p.strip()]
        if not raw_paths:
            raise HTTPException(
                status_code=400,
                detail="At least one path is required"
            )

        # Expand ~ and validate each path
        expanded_paths = []
        invalid_paths = []
        for p in raw_paths:
            expanded = os.path.expanduser(p)
            if os.path.exists(expanded):
                expanded_paths.append(expanded)
            else:
                invalid_paths.append(p)

        if invalid_paths:
            raise HTTPException(
                status_code=400,
                detail=f"Path(s) do not exist: {', '.join(invalid_paths)}"
            )

        project.path = ', '.join(expanded_paths)

    if project_data.default_branch is not None:
        project.default_branch = project_data.default_branch

    if project_data.project_type is not None:
        project.project_type = project_data.project_type if project_data.project_type else "other"

    if project_data.config is not None:
        project.config = project_data.config.dict(exclude_none=True)

    db.commit()
    db.refresh(project)

    # Build config for response (merge config with legacy fields)
    def build_config(p):
        if p.config:
            return p.config
        config = {}
        if p.default_context:
            config["context"] = p.default_context
        if p.idl_repo:
            config["idl_repo"] = p.idl_repo
        if p.idl_file:
            config["idl_file"] = p.idl_file
        if p.psm:
            config["psm"] = p.psm
        if p.test_dir:
            config["test_dir"] = p.test_dir
        if p.test_tags:
            config["test_tags"] = p.test_tags
        return config if config else None

    return ProjectResponse(
        id=project.id,
        user_id=project.user_id,
        name=project.name,
        path=project.path,
        project_type=project.project_type,
        default_branch=project.default_branch,
        config=build_config(project),
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


@router.delete("/projects/{project_id}")
async def delete_project(project_id: str, db: Session = Depends(get_db)):
    """Delete a saved project."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    project_name = project.name
    db.delete(project)
    db.commit()

    return {"message": f"Project '{project_name}' deleted successfully"}