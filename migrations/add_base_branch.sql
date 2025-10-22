-- Migration: Add base_branch column to tasks table
-- Date: 2025-10-22
-- Description: Add base_branch field to store the branch to branch off from

ALTER TABLE tasks ADD COLUMN base_branch VARCHAR(200) NULL COMMENT 'Branch to branch off from (e.g., main, develop, master)';
