import React, { useState, useEffect, useCallback } from 'react';
import { projectApi } from '../../services/api';
import type { Project, ProjectType, ProjectConfigData } from '../../types';
import './Projects.css';

const PROJECT_TYPES: { value: ProjectType; label: string }[] = [
  { value: 'rpc', label: 'RPC Service' },
  { value: 'web', label: 'Web Application' },
  { value: 'idl', label: 'IDL Repository' },
  { value: 'sdk', label: 'SDK/Library' },
  { value: 'other', label: 'Other' },
];

// AI-based project type guessing from name, path, and context
function guessProjectType(name: string, path: string, context: string): ProjectType {
  const combined = `${name} ${path} ${context}`.toLowerCase();

  // IDL patterns - check first as it's most specific
  if (
    combined.includes('idl') ||
    combined.includes('proto') ||
    combined.includes('thrift') ||
    combined.includes('interface definition') ||
    /\.(proto|thrift)/.test(combined)
  ) {
    return 'idl';
  }

  // SDK patterns
  if (
    combined.includes('sdk') ||
    combined.includes('library') ||
    combined.includes('client') ||
    combined.includes('package') ||
    combined.includes('-go') ||
    combined.includes('-js') ||
    combined.includes('-py')
  ) {
    return 'sdk';
  }

  // Web patterns
  if (
    combined.includes('web') ||
    combined.includes('frontend') ||
    combined.includes('ui') ||
    combined.includes('react') ||
    combined.includes('vue') ||
    combined.includes('angular') ||
    combined.includes('next') ||
    combined.includes('dashboard')
  ) {
    return 'web';
  }

  // RPC patterns - services, servers, backends
  if (
    combined.includes('rpc') ||
    combined.includes('service') ||
    combined.includes('server') ||
    combined.includes('backend') ||
    combined.includes('api') ||
    combined.includes('handler') ||
    combined.includes('grpc')
  ) {
    return 'rpc';
  }

  return 'other';
}

type ViewMode = 'list' | 'new' | 'edit';
type SortBy = 'updated_at' | 'created_at' | 'name';

const PAGE_SIZE_OPTIONS = [10, 20, 50, 100];

