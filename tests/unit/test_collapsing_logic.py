#!/usr/bin/env python3
"""
Test the enhanced collapsing logic directly.
"""

def is_tool_use_message(content):
    """Check if a claude_response is just a tool use message."""
    if not content:
        return False
    content_lower = content.lower().strip()
    return (content_lower.startswith("[tool use:") or
            "tool use:" in content_lower or
            content_lower == "[tool use: 1 tools]" or
            content_lower.startswith("i'll") and "tool" in content_lower)

def collapse_consecutive_tool_results(messages):
    """
    Enhanced collapsing that groups claude_response tool use messages with tool_results.
    """
    if not messages:
        return []

    result = []
    i = 0

    while i < len(messages):
        current_msg = messages[i]

        # Check if this is a sequence we want to collapse
        if (current_msg.get('type') == 'claude_response' and
            is_tool_use_message(current_msg.get('content', ''))):

            # Start collecting a tool sequence
            tool_sequence = [current_msg]
            j = i + 1

            # Look ahead to collect tool_results and more tool use claude_responses
            while j < len(messages):
                next_msg = messages[j]
                msg_type = next_msg.get('type')

                if msg_type == 'tool_result':
                    tool_sequence.append(next_msg)
                    j += 1
                elif (msg_type == 'claude_response' and
                      is_tool_use_message(next_msg.get('content', ''))):
                    tool_sequence.append(next_msg)
                    j += 1
                elif msg_type == 'simulated_human' and not next_msg.get('content', '').strip():
                    # Skip empty simulated human messages
                    j += 1
                else:
                    # Break on any substantial message
                    break

            # If we collected multiple messages, create a tool group
            if len(tool_sequence) > 1:
                tool_count = sum(1 for msg in tool_sequence if msg.get('type') == 'tool_result')

                tool_group = {
                    'type': 'tool_group',
                    'timestamp': tool_sequence[0].get('timestamp'),
                    'summary': f'Tool execution sequence ({tool_count} tools)',
                    'tool_count': tool_count,
                    'tools': tool_sequence
                }
                result.append(tool_group)
                i = j
            else:
                # Single message, keep as is
                result.append(current_msg)
                i += 1
        else:
            # Not a tool use message, keep as is
            result.append(current_msg)
            i += 1

    return result

def test_enhanced_collapsing():
    """Test the enhanced collapsing logic."""

    # Create test messages that simulate the problematic pattern
    test_messages = [
        {
            'type': 'user_request',
            'content': 'Create a hello world script',
            'timestamp': '2023-01-01T10:00:00Z'
        },
        {
            'type': 'claude_response',
            'content': "[Tool use: 1 tools]",
            'timestamp': '2023-01-01T10:00:01Z'
        },
        {
            'type': 'tool_result',
            'content': 'Tool write_file:\nCreated hello.py successfully',
            'timestamp': '2023-01-01T10:00:02Z'
        },
        {
            'type': 'claude_response',
            'content': "[Tool use: 1 tools]",
            'timestamp': '2023-01-01T10:00:03Z'
        },
        {
            'type': 'tool_result',
            'content': 'Tool bash:\nExecuted python hello.py\nOutput: Hello, World!',
            'timestamp': '2023-01-01T10:00:04Z'
        },
        {
            'type': 'simulated_human',
            'content': '',  # Empty simulated human message
            'timestamp': '2023-01-01T10:00:05Z'
        },
        {
            'type': 'claude_response',
            'content': "Perfect! I've successfully created and tested the hello world script. The task is complete.",
            'timestamp': '2023-01-01T10:00:06Z'
        }
    ]

    print("Original messages:")
    for i, msg in enumerate(test_messages):
        print(f"  {i+1}. {msg['type']}: {msg['content'][:50]}...")

    print(f"\nOriginal message count: {len(test_messages)}")

    # Test the collapsing
    collapsed = collapse_consecutive_tool_results(test_messages)

    print(f"\nCollapsed message count: {len(collapsed)}")
    print("\nCollapsed messages:")
    for i, msg in enumerate(collapsed):
        if msg.get('type') == 'tool_group':
            print(f"  {i+1}. {msg['type']}: {msg['summary']} (contains {len(msg['tools'])} messages)")
        else:
            print(f"  {i+1}. {msg['type']}: {msg['content'][:50]}...")

    # Verify the results
    expected_length = 3  # user_request + tool_group + final claude_response
    if len(collapsed) == expected_length:
        print(f"\n✅ Success! Messages reduced from {len(test_messages)} to {len(collapsed)}")

        # Check that tool group was created correctly
        tool_group = next((msg for msg in collapsed if msg.get('type') == 'tool_group'), None)
        if tool_group and tool_group['tool_count'] == 2:
            print("✅ Tool group created correctly with 2 tools")
            return True
        else:
            print("❌ Tool group not created correctly")
            return False
    else:
        print(f"❌ Expected {expected_length} messages but got {len(collapsed)}")
        return False

def test_is_tool_use_message():
    """Test the is_tool_use_message function."""

    test_cases = [
        ("[Tool use: 1 tools]", True),
        ("I'll use the Write tool to create a file", True),
        ("Tool use: bash command", True),
        ("This is a normal response about the implementation", False),
        ("", False),
        ("Perfect! The task is complete.", False)
    ]

    print("Testing is_tool_use_message function:")
    all_passed = True

    for content, expected in test_cases:
        result = is_tool_use_message(content)
        status = "✅" if result == expected else "❌"
        print(f"  {status} '{content[:30]}...' -> {result} (expected {expected})")
        if result != expected:
            all_passed = False

    return all_passed

if __name__ == "__main__":
    print("Testing Enhanced Tool Collapsing Logic")
    print("=" * 50)

    # Test the helper function
    helper_passed = test_is_tool_use_message()
    print()

    # Test the main collapsing logic
    main_passed = test_enhanced_collapsing()

    print("\n" + "=" * 50)
    if helper_passed and main_passed:
        print("🎉 All tests passed! Enhanced collapsing logic is working correctly.")
    else:
        print("❌ Some tests failed. Please check the implementation.")