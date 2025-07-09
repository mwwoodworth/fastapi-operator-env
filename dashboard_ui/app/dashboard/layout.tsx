import React from 'react';
import Link from 'next/link';
import '../../styles/globals.css';
import AssistantChatWidget from '../../components/AssistantChatWidget';

export const metadata = {
  title: 'BrainOps Dashboard',
};

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen flex">
      <aside className="w-64 bg-muted p-4 hidden md:block">
        <h1 className="font-bold mb-4">BrainOps</h1>
        <nav className="space-y-2">
          <Link href="/dashboard" className="block">Home</Link>
          <Link href="/dashboard/memory" className="block">Memory</Link>
          <Link href="/dashboard/copilot" className="block">Copilot</Link>
          <Link href="/dashboard/copilot-v2" className="block">Copilot v2</Link>
          <Link href="/dashboard/sync" className="block">Sync</Link>
          <Link href="/dashboard/documents" className="block">Documents</Link>
          <Link href="/dashboard/generate" className="block">Generate</Link>
          <Link href="/dashboard/export" className="block">Export</Link>
        </nav>
      </aside>
      <div className="flex-1 p-4">
        {children}
      </div>
      <AssistantChatWidget />
    </div>
  );
}
