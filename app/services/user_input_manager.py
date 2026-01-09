"""
User Input Manager - High-priority queue system for user input handling.

This replaces the race-condition prone custom_human_input system with a robust
queue-based approach that ensures user input is never overlooked.
"""

import json
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from app.models import Task, InteractionType
from app.models.interaction import ClaudeInteraction
import logging

logger = logging.getLogger(__name__)


class UserInputManager:
    """Manages user input queue with high priority and no race conditions."""

    @staticmethod
    def add_user_input(db: Session, task_id: str, user_input: str, auto_commit: bool = True, use_separate_session: bool = False, images: List[Dict[str, str]] = None) -> bool:
        """
        Add user input to the high-priority queue.

        Args:
            db: Database session
            task_id: ID of the task
            user_input: The user's input message
            images: Optional list of images [{"base64": "...", "media_type": "image/png"}, ...]

        Returns:
            True if successfully added, False otherwise
        """
        try:
            print(f"🔍 UserInputManager DEBUG: Starting add_user_input for task {task_id}, use_separate_session={use_separate_session}")

            # Use separate session if requested to avoid transaction conflicts
            if use_separate_session:
                from app.database import SessionLocal
                separate_db = SessionLocal()
                print(f"🔍 UserInputManager DEBUG: Using separate database session")
                working_db = separate_db
            else:
                working_db = db

            task = working_db.query(Task).filter(Task.id == task_id).first()
            if not task:
                print(f"❌ UserInputManager DEBUG: Task {task_id} not found")
                logger.error(f"Task {task_id} not found")
                if use_separate_session:
                    separate_db.close()
                return False

            print(f"🔍 UserInputManager DEBUG: Found task {task.task_name}")
            print(f"🔍 UserInputManager DEBUG: Current queue: {task.user_input_queue}")

            # Initialize queue if it doesn't exist
            if not task.user_input_queue:
                task.user_input_queue = []
                print(f"🔍 UserInputManager DEBUG: Initialized empty queue")

            # Check for recent duplicates to prevent spam (same logic as REST endpoint)
            from datetime import timedelta
            current_queue = task.user_input_queue or []
            recent_cutoff = datetime.utcnow() - timedelta(seconds=30)  # 30 second window

            for entry in current_queue:
                try:
                    entry_time = datetime.fromisoformat(entry.get("timestamp", "1970-01-01T00:00:00"))
                    entry_input = entry.get("input", "")
                    if entry_time > recent_cutoff and entry_input == user_input:
                        print(f"🚫 UserInputManager DUPLICATE BLOCKED: '{user_input[:50]}...' was already sent within 30 seconds")
                        if use_separate_session:
                            separate_db.close()
                        return False  # Duplicate detected, don't add
                except Exception as e:
                    print(f"⚠️ UserInputManager WARNING: Error parsing timestamp in queue entry: {e}")
                    continue

            # Create new input entry
            input_entry = {
                "id": str(uuid.uuid4()),
                "input": user_input,
                "timestamp": datetime.utcnow().isoformat(),
                "status": "pending",  # pending -> sent -> processed
                "processed": False  # Keep for backward compatibility
            }

            # Store images if provided (format: [{"base64": "...", "media_type": "image/png"}, ...])
            if images and len(images) > 0:
                input_entry["images"] = images
                print(f"🖼️ UserInputManager DEBUG: Added {len(images)} images to input entry")

            print(f"🔍 UserInputManager DEBUG: Created input entry: {input_entry}")

            # Add to queue
            current_queue = task.user_input_queue or []
            print(f"🔍 UserInputManager DEBUG: Current queue before append: {current_queue}")
            current_queue.append(input_entry)
            print(f"🔍 UserInputManager DEBUG: Current queue after append: {current_queue}")

            # CRITICAL: Create new list object so SQLAlchemy detects the change
            task.user_input_queue = list(current_queue)
            task.user_input_pending = True

            # Also mark the field as modified to ensure SQLAlchemy persists it
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(task, 'user_input_queue')
            print(f"🔍 UserInputManager DEBUG: Set task.user_input_queue to: {task.user_input_queue} and flagged as modified")

            if auto_commit:
                print(f"🔍 UserInputManager DEBUG: About to commit...")
                working_db.commit()
                print(f"✅ UserInputManager DEBUG: Commit successful")

                # Verify commit by re-querying database
                verification_task = working_db.query(Task).filter(Task.id == task_id).first()
                print(f"🔍 UserInputManager DEBUG: Post-commit verification - database shows queue: {verification_task.user_input_queue}")
            else:
                print(f"🔍 UserInputManager DEBUG: Skipping commit (auto_commit=False)")

            # Close separate session if used
            if use_separate_session:
                separate_db.close()
                print(f"🔍 UserInputManager DEBUG: Closed separate database session")

            logger.info(f"Added user input to queue for task {task_id}: {user_input[:50]}...")
            return True

        except Exception as e:
            logger.error(f"Failed to add user input for task {task_id}: {e}")
            working_db.rollback()
            if use_separate_session:
                separate_db.close()
            return False

    @staticmethod
    def has_pending_input(db: Session, task_id: str) -> bool:
        """
        Check if task has pending user input.

        Args:
            db: Database session
            task_id: ID of the task

        Returns:
            True if there's pending input, False otherwise
        """
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            return False

        return task.user_input_pending and task.user_input_queue

    @staticmethod
    def get_next_pending_user_input(db: Session, task_id: str) -> Optional[str]:
        """
        Get the next PENDING user input from the queue (not sent yet).
        This prevents duplicate processing by only returning unsent messages.

        Args:
            db: Database session
            task_id: ID of the task

        Returns:
            The next pending user input message, or None if no pending input
        """
        try:
            task = db.query(Task).filter(Task.id == task_id).first()
            if not task or not task.user_input_queue:
                return None

            # Get current queue
            current_queue = task.user_input_queue or []

            # Find first pending input (status="pending", not "sent" or "processed")
            for entry in current_queue:
                status = entry.get("status", "pending")  # Default to pending for backward compatibility
                if status == "pending":
                    print(f"📤 Found pending message: {entry['input'][:50]}...")
                    return entry["input"]

            print(f"📤 No pending messages found for task {task_id}")
            return None

        except Exception as e:
            logger.error(f"Failed to get pending user input for task {task_id}: {e}")
            return None

    @staticmethod
    def get_next_pending_user_input_with_images(db: Session, task_id: str) -> tuple[Optional[str], Optional[List[Dict[str, str]]]]:
        """
        Get the next PENDING user input from the queue with any attached images.
        This prevents duplicate processing by only returning unsent messages.

        Args:
            db: Database session
            task_id: ID of the task

        Returns:
            Tuple of (user_input_text, images_list) or (None, None) if no pending input
        """
        try:
            task = db.query(Task).filter(Task.id == task_id).first()
            if not task or not task.user_input_queue:
                return None, None

            # Get current queue
            current_queue = task.user_input_queue or []

            # Find first pending input (status="pending", not "sent" or "processed")
            for entry in current_queue:
                status = entry.get("status", "pending")  # Default to pending for backward compatibility
                if status == "pending":
                    user_input = entry["input"]
                    images = entry.get("images")  # May be None or list of image dicts
                    image_count = len(images) if images else 0
                    print(f"📤 Found pending message with {image_count} images: {user_input[:50]}...")
                    return user_input, images

            print(f"📤 No pending messages found for task {task_id}")
            return None, None

        except Exception as e:
            logger.error(f"Failed to get pending user input with images for task {task_id}: {e}")
            return None, None

    @staticmethod
    def mark_message_as_sent(db: Session, task_id: str, user_input: str) -> bool:
        """
        Mark a specific message as 'sent' to prevent duplicate processing.

        Args:
            db: Database session
            task_id: ID of the task
            user_input: The message that was sent

        Returns:
            True if message was found and marked as sent
        """
        try:
            task = db.query(Task).filter(Task.id == task_id).first()
            if not task or not task.user_input_queue:
                return False

            # Get current queue
            current_queue = task.user_input_queue or []
            updated_queue = []
            message_found = False

            for entry in current_queue:
                if entry["input"] == user_input and entry.get("status", "pending") == "pending":
                    # Mark this message as sent
                    entry["status"] = "sent"
                    entry["sent_at"] = datetime.utcnow().isoformat()
                    message_found = True
                    print(f"📤 Marked message as SENT: {user_input[:50]}...")

                updated_queue.append(entry)

            if message_found:
                # Update the queue
                task.user_input_queue = updated_queue
                from sqlalchemy.orm.attributes import flag_modified
                flag_modified(task, 'user_input_queue')
                db.commit()
                print(f"✅ Successfully marked message as sent for task {task_id}")
                return True
            else:
                print(f"⚠️ Message not found in pending queue for task {task_id}")
                return False

        except Exception as e:
            logger.error(f"Failed to mark message as sent for task {task_id}: {e}")
            db.rollback()
            return False

    @staticmethod
    def get_next_user_input(db: Session, task_id: str) -> Optional[str]:
        """
        Get the next user input from the queue and mark it as processed.
        DEPRECATED: Use get_next_pending_user_input() + mark_message_as_sent() instead.

        Args:
            db: Database session
            task_id: ID of the task

        Returns:
            The next user input message, or None if no input pending
        """
        try:
            task = db.query(Task).filter(Task.id == task_id).first()
            if not task or not task.user_input_queue:
                return None

            # Get current queue
            current_queue = task.user_input_queue or []

            # Find first unprocessed input
            next_input = None
            updated_queue = []

            for entry in current_queue:
                if not entry.get("processed", False) and next_input is None:
                    # This is our next input
                    next_input = entry["input"]
                    entry["processed"] = True
                    entry["processed_at"] = datetime.utcnow().isoformat()

                updated_queue.append(entry)

            if next_input:
                # Update the queue
                task.user_input_queue = updated_queue

                # Check if there are more unprocessed inputs
                has_more_pending = any(
                    not entry.get("processed", False)
                    for entry in updated_queue
                )
                task.user_input_pending = has_more_pending

                db.commit()
                logger.info(f"Retrieved user input for task {task_id}: {next_input[:50]}...")
                return next_input

            return None

        except Exception as e:
            logger.error(f"Failed to get user input for task {task_id}: {e}")
            db.rollback()
            return None

    @staticmethod
    def clear_processed_inputs(db: Session, task_id: str) -> int:
        """
        Clear processed inputs from the queue to prevent memory buildup.

        Args:
            db: Database session
            task_id: ID of the task

        Returns:
            Number of inputs cleared
        """
        try:
            task = db.query(Task).filter(Task.id == task_id).first()
            if not task or not task.user_input_queue:
                return 0

            current_queue = task.user_input_queue or []

            # Keep only unprocessed inputs
            unprocessed_queue = [
                entry for entry in current_queue
                if not entry.get("processed", False)
            ]

            cleared_count = len(current_queue) - len(unprocessed_queue)

            if cleared_count > 0:
                task.user_input_queue = unprocessed_queue
                task.user_input_pending = len(unprocessed_queue) > 0
                db.commit()
                logger.info(f"Cleared {cleared_count} processed inputs for task {task_id}")

            return cleared_count

        except Exception as e:
            logger.error(f"Failed to clear processed inputs for task {task_id}: {e}")
            db.rollback()
            return 0

    @staticmethod
    def save_user_interaction(db: Session, task_id: str, user_input: str) -> bool:
        """
        Save user input as a USER_REQUEST interaction.

        Args:
            db: Database session
            task_id: ID of the task
            user_input: The user's input message

        Returns:
            True if successfully saved, False otherwise
        """
        try:
            interaction = ClaudeInteraction(
                task_id=task_id,
                interaction_type=InteractionType.USER_REQUEST,
                content=user_input
            )
            db.add(interaction)
            db.commit()
            logger.info(f"Saved user interaction for task {task_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to save user interaction for task {task_id}: {e}")
            db.rollback()
            return False

    @staticmethod
    def trigger_immediate_processing(db: Session, task_id: str, user_input: str) -> bool:
        """
        Trigger immediate processing of user input by sending it directly to Claude.
        This bypasses the wait-for-pause-cycle approach and processes the input immediately.

        Args:
            db: Database session
            task_id: ID of the task
            user_input: The user's input message

        Returns:
            True if immediate processing was triggered successfully
        """
        try:
            from app.services.streaming_cli_client import StreamingCLIClient
            from app.models import Task, TaskStatus
            import os

            # Get the task
            task = db.query(Task).filter(Task.id == task_id).first()
            if not task:
                logger.error(f"Task {task_id} not found for immediate processing")
                return False

            # Refresh task to get latest claude_session_id from database
            db.refresh(task)

            # Only process if task is actively running
            if task.status != TaskStatus.RUNNING:
                logger.info(f"Task {task_id} not running (status: {task.status}) - skipping immediate processing")
                return False

            # Save the user interaction immediately
            if not UserInputManager.save_user_interaction(db, task_id, user_input):
                logger.error(f"Failed to save user interaction for immediate processing")
                return False

            # CRITICAL: Mark the message as "sent" to prevent duplicate processing
            if not UserInputManager.mark_message_as_sent(db, task_id, user_input):
                logger.warning(f"Failed to mark message as sent for immediate processing - may cause duplicates")

            # Create streaming client to send message to Claude immediately
            cli_cmd = os.getenv("CLAUDE_CLI_COMMAND", "claude")
            streaming_client = StreamingCLIClient(cli_command=cli_cmd)

            # Send the user message to Claude with session continuity
            claude_session_id = task.claude_session_id
            print(f"🔍 IMMEDIATE PROCESSING DEBUG: task_id={task_id}, claude_session_id={claude_session_id}")

            # If no session ID yet, don't use session continuity (let Claude create new session)
            # This happens when immediate processing runs before task executor sets claude_session_id
            if not claude_session_id:
                print(f"⚠️  No claude_session_id available yet for task {task_id}, proceeding without session continuity")
                claude_session_id = None  # Explicitly set to None for new session
            else:
                print(f"✅ Using existing claude_session_id: {claude_session_id} for task {task_id}")

            logger.info(f"Immediate processing using claude_session_id: {claude_session_id} for task {task_id}")

            def handle_immediate_response(event: dict):
                """Handle Claude's immediate response to user input."""
                event_type = event.get('type')

                if event_type == 'message':
                    content = event.get('content', '')
                    if content.strip():
                        # Save Claude's immediate response
                        from app.models.interaction import ClaudeInteraction, InteractionType
                        interaction = ClaudeInteraction(
                            task_id=task_id,
                            interaction_type=InteractionType.CLAUDE_RESPONSE,
                            content=content
                        )
                        db.add(interaction)

                        # Update task tokens if available
                        usage = event.get('usage', {})
                        if usage:
                            input_tokens = usage.get('input_tokens', 0)
                            output_tokens = usage.get('output_tokens', 0)
                            task.total_tokens_used += output_tokens

                        db.commit()
                        logger.info(f"Saved immediate Claude response for task {task_id}")

            # Send message immediately with session continuity
            # Use background thread to avoid blocking the API response
            import threading

            def send_message_background():
                try:
                    import asyncio

                    async def send_immediate():
                        await streaming_client.send_message_streaming(
                            message=user_input,
                            event_callback=handle_immediate_response,
                            session_id=claude_session_id
                        )

                    # Create new event loop for background thread
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        loop.run_until_complete(send_immediate())
                    finally:
                        loop.close()

                except Exception as e:
                    error_str = str(e)
                    logger.error(f"Background message sending failed: {e}")

                    # If session ID is invalid (process terminated), try without session continuity
                    if "No conversation found with session ID" in error_str and claude_session_id:
                        print(f"🔄 Session {claude_session_id} invalid, retrying without session continuity")
                        try:
                            async def retry_without_session():
                                await streaming_client.send_message_streaming(
                                    message=user_input,
                                    event_callback=handle_immediate_response,
                                    session_id=None  # Start new session
                                )

                            # Retry in new event loop
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            try:
                                loop.run_until_complete(retry_without_session())
                                print(f"✅ Retry without session succeeded for task {task_id}")
                            finally:
                                loop.close()
                        except Exception as retry_error:
                            logger.error(f"Retry without session also failed: {retry_error}")

            # Start background processing
            thread = threading.Thread(target=send_message_background, daemon=True)
            thread.start()

            logger.info(f"Triggered immediate processing for task {task_id}: {user_input[:50]}...")

            # CRITICAL: After starting immediate processing, schedule flag reset
            # so that task executor doesn't skip processing when it restarts
            def reset_flag_after_processing():
                import time
                time.sleep(3)  # Give immediate processing time to complete
                try:
                    from app.database import SessionLocal
                    reset_db = SessionLocal()
                    try:
                        reset_task = reset_db.query(Task).filter(Task.id == task_id).first()
                        if reset_task and reset_task.immediate_processing_active:
                            reset_task.immediate_processing_active = False
                            reset_db.commit()
                            print(f"🔄 Auto-reset immediate_processing_active=False for task {task_id} after processing")
                    finally:
                        reset_db.close()
                except Exception as e:
                    print(f"❌ Failed to reset immediate_processing_active for task {task_id}: {e}")

            # Start reset thread
            reset_thread = threading.Thread(target=reset_flag_after_processing, daemon=True)
            reset_thread.start()

            return True

        except Exception as e:
            logger.error(f"Failed to trigger immediate processing for task {task_id}: {e}")
            return False

    @staticmethod
    def get_queue_status(db: Session, task_id: str) -> Dict[str, Any]:
        """
        Get detailed status of the user input queue.

        Args:
            db: Database session
            task_id: ID of the task

        Returns:
            Dictionary with queue status information
        """
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            return {"error": "Task not found"}

        queue = task.user_input_queue or []

        return {
            "total_inputs": len(queue),
            "pending_inputs": len([e for e in queue if not e.get("processed", False)]),
            "processed_inputs": len([e for e in queue if e.get("processed", False)]),
            "has_pending": task.user_input_pending,
            "queue_preview": [
                {
                    "id": entry["id"],
                    "input_preview": entry["input"][:50] + "..." if len(entry["input"]) > 50 else entry["input"],
                    "timestamp": entry["timestamp"],
                    "processed": entry.get("processed", False)
                }
                for entry in queue[-5:]  # Show last 5 entries
            ]
        }