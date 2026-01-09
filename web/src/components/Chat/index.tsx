import React, { useState, useEffect, useCallback, useRef } from 'react';
import { taskApi } from '../../services/api';
import type { Task, ChatMessage } from '../../types';
import TaskList from './TaskList';
import NewTask from './NewTask';
import MessageList from './MessageList';
import ChatInput from './ChatInput';
import './Chat.css';

type ViewMode = 'list' | 'new' | 'chat';

const Chat: React.FC = () => {
  const [viewMode, setViewMode] = useState<ViewMode>('list');
  const [tasks, setTasks] = useState<Task[]>([]);
  const [currentTask, setCurrentTask] = useState<Task | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const unsubscribeRef = useRef<(() => void) | null>(null);
  const seenMessageIdsRef = useRef<Set<string>>(new Set());

  // Load tasks on mount
  useEffect(() => {
    loadTasks();
  }, []);

  // Cleanup subscription on unmount
  useEffect(() => {
    return () => {
      if (unsubscribeRef.current) {
        unsubscribeRef.current();
      }
    };
  }, []);

  const loadTasks = async () => {
    setIsLoading(true);
    try {
      const data = await taskApi.list();
      // Filter to only show chat_mode tasks
      const chatTasks = data.filter((t) => t.chat_mode);
      setTasks(chatTasks);
    } catch (error) {
      console.error('Failed to load tasks:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleCreateTask = async (taskName: string, description: string) => {
    setIsLoading(true);
    try {
      const task = await taskApi.create({
        task_name: taskName,
        description: description || taskName,
        user_id: 'web-user',
        auto_start: false,
        max_iterations: 50,
        chat_mode: true,
        project_context: description,
      });

      setCurrentTask(task);
      setMessages([]);
      seenMessageIdsRef.current.clear();

      // Subscribe to updates
      subscribeToTask(task.task_name);

      // If description provided, send it as first message and start
      if (description) {
        await taskApi.sendMessage({ task_name: taskName, input: description });
        await taskApi.start(taskName);
        setCurrentTask({ ...task, status: 'RUNNING' });
      }

      setViewMode('chat');
      await loadTasks();
    } catch (error) {
      console.error('Failed to create task:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSelectTask = async (task: Task) => {
    setIsLoading(true);
    seenMessageIdsRef.current.clear();

    // Cleanup previous subscription
    if (unsubscribeRef.current) {
      unsubscribeRef.current();
      unsubscribeRef.current = null;
    }

    try {
      setCurrentTask(task);
      const history = await taskApi.getHistory(task.task_name);
      setMessages(history);
      history.forEach((m) => seenMessageIdsRef.current.add(m.id));

      // Subscribe if active
      if (['RUNNING', 'PAUSED', 'PENDING'].includes(task.status)) {
        subscribeToTask(task.task_name);
      }

      setViewMode('chat');
    } catch (error) {
      console.error('Failed to load task:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const subscribeToTask = useCallback((taskName: string) => {
    if (unsubscribeRef.current) {
      unsubscribeRef.current();
    }

    unsubscribeRef.current = taskApi.subscribeToStream(
      taskName,
      (message) => {
        if (!seenMessageIdsRef.current.has(message.id)) {
          seenMessageIdsRef.current.add(message.id);
          setMessages((prev) => [...prev, message]);
        }
      },
      () => {
        // Status updates handled via polling
      },
      (error) => {
        console.error('SSE error:', error);
      }
    );
  }, []);

  const handleSendMessage = async (text: string) => {
    if (!currentTask) return;

    setIsSending(true);
    try {
      if (currentTask.status === 'PENDING') {
        await taskApi.sendMessage({ task_name: currentTask.task_name, input: text });
        await taskApi.start(currentTask.task_name);
        setCurrentTask({ ...currentTask, status: 'RUNNING' });
        subscribeToTask(currentTask.task_name);
      } else {
        await taskApi.sendMessage({ task_name: currentTask.task_name, input: text });
      }
    } catch (error) {
      console.error('Failed to send message:', error);
    } finally {
      setIsSending(false);
    }
  };

  const handleStop = async () => {
    if (!currentTask) return;
    try {
      await taskApi.stop(currentTask.task_name);
      setCurrentTask({ ...currentTask, status: 'STOPPED' });
    } catch (error) {
      console.error('Failed to stop task:', error);
    }
  };

  const handleResume = async () => {
    if (!currentTask) return;
    try {
      await taskApi.resume(currentTask.task_name);
      setCurrentTask({ ...currentTask, status: 'RUNNING' });
      subscribeToTask(currentTask.task_name);
    } catch (error) {
      console.error('Failed to resume task:', error);
    }
  };

  const handleDelete = async (taskName: string) => {
    try {
      await taskApi.delete(taskName);
      if (currentTask?.task_name === taskName) {
        setCurrentTask(null);
        setMessages([]);
        if (unsubscribeRef.current) {
          unsubscribeRef.current();
          unsubscribeRef.current = null;
        }
      }
      await loadTasks();
    } catch (error) {
      console.error('Failed to delete task:', error);
    }
  };

  const handleBack = () => {
    if (unsubscribeRef.current) {
      unsubscribeRef.current();
      unsubscribeRef.current = null;
    }
    setCurrentTask(null);
    setMessages([]);
    seenMessageIdsRef.current.clear();
    setViewMode('list');
  };

  return (
    <div className="chat-container">
      <div className="chat-header">
        {viewMode !== 'list' && (
          <button className="back-button" onClick={handleBack}>
            ← Back
          </button>
        )}
        <h2 className="chat-title">
          {viewMode === 'new' ? 'New Chat' : viewMode === 'chat' ? currentTask?.task_name : 'Chats'}
        </h2>
        {viewMode === 'list' && (
          <button className="new-button" onClick={() => setViewMode('new')}>
            + New
          </button>
        )}
      </div>

      <div className="chat-content">
        {viewMode === 'list' && (
          <TaskList
            tasks={tasks}
            isLoading={isLoading}
            onSelect={handleSelectTask}
            onDelete={handleDelete}
          />
        )}

        {viewMode === 'new' && (
          <NewTask
            isLoading={isLoading}
            onCreate={handleCreateTask}
            onCancel={() => setViewMode('list')}
          />
        )}

        {viewMode === 'chat' && currentTask && (
          <>
            <MessageList
              messages={messages}
              isLoading={isLoading}
              status={currentTask.status}
            />
            <ChatInput
              onSend={handleSendMessage}
              onStop={handleStop}
              onResume={handleResume}
              isSending={isSending}
              status={currentTask.status}
            />
          </>
        )}
      </div>
    </div>
  );
};

export default Chat;
