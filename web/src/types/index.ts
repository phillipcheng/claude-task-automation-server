export interface Task {
  id: number;
  task_name: string;
  description: string;
  status: TaskStatus;
  user_id: string;
  root_folder?: string;
  branch_name?: string;
  worktree_path?: string;
  project_context?: string;
  summary?: string;
  error_message?: string;
  total_tokens_used?: number;
  chat_mode?: boolean;
  created_at: string;
  updated_at: string;
  interaction_count?: number;
}

export type TaskStatus =
  | 'PENDING'
  | 'RUNNING'
  | 'PAUSED'
  | 'STOPPED'
  | 'TESTING'
  | 'COMPLETED'
  | 'FAILED'
  | 'FINISHED'
  | 'EXHAUSTED';

export interface ToolOutput {
  id: string;
  type: string;
  content: string;
  timestamp: string;
}

export interface ChatMessage {
  id: string;
  type: 'user_request' | 'claude_response' | 'simulated_human' | 'tool_result' | 'tool_group' | 'system_message';
  content: string;
  timestamp: string;
  input_tokens?: number;
  output_tokens?: number;
  images?: { base64: string; media_type: string }[];
  // Tool group specific fields
  tool_count?: number;
  summary?: string;
  tools?: ToolOutput[];
  first_timestamp?: string;
  last_timestamp?: string;
}

export type ProjectType = 'rpc' | 'web' | 'idl' | 'sdk' | 'other';

// Project config stored as JSON (non-searchable attributes)
export interface ProjectConfigData {
  context?: string;  // Description/context for Claude
  idl_repo?: string;  // Path to IDL repository
  idl_file?: string;  // IDL file path relative to repo root
  psm?: string;  // Platform Service Manager identifier
  test_dir?: string;  // Directory containing tests
  test_tags?: string;  // Test tags/flags
  overpass_module?: string;  // Overpass module dependency (e.g., code.byted.org/oec/rpcv2_xxx)
}

export interface Project {
  id: string;
  name: string;
  path: string;
  project_type?: ProjectType;
  default_branch: string;
  config?: ProjectConfigData;  // All non-searchable config in JSON
  user_id: string;
  created_at: string;
  updated_at: string;
}

// Task project configuration (for multi-project task creation)
export interface TaskProjectConfig {
  path: string;
  access: 'read' | 'write';
  context?: string;
  project_type?: ProjectType;
  idl_repo?: string;
  idl_file?: string;
  psm?: string;
}

export interface CreateTaskParams {
  task_name: string;
  description: string;
  user_id: string;
  auto_start?: boolean;
  max_iterations?: number;
  chat_mode?: boolean;
  project_context?: string;
  root_folder?: string;
  use_worktree?: boolean;
  projects?: TaskProjectConfig[];  // Multi-project with read/write access
}

export interface SendMessageParams {
  task_name: string;
  input: string;
  images?: ImageData[];
}

export interface ImageData {
  base64: string;
  media_type: string;
}
