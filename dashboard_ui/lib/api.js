const API_BASE = process.env.NEXT_PUBLIC_API_BASE || '';
const AUTH_HEADER = process.env.NEXT_PUBLIC_AUTH_HEADER;

export async function apiFetch(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (AUTH_HEADER) headers['Authorization'] = AUTH_HEADER;
  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!res.ok) throw new Error(`Request failed: ${res.status}`);
  return res.json();
}
