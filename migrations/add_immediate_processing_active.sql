-- Add immediate_processing_active column to prevent duplicate user message processing
-- This flag is set when immediate processing sends a message to Claude,
-- preventing the task executor from processing the same message again

ALTER TABLE tasks ADD COLUMN immediate_processing_active BOOLEAN NOT NULL DEFAULT FALSE COMMENT 'Flag to prevent duplicate processing when immediate processing is active';