import { API_BASE } from './api';

export async function runExportJob() {
  try {
    const res = await fetch(`${API_BASE}/export-docs`, { method: 'POST' });
    if (res.ok) return res.json();
  } catch (e) {
    // ignore
  }
  // fallback
  return { message: 'Local export simulated' };
}

export async function listExportedFiles() {
  try {
    const res = await fetch(`${API_BASE}/export-docs/list`);
    if (res.ok) return res.json();
  } catch (e) {
    // ignore
  }
  return fetch('/exports/index.json').then(r => r.json());
}

export async function uploadFileToDrive(fileId: string) {
  try {
    const res = await fetch(`${API_BASE}/export-docs/upload/${fileId}`, { method: 'POST' });
    if (res.ok) return res.json();
  } catch (e) {
    // ignore
  }
  return { url: '' };
}
