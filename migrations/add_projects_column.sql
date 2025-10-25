-- Add projects column to tasks table
-- This allows tasks to specify multiple projects with read/write access control
-- Projects with "write" access will get git worktree branches created
-- Projects with "read" access are read-only (no worktree needed)

ALTER TABLE tasks ADD COLUMN projects JSON;

-- Add a comment to the column
COMMENT ON COLUMN tasks.projects IS 'Multi-project configuration with read/write access. Format: [{"path": "/path/to/project1", "access": "write", "context": "Main service project", "branch_name": "feature-branch"}, {"path": "/path/to/project2", "access": "read", "context": "Shared SDK for runtime operations"}]';