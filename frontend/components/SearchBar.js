import { useState } from 'react';
import { motion } from 'framer-motion';
import { apiFetch } from '../lib/api';

export default function SearchBar() {
  const [q, setQ] = useState('');
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);

  const search = async () => {
    if (!q) return;
    setLoading(true);
    try {
      const data = await apiFetch(`/memory/search?q=${encodeURIComponent(q)}`);
      setResults(data.entries || []);
    } catch (err) {
      console.error(err);
      setResults([]);
    }
    setLoading(false);
  };

  return (
    <div className="space-y-2">
      <div className="flex gap-2">
        <input
          className="border rounded p-2 flex-1"
          value={q}
          aria-label="Search Memory"
          placeholder="Search Memory"
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && search()}
        />
        <button className="border rounded px-3" onClick={search} aria-label="Search">Search</button>
      </div>
      {loading && <p>Searching...</p>}
      {!loading && results && (
        <motion.ul initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="list-disc list-inside space-y-1">
          {results.length === 0 && <li className="italic">No results</li>}
          {results.map((r, i) => (
            <li key={i}>{r.content || JSON.stringify(r)}</li>
          ))}
        </motion.ul>
      )}
    </div>
  );
}
