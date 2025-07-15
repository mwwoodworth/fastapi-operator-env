'use client';
import React, { useEffect, useState } from 'react';
import { fetchOpsMetrics, fetchRecentPosts, fetchRecentTasks } from '../../../utils/api';

export default function OpsPage() {
  const [metrics, setMetrics] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [recentPosts, setRecentPosts] = useState<any[]>([]);
  const [taskInfo, setTaskInfo] = useState<any | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const data = await fetchOpsMetrics();
        setMetrics(data);
        const posts = await fetchRecentPosts();
        setRecentPosts(posts.entries || posts.documents || []);
        const tasks = await fetchRecentTasks();
        setTaskInfo(tasks);
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
      {taskInfo && (
        <div className="border rounded p-4">
          <h3 className="font-semibold mb-2">Task Summary</h3>
          <p>Pending: {taskInfo.pending}</p>
          <p>Recurring Enabled: {taskInfo.recurring_enabled}</p>
        </div>
      )}
      {recentPosts.length > 0 && (
        <div className="border rounded p-4">
          <h3 className="font-semibold mb-2">Recent Content</h3>
          <ul className="list-disc pl-4">
            {recentPosts.map((p: any) => (
              <li key={p.id || p.document_id}>{p.title}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
