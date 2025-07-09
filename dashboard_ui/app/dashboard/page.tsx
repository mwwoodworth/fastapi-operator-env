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
      </ul>
    </div>
  );
}
