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

    async def execute_task(self, task_id: str):
        """
        Execute a task asynchronously.

        Args:
            task_id: ID of the task to execute
        """
        print(f"🔥 EXECUTE_TASK DEBUG: Starting execution for task {task_id}")
        db = SessionLocal()
        try:
            task = db.query(Task).filter(Task.id == task_id).first()
            if not task:
                print(f"🔥 EXECUTE_TASK DEBUG: Task {task_id} not found")
                return

            print(f"🔥 EXECUTE_TASK DEBUG: Found task {task.task_name}, current status: {task.status}")

            # Update task status (only if not stopped)
            task.status = TaskStatus.RUNNING
            db.commit()
            print(f"🔥 EXECUTE_TASK DEBUG: Updated task status to RUNNING")

            # Get session for project context
            session = db.query(Session).filter(Session.id == task.session_id).first()

            # Handle multi-project tasks with multiple worktrees
            if hasattr(task, 'projects') and task.projects:
                # Multi-project task: Use the main project's worktree as primary working directory
                # Additional project worktrees are available through relative paths
                project_path = self._get_primary_project_path(task, session)
                logger.info(f"Task {task.id}: Multi-project task using primary path: {project_path}")

                # Validate all project worktrees are accessible
                validation_result = self._validate_multi_project_worktrees(task)
                if not validation_result["success"]:
                    task.status = TaskStatus.FAILED
                    task.error_message = validation_result["error"]
                    db.commit()
                    return

            elif task.worktree_path:
                # Single-project task with worktree isolation
                # Validate that worktree path exists and is a valid directory
                import os
                if not os.path.exists(task.worktree_path) or not os.path.isdir(task.worktree_path):
                    logger.error(f"Task {task.id}: Worktree path {task.worktree_path} does not exist or is not a directory")
                    task.status = TaskStatus.FAILED
                    task.error_message = f"Worktree path not found: {task.worktree_path}"
                    db.commit()
                    return
                project_path = task.worktree_path

                # Additional validation: verify the worktree is on the correct branch
                try:
                    import subprocess
                    result = subprocess.run(
                        ["git", "branch", "--show-current"],
                        cwd=project_path,
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    current_branch = result.stdout.strip()
                    if task.branch_name and current_branch != task.branch_name:
                        logger.error(f"Task {task.id}: Worktree branch mismatch. Expected: {task.branch_name}, Current: {current_branch}")
                        task.status = TaskStatus.FAILED
                        task.error_message = f"Branch mismatch in worktree. Expected: {task.branch_name}, Current: {current_branch}"
                        db.commit()
                        return
                    logger.info(f"Task {task.id}: Using worktree path for isolation: {project_path} (branch: {current_branch})")
                except Exception as e:
                    logger.warning(f"Task {task.id}: Could not verify branch in worktree: {e}")
            else:
                # Fallback to root_folder or session path for tasks without worktrees
                # IMPORTANT FIX: Ensure we have a valid project path, not just "."
                import os
                if task.root_folder and os.path.exists(task.root_folder):
                    project_path = task.root_folder
                    logger.info(f"Task {task.id}: Using task root_folder as project path: {project_path}")
                elif session and hasattr(session, 'project_path') and session.project_path and os.path.exists(session.project_path):
                    project_path = session.project_path
                    logger.info(f"Task {task.id}: Using session project_path: {project_path}")
                else:
                    # Last resort: Use current working directory, but this should be avoided
                    project_path = "."
                    logger.warning(f"Task {task.id}: No valid project path found, falling back to current directory (this may cause issues)")

            # Execute the task with Claude
            await self._execute_with_claude(db, task, project_path)

        except Exception as e:
            task = db.query(Task).filter(Task.id == task_id).first()
            if task:
                task.status = TaskStatus.FAILED
                task.error_message = str(e)
                db.commit()
        finally:
            db.close()

    async def _execute_with_claude(self, db: DBSession, task: Task, project_path: str):
        """
        Execute task with Claude CLI, handling conversation and pauses.

        Args:
            db: Database session
            task: Task to execute
            project_path: Path to the project
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
        # CRITICAL: Only provide the working directory path to Claude (worktree for isolation)
        # Never expose the main repository path to prevent cross-branch contamination
        project_context = self._get_project_context(project_path, task)

        # Build comprehensive initial message with task description, project context, and ending criteria
        initial_message = self._build_comprehensive_initial_message(task, project_context)

        # ALWAYS check for pending user input at startup (both new tasks and restarts)
        print(f"🔍 STARTUP DEBUG: Checking for pending user input for task {task.id}")

        # Use new status-based deduplication: only process messages that haven't been sent yet
        user_input = self.user_input_manager.get_next_pending_user_input(db, task.id)
        print(f"🔍 STARTUP DEBUG: get_next_pending_user_input returned: {user_input}")

        if user_input:
            # User input takes priority - process it immediately
            print(f"🔍 STARTUP DEBUG: Found pending user input, processing: {user_input[:50]}...")
            logger.info(f"Task {task.id}: Processing pending user input at startup: {user_input[:50]}...")

            # CRITICAL: Mark message as sent BEFORE sending to Claude to prevent duplicates
            self.user_input_manager.mark_message_as_sent(db, task.id, user_input)

            # Save as USER_REQUEST interaction
            self._save_interaction(db, task.id, InteractionType.USER_REQUEST, user_input)
            # Use user input as the message to send
            initial_message = user_input
            is_first_message = True  # Always treat user input as the first message
            print(f"🔍 STARTUP DEBUG: Set user input as first message")
        elif is_first_message:
            # No user input and this is a new task - send initial task description
            self._save_interaction(
                db, task.id, InteractionType.USER_REQUEST, initial_message
            )
            logger.info(f"Task {task.id}: Saved initial interaction for new task")
            print(f"🔍 STARTUP DEBUG: No user input found, using initial task message")
        else:
            # No user input and this is a restart - skip initial message
            logger.info(f"Task {task.id}: Skipping initial interaction - task restart with no user input")
            print(f"🔍 STARTUP DEBUG: No user input found on restart, skipping initial message")
            # Set a flag to skip the first iteration
            is_first_message = False

        last_response = ""
        conversation_history = []  # Track conversation for criteria checking

        while iteration < max_iterations:
            iteration += 1
            print(f"🔥 TASK EXECUTOR DEBUG: Starting iteration {iteration} for task {task.id}")

            # Check if task was stopped
            db.refresh(task)
            if task.status == TaskStatus.STOPPED:
                print(f"🔥 TASK EXECUTOR DEBUG: Task {task.id} was stopped, breaking")
                break

            # Check if max tokens limit reached
            if max_tokens and task.total_tokens_used >= max_tokens:
                task.status = TaskStatus.EXHAUSTED
                task.error_message = f"Max tokens limit reached: {task.total_tokens_used}/{max_tokens} tokens used"
                db.commit()
                break

            try:
                # Send message to Claude CLI
                if is_first_message:
                    message_to_send = initial_message
                    is_first_message = False
                else:
                    # CRITICAL FIX: Always check for user input first before deciding to stop
                    db.refresh(task)  # Refresh to get latest state
                    has_pending_user_input = self.user_input_manager.has_pending_input(db, task.id)

                    logger.info(f"Task {task.id} iteration {iteration}: pending_user_input={has_pending_user_input}")

                    # If no user input is pending, check if we should continue based on last response
                    if not has_pending_user_input and not self.intelligent_responder.should_continue_conversation(
                        last_response, iteration, self.max_iterations
                    ):
                        logger.info(f"Task {task.id}: No user input pending and should not continue conversation - breaking")
                        break

                    if has_pending_user_input:
                        logger.info(f"Task {task.id}: User input pending - forcing continuation to process input")

                    # Use intelligent responder to generate context-aware reply
                    if pause_count < self.max_pauses:
                        task.status = TaskStatus.PAUSED
                        db.commit()

                        # Wait a bit to simulate human thinking
                        await asyncio.sleep(1)

                        # HIGH PRIORITY: Check for user input first (never overlook user input)
                        db.refresh(task)  # Refresh to get latest state

                        logger.info(f"Task {task.id}: Checking for user input in pause cycle")

                        # Use new status-based deduplication: only process messages that haven't been sent yet
                        user_input = self.user_input_manager.get_next_pending_user_input(db, task.id)

                        if user_input:
                            logger.info(f"Task {task.id}: Found pending user input in queue: {user_input[:50]}...")
                            # CRITICAL: Mark message as sent BEFORE sending to Claude to prevent duplicates
                            self.user_input_manager.mark_message_as_sent(db, task.id, user_input)
                        else:
                            logger.info(f"Task {task.id}: No pending user input found in queue")

                        # Fallback to legacy custom_human_input for backward compatibility
                        if not user_input and task.custom_human_input:
                            user_input = task.custom_human_input
                            task.custom_human_input = None
                            db.commit()

                        if user_input:
                            # USER INPUT TAKES ABSOLUTE PRIORITY
                            human_prompt = user_input

                            # Save as REAL human interaction
                            self.user_input_manager.save_user_interaction(
                                db, task.id, human_prompt
                            )

                            logger.info(f"Processing user input for task {task.id}: {human_prompt[:50]}...")
                        else:
                            # Only generate simulated human if NO user input is pending
                            human_prompt = self.intelligent_responder.generate_response(
                                claude_response=last_response,
                                task_description=task.description,
                                iteration=iteration
                            )

                            # Save simulated human interaction
                            self._save_interaction(
                                db, task.id, InteractionType.SIMULATED_HUMAN, human_prompt
                            )

                            logger.info(f"Generated simulated human input for task {task.id}: {human_prompt[:50]}...")

                        message_to_send = human_prompt

                        task.status = TaskStatus.RUNNING
                        db.commit()
                        pause_count += 1
                    else:
                        # Max pauses reached, stop
                        break

                # Get Claude's response via CLI (using streaming client)
                # Save events to DB in real-time as they arrive
                def handle_event(event: dict):
                    """Process and save stream events in real-time."""
                    event_type = event.get('type')
                    print(f"🔥 HANDLE_EVENT DEBUG: Received event type: {event_type}, event: {event}")
                    logger.info(f"HANDLE_EVENT: Received event type: {event_type}")

                    # Save assistant messages (Claude's responses)
                    if event_type == 'assistant':
                        print(f"🔥 HANDLE_EVENT DEBUG: Processing assistant event")
                        message_data = event.get('message', {})
                        content = message_data.get('content', [])
                        print(f"🔥 HANDLE_EVENT DEBUG: message_data: {message_data}")
                        print(f"🔥 HANDLE_EVENT DEBUG: content: {content}")

                        # Extract text and tool uses from content
                        text_parts = []
                        tool_uses = []
                        for block in content:
                            if block.get('type') == 'text':
                                text_parts.append(block.get('text', ''))
                            elif block.get('type') == 'tool_use':
                                tool_uses.append(block)

                        print(f"🔥 HANDLE_EVENT DEBUG: text_parts: {text_parts}")
                        print(f"🔥 HANDLE_EVENT DEBUG: tool_uses: {tool_uses}")

                        # Save as interaction if there's text or tool use
                        if text_parts or tool_uses:
                            content_str = '\n'.join(text_parts) if text_parts else f"[Tool use: {len(tool_uses)} tools]"
                            print(f"🔥 HANDLE_EVENT DEBUG: Saving interaction with content: {content_str[:100]}...")
                            self._save_interaction(
                                db, task.id, InteractionType.CLAUDE_RESPONSE, content_str
                            )
                            print(f"🔥 HANDLE_EVENT DEBUG: Interaction saved successfully")
                        else:
                            print(f"🔥 HANDLE_EVENT DEBUG: No text or tool use found, skipping interaction save")

                    # Save user messages (tool results)
                    elif event_type == 'user':
                        message_data = event.get('message', {})
                        content = message_data.get('content', [])

                        # Extract tool results
                        tool_results = []
                        for block in content:
                            if block.get('type') == 'tool_result':
                                tool_id = block.get('tool_use_id', 'unknown')
                                is_error = block.get('is_error', False)
                                result_content = block.get('content', [])

                                # Collect all text from result content blocks
                                result_texts = []
                                for result_block in result_content:
                                    if isinstance(result_block, dict) and result_block.get('type') == 'text':
                                        result_texts.append(result_block.get('text', ''))
                                    elif isinstance(result_block, str):
                                        # Sometimes content is just a string
                                        result_texts.append(result_block)

                                # Join with empty string instead of newlines to fix vertical text issue
                                full_result_text = ''.join(result_texts)

                                # Format the tool result with tool_id and full content
                                if is_error:
                                    tool_results.append(f"Tool {tool_id} ERROR:\n{full_result_text}")
                                else:
                                    tool_results.append(f"Tool {tool_id}:\n{full_result_text}")

                        if tool_results:
                            self._save_interaction(
                                db, task.id, InteractionType.TOOL_RESULT, '\n\n'.join(tool_results)
                            )

                # Use streaming client with event callback for real-time DB saves
                print(f"🔥 TASK EXECUTOR DEBUG: About to call streaming client for task {task.id}")
                print(f"🔥 TASK EXECUTOR DEBUG: message_to_send: {message_to_send[:100]}...")
                print(f"🔥 TASK EXECUTOR DEBUG: project_path: {project_path}")
                print(f"🔥 TASK EXECUTOR DEBUG: session_id: {task.claude_session_id}")

                response, pid, returned_session_id, usage_data = await self.streaming_client.send_message_streaming(
                    message=message_to_send,
                    project_path=project_path,
                    output_callback=None,
                    session_id=task.claude_session_id,  # Pass existing session_id or None for first message
                    event_callback=handle_event,  # Process events in real-time
                )

                print(f"🔥 TASK EXECUTOR DEBUG: Streaming client returned, response length: {len(response) if response else 0}")
                print(f"🔥 TASK EXECUTOR DEBUG: PID: {pid}, session_id: {returned_session_id}")

                # Store PID and session_id for process management and conversation continuity
                task.process_pid = pid
                if returned_session_id:
                    task.claude_session_id = returned_session_id
                    print(f"🔍 TASK EXECUTOR DEBUG: task_id={task.id}, set claude_session_id={returned_session_id}")
                    logger.info(f"Task executor set claude_session_id: {returned_session_id} for task {task.id}")
                db.commit()

                # Track cumulative output tokens from usage data
                if usage_data and 'usage' in usage_data:
                    output_tokens = usage_data['usage'].get('output_tokens', 0)
                    task.total_tokens_used = (task.total_tokens_used or 0) + output_tokens
                    db.commit()

                # Note: We no longer save the final response here since interactions
                # are saved in real-time via the event_callback

                # Store for next iteration
                last_response = response
                conversation_history.append(response)

                # Check if task meets ending criteria (if defined)
                criteria_met = False
                if ending_criteria:
                    try:
                        # Check if ending criteria is met
                        criteria_met, reasoning = await self.criteria_analyzer.check_task_completion(
                            ending_criteria=ending_criteria,
                            task_description=task.description,
                            conversation_history="\n\n".join(conversation_history[-3:]),  # Last 3 responses
                            latest_response=last_response
                        )

                        if criteria_met:
                            task.summary = f"Task completed - Criteria met: {reasoning}"
                            task.status = TaskStatus.FINISHED
                            db.commit()
                            break
                    except Exception as e:
                        print(f"Error checking ending criteria: {e}")

                # Fallback: Check if task seems complete using old heuristic
                # CRITICAL: Don't mark task as complete if user input is pending
                has_pending_user_input = self.user_input_manager.has_pending_input(db, task.id)
                if not criteria_met and not has_pending_user_input and self._is_task_complete(response):
                    task.summary = self._extract_summary(response)
                    db.commit()
                    break
                elif has_pending_user_input:
                    logger.info(f"Task {task.id}: Not marking as complete - user input pending")

            except Exception as e:
                error_str = str(e)

                # Check for recoverable chunk size limit errors
                if "Separator is found, but chunk is longer than limit" in error_str:
                    logger.warning(f"Task {task.id}: Chunk size limit reached - setting error message but continuing")
                    task.error_message = f"Error during execution: {error_str}"
                    db.commit()
                    # Don't break - let the task continue with the next iteration
                    continue

                # For all other errors, set error and break
                task.error_message = f"Error during execution: {error_str}"
                db.commit()
                break

        # Check if loop ended due to hitting max iterations
        if iteration >= max_iterations and task.status == TaskStatus.RUNNING:
            # Max iterations reached without completing
            task.status = TaskStatus.EXHAUSTED
            task.error_message = f"Max iterations limit reached: {iteration}/{max_iterations} iterations completed without meeting ending criteria"
            db.commit()

        # If no summary yet, try to extract from last response
        if not task.summary:
            # Get last Claude response
            last_responses = [i for i in db.query(ClaudeInteraction).filter(
                ClaudeInteraction.task_id == task.id,
                ClaudeInteraction.interaction_type == InteractionType.CLAUDE_RESPONSE
            ).all()]
            if last_responses:
                task.summary = self._extract_summary(last_responses[-1].content)
                db.commit()

        # Generate and run tests only if task is complete and no user input is pending
        has_pending_user_input = self.user_input_manager.has_pending_input(db, task.id)
        if not has_pending_user_input and task.status in [TaskStatus.FINISHED, TaskStatus.COMPLETED, TaskStatus.EXHAUSTED]:
            await self._generate_and_run_tests(db, task, project_path)
        elif has_pending_user_input:
            logger.info(f"Task {task.id}: Skipping test generation - user input pending")
        else:
            logger.info(f"Task {task.id}: Task not finished (status: {task.status}) - skipping test generation")

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

        # Add ending criteria if configured
        if hasattr(task, 'end_criteria_config') and task.end_criteria_config:
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

        # Add standard closing instructions
        message += "\n\nPlease implement this task. You have permissions for file operations and testing. When complete, provide a summary."

        return message

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
            for i, project in enumerate(task.projects, 1):
                project_context = project.get('context', 'No context provided')
                access = project.get('access', 'write')
                branch = project.get('branch_name', 'default')

                context += f"{i}. {project_context}\n"
                context += f"   - Access: {access}\n"
                if access == "write":
                    context += f"   - Branch: {branch} (🔒 ISOLATED WORKTREE - changes stay here)\n"
                else:
                    context += f"   - Read-only access (reference only)\n"
                context += "\n"

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
        self, db: DBSession, task_id: str, interaction_type: InteractionType, content: str, usage_data: Optional[Dict] = None
    ):
        """Save an interaction to the database with optional usage data."""
        interaction = ClaudeInteraction(
            task_id=task_id, interaction_type=interaction_type, content=content
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
        Validate that all project worktrees are accessible for multi-project tasks.

        CRITICAL: For write-access projects, this validates the WORKTREE paths, not main repo paths.

        Args:
            task: Task object with projects configuration

        Returns:
            Dict with 'success' boolean and optional 'error' message
        """
        import os

        # For multi-project tasks, validate all write-access projects have proper isolation
        write_projects = [p for p in task.projects if p.get("access") == "write"]

        for project in write_projects:
            main_repo_path = project.get("path")
            if not main_repo_path:
                continue

            # CRITICAL FIX: For write-access projects, validate the WORKTREE path, not main repo path
            if task.task_name:
                # Construct expected worktree path
                worktree_path = os.path.join(main_repo_path, ".claude_worktrees", task.task_name)

                # Validate worktree exists
                if not os.path.exists(worktree_path) or not os.path.isdir(worktree_path):
                    return {
                        "success": False,
                        "error": f"Multi-project worktree path not found: {worktree_path} (derived from main repo: {main_repo_path})"
                    }

                # Verify git worktree for write-access projects
                try:
                    import subprocess
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
                        expected_branch = project.get('branch_name', task.branch_name)
                        if expected_branch and current_branch != expected_branch:
                            logger.warning(f"Task {task.id}: Worktree branch mismatch. Expected: {expected_branch}, Current: {current_branch}")
                        else:
                            logger.info(f"Task {task.id}: Worktree validation successful - branch: {current_branch}")

                except Exception as e:
                    return {
                        "success": False,
                        "error": f"Could not validate git worktree for {worktree_path}: {e}"
                    }
            else:
                # Fallback: validate main repo path if no task name
                if not os.path.exists(main_repo_path) or not os.path.isdir(main_repo_path):
                    return {
                        "success": False,
                        "error": f"Multi-project main repo path not found: {main_repo_path}"
                    }

        return {"success": True}
