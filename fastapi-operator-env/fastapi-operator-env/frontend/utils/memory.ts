import { API_BASE } from './config';

export interface MemoryEntry {
  project_id: string;
  title: string;
  content: string;
  author_id: string;
}

export async function postMemoryWrite(entry: MemoryEntry) {
  const res = await fetch(`${API_BASE}/memory/write`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(entry),
  });
  return res.json();
}

export async function getMemoryQuery(query: string) {
  const res = await fetch(`${API_BASE}/memory/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query }),
  });
  return res.json();
}
