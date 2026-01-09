import React, { useState, useCallback } from 'react';

interface NewTaskProps {
  isLoading: boolean;
  onCreate: (taskName: string, description: string) => void;
  onCancel: () => void;
}

const NewTask: React.FC<NewTaskProps> = ({ isLoading, onCreate, onCancel }) => {
  const [taskName, setTaskName] = useState('');
  const [description, setDescription] = useState('');

  const handleSubmit = useCallback(() => {
    const name = taskName.trim();
    if (!name) return;
    onCreate(name, description.trim());
  }, [taskName, description, onCreate]);

  const isValid = taskName.trim().length > 0;

  return (
    <div className="new-task-form">
      <div className="form-group">
        <label className="form-label">Task Name</label>
        <input
          type="text"
          className="form-input"
          placeholder="e.g., fix-refund-bug, add-new-feature"
          value={taskName}
          onChange={(e) => setTaskName(e.target.value)}
          autoFocus
        />
      </div>

      <div className="form-group">
        <label className="form-label">Description (optional)</label>
        <textarea
          className="form-input form-textarea"
          placeholder="What would you like to work on?"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
      </div>

      <div className="form-actions">
        <button className="btn btn-secondary" onClick={onCancel}>
          Cancel
        </button>
        <button
          className="btn btn-primary"
          onClick={handleSubmit}
          disabled={!isValid || isLoading}
        >
          {isLoading ? 'Creating...' : 'Start Chat'}
        </button>
      </div>
    </div>
  );
};

export default NewTask;
