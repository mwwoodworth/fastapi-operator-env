import { useState } from 'react';

export default function MemoryPage() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);

  async function handleSearch(e) {
    e.preventDefault();
    const res = await fetch('/api/memory/query', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query }),
    });
    const data = await res.json();
    setResults(data.results || []);
  }

  return (
    <div className="p-6">
      <h1 className="text-2xl font-semibold mb-4">Memory Search</h1>
      <form onSubmit={handleSearch} className="mb-6">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search memory..."
          className="border px-3 py-2 mr-2"
        />
        <button type="submit" className="bg-blue-600 text-white px-4 py-2">
          Search
        </button>
      </form>

      <ul className="space-y-4">
        {results.map((r, idx) => (
          <li key={idx} className="border p-4 rounded">
            {r.content_chunk || r.content}
          </li>
        ))}
      </ul>
    </div>
  );
}
