#!/usr/bin/env python3
"""Simple test to see if Claude CLI works from Python subprocess."""

import subprocess
import sys

message = "Create a file /tmp/test.txt with the text 'Hello World'"
cmd = ["claude", "-p", message, "--output-format", "stream-json", "--verbose", "--permission-mode", "bypassPermissions"]

print(f"Running command: {' '.join(cmd[:3])}...")
print(f"Working directory: /tmp")

process = subprocess.Popen(
    cmd,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    cwd="/tmp",
)

print(f"Process started with PID: {process.pid}")
print("Waiting for output...")

# Try to read with a timeout
import select
import time

start = time.time()
timeout_seconds = 10

while time.time() - start < timeout_seconds:
    # Check if process has output ready
    if process.poll() is not None:
        print(f"Process exited with code: {process.returncode}")
        stdout_data = process.stdout.read()
        stderr_data = process.stderr.read()
        print(f"STDOUT: {stdout_data[:500]}")
        print(f"STDERR: {stderr_data[:500]}")
        break

    time.sleep(0.5)
    print(f"Still waiting... ({time.time() - start:.1f}s)")
else:
    print(f"TIMEOUT after {timeout_seconds} seconds!")
    print(f"Process still alive: {process.poll() is None}")
    process.kill()

print("Done")
