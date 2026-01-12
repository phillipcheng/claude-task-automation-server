import React, { useState, useCallback, useRef, useEffect } from 'react';

interface ImageData {
  base64: string;
  media_type: string;
  preview: string;
}

interface ChatInputProps {
  onSend: (text: string, images?: { base64: string; media_type: string }[]) => void;
  onStop: () => void;
  onResume: () => void;
  onRecover?: () => void;
  isSending: boolean;
  status: string;
  errorMessage?: string;
  suggestedMessage?: string;  // Pre-fill input with this message
  onSuggestedMessageUsed?: () => void;  // Called when suggested message is consumed
}

const ChatInput: React.FC<ChatInputProps> = ({
  onSend,
  onStop,
  onResume,
  onRecover,
  isSending,
  status,
  errorMessage,
  suggestedMessage,
  onSuggestedMessageUsed,
}) => {
  const [input, setInput] = useState('');
  const [images, setImages] = useState<ImageData[]>([]);
  const [isRecording, setIsRecording] = useState(false);
  const [isDragOver, setIsDragOver] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const recognitionRef = useRef<any>(null);

  const isRunning = status === 'RUNNING';
  const isStopped = status === 'STOPPED';
  const isPaused = status === 'PAUSED';
  const isFailed = status === 'FAILED' || status === 'EXHAUSTED';

  // Handle suggested message - pre-fill input when provided
  useEffect(() => {
    if (suggestedMessage && suggestedMessage.trim()) {
      setInput(suggestedMessage);
      onSuggestedMessageUsed?.();
      // Focus the textarea
      setTimeout(() => {
        textareaRef.current?.focus();
        textareaRef.current?.select();
      }, 100);
    }
  }, [suggestedMessage, onSuggestedMessageUsed]);

  // Initialize speech recognition
  useEffect(() => {
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (SpeechRecognition) {
      recognitionRef.current = new SpeechRecognition();
      recognitionRef.current.continuous = true;
      recognitionRef.current.interimResults = true;
      recognitionRef.current.lang = 'en-US';

      recognitionRef.current.onresult = (event: any) => {
        let finalTranscript = '';
        let interimTranscript = '';

        for (let i = event.resultIndex; i < event.results.length; i++) {
          const transcript = event.results[i][0].transcript;
          if (event.results[i].isFinal) {
            finalTranscript += transcript;
          } else {
            interimTranscript += transcript;
          }
        }

        if (finalTranscript) {
          setInput(prev => prev + finalTranscript + ' ');
        }
      };

      recognitionRef.current.onerror = (event: any) => {
        console.error('Speech recognition error:', event.error);
        setIsRecording(false);
      };

      recognitionRef.current.onend = () => {
        setIsRecording(false);
      };
    }

    return () => {
      if (recognitionRef.current) {
        recognitionRef.current.stop();
      }
    };
  }, []);

  const handleSend = useCallback(() => {
    const text = input.trim();
    if ((!text && images.length === 0) || isSending) return;

    const imageData = images.length > 0
      ? images.map(img => ({ base64: img.base64, media_type: img.media_type }))
      : undefined;

    onSend(text, imageData);
    setInput('');
    setImages([]);
  }, [input, images, isSending, onSend]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend]
  );

  // Process image file to base64
  const processImage = useCallback((file: File): Promise<ImageData> => {
    return new Promise((resolve, reject) => {
      if (!file.type.startsWith('image/')) {
        reject(new Error('Not an image file'));
        return;
      }

      const reader = new FileReader();
      reader.onload = (e) => {
        const result = e.target?.result as string;
        // Extract base64 data (remove data:image/xxx;base64, prefix)
        const base64 = result.split(',')[1];
        resolve({
          base64,
          media_type: file.type,
          preview: result, // Full data URL for preview
        });
      };
      reader.onerror = () => reject(new Error('Failed to read file'));
      reader.readAsDataURL(file);
    });
  }, []);

  // Handle file drop
  const handleDrop = useCallback(async (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);

    const files = Array.from(e.dataTransfer.files);
    const imageFiles = files.filter(f => f.type.startsWith('image/'));

    try {
      const newImages = await Promise.all(imageFiles.map(processImage));
      setImages(prev => [...prev, ...newImages].slice(0, 5)); // Max 5 images
    } catch (error) {
      console.error('Error processing images:', error);
    }
  }, [processImage]);

  // Handle paste
  const handlePaste = useCallback(async (e: React.ClipboardEvent) => {
    const items = Array.from(e.clipboardData.items);
    const imageItems = items.filter(item => item.type.startsWith('image/'));

    if (imageItems.length > 0) {
      e.preventDefault();
      try {
        const newImages = await Promise.all(
          imageItems.map(item => {
            const file = item.getAsFile();
            if (file) return processImage(file);
            return Promise.reject(new Error('No file'));
          })
        );
        setImages(prev => [...prev, ...newImages].slice(0, 5));
      } catch (error) {
        console.error('Error processing pasted images:', error);
      }
    }
  }, [processImage]);

  // Handle file input change
  const handleFileChange = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    try {
      const newImages = await Promise.all(files.map(processImage));
      setImages(prev => [...prev, ...newImages].slice(0, 5));
    } catch (error) {
      console.error('Error processing images:', error);
    }
    // Reset input so same file can be selected again
    e.target.value = '';
  }, [processImage]);

  // Remove image
  const removeImage = useCallback((index: number) => {
    setImages(prev => prev.filter((_, i) => i !== index));
  }, []);

  // Toggle voice recording
  const toggleRecording = useCallback(() => {
    if (!recognitionRef.current) {
      alert('Speech recognition is not supported in this browser.');
      return;
    }

    if (isRecording) {
      recognitionRef.current.stop();
      setIsRecording(false);
    } else {
      recognitionRef.current.start();
      setIsRecording(true);
    }
  }, [isRecording]);

  // Auto-resize textarea
  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = 'auto';
      textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
    }
  }, [input]);

  return (
    <div className="chat-input-container">
      {/* Error banner for failed tasks */}
      {isFailed && (
        <div className="error-banner">
          <div className="error-content">
            <span className="error-icon">!</span>
            <div className="error-text">
              <strong>Task Failed</strong>
              {errorMessage && <p>{errorMessage.length > 150 ? errorMessage.slice(0, 150) + '...' : errorMessage}</p>}
            </div>
          </div>
          {onRecover && (
            <button className="recover-button" onClick={onRecover}>
              Recover
            </button>
          )}
        </div>
      )}

      {/* Image previews */}
      {images.length > 0 && (
        <div className="image-previews">
          {images.map((img, index) => (
            <div key={index} className="image-preview">
              <img src={img.preview} alt={`Attachment ${index + 1}`} />
              <button
                className="remove-image"
                onClick={() => removeImage(index)}
                title="Remove image"
              >
                x
              </button>
            </div>
          ))}
        </div>
      )}

      <div
        className={`chat-input ${isDragOver ? 'drag-over' : ''}`}
        onDragOver={(e) => { e.preventDefault(); setIsDragOver(true); }}
        onDragLeave={() => setIsDragOver(false)}
        onDrop={handleDrop}
      >
        <div className="input-tools">
          {/* Image upload button */}
          <button
            className="tool-btn"
            onClick={() => fileInputRef.current?.click()}
            title="Attach image"
            disabled={isSending}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
              <circle cx="8.5" cy="8.5" r="1.5"/>
              <polyline points="21,15 16,10 5,21"/>
            </svg>
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            multiple
            onChange={handleFileChange}
            style={{ display: 'none' }}
          />

          {/* Voice input button */}
          <button
            className={`tool-btn ${isRecording ? 'recording' : ''}`}
            onClick={toggleRecording}
            title={isRecording ? 'Stop recording' : 'Voice input'}
            disabled={isSending}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
              <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
              <line x1="12" y1="19" x2="12" y2="23"/>
              <line x1="8" y1="23" x2="16" y2="23"/>
            </svg>
          </button>
        </div>

        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          onPaste={handlePaste}
          placeholder={isDragOver ? 'Drop images here...' : isRunning ? 'Waiting for response...' : 'Type a message or drop images...'}
          disabled={isSending}
          rows={1}
        />

        <div className="chat-input-actions">
          {isRunning ? (
            <button className="stop-button" onClick={onStop}>
              Stop
            </button>
          ) : isStopped || isPaused ? (
            <>
              <button
                className="send-button"
                onClick={handleSend}
                disabled={(!input.trim() && images.length === 0) || isSending}
              >
                {isSending ? 'Sending...' : 'Send'}
              </button>
              <button className="resume-button" onClick={onResume}>
                Resume
              </button>
            </>
          ) : (
            <button
              className="send-button"
              onClick={handleSend}
              disabled={(!input.trim() && images.length === 0) || isSending}
            >
              {isSending ? 'Sending...' : 'Send'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default ChatInput;
