// Offline Queue Management System
import { offlineStorage } from './offline-storage';

interface Message {
  id: string;
  content: string;
  role: 'user' | 'assistant' | 'system';
  timestamp: number;
  synced?: boolean;
  sessionId?: string;
  metadata?: Record<string, unknown>;
}

export interface QueueItem {
  type: 'message' | 'file' | 'voice' | 'task';
  payload: Record<string, unknown>;
  endpoint?: string;
  method?: string;
}

export class OfflineQueue {
  private syncInProgress = false;
  private onlineStatusListeners: ((online: boolean) => void)[] = [];
  private syncInterval: NodeJS.Timeout | null = null;

  constructor() {
    if (typeof window !== 'undefined') {
      this.setupOnlineListener();
      this.startPeriodicSync();
    }
  }

  // Setup online/offline detection
  private setupOnlineListener() {
    window.addEventListener('online', () => {
      console.log('[OfflineQueue] Back online, starting sync...');
      this.notifyStatusChange(true);
      this.sync();
    });

    window.addEventListener('offline', () => {
      console.log('[OfflineQueue] Gone offline');
      this.notifyStatusChange(false);
    });
  }

  // Add status change listener
  onStatusChange(callback: (online: boolean) => void) {
    this.onlineStatusListeners.push(callback);
    // Call immediately with current status
    callback(navigator.onLine);
  }

  // Notify all listeners of status change
  private notifyStatusChange(online: boolean) {
    this.onlineStatusListeners.forEach(cb => cb(online));
  }

  // Start periodic sync attempts
  private startPeriodicSync() {
    this.syncInterval = setInterval(() => {
      if (navigator.onLine && !this.syncInProgress) {
        this.sync();
      }
    }, 30000); // Try every 30 seconds
  }

  // Add item to queue
  async enqueue(item: QueueItem): Promise<string> {
    const queueItem = {
      type: item.type,
      payload: item.payload,
      timestamp: Date.now(),
      retries: 0,
      status: 'pending' as const,
      endpoint: item.endpoint,
      method: item.method,
    };

    return offlineStorage.addToQueue(queueItem);
  }

