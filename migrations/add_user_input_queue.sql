-- Add user input queue system for high-priority user input handling
-- This replaces the race-condition prone custom_human_input system

ALTER TABLE tasks
ADD COLUMN user_input_queue JSON COMMENT 'Queue of pending user inputs in FIFO order',
ADD COLUMN user_input_pending BOOLEAN DEFAULT FALSE COMMENT 'Quick flag to check if user input is pending';

-- Create index for faster queries on pending user input
CREATE INDEX idx_tasks_user_input_pending ON tasks(user_input_pending);

-- Update existing tasks to have empty queue and no pending input
UPDATE tasks SET
    user_input_queue = '[]',
    user_input_pending = FALSE
WHERE user_input_queue IS NULL;