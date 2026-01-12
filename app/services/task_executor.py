import asyncio
from typing import List, Dict, Optional
from sqlalchemy.orm import Session as DBSession
from app.database import SessionLocal
from app.models import (
    Task,
    TaskStatus,
    ClaudeInteraction,
    InteractionType,
    TestCase,
    TestCaseType,
    TestCaseStatus,
    Session,
)
from app.services.streaming_cli_client import StreamingCLIClient
from app.services.simulated_human import SimulatedHuman
from app.services.intelligent_responder import IntelligentResponder
from app.services.test_runner import TestRunner
from app.services.criteria_analyzer import CriteriaAnalyzer
from app.services.user_input_manager import UserInputManager
from datetime import datetime
import re
import os
import json
import logging

logger = logging.getLogger(__name__)


class TaskExecutor:
    """Executes tasks asynchronously with Claude CLI interaction."""

    def __init__(self, cli_command: str = None):
        # Use environment variable or default to "claude"
        cli_cmd = cli_command or os.getenv("CLAUDE_CLI_COMMAND", "claude")
        # Only use streaming client now - it has session support and no timeouts
        self.streaming_client = StreamingCLIClient(cli_command=cli_cmd)
        self.simulated_human = SimulatedHuman()
        self.intelligent_responder = IntelligentResponder()
        self.test_runner = TestRunner()
        self.criteria_analyzer = CriteriaAnalyzer(cli_command=cli_cmd)
        self.user_input_manager = UserInputManager()
        self.max_iterations = 20
        self.max_pauses = 5

        # Import GitWorktreeManager for dynamic worktree creation
        from app.services.git_worktree import GitWorktreeManager
        self.git_worktree_manager_class = GitWorktreeManager

    async def execute_task(self, task_id: str):
        """
        Execute a task asynchronously.

        Planning and worktree creation are now handled dynamically in _execute_with_claude,
        so this method just sets up the initial project path and delegates execution.

        Args:
            task_id: ID of the task to execute
        """
        print(f"🔧 Task {task_id}: Starting execution", flush=True)
        logger.info(f"Task {task_id}: Starting execution")
        db = SessionLocal()
        try:
            task = db.query(Task).filter(Task.id == task_id).first()
            if not task:
                logger.error(f"Task {task_id}: Not found")
                return

            logger.info(f"Task {task.id}: Found task '{task.task_name}', status: {task.status}")

            # Update task status
            task.status = TaskStatus.RUNNING
            db.commit()

            # Determine initial project path (worktree creation happens dynamically in _execute_with_claude)
            project_path = self._get_initial_project_path(db, task)

            if not project_path:
                task.status = TaskStatus.FAILED
                task.error_message = "No valid project path found"
                db.commit()
                return

            print(f"📂 Task {task.id}: Initial project path: {project_path}", flush=True)
            logger.info(f"Task {task.id}: Initial project path: {project_path}")

            # Execute the task with Claude (planning and worktree handled inside)
            print(f"🎬 Task {task.id}: Calling _execute_with_claude", flush=True)
            await self._execute_with_claude(db, task, project_path)
            print(f"✅ Task {task.id}: _execute_with_claude completed", flush=True)

        except Exception as e:
            logger.error(f"Task {task_id}: Execution failed: {e}")
            task = db.query(Task).filter(Task.id == task_id).first()
            if task:
                task.status = TaskStatus.FAILED
                task.error_message = str(e)
                db.commit()
        finally:
            db.close()

    def _get_initial_project_path(self, db: DBSession, task: Task) -> Optional[str]:
        """
        Determine the initial project path for a task.

        This is the starting point - worktree creation happens dynamically
        in _execute_with_claude when write access is needed.

        Args:
            db: Database session
            task: Task object

        Returns:
            Initial project path or None if not found
        """
        # Priority 1: Existing worktree (from previous execution or pre-created)
        if task.worktree_path and os.path.exists(task.worktree_path):
            logger.info(f"Task {task.id}: Using existing worktree: {task.worktree_path}")
            return task.worktree_path

        # Priority 2: Multi-project - use first project path
        if hasattr(task, 'projects') and task.projects:
            first_project = task.projects[0]
            paths_str = first_project.get('path', '')
            # Handle comma-separated paths
            if ',' in paths_str:
                project_path = paths_str.split(',')[0].strip()
            else:
                project_path = paths_str.strip()

            if project_path and os.path.exists(project_path):
                logger.info(f"Task {task.id}: Using first project path: {project_path}")
                return project_path

        # Priority 3: Task root_folder
        if task.root_folder and os.path.exists(task.root_folder):
            logger.info(f"Task {task.id}: Using root_folder: {task.root_folder}")
            return task.root_folder

        # Priority 4: Session project_path
        if task.session_id:
            session = db.query(Session).filter(Session.id == task.session_id).first()
            if session and hasattr(session, 'project_path') and session.project_path:
                if os.path.exists(session.project_path):
                    logger.info(f"Task {task.id}: Using session project_path: {session.project_path}")
                    return session.project_path

        # Priority 5: Current directory (fallback)
        logger.warning(f"Task {task.id}: No valid project path found, using current directory")
        return "."

    async def _execute_with_claude(self, db: DBSession, task: Task, project_path: str):
        """
        Execute task with Claude CLI.

        Flow:
        For each user message:
        1. PLANNING PHASE - Analyze the message to determine which projects need write access
        2. WORKTREE SETUP - Create worktrees for projects needing modification (if not already created)
        3. EXECUTION - Send the user message to Claude with the appropriate execution path

        Args:
            db: Database session
            task: Task to execute
            project_path: Path to the project (may change to worktree)
        """
        print(f"🎯 Task {task.id}: _execute_with_claude started, project_path={project_path}")
        iteration = 0
        current_project_path = project_path  # Track current working path (may become worktree)

        # Get ending criteria configuration (only for work mode)
        end_criteria_config = task.end_criteria_config or {}
        ending_criteria = end_criteria_config.get("criteria") if not task.chat_mode else None
        max_iterations = end_criteria_config.get("max_iterations", self.max_iterations)
        max_tokens = end_criteria_config.get("max_tokens")

        # Track cumulative tokens
        if task.total_tokens_used is None:
            task.total_tokens_used = 0
            db.commit()

        # Check if this is first run (no existing interactions)
        existing_interactions = db.query(ClaudeInteraction).filter(
            ClaudeInteraction.task_id == task.id
        ).count()
        is_first_run = existing_interactions == 0
        print(f"📋 Task {task.id}: is_first_run={is_first_run}, existing_interactions={existing_interactions}")

        # Update current_project_path if worktree already exists (from previous run)
        if task.worktree_path and os.path.exists(task.worktree_path):
            current_project_path = task.worktree_path
            print(f"📂 Task {task.id}: Using existing worktree path: {current_project_path}")

        # ============================================================
        # INITIAL CONTEXT (runs once at task start)
        # Sends project info and tells Claude to wait for instructions
        # Note: Worktree creation happens AFTER planning phase determines
        # which repos need write access. If worktree is created, we clear
        # the session and re-send context in the worktree.
        # ============================================================
        if is_first_run:
            print(f"📨 Task {task.id}: Will send initial context")
            await self._send_initial_context(db, task, current_project_path)

        # ============================================================
        # CHAT LOOP - Handle user messages with per-message planning
        # ============================================================
        last_response = ""
        conversation_history = []

        while iteration < max_iterations:
            iteration += 1
            logger.info(f"Task {task.id}: Starting iteration {iteration}")

            # Check if task was stopped
            db.refresh(task)
            if task.status == TaskStatus.STOPPED:
                logger.info(f"Task {task.id}: Task was stopped, breaking")
                break

            # Check if max tokens limit reached
            if max_tokens and task.total_tokens_used >= max_tokens:
                task.status = TaskStatus.EXHAUSTED
                task.error_message = f"Max tokens limit reached: {task.total_tokens_used}/{max_tokens} tokens used"
                db.commit()
                break

            # Get user message
            user_message = None
            user_images = None

            pending_input, pending_images = self.user_input_manager.get_next_pending_user_input_with_images(db, task.id)
            if pending_input:
                self.user_input_manager.mark_message_as_sent(db, task.id, pending_input)
                user_message = pending_input
                user_images = pending_images
                logger.info(f"Task {task.id}: Got user message: {user_message[:50]}...")

                # Save user message IMMEDIATELY so it appears before planning phase
                self._save_interaction(db, task.id, InteractionType.USER_REQUEST, user_message, images=user_images)
                db.commit()
            else:
                # No user message, wait for input in chat mode or end in work mode
                if task.chat_mode:
                    logger.info(f"Task {task.id}: Chat mode - waiting for user input")
                    break
                else:
                    logger.info(f"Task {task.id}: Work mode - no more input, ending")
                    break

            try:
                # ============================================================
                # PHASE 1: PLANNING - Determine which repos need write access
                # ============================================================
                logger.info(f"Task {task.id}: PHASE 1 - Planning for user message")

                planning_result = await self._run_iteration_planning(
                    db, task, current_project_path, user_message, iteration == 1
                )

                # ============================================================
                # PHASE 2: WORKTREE SETUP - Create worktrees for ALL targets
                # ============================================================
                write_targets = planning_result.get('write_targets', [])
                worktree_paths = []

                if planning_result.get('needs_write') and write_targets:
                    logger.info(f"Task {task.id}: PHASE 2 - Creating worktrees for {len(write_targets)} targets: {write_targets}")

                    for write_target in write_targets:
                        # Create worktree for each target
                        worktree_path = await self._ensure_worktree_for_target(db, task, write_target)
                        if worktree_path:
                            worktree_paths.append(worktree_path)
                            logger.info(f"Task {task.id}: Created worktree: {worktree_path}")

                    # Set the first worktree as the primary execution path (for backward compat)
                    if worktree_paths and not task.worktree_path:
                        task.worktree_path = worktree_paths[0]
                        current_project_path = worktree_paths[0]

                        # ============================================================
                        # CRITICAL: Clear session ID to force new session in worktree
                        # The previous session was started in the original repo directory.
                        # We must start a NEW session in the worktree directory so that
                        # Claude CLI's working directory is correctly set to the worktree.
                        # ============================================================
                        old_session_id = task.claude_session_id
                        task.claude_session_id = None
                        db.commit()
                        print(f"🔄 Task {task.id}: Worktree created, cleared session {old_session_id} to start fresh in worktree")
                        logger.info(f"Task {task.id}: Cleared session {old_session_id} to start fresh in worktree {worktree_paths[0]}")

                        # ============================================================
                        # RE-SEND INITIAL CONTEXT in new session (in worktree)
                        # This ensures the new session has all the project context
                        # ============================================================
                        print(f"📨 Task {task.id}: Re-sending initial context in worktree session")
                        await self._send_initial_context(db, task, worktree_paths[0])

                execution_path = task.worktree_path or current_project_path

                # ============================================================
                # PHASE 3: EXECUTION - Send user message to Claude
                # ============================================================
                logger.info(f"Task {task.id}: PHASE 3 - Executing user message")

                # Build continue prompt with worktree info if created
                if planning_result.get('needs_write') and worktree_paths:
                    if len(worktree_paths) == 1:
                        worktree_info = f"""Worktree created at: {worktree_paths[0]}
Branch: {task.branch_name or 'task branch'}
All file changes should be made in the worktree directory."""
                    else:
                        worktree_list = "\n".join([f"  - {wp}" for wp in worktree_paths])
                        worktree_info = f"""Worktrees created for {len(worktree_paths)} repositories:
{worktree_list}
Branch: {task.branch_name or 'task branch'}
All file changes should be made in the worktree directories."""

                    # Save worktree info as system message so user can see it
                    self._save_interaction(db, task.id, InteractionType.SYSTEM_MESSAGE, worktree_info)
                    db.commit()

                    continue_prompt = f"""{worktree_info}

Now proceed with the original request:
{user_message}"""
                else:
                    continue_prompt = user_message

                # Note: User message already saved before planning phase

                # Execute with streaming
                response, pid, session_id, usage_data = await self._execute_iteration(
                    db, task, execution_path, continue_prompt, user_images
                )

                # Clear images after first use
                user_images = None

                # Update task state
                if session_id:
                    task.claude_session_id = session_id
                task.process_pid = pid
                db.commit()

                # Update token usage
                if usage_data and 'usage' in usage_data:
                    output_tokens = usage_data['usage'].get('output_tokens', 0)
                    task.total_tokens_used = (task.total_tokens_used or 0) + output_tokens
                    db.commit()

                last_response = response
                conversation_history.append(response)
                is_first_iteration = False

                # ============================================================
                # PHASE 4: DECISION - Determine next action
                # ============================================================
                logger.info(f"Task {task.id}: PHASE 4 - Decision")

                # Check ending criteria (work mode only)
                if ending_criteria:
                    try:
                        criteria_met, reasoning = await self.criteria_analyzer.check_task_completion(
                            ending_criteria=ending_criteria,
                            task_description=task.description,
                            conversation_history="\n\n".join(conversation_history[-3:]),
                            latest_response=last_response
                        )
                        if criteria_met:
                            task.summary = f"Task completed - Criteria met: {reasoning}"
                            task.status = TaskStatus.FINISHED
                            db.commit()
                            break
                    except Exception as e:
                        logger.warning(f"Task {task.id}: Error checking criteria: {e}")

                # Check for pending user input (always priority)
                pending_input, pending_images = self.user_input_manager.get_next_pending_user_input_with_images(db, task.id)

                if pending_input:
                    # User input takes priority
                    self.user_input_manager.mark_message_as_sent(db, task.id, pending_input)
                    user_message = pending_input
                    user_images = pending_images
                    self._save_interaction(db, task.id, InteractionType.USER_REQUEST, user_message, images=user_images)
                    logger.info(f"Task {task.id}: Processing user input: {user_message[:50]}...")
                    continue  # Go to next iteration with user input

                # CHAT MODE: Stop and wait for user input
                if task.chat_mode:
                    logger.info(f"Task {task.id}: Chat mode - waiting for user input")
                    task.status = TaskStatus.PAUSED
                    db.commit()
                    break

                # WORK MODE: Use intelligent responder to decide next action
                if not self.intelligent_responder.should_continue_conversation(last_response, iteration, max_iterations):
                    logger.info(f"Task {task.id}: Intelligent responder says conversation complete")
                    task.summary = self._extract_summary(last_response)
                    db.commit()
                    break

                # Generate auto-response for next iteration
                user_message = self.intelligent_responder.generate_response(
                    claude_response=last_response,
                    task_description=task.description,
                    iteration=iteration
                )
                self._save_interaction(db, task.id, InteractionType.SIMULATED_HUMAN, user_message)
                logger.info(f"Task {task.id}: Generated auto-response: {user_message[:50]}...")

            except Exception as e:
                error_str = str(e)
                logger.error(f"Task {task.id}: Error in iteration {iteration}: {error_str}")

                # Check for recoverable errors
                if "Separator is found, but chunk is longer than limit" in error_str:
                    logger.warning(f"Task {task.id}: Chunk size limit - continuing")
                    task.error_message = f"Error during execution: {error_str}"
                    db.commit()
                    continue

                task.error_message = f"Error during execution: {error_str}"
                task.status = TaskStatus.FAILED
                db.commit()
                break

        # Post-loop processing
        if iteration >= max_iterations and task.status == TaskStatus.RUNNING:
            task.status = TaskStatus.EXHAUSTED
            task.error_message = f"Max iterations reached: {iteration}/{max_iterations}"
            db.commit()
        elif task.chat_mode and task.status == TaskStatus.RUNNING:
            # Chat mode ended loop waiting for user input - set to PAUSED
            task.status = TaskStatus.PAUSED
            db.commit()
            logger.info(f"Task {task.id}: Chat mode - set status to PAUSED, waiting for user input")

        # Extract summary if not set
        if not task.summary:
            last_responses = db.query(ClaudeInteraction).filter(
                ClaudeInteraction.task_id == task.id,
                ClaudeInteraction.interaction_type == InteractionType.CLAUDE_RESPONSE
            ).all()
            if last_responses:
                task.summary = self._extract_summary(last_responses[-1].content)
                db.commit()

        # Run tests for completed work mode tasks
        if not task.chat_mode and task.status in [TaskStatus.FINISHED, TaskStatus.COMPLETED, TaskStatus.EXHAUSTED]:
            await self._generate_and_run_tests(db, task, current_project_path)

    async def _send_initial_context(self, db: DBSession, task: Task, project_path: str):
        """
        Send initial context message when task starts.

        This provides Claude with information about all available projects
        and tells it to wait for user instructions.

        Args:
            db: Database session
            task: Task object
            project_path: Current working directory
        """
        print(f"📨 Task {task.id}: Sending initial context message")
        logger.info(f"Task {task.id}: Sending initial context message")

        # Build context message with all projects info
        context_parts = []

        # Task info
        context_parts.append(f"Task: {task.task_name}")
        if task.description:
            context_parts.append(f"Description: {task.description}")

        # Project information
        if task.projects:
            context_parts.append("\n## Available Projects/Repositories:")
            for i, proj in enumerate(task.projects, 1):
                path = proj.get('path', 'unknown')
                description = proj.get('context', 'No description provided')
                access = proj.get('access', 'read')

                context_parts.append(f"\n[{i}] {path}")
                context_parts.append(f"    Description: {description}")
                context_parts.append(f"    Access: {access}")

                # Add IDL/PSM info if available
                psm = proj.get('psm')
                if psm:
                    context_parts.append(f"    PSM: {psm}")
                idl_repo = proj.get('idl_repo')
                if idl_repo:
                    context_parts.append(f"    IDL Repo: {idl_repo}")
        else:
            context_parts.append(f"\nWorking Directory: {project_path}")

        # Instructions to wait - CRITICAL: Tell Claude not to explore proactively
        context_parts.append("\n## Instructions")
        context_parts.append("IMPORTANT: Do NOT explore or read any files proactively.")
        context_parts.append("Do NOT use any tools until the user gives you a specific request.")
        context_parts.append("Simply acknowledge this context and wait for user instructions.")
        context_parts.append("Reply with a brief acknowledgment only.")

        initial_message = "\n".join(context_parts)

        try:
            # Save initial context as SYSTEM_MESSAGE so frontend can display it while Claude processes
            self._save_interaction(db, task.id, InteractionType.SYSTEM_MESSAGE, initial_message)
            db.commit()
            print(f"💬 Task {task.id}: Initial context saved, sending to Claude...", flush=True)

            # Send to Claude
            print(f"📤 Task {task.id}: Calling streaming_client.send_message_streaming...", flush=True)
            response, pid, session_id, usage_data = await self.streaming_client.send_message_streaming(
                message=initial_message,
                project_path=project_path,
                session_id=task.claude_session_id,
                mcp_servers=task.mcp_servers,
            )
            print(f"📥 Task {task.id}: Got response from streaming_client", flush=True)

            # Update session info
            if session_id:
                task.claude_session_id = session_id
            task.process_pid = pid
            db.commit()

            # Save Claude's response
            self._save_interaction(db, task.id, InteractionType.CLAUDE_RESPONSE, response, usage_data)

            # Update token usage
            if usage_data and 'usage' in usage_data:
                output_tokens = usage_data['usage'].get('output_tokens', 0)
                task.total_tokens_used = (task.total_tokens_used or 0) + output_tokens
                db.commit()

            print(f"✅ Task {task.id}: Initial context sent successfully", flush=True)
            logger.info(f"Task {task.id}: Initial context sent successfully")

        except Exception as e:
            print(f"❌ Task {task.id}: Failed to send initial context: {e}", flush=True)
            logger.error(f"Task {task.id}: Failed to send initial context: {e}")
            # Don't fail the task - just log and continue

    async def _execute_iteration(self, db: DBSession, task: Task, project_path: str,
                                  message: str, images: list = None) -> tuple:
        """
        Execute a single iteration - send message to Claude and get response.

        Args:
            db: Database session
            task: Task object
            project_path: Working directory for Claude
            message: Message to send
            images: Optional list of images

        Returns:
            Tuple of (response, pid, session_id, usage_data)
        """
        task.status = TaskStatus.RUNNING
        db.commit()

        # Event handler for real-time saves
        def handle_event(event: dict):
            event_type = event.get('type')

            if event_type == 'assistant':
                message_data = event.get('message', {})
                content = message_data.get('content', [])
                text_parts = []
                tool_uses = []

                for block in content:
                    if block.get('type') == 'text':
                        text_parts.append(block.get('text', ''))
                    elif block.get('type') == 'tool_use':
                        tool_uses.append(block)

                if text_parts or tool_uses:
                    content_str = '\n'.join(text_parts) if text_parts else f"[Tool use: {len(tool_uses)} tools]"
                    self._save_interaction(db, task.id, InteractionType.CLAUDE_RESPONSE, content_str)

            elif event_type == 'user':
                message_data = event.get('message', {})
                content = message_data.get('content', [])
                tool_results = []

                for block in content:
                    if block.get('type') == 'tool_result':
                        tool_id = block.get('tool_use_id', 'unknown')
                        is_error = block.get('is_error', False)
                        result_content = block.get('content', [])
                        result_texts = []

                        for result_block in result_content:
                            if isinstance(result_block, dict) and result_block.get('type') == 'text':
                                result_texts.append(result_block.get('text', ''))
                            elif isinstance(result_block, str):
                                result_texts.append(result_block)

                        full_result_text = ''.join(result_texts)
                        if is_error:
                            tool_results.append(f"Tool {tool_id} ERROR:\n{full_result_text}")
                        else:
                            tool_results.append(f"Tool {tool_id}:\n{full_result_text}")

                if tool_results:
                    self._save_interaction(db, task.id, InteractionType.TOOL_RESULT, '\n\n'.join(tool_results))

        # Send message via streaming client
        response, pid, session_id, usage_data = await self.streaming_client.send_message_streaming(
            message=message,
            project_path=project_path,
            output_callback=None,
            session_id=task.claude_session_id,
            event_callback=handle_event,
            images=images,
            mcp_servers=task.mcp_servers,
        )

        return response, pid, session_id, usage_data

    async def _execute_with_claude_legacy(self, db: DBSession, task: Task, project_path: str):
        """
        Legacy execution method - kept for reference.
        """
        iteration = 0
        pause_count = 0

        # Check if this task already has interactions (indicating a restart)
        existing_interactions = db.query(ClaudeInteraction).filter(
            ClaudeInteraction.task_id == task.id
        ).count()

        is_first_message = existing_interactions == 0
        logger.info(f"Task {task.id}: existing_interactions={existing_interactions}, is_first_message={is_first_message}")

        # Get ending criteria configuration
        end_criteria_config = task.end_criteria_config or {}
        ending_criteria = end_criteria_config.get("criteria")
        max_iterations = end_criteria_config.get("max_iterations", self.max_iterations)
        max_tokens = end_criteria_config.get("max_tokens")

        # Track cumulative tokens
        if task.total_tokens_used is None:
            task.total_tokens_used = 0
            db.commit()

        # Get project context (using simple file-based fallback)
        project_context = self._get_project_context(project_path, task)

        # Build comprehensive initial message
        initial_message = self._build_comprehensive_initial_message(task, project_context)

        # Check for pending user input at startup
        user_input, user_images = self.user_input_manager.get_next_pending_user_input_with_images(db, task.id)

        if user_input:
            self.user_input_manager.mark_message_as_sent(db, task.id, user_input)
            self._save_interaction(db, task.id, InteractionType.USER_REQUEST, user_input, images=user_images)
            db.commit()  # Commit immediately so frontend can display
            initial_message = user_input
            is_first_message = True
        elif is_first_message:
            self._save_interaction(db, task.id, InteractionType.USER_REQUEST, initial_message)
            db.commit()  # Commit immediately so frontend can display
        else:
            is_first_message = False

        last_response = ""
        conversation_history = []
        images_to_send = user_images

        while iteration < max_iterations:
            iteration += 1

            db.refresh(task)
            if task.status == TaskStatus.STOPPED:
                break

            if max_tokens and task.total_tokens_used >= max_tokens:
                task.status = TaskStatus.EXHAUSTED
                task.error_message = f"Max tokens limit reached"
                db.commit()
                break

            try:
                if is_first_message:
                    message_to_send = initial_message
                    is_first_message = False
                else:
                    db.refresh(task)
                    has_pending_user_input = self.user_input_manager.has_pending_input(db, task.id)

                    if task.chat_mode and not has_pending_user_input:
                        task.status = TaskStatus.PAUSED
                        db.commit()
                        break

                    if not has_pending_user_input and not self.intelligent_responder.should_continue_conversation(
                        last_response, iteration, self.max_iterations
                    ):
                        break

                    if pause_count < self.max_pauses:
                        task.status = TaskStatus.PAUSED
                        db.commit()
                        await asyncio.sleep(1)
                        db.refresh(task)

                        user_input, user_images = self.user_input_manager.get_next_pending_user_input_with_images(db, task.id)

                        if user_input:
                            self.user_input_manager.mark_message_as_sent(db, task.id, user_input)
                            human_prompt = user_input
                            current_images = user_images
                            self._save_interaction(db, task.id, InteractionType.USER_REQUEST, human_prompt, images=user_images)
                            db.commit()  # Commit immediately so frontend can display
                        elif task.chat_mode:
                            task.status = TaskStatus.PAUSED
                            db.commit()
                            break
                        else:
                            human_prompt = self.intelligent_responder.generate_response(
                                claude_response=last_response,
                                task_description=task.description,
                                iteration=iteration
                            )
                            current_images = None
                            self._save_interaction(db, task.id, InteractionType.SIMULATED_HUMAN, human_prompt)

                        message_to_send = human_prompt
                        images_to_send = current_images
                        task.status = TaskStatus.RUNNING
                        db.commit()
                        pause_count += 1
                    else:
                        # Max pauses reached, stop
                        break

            except Exception as e:
                task.error_message = f"Error during execution: {str(e)}"
                task.status = TaskStatus.FAILED
                db.commit()
                break

        # Post-loop processing for legacy method
        if iteration >= max_iterations and task.status == TaskStatus.RUNNING:
            task.status = TaskStatus.EXHAUSTED
            task.error_message = f"Max iterations reached"
            db.commit()

    def _build_comprehensive_initial_message(self, task, project_context: str) -> str:
        """
        Build a comprehensive initial message that includes:
        1. Task description
        2. Project descriptions (via project_context)
        3. Ending criteria

        This is used for both task starts and clear/restart operations.
        """
        # Start with task description
        message = f"Task: {task.description}\n\n"

        # Add project context (includes working directory and project descriptions)
        message += project_context

        # Add ending criteria if configured (skip for chat mode - it's interactive)
        is_chat_mode = hasattr(task, 'chat_mode') and task.chat_mode
        if not is_chat_mode and hasattr(task, 'end_criteria_config') and task.end_criteria_config:
            end_criteria_config = task.end_criteria_config

            # Build ending criteria section
            criteria_text = "\n\nEnding Criteria:\n"

            # Success criteria
            if 'criteria' in end_criteria_config and end_criteria_config['criteria']:
                criteria_text += f"- Success Condition: {end_criteria_config['criteria']}\n"

            # Iteration limit
            if 'max_iterations' in end_criteria_config and end_criteria_config['max_iterations']:
                criteria_text += f"- Maximum Iterations: {end_criteria_config['max_iterations']}\n"

            # Token limit
            if 'max_tokens' in end_criteria_config and end_criteria_config['max_tokens']:
                criteria_text += f"- Maximum Tokens: {end_criteria_config['max_tokens']:,}\n"

            # Only add section if we have any criteria
            if criteria_text != "\n\nEnding Criteria:\n":
                message += criteria_text

        # Add closing instructions based on mode
        if is_chat_mode:
            message += "\n\nIMPORTANT: This is an interactive chat session. Do NOT automatically commit changes. Make the code changes but let the user review and decide when to commit."
        else:
            message += "\n\nPlease implement this task. You have permissions for file operations and testing. When complete, provide a summary."

        return message

    async def _run_iteration_planning(self, db: DBSession, task: Task, project_path: str,
                                       user_message: str, is_first_iteration: bool) -> dict:
        """
        Run planning phase for an iteration to determine if code changes are needed.

        Args:
            db: Database session
            task: Task object
            project_path: Current working directory
            user_message: The user's message/request for this iteration
            is_first_iteration: Whether this is the first iteration

        Returns:
            dict with keys:
                - needs_write: bool - whether code changes are needed
                - write_target: str - path to repo that needs write access (if any)
                - plan_response: str - Claude's planning response
                - continue_prompt: str - prompt to continue execution
        """
        logger.info(f"Task {task.id}: Running iteration planning phase")

        # Build projects info from task.projects
        projects_info = ""
        projects_list = ""
        if task.projects:
            for i, proj in enumerate(task.projects, 1):
                path = proj.get('path', 'unknown')
                context = proj.get('context', 'No description')
                access = proj.get('access', 'read')
                projects_info += f"[{i}] {path}\n    Description: {context}\n    Current Access: {access}\n\n"
                projects_list += f"[{i}] {path}\n"
        else:
            # Fallback to single project path
            projects_info = f"[1] {project_path}\n    Description: Main project\n    Current Access: read\n\n"
            projects_list = f"[1] {project_path}\n"

        # Build planning prompt - supports multiple write targets
        if is_first_iteration:
            planning_prompt = f"""PLANNING PHASE - Before starting work, analyze this request.

Request: {user_message}

Available Projects/Repositories:
{projects_info}
Please analyze this request and determine:
1. Does this request require making code changes (creating, editing, or deleting files)?
2. If yes, which project(s) will need to be modified?

Respond with your analysis in this EXACT format:
```planning
NEEDS_WRITE: YES or NO
WRITE_TARGETS: [numbers separated by comma, e.g., 1, 2, 3] or NONE
```

Available project numbers:
{projects_list}
After the planning block, briefly explain your reasoning and provide an implementation plan.
Do NOT make any file changes yet - this is only the planning phase."""
        else:
            # Implementation Prompt - for subsequent iterations after initial planning
            planning_prompt = f"""IMPLEMENTATION PHASE - Continue with the task.

Previous context: We are working on a task. Now proceeding with implementation.

Current request/context: {user_message}

Available Projects/Repositories:
{projects_info}
Current worktrees: {task.worktree_path or 'None (using main repo)'}

IMPORTANT IMPLEMENTATION RULES:

1. DATABASE SCHEMA CHANGES:
   If your changes require database schema modifications (new tables, columns, indexes, etc.):
   - Generate migration SQL files under the RPC project's `sql/` folder
   - Use incremental migration naming (e.g., `001_create_table.sql`, `002_add_column.sql`)
   - Include both UP and DOWN migrations when applicable

2. IDL CHANGES (Thrift/Proto files):
   If your changes require IDL modifications:
   - Make the IDL changes in the IDL repository first
   - Commit and push the IDL changes to the IDL repo's default branch
   - WAIT for the overpass auto-generation to complete (typically takes 1-2 minutes)
   - Then in the RPC/SDK projects, run: `go get -v <overpass_module>@<default_branch>`
     Example: `go get -v code.byted.org/oec/rpcv2_xxx@feat/asbot`
   - Only after the dependency is updated can the RPC/SDK projects be built successfully

3. BUILD ORDER for cross-project changes:
   IDL changes → Push IDL → Wait for overpass → Update go.mod in RPC/SDK → Build RPC/SDK

4. RPC/BACKEND UNIT TESTING:
   After the RPC module is built successfully:
   - Create unit test cases for the new functionality (test the backend logic)
   - Place test files in the appropriate `_test.go` files near the code being tested
   - Run the NEW tests first to verify they pass: `go test -v -tags local -run TestNewFunction ./...`
   - Then run ALL existing tests to ensure no regressions: `go test -v -tags local ./...`
   - Use `-tags local` flag for local mode testing
   - Fix any failing tests before considering the implementation complete

5. COMPLETION CHECKLIST:
   Before marking the task complete, ensure:
   - [ ] Code compiles without errors
   - [ ] New unit tests created and passing
   - [ ] All existing unit tests still passing
   - [ ] Migration SQL generated (if DB changes)
   - [ ] IDL changes committed and pushed (if IDL changes)

Does continuing this work require making code changes?

Respond with:
```planning
NEEDS_WRITE: YES or NO
WRITE_TARGETS: [numbers separated by comma] or NONE or CURRENT
```

Available project numbers:
{projects_list}
Brief explanation, then proceed with implementation."""

        try:
            # Save planning message as SYSTEM_MESSAGE (not user message)
            self._save_interaction(db, task.id, InteractionType.SYSTEM_MESSAGE, planning_prompt)
            db.commit()

            # Send planning message to Claude
            response, pid, session_id, usage_data = await self.streaming_client.send_message_streaming(
                message=planning_prompt,
                project_path=project_path,
                session_id=task.claude_session_id,
                mcp_servers=task.mcp_servers,
            )

            # Update session info
            if session_id:
                task.claude_session_id = session_id
            task.process_pid = pid
            db.commit()

            # Save Claude's response
            self._save_interaction(db, task.id, InteractionType.CLAUDE_RESPONSE, response, usage_data)

            # Update token usage
            if usage_data and 'usage' in usage_data:
                output_tokens = usage_data['usage'].get('output_tokens', 0)
                task.total_tokens_used = (task.total_tokens_used or 0) + output_tokens
                db.commit()

            # Parse planning response - now supports multiple write targets
            needs_write = False
            write_targets = []  # List of paths that need write access
            write_target_nums = []  # List of project numbers

            # Build projects lookup for number-to-path conversion
            projects_lookup = {}
            if task.projects:
                for i, proj in enumerate(task.projects, 1):
                    projects_lookup[i] = proj.get('path', '')

            # Look for planning block
            pattern = r'```planning\s*(.*?)\s*```'
            match = re.search(pattern, response, re.DOTALL | re.IGNORECASE)

            if match:
                planning_text = match.group(1).strip()

                # Parse NEEDS_WRITE
                needs_write_match = re.search(r'NEEDS_WRITE:\s*(YES|NO)', planning_text, re.IGNORECASE)
                if needs_write_match:
                    needs_write = needs_write_match.group(1).upper() == 'YES'

                # Parse WRITE_TARGETS (plural) - can be comma-separated numbers, NONE, or CURRENT
                # Also support legacy WRITE_TARGET (singular)
                write_target_match = re.search(r'WRITE_TARGETS?:\s*(.+)', planning_text, re.IGNORECASE)
                if write_target_match:
                    target_str = write_target_match.group(1).strip()

                    # Check for NONE or CURRENT
                    if target_str.upper() == 'NONE':
                        write_targets = []
                    elif target_str.upper() == 'CURRENT' and task.worktree_path:
                        # Use existing worktrees
                        write_targets = [task.worktree_path]
                    else:
                        # Parse comma-separated numbers (e.g., "1, 2, 3" or "1,2,3" or "[1], [2]")
                        # Find all numbers in the string
                        numbers = re.findall(r'\d+', target_str)
                        for num_str in numbers:
                            num = int(num_str)
                            if num in projects_lookup:
                                path = projects_lookup[num]
                                if path and path not in write_targets:
                                    write_targets.append(path)
                                    write_target_nums.append(num)
                                    logger.info(f"Task {task.id}: Write target {num} -> {path}")
                            else:
                                logger.warning(f"Task {task.id}: Invalid project number {num}")
            else:
                # Fallback: look for keywords indicating write intent
                response_lower = response.lower()
                write_keywords = ['create', 'edit', 'modify', 'update', 'write', 'add', 'delete', 'change', 'implement']
                needs_write = any(keyword in response_lower for keyword in write_keywords)
                if needs_write:
                    write_targets = [task.root_folder or project_path]

            logger.info(f"Task {task.id}: Planning result - needs_write={needs_write}, write_targets={write_targets}")

            # Return results with both singular (for backward compat) and plural
            return {
                'needs_write': needs_write,
                'write_target': write_targets[0] if write_targets else None,  # First target for backward compat
                'write_targets': write_targets,  # All targets
                'write_target_nums': write_target_nums,
                'plan_response': response,
                'continue_prompt': None  # Will be set after worktree creation
            }

        except Exception as e:
            logger.error(f"Task {task.id}: Planning phase failed: {e}")
            # On error, assume write might be needed
            return {
                'needs_write': True,
                'write_target': task.root_folder or project_path,
                'write_targets': [task.root_folder or project_path] if task.root_folder or project_path else [],
                'write_target_nums': [],
                'plan_response': f"Planning failed: {e}",
                'continue_prompt': None
            }

    def _get_write_target_for_task(self, task: Task, fallback_path: str) -> Optional[str]:
        """
        Determine the write target path for a task.

        This is used to pre-create worktrees before the initial context is sent.

        Args:
            task: Task object
            fallback_path: Fallback path if no project is found

        Returns:
            Path to the repository that needs a worktree, or None if not applicable
        """
        # Priority 1: First project with path (regardless of access - we're pre-creating based on branch config)
        if task.projects:
            for project in task.projects:
                project_path = project.get('path', '')
                # Handle comma-separated paths - use first one
                if ',' in project_path:
                    project_path = project_path.split(',')[0].strip()
                if project_path and os.path.exists(project_path):
                    # Check if it's a git repo
                    git_dir = os.path.join(project_path, '.git')
                    if os.path.exists(git_dir):
                        logger.info(f"Task {task.id}: Write target from projects: {project_path}")
                        return project_path

        # Priority 2: Task root_folder
        if task.root_folder and os.path.exists(task.root_folder):
            git_dir = os.path.join(task.root_folder, '.git')
            if os.path.exists(git_dir):
                logger.info(f"Task {task.id}: Write target from root_folder: {task.root_folder}")
                return task.root_folder

        # Priority 3: Fallback path
        if fallback_path and os.path.exists(fallback_path):
            git_dir = os.path.join(fallback_path, '.git')
            if os.path.exists(git_dir):
                logger.info(f"Task {task.id}: Write target from fallback: {fallback_path}")
                return fallback_path

        logger.warning(f"Task {task.id}: No valid git repository found for worktree creation")
        return None

    async def _ensure_worktree_for_target(self, db: DBSession, task: Task, write_target: str) -> str:
        """
        Create a git worktree for a specific write target.

        Unlike _ensure_worktree_for_write, this doesn't check task.worktree_path
        and always tries to create a worktree for the given target.

        Args:
            db: Database session
            task: Task object
            write_target: Path to the repo that needs write access

        Returns:
            Worktree path if created, or the original path if not a git repo
        """
        # Check if write_target is a git repo
        if not write_target or not os.path.exists(write_target):
            logger.warning(f"Task {task.id}: Write target does not exist: {write_target}")
            return write_target or "."

        # Check if this is an IDL project - skip worktree creation for IDL
        project_type = self._get_project_type_for_path(task, write_target)
        if project_type == "idl":
            logger.info(f"Task {task.id}: Skipping worktree for IDL project: {write_target} (using default branch)")
            return write_target

        git_dir = os.path.join(write_target, '.git')
        if not os.path.exists(git_dir):
            logger.info(f"Task {task.id}: Write target is not a git repo, using directly: {write_target}")
            return write_target

        # Create worktree for isolation
        try:
            worktree_manager = self.git_worktree_manager_class(write_target)

            # Determine branch name
            branch_name = task.branch_name or f"task/{task.task_name}"
            base_branch = task.base_branch or "main"

            success, worktree_path, message = worktree_manager.create_worktree(
                task_name=task.task_name,
                branch_name=branch_name,
                base_branch=base_branch
            )

            if success and worktree_path:
                logger.info(f"Task {task.id}: Created worktree at {worktree_path} for {write_target}")

                # Update task branch name if not already set
                if not task.branch_name:
                    task.branch_name = branch_name
                    db.commit()

                return worktree_path
            else:
                logger.warning(f"Task {task.id}: Failed to create worktree for {write_target}: {message}")
                return write_target

        except Exception as e:
            logger.error(f"Task {task.id}: Error creating worktree for {write_target}: {e}")
            return write_target

    async def _ensure_worktree_for_write(self, db: DBSession, task: Task, write_target: str) -> str:
        """
        Ensure a git worktree exists for write operations.

        Args:
            db: Database session
            task: Task object
            write_target: Path to the repo that needs write access

        Returns:
            Path to use for execution (worktree path if created, or existing path)
        """
        # If already have a worktree, use it
        if task.worktree_path and os.path.exists(task.worktree_path):
            logger.info(f"Task {task.id}: Using existing worktree: {task.worktree_path}")
            return task.worktree_path

        # Check if write_target is a git repo
        if not write_target or not os.path.exists(write_target):
            logger.warning(f"Task {task.id}: Write target does not exist: {write_target}")
            return write_target or "."

        git_dir = os.path.join(write_target, '.git')
        if not os.path.exists(git_dir):
            logger.info(f"Task {task.id}: Write target is not a git repo, using directly: {write_target}")
            return write_target

        # Create worktree for isolation
        try:
            worktree_manager = self.git_worktree_manager_class(write_target)

            # Determine branch name
            branch_name = task.branch_name or f"task/{task.task_name}"
            base_branch = task.base_branch or "main"

            # Create worktree
            logger.info(f"Task {task.id}: Creating worktree for branch {branch_name} from {base_branch}")
            success, worktree_path, message = worktree_manager.create_worktree(
                task_name=task.task_name,
                branch_name=branch_name,
                base_branch=base_branch
            )

            if success and worktree_path and os.path.exists(worktree_path):
                # Update task with worktree info
                task.worktree_path = worktree_path
                task.branch_name = branch_name
                db.commit()

                logger.info(f"Task {task.id}: Created worktree at {worktree_path}")
                return worktree_path
            else:
                logger.warning(f"Task {task.id}: Failed to create worktree ({message}), using original path")
                return write_target

        except Exception as e:
            logger.error(f"Task {task.id}: Error creating worktree: {e}")
            return write_target

    def _get_project_type_for_path(self, task: Task, path: str) -> Optional[str]:
        """
        Get the project type for a given path from task's projects configuration.

        Args:
            task: Task object with projects configuration
            path: Path to look up

        Returns:
            Project type string (e.g., 'rpc', 'web', 'idl', 'sdk', 'other') or None if not found
        """
        if not task.projects:
            return None

        # Normalize the path for comparison
        normalized_path = os.path.normpath(path)

        for project in task.projects:
            project_paths_str = project.get('path', '')

            # Handle comma-separated paths
            if ',' in project_paths_str:
                project_paths = [p.strip() for p in project_paths_str.split(',')]
            else:
                project_paths = [project_paths_str.strip()]

            for project_path in project_paths:
                if os.path.normpath(project_path) == normalized_path:
                    return project.get('project_type', 'other')

        return None

    def _get_project_context(self, project_path: str, task) -> str:
        """
        Get context about the project structure for Claude.

        CRITICAL: This function must NOT expose absolute paths to the main repository.
        Claude should only know about the current working directory (worktree for isolated tasks).

        Args:
            project_path: Path to the working directory (worktree for isolated tasks)
            task: Task object to determine if we're in an isolated worktree

        Returns:
            Project context string that only references the current working directory
        """
        import os

        # CRITICAL: Never expose absolute paths that could leak main repository location
        # Claude should only work within the current working directory

        # Handle multi-project mode
        if hasattr(task, 'projects') and task.projects:
            context = "Multi-Project Environment:\n"
            context += "You are working on a task that involves multiple projects.\n\n"

            # CRITICAL: Claude must understand it's working in an isolated worktree
            primary_project = task.projects[0] if task.projects else None
            primary_access = primary_project.get('access', 'write') if primary_project else 'write'

            if primary_access == "write":
                context += f"🔒 ISOLATION MODE: You are working in an ISOLATED WORKTREE ENVIRONMENT\n"
                context += f"Current Working Directory: Isolated worktree (Task: {task.task_name})\n"
                if task.branch_name:
                    context += f"Task Branch: {task.branch_name}\n"
                context += f"⚠️  CRITICAL: ALL your file changes will be made in this isolated environment\n"
                context += f"⚠️  CRITICAL: The main branch will NOT be affected by your changes\n"
                context += f"⚠️  CRITICAL: Use relative paths for ALL file operations\n\n"
            else:
                context += f"Working Directory: Current directory (read-only mode)\n\n"

            context += "Project Configuration:\n"
            idl_projects = []  # Track projects with IDL configuration
            for i, project in enumerate(task.projects, 1):
                project_context = project.get('context', 'No context provided')
                access = project.get('access', 'write')
                branch = project.get('branch_name', 'default')
                idl_repo = project.get('idl_repo')
                idl_file = project.get('idl_file')

                context += f"{i}. {project_context}\n"
                context += f"   - Access: {access}\n"
                if access == "write":
                    context += f"   - Branch: {branch} (🔒 ISOLATED WORKTREE - changes stay here)\n"
                else:
                    context += f"   - Read-only access (reference only)\n"

                # Track IDL configuration
                psm = project.get('psm')
                if idl_repo or psm:
                    idl_info = {'repo': idl_repo, 'file': idl_file, 'psm': psm, 'project_context': project_context}
                    idl_projects.append(idl_info)
                    if psm:
                        context += f"   - PSM: {psm}\n"
                    if idl_repo:
                        context += f"   - IDL Repository: {idl_repo}\n"
                    if idl_file:
                        context += f"   - IDL File: {idl_file}\n"
                context += "\n"

            # Add IDL workflow instructions if any project has IDL configuration
            if idl_projects:
                context += self._get_idl_instructions(idl_projects)

            context += "🔒 ISOLATION INSTRUCTIONS:\n"
            context += "- You are working in an ISOLATED WORKTREE environment\n"
            context += "- ALL file changes you make will be contained in this isolated branch\n"
            context += "- The main branch and other tasks are completely protected\n"
            context += "- Use relative paths (./file.txt, not absolute paths)\n"
            context += "- Your changes will NOT affect the main repository\n\n"

        else:
            # Single project mode
            # For isolated tasks (worktrees), only mention current working directory
            if hasattr(task, 'worktree_path') and task.worktree_path and task.branch_name:
                context = f"Working Directory: Current directory (isolated branch: {task.branch_name})\n"
                context += f"Task Branch: {task.branch_name}\n"
                context += "You are working in a task-specific isolated environment.\n"
            else:
                # Fallback for non-isolated tasks - still avoid absolute path exposure
                context = "Working Directory: Current directory\n"

        # Add project architecture information
        # Priority: 1. User-specified project context, 2. Automatic detection, 3. None
        if hasattr(task, 'project_context') and task.project_context:
            # User provided explicit project context - use that
            context += f"\nProject Context:\n{task.project_context}\n"
            context += "IMPORTANT: You are working in an isolated git worktree/task branch - all changes will be made to this branch only.\n"
        elif not (hasattr(task, 'projects') and task.projects):
            # Only do automatic detection for single-project mode (multi-project has explicit context)
            project_info = self._detect_project_info(project_path)
            if project_info:
                context += f"\nProject Architecture:\n{project_info}"

        try:
            if os.path.exists(project_path):
                # Just indicate directory exists - Claude can explore using relative paths
                context += "\nThe working directory exists and you have full access to explore it.\n"
                context += "Use relative paths for all file operations to ensure proper isolation.\n"
                context += "IMPORTANT: You are working in an isolated git worktree - any changes you make will be committed to your task branch only.\n"

                # Check for specific project structure
                test_dir = os.path.join(project_path, "test")
                if os.path.exists(test_dir):
                    context += "- Found ./test directory with regression test cases\n"

                go_mod = os.path.join(project_path, "go.mod")
                if os.path.exists(go_mod):
                    context += "- Found go.mod file (Go module project)\n"

            else:
                context += "Note: Working directory does not exist yet.\n"
        except Exception as e:
            context += f"Error reading working directory: {str(e)}\n"

        return context

    def _get_idl_instructions(self, idl_projects: list) -> str:
        """
        Generate IDL workflow instructions for projects with IDL configuration.

        This instructs Claude to use the ByteDance overpass MCP tools when working
        with IDL files to regenerate backend code after IDL changes.

        Args:
            idl_projects: List of dicts with keys: repo, file, psm, project_context

        Returns:
            IDL instruction string to include in project context
        """
        instructions = "\n📋 IDL WORKFLOW INSTRUCTIONS:\n"
        instructions += "This project uses IDL (Interface Definition Language) for service definitions.\n\n"

        # List IDL configurations
        instructions += "IDL Configuration:\n"
        for idl in idl_projects:
            if idl.get('psm'):
                instructions += f"  - PSM: {idl['psm']}\n"
            if idl.get('repo'):
                instructions += f"    Repository: {idl['repo']}\n"
            if idl.get('file'):
                instructions += f"    File: {idl['file']}\n"
            instructions += f"    Project: {idl['project_context']}\n"

        # Extract PSM names for tool usage examples
        psm_names = [idl.get('psm') for idl in idl_projects if idl.get('psm')]
        psm_example = psm_names[0] if psm_names else "your.service.psm"

        # Add overpass MCP usage instructions
        instructions += f"""
⚠️  CRITICAL IDL WORKFLOW:
When you make changes to IDL files (*.thrift, *.proto, or other IDL formats), you MUST follow this workflow:

1. **Before modifying IDL**: Use the overpass MCP tools to understand the current state:
   - `get_psm_idl_info` with PSM name (e.g., "{psm_example}") - Get service IDL basic information
   - `get_psm_method_list` with PSM name - Get IDL method list with method names and comments

2. **After modifying IDL**: You MUST regenerate the backend code:
   - `generate_psm_repo` with PSM name - Generate overpass code for the PSM
   - ⚠️  This operation may take several minutes to complete
   - Wait for code generation to finish before proceeding

3. **Verify the changes**: After code generation:
   - Check that the generated code compiles correctly
   - Review the generated client/server stubs
   - Use `get_psm_repo_info` with PSM name to verify code generation repository info

OVERPASS MCP TOOLS AVAILABLE:
- `get_psm_idl_info(psm)`: Get service IDL basic information
- `get_psm_repo_info(psm)`: Get service overpass code generation repository info
- `get_psm_method_list(psm)`: Get IDL method list including GO method names and comments
- `generate_psm_repo(psm)`: Generate overpass code for PSM (REQUIRED after IDL changes)

PSM IDENTIFIER(S) FOR THIS PROJECT: {', '.join(psm_names) if psm_names else 'Not configured - please provide PSM name when using tools'}

IMPORTANT: If you modify any IDL file, the backend service code will be out of sync.
You MUST call `generate_psm_repo` to regenerate the code, otherwise the backend
will not reflect your IDL changes and the service will fail.

"""
        return instructions

    def _detect_project_info(self, project_path: str) -> str:
        """
        Dynamically detect project information based on files and structure.
        Returns project context string that can be added to prompts.
        """
        import os
        import json

        if not os.path.exists(project_path):
            return ""

        info_lines = []

        try:
            # Detect project type and language
            project_type = self._detect_project_type(project_path)
            if project_type:
                info_lines.append(f"- {project_type}")

            # Look for configuration files that might give hints about dependencies
            dependencies = self._detect_dependencies(project_path)
            if dependencies:
                info_lines.extend(dependencies)

            # Check for test directories and mention testing setup
            test_info = self._detect_test_structure(project_path)
            if test_info:
                info_lines.extend(test_info)

            # Look for project configuration files
            config_info = self._detect_project_config(project_path)
            if config_info:
                info_lines.extend(config_info)

        except Exception as e:
            # If detection fails, don't break the whole system
            logger.warning(f"Project detection failed: {e}")
            return ""

        if info_lines:
            return "\n".join(info_lines) + "\n- When making changes, consider impact on project structure and existing functionality\n- IMPORTANT: You are working in an isolated git worktree/task branch - all changes will be made to this branch only\n- All file modifications will automatically be committed to your task branch and will not affect the main branch\n"

        return ""

    def _detect_project_type(self, project_path: str) -> str:
        """Detect the project type based on key files."""
        import os

        # Go project
        if os.path.exists(os.path.join(project_path, "go.mod")):
            return "Go project (detected go.mod)"

        # Python project
        if any(os.path.exists(os.path.join(project_path, f)) for f in ["setup.py", "pyproject.toml", "requirements.txt"]):
            return "Python project"

        # Node.js project
        if os.path.exists(os.path.join(project_path, "package.json")):
            return "Node.js project (detected package.json)"

        # Java project
        if any(os.path.exists(os.path.join(project_path, f)) for f in ["pom.xml", "build.gradle"]):
            return "Java project"

        # Rust project
        if os.path.exists(os.path.join(project_path, "Cargo.toml")):
            return "Rust project (detected Cargo.toml)"

        # C/C++ project
        if any(os.path.exists(os.path.join(project_path, f)) for f in ["Makefile", "CMakeLists.txt"]):
            return "C/C++ project"

        return ""

    def _detect_dependencies(self, project_path: str) -> list:
        """Detect project dependencies based on configuration files."""
        import os
        import json

        deps = []

        # Go dependencies
        go_mod_path = os.path.join(project_path, "go.mod")
        if os.path.exists(go_mod_path):
            try:
                with open(go_mod_path, 'r') as f:
                    content = f.read()
                    # Look for SDK patterns in go.mod
                    if "sdk" in content.lower():
                        deps.append("- Dependencies: Uses SDK modules (detected in go.mod)")
                    elif "require" in content:
                        deps.append("- Dependencies: Uses Go modules (see go.mod)")
            except Exception:
                pass

        # Node.js dependencies
        package_json_path = os.path.join(project_path, "package.json")
        if os.path.exists(package_json_path):
            try:
                with open(package_json_path, 'r') as f:
                    package_data = json.load(f)
                    if package_data.get("dependencies") or package_data.get("devDependencies"):
                        deps.append("- Dependencies: Uses npm packages (see package.json)")
            except Exception:
                pass

        # Python dependencies
        if os.path.exists(os.path.join(project_path, "requirements.txt")):
            deps.append("- Dependencies: Uses Python packages (see requirements.txt)")

        return deps

    def _detect_test_structure(self, project_path: str) -> list:
        """Detect testing structure and configuration."""
        import os

        test_info = []

        # Look for common test directories
        test_dirs = ["test", "tests", "__tests__", "spec"]
        for test_dir in test_dirs:
            test_path = os.path.join(project_path, test_dir)
            if os.path.exists(test_path) and os.path.isdir(test_path):
                test_info.append(f"- Testing: ./{test_dir} directory contains test cases")
                break

        # Look for test configuration files
        test_configs = {
            "pytest.ini": "pytest configuration",
            "jest.config.js": "Jest configuration",
            "go.test": "Go test setup",
            "phpunit.xml": "PHPUnit configuration"
        }

        for config_file, description in test_configs.items():
            if os.path.exists(os.path.join(project_path, config_file)):
                test_info.append(f"- Testing: {description} found")

        return test_info

    def _detect_project_config(self, project_path: str) -> list:
        """Detect project configuration files."""
        import os

        config_info = []

        # Common configuration files
        configs = {
            ".env": "Environment configuration",
            "docker-compose.yml": "Docker composition setup",
            "Dockerfile": "Docker containerization",
            "README.md": "Project documentation available",
            "Makefile": "Build automation with Make"
        }

        for config_file, description in configs.items():
            if os.path.exists(os.path.join(project_path, config_file)):
                config_info.append(f"- Configuration: {description}")

        return config_info

    def _save_interaction(
        self, db: DBSession, task_id: str, interaction_type: InteractionType, content: str, usage_data: Optional[Dict] = None, images: Optional[List[Dict]] = None
    ):
        """Save an interaction to the database with optional usage data and images."""
        interaction = ClaudeInteraction(
            task_id=task_id, interaction_type=interaction_type, content=content, images=images
        )

        # Add usage data if available (from Claude CLI result event)
        if usage_data:
            interaction.duration_ms = usage_data.get('duration_ms')
            interaction.cost_usd = usage_data.get('cost_usd')

            usage = usage_data.get('usage', {})
            interaction.input_tokens = usage.get('input_tokens')
            interaction.output_tokens = usage.get('output_tokens')
            interaction.cache_creation_tokens = usage.get('cache_creation_input_tokens')
            interaction.cache_read_tokens = usage.get('cache_read_input_tokens')

        db.add(interaction)
        db.commit()

    def _is_task_complete(self, response: str) -> bool:
        """
        Determine if the task is complete based on Claude's response.

        Args:
            response: Claude's response

        Returns:
            True if task appears complete
        """
        completion_indicators = [
            "implementation is complete",
            "task is complete",
            "finished implementing",
            "implementation done",
            "completed the task",
            "all done",
            "implementation summary",
            "successfully implemented",
        ]

        response_lower = response.lower()
        return any(indicator in response_lower for indicator in completion_indicators)

    def _extract_summary(self, response: str) -> str:
        """
        Extract a summary from Claude's response.

        Args:
            response: Claude's response

        Returns:
            Extracted summary
        """
        # Try to find summary section
        summary_patterns = [
            r"(?i)summary:?\s*(.+?)(?:\n\n|\Z)",
            r"(?i)implementation summary:?\s*(.+?)(?:\n\n|\Z)",
            r"(?i)what (?:i've|i have) done:?\s*(.+?)(?:\n\n|\Z)",
        ]

        for pattern in summary_patterns:
            match = re.search(pattern, response, re.DOTALL)
            if match:
                return match.group(1).strip()[:500]  # Limit to 500 chars

        # If no summary found, take first 300 characters
        return response[:300] + "..." if len(response) > 300 else response

    async def _generate_and_run_tests(
        self,
        db: DBSession,
        task: Task,
        project_path: str,
    ):
        """
        Generate test cases and run them.

        Args:
            db: Database session
            task: Task object
            project_path: Path to the project
        """
        task.status = TaskStatus.TESTING
        db.commit()

        try:
            # Generate test cases using Claude CLI (with streaming client and session continuity)
            test_message = f"""Based on the following implementation, generate comprehensive pytest test cases.

Task: {task.description}

Implementation Summary: {task.summary or "Task implementation"}

Please generate pytest test cases that thoroughly test this implementation.
Create the test file in the appropriate location in the project.
Return the test code you created."""

            # Use streaming client with session continuity (continues conversation from main task)
            test_code, pid, returned_session_id, usage_data = await self.streaming_client.send_message_streaming(
                message=test_message,
                project_path=project_path,
                session_id=task.claude_session_id,  # Continue the same conversation
                mcp_servers=task.mcp_servers,
            )

            # Update session_id if changed
            if returned_session_id:
                task.claude_session_id = returned_session_id
            task.process_pid = pid
            db.commit()

            # Save test generation interaction with usage data
            self._save_interaction(
                db, task.id, InteractionType.CLAUDE_RESPONSE, test_code, usage_data
            )

            # Validate test code
            is_valid, error_msg = await self.test_runner.validate_test_code(test_code)

            if is_valid:
                # Create test case record
                test_case = TestCase(
                    task_id=task.id,
                    name=f"Generated test for: {task.description[:50]}",
                    description="Auto-generated test case",
                    test_code=test_code,
                    test_type=TestCaseType.GENERATED,
                    status=TestCaseStatus.PENDING,
                )
                db.add(test_case)
                db.commit()

                # Run the test
                success, output = await self.test_runner.run_test(test_code, project_path)

                test_case.status = TestCaseStatus.PASSED if success else TestCaseStatus.FAILED
                test_case.output = output
                db.commit()

            # Run regression tests if they exist
            regression_passed, regression_output, _ = await self.test_runner.run_regression_tests(
                project_path
            )

            # Determine final task status
            all_tests_passed = (
                is_valid
                and all(tc.status == TestCaseStatus.PASSED for tc in task.test_cases)
                and regression_passed
            )

            if all_tests_passed:
                task.status = TaskStatus.COMPLETED
                task.completed_at = datetime.utcnow()
            else:
                task.status = TaskStatus.FAILED
                task.error_message = "Some tests failed"

            db.commit()

        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error_message = f"Error during testing: {str(e)}"
            db.commit()

    def _get_primary_project_path(self, task, session) -> str:
        """
        Get the primary project path for multi-project tasks.
        This is where Claude CLI will be executed from.

        CRITICAL: For write-access projects, this MUST return the worktree path to ensure isolation.
        Never return the main branch path for write-access projects.

        Args:
            task: Task object with projects configuration
            session: Session object with fallback path

        Returns:
            Path to the primary project working directory (worktree for write-access projects)
        """
        # For multi-project tasks, ALWAYS use worktree path for isolated execution
        if task.worktree_path:
            logger.info(f"Task {task.id}: Using task worktree path: {task.worktree_path}")
            return task.worktree_path

        # CRITICAL FIX: For multi-project tasks with write access, construct worktree path
        if task.projects and len(task.projects) > 0:
            primary_project = task.projects[0]
            primary_access = primary_project.get("access", "write")

            if primary_access == "write":
                # Write-access projects must use worktree isolation
                # Construct worktree path based on task name and main repository path
                main_repo_path = primary_project.get("path")
                if main_repo_path and task.task_name:
                    import os
                    # Expected worktree structure: {main_repo}/.claude_worktrees/{task_name}
                    worktree_path = os.path.join(main_repo_path, ".claude_worktrees", task.task_name)

                    # Validate that the worktree exists
                    if os.path.exists(worktree_path) and os.path.isdir(worktree_path):
                        logger.info(f"Task {task.id}: Using constructed worktree path for write-access: {worktree_path}")
                        return worktree_path
                    else:
                        logger.error(f"Task {task.id}: Worktree path does not exist: {worktree_path}")
                        # Fall back to main repo path but this will break isolation
                        logger.warning(f"Task {task.id}: ISOLATION BROKEN - using main repo path: {main_repo_path}")
                        return main_repo_path
                else:
                    logger.error(f"Task {task.id}: Cannot construct worktree path - missing main_repo_path or task.task_name")
            else:
                # Read-only access can use main repository path
                primary_path = primary_project.get("path")
                if primary_path:
                    logger.info(f"Task {task.id}: Using main repo path for read-only access: {primary_path}")
                    return primary_path

        # Fallback to task root_folder or session path
        fallback_path = task.root_folder or (session.project_path if session else ".")
        logger.warning(f"Task {task.id}: Using fallback path: {fallback_path}")
        return fallback_path

    def _validate_multi_project_worktrees(self, task) -> Dict[str, any]:
        """
        Validate that all module worktrees are accessible for multi-project tasks.

        CRITICAL: For write-access modules, this validates the WORKTREE paths, not main repo paths.

        Args:
            task: Task object with projects configuration

        Returns:
            Dict with 'success' boolean and optional 'error' message
        """
        import os
        import subprocess

        # Use parsed modules if available, otherwise fall back to projects config
        if hasattr(task, '_parsed_modules') and task._parsed_modules:
            write_modules = [m for m in task._parsed_modules if m.get("access") == "write"]
        else:
            # Fallback: parse from projects (handles comma-separated paths)
            write_modules = []
            for project in (task.projects or []):
                if project.get("access") == "write":
                    paths_str = project.get("path", "")
                    if ',' in paths_str:
                        for path in paths_str.split(','):
                            path = path.strip()
                            if path:
                                write_modules.append({"path": path})
                    elif paths_str:
                        write_modules.append({"path": paths_str})

        for module in write_modules:
            module_path = module.get("path")
            if not module_path:
                continue

            # Check for worktree_path directly in module (set during worktree creation)
            worktree_path = module.get("worktree_path")

            # If not set, construct expected worktree path
            if not worktree_path and task.task_name:
                # Sanitize task name for directory
                safe_task_name = task.task_name.replace("/", "_").replace(" ", "_")
                worktree_path = os.path.join(module_path, ".claude_worktrees", safe_task_name)

            if not worktree_path:
                continue

            # Validate worktree exists
            if not os.path.exists(worktree_path) or not os.path.isdir(worktree_path):
                return {
                    "success": False,
                    "error": f"Module worktree path not found: {worktree_path} (module: {module_path})"
                }

            # Verify git worktree for write-access modules
            try:
                result = subprocess.run(
                    ["git", "rev-parse", "--is-inside-work-tree"],
                    cwd=worktree_path,
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode != 0:
                    return {
                        "success": False,
                        "error": f"Worktree path is not a valid git worktree: {worktree_path}"
                    }

                # Also validate that it's on the expected branch
                branch_result = subprocess.run(
                    ["git", "branch", "--show-current"],
                    cwd=worktree_path,
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if branch_result.returncode == 0:
                    current_branch = branch_result.stdout.strip()
                    expected_branch = module.get('branch_name', task.branch_name)
                    if expected_branch and current_branch != expected_branch:
                        logger.warning(f"Task {task.id}: Worktree branch mismatch. Expected: {expected_branch}, Current: {current_branch}")
                    else:
                        logger.info(f"Task {task.id}: Worktree validation successful for {module_path} - branch: {current_branch}")

            except Exception as e:
                return {
                    "success": False,
                    "error": f"Could not validate git worktree for {worktree_path}: {e}"
                }

        return {"success": True}

    def _parse_module_paths(self, task: Task) -> List[Dict[str, str]]:
        """
        Parse comma-separated paths in project config to get individual modules.

        Each project's path field can contain comma-separated paths, where each
        path is an independent git repo (module).

        Args:
            task: Task object with projects configuration

        Returns:
            List of module dicts with 'path', 'context', 'project_index' keys
        """
        modules = []

        if not task.projects:
            return modules

        for project_idx, project in enumerate(task.projects):
            paths_str = project.get('path', '')
            context = project.get('context', 'No context provided')

            # Split comma-separated paths
            if ',' in paths_str:
                individual_paths = [p.strip() for p in paths_str.split(',') if p.strip()]
            else:
                individual_paths = [paths_str.strip()] if paths_str.strip() else []

            # Create a module entry for each individual path
            for path in individual_paths:
                if path and os.path.exists(path):
                    # Try to get module name from path
                    module_name = os.path.basename(path.rstrip('/'))
                    modules.append({
                        'path': path,
                        'context': context,
                        'module_name': module_name,
                        'project_index': project_idx,
                        'access': 'read'  # Start with read-only
                    })
                else:
                    logger.warning(f"Task {task.id}: Module path does not exist: {path}")

        logger.info(f"Task {task.id}: Parsed {len(modules)} modules from project config")
        return modules

    async def _run_planning_phase(self, db: DBSession, task: Task, project_path: str) -> List[str]:
        """
        Run planning phase to identify which modules need write access.

        Claude analyzes the task and identifies which modules (individual git repos)
        need modification. Returns list of module paths that need write access.

        Args:
            db: Database session
            task: Task object
            project_path: Initial project path (read-only access)

        Returns:
            List of module paths that need write access
        """
        logger.info(f"Task {task.id}: Running planning phase to identify write targets")

        # Parse all modules from project config (handles comma-separated paths)
        modules = self._parse_module_paths(task)

        if not modules:
            logger.warning(f"Task {task.id}: No valid modules found in project config")
            return []

        # Store parsed modules in task for later use
        task._parsed_modules = modules

        # Build planning prompt with individual modules - use numbered list with exact paths
        modules_info = ""
        modules_list = ""
        for i, module in enumerate(modules, 1):
            path = module.get('path', 'unknown')
            module_name = module.get('module_name', 'unknown')
            context = module.get('context', 'No context')
            modules_info += f"[{i}] {path}\n    Name: {module_name}\n    Context: {context}\n\n"
            modules_list += f"[{i}] {path}\n"

        planning_prompt = f"""PLANNING PHASE - Analyze this task and identify which modules need modification.

Task Description: {task.description}

Available Modules (each is an independent git repository):
{modules_info}
CRITICAL INSTRUCTION - You MUST respond with EXACTLY this format:

```write_targets
[numbers of modules that need write access, one per line]
```

Example - if modules [1] and [3] need modification:
```write_targets
1
3
```

Example - if no modules need modification:
```write_targets
NONE
```

Available module numbers:
{modules_list}
RULES:
- ONLY output numbers (1, 2, 3, etc.) or NONE inside the write_targets block
- Do NOT include paths, names, or any other text inside the block
- One number per line
- Numbers must match the module list above

After the write_targets block, explain your reasoning and provide a brief implementation plan.
Do NOT make any file changes yet - this is only the planning phase."""

        try:
            # Save planning message as SYSTEM_MESSAGE (not user message)
            self._save_interaction(db, task.id, InteractionType.SYSTEM_MESSAGE, planning_prompt)
            db.commit()

            # Send planning message to Claude
            response, pid, session_id, usage_data = await self.streaming_client.send_message_streaming(
                message=planning_prompt,
                project_path=project_path,
                session_id=task.claude_session_id,
                mcp_servers=task.mcp_servers,
            )

            # Store session_id for conversation continuity
            if session_id:
                task.claude_session_id = session_id
            task.process_pid = pid
            db.commit()

            # Save Claude's response
            self._save_interaction(db, task.id, InteractionType.CLAUDE_RESPONSE, response, usage_data)

            # Parse write targets from response (use parsed modules)
            write_targets = self._parse_write_targets(response, modules)

            logger.info(f"Task {task.id}: Planning phase identified write targets: {write_targets}")
            return write_targets

        except Exception as e:
            logger.error(f"Task {task.id}: Planning phase failed: {e}")
            # On error, fall back to write access for all modules
            return [m.get('path') for m in modules if m.get('path')]

    def _parse_write_targets(self, response: str, modules: List[Dict]) -> List[str]:
        """
        Parse Claude's response to extract write target paths.

        Expects Claude to respond with module numbers (1-indexed) in a write_targets block.

        Args:
            response: Claude's planning response
            modules: List of module configurations (parsed from project config)

        Returns:
            List of module paths that need write access
        """
        write_targets = []

        # Look for write_targets block
        pattern = r'```write_targets\s*(.*?)\s*```'
        match = re.search(pattern, response, re.DOTALL | re.IGNORECASE)

        if match:
            targets_text = match.group(1).strip()
            if targets_text.upper() != 'NONE':
                # Parse module numbers
                for line in targets_text.split('\n'):
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue

                    # Try to extract number from the line
                    # Handle formats like "1", "[1]", "1.", "1)", etc.
                    num_match = re.search(r'^\[?(\d+)\]?[.):]?\s*$', line)
                    if num_match:
                        module_num = int(num_match.group(1))
                        # Convert 1-indexed to 0-indexed
                        module_idx = module_num - 1
                        if 0 <= module_idx < len(modules):
                            module_path = modules[module_idx].get('path', '')
                            if module_path and module_path not in write_targets:
                                write_targets.append(module_path)
                                logger.info(f"Planning: Module {module_num} ({module_path}) needs write access")
                        else:
                            logger.warning(f"Planning: Invalid module number {module_num}, max is {len(modules)}")
                    else:
                        # Fallback: try to match as path
                        for module in modules:
                            module_path = module.get('path', '')
                            if line == module_path or module_path.endswith('/' + line):
                                if module_path not in write_targets:
                                    write_targets.append(module_path)
                                    logger.info(f"Planning: Module path {module_path} needs write access")
                                break
        else:
            logger.warning("Planning: No write_targets block found in response")

        return write_targets

    async def _create_dynamic_worktrees(self, db: DBSession, task: Task, write_targets: List[str]) -> Dict[str, str]:
        """
        Dynamically create git worktrees for modules that need write access.

        Each module is an independent git repo. Worktrees are created with the task name
        to provide isolation for code changes.

        Args:
            db: Database session
            task: Task object
            write_targets: List of module paths needing write access

        Returns:
            Dict mapping original module paths to worktree paths
        """
        worktree_map = {}

        if not write_targets:
            logger.info(f"Task {task.id}: No write targets - skipping worktree creation")
            return worktree_map

        # Generate branch name from task (used for all modules)
        branch_name = task.branch_name
        if not branch_name:
            sanitized_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', task.task_name)
            sanitized_name = re.sub(r'_+', '_', sanitized_name).strip('_')
            branch_name = f"task/{sanitized_name}"

        logger.info(f"Task {task.id}: Creating worktrees for {len(write_targets)} modules with branch '{branch_name}'")

        for module_path in write_targets:
            try:
                # Check if it's a git repo
                import subprocess
                result = subprocess.run(
                    ["git", "rev-parse", "--git-dir"],
                    cwd=module_path,
                    capture_output=True,
                    text=True,
                    timeout=5
                )

                if result.returncode != 0:
                    logger.warning(f"Task {task.id}: {module_path} is not a git repo, skipping worktree")
                    continue

                # Create worktree for this module
                git_manager = self.git_worktree_manager_class(module_path)

                # Use task name for worktree (creates worktree at {module}/.claude_worktrees/{task_name})
                success, worktree_path, message = git_manager.create_worktree(
                    task.task_name,
                    branch_name,
                    task.base_branch
                )

                if success:
                    worktree_map[module_path] = worktree_path
                    logger.info(f"Task {task.id}: Created worktree for module {module_path} -> {worktree_path}")

                    # Update parsed modules if available
                    if hasattr(task, '_parsed_modules') and task._parsed_modules:
                        for module in task._parsed_modules:
                            if module.get('path') == module_path:
                                module['access'] = 'write'
                                module['worktree_path'] = worktree_path
                                break
                else:
                    logger.error(f"Task {task.id}: Failed to create worktree for module {module_path}: {message}")

            except Exception as e:
                logger.error(f"Task {task.id}: Error creating worktree for module {module_path}: {e}")

        # Update task with worktree info
        if worktree_map:
            # Use first worktree as primary working path
            task.worktree_path = list(worktree_map.values())[0]
            task.branch_name = branch_name

            # Store all worktree mappings in task for reference
            if not hasattr(task, '_worktree_map'):
                task._worktree_map = {}
            task._worktree_map.update(worktree_map)

            db.commit()
            logger.info(f"Task {task.id}: Created {len(worktree_map)} worktrees, primary: {task.worktree_path}")

        return worktree_map
