#!/usr/bin/env python3
"""Test that exactly mimics what the server does with the real task message."""
import asyncio
import subprocess
import shlex

async def test_real_task():
    """Test with the actual task description."""

    # This is the EXACT message from the real task
    message = """Task: 1. I already added fields sceneCodes and eventCodes to stra,
2. we need to populate these fields in create and upsert together with the previous sceneCode and eventCode,
3. store sceneCodes and  eventCodes in the json content field of stra

/Users/bytedance/go/src/code.byted.org/aftersales/reverse_strategy (CRUD/release) uses /Users/bytedance/go/src/code.byted.org/aftersales/reverse_strategy_sdk (Get/Runtime/Cache).
/Users/bytedance/go/src/code.byted.org/aftersales/reverse_strategy/test contains the regression test cases, now it is in local mode.
you can never run "git clean".
also for the exisiting test cases under test folder, you need to make sure they pass after your changes to the engine code.

Project Path: /Users/bytedance/go/src/code.byted.org/aftersales/reverse_strategy
The project directory exists and you have full access to explore it.


Please implement this task. You have permissions for file operations and testing. When complete, provide a summary."""

    escaped_message = shlex.quote(message)
    cmd = f'claude -p {escaped_message} --output-format stream-json --verbose --permission-mode bypassPermissions'

    print(f"Command length: {len(cmd)}")
    print(f"Escaped message length: {len(escaped_message)}")
    print(f"Starting process with shell=True...")

    process = subprocess.Popen(
        cmd,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        cwd="/Users/bytedance/go/src/code.byted.org/aftersales/reverse_strategy",
    )

    print(f"Process PID: {process.pid}")
    print("Calling communicate()...")

    loop = asyncio.get_event_loop()
    stdout_data, stderr_data = await loop.run_in_executor(None, process.communicate)

    print(f"Return code: {process.returncode}")
    print(f"Stdout lines: {len(stdout_data.splitlines())}")
    print(f"Stderr: {stderr_data[:200] if stderr_data else 'None'}")

    if process.returncode == 0:
        print("✅ SUCCESS!")
    else:
        print(f"❌ FAILED: {stderr_data}")

if __name__ == "__main__":
    asyncio.run(test_real_task())
