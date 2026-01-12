"""
Utilities for formatting conversation data consistently across API endpoints.
"""

def collapse_consecutive_tool_results(interactions_list, collapse_tools=True):
    """
    Collapse consecutive tool operations (claude_response + tool_result) into groups.

    Args:
        interactions_list: List of interaction objects with id, interaction_type, content, created_at
        collapse_tools: Whether to collapse tool groups (default True)

    Returns:
        List of formatted interaction/tool_group objects
    """
    if not collapse_tools:
        return [
            {
                "id": interaction.id,
                "type": interaction.interaction_type.value,
                "content": interaction.content,
                "timestamp": interaction.created_at.isoformat(),
                "images": interaction.images if hasattr(interaction, 'images') and interaction.images else None
            }
            for interaction in interactions_list
            if interaction.content and interaction.content.strip()  # Filter out empty content
        ]

    collapsed = []
    current_tool_group = None
    i = 0

    def is_tool_use_message(content):
        """Check if a claude_response is just a tool use message."""
        if not content:
            return False
        content_lower = content.lower().strip()
        return (content_lower.startswith("[tool use:") or
                "tool use:" in content_lower or
                content_lower == "[tool use: 1 tools]" or
                content_lower.startswith("i'll") and "tool" in content_lower)

    while i < len(interactions_list):
        interaction = interactions_list[i]

        # Check if this starts a tool operation sequence
        if (interaction.interaction_type.value == "claude_response" and
            is_tool_use_message(interaction.content)):

            # This is a tool use message, start collecting the sequence
            if current_tool_group is None:
                current_tool_group = {
                    "id": f"tool_group_{interaction.id}",
                    "type": "tool_group",
                    "tool_count": 0,
                    "first_timestamp": interaction.created_at.isoformat(),
                    "last_timestamp": interaction.created_at.isoformat(),
                    "summary": "",
                    "tools": []
                }

            # Collect all following tool_results
            i += 1
            while i < len(interactions_list) and interactions_list[i].interaction_type.value == "tool_result":
                tool_result = interactions_list[i]
                current_tool_group["tool_count"] += 1
                current_tool_group["last_timestamp"] = tool_result.created_at.isoformat()
                current_tool_group["tools"].append({
                    "id": tool_result.id,
                    "type": tool_result.interaction_type.value,
                    "content": tool_result.content,
                    "timestamp": tool_result.created_at.isoformat()
                })
                i += 1

            # Update summary
            current_tool_group["summary"] = f"Tool execution results ({current_tool_group['tool_count']} tools)"

            # Don't increment i here since we already moved past the tool_results
            continue

        elif interaction.interaction_type.value == "tool_result" and current_tool_group is not None:
            # Standalone tool_result that should be added to current group
            current_tool_group["tool_count"] += 1
            current_tool_group["last_timestamp"] = interaction.created_at.isoformat()
            current_tool_group["summary"] = f"Tool execution results ({current_tool_group['tool_count']} tools)"
            current_tool_group["tools"].append({
                "id": interaction.id,
                "type": interaction.interaction_type.value,
                "content": interaction.content,
                "timestamp": interaction.created_at.isoformat()
            })
        else:
            # Non-tool interaction or meaningful claude_response
            # Finalize any current tool group
            if current_tool_group is not None:
                collapsed.append(current_tool_group)
                current_tool_group = None

            # Add the meaningful interaction (skip empty/simulated human if needed)
            if not (interaction.interaction_type.value == "simulated_human" and
                   (not interaction.content or interaction.content.strip() == "")):
                collapsed.append({
                    "id": interaction.id,
                    "type": interaction.interaction_type.value,
                    "content": interaction.content,
                    "timestamp": interaction.created_at.isoformat(),
                    "images": interaction.images if hasattr(interaction, 'images') and interaction.images else None
                })

        i += 1

    # Don't forget to add the last tool group if it exists
    if current_tool_group is not None:
        collapsed.append(current_tool_group)

    return collapsed