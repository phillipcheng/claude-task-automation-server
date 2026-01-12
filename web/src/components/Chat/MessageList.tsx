import React, { useRef, useEffect, useState } from 'react';
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
    case 'system_message':
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
  // For regular messages, filter empty content
  if (message.type !== 'tool_group' && (!message.content || message.content.trim() === '')) return false;
  // Tool groups are now displayed
  return true;
};

// Collapsible Tool Group Component
const ToolGroupMessage: React.FC<{ message: ChatMessage }> = ({ message }) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const toolCount = message.tool_count || message.tools?.length || 0;

  return (
    <div className="tool-group-container">
      <div
        className="tool-group-header"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <span className="tool-group-icon">{isExpanded ? '▼' : '▶'}</span>
        <span className="tool-group-summary">
          Tool Execution ({toolCount} {toolCount === 1 ? 'tool' : 'tools'})
        </span>
      </div>
      {isExpanded && message.tools && (
        <div className="tool-group-content">
          {message.tools.map((tool, index) => (
            <div key={tool.id || index} className="tool-output-item">
              <pre className="tool-output-content">{tool.content}</pre>
            </div>
          ))}
        </div>
      )}
    </div>
  );
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
          <div style={{ fontSize: 14, color: '#9ca3af' }}>
            Type a message to start
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="message-list" ref={containerRef}>
      {messages.filter(shouldDisplayMessage).map((message) => {
        const isUser = message.type === 'user_request';
        const isSystem = message.type === 'system_message';
        const isToolResult = message.type === 'tool_result';
        const isToolGroup = message.type === 'tool_group';
        const timestamp = formatTimestamp(message.timestamp || message.first_timestamp || '');

        // Handle tool group messages with special rendering
        if (isToolGroup) {
          return (
            <div key={message.id} className="message-wrapper tool-group">
              <div className="message-avatar tool">T</div>
              <div className="message-content">
                <ToolGroupMessage message={message} />
                <div className="message-meta">
                  Tool Output · {timestamp}
                </div>
              </div>
            </div>
          );
        }

        const avatarClass = isUser ? 'user' : isSystem ? 'system' : 'assistant';
        const avatarText = isUser ? 'U' : isSystem ? 'S' : 'A';

        return (
          <div key={message.id} className={`message-wrapper ${isUser ? 'user' : ''} ${isSystem ? 'system' : ''}`}>
            <div className={`message-avatar ${avatarClass}`}>
              {avatarText}
            </div>
            <div className="message-content">
              {/* Display attached images */}
              {message.images && message.images.length > 0 && (
                <div className="message-images">
                  {message.images.map((img, index) => (
                    <img
                      key={index}
                      src={`data:${img.media_type};base64,${img.base64}`}
                      alt={`Attachment ${index + 1}`}
                      className="message-image"
                    />
                  ))}
                </div>
              )}
              <div className={`message-bubble ${isToolResult ? 'tool-result' : ''} ${isSystem ? 'system' : ''}`}>
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
