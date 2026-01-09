import axios from 'axios';
import type { Task, ChatMessage, Project, CreateTaskParams, SendMessageParams } from '../types';

const API_BASE_URL = '/api/v1';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Task API
export const taskApi = {
  list: async (userId?: string, limit = 50): Promise<Task[]> => {
    const params: Record<string, string | number> = { limit };
    if (userId) params.user_id = userId;
    const response = await api.get('/tasks', { params });
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

  delete: async (taskName: string): Promise<void> => {
    await api.delete(`/tasks/by-name/${encodeURIComponent(taskName)}`);
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
  list: async (userId: string): Promise<Project[]> => {
    const response = await api.get('/projects', { params: { user_id: userId } });
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
};

export default api;
