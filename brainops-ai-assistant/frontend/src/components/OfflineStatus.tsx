'use client';

import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { WifiOff, Wifi, RefreshCw, CheckCircle, AlertCircle, Cloud } from 'lucide-react';
import { offlineQueue } from '@/lib/offline-queue';
import { offlineStorage } from '@/lib/offline-storage';

interface OfflineStatusProps {
  className?: string;
}

export default function OfflineStatus({ className = '' }: OfflineStatusProps) {
  const [isOnline, setIsOnline] = useState(true);
  const [syncStatus, setSyncStatus] = useState<'idle' | 'syncing' | 'complete'>('idle');
  const [queuedItems, setQueuedItems] = useState(0);
  const [storageStats, setStorageStats] = useState<any>(null);
  const [showDetails, setShowDetails] = useState(false);

  useEffect(() => {
    // Initial status
    setIsOnline(navigator.onLine);

    // Listen for online/offline changes
    const updateOnlineStatus = () => setIsOnline(navigator.onLine);
    window.addEventListener('online', updateOnlineStatus);
    window.addEventListener('offline', updateOnlineStatus);

    // Listen for queue status changes
    offlineQueue.onStatusChange((online) => {
      setIsOnline(online);
      updateQueueStatus();
    });

    // Listen for sync events
    const handleSyncComplete = (event: CustomEvent) => {
      setSyncStatus('complete');
      setTimeout(() => setSyncStatus('idle'), 3000);
      updateQueueStatus();
    };

    window.addEventListener('offline-sync-complete', handleSyncComplete as EventListener);

    // Update queue status periodically
    const interval = setInterval(updateQueueStatus, 5000);
    updateQueueStatus();

    return () => {
      window.removeEventListener('online', updateOnlineStatus);
      window.removeEventListener('offline', updateOnlineStatus);
      window.removeEventListener('offline-sync-complete', handleSyncComplete as EventListener);
      clearInterval(interval);
    };
  }, []);

  const updateQueueStatus = async () => {
    const status = await offlineQueue.getStatus();
    setQueuedItems(status.queuedItems);
    setStorageStats(status.storageStats);
    if (status.syncInProgress) {
      setSyncStatus('syncing');
    }
  };

  const handleManualSync = () => {
    if (isOnline) {
      setSyncStatus('syncing');
      offlineQueue.sync();
    }
  };

  const getStatusIcon = () => {
    if (!isOnline) return <WifiOff className="w-5 h-5" />;
    if (syncStatus === 'syncing') return <RefreshCw className="w-5 h-5 animate-spin" />;
    if (syncStatus === 'complete') return <CheckCircle className="w-5 h-5" />;
    if (queuedItems > 0) return <Cloud className="w-5 h-5" />;
    return <Wifi className="w-5 h-5" />;
  };

  const getStatusColor = () => {
    if (!isOnline) return 'bg-red-500';
    if (syncStatus === 'syncing') return 'bg-blue-500';
    if (syncStatus === 'complete') return 'bg-green-500';
    if (queuedItems > 0) return 'bg-yellow-500';
    return 'bg-green-500';
  };

  const getStatusText = () => {
    if (!isOnline) return 'Offline';
    if (syncStatus === 'syncing') return 'Syncing...';
    if (syncStatus === 'complete') return 'Synced';
    if (queuedItems > 0) return `${queuedItems} queued`;
    return 'Online';
  };

  return (
    <>
      {/* Main status indicator */}
      <div className={`relative ${className}`}>
        <button
          onClick={() => setShowDetails(!showDetails)}
          className={`
            flex items-center gap-2 px-3 py-1.5 rounded-full text-white text-sm font-medium
            transition-all duration-200 hover:opacity-90 ${getStatusColor()}
          `}
        >
          {getStatusIcon()}
          <span>{getStatusText()}</span>
        </button>

        {/* Sync button when items are queued */}
        {isOnline && queuedItems > 0 && syncStatus !== 'syncing' && (
          <button
            onClick={handleManualSync}
            className="absolute -right-2 -top-2 p-1 bg-blue-600 rounded-full text-white hover:bg-blue-700"
            title="Sync now"
          >
            <RefreshCw className="w-3 h-3" />
          </button>
        )}
      </div>

      {/* Detailed status popup */}
      <AnimatePresence>
        {showDetails && (
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: -10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: -10 }}
            className="absolute top-12 right-4 bg-gray-900 border border-gray-700 rounded-lg shadow-xl p-4 z-50 min-w-[280px]"
          >
            <h3 className="text-white font-semibold mb-3 flex items-center gap-2">
              <Cloud className="w-4 h-4" />
              Offline Storage Status
            </h3>

            <div className="space-y-2 text-sm">
              {/* Connection status */}
              <div className="flex justify-between items-center">
                <span className="text-gray-400">Connection:</span>
                <span className={isOnline ? 'text-green-400' : 'text-red-400'}>
                  {isOnline ? 'Online' : 'Offline'}
                </span>
              </div>

              {/* Storage stats */}
              {storageStats && (
                <>
                  <div className="flex justify-between items-center">
                    <span className="text-gray-400">Messages:</span>
                    <span className="text-gray-200">{storageStats.messages}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-gray-400">Files:</span>
                    <span className="text-gray-200">{storageStats.files}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-gray-400">Voice Memos:</span>
                    <span className="text-gray-200">{storageStats.voiceMemos}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-gray-400">Queued Items:</span>
                    <span className={queuedItems > 0 ? 'text-yellow-400' : 'text-gray-200'}>
                      {queuedItems}
                    </span>
                  </div>
                </>
              )}

              {/* Offline mode features */}
              {!isOnline && (
                <div className="mt-3 pt-3 border-t border-gray-700">
                  <p className="text-gray-300 mb-2">Available offline:</p>
                  <ul className="space-y-1 text-gray-400">
                    <li className="flex items-center gap-2">
                      <CheckCircle className="w-3 h-3 text-green-400" />
                      <span>Chat messages saved locally</span>
                    </li>
                    <li className="flex items-center gap-2">
                      <CheckCircle className="w-3 h-3 text-green-400" />
                      <span>Voice recording enabled</span>
                    </li>
                    <li className="flex items-center gap-2">
                      <CheckCircle className="w-3 h-3 text-green-400" />
                      <span>File uploads cached</span>
                    </li>
                    <li className="flex items-center gap-2">
                      <CheckCircle className="w-3 h-3 text-green-400" />
                      <span>Auto-sync when online</span>
                    </li>
                  </ul>
                </div>
              )}

              {/* Sync button */}
              {isOnline && queuedItems > 0 && (
                <button
                  onClick={handleManualSync}
                  disabled={syncStatus === 'syncing'}
                  className="w-full mt-3 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                >
                  <RefreshCw className={`w-4 h-4 ${syncStatus === 'syncing' ? 'animate-spin' : ''}`} />
                  {syncStatus === 'syncing' ? 'Syncing...' : 'Sync Now'}
                </button>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}