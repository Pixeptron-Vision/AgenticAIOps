// components/chat/ChatInput.tsx
import { useState, useRef } from 'react';
import { Send, Mic, Paperclip, Sparkles } from 'lucide-react';
import { motion } from 'framer-motion';
import { SmartSuggestions } from './SmartSuggestions';

export function ChatInput({ onSend, onFileUpload, isLoading }: { onSend: (text: string) => void; onFileUpload: (file: File) => Promise<void> | void; isLoading?: boolean }) {
  const [message, setMessage] = useState('');
  const [isRecording, setIsRecording] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (message.trim() && !isLoading) {
      onSend(message);
      setMessage('');
      textareaRef.current?.focus();
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e as any);
    }
  };

  return (
    <div className="border-t border-gray-200 bg-white p-4">
      {/* Smart Suggestions (when empty) */}
      {message.length === 0 && (
        <div className="mb-3">
          <SmartSuggestions onSelect={setMessage} />
        </div>
      )}

      {/* Input Form */}
      <form onSubmit={handleSubmit} className="relative">
        <div className="flex items-end gap-2">
          {/* File Upload Button */}
          <button
            type="button"
            onClick={() => document.getElementById('file-upload')?.click()}
            className="p-2 text-gray-400 hover:text-gray-600 transition-colors"
          >
            <Paperclip className="w-5 h-5" />
          </button>
          <input
            id="file-upload"
            type="file"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) onFileUpload(f);
            }}
          />

          {/* Text Input */}
          <div className="flex-1 relative">
            <textarea
              ref={textareaRef}
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Type your message... (Shift+Enter for new line)"
              disabled={isLoading}
              rows={1}
              className="w-full px-4 py-3 pr-12 border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none disabled:bg-gray-50 disabled:text-gray-400"
              style={{
                minHeight: '48px',
                maxHeight: '200px',
              }}
            />

            {/* Character count & AI hint */}
            {message.length > 0 && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="absolute bottom-2 left-4 text-xs text-gray-400"
              >
                {message.length} chars
              </motion.div>
            )}
          </div>

          {/* Voice Input Button */}
          <button
            type="button"
            onClick={() => setIsRecording(!isRecording)}
            className={`p-2 transition-colors ${
              isRecording
                ? 'text-red-500 animate-pulse'
                : 'text-gray-400 hover:text-gray-600'
            }`}
          >
            <Mic className="w-5 h-5" />
          </button>

          {/* Send Button */}
          <button
            type="submit"
            disabled={!message.trim() || isLoading}
            className="p-3 bg-gradient-to-r from-blue-500 to-blue-600 text-white rounded-xl hover:from-blue-600 hover:to-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-lg hover:shadow-xl"
          >
            {isLoading ? (
              <motion.div
                animate={{ rotate: 360 }}
                transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
              >
                <Sparkles className="w-5 h-5" />
              </motion.div>
            ) : (
              <Send className="w-5 h-5" />
            )}
          </button>
        </div>
      </form>
    </div>
  );
}