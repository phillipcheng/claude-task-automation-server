#!/usr/bin/env python3
"""Test the async streaming client directly."""
import asyncio
import sys
sys.path.insert(0, '/Users/bytedance/python/claudeserver')

from app.services.streaming_cli_client import StreamingCLIClient

async def test_streaming():
    client = StreamingCLIClient()

    print("Testing async streaming client...")
    print("Sending message: 'Say hello in one sentence'")

    events_received = []
    def handle_event(event):
        print(f"  Event: {event.get('type')} - {str(event)[:100]}...")
        events_received.append(event)

    response, pid, session_id, usage_data = await client.send_message_streaming(
        message="Say hello in one sentence",
        project_path="/tmp",
        event_callback=handle_event
    )

    print(f"\nDone!")
    print(f"  PID: {pid}")
    print(f"  Session ID: {session_id}")
    print(f"  Events received: {len(events_received)}")
    print(f"  Response: {response}")
    print(f"  Usage: {usage_data}")

if __name__ == "__main__":
    asyncio.run(test_streaming())
