'use client';

import { useState, useRef, useEffect } from 'react';
import { Send, Mic, MicOff, Paperclip, X } from 'lucide-react';
import { useOfflineSync } from '@/hooks/useOfflineSync';
import { motion, AnimatePresence } from 'framer-motion';
import { voiceRecorder } from '@/lib/voice-recorder';

interface Message {
  id: string;
  content: string;
  role: 'user' | 'assistant';
  timestamp: number;
  synced?: boolean;
}

export default function OfflineChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isRecording, setIsRecording] = useState(false);
  const [attachedFile, setAttachedFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const {
    isOnline,
    saveMessage,
    saveFile,
    startVoiceRecording,
    stopVoiceRecording,
    getSessionMessages,
  } = useOfflineSync({
    sessionId: 'main-chat',
    autoSync: true,
  });

  // Load existing messages on mount
  useEffect(() => {
    loadMessages();
  }, []);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Listen for recording status
  useEffect(() => {
    voiceRecorder.onRecordingChange(setIsRecording);
  }, []);

  const loadMessages = async () => {
    const storedMessages = await getSessionMessages();
    setMessages(storedMessages.sort((a, b) => a.timestamp - b.timestamp));
  };

  const handleSend = async () => {
    if (!input.trim() && !attachedFile) return;

    // Save user message
    const userMessage: Message = {
      id: `msg-${Date.now()}`,
      content: input,
      role: 'user',
      timestamp: Date.now(),
      synced: isOnline,
    };

    setMessages(prev => [...prev, userMessage]);
    await saveMessage(input, 'user');

    // Handle file attachment
    if (attachedFile) {
      await saveFile(attachedFile);
      userMessage.content += ` [Attached: ${attachedFile.name}]`;
      setAttachedFile(null);
    }

    setInput('');

    // Simulate AI response (in real app, this would be from API)
    if (isOnline) {
      // Online: would call API
      setTimeout(async () => {
        const aiResponse: Message = {
          id: `msg-${Date.now()}-ai`,
          content: 'This is a simulated response. In production, this would come from the AI backend.',
          role: 'assistant',
          timestamp: Date.now(),
          synced: true,
        };
        setMessages(prev => [...prev, aiResponse]);
        await saveMessage(aiResponse.content, 'assistant');
      }, 1000);
    } else {
      // Offline: show queued message
      const offlineResponse: Message = {
        id: `msg-${Date.now()}-offline`,
        content: '📴 Your message has been saved and will be processed when you\'re back online.',
        role: 'assistant',
        timestamp: Date.now(),
        synced: false,
      };
      setMessages(prev => [...prev, offlineResponse]);
    }
  };

  const handleVoiceToggle = async () => {
    if (isRecording) {
      const memoId = await stopVoiceRecording();
      if (memoId) {
        const voiceMessage: Message = {
          id: `msg-${Date.now()}-voice`,
          content: '🎤 Voice memo recorded',
          role: 'user',
          timestamp: Date.now(),
          synced: isOnline,
        };
        setMessages(prev => [...prev, voiceMessage]);
      }
    } else {
      await startVoiceRecording();
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setAttachedFile(file);
    }
  };

  return (
    <div className="flex flex-col h-screen bg-gray-900">
      {/* Messages area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        <AnimatePresence>
          {messages.map((message) => (
            <motion.div
              key={message.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`
                  max-w-[70%] px-4 py-2 rounded-lg
                  ${message.role === 'user' 
                    ? 'bg-blue-600 text-white' 
                    : 'bg-gray-800 text-gray-200'}
                  ${!message.synced ? 'opacity-70' : ''}
                `}
              >
                <p className="whitespace-pre-wrap">{message.content}</p>
                {!message.synced && (
                  <p className="text-xs mt-1 opacity-70">
                    {isOnline ? 'Syncing...' : 'Queued'}
                  </p>
                )}
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
        <div ref={messagesEndRef} />
      </div>

      {/* File attachment indicator */}
      {attachedFile && (
        <div className="mx-4 mb-2 p-2 bg-gray-800 rounded-lg flex items-center justify-between">
          <span className="text-sm text-gray-300">
            📎 {attachedFile.name}
          </span>
          <button
            onClick={() => setAttachedFile(null)}
            className="text-gray-400 hover:text-white"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Input area */}
      <div className="border-t border-gray-800 p-4">
        <div className="flex items-center gap-2">
          {/* File attachment */}
          <input
            ref={fileInputRef}
            type="file"
            onChange={handleFileSelect}
            className="hidden"
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            className="p-2 text-gray-400 hover:text-white transition-colors"
            title="Attach file"
          >
            <Paperclip className="w-5 h-5" />
          </button>

          {/* Voice recording */}
          <button
            onClick={handleVoiceToggle}
            className={`p-2 transition-colors ${
              isRecording 
                ? 'text-red-500 hover:text-red-400' 
                : 'text-gray-400 hover:text-white'
            }`}
            title={isRecording ? 'Stop recording' : 'Start recording'}
          >
            {isRecording ? (
              <MicOff className="w-5 h-5" />
            ) : (
              <Mic className="w-5 h-5" />
            )}
          </button>

          {/* Text input */}
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleSend()}
            placeholder={isOnline ? "Type a message..." : "Type a message (offline mode)..."}
            className="flex-1 bg-gray-800 text-white px-4 py-2 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          />

          {/* Send button */}
          <button
            onClick={handleSend}
            disabled={!input.trim() && !attachedFile}
            className="p-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <Send className="w-5 h-5" />
          </button>
        </div>

        {/* Offline indicator */}
        {!isOnline && (
          <p className="text-xs text-yellow-400 mt-2">
            📴 Offline mode - Messages will be sent when connection is restored
          </p>
        )}
      </div>
    </div>
  );
}