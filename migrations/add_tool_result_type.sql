-- Add TOOL_RESULT to the interaction_type enum
ALTER TABLE claude_interactions
MODIFY COLUMN interaction_type ENUM('user_request', 'claude_response', 'simulated_human', 'tool_result') NOT NULL;
