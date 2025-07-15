'use client';
import React, { useEffect, useState } from 'react';
import { runExportJob, listExportedFiles, uploadFileToDrive } from '../utils/export';
import Link from 'next/link';

interface ExportFile {
  id: string;
  title?: string;
  name?: string;
  created_at?: string;
  date?: string;
  uploaded?: boolean;
  drive_url?: string;
  path?: string;
  summary?: string;
}

export default function ExportPanel() {
  const [files, setFiles] = useState<ExportFile[]>([]);
  const [loading, setLoading] = useState(false);
  const [log, setLog] = useState('');

  async function load() {
    try {
      const res = await listExportedFiles();
      const list = res.files || res;
      setFiles(list);
    } catch (e) {
      console.error(e);
    }
  }

  useEffect(() => {
    load();
    const id = setInterval(handleExport, 21600000);
    return () => clearInterval(id);
  }, []);

  async function handleExport() {
    setLoading(true);
    try {
      const res = await runExportJob();
      setLog(res.message || 'Export completed');
      await load();
    } catch (e) {
      setLog('Failed');
    } finally {
      setLoading(false);
    }
  }

  async function handleUpload(id: string) {
    try {
      const res = await uploadFileToDrive(id);
      const url = res.url || res.drive_url;
      setFiles(prev => prev.map(f => (f.id === id ? { ...f, uploaded: true, drive_url: url } : f)));
    } catch (e) {
      console.error(e);
    }
  }

  return (
    <div className="space-y-4">
      <button onClick={handleExport} disabled={loading} className="bg-primary text-primary-foreground px-4 py-2 rounded">
        {loading ? 'Exporting...' : 'Run Export Now'}
      </button>
      {log && <p className="text-sm">{log}</p>}
      <ul className="space-y-2">
        {files.map(f => (
          <li key={f.id} className="border rounded p-2">
            <div className="flex justify-between items-center">
              <span>{f.title || f.name}</span>
              <span className="text-xs opacity-60">{f.created_at || f.date}</span>
            </div>
            {f.summary && (
              <p className="text-xs mt-1 whitespace-pre-wrap">{f.summary}</p>
            )}
            <div className="flex items-center gap-2 mt-1 text-sm">
              <button
                onClick={() => handleUpload(f.id)}
                disabled={f.uploaded}
                className="bg-primary text-primary-foreground px-2 py-1 rounded"
              >
                Upload to Drive
              </button>
              {f.uploaded ? (
                <span className="text-green-600">✅</span>
              ) : (
                <span className="text-red-600">❌</span>
              )}
              {f.drive_url && (
                <Link href={f.drive_url} target="_blank" rel="noopener noreferrer" className="underline">
                  Open
                </Link>
              )}
              {!f.drive_url && f.path && (
                <Link href={f.path} target="_blank" rel="noopener noreferrer" className="underline">
                  Preview
                </Link>
              )}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
