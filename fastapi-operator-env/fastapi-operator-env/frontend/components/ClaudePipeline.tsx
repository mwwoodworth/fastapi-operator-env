'use client';
import React, { useState } from 'react';
import { promptClaude } from '../utils/ai';
import { writeMemory } from '../utils/api';

const categories = [
  'Estimators',
  'Templates',
  'SOPs',
  'Calculators',
  'Proposal Builders',
];

export default function ClaudePipeline() {
  const [category, setCategory] = useState(categories[0]);
  const [prompt, setPrompt] = useState('');
  const [result, setResult] = useState('');
  const [loading, setLoading] = useState(false);

  async function run() {
    if (!prompt.trim()) return;
    setLoading(true);
    try {
      const res = await promptClaude(`${category}: ${prompt}`);
      const text = res.result || res.response || res.completion || '';
      setResult(text);
      await writeMemory({
        project_id: 'pipeline',
        title: prompt.slice(0, 40),
        content: `${prompt}\n${text}`,
        author_id: 'user',
      });
    } finally {
      setLoading(false);
    }
  }

  function download() {
    const blob = new Blob([result], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${category}.md`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <select
          className="border px-2 py-1 rounded text-sm"
          value={category}
          onChange={e => setCategory(e.target.value)}
        >
          {categories.map(c => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
        <input
          className="flex-1 border px-2 py-1 rounded"
          value={prompt}
          onChange={e => setPrompt(e.target.value)}
          placeholder="Enter prompt"
        />
        <button
          onClick={run}
          disabled={loading}
          className="bg-primary text-primary-foreground px-4 py-1 rounded"
        >
          {loading ? 'Running...' : 'Submit'}
        </button>
      </div>
      {result && (
        <div className="space-y-2">
          <pre className="whitespace-pre-wrap text-sm border rounded p-2 bg-muted">
            {result}
          </pre>
          <button onClick={download} className="underline text-sm">Export as Markdown</button>
        </div>
      )}
    </div>
  );
}
