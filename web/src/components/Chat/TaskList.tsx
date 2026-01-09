import React from 'react';
import type { Task } from '../../types';

interface TaskListProps {
  tasks: Task[];
  isLoading: boolean;
  onSelect: (task: Task) => void;
  onDelete: (taskName: string) => void;
}

const formatTime = (dateString: string): string => {
  const date = new Date(dateString);
  const now = new Date();
  const diff = now.getTime() - date.getTime();
  const minutes = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);
  const days = Math.floor(diff / 86400000);

  if (minutes < 1) return 'Just now';
  if (minutes < 60) return `${minutes}m ago`;
  if (hours < 24) return `${hours}h ago`;
  if (days < 7) return `${days}d ago`;
  return date.toLocaleDateString();
};

const TaskList: React.FC<TaskListProps> = ({ tasks, isLoading, onSelect, onDelete }) => {
  if (isLoading) {
    return (
      <div className="loading-container">
        <div className="spinner" />
      </div>
    );
  }

  if (tasks.length === 0) {
    return (
      <div className="task-list-empty">
        <div style={{ fontSize: 48, marginBottom: 16 }}>💬</div>
        <div style={{ fontSize: 16, fontWeight: 500, marginBottom: 8 }}>No chats yet</div>
        <div style={{ fontSize: 14 }}>Click "New" to start a conversation</div>
      </div>
    );
  }

  return (
    <div className="task-list">
      {tasks.map((task) => (
        <div key={task.id} className="task-item" onClick={() => onSelect(task)}>
          <div className="task-icon">💬</div>
          <div className="task-info">
            <div className="task-name">{task.task_name}</div>
            <div className="task-meta">
              <span className={`task-status ${task.status.toLowerCase()}`}>
                {task.status}
              </span>
              <span>{formatTime(task.created_at)}</span>
              {task.interaction_count !== undefined && (
                <span>{task.interaction_count} messages</span>
              )}
            </div>
          </div>
          <button
            className="task-delete"
            onClick={(e) => {
              e.stopPropagation();
              if (confirm('Delete this chat?')) {
                onDelete(task.task_name);
              }
            }}
          >
            🗑️
          </button>
        </div>
      ))}
    </div>
  );
};

export default TaskList;
