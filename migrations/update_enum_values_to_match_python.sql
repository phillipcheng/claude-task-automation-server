-- Convert database enum values to match Python enum names (uppercase)
-- First alter the column to VARCHAR temporarily
ALTER TABLE claude_interactions MODIFY COLUMN interaction_type VARCHAR(20) NOT NULL;

-- Update all existing values to match Python enum names
UPDATE claude_interactions SET interaction_type = 'USER_REQUEST' WHERE interaction_type = 'user_request';
UPDATE claude_interactions SET interaction_type = 'CLAUDE_RESPONSE' WHERE interaction_type = 'claude_response';
UPDATE claude_interactions SET interaction_type = 'SIMULATED_HUMAN' WHERE interaction_type = 'simulated_human';
UPDATE claude_interactions SET interaction_type = 'TOOL_RESULT' WHERE interaction_type = 'tool_result';
