'use client';
import React, { useState } from 'react';
import { syncClaudeLogs } from '../utils/api';
import { motion } from 'framer-motion';

export default function ClaudeSyncPanel() {
  const [lastSync, setLastSync] = useState<string | null>(null);
  const [count, setCount] = useState<number>(0);
  const [status, setStatus] = useState<'success' | 'fail' | null>(null);
  const [loading, setLoading] = useState(false);
  const [enabled, setEnabled] = useState(false);

  async function handleSync() {
    setLoading(true);
    try {
      const res = await syncClaudeLogs();
      setCount(res.synced || 0);
      setStatus('success');
    } catch (err) {
      setStatus('fail');
    } finally {
      setLastSync(new Date().toLocaleString());
      setLoading(false);
    }
  }

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-4">
      <div className="flex items-center gap-2">
        <button
          onClick={handleSync}
          disabled={loading}
          className="bg-primary text-primary-foreground px-4 py-2 rounded"
        >
          {loading ? 'Syncing...' : 'Sync Logs'}
        </button>
        <label className="flex items-center gap-1 text-sm">
          <input type="checkbox" checked={enabled} onChange={() => setEnabled(!enabled)} />
          Cron
        </label>
      </div>
      {lastSync && (
        <div className="text-sm space-x-2">
          <span>Last sync: {lastSync}</span>
          <span>Ingested: {count}</span>
          {status === 'success' && (
            <span className="px-2 py-1 bg-green-600 text-white rounded">✅</span>
          )}
          {status === 'fail' && (
            <span className="px-2 py-1 bg-red-600 text-white rounded">❌</span>
          )}
        </div>
      )}
    </motion.div>
  );
}
