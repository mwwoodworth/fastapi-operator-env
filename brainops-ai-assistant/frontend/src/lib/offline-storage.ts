// IndexedDB Storage for Offline Resilience
import { openDB, IDBPDatabase } from 'idb';

// Type definitions for message and other data structures
interface Message {
  id: string;
  content: string;
  role: 'user' | 'assistant' | 'system';
  timestamp: number;
  synced: boolean;
  sessionId: string;
  metadata?: Record<string, unknown>;
}

interface Session {
  id: string;
  createdAt: number;
  updatedAt: number;
  context: Record<string, unknown>;
  online: boolean;
}

interface QueueItem {
  id: string;
  type: 'message' | 'file' | 'voice' | 'task';
  payload: Record<string, unknown>;
  timestamp: number;
  retries: number;
  status: 'pending' | 'syncing' | 'failed';
}

interface FileItem {
  id: string;
  name: string;
  type: string;
  size: number;
  data: ArrayBuffer;
  timestamp: number;
  synced: boolean;
}

interface VoiceMemo {
  id: string;
  blob: Blob;
  duration: number;
  timestamp: number;
  transcription?: string;
  synced: boolean;
}

class OfflineStorage {
  private db: IDBPDatabase | null = null;
  private readonly DB_NAME = 'BrainOpsAssistant';
  private readonly DB_VERSION = 1;

  async initialize() {
    if (this.db) return;

    this.db = await openDB(this.DB_NAME, this.DB_VERSION, {
      upgrade(db) {
        // Messages store
        if (!db.objectStoreNames.contains('messages')) {
          const messageStore = db.createObjectStore('messages', { keyPath: 'id' });
          messageStore.createIndex('sessionId', 'sessionId');
          messageStore.createIndex('timestamp', 'timestamp');
          messageStore.createIndex('synced', 'synced');
        }

        // Sessions store
        if (!db.objectStoreNames.contains('sessions')) {
          const sessionStore = db.createObjectStore('sessions', { keyPath: 'id' });
          sessionStore.createIndex('updatedAt', 'updatedAt');
        }

        // Queue store for pending operations
        if (!db.objectStoreNames.contains('queue')) {
          const queueStore = db.createObjectStore('queue', { keyPath: 'id' });
          queueStore.createIndex('timestamp', 'timestamp');
          queueStore.createIndex('status', 'status');
        }

        // Files store
        if (!db.objectStoreNames.contains('files')) {
          const fileStore = db.createObjectStore('files', { keyPath: 'id' });
          fileStore.createIndex('timestamp', 'timestamp');
          fileStore.createIndex('synced', 'synced');
        }

        // Voice memos store
        if (!db.objectStoreNames.contains('voiceMemos')) {
          const voiceStore = db.createObjectStore('voiceMemos', { keyPath: 'id' });
          voiceStore.createIndex('timestamp', 'timestamp');
          voiceStore.createIndex('synced', 'synced');
        }
      },
    });
  }

  // Message operations
  async saveMessage(message: Message) {
    await this.ensureDB();
    return this.db!.put('messages', message);
  }

  async getMessages(sessionId: string) {
    await this.ensureDB();
    return this.db!.getAllFromIndex('messages', 'sessionId', sessionId);
  }

  async getUnsyncedMessages() {
    await this.ensureDB();
    const allMessages = await this.db!.getAll('messages');
    return allMessages.filter(msg => !msg.synced);
  }

  // Session operations
  async saveSession(session: Session) {
    await this.ensureDB();
    return this.db!.put('sessions', session);
  }

  async getSession(id: string) {
    await this.ensureDB();
    return this.db!.get('sessions', id);
  }

  async getCurrentSession() {
    await this.ensureDB();
    const sessions = await this.db!.getAllFromIndex('sessions', 'updatedAt');
    return sessions[sessions.length - 1];
  }

