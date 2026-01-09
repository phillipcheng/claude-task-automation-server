import React, { useState, useEffect } from 'react';
import { projectApi } from '../../services/api';
import type { Project } from '../../types';
import './Projects.css';

type ViewMode = 'list' | 'new' | 'edit';

const Projects: React.FC = () => {
  const [viewMode, setViewMode] = useState<ViewMode>('list');
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  // Form state
  const [name, setName] = useState('');
  const [path, setPath] = useState('');
  const [defaultAccess, setDefaultAccess] = useState<'read' | 'write'>('write');
  const [defaultBranch, setDefaultBranch] = useState('');
  const [defaultContext, setDefaultContext] = useState('');

  useEffect(() => {
    loadProjects();
  }, []);

  const loadProjects = async () => {
    setIsLoading(true);
    try {
      const data = await projectApi.list('web-user');
      setProjects(data);
    } catch (error) {
      console.error('Failed to load projects:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const resetForm = () => {
    setName('');
    setPath('');
    setDefaultAccess('write');
    setDefaultBranch('');
    setDefaultContext('');
    setSelectedProject(null);
  };

  const handleCreate = async () => {
    if (!name.trim() || !path.trim()) return;

    setIsLoading(true);
    try {
      await projectApi.create({
        name: name.trim(),
        path: path.trim(),
        default_access: defaultAccess,
        default_branch: defaultBranch.trim() || undefined,
        default_context: defaultContext.trim() || undefined,
        user_id: 'web-user',
      });
      resetForm();
      setViewMode('list');
      await loadProjects();
    } catch (error) {
      console.error('Failed to create project:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleUpdate = async () => {
    if (!selectedProject || !name.trim() || !path.trim()) return;

    setIsLoading(true);
    try {
      await projectApi.update(selectedProject.id, {
        name: name.trim(),
        path: path.trim(),
        default_access: defaultAccess,
        default_branch: defaultBranch.trim() || undefined,
        default_context: defaultContext.trim() || undefined,
      });
      resetForm();
      setViewMode('list');
      await loadProjects();
    } catch (error) {
      console.error('Failed to update project:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleDelete = async (projectId: string) => {
    if (!confirm('Delete this project?')) return;

    try {
      await projectApi.delete(projectId);
      await loadProjects();
    } catch (error) {
      console.error('Failed to delete project:', error);
    }
  };

  const handleEdit = (project: Project) => {
    setSelectedProject(project);
    setName(project.name);
    setPath(project.path);
    setDefaultAccess(project.default_access);
    setDefaultBranch(project.default_branch || '');
    setDefaultContext(project.default_context || '');
    setViewMode('edit');
  };

  const handleCancel = () => {
    resetForm();
    setViewMode('list');
  };

  if (viewMode === 'new' || viewMode === 'edit') {
    return (
      <div className="projects-container">
        <div className="projects-header">
          <button className="back-btn" onClick={handleCancel}>← Back</button>
          <h2>{viewMode === 'new' ? 'Add Project' : 'Edit Project'}</h2>
        </div>
        <div className="project-form">
          <div className="form-group">
            <label>Project Name *</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g., My Service"
            />
          </div>

          <div className="form-group">
            <label>Path *</label>
            <input
              type="text"
              value={path}
              onChange={(e) => setPath(e.target.value)}
              placeholder="/path/to/project"
            />
          </div>

          <div className="form-group">
            <label>Default Access</label>
            <select
              value={defaultAccess}
              onChange={(e) => setDefaultAccess(e.target.value as 'read' | 'write')}
            >
              <option value="write">Write</option>
              <option value="read">Read</option>
            </select>
          </div>

          <div className="form-group">
            <label>Default Branch (optional)</label>
            <input
              type="text"
              value={defaultBranch}
              onChange={(e) => setDefaultBranch(e.target.value)}
              placeholder="main"
            />
          </div>

          <div className="form-group">
            <label>Context (optional)</label>
            <textarea
              value={defaultContext}
              onChange={(e) => setDefaultContext(e.target.value)}
              placeholder="Description or context for the AI..."
              rows={3}
            />
          </div>

          <div className="form-actions">
            <button className="btn btn-secondary" onClick={handleCancel}>
              Cancel
            </button>
            <button
              className="btn btn-primary"
              onClick={viewMode === 'new' ? handleCreate : handleUpdate}
              disabled={!name.trim() || !path.trim() || isLoading}
            >
              {isLoading ? 'Saving...' : viewMode === 'new' ? 'Add Project' : 'Save Changes'}
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="projects-container">
      <div className="projects-header">
        <h2>Projects</h2>
        <button className="btn btn-primary" onClick={() => setViewMode('new')}>
          + Add Project
        </button>
      </div>

      {isLoading ? (
        <div className="loading-container">
          <div className="spinner" />
        </div>
      ) : projects.length === 0 ? (
        <div className="empty-state">
          <div style={{ fontSize: 48, marginBottom: 16 }}>📁</div>
          <div style={{ fontSize: 16, fontWeight: 500, marginBottom: 8 }}>No projects yet</div>
          <div style={{ fontSize: 14 }}>Add a project to get started</div>
        </div>
      ) : (
        <div className="projects-list">
          {projects.map((project) => (
            <div key={project.id} className="project-card">
              <div className="project-info">
                <div className="project-name">{project.name}</div>
                <div className="project-path">{project.path}</div>
                <div className="project-meta">
                  <span className={`access-badge ${project.default_access}`}>
                    {project.default_access}
                  </span>
                  {project.default_branch && (
                    <span className="branch">📌 {project.default_branch}</span>
                  )}
                </div>
              </div>
              <div className="project-actions">
                <button className="action-btn edit" onClick={() => handleEdit(project)}>
                  Edit
                </button>
                <button className="action-btn delete" onClick={() => handleDelete(project.id)}>
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default Projects;
