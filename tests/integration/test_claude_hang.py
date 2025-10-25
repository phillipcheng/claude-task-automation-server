#!/usr/bin/env python3
"""Test script to reproduce Claude CLI hanging issue."""

import subprocess
import threading
import queue
import time
import json

def test_claude_cli():
    """Test Claude CLI with the same configuration as streaming_cli_client."""

    message = """Task: 1. I already added fields sceneCodes and eventCodes to stra,
2. we need to populate these fields in create and upsert together with the previous sceneCode and eventCode,
3. store sceneCodes and  eventCodes in the json content field of stra

/Users/bytedance/go/src/code.byted.org/aftersales/reverse_strategy (CRUD/release) uses /Users/bytedance/go/src/code.byted.org/aftersales/reverse_strategy_sdk (Get/Runtime/Cache).
/Users/bytedance/go/src/code.byted.org/aftersales/reverse_strategy/test contains the regression test cases, now it is in local mode.
you can never run "git clean".
also for the exisiting test cases under test folder, you need to make sure they pass after your changes to the engine code.

Project Path: /Users/bytedance/go/src/code.byted.org/aftersales/reverse_strategy/.claude_worktrees/add_scene_event_codes_to_stra
The project directory exists and you have full access to explore it.


Please implement this task. You have permissions for file operations and testing. When complete, provide a summary."""

    cmd = ["claude", "-p", message, "--output-format", "stream-json", "--verbose", "--permission-mode", "bypassPermissions"]

    print(f"Starting Claude CLI process...")
    print(f"Command: {' '.join(cmd[:3])}...")

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,  # Line buffered
        cwd="/Users/bytedance/go/src/code.byted.org/aftersales/reverse_strategy/.claude_worktrees/add_scene_event_codes_to_stra",
    )

    print(f"Process started with PID: {process.pid}")

    output_queue = queue.Queue()

    def read_output():
        """Thread function to read NDJSON stream line by line."""
        try:
            print("[Thread] Starting to read output...")
            for line in iter(process.stdout.readline, ''):
                print(f"[Thread] Got line: {line[:100]}...")
                if line.strip():
                    output_queue.put(('line', line))
            print("[Thread] Finished reading output")
            output_queue.put(('done', None))
        except Exception as e:
            print(f"[Thread] Error: {e}")
            output_queue.put(('error', str(e)))

    reader_thread = threading.Thread(target=read_output, daemon=True)
    reader_thread.start()

    print("Waiting for output...")
    start_time = time.time()
    timeout_seconds = 30

    while time.time() - start_time < timeout_seconds:
        try:
            msg_type, data = output_queue.get(timeout=0.5)

            if msg_type == 'line':
                print(f"Got line: {data[:100]}...")
                try:
                    event = json.loads(data)
                    print(f"Event type: {event.get('type')}, subtype: {event.get('subtype')}")
                except json.JSONDecodeError:
                    pass
            elif msg_type == 'done':
                print("Stream complete")
                break
            elif msg_type == 'error':
                print(f"Error: {data}")
                break
        except queue.Empty:
            elapsed = time.time() - start_time
            print(f"Waiting... ({elapsed:.1f}s elapsed, process alive: {process.poll() is None})")
            if process.poll() is not None:
                print(f"Process ended with return code: {process.returncode}")
                break

    if time.time() - start_time >= timeout_seconds:
        print(f"TIMEOUT after {timeout_seconds} seconds!")
        print(f"Process state: PID={process.pid}, poll={process.poll()}")
        process.kill()

    print("Test complete")

if __name__ == "__main__":
    test_claude_cli()