const Projects: React.FC = () => {
  const [viewMode, setViewMode] = useState<ViewMode>('list');
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [userId, setUserId] = useState('default_user');
  const [nameFilter, setNameFilter] = useState('');
  const [sortBy, setSortBy] = useState<SortBy>('updated_at');
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(20);
  const [hasMore, setHasMore] = useState(true);

  // Multi-select for batch delete
  const [selectedProjectIds, setSelectedProjectIds] = useState<Set<string>>(new Set());
  const [isDeleting, setIsDeleting] = useState(false);

  // Form state - searchable fields
  const [name, setName] = useState('');
  const [path, setPath] = useState('');
  const [projectType, setProjectType] = useState<ProjectType>('other');
  const [defaultBranch, setDefaultBranch] = useState('');
  // Form state - config fields (stored as JSON)
  const [context, setContext] = useState('');
  const [idlRepo, setIdlRepo] = useState('');
  const [idlFile, setIdlFile] = useState('');
  const [psm, setPsm] = useState('');
  const [testDir, setTestDir] = useState('');
  const [testTags, setTestTags] = useState('');
  const [overpassModule, setOverpassModule] = useState('');

  // AI-recommended type
  const [recommendedType, setRecommendedType] = useState<ProjectType | null>(null);

  // Update recommendation when name, path, or context changes
  useEffect(() => {
    if (viewMode === 'new' || viewMode === 'edit') {
      const guessed = guessProjectType(name, path, context);
      if (guessed !== projectType && guessed !== 'other') {
        setRecommendedType(guessed);
      } else {
        setRecommendedType(null);
      }
    }
  }, [name, path, context, projectType, viewMode]);

  // Debounce name filter
  const [debouncedNameFilter, setDebouncedNameFilter] = useState('');
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedNameFilter(nameFilter);
      setPage(0);
    }, 300);
    return () => clearTimeout(timer);
  }, [nameFilter]);

  const loadProjects = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await projectApi.list({
        userId,
        nameFilter: debouncedNameFilter || undefined,
        sortBy,
        sortOrder: 'desc',
        limit: pageSize,
        offset: page * pageSize,
      });
      setProjects(data);
      setHasMore(data.length === pageSize);
      // Clear selection when loading new data
      setSelectedProjectIds(new Set());
    } catch (error) {
      console.error('Failed to load projects:', error);
    } finally {
      setIsLoading(false);
    }
  }, [userId, debouncedNameFilter, sortBy, page, pageSize]);

  useEffect(() => {
    loadProjects();
  }, [loadProjects]);

  const resetForm = () => {
    setName('');
    setPath('');
    setProjectType('other');
    setDefaultBranch('');
    setContext('');
    setIdlRepo('');
    setIdlFile('');
    setPsm('');
    setTestDir('');
    setTestTags('');
    setOverpassModule('');
    setSelectedProject(null);
  };

  const handleCreate = async () => {
    if (!name.trim() || !path.trim() || !defaultBranch.trim()) return;

    // Convert newlines to commas for storage
    const pathsForStorage = path.split('\n').map(p => p.trim()).filter(p => p).join(',');

    // Build config object with non-searchable attributes
    const config: ProjectConfigData = {};
    if (context.trim()) config.context = context.trim();
    if (idlRepo.trim()) config.idl_repo = idlRepo.trim();
    if (idlFile.trim()) config.idl_file = idlFile.trim();
    if (psm.trim()) config.psm = psm.trim();
    if (testDir.trim()) config.test_dir = testDir.trim();
    if (testTags.trim()) config.test_tags = testTags.trim();
    if (overpassModule.trim()) config.overpass_module = overpassModule.trim();

    setIsLoading(true);
    try {
      await projectApi.create({
        name: name.trim(),
        path: pathsForStorage,
        project_type: projectType,
        default_branch: defaultBranch.trim(),
        user_id: userId,
        config: Object.keys(config).length > 0 ? config : undefined,
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
    if (!selectedProject || !name.trim() || !path.trim() || !defaultBranch.trim()) return;

    // Convert newlines to commas for storage
    const pathsForStorage = path.split('\n').map(p => p.trim()).filter(p => p).join(',');

    // Build config object with non-searchable attributes
    const config: ProjectConfigData = {};
    if (context.trim()) config.context = context.trim();
    if (idlRepo.trim()) config.idl_repo = idlRepo.trim();
    if (idlFile.trim()) config.idl_file = idlFile.trim();
    if (psm.trim()) config.psm = psm.trim();
    if (testDir.trim()) config.test_dir = testDir.trim();
    if (testTags.trim()) config.test_tags = testTags.trim();
    if (overpassModule.trim()) config.overpass_module = overpassModule.trim();

    setIsLoading(true);
    try {
      await projectApi.update(selectedProject.id, {
        name: name.trim(),
        path: pathsForStorage,
        project_type: projectType,
        default_branch: defaultBranch.trim(),
        config: Object.keys(config).length > 0 ? config : undefined,
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
    // Convert commas to newlines for display
    setPath(project.path.split(',').map(p => p.trim()).join('\n'));
    setProjectType(project.project_type || 'other');
    setDefaultBranch(project.default_branch || '');
    // Load from config object
    const cfg = project.config || {};
    setContext(cfg.context || '');
    setIdlRepo(cfg.idl_repo || '');
    setIdlFile(cfg.idl_file || '');
    setPsm(cfg.psm || '');
    setTestDir(cfg.test_dir || '');
    setTestTags(cfg.test_tags || '');
    setOverpassModule(cfg.overpass_module || '');
    setViewMode('edit');
  };

  const handleClone = (project: Project) => {
    setSelectedProject(null);
    setName(`${project.name} (copy)`);
    setPath(project.path.split(',').map(p => p.trim()).join('\n'));
    setProjectType(project.project_type || 'other');
    setDefaultBranch(project.default_branch || '');
    // Load from config object
    const cfg = project.config || {};
    setContext(cfg.context || '');
    setIdlRepo(cfg.idl_repo || '');
    setIdlFile(cfg.idl_file || '');
    setPsm(cfg.psm || '');
    setTestDir(cfg.test_dir || '');
    setTestTags(cfg.test_tags || '');
    setOverpassModule(cfg.overpass_module || '');
    setViewMode('new');
  };

  // Batch delete handlers
  const handleBatchDelete = async () => {
    if (selectedProjectIds.size === 0) return;
    if (!confirm(`Delete ${selectedProjectIds.size} selected project(s)?`)) return;

    setIsDeleting(true);
    try {
      const result = await projectApi.batchDelete(Array.from(selectedProjectIds));
      if (result.failed > 0) {
        const errors = result.results
          .filter(r => !r.success)
          .map(r => `${r.project_name || r.project_id}: ${r.error}`)
          .join('\n');
        alert(`Deleted ${result.successful} of ${result.total} projects.\n\nFailed:\n${errors}`);
      }
      setSelectedProjectIds(new Set());
      await loadProjects();
    } catch (error: any) {
      console.error('Failed to batch delete:', error);
      const message = error?.response?.data?.detail || error?.message || 'Unknown error';
      alert(`Failed to delete projects: ${message}`);
    } finally {
      setIsDeleting(false);
    }
  };

  const handleToggleSelectAll = () => {
    if (selectedProjectIds.size === projects.length) {
      setSelectedProjectIds(new Set());
    } else {
      setSelectedProjectIds(new Set(projects.map(p => p.id)));
    }
  };

  const handleToggleSelect = (projectId: string) => {
    const newSelected = new Set(selectedProjectIds);
    if (newSelected.has(projectId)) {
      newSelected.delete(projectId);
    } else {
      newSelected.add(projectId);
    }
    setSelectedProjectIds(newSelected);
  };

  const handlePageSizeChange = (newSize: number) => {
    setPageSize(newSize);
    setPage(0);
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
            <label>Paths * (one per line for multi-repo projects)</label>
            <textarea
              value={path}
              onChange={(e) => setPath(e.target.value)}
              placeholder={"/path/to/repo1\n/path/to/repo2\n/path/to/repo3"}
              rows={3}
            />
          </div>

          <div className="form-group">
            <label>Project Type</label>
            <div className="type-select-row">
              <select
                value={projectType}
                onChange={(e) => setProjectType(e.target.value as ProjectType)}
              >
                {PROJECT_TYPES.map(pt => (
                  <option key={pt.value} value={pt.value}>{pt.label}</option>
                ))}
              </select>
              {recommendedType && (
                <button
                  type="button"
                  className="type-recommendation"
                  onClick={() => setProjectType(recommendedType)}
                  title="Click to apply recommended type"
                >
                  Suggested: {PROJECT_TYPES.find(pt => pt.value === recommendedType)?.label}
                </button>
              )}
            </div>
          </div>

          <div className="form-group">
            <label>Default Branch * (for release/integration testing)</label>
            <input
              type="text"
              value={defaultBranch}
              onChange={(e) => setDefaultBranch(e.target.value)}
              placeholder="main, develop, master..."
            />
          </div>

          <div className="form-group">
            <label>Context (optional)</label>
            <textarea
              value={context}
              onChange={(e) => setContext(e.target.value)}
              placeholder="Description or context for the AI..."
              rows={3}
            />
          </div>

          <div className="form-group">
            <label>IDL Repository (optional)</label>
            <input
              type="text"
              value={idlRepo}
              onChange={(e) => setIdlRepo(e.target.value)}
              placeholder="/path/to/idl/repo"
            />
          </div>

          <div className="form-group">
            <label>IDL File (optional, relative to IDL repo root)</label>
            <input
              type="text"
              value={idlFile}
              onChange={(e) => setIdlFile(e.target.value)}
              placeholder="api/service.proto"
            />
          </div>

          <div className="form-group">
            <label>PSM (optional, Platform Service Manager for overpass)</label>
            <input
              type="text"
              value={psm}
              onChange={(e) => setPsm(e.target.value)}
              placeholder="bytedance.service.name"
            />
          </div>

          {/* Overpass Module for RPC/Web/SDK types (used after IDL change) */}
          {(projectType === 'rpc' || projectType === 'web' || projectType === 'sdk') && (
            <div className="form-group">
              <label>Overpass Module (optional, for IDL code generation)</label>
              <input
                type="text"
                value={overpassModule}
                onChange={(e) => setOverpassModule(e.target.value)}
                placeholder="code.byted.org/oec/rpcv2_xxx"
              />
            </div>
          )}

          {/* Test Configuration Section */}
          {(projectType === 'rpc' || projectType === 'sdk') && (
            <>
              <div className="form-section-header">Test Configuration</div>

              <div className="form-group">
                <label>Test Directory (optional)</label>
                <input
                  type="text"
                  value={testDir}
                  onChange={(e) => setTestDir(e.target.value)}
                  placeholder="./... or test/ or tests/"
                />
              </div>

              <div className="form-group">
                <label>Test Tags (optional, e.g., Go build tags)</label>
                <input
                  type="text"
                  value={testTags}
                  onChange={(e) => setTestTags(e.target.value)}
                  placeholder="-tags local"
                />
              </div>
            </>
          )}

          <div className="form-actions">
            <button className="btn btn-secondary" onClick={handleCancel}>
              Cancel
            </button>
            <button
              className="btn btn-primary"
              onClick={viewMode === 'new' ? handleCreate : handleUpdate}
              disabled={!name.trim() || !path.trim() || !defaultBranch.trim() || isLoading}
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
        <div className="header-actions">
          <input
            type="text"
            className="search-filter"
            placeholder="Search by name..."
            value={nameFilter}
            onChange={(e) => setNameFilter(e.target.value)}
          />
          <input
            type="text"
            className="user-filter"
            placeholder="User ID..."
            value={userId}
            onChange={(e) => { setUserId(e.target.value); setPage(0); }}
          />
          <select
            className="filter-select"
            value={sortBy}
            onChange={(e) => { setSortBy(e.target.value as SortBy); setPage(0); }}
          >
            <option value="updated_at">Sort: Updated</option>
            <option value="created_at">Sort: Created</option>
            <option value="name">Sort: Name</option>
          </select>
          <button className="btn btn-primary" onClick={() => setViewMode('new')}>
            + Add Project
          </button>
        </div>
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
        <>
          {/* Selection action bar */}
          {selectedProjectIds.size > 0 && (
            <div className="selection-bar">
              <input
                type="checkbox"
                checked={selectedProjectIds.size === projects.length && projects.length > 0}
                onChange={handleToggleSelectAll}
              />
              <span>{selectedProjectIds.size} project(s) selected</span>
              <button
                className="btn btn-danger"
                onClick={handleBatchDelete}
                disabled={isDeleting}
              >
                {isDeleting ? 'Deleting...' : 'Delete Selected'}
              </button>
              <button
                className="btn btn-secondary"
                onClick={() => setSelectedProjectIds(new Set())}
              >
                Clear Selection
              </button>
            </div>
          )}
          <div className="projects-list">
            {projects.map((project) => (
              <div key={project.id} className={`project-card ${selectedProjectIds.has(project.id) ? 'selected' : ''}`}>
                <div className="project-checkbox">
                  <input
                    type="checkbox"
                    checked={selectedProjectIds.has(project.id)}
                    onChange={() => handleToggleSelect(project.id)}
                  />
                </div>
                <div className="project-info">
                  <div className="project-name clickable" onClick={() => handleEdit(project)}>{project.name}</div>
                  <div className="project-path">
                    {project.path.split(',').map((p, i) => (
                      <div key={i}>{p.trim()}</div>
                    ))}
                  </div>
                  <div className="project-meta">
                    <span className={`project-type type-${project.project_type || 'other'}`}>
                      {(project.project_type || 'other').toUpperCase()}
                    </span>
                    {project.default_branch && (
                      <span className="branch">{project.default_branch}</span>
                    )}
                  </div>
                  {(project.config?.idl_repo || project.config?.psm) && (
                    <div className="project-idl">
                      {project.config?.psm && <span>PSM: {project.config.psm}</span>}
                      {project.config?.psm && project.config?.idl_repo && <span> | </span>}
                      {project.config?.idl_repo && <span>IDL: {project.config?.idl_file ? `${project.config.idl_repo}/${project.config.idl_file}` : project.config.idl_repo}</span>}
                    </div>
                  )}
                  {project.config?.overpass_module && (
                    <div className="project-overpass">
                      <span className="overpass-badge">Overpass: {project.config.overpass_module}</span>
                    </div>
                  )}
                  {project.config?.test_dir && (
                    <div className="project-tests">
                      <span className="test-badge">Tests: {project.config.test_dir}</span>
                    </div>
                  )}
                </div>
                <div className="project-actions">
                  <button className="action-btn clone" onClick={() => handleClone(project)}>
                    Clone
                  </button>
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
          <div className="pagination">
            <button
              className="btn btn-secondary"
              onClick={() => setPage(p => Math.max(0, p - 1))}
              disabled={page === 0}
            >
              Previous
            </button>
            <span className="page-info">Page {page + 1}</span>
            <button
              className="btn btn-secondary"
              onClick={() => setPage(p => p + 1)}
              disabled={!hasMore}
            >
              Next
            </button>
            <select
              className="page-size-select"
              value={pageSize}
              onChange={(e) => handlePageSizeChange(Number(e.target.value))}
            >
              {PAGE_SIZE_OPTIONS.map(size => (
                <option key={size} value={size}>{size} / page</option>
              ))}
            </select>
          </div>
        </>
      )}
    </div>
  );
};

export default Projects;
