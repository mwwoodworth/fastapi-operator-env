'use client';
import React, { useState } from 'react';
import { postMemoryQuery } from '../utils/api';
import MemoryResultCard from './MemoryResultCard';

export default function CopilotChat() {
  const [prompt, setPrompt] = useState('');
  const [result, setResult] = useState(null as any);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e?: any) {
    e?.preventDefault();
    if (!prompt) return;
    setLoading(true);
    try {
      const data = await postMemoryQuery(prompt);
      const top = data.results?.[0];
      if (top) setResult(top);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-auto p-2 space-y-2">
        {result && <MemoryResultCard result={result} />}
      </div>
      <form onSubmit={handleSubmit} className="mt-auto flex gap-2 p-2 border-t">
        <input
          value={prompt}
        onChange={(e: any) => setPrompt(e.target.value)}
          placeholder="Ask the copilot..."
          className="flex-1 border px-3 py-2 rounded"
        />
        <button type="submit" className="bg-primary text-primary-foreground px-4 py-2 rounded">
          Send
        </button>
      </form>
      {loading && <p className="p-2">Loading...</p>}
    </div>
  );
}

interface MemoryResult {
  title?: string;
  content_chunk: string;
}
