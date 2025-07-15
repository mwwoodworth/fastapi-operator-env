'use client';
import React, { useState, useRef } from 'react';
import { motion } from 'framer-motion';
import CopilotHeader from './CopilotHeader';
import CopilotResponse from './CopilotResponse';
import { postMemoryQuery, writeMemory } from '../utils/api';
import { promptClaude, promptChatGPT } from '../utils/ai';

interface Message { role: 'user' | 'ai'; content: string; }

export default function CopilotV2() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [model, setModel] = useState('claude');
  const [loading, setLoading] = useState(false);
  const [memPreview, setMemPreview] = useState('');
  const [showMem, setShowMem] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  async function send() {
    if (!input.trim() || model === 'disabled') return;
    const userText = input;
    setInput('');
    setMessages(m => [...m, { role: 'user', content: userText }]);
    setLoading(true);
    try {
      const mem = await postMemoryQuery(userText);
      const top = mem.results?.[0]?.content_chunk || '';
      setMemPreview(top);
      const prompt = `Context:\n${top}\n\nPrompt:\n${userText}`;
      const aiFunc = model === 'claude' ? promptClaude : promptChatGPT;
      const res = await aiFunc(prompt);
      const full = res.result || res.response || res.completion || '';
      setMessages(m => [...m, { role: 'ai', content: '' }]);
      let partial = '';
      for (const ch of full) {
        partial += ch;
        setMessages(m => {
          const copy = [...m];
          copy[copy.length - 1] = { role: 'ai', content: partial };
          return copy;
        });
        await new Promise(r => setTimeout(r, 20));
      }
      writeMemory({
        project_id: 'chat',
        title: userText.slice(0, 40),
        content: `${userText}\n${full}`,
        author_id: 'user',
      }).catch(() => {});
    } catch (e) {
      setMessages(m => [...m, { role: 'ai', content: 'Error' }]);
    } finally {
      setLoading(false);
      setTimeout(() => endRef.current?.scrollIntoView({ behavior: 'smooth' }), 50);
    }
  }

  return (
    <div className="flex flex-col h-full">
      <CopilotHeader model={model} onModelChange={setModel} />
      {memPreview && (
        <button
          onClick={() => setShowMem(!showMem)}
          className="self-end text-xs underline mb-1"
        >
          {showMem ? 'Hide memory' : 'Show memory'}
        </button>
      )}
      {showMem && memPreview && (
        <div className="border rounded p-2 text-xs whitespace-pre-wrap mb-2 bg-muted">
          {memPreview}
        </div>
      )}
      <div className="flex-1 overflow-auto p-2 space-y-2">
        {messages.length === 0 && !loading && (
          <p className="text-sm opacity-60">Ask me anything to begin...</p>
        )}
        {messages.map((m, idx) => (
          <CopilotResponse key={idx} role={m.role} text={m.content} />
        ))}
        {loading && <p className="text-sm opacity-60">Loading...</p>}
        <div ref={endRef} />
      </div>
      <motion.form
        initial={{ y: 50, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        onSubmit={e => {
          e.preventDefault();
          send();
        }}
        className="p-2 border-t flex gap-2"
      >
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          placeholder="Ask the copilot..."
          className="flex-1 border px-3 py-2 rounded"
        />
        <button
          type="submit"
          disabled={loading}
          className="bg-primary text-primary-foreground px-4 py-2 rounded"
        >
          Send
        </button>
      </motion.form>
    </div>
  );
}