  // Process queued messages
  async processMessage(item: {
    id: string;
    type: string;
    payload: Record<string, unknown> & { messageId?: string; sessionId?: string };
    endpoint?: string;
    method?: string;
    status: string;
    retries: number;
  }): Promise<boolean> {
    try {
      const response = await fetch(item.endpoint || '/api/assistant/messages', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(item.payload),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      // Mark the original message as synced
      if (item.payload.messageId && item.payload.sessionId) {
        const messages = await offlineStorage.getMessages(item.payload.sessionId);
        const message = messages.find((m: Message) => m.id === item.payload.messageId);
        if (message) {
          message.synced = true;
          await offlineStorage.saveMessage(message);
        }
      }

      return true;
    } catch (error) {
      console.error('[OfflineQueue] Error processing message:', error);
      return false;
    }
  }

  // Process queued files
  async processFile(item: {
    id: string;
    type: string;
    payload: Record<string, unknown> & { fileId?: string };
    endpoint?: string;
    method?: string;
    status: string;
    retries: number;
  }): Promise<boolean> {
    try {
      if (!item.payload.fileId) {
        console.error('[OfflineQueue] No fileId in payload');
        return true; // Remove from queue anyway
      }
      const file = await offlineStorage.getFile(item.payload.fileId as string);
      if (!file) {
        console.error('[OfflineQueue] File not found:', item.payload.fileId);
        return true; // Remove from queue anyway
      }

      const formData = new FormData();
      const blob = new Blob([file.data], { type: file.type });
      formData.append('file', blob, file.name);

      const response = await fetch(item.endpoint || '/api/files/upload', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      // Mark file as synced
      await offlineStorage.markFileAsSynced(file.id);

      return true;
    } catch (error) {
      console.error('[OfflineQueue] Error processing file:', error);
      return false;
    }
  }

  // Process queued voice memos
  async processVoiceMemo(item: {
    id: string;
    type: string;
    payload: Record<string, unknown> & { voiceId?: string };
    endpoint?: string;
    method?: string;
    status: string;
    retries: number;
  }): Promise<boolean> {
    try {
      if (!item.payload.voiceId) {
        console.error('[OfflineQueue] No voiceId in payload');
        return true; // Remove from queue anyway
      }
      const voiceMemo = await offlineStorage.getVoiceMemo(item.payload.voiceId as string);
      if (!voiceMemo) {
        console.error('[OfflineQueue] Voice memo not found:', item.payload.voiceId);
        return true; // Remove from queue anyway
      }

      const formData = new FormData();
      formData.append('audio', voiceMemo.blob, 'voice-memo.webm');
      formData.append('duration', voiceMemo.duration.toString());

      const response = await fetch(item.endpoint || '/api/voice/upload', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const result = await response.json();

      // Update voice memo with transcription if available
      if (result.transcription) {
        await offlineStorage.updateVoiceMemoTranscription(voiceMemo.id, result.transcription);
      }

      // Mark as synced
      await offlineStorage.markVoiceMemoAsSynced(voiceMemo.id);

      return true;
    } catch (error) {
      console.error('[OfflineQueue] Error processing voice memo:', error);
      return false;
    }
  }

  // Process queued tasks
  async processTask(item: {
    id: string;
    type: string;
    payload: Record<string, unknown>;
    endpoint?: string;
    method?: string;
    status: string;
    retries: number;
  }): Promise<boolean> {
    try {
      const response = await fetch(item.endpoint || '/api/tasks', {
        method: item.method || 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(item.payload),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      return true;
    } catch (error) {
      console.error('[OfflineQueue] Error processing task:', error);
      return false;
    }
  }

  // Main sync function
  async sync(): Promise<void> {
    if (this.syncInProgress || !navigator.onLine) {
      return;
    }

    this.syncInProgress = true;
    console.log('[OfflineQueue] Starting sync...');

    try {
      const pendingItems = await offlineStorage.getQueueItems('pending');
      console.log(`[OfflineQueue] Found ${pendingItems.length} items to sync`);

      for (const item of pendingItems) {
        // Update status to syncing
        await offlineStorage.updateQueueItem(item.id, { status: 'syncing' });

        let success = false;

        // Process based on type
        switch (item.type) {
          case 'message':
            success = await this.processMessage(item);
            break;
          case 'file':
            success = await this.processFile(item);
            break;
          case 'voice':
            success = await this.processVoiceMemo(item);
            break;
          case 'task':
            success = await this.processTask(item);
            break;
        }

        if (success) {
          // Remove from queue
          await offlineStorage.removeFromQueue(item.id);
          console.log(`[OfflineQueue] Successfully synced item ${item.id}`);
        } else {
          // Increment retry count and mark as pending again
          await offlineStorage.updateQueueItem(item.id, {
            status: 'pending',
            retries: item.retries + 1,
          });

          // If too many retries, mark as failed
          if (item.retries >= 3) {
            await offlineStorage.updateQueueItem(item.id, { status: 'failed' });
            console.error(`[OfflineQueue] Item ${item.id} failed after 3 retries`);
          }
        }
      }

      // Notify completion
      window.dispatchEvent(new CustomEvent('offline-sync-complete', {
        detail: { itemsProcessed: pendingItems.length }
      }));

    } catch (error) {
      console.error('[OfflineQueue] Sync error:', error);
    } finally {
      this.syncInProgress = false;
    }
  }

  // Get queue status
  async getStatus() {
    const stats = await offlineStorage.getStorageStats();
    const pending = await offlineStorage.getQueueItems('pending');
    const failed = await offlineStorage.getQueueItems('failed');

    return {
      online: navigator.onLine,
      syncInProgress: this.syncInProgress,
      queuedItems: pending.length,
      failedItems: failed.length,
      storageStats: stats,
    };
  }

  // Clear failed items
  async clearFailed() {
    const failed = await offlineStorage.getQueueItems('failed');
    for (const item of failed) {
      await offlineStorage.removeFromQueue(item.id);
    }
  }

  // Retry failed items
  async retryFailed() {
    const failed = await offlineStorage.getQueueItems('failed');
    for (const item of failed) {
      await offlineStorage.updateQueueItem(item.id, {
        status: 'pending',
        retries: 0,
      });
    }
    this.sync();
  }

  // Cleanup
  destroy() {
    if (this.syncInterval) {
      clearInterval(this.syncInterval);
    }
  }
}

// Export singleton instance
export const offlineQueue = typeof window !== 'undefined' ? new OfflineQueue() : null as unknown as OfflineQueue;