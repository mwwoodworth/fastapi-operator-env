'use client';
import React, { useState } from 'react';
import { runPipeline } from '../utils/pipeline';

const types = ['SOP', 'Proposal', 'Toolkit'];

export default function GeneratorPanel() {
  const [blueprint, setBlueprint] = useState(types[0]);
  const [topic, setTopic] = useState('');
  const [output, setOutput] = useState('');
  const [loading, setLoading] = useState(false);

  async function generate() {
    if (!topic.trim()) return;
    setLoading(true);
    try {
      const res = await runPipeline(blueprint, topic);
      setOutput(res);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-2">
      <div className="flex gap-2">
        <select className="border px-2 py-1 rounded" value={blueprint} onChange={e => setBlueprint(e.target.value)}>
          {types.map(t => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
        <input className="flex-1 border px-2 py-1 rounded" value={topic} onChange={e => setTopic(e.target.value)} placeholder="Topic" />
        <button onClick={generate} disabled={loading} className="bg-primary text-primary-foreground px-3 py-1 rounded">
          {loading ? 'Generating...' : 'Generate'}
        </button>
      </div>
      {output && (
        <pre className="whitespace-pre-wrap text-sm border p-2 rounded bg-muted">{output}</pre>
      )}
    </div>
  );
}
