import React from 'react';
import Link from 'next/link';

export default function DashboardHome() {
  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-semibold">Dashboard</h2>
      <p>Select a module:</p>
      <ul className="list-disc pl-6 space-y-1">
        <li>
          <Link href="/dashboard/memory" className="text-blue-600 underline">
            Memory Explorer
          </Link>
        </li>
        <li>
          <Link href="/dashboard/copilot" className="text-blue-600 underline">
            Copilot Assistant
          </Link>
        </li>
        <li>
          <Link href="/dashboard/copilot-v2" className="text-blue-600 underline">
            Copilot v2
          </Link>
        </li>
        <li>
          <Link href="/dashboard/sync" className="text-blue-600 underline">
            Claude Sync
          </Link>
        </li>
        <li>
          <Link href="/dashboard/documents" className="text-blue-600 underline">
            Documents
          </Link>
        </li>
        <li>
          <Link href="/dashboard/export" className="text-blue-600 underline">
            Export
          </Link>
        </li>
      </ul>
    </div>
  );
}
