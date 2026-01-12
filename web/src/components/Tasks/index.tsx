import React, { useState, useEffect, useCallback, useRef } from 'react';
import { taskApi, projectApi } from '../../services/api';
import type { Task, CreateTaskParams, ChatMessage, Project } from '../../types';
import MessageList from '../Chat/MessageList';
import ChatInput from '../Chat/ChatInput';
import '../Chat/Chat.css';
import './Tasks.css';

type ViewMode = 'list' | 'new' | 'detail' | 'tabs';
type FilterStatus = 'all' | 'running' | 'pending' | 'completed';
type FilterMode = 'all' | 'chat' | 'work';
type SortBy = 'updated_at' | 'created_at' | 'task_name';

const PAGE_SIZE_OPTIONS = [10, 20, 50, 100];

// Tab data for each open task
interface TabData {
  task: Task;
  messages: ChatMessage[];
  seenMessageIds: Set<string>;
  unsubscribe: (() => void) | null;
  isSending: boolean;
  detailTab: 'info' | 'conversation';
  suggestedMessage: string;
}

const Tasks: React.FC = () => {
  const [viewMode, setViewMode] = useState<ViewMode>('list');
  const [tasks, setTasks] = useState<Task[]>([]);
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [filter, setFilter] = useState<FilterStatus>('all');
  const [modeFilter, setModeFilter] = useState<FilterMode>('all');
  const [userId, setUserId] = useState('');
  const [nameFilter, setNameFilter] = useState('');
  const [sortBy, setSortBy] = useState<SortBy>('updated_at');
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(20);
  const [hasMore, setHasMore] = useState(true);

  // Multi-select for batch delete
  const [selectedTaskNames, setSelectedTaskNames] = useState<Set<string>>(new Set());
  const [isDeleting, setIsDeleting] = useState(false);

  // New task form
  const [taskName, setTaskName] = useState('');
  const [description, setDescription] = useState('');
  const [autoStart, setAutoStart] = useState(true);
  const [chatMode, setChatMode] = useState(false);
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProjectIds, setSelectedProjectIds] = useState<string[]>([]);
  const [detailTab, setDetailTab] = useState<'info' | 'conversation'>('info');

  // Chat state (for single detail view)
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isSending, setIsSending] = useState(false);
  const [suggestedMessage, setSuggestedMessage] = useState<string>('');
  const unsubscribeRef = useRef<(() => void) | null>(null);
  const seenMessageIdsRef = useRef<Set<string>>(new Set());

  // Tab view state
  const [openTabs, setOpenTabs] = useState<string[]>([]); // Array of task_names
  const [activeTabIndex, setActiveTabIndex] = useState(0);
  const [tabsData, setTabsData] = useState<Map<string, TabData>>(new Map());

  // Debounce name filter
  const [debouncedNameFilter, setDebouncedNameFilter] = useState('');
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedNameFilter(nameFilter);
      setPage(0);
    }, 300);
    return () => clearTimeout(timer);
  }, [nameFilter]);

  // Cleanup subscription on unmount
  useEffect(() => {
    return () => {
      if (unsubscribeRef.current) {
        unsubscribeRef.current();
      }
      // Cleanup all tab subscriptions
      tabsData.forEach((data) => {
        if (data.unsubscribe) {
          data.unsubscribe();
        }
      });
    };
  }, []);

  const loadTasks = useCallback(async () => {
    setIsLoading(true);
    try {
      const statusParam = filter === 'all' ? undefined :
        filter === 'running' ? 'running' :
        filter === 'pending' ? 'pending' :
        filter === 'completed' ? 'completed' : undefined;

      const data = await taskApi.list({
        userId: userId || undefined,
        status: statusParam,
        nameFilter: debouncedNameFilter || undefined,
        sortBy,
        sortOrder: 'desc',
        limit: pageSize,
        offset: page * pageSize,
      });

      // Filter by mode on client-side (could be moved to backend)
      const filteredData = modeFilter === 'all' ? data :
        modeFilter === 'chat' ? data.filter(t => t.chat_mode) :
        data.filter(t => !t.chat_mode);

      setTasks(filteredData);
      setHasMore(data.length === pageSize);
      // Clear selection when loading new data
      setSelectedTaskNames(new Set());
    } catch (error) {
      console.error('Failed to load tasks:', error);
    } finally {
      setIsLoading(false);
    }
  }, [userId, filter, modeFilter, debouncedNameFilter, sortBy, page, pageSize]);

  useEffect(() => {
    loadTasks();
  }, [loadTasks]);

  const subscribeToTask = useCallback((taskName: string) => {
    if (unsubscribeRef.current) {
      unsubscribeRef.current();
    }

    unsubscribeRef.current = taskApi.subscribeToStream(
      taskName,
      (message) => {
        if (!seenMessageIdsRef.current.has(message.id)) {
          seenMessageIdsRef.current.add(message.id);
          setMessages((prev) => {
            const newMessages = [...prev, message];

            // Check if this is a planning response that needs confirmation
            // A planning response is a claude_response that contains "```planning" block
            if (message.type === 'claude_response' && message.content) {
              const hasPlanningBlock = message.content.includes('```planning');
              const needsConfirmation = message.content.toLowerCase().includes('needs_write') ||
                                        message.content.toLowerCase().includes('write_target');

              if (hasPlanningBlock && needsConfirmation) {
                // Suggest a confirmation message
                setSuggestedMessage('I confirm the plan. Please proceed.');
              }
            }

            return newMessages;
          });
        }
      },
      () => {
        // Status updates - could refresh task
      },
      (error) => {
        console.error('SSE error:', error);
      }
    );
  }, []);

  // Subscribe to SSE for a tab
  const subscribeToTaskTab = useCallback((taskNameToSubscribe: string) => {
    const unsubscribe = taskApi.subscribeToStream(
      taskNameToSubscribe,
      (message) => {
        setTabsData((prev) => {
          const newMap = new Map(prev);
          const data = newMap.get(taskNameToSubscribe);
          if (data && !data.seenMessageIds.has(message.id)) {
            data.seenMessageIds.add(message.id);
            data.messages = [...data.messages, message];

            // Check if this is a planning response that needs confirmation
            if (message.type === 'claude_response' && message.content) {
              const hasPlanningBlock = message.content.includes('```planning');
              const needsConfirmation = message.content.toLowerCase().includes('needs_write') ||
                                        message.content.toLowerCase().includes('write_target');

              if (hasPlanningBlock && needsConfirmation) {
                data.suggestedMessage = 'I confirm the plan. Please proceed.';
              }
            }

            newMap.set(taskNameToSubscribe, { ...data });
          }
          return newMap;
        });
      },
      () => {
        // Status updates
      },
      (error) => {
        console.error('SSE error for tab:', error);
      }
    );
    return unsubscribe;
  }, []);

  // Open a task in a new tab
  const openTaskInTab = useCallback(async (task: Task) => {
    // Check if already open
    if (openTabs.includes(task.task_name)) {
      // Just switch to that tab
      setActiveTabIndex(openTabs.indexOf(task.task_name));
      setViewMode('tabs');
      return;
    }

    // Load conversation history
    let history: ChatMessage[] = [];
    try {
      history = await taskApi.getHistory(task.task_name);
    } catch (error) {
      console.error('Failed to load conversation:', error);
    }

    const seenIds = new Set(history.map((m) => m.id));

    // Subscribe if active
    let unsubscribe: (() => void) | null = null;
    if (['RUNNING', 'PAUSED', 'PENDING'].includes(task.status)) {
      unsubscribe = subscribeToTaskTab(task.task_name);
    }

    const tabData: TabData = {
      task,
      messages: history,
      seenMessageIds: seenIds,
      unsubscribe,
      isSending: false,
      detailTab: task.chat_mode ? 'conversation' : 'info',
      suggestedMessage: '',
    };

    setTabsData((prev) => {
      const newMap = new Map(prev);
      newMap.set(task.task_name, tabData);
      return newMap;
    });

    setOpenTabs((prev) => [...prev, task.task_name]);
    setActiveTabIndex(openTabs.length); // New tab will be at this index
    setViewMode('tabs');
  }, [openTabs, subscribeToTaskTab]);

  // Close a tab
  const closeTab = useCallback((taskNameToClose: string) => {
    const tabData = tabsData.get(taskNameToClose);
    if (tabData?.unsubscribe) {
      tabData.unsubscribe();
    }

    setTabsData((prev) => {
      const newMap = new Map(prev);
      newMap.delete(taskNameToClose);
      return newMap;
    });

    setOpenTabs((prev) => {
      const newTabs = prev.filter((name) => name !== taskNameToClose);
      // Adjust active tab index
      const closedIndex = prev.indexOf(taskNameToClose);
      if (newTabs.length === 0) {
        setViewMode('list');
      } else if (activeTabIndex >= closedIndex && activeTabIndex > 0) {
        setActiveTabIndex(activeTabIndex - 1);
      }
      return newTabs;
    });
  }, [tabsData, activeTabIndex]);

  // Send message in a tab
  const handleTabSendMessage = useCallback(async (taskNameForMessage: string, text: string, images?: { base64: string; media_type: string }[]) => {
    const tabData = tabsData.get(taskNameForMessage);
    if (!tabData) return;

    // Set sending state
    setTabsData((prev) => {
      const newMap = new Map(prev);
      const data = newMap.get(taskNameForMessage);
      if (data) {
        newMap.set(taskNameForMessage, { ...data, isSending: true });
      }
      return newMap;
    });

    try {
      await taskApi.sendMessage({
        task_name: taskNameForMessage,
        input: text,
        images,
      });

      // If task is PENDING, start it
      if (tabData.task.status === 'PENDING') {
        try {
          await taskApi.start(taskNameForMessage);
        } catch (startError: any) {
          if (startError?.response?.status !== 400) {
            throw startError;
          }
        }

        // Update task status and subscribe
        const unsubscribe = subscribeToTaskTab(taskNameForMessage);
        setTabsData((prev) => {
          const newMap = new Map(prev);
          const data = newMap.get(taskNameForMessage);
          if (data) {
            newMap.set(taskNameForMessage, {
              ...data,
              task: { ...data.task, status: 'RUNNING' },
              unsubscribe,
              isSending: false,
            });
          }
          return newMap;
        });
      } else {
        setTabsData((prev) => {
          const newMap = new Map(prev);
          const data = newMap.get(taskNameForMessage);
          if (data) {
            newMap.set(taskNameForMessage, { ...data, isSending: false });
          }
          return newMap;
        });
      }
    } catch (error) {
      console.error('Failed to send message:', error);
      setTabsData((prev) => {
        const newMap = new Map(prev);
        const data = newMap.get(taskNameForMessage);
        if (data) {
          newMap.set(taskNameForMessage, { ...data, isSending: false });
        }
        return newMap;
      });
    }
  }, [tabsData, subscribeToTaskTab]);

  // Change detail tab in a tab
  const handleTabDetailTabChange = useCallback((taskNameForTab: string, newDetailTab: 'info' | 'conversation') => {
    setTabsData((prev) => {
      const newMap = new Map(prev);
      const data = newMap.get(taskNameForTab);
      if (data) {
        newMap.set(taskNameForTab, { ...data, detailTab: newDetailTab });
      }
      return newMap;
    });
  }, []);

  // Clear suggested message for a tab
  const handleTabSuggestedMessageUsed = useCallback((taskNameForTab: string) => {
    setTabsData((prev) => {
      const newMap = new Map(prev);
      const data = newMap.get(taskNameForTab);
      if (data) {
        newMap.set(taskNameForTab, { ...data, suggestedMessage: '' });
      }
      return newMap;
    });
  }, []);

  // Handle tab task actions (stop/resume)
  const handleTabStop = useCallback(async (taskNameToStop: string) => {
    try {
      await taskApi.stop(taskNameToStop);
      setTabsData((prev) => {
        const newMap = new Map(prev);
        const data = newMap.get(taskNameToStop);
        if (data) {
          newMap.set(taskNameToStop, {
            ...data,
            task: { ...data.task, status: 'STOPPED' },
          });
        }
        return newMap;
      });
      await loadTasks();
    } catch (error) {
      console.error('Failed to stop task:', error);
    }
  }, []);

  const handleTabResume = useCallback(async (taskNameToResume: string) => {
    try {
      await taskApi.resume(taskNameToResume);
      const unsubscribe = subscribeToTaskTab(taskNameToResume);
      setTabsData((prev) => {
        const newMap = new Map(prev);
        const data = newMap.get(taskNameToResume);
        if (data) {
          if (data.unsubscribe) {
            data.unsubscribe();
          }
          newMap.set(taskNameToResume, {
            ...data,
            task: { ...data.task, status: 'RUNNING' },
            unsubscribe,
          });
        }
        return newMap;
      });
      await loadTasks();
    } catch (error) {
      console.error('Failed to resume task:', error);
    }
  }, [subscribeToTaskTab]);

  const loadProjects = useCallback(async () => {
    try {
      const data = await projectApi.list({
        userId: userId || 'default_user',
        sortBy: 'name',
        sortOrder: 'asc',
        limit: 100,
      });
      setProjects(data);
    } catch (error) {
      console.error('Failed to load projects:', error);
    }
  }, [userId]);

  const handleCreateTask = async () => {
    if (!taskName.trim()) return;

    // Get selected projects details
    const selectedProjects = projects.filter(p => selectedProjectIds.includes(p.id));

    setIsLoading(true);
    try {
      // Build project context from all selected projects + description
      let projectContext: string | undefined;
      if (selectedProjects.length > 0) {
        projectContext = selectedProjects.map(proj => {
          let ctx = `Project: ${proj.name}\nPath: ${proj.path}`;
          if (proj.config?.context) {
            ctx += `\n${proj.config.context}`;
          }
          return ctx;
        }).join('\n\n---\n\n');

        if (description.trim()) {
          projectContext += `\n\nTask Description:\n${description.trim()}`;
        }
      } else {
        projectContext = description.trim() || undefined;
      }

      // Build projects array from all selected projects' paths
      // Start with ALL projects as 'read' access
      // Backend will run planning phase to identify write targets and create worktrees dynamically
      let projectConfigs: Array<{
        path: string;
        access: 'read' | 'write';
        context?: string;
        idl_repo?: string;
        idl_file?: string;
        psm?: string;
      }> | undefined;
      let rootFolder: string | undefined;

      if (selectedProjects.length > 0) {
        projectConfigs = [];
        for (const proj of selectedProjects) {
          const paths = proj.path.split(',').map(p => p.trim()).filter(p => p);
          for (const path of paths) {
            if (!rootFolder) {
              rootFolder = path; // First path from first project as root_folder
            }
            projectConfigs.push({
              path,
              access: 'read' as const,  // Always start as read, backend upgrades dynamically
              context: proj.config?.context || undefined,
              // Include IDL configuration for overpass MCP integration
              idl_repo: proj.config?.idl_repo || undefined,
              idl_file: proj.config?.idl_file || undefined,
              psm: proj.config?.psm || undefined,
            });
          }
        }
      }

      const params: CreateTaskParams = {
        task_name: taskName.trim(),
        description: description.trim() || taskName.trim(),
        user_id: userId || 'default_user',
        auto_start: chatMode ? false : autoStart,
        max_iterations: 50,
        chat_mode: chatMode,
        project_context: projectContext,
        root_folder: rootFolder,
        use_worktree: false,  // Don't create worktree at task creation - let planning phase decide
        projects: projectConfigs,
      };

      console.log('Creating task with params:', params);
      console.log('chatMode state:', chatMode);

      const task = await taskApi.create(params);
      console.log('Created task:', task);

      // For chat mode, auto-start and navigate to conversation view
      if (chatMode) {
        seenMessageIdsRef.current.clear();
        setMessages([]);

        // If description provided, send as first message
        if (description.trim()) {
          await taskApi.sendMessage({ task_name: taskName.trim(), input: description.trim() });
        }

        // Auto-start chat task
        await taskApi.start(taskName.trim());
        setSelectedTask({ ...task, status: 'RUNNING' });
        subscribeToTask(taskName.trim());

        // Load conversation history
        try {
          const history = await taskApi.getHistory(taskName.trim());
          setMessages(history);
          history.forEach((m) => seenMessageIdsRef.current.add(m.id));
        } catch (e) {
          console.error('Failed to load history:', e);
        }

        setViewMode('detail');
      } else {
        setViewMode('list');
      }

      setTaskName('');
      setDescription('');
      setChatMode(false);
      setSelectedProjectIds([]);
      await loadTasks();
    } catch (error: any) {
      console.error('Failed to create task:', error);
      const message = error?.response?.data?.detail || error?.message || 'Unknown error';
      alert(`Failed to create task: ${message}`);
    } finally {
      setIsLoading(false);
    }
  };

  const handleStart = async (taskName: string) => {
    try {
      await taskApi.start(taskName);
      if (selectedTask?.task_name === taskName) {
        setSelectedTask({ ...selectedTask, status: 'RUNNING' });
        if (selectedTask.chat_mode) {
          subscribeToTask(taskName);
        }
      }
      await loadTasks();
    } catch (error) {
      console.error('Failed to start task:', error);
    }
  };

  const handleStop = async (taskName: string) => {
    try {
      await taskApi.stop(taskName);
      if (selectedTask?.task_name === taskName) {
        setSelectedTask({ ...selectedTask, status: 'STOPPED' });
      }
      await loadTasks();
    } catch (error) {
      console.error('Failed to stop task:', error);
    }
  };

  const handleResume = async (taskName: string) => {
    try {
      await taskApi.resume(taskName);
      if (selectedTask?.task_name === taskName) {
        setSelectedTask({ ...selectedTask, status: 'RUNNING' });
        if (selectedTask.chat_mode) {
          subscribeToTask(taskName);
        }
      }
      await loadTasks();
    } catch (error) {
      console.error('Failed to resume task:', error);
    }
  };

  const handleMergeToTest = async (taskName: string) => {
    if (!confirm('Merge this task branch to the default branch for testing?')) return;
    try {
      const result = await taskApi.mergeToTest(taskName);
      alert(`${result.message}\n\nSource: ${result.source_branch}\nTarget: ${result.target_branch}\nPushed: ${result.pushed ? 'Yes' : 'No'}`);
      await loadTasks();
    } catch (error: any) {
      console.error('Failed to merge to test:', error);
      const message = error?.response?.data?.detail || error?.message || 'Unknown error';
      alert(`Failed to merge: ${message}`);
    }
  };

  const handleDelete = async (taskName: string) => {
    if (!confirm('Delete this task?')) return;
    try {
      await taskApi.delete(taskName);
      // Refresh list first, then navigate back if needed
      await loadTasks();
      if (selectedTask?.task_name === taskName) {
        handleBack();
      }
    } catch (error: any) {
      console.error('Failed to delete task:', error);
      const message = error?.response?.data?.detail || error?.message || 'Unknown error';
      alert(`Failed to delete task: ${message}`);
    }
  };

  // Batch delete handlers
  const handleBatchDelete = async () => {
    if (selectedTaskNames.size === 0) return;
    if (!confirm(`Delete ${selectedTaskNames.size} selected task(s)?`)) return;

    setIsDeleting(true);
    try {
      const result = await taskApi.batchDelete(Array.from(selectedTaskNames));
      if (result.failed > 0) {
        const errors = result.results
          .filter(r => !r.success)
          .map(r => `${r.task_name}: ${r.error}`)
          .join('\n');
        alert(`Deleted ${result.successful} of ${result.total} tasks.\n\nFailed:\n${errors}`);
      }
      setSelectedTaskNames(new Set());
      await loadTasks();
    } catch (error: any) {
      console.error('Failed to batch delete:', error);
      const message = error?.response?.data?.detail || error?.message || 'Unknown error';
      alert(`Failed to delete tasks: ${message}`);
    } finally {
      setIsDeleting(false);
    }
  };

  const handleToggleSelectAll = () => {
    if (selectedTaskNames.size === tasks.length) {
      setSelectedTaskNames(new Set());
    } else {
      setSelectedTaskNames(new Set(tasks.map(t => t.task_name)));
    }
  };

  const handleToggleSelect = (taskName: string) => {
    const newSelected = new Set(selectedTaskNames);
    if (newSelected.has(taskName)) {
      newSelected.delete(taskName);
    } else {
      newSelected.add(taskName);
    }
    setSelectedTaskNames(newSelected);
  };

  const handlePageSizeChange = (newSize: number) => {
    setPageSize(newSize);
    setPage(0);
  };

  const handleClone = async (taskName: string) => {
    const newName = prompt(`Clone task "${taskName}" as:`, `${taskName}-copy`);
    if (!newName) return;

    // Ask if user wants to continue Claude's session context
    const continueSession = confirm(
      'Continue Claude\'s conversation context from the original task?\n\n' +
      '• Yes: New task will have Claude\'s memory/context from original task\n' +
      '• No: New task starts with fresh Claude session'
    );

    try {
      const clonedTask = await taskApi.clone(taskName, newName, continueSession);
      const sessionMsg = continueSession ? ' (with session context)' : '';
      alert(`Task cloned successfully as "${clonedTask.task_name}"${sessionMsg}`);
      await loadTasks();
    } catch (error: any) {
      console.error('Failed to clone task:', error);
      const message = error?.response?.data?.detail || error?.message || 'Unknown error';
      alert(`Failed to clone task: ${message}`);
    }
  };

  const handleViewDetail = async (task: Task) => {
    // Cleanup previous subscription
    if (unsubscribeRef.current) {
      unsubscribeRef.current();
      unsubscribeRef.current = null;
    }

    setSelectedTask(task);
    seenMessageIdsRef.current.clear();
    setDetailTab(task.chat_mode ? 'conversation' : 'info');

    // Always load conversation history
    setIsLoading(true);
    try {
      const history = await taskApi.getHistory(task.task_name);
      setMessages(history);
      history.forEach((m) => seenMessageIdsRef.current.add(m.id));

      // Subscribe if active
      if (['RUNNING', 'PAUSED', 'PENDING'].includes(task.status)) {
        subscribeToTask(task.task_name);
      }
    } catch (error) {
      console.error('Failed to load conversation:', error);
      setMessages([]);
    } finally {
      setIsLoading(false);
    }

    setViewMode('detail');
  };

  const handleBack = () => {
    if (unsubscribeRef.current) {
      unsubscribeRef.current();
      unsubscribeRef.current = null;
    }
    setSelectedTask(null);
    setMessages([]);
    seenMessageIdsRef.current.clear();
    setViewMode('list');
  };

  const handleSendMessage = async (text: string, images?: { base64: string; media_type: string }[]) => {
    if (!selectedTask) return;

    setIsSending(true);
    try {
      const messageParams = {
        task_name: selectedTask.task_name,
        input: text,
        images: images,
      };

      // Always send the message first
      await taskApi.sendMessage(messageParams);

      // If task is PENDING, try to start it (ignore error if already running)
      if (selectedTask.status === 'PENDING') {
        try {
          await taskApi.start(selectedTask.task_name);
        } catch (startError: any) {
          // Ignore 400 error (task already running)
          if (startError?.response?.status !== 400) {
            throw startError;
          }
        }
        setSelectedTask({ ...selectedTask, status: 'RUNNING' });
        subscribeToTask(selectedTask.task_name);
      }
    } catch (error) {
      console.error('Failed to send message:', error);
    } finally {
      setIsSending(false);
    }
  };

  const formatTime = (dateString: string): string => {
    const date = new Date(dateString);
    return date.toLocaleString();
  };

  const handleFilterChange = (newFilter: FilterStatus) => {
    setFilter(newFilter);
    setPage(0);
  };

  const handleModeFilterChange = (newMode: FilterMode) => {
    setModeFilter(newMode);
    setPage(0);
  };

  const handleSortChange = (newSort: SortBy) => {
    setSortBy(newSort);
    setPage(0);
  };

  const handleNewTask = () => {
    // Reset form state
    setTaskName('');
    setDescription('');
    setChatMode(false);
    setAutoStart(true);
    setSelectedProjectIds([]);
    setViewMode('new');
  };

  const handleProjectToggle = (projectId: string) => {
    setSelectedProjectIds(prev =>
      prev.includes(projectId)
        ? prev.filter(id => id !== projectId)
        : [...prev, projectId]
    );
  };

  // Load projects when entering new task form
  useEffect(() => {
    if (viewMode === 'new') {
      loadProjects();
    }
  }, [viewMode, loadProjects]);

  if (viewMode === 'new') {
    const selectedProjects = projects.filter(p => selectedProjectIds.includes(p.id));

    return (
      <div className="tasks-container">
        <div className="tasks-header">
          <button className="back-btn" onClick={() => setViewMode('list')}>← Back</button>
          <h2>Create New Task</h2>
        </div>
        <div className="new-task-form">
          <div className="form-group">
            <label>Projects (select one or more)</label>
            <div className="project-checkboxes">
              {projects.length === 0 ? (
                <div className="no-projects">No projects available. Create a project first.</div>
              ) : (
                projects.map((project) => (
                  <label key={project.id} className="project-checkbox-item">
                    <input
                      type="checkbox"
                      checked={selectedProjectIds.includes(project.id)}
                      onChange={() => handleProjectToggle(project.id)}
                    />
                    <span className="project-checkbox-label">
                      <span className="project-checkbox-name">{project.name}</span>
                      <span className="project-checkbox-path">{project.path}</span>
                    </span>
                  </label>
                ))
              )}
            </div>
            {selectedProjects.length > 0 && selectedProjects.some(p => p.config?.context) && (
              <div className="project-context-preview">
                <strong>Selected project contexts:</strong>
                {selectedProjects.filter(p => p.config?.context).map(p => (
                  <div key={p.id} className="context-item">
                    <span className="context-project-name">{p.name}:</span> {p.config?.context}
                  </div>
                ))}
              </div>
            )}
          </div>
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
          <div className="form-group">
            <label>Task Mode</label>
            <div className="mode-toggle">
              <button
                type="button"
                className={`mode-btn ${!chatMode ? 'active' : ''}`}
                onClick={() => setChatMode(false)}
              >
                Work Mode
              </button>
              <button
                type="button"
                className={`mode-btn ${chatMode ? 'active' : ''}`}
                onClick={() => setChatMode(true)}
              >
                Chat Mode
              </button>
            </div>
            <div className="mode-description">
              {chatMode
                ? 'Human in the loop - interactive conversation with the AI'
                : 'Autonomous - runs until iteration limit or finish condition'}
            </div>
          </div>
          {!chatMode && (
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
          )}
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
      <div className={`tasks-container ${detailTab === 'conversation' ? 'chat-view' : ''}`}>
        {/* Floating controls */}
        <div className="floating-controls top-left">
          <button className="floating-btn" onClick={handleBack} title="Back to list">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M19 12H5M12 19l-7-7 7-7"/>
            </svg>
          </button>
          <div className="floating-task-info">
            <span className={`status-dot ${selectedTask.status.toLowerCase()}`}></span>
            <span className="task-name-sm">{selectedTask.task_name}</span>
          </div>
        </div>
        <div className="floating-controls top-right">
          <button
            className={`floating-btn ${detailTab === 'info' ? 'active' : ''}`}
            onClick={() => setDetailTab('info')}
            title="Task Info"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/>
            </svg>
          </button>
          <button
            className={`floating-btn ${detailTab === 'conversation' ? 'active' : ''}`}
            onClick={() => setDetailTab('conversation')}
            title="Conversation"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/>
            </svg>
          </button>
        </div>

        {detailTab === 'info' ? (
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
                <dt>Mode</dt>
                <dd>{selectedTask.chat_mode ? 'Chat (Human in the loop)' : 'Work (Autonomous)'}</dd>
                {selectedTask.total_tokens_used != null && selectedTask.total_tokens_used > 0 && (
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
                {selectedTask.root_folder && (
                  <>
                    <dt>Project Path</dt>
                    <dd>{selectedTask.root_folder}</dd>
                  </>
                )}
                {selectedTask.worktree_path && (
                  <>
                    <dt>Worktree Path</dt>
                    <dd style={{ color: '#4caf50' }}>{selectedTask.worktree_path}</dd>
                  </>
                )}
              </dl>
            </div>
            <div className="detail-actions">
              {selectedTask.status === 'PENDING' && !selectedTask.chat_mode && (
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
                <button className="btn btn-primary" onClick={() => handleResume(selectedTask.task_name)}>
                  Resume
                </button>
              )}
              {selectedTask.status !== 'PENDING' && selectedTask.status !== 'RUNNING' && (
                <button className="btn btn-success" onClick={() => handleMergeToTest(selectedTask.task_name)}>
                  Test
                </button>
              )}
              <button className="btn btn-danger" onClick={() => handleDelete(selectedTask.task_name)}>
                Delete
              </button>
            </div>
          </div>
        ) : (
          <div className="chat-content">
            <MessageList
              messages={messages}
              isLoading={isLoading}
              status={selectedTask.status}
            />
            <ChatInput
              onSend={handleSendMessage}
              onStop={() => handleStop(selectedTask.task_name)}
              onResume={() => handleResume(selectedTask.task_name)}
              isSending={isSending}
              status={selectedTask.status}
              suggestedMessage={suggestedMessage}
              onSuggestedMessageUsed={() => setSuggestedMessage('')}
            />
          </div>
        )}
      </div>
    );
  }

  // Tabs view - multiple tasks in tabs
  if (viewMode === 'tabs' && openTabs.length > 0) {
    const activeTaskName = openTabs[activeTabIndex];
    const activeTabData = tabsData.get(activeTaskName);

    return (
      <div className="tasks-container tabs-view">
        {/* Floating task tabs on left */}
        <div className="floating-controls top-left">
          <button className="floating-btn" onClick={() => setViewMode('list')} title="Back to list">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M19 12H5M12 19l-7-7 7-7"/>
            </svg>
          </button>
          <div className="floating-tabs">
            {openTabs.map((tabTaskName, index) => {
              const tabData = tabsData.get(tabTaskName);
              return (
                <button
                  key={tabTaskName}
                  className={`floating-tab-btn ${index === activeTabIndex ? 'active' : ''}`}
                  onClick={() => setActiveTabIndex(index)}
                  title={tabTaskName}
                >
                  <span className={`status-dot ${tabData?.task.status.toLowerCase() || ''}`}></span>
                  <span className="floating-tab-name">{tabTaskName}</span>
                  <span
                    className="floating-tab-close"
                    onClick={(e) => {
                      e.stopPropagation();
                      closeTab(tabTaskName);
                    }}
                  >×</span>
                </button>
              );
            })}
            <button className="floating-btn" onClick={() => setViewMode('list')} title="Add tab">+</button>
          </div>
        </div>

        {/* Floating view toggle on right */}
        {activeTabData && (
          <div className="floating-controls top-right">
            <button
              className={`floating-btn ${activeTabData.detailTab === 'info' ? 'active' : ''}`}
              onClick={() => handleTabDetailTabChange(activeTaskName, 'info')}
              title="Task Info"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/>
              </svg>
            </button>
            <button
              className={`floating-btn ${activeTabData.detailTab === 'conversation' ? 'active' : ''}`}
              onClick={() => handleTabDetailTabChange(activeTaskName, 'conversation')}
              title="Conversation"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/>
              </svg>
            </button>
          </div>
        )}

        {/* Active tab content - full screen */}
        {activeTabData && (
          <div className={`tab-content-full ${activeTabData.detailTab === 'conversation' ? 'chat-view' : ''}`}>

            {activeTabData.detailTab === 'info' ? (
              <div className="task-detail">
                <div className="detail-section">
                  <h3>Status</h3>
                  <span className={`status-badge ${activeTabData.task.status.toLowerCase()}`}>
                    {activeTabData.task.status}
                  </span>
                </div>
                <div className="detail-section">
                  <h3>Description</h3>
                  <p>{activeTabData.task.description || 'No description'}</p>
                </div>
                {activeTabData.task.summary && (
                  <div className="detail-section">
                    <h3>Summary</h3>
                    <p>{activeTabData.task.summary}</p>
                  </div>
                )}
                {activeTabData.task.error_message && (
                  <div className="detail-section error">
                    <h3>Error</h3>
                    <p>{activeTabData.task.error_message}</p>
                  </div>
                )}
                <div className="detail-section">
                  <h3>Details</h3>
                  <dl>
                    <dt>Created</dt>
                    <dd>{formatTime(activeTabData.task.created_at)}</dd>
                    <dt>Updated</dt>
                    <dd>{formatTime(activeTabData.task.updated_at)}</dd>
                    <dt>Mode</dt>
                    <dd>{activeTabData.task.chat_mode ? 'Chat (Human in the loop)' : 'Work (Autonomous)'}</dd>
                    {activeTabData.task.branch_name && (
                      <>
                        <dt>Branch</dt>
                        <dd>{activeTabData.task.branch_name}</dd>
                      </>
                    )}
                    {activeTabData.task.worktree_path && (
                      <>
                        <dt>Worktree Path</dt>
                        <dd style={{ color: '#4caf50' }}>{activeTabData.task.worktree_path}</dd>
                      </>
                    )}
                  </dl>
                </div>
                <div className="detail-actions">
                  {activeTabData.task.status === 'RUNNING' && (
                    <button className="btn btn-warning" onClick={() => handleTabStop(activeTaskName)}>
                      Stop
                    </button>
                  )}
                  {activeTabData.task.status === 'STOPPED' && (
                    <button className="btn btn-primary" onClick={() => handleTabResume(activeTaskName)}>
                      Resume
                    </button>
                  )}
                </div>
              </div>
            ) : (
              <div className="chat-content">
                <MessageList
                  messages={activeTabData.messages}
                  isLoading={false}
                  status={activeTabData.task.status}
                />
                <ChatInput
                  onSend={(text, images) => handleTabSendMessage(activeTaskName, text, images)}
                  onStop={() => handleTabStop(activeTaskName)}
                  onResume={() => handleTabResume(activeTaskName)}
                  isSending={activeTabData.isSending}
                  status={activeTabData.task.status}
                  suggestedMessage={activeTabData.suggestedMessage}
                  onSuggestedMessageUsed={() => handleTabSuggestedMessageUsed(activeTaskName)}
                />
              </div>
            )}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="tasks-container">
      <div className="tasks-header">
        <h2>Tasks</h2>
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
            placeholder="Filter by user..."
            value={userId}
            onChange={(e) => { setUserId(e.target.value); setPage(0); }}
          />
          <select
            className="filter-select"
            value={modeFilter}
            onChange={(e) => handleModeFilterChange(e.target.value as FilterMode)}
          >
            <option value="all">All Modes</option>
            <option value="chat">Chat Mode</option>
            <option value="work">Work Mode</option>
          </select>
          <select
            className="filter-select"
            value={filter}
            onChange={(e) => handleFilterChange(e.target.value as FilterStatus)}
          >
            <option value="all">All Status</option>
            <option value="running">Running</option>
            <option value="pending">Pending</option>
            <option value="completed">Completed</option>
          </select>
          <select
            className="filter-select"
            value={sortBy}
            onChange={(e) => handleSortChange(e.target.value as SortBy)}
          >
            <option value="updated_at">Sort: Updated</option>
            <option value="created_at">Sort: Created</option>
            <option value="task_name">Sort: Name</option>
          </select>
          <button className="btn btn-primary" onClick={handleNewTask}>
            + New Task
          </button>
        </div>
      </div>

      {isLoading ? (
        <div className="loading-container">
          <div className="spinner" />
        </div>
      ) : tasks.length === 0 ? (
        <div className="empty-state">
          <div style={{ fontSize: 48, marginBottom: 16 }}>📋</div>
          <div style={{ fontSize: 16, fontWeight: 500, marginBottom: 8 }}>No tasks found</div>
          <div style={{ fontSize: 14 }}>Create a new task to get started</div>
        </div>
      ) : (
        <>
          {/* Selection action bar */}
          {selectedTaskNames.size > 0 && (
            <div className="selection-bar">
              <span>{selectedTaskNames.size} task(s) selected</span>
              <button
                className="btn btn-primary"
                onClick={() => {
                  // Open all selected tasks in tabs
                  const selectedTasks = tasks.filter(t => selectedTaskNames.has(t.task_name));
                  selectedTasks.forEach(t => openTaskInTab(t));
                  setSelectedTaskNames(new Set());
                }}
              >
                Open in Tabs
              </button>
              <button
                className="btn btn-danger"
                onClick={handleBatchDelete}
                disabled={isDeleting}
              >
                {isDeleting ? 'Deleting...' : 'Delete Selected'}
              </button>
              <button
                className="btn btn-secondary"
                onClick={() => setSelectedTaskNames(new Set())}
              >
                Clear Selection
              </button>
            </div>
          )}
          <div className="tasks-list">
            <table>
              <thead>
                <tr>
                  <th className="checkbox-cell">
                    <input
                      type="checkbox"
                      checked={selectedTaskNames.size === tasks.length && tasks.length > 0}
                      onChange={handleToggleSelectAll}
                    />
                  </th>
                  <th>Name</th>
                  <th>Mode</th>
                  <th>Status</th>
                  <th>Updated</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {tasks.map((task) => (
                  <tr key={task.id} className={selectedTaskNames.has(task.task_name) ? 'selected' : ''}>
                    <td className="checkbox-cell" onClick={(e) => e.stopPropagation()}>
                      <input
                        type="checkbox"
                        checked={selectedTaskNames.has(task.task_name)}
                        onChange={() => handleToggleSelect(task.task_name)}
                      />
                    </td>
                    <td className="task-name-cell" onClick={() => handleViewDetail(task)}>
                      <div className="task-name">{task.task_name}</div>
                      {task.description && (
                        <div className="task-desc">{task.description}</div>
                      )}
                    </td>
                    <td onClick={() => handleViewDetail(task)}>
                      <span className={`mode-badge ${task.chat_mode ? 'chat' : 'work'}`}>
                        {task.chat_mode ? 'Chat' : 'Work'}
                      </span>
                    </td>
                    <td onClick={() => handleViewDetail(task)}>
                      <span className={`status-badge ${task.status.toLowerCase()}`}>
                        {task.status}
                      </span>
                    </td>
                    <td onClick={() => handleViewDetail(task)}>{formatTime(task.updated_at)}</td>
                    <td className="actions-cell" onClick={(e) => e.stopPropagation()}>
                      {task.status === 'PENDING' && !task.chat_mode && (
                        <button className="action-btn start" onClick={() => handleStart(task.task_name)}>
                          Start
                        </button>
                      )}
                      {task.status === 'RUNNING' && (
                        <button className="action-btn stop" onClick={() => handleStop(task.task_name)}>
                          Stop
                        </button>
                      )}
                      {task.status === 'STOPPED' && (
                        <button className="action-btn start" onClick={() => handleResume(task.task_name)}>
                          Resume
                        </button>
                      )}
                      {task.status !== 'PENDING' && task.status !== 'RUNNING' && (
                        <button className="action-btn test" onClick={() => handleMergeToTest(task.task_name)}>
                          Test
                        </button>
                      )}
                      <button className="action-btn open-tab" onClick={() => openTaskInTab(task)}>
                        Tab
                      </button>
                      <button className="action-btn clone" onClick={() => handleClone(task.task_name)}>
                        Clone
                      </button>
                      <button className="action-btn delete" onClick={() => handleDelete(task.task_name)}>
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
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

export default Tasks;
