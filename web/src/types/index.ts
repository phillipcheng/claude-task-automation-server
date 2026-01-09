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

export interface ChatMessage {
  id: string;
  type: 'user_request' | 'claude_response' | 'simulated_human' | 'tool_result' | 'tool_group';
  content: string;
  timestamp: string;
  input_tokens?: number;
  output_tokens?: number;
}

export interface Project {
  id: string;
  name: string;
  path: string;
  default_access: 'read' | 'write';
  default_branch?: string;
  default_context?: string;
  user_id: string;
  created_at: string;
  updated_at: string;
}

export interface CreateTaskParams {
  task_name: string;
  description: string;
  user_id: string;
  auto_start?: boolean;
  max_iterations?: number;
  chat_mode?: boolean;
  project_context?: string;
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
