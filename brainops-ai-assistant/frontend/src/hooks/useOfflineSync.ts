// Hook for managing offline sync in components
import { useEffect, useState, useCallback } from 'react';
import { offlineStorage } from '@/lib/offline-storage';
import { offlineQueue } from '@/lib/offline-queue';
import { voiceRecorder } from '@/lib/voice-recorder';
import toast from 'react-hot-toast';

interface UseOfflineSyncOptions {
  sessionId?: string;
  autoSync?: boolean;
  onSyncComplete?: () => void;
}

export function useOfflineSync(options: UseOfflineSyncOptions = {}) {
  const { sessionId, autoSync = true, onSyncComplete } = options;
  const [isOnline, setIsOnline] = useState(navigator.onLine);
  const [isSyncing, setIsSyncing] = useState(false);
  const [queuedCount, setQueuedCount] = useState(0);
  const [lastSyncTime, setLastSyncTime] = useState<Date | null>(null);

  // Initialize offline storage
  useEffect(() => {
    offlineStorage.initialize().catch(console.error);
  }, []);

  // Sync data to server
  const syncData = useCallback(async () => {
    if (!isOnline || isSyncing) return;
    
    setIsSyncing(true);
    try {
      await offlineQueue.sync();
    } catch (error) {
      console.error('Sync failed:', error);
      toast.error('Failed to sync data. Will retry later.');
      setIsSyncing(false);
    }
  }, [isOnline, isSyncing]);

  // Update queued items count
  const updateQueueCount = useCallback(async () => {
    const status = await offlineQueue.getStatus();
    setQueuedCount(status.queuedItems);
  }, []);

  // Monitor online status
  useEffect(() => {
    const handleOnline = () => {
      setIsOnline(true);
      toast.success('Back online! Syncing your data...', {
        icon: '🌐',
        duration: 3000,
      });
      if (autoSync) {
        syncData();
      }
    };

    const handleOffline = () => {
      setIsOnline(false);
      toast.error('You\'re offline. Your work will be saved locally.', {
        icon: '📴',
        duration: 4000,
      });
    };

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    // Listen for sync completion
    const handleSyncComplete = () => {
      setIsSyncing(false);
      setLastSyncTime(new Date());
      updateQueueCount();
      onSyncComplete?.();
      toast.success('All data synced successfully!', {
        icon: '✅',
        duration: 2000,
      });
    };

    window.addEventListener('offline-sync-complete', handleSyncComplete);

    // Initial queue count
    updateQueueCount();

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
      window.removeEventListener('offline-sync-complete', handleSyncComplete);
    };
  }, [autoSync, onSyncComplete, syncData, updateQueueCount]);

  // Save message locally
  const saveMessage = useCallback(async (content: string, role: 'user' | 'assistant' | 'system') => {
    const message = {
      id: `msg-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      content,
      role,
      timestamp: Date.now(),
      synced: isOnline,
      sessionId: sessionId || 'default',
    };

    await offlineStorage.saveMessage(message);

    // Queue for sync if offline
    if (!isOnline) {
      await offlineQueue.enqueue({
        type: 'message',
        payload: {
          messageId: message.id,
          sessionId: message.sessionId,
          content: message.content,
          role: message.role,
        },
      });
      updateQueueCount();
    }

    return message.id;
  }, [isOnline, sessionId, updateQueueCount]);

  // Save file locally
  const saveFile = useCallback(async (file: File) => {
    const fileId = await offlineStorage.saveFile(file);

    // Queue for upload if offline
    if (!isOnline) {
      await offlineQueue.enqueue({
        type: 'file',
        payload: { fileId },
      });
      updateQueueCount();
    }

    return fileId;
  }, [isOnline, updateQueueCount]);

  // Start voice recording
  const startVoiceRecording = useCallback(async () => {
    try {
      await voiceRecorder.startRecording();
      toast.success('Recording started...', {
        icon: '🎙️',
        duration: 2000,
      });
    } catch (error) {
      toast.error('Failed to start recording');
      console.error(error);
    }
  }, []);

  // Stop voice recording
  const stopVoiceRecording = useCallback(async () => {
    try {
      const memoId = await voiceRecorder.stopRecording();
      if (memoId) {
        toast.success('Voice memo saved!', {
          icon: '🎵',
          duration: 2000,
        });
        updateQueueCount();
      }
      return memoId;
    } catch (error) {
      toast.error('Failed to save recording');
      console.error(error);
      return null;
    }
  }, [updateQueueCount]);

  // Get session messages
  const getSessionMessages = useCallback(async () => {
    if (!sessionId) return [];
    return offlineStorage.getMessages(sessionId);
  }, [sessionId]);

  // Clear local data
  const clearLocalData = useCallback(async () => {
    await offlineStorage.clearAll();
    toast.success('Local data cleared');
  }, []);

  // Get storage stats
  const getStorageStats = useCallback(async () => {
    return offlineStorage.getStorageStats();
  }, []);

  return {
    // State
    isOnline,
    isSyncing,
    queuedCount,
    lastSyncTime,
    
    // Actions
    saveMessage,
    saveFile,
    startVoiceRecording,
    stopVoiceRecording,
    syncData,
    getSessionMessages,
    clearLocalData,
    getStorageStats,
    
    // Utils
    updateQueueCount,
  };
}