'use client';
import React, { useState } from 'react';
import { postMemoryQuery } from '../utils/api';
import MemoryResultCard from './MemoryResultCard';

export default function MemorySearchPanel() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([] as any[]);
  const [loading, setLoading] = useState(false);

  async function handleSearch(e?: any) {
    e?.preventDefault();
    if (!query) return;
    setLoading(true);
    try {
      const data = await postMemoryQuery(query);
      setResults(data.results || []);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4">
      <form onSubmit={handleSearch} className="flex gap-2">
        <input
          value={query}
          onChange={(e: any) => setQuery(e.target.value)}
          placeholder="Search memory..."
          className="flex-1 border px-3 py-2 rounded"
        />
        <button type="submit" className="bg-primary text-primary-foreground px-4 py-2 rounded">
          Search
        </button>
      </form>
      {loading && <p>Loading...</p>}
      <div className="space-y-2">
        {results.map((r: any, idx: number) => (
          (<MemoryResultCard key={idx} result={r} /> as any)
        ))}
      </div>
    </div>
  );
}

interface MemoryResult {
  title?: string;
  content_chunk: string;
}
