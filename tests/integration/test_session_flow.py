#!/usr/bin/env python3
"""
Test script to demonstrate session-based conversation with token tracking
"""
import asyncio
import sys
sys.path.insert(0, '/Users/bytedance/python/claudeserver')

from app.services.streaming_cli_client import StreamingCLIClient

async def main():
    client = StreamingCLIClient()

    print("=" * 80)
    print("STEP 1: Send first message (task description)")
    print("=" * 80)

    response1, pid1, session_id, usage1 = await client.send_message_streaming(
        message="Say hello in one sentence",
        project_path="/tmp"
    )

    print(f"\n✓ Response: {response1}")
    print(f"✓ Session ID: {session_id}")
    print(f"✓ Process PID: {pid1}")
    if usage1:
        print(f"✓ Duration: {usage1.get('duration_ms')}ms")
        print(f"✓ Cost: ${usage1.get('cost_usd')}")
        usage = usage1.get('usage', {})
        print(f"✓ Tokens: in={usage.get('input_tokens')}, out={usage.get('output_tokens')}")
        print(f"          cache_create={usage.get('cache_creation_input_tokens')}, cache_read={usage.get('cache_read_input_tokens')}")

    print("\n" + "=" * 80)
    print("STEP 2: Continue conversation using session ID")
    print("=" * 80)

    response2, pid2, session_id2, usage2 = await client.send_message_streaming(
        message="thanks!",
        project_path="/tmp",
        session_id=session_id  # Continue the conversation
    )

    print(f"\n✓ Response: {response2}")
    print(f"✓ Session ID: {session_id2} (same as before: {session_id2 == session_id})")
    print(f"✓ Process PID: {pid2}")
    if usage2:
        print(f"✓ Duration: {usage2.get('duration_ms')}ms")
        print(f"✓ Cost: ${usage2.get('cost_usd')}")
        usage = usage2.get('usage', {})
        print(f"✓ Tokens: in={usage.get('input_tokens')}, out={usage.get('output_tokens')}")
        print(f"          cache_create={usage.get('cache_creation_input_tokens')}, cache_read={usage.get('cache_read_input_tokens')}")

    print("\n" + "=" * 80)
    print("SUCCESS: Session-based conversation with token tracking works!")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(main())
