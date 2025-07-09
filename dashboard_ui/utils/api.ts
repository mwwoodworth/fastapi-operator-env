export const API_BASE = 'https://brainops-operator.onrender.com';

export async function postMemoryQuery(query: string) {
  const res = await fetch(`${API_BASE}/memory/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query }),
  });
  return res.json();
}
