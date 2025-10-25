-- Add project_context column to tasks table
-- This allows users to specify custom project context that will be included in Claude's prompts

ALTER TABLE tasks ADD COLUMN project_context TEXT;

-- Add a comment to the column
COMMENT ON COLUMN tasks.project_context IS 'User-specified project context that will be included in Claude''s prompts. Example: "This is a Go project that handles CRUD operations. Dependencies: reverse_strategy_sdk for Get/Runtime/Cache. Testing: ./test directory contains regression test cases."';