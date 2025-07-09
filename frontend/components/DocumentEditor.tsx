'use client';
import React, { useState } from 'react';
import { updateDocument } from '../utils/api';
import { motion } from 'framer-motion';

interface Props {
  doc: any;
  onSaved?: (id: string, content: string) => void;
}

export default function DocumentEditor({ doc, onSaved }: Props) {
  const [content, setContent] = useState<string>(doc.content || '');
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState<'saved' | 'error' | null>(null);

  async function save() {
    setSaving(true);
    try {
      await updateDocument(doc.id, content);
      setStatus('saved');
      onSaved && onSaved(doc.id, content);
    } catch (e) {
      setStatus('error');
    } finally {
      setSaving(false);
    }
  }

  return (
    <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} className="space-y-2 border rounded p-2">
      <textarea
        className="w-full border rounded p-2 text-sm"
        rows={8}
        value={content}
        onChange={e => setContent(e.target.value)}
      />
      <div className="flex items-center gap-2">
        <button onClick={save} disabled={saving} className="bg-primary text-primary-foreground px-3 py-1 rounded">
          {saving ? 'Saving...' : 'Save'}
        </button>
        {status === 'saved' && <span className="text-green-600 text-sm">Saved</span>}
        {status === 'error' && <span className="text-red-600 text-sm">Error</span>}
      </div>
    </motion.div>
  );
}
