import { API_BASE } from './config';

export async function postMemoryQuery(query: string) {
  const res = await fetch(`${API_BASE}/memory/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query }),
  });
  return res.json();
}

export async function syncClaudeLogs() {
  return fetch(`${API_BASE}/sync-claude-logs`, { method: 'POST' }).then(r => r.json());
}

export async function fetchDocuments() {
  return fetch(`${API_BASE}/documents`).then(r => r.json());
}

export async function updateDocument(id: string, content: string) {
  return fetch(`${API_BASE}/memory/update`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ document_id: id, content }),
  }).then(r => r.json());
}

export async function writeMemory(entry: {
  project_id: string;
  title: string;
  content: string;
  author_id: string;
}) {
  return fetch(`${API_BASE}/memory/write`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(entry),
  }).then(r => r.json());
}

export async function fetchProductDocs() {
  return fetch(`${API_BASE}/memory/query?tags=product&limit=50`).then(r => r.json());
}

export async function fetchOpsMetrics() {
  return fetch(`${API_BASE}/dashboard/ops`).then(r => r.json());
}
