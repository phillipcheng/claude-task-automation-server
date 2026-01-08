-- Migration: Add user_id column to tasks table
-- Run this on the database server (10.251.236.152)

-- For MySQL:
ALTER TABLE tasks ADD COLUMN user_id VARCHAR(100) NULL;
CREATE INDEX idx_tasks_user_id ON tasks(user_id);

-- Verify the change
DESCRIBE tasks;
