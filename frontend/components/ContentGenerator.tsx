'use client';
import React, { useState } from 'react';

export default function ContentGenerator() {
  const [prompt, setPrompt] = useState('');
  const [output, setOutput] = useState('');
  const [loading, setLoading] = useState(false);

  async function generate() {
    if (!prompt.trim()) return;
    setLoading(true);
    try {
      const res = await fetch('/api/assistant/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: prompt }),
      });
      const data = await res.json();
      setOutput(data.response || data.result || '');
    } catch (e) {
      setOutput('Error generating');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-2">
      <textarea
        className="w-full border p-2 rounded"
        rows={4}
        value={prompt}
        onChange={e => setPrompt(e.target.value)}
        placeholder="Enter content prompt"
      />
      <button onClick={generate} disabled={loading} className="bg-primary text-primary-foreground px-4 py-2 rounded">
        Generate
      </button>
      {loading && <p>Loading...</p>}
      {output && (
        <div className="border p-2 rounded bg-muted">
          <pre className="whitespace-pre-wrap text-sm">{output}</pre>
        </div>
      )}
    </div>
  );
}
