-- Add ending criteria and resource limit tracking columns to tasks table

-- Check if columns exist, add them if not
SET @dbname = DATABASE();
SET @tablename = "tasks";

-- Add end_criteria_config if it doesn't exist
SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = @dbname AND TABLE_NAME = @tablename AND COLUMN_NAME = 'end_criteria_config');
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE tasks ADD COLUMN end_criteria_config JSON NULL AFTER error_message',
    'SELECT "Column end_criteria_config already exists"');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Add total_tokens_used if it doesn't exist
SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = @dbname AND TABLE_NAME = @tablename AND COLUMN_NAME = 'total_tokens_used');
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE tasks ADD COLUMN total_tokens_used INT DEFAULT 0 AFTER end_criteria_config',
    'SELECT "Column total_tokens_used already exists"');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- end_criteria_config format: {"criteria": "success description", "max_iterations": 20, "max_tokens": 100000}
