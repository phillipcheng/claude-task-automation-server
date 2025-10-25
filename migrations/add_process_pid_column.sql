-- Migration: Add process_pid column to tasks table
-- Date: 2025-10-22
-- Description: Add process_pid column to track Claude CLI subprocess PIDs for proper process management

ALTER TABLE tasks ADD COLUMN process_pid INT NULL AFTER custom_human_input;
