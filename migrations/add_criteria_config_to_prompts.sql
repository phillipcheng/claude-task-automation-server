-- Add criteria_config column to prompts table for storing ending criteria templates

-- Check if column exists before adding
SET @dbname = DATABASE();
SET @tablename = "prompts";

-- Add criteria_config if it doesn't exist
SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = @dbname AND TABLE_NAME = @tablename AND COLUMN_NAME = 'criteria_config');

SET @sql = IF(@col_exists = 0,
    'ALTER TABLE prompts ADD COLUMN criteria_config JSON NULL AFTER usage_count',
    'SELECT "Column criteria_config already exists" AS message');

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Show result
SELECT IF(@col_exists = 0, 'Column criteria_config added successfully', 'Column criteria_config already exists') AS result;
