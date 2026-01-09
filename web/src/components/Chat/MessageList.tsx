import React, { useRef, useEffect } from 'react';
import type { ChatMessage } from '../../types';

interface MessageListProps {
  messages: ChatMessage[];
  isLoading: boolean;
  status: string;
}

const formatTimestamp = (timestamp: string): string => {
  if (!timestamp) return '';
  const date = new Date(timestamp);
  if (isNaN(date.getTime())) return '';
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
};

const getMessageTypeLabel = (type: string): string => {
  switch (type) {
    case 'user_request':
      return 'You';
    case 'claude_response':
      return 'Assistant';
    case 'simulated_human':
      return 'System';
    case 'tool_result':
    case 'tool_group':
      return 'Tool Output';
    default:
      return 'Assistant';
  }
};

const shouldDisplayMessage = (message: ChatMessage): boolean => {
  if (message.type === 'simulated_human') return false;
  if (!message.content || message.content.trim() === '') return false;
  if (message.type === 'tool_group') return false;
  return true;
};

const MessageList: React.FC<MessageListProps> = ({ messages, isLoading, status }) => {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [messages]);

  if (messages.length === 0 && !isLoading) {
    return (
      <div className="message-list" ref={containerRef}>
        <div className="message-list-empty">
          <div style={{ fontSize: 48, marginBottom: 16 }}>🤖</div>
          <div style={{ fontSize: 16, fontWeight: 500, marginBottom: 8 }}>
            Start a conversation
          </div>
          <div style={{ fontSize: 14 }}>
            Type a message below to start chatting
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="message-list" ref={containerRef}>
      {messages.filter(shouldDisplayMessage).map((message) => {
        const isUser = message.type === 'user_request';
        const isToolResult = message.type === 'tool_result';
        const timestamp = formatTimestamp(message.timestamp);

        return (
          <div key={message.id} className={`message-wrapper ${isUser ? 'user' : ''}`}>
            <div className={`message-avatar ${isUser ? 'user' : 'assistant'}`}>
              {isUser ? '👤' : '🤖'}
            </div>
            <div className="message-content">
              <div className={`message-bubble ${isToolResult ? 'tool-result' : ''}`}>
                {message.content}
              </div>
              <div className="message-meta">
                {getMessageTypeLabel(message.type)}
                {timestamp && ` · ${timestamp}`}
                {message.output_tokens && ` · ${message.output_tokens} tokens`}
              </div>
            </div>
          </div>
        );
      })}

      {status === 'RUNNING' && (
        <div className="typing-indicator">
          <div className="spinner" />
          <span>Thinking...</span>
        </div>
      )}
    </div>
  );
};

export default MessageList;
