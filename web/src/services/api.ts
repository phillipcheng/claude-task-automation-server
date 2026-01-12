import axios from 'axios';
import type { Task, ChatMessage, Project, CreateTaskParams, SendMessageParams } from '../types';

const API_BASE_URL = '/api/v1';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Task list query parameters
export interface TaskListParams {
  userId?: string;
  status?: string;
  nameFilter?: string;
  sortBy?: 'created_at' | 'updated_at' | 'task_name';
  sortOrder?: 'asc' | 'desc';
  limit?: number;
  offset?: number;
}

// Project list query parameters
export interface ProjectListParams {
  userId: string;
  nameFilter?: string;
  sortBy?: 'name' | 'created_at' | 'updated_at';
  sortOrder?: 'asc' | 'desc';
  limit?: number;
  offset?: number;
}

// Task API
export const taskApi = {
  list: async (params: TaskListParams = {}): Promise<Task[]> => {
    const queryParams: Record<string, string | number> = {
      limit: params.limit ?? 50,
      offset: params.offset ?? 0,
      sort_by: params.sortBy ?? 'updated_at',
      sort_order: params.sortOrder ?? 'desc',
    };
    if (params.userId) queryParams.user_id = params.userId;
    if (params.status) queryParams.status = params.status;
    if (params.nameFilter) queryParams.name_filter = params.nameFilter;
    const response = await api.get('/tasks', { params: queryParams });
    return response.data;
  },

  get: async (taskName: string): Promise<Task> => {
    const response = await api.get(`/tasks/by-name/${encodeURIComponent(taskName)}`);
    return response.data;
  },

  create: async (params: CreateTaskParams): Promise<Task> => {
    const response = await api.post('/tasks', params);
    return response.data;
  },

  start: async (taskName: string): Promise<void> => {
    await api.post(`/tasks/by-name/${encodeURIComponent(taskName)}/start`);
  },

  stop: async (taskName: string): Promise<void> => {
    await api.post(`/tasks/by-name/${encodeURIComponent(taskName)}/stop`);
  },

  resume: async (taskName: string): Promise<void> => {
    await api.post(`/tasks/by-name/${encodeURIComponent(taskName)}/resume`);
  },

  recover: async (taskName: string): Promise<{
    message: string;
    status: string;
    previous_session_cleared: boolean;
    conversation_preserved: boolean;
    interactions_count: number;
  }> => {
    const response = await api.post(`/tasks/by-name/${encodeURIComponent(taskName)}/recover`);
    return response.data;
  },

  mergeToTest: async (taskName: string): Promise<{ message: string; source_branch: string; target_branch: string; pushed: boolean }> => {
    const response = await api.post(`/tasks/by-name/${encodeURIComponent(taskName)}/merge-to-test`);
    return response.data;
  },

  delete: async (taskName: string): Promise<void> => {
    await api.delete(`/tasks/by-name/${encodeURIComponent(taskName)}`);
  },

  batchDelete: async (taskNames: string[], cleanupWorktree: boolean = true): Promise<{
    total: number;
    successful: number;
    failed: number;
    results: Array<{ task_name: string; success: boolean; message?: string; error?: string }>;
  }> => {
    const response = await api.post('/tasks/batch-delete', {
      task_names: taskNames,
      cleanup_worktree: cleanupWorktree,
    });
    return response.data;
  },

  clone: async (taskName: string, newName?: string, continueSession: boolean = false): Promise<Task> => {
    const params: Record<string, string | boolean> = {};
    if (newName) params.new_name = newName;
    if (continueSession) params.continue_session = true;
    const response = await api.post(`/tasks/by-name/${encodeURIComponent(taskName)}/clone`, null, { params });
    return response.data;
  },

  getHistory: async (taskName: string): Promise<ChatMessage[]> => {
    const response = await api.get(`/tasks/by-name/${encodeURIComponent(taskName)}/conversation`);
    return response.data.conversation || [];
  },

  sendMessage: async (params: SendMessageParams): Promise<void> => {
    await api.post(`/tasks/by-name/${encodeURIComponent(params.task_name)}/set-input`, {
      input: params.input,
      images: params.images,
    });
  },

  subscribeToStream: (
    taskName: string,
    onMessage: (message: ChatMessage) => void,
    onStatus: (status: { status: string; total_interactions: number }) => void,
    onError?: (error: Event) => void
  ): (() => void) => {
    const url = `${API_BASE_URL}/tasks/by-name/${encodeURIComponent(taskName)}/stream`;
    const eventSource = new EventSource(url);

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'status') {
          onStatus(data);
        } else {
          onMessage(data);
        }
      } catch (e) {
        console.error('Failed to parse SSE message:', e);
      }
    };

    eventSource.onerror = (error) => {
      console.error('SSE connection error:', error);
      onError?.(error);
    };

    return () => {
      eventSource.close();
    };
  },
};

// Project API
export const projectApi = {
  list: async (params: ProjectListParams): Promise<Project[]> => {
    const queryParams: Record<string, string | number> = {
      user_id: params.userId,
      limit: params.limit ?? 50,
      offset: params.offset ?? 0,
      sort_by: params.sortBy ?? 'updated_at',
      sort_order: params.sortOrder ?? 'desc',
    };
    if (params.nameFilter) queryParams.name_filter = params.nameFilter;
    const response = await api.get('/projects', { params: queryParams });
    return response.data;
  },

  get: async (projectId: string): Promise<Project> => {
    const response = await api.get(`/projects/${projectId}`);
    return response.data;
  },

  create: async (project: Omit<Project, 'id' | 'created_at' | 'updated_at'>): Promise<Project> => {
    const response = await api.post('/projects', project);
    return response.data;
  },

  update: async (projectId: string, updates: Partial<Project>): Promise<Project> => {
    const response = await api.put(`/projects/${projectId}`, updates);
    return response.data;
  },

  delete: async (projectId: string): Promise<void> => {
    await api.delete(`/projects/${projectId}`);
  },

  batchDelete: async (projectIds: string[]): Promise<{
    total: number;
    successful: number;
    failed: number;
    results: Array<{ project_id: string; project_name?: string; success: boolean; message?: string; error?: string }>;
  }> => {
    const response = await api.post('/projects/batch-delete', {
      project_ids: projectIds,
    });
    return response.data;
  },
};

export default api;
