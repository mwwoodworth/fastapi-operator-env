'use client';
import React, { useState } from 'react';
import { suggestSEO } from '../utils/pipeline';

export default function SEOInsights() {
  const [url, setUrl] = useState('');
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  async function handleSuggest() {
    if (!url.trim()) return;
    setLoading(true);
    try {
      const res = await suggestSEO(url);
      setResult(res);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-2">
      <div className="flex gap-2">
        <input className="flex-1 border px-2 py-1 rounded" value={url} onChange={e => setUrl(e.target.value)} placeholder="Page URL or Markdown" />
        <button onClick={handleSuggest} disabled={loading} className="bg-primary text-primary-foreground px-3 py-1 rounded">
          {loading ? 'Analyzing...' : 'Suggest SEO'}
        </button>
      </div>
      {result && (
        <pre className="whitespace-pre-wrap text-sm border p-2 rounded bg-muted">{JSON.stringify(result, null, 2)}</pre>
      )}
    </div>
  );
}
