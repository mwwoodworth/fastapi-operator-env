'use client';

import dynamic from 'next/dynamic';

// Dynamic import to avoid SSR issues with offline features
const OfflineChat = dynamic(() => import('@/components/OfflineChat'), {
  ssr: false,
});

export default function Home() {
  return (
    <div className="min-h-screen bg-gray-900">
      <OfflineChat />
    </div>
  );
}