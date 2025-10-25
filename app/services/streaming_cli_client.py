"""
Streaming wrapper for Claude CLI that provides real-time output capture.
Uses the --output-format stream-json flag for proper NDJSON streaming.
"""
import asyncio
import json
import logging
import shlex
from typing import Optional, Callable

logger = logging.getLogger(__name__)


class StreamingCLIClient:
    """Wrapper that captures Claude CLI output in real-time using stream-json format."""

    def __init__(self, cli_command: str = "claude"):
        self.cli_command = cli_command

    async def send_message_streaming(
        self,
        message: str,
        project_path: Optional[str] = None,
        output_callback: Optional[Callable[[str], None]] = None,
        session_id: Optional[str] = None,
        event_callback: Optional[Callable[[dict], None]] = None,
    ) -> tuple[str, Optional[int], Optional[str], Optional[dict]]:
        """
        Send message to Claude CLI and capture streaming output in real-time.

        Args:
            message: Message to send
            project_path: Working directory
            output_callback: Callback for each content chunk (sync function)
            session_id: Optional session ID to continue conversation (use -r flag)
            event_callback: Callback for each NDJSON event (for saving interactions in real-time)

        Returns:
            Tuple of (full_output, process_pid, session_id, usage_data)
            where usage_data contains: {duration_ms, cost_usd, usage: {input_tokens, output_tokens, ...}}
        """
        # Use -p flag for new conversation or -r flag to resume existing session
        # Requires --verbose flag for stream-json to work
        # Use --permission-mode bypassPermissions to auto-approve all actions (non-interactive mode)

        # Build command string for shell execution
        # IMPORTANT: Use shell=True because Claude CLI requires shell environment to work properly
        # This avoids the hanging issue that occurs with shell=False
        # Use shlex.quote() to safely escape the message for shell execution
        escaped_message = shlex.quote(message)
        if session_id:
            # Continue existing conversation
            cmd = f'{self.cli_command} -r {shlex.quote(session_id)} -p {escaped_message} --output-format stream-json --verbose --permission-mode bypassPermissions'
        else:
            # Start new conversation
            cmd = f'{self.cli_command} -p {escaped_message} --output-format stream-json --verbose --permission-mode bypassPermissions'

        # Log working directory for isolation verification
        if project_path:
            logger.info(f"Claude CLI executing in directory: {project_path}")
            # Validate that the path exists
            import os
            if not os.path.exists(project_path):
                logger.error(f"Working directory does not exist: {project_path}")
                raise ValueError(f"Working directory not found: {project_path}")
        else:
            logger.warning("Claude CLI executing in current directory (no project_path specified)")

        # Start process with shell=True using asyncio for proper async streaming
        # CRITICAL: Use asyncio.create_subprocess_shell for real-time line reading
        # IMPORTANT: Set stdin=DEVNULL to prevent Claude from waiting on stdin
        # FIX: Increase buffer limit to handle large output chunks and prevent "chunk is longer than limit" error
        process = await asyncio.create_subprocess_shell(
            cmd,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=project_path if project_path else None,
            limit=1024 * 256,  # 256 KB buffer limit (default is ~64KB) to handle large Claude outputs
        )

        pid = process.pid
        full_text = []
        extracted_session_id = session_id  # Keep the passed session_id or will extract from stream
        usage_data = None  # Will be populated from result event

        # Read stdout line by line in real-time using async
        async for line_bytes in process.stdout:
            # Decode bytes to string
            line = line_bytes.decode('utf-8').strip()
            if not line:
                continue

            try:
                # Parse NDJSON line
                event = json.loads(line)

                # Call event callback for every event (allows real-time interaction saving)
                if event_callback:
                    event_callback(event)

                # Extract session_id from system init event (first message in stream)
                if event.get('type') == 'system' and event.get('subtype') == 'init':
                    extracted_session_id = event.get('session_id')

                # Extract content from assistant messages
                if event.get('type') == 'assistant':
                    message = event.get('message', {})
                    content = message.get('content', [])

                    # Extract text from content blocks
                    for block in content:
                        if block.get('type') == 'text':
                            text_chunk = block.get('text', '')
                            full_text.append(text_chunk)

                            # Call callback with text
                            if output_callback:
                                output_callback(text_chunk)

                # Handle 'result' type for final output (this is authoritative)
                elif event.get('type') == 'result':
                    result_text = event.get('result', '')
                    # The result contains the final assembled text - this is what we should use!
                    # Clear full_text and use the result instead
                    if result_text:
                        full_text = [result_text]

                    # Extract usage data from result event
                    usage_data = {
                        'duration_ms': event.get('duration_ms'),
                        'cost_usd': event.get('total_cost_usd'),
                        'usage': event.get('usage', {})
                    }

            except json.JSONDecodeError:
                # Skip non-JSON lines
                pass

        # Wait for process to complete and check return code
        await process.wait()

        if process.returncode != 0:
            # Read any stderr output
            stderr_bytes = await process.stderr.read()
            error_msg = stderr_bytes.decode('utf-8') if stderr_bytes else "Unknown error"

            # Check for specific chunk size limit error that can be recovered from
            if "Separator is found, but chunk is longer than limit" in error_msg:
                logger.warning(f"Claude CLI chunk size limit exceeded - continuing with partial output")
                # Return what we have so far - the conversation can continue
                full_output = ''.join(full_text).strip()
                if not full_output:
                    full_output = "⚠️ Output truncated due to size limit. Please continue with a follow-up message."
                return (full_output, pid, extracted_session_id, usage_data)

            # For other errors, still raise the exception
            raise Exception(f"Claude CLI error (exit code {process.returncode}): {error_msg}")

        full_output = ''.join(full_text).strip()
        return (full_output, pid, extracted_session_id, usage_data)
