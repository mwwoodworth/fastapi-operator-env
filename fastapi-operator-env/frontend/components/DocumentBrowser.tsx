'use client';
import React, { useEffect, useState } from 'react';
import { fetchDocuments } from '../utils/api';
import DocumentEditor from './DocumentEditor';
import { motion } from 'framer-motion';

export default function DocumentBrowser() {
  const [docs, setDocs] = useState<any[]>([]);
  const [openId, setOpenId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    async function load() {
      setLoading(true);
      try {
        const res = await fetchDocuments();
        const list = res.documents || res.docs || res;
        setDocs(list);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  function handleSaved(id: string, content: string) {
    setDocs(prev => prev.map(d => (d.id === id ? { ...d, content } : d)));
  }

  return (
    <div className="space-y-4">
      {loading && <p>Loading...</p>}
      {!loading && (
        <ul className="space-y-2">
          {docs.map(doc => (
            <li key={doc.id} className="border rounded">
              <button
                className="w-full text-left p-2 font-semibold"
                onClick={() => setOpenId(openId === doc.id ? null : doc.id)}
              >
                {doc.title} <span className="opacity-60 text-xs">{doc.project_id}</span>
              </button>
              {openId === doc.id && (
                <DocumentEditor doc={doc} onSaved={handleSaved} />
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
