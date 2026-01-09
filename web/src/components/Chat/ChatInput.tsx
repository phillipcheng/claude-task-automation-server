import React, { useState, useCallback, useRef, useEffect } from 'react';

interface ChatInputProps {
  onSend: (text: string) => void;
  onStop: () => void;
  onResume: () => void;
  isSending: boolean;
  status: string;
}

const ChatInput: React.FC<ChatInputProps> = ({
  onSend,
  onStop,
  onResume,
  isSending,
  status,
}) => {
  const [input, setInput] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const isRunning = status === 'RUNNING';
  const isStopped = status === 'STOPPED';
  const isPaused = status === 'PAUSED';

  const handleSend = useCallback(() => {
    const text = input.trim();
    if (!text || isSending || isRunning) return;
    onSend(text);
    setInput('');
  }, [input, isSending, isRunning, onSend]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend]
  );

  // Auto-resize textarea
  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = 'auto';
      textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
    }
  }, [input]);

  return (
    <div className="chat-input">
      <textarea
        ref={textareaRef}
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={isRunning ? 'Waiting for response...' : 'Type a message...'}
        disabled={isRunning || isSending}
        rows={1}
      />
      <div className="chat-input-actions">
        {isRunning ? (
          <button className="stop-button" onClick={onStop}>
            Stop
          </button>
        ) : isStopped || isPaused ? (
          <button className="resume-button" onClick={onResume}>
            Resume
          </button>
        ) : (
          <button
            className="send-button"
            onClick={handleSend}
            disabled={!input.trim() || isSending}
          >
            {isSending ? 'Sending...' : 'Send'}
          </button>
        )}
      </div>
    </div>
  );
};

export default ChatInput;
