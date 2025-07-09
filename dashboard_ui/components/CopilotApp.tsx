'use client';
import { useState, useRef } from 'react';
import CopilotMessage, { CopilotMsg } from './CopilotMessage';
import { streamResponse } from '../utils/streaming';

export default function CopilotApp() {
  const [messages, setMessages] = useState<CopilotMsg[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  async function send() {
    if (!input.trim()) return;
    const prompt = input;
    setInput('');
    setMessages(m => [...m, { role: 'user', content: prompt }, { role: 'ai', content: '' }]);
    setLoading(true);
    await streamResponse('/api/claude', { prompt }, token => {
      setMessages(m => {
        const copy = [...m];
        copy[copy.length - 1] = { role: 'ai', content: copy[copy.length - 1].content + token };
        return copy;
      });
    });
    setLoading(false);
    setTimeout(() => endRef.current?.scrollIntoView({ behavior: 'smooth' }), 50);
  }

  return (
    <div className="flex flex-col flex-1">
      <div className="flex-1 overflow-auto p-2 space-y-2">
        {messages.map((m, idx) => (
          <CopilotMessage key={idx} message={m} />
        ))}
        {loading && <p className="text-sm opacity-60">Loading...</p>}
        <div ref={endRef} />
      </div>
      <form
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
      </form>
    </div>
  );
}
