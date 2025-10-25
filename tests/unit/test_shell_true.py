#!/usr/bin/env python3
"""Test Claude CLI with shell=True to see if it fixes the hanging issue."""

import subprocess
import asyncio

async def test_with_shell_true():
    """Test Claude with shell=True."""
    print("Testing with shell=True...")

    cmd = 'claude -p "Say hello" --output-format stream-json --verbose --permission-mode bypassPermissions'

    process = subprocess.Popen(
        cmd,
        shell=True,  # KEY DIFFERENCE
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd="/tmp",
    )

    print(f"Process started with PID: {process.pid}")

    # Use communicate() with async
    loop = asyncio.get_event_loop()
    stdout_data, stderr_data = await loop.run_in_executor(None, process.communicate)

    print(f"Return code: {process.returncode}")
    print(f"Output lines: {len(stdout_data.splitlines())}")
    print(f"First line: {stdout_data.splitlines()[0] if stdout_data else 'NONE'}")

    if process.returncode == 0:
        print("✅ SUCCESS with shell=True!")
    else:
        print(f"❌ FAILED with stderr: {stderr_data}")

if __name__ == "__main__":
    asyncio.run(test_with_shell_true())
