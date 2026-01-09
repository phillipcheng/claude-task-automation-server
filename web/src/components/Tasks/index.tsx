import React, { useState, useEffect, useCallback } from 'react';
import { taskApi } from '../../services/api';
import type { Task, CreateTaskParams } from '../../types';
import './Tasks.css';

type ViewMode = 'list' | 'new' | 'detail';
type FilterStatus = 'all' | 'running' | 'pending' | 'completed';

const Tasks: React.FC = () => {
  const [viewMode, setViewMode] = useState<ViewMode>('list');
  const [tasks, setTasks] = useState<Task[]>([]);
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [filter, setFilter] = useState<FilterStatus>('all');

  // New task form
  const [taskName, setTaskName] = useState('');
  const [description, setDescription] = useState('');
  const [autoStart, setAutoStart] = useState(true);

  useEffect(() => {
    loadTasks();
  }, []);

  const loadTasks = async () => {
    setIsLoading(true);
    try {
      const data = await taskApi.list();
      setTasks(data);
    } catch (error) {
      console.error('Failed to load tasks:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleCreateTask = async () => {
    if (!taskName.trim()) return;

    setIsLoading(true);
    try {
      const params: CreateTaskParams = {
        task_name: taskName.trim(),
        description: description.trim() || taskName.trim(),
        user_id: 'web-user',
        auto_start: autoStart,
        max_iterations: 50,
        chat_mode: false,
        project_context: description.trim() || undefined,
      };

      await taskApi.create(params);
      setTaskName('');
      setDescription('');
      setViewMode('list');
      await loadTasks();
    } catch (error) {
      console.error('Failed to create task:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleStart = async (taskName: string) => {
    try {
      await taskApi.start(taskName);
      await loadTasks();
    } catch (error) {
      console.error('Failed to start task:', error);
    }
  };

  const handleStop = async (taskName: string) => {
    try {
      await taskApi.stop(taskName);
      await loadTasks();
    } catch (error) {
      console.error('Failed to stop task:', error);
    }
  };

  const handleDelete = async (taskName: string) => {
    if (!confirm('Delete this task?')) return;
    try {
      await taskApi.delete(taskName);
      await loadTasks();
    } catch (error) {
      console.error('Failed to delete task:', error);
    }
  };

  const handleViewDetail = async (task: Task) => {
    setSelectedTask(task);
    setViewMode('detail');
  };

  const filteredTasks = tasks.filter((task) => {
    if (filter === 'all') return true;
    if (filter === 'running') return task.status === 'RUNNING';
    if (filter === 'pending') return task.status === 'PENDING';
    if (filter === 'completed') return ['COMPLETED', 'FINISHED', 'FAILED'].includes(task.status);
    return true;
  });

  const formatTime = (dateString: string): string => {
    const date = new Date(dateString);
    return date.toLocaleString();
  };

  if (viewMode === 'new') {
    return (
      <div className="tasks-container">
        <div className="tasks-header">
          <button className="back-btn" onClick={() => setViewMode('list')}>← Back</button>
          <h2>Create New Task</h2>
        </div>
        <div className="new-task-form">
          <div className="form-group">
            <label>Task Name *</label>
            <input
              type="text"
              value={taskName}
              onChange={(e) => setTaskName(e.target.value)}
              placeholder="e.g., implement-feature-x"
            />
          </div>
          <div className="form-group">
            <label>Description</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Describe what the task should accomplish..."
              rows={4}
            />
          </div>
          <div className="form-group checkbox">
            <label>
              <input
                type="checkbox"
                checked={autoStart}
                onChange={(e) => setAutoStart(e.target.checked)}
              />
              Auto-start task
            </label>
          </div>
          <div className="form-actions">
            <button className="btn btn-secondary" onClick={() => setViewMode('list')}>
              Cancel
            </button>
            <button
              className="btn btn-primary"
              onClick={handleCreateTask}
              disabled={!taskName.trim() || isLoading}
            >
              {isLoading ? 'Creating...' : 'Create Task'}
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (viewMode === 'detail' && selectedTask) {
    return (
      <div className="tasks-container">
        <div className="tasks-header">
          <button className="back-btn" onClick={() => setViewMode('list')}>← Back</button>
          <h2>{selectedTask.task_name}</h2>
        </div>
        <div className="task-detail">
          <div className="detail-section">
            <h3>Status</h3>
            <span className={`status-badge ${selectedTask.status.toLowerCase()}`}>
              {selectedTask.status}
            </span>
          </div>
          <div className="detail-section">
            <h3>Description</h3>
            <p>{selectedTask.description || 'No description'}</p>
          </div>
          {selectedTask.summary && (
            <div className="detail-section">
              <h3>Summary</h3>
              <p>{selectedTask.summary}</p>
            </div>
          )}
          {selectedTask.error_message && (
            <div className="detail-section error">
              <h3>Error</h3>
              <p>{selectedTask.error_message}</p>
            </div>
          )}
          <div className="detail-section">
            <h3>Details</h3>
            <dl>
              <dt>Created</dt>
              <dd>{formatTime(selectedTask.created_at)}</dd>
              <dt>Updated</dt>
              <dd>{formatTime(selectedTask.updated_at)}</dd>
              {selectedTask.total_tokens_used && (
                <>
                  <dt>Tokens Used</dt>
                  <dd>{selectedTask.total_tokens_used.toLocaleString()}</dd>
                </>
              )}
              {selectedTask.branch_name && (
                <>
                  <dt>Branch</dt>
                  <dd>{selectedTask.branch_name}</dd>
                </>
              )}
            </dl>
          </div>
          <div className="detail-actions">
            {selectedTask.status === 'PENDING' && (
              <button className="btn btn-primary" onClick={() => handleStart(selectedTask.task_name)}>
                Start
              </button>
            )}
            {selectedTask.status === 'RUNNING' && (
              <button className="btn btn-warning" onClick={() => handleStop(selectedTask.task_name)}>
                Stop
              </button>
            )}
            {selectedTask.status === 'STOPPED' && (
              <button className="btn btn-primary" onClick={() => handleStart(selectedTask.task_name)}>
                Resume
              </button>
            )}
            <button className="btn btn-danger" onClick={() => handleDelete(selectedTask.task_name)}>
              Delete
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="tasks-container">
      <div className="tasks-header">
        <h2>Tasks</h2>
        <div className="header-actions">
          <select
            className="filter-select"
            value={filter}
            onChange={(e) => setFilter(e.target.value as FilterStatus)}
          >
            <option value="all">All Tasks</option>
            <option value="running">Running</option>
            <option value="pending">Pending</option>
            <option value="completed">Completed</option>
          </select>
          <button className="btn btn-primary" onClick={() => setViewMode('new')}>
            + New Task
          </button>
        </div>
      </div>

      {isLoading ? (
        <div className="loading-container">
          <div className="spinner" />
        </div>
      ) : filteredTasks.length === 0 ? (
        <div className="empty-state">
          <div style={{ fontSize: 48, marginBottom: 16 }}>📋</div>
          <div style={{ fontSize: 16, fontWeight: 500, marginBottom: 8 }}>No tasks found</div>
          <div style={{ fontSize: 14 }}>Create a new task to get started</div>
        </div>
      ) : (
        <div className="tasks-list">
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Status</th>
                <th>Created</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredTasks.map((task) => (
                <tr key={task.id} onClick={() => handleViewDetail(task)}>
                  <td className="task-name-cell">
                    <div className="task-name">{task.task_name}</div>
                    {task.description && (
                      <div className="task-desc">{task.description}</div>
                    )}
                  </td>
                  <td>
                    <span className={`status-badge ${task.status.toLowerCase()}`}>
                      {task.status}
                    </span>
                  </td>
                  <td>{formatTime(task.created_at)}</td>
                  <td className="actions-cell" onClick={(e) => e.stopPropagation()}>
                    {task.status === 'PENDING' && (
                      <button className="action-btn start" onClick={() => handleStart(task.task_name)}>
                        Start
                      </button>
                    )}
                    {task.status === 'RUNNING' && (
                      <button className="action-btn stop" onClick={() => handleStop(task.task_name)}>
                        Stop
                      </button>
                    )}
                    <button className="action-btn delete" onClick={() => handleDelete(task.task_name)}>
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export default Tasks;
