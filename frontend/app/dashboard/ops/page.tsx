'use client';
import React, { useEffect, useState } from 'react';
import { fetchOpsMetrics } from '../../../utils/api';

export default function OpsPage() {
  const [metrics, setMetrics] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const data = await fetchOpsMetrics();
        setMetrics(data);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold">Operations Dashboard</h2>
      {loading && <p>Loading...</p>}
      {metrics && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="border rounded p-4 text-center">
            <p className="text-sm opacity-70">Sales</p>
            <p className="text-2xl font-semibold">{metrics.sales ?? 0}</p>
          </div>
          <div className="border rounded p-4 text-center">
            <p className="text-sm opacity-70">Signups</p>
            <p className="text-2xl font-semibold">{metrics.signups ?? 0}</p>
          </div>
          <div className="border rounded p-4 text-center">
            <p className="text-sm opacity-70">Active Users</p>
            <p className="text-2xl font-semibold">{metrics.active_users ?? 0}</p>
          </div>
          <div className="border rounded p-4 text-center">
            <p className="text-sm opacity-70">Tasks Logged</p>
            <p className="text-2xl font-semibold">{metrics.tasks_logged ?? 0}</p>
          </div>
        </div>
      )}
    </div>
  );
}