  // Queue operations
  async addToQueue(item: Omit<QueueItem, 'id'>) {
    await this.ensureDB();
    const id = `queue-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    await this.db!.put('queue', { ...item, id });
    return id;
  }

  async getQueueItems(status?: QueueItem['status']) {
    await this.ensureDB();
    if (status) {
      return this.db!.getAllFromIndex('queue', 'status', status);
    }
    return this.db!.getAll('queue');
  }

  async updateQueueItem(id: string, updates: Partial<QueueItem>) {
    await this.ensureDB();
    const item = await this.db!.get('queue', id);
    if (item) {
      return this.db!.put('queue', { ...item, ...updates });
    }
  }

  async removeFromQueue(id: string) {
    await this.ensureDB();
    return this.db!.delete('queue', id);
  }

  // File operations
  async saveFile(file: File) {
    await this.ensureDB();
    const id = `file-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    const data = await file.arrayBuffer();
    
    await this.db!.put('files', {
      id,
      name: file.name,
      type: file.type,
      size: file.size,
      data,
      timestamp: Date.now(),
      synced: false,
    });
    return id;
  }

  async getFile(id: string) {
    await this.ensureDB();
    return this.db!.get('files', id);
  }

  async getUnsyncedFiles() {
    await this.ensureDB();
    const allFiles = await this.db!.getAll('files');
    return allFiles.filter(file => !file.synced);
  }

  // Voice memo operations
  async saveVoiceMemo(blob: Blob, duration: number) {
    await this.ensureDB();
    const id = `voice-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    
    await this.db!.put('voiceMemos', {
      id,
      blob,
      duration,
      timestamp: Date.now(),
      synced: false,
    });
    return id;
  }

  async getVoiceMemo(id: string) {
    await this.ensureDB();
    return this.db!.get('voiceMemos', id);
  }

  async updateVoiceMemoTranscription(id: string, transcription: string) {
    await this.ensureDB();
    const memo = await this.db!.get('voiceMemos', id);
    if (memo) {
      return this.db!.put('voiceMemos', { ...memo, transcription });
    }
  }

  async getUnsyncedVoiceMemos() {
    await this.ensureDB();
    const allMemos = await this.db!.getAll('voiceMemos');
    return allMemos.filter(memo => !memo.synced);
  }

  async getAllVoiceMemos() {
    await this.ensureDB();
    return this.db!.getAll('voiceMemos');
  }

  async deleteVoiceMemo(id: string) {
    await this.ensureDB();
    return this.db!.delete('voiceMemos', id);
  }

  // Mark items as synced
  async markFileAsSynced(id: string) {
    await this.ensureDB();
    const file = await this.db!.get('files', id);
    if (file) {
      return this.db!.put('files', { ...file, synced: true });
    }
  }

  async markVoiceMemoAsSynced(id: string) {
    await this.ensureDB();
    const memo = await this.db!.get('voiceMemos', id);
    if (memo) {
      return this.db!.put('voiceMemos', { ...memo, synced: true });
    }
  }

  // Utility methods
  private async ensureDB() {
    if (!this.db) {
      await this.initialize();
    }
  }

  async clearAll() {
    await this.ensureDB();
    const stores = ['messages', 'sessions', 'queue', 'files', 'voiceMemos'];
    
    for (const store of stores) {
      await this.db!.clear(store);
    }
  }

  async getStorageStats() {
    await this.ensureDB();
    
    const messageCount = await this.db!.count('messages');
    const sessionCount = await this.db!.count('sessions');
    const queueCount = await this.db!.count('queue');
    const fileCount = await this.db!.count('files');
    const voiceMemoCount = await this.db!.count('voiceMemos');
    
    return {
      messages: messageCount,
      sessions: sessionCount,
      queuedItems: queueCount,
      files: fileCount,
      voiceMemos: voiceMemoCount,
    };
  }
}

// Export singleton instance
export const offlineStorage = typeof window !== 'undefined' ? new OfflineStorage() : null as unknown as OfflineStorage;

// Export types
export type { Message, Session, QueueItem, FileItem, VoiceMemo };