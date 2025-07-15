// IndexedDB Storage for Offline Resilience
import { openDB, DBSchema, IDBPDatabase } from 'idb';

// Database schema
interface BrainOpsDB extends DBSchema {
  messages: {
    key: string;
    value: {
      id: string;
      content: string;
      role: 'user' | 'assistant' | 'system';
      timestamp: number;
      synced: boolean;
      sessionId: string;
      metadata?: any;
    };
  };
  
  sessions: {
    key: string;
    value: {
      id: string;
      createdAt: number;
      updatedAt: number;
      context: any;
      online: boolean;
    };
  };
  
  queue: {
    key: string;
    value: {
      id: string;
      type: 'message' | 'file' | 'voice' | 'task';
      payload: any;
      timestamp: number;
      retries: number;
      status: 'pending' | 'syncing' | 'failed';
    };
  };
  
  files: {
    key: string;
    value: {
      id: string;
      name: string;
      type: string;
      size: number;
      data: ArrayBuffer;
      timestamp: number;
      synced: boolean;
    };
  };
  
  voiceMemos: {
    key: string;
    value: {
      id: string;
      blob: Blob;
      duration: number;
      timestamp: number;
      transcription?: string;
      synced: boolean;
    };
  };
}

class OfflineStorage {
  private db: IDBPDatabase<BrainOpsDB> | null = null;
  private readonly DB_NAME = 'BrainOpsAssistant';
  private readonly DB_VERSION = 1;

  async initialize() {
    if (this.db) return;

    this.db = await openDB<BrainOpsDB>(this.DB_NAME, this.DB_VERSION, {
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
  async saveMessage(message: BrainOpsDB['messages']['value']) {
    await this.ensureDB();
    return this.db!.put('messages', message);
  }

  async getMessages(sessionId: string) {
    await this.ensureDB();
    return this.db!.getAllFromIndex('messages', 'sessionId', sessionId);
  }

  async getUnsyncedMessages() {
    await this.ensureDB();
    return this.db!.getAllFromIndex('messages', 'synced', false);
  }

  // Session operations
  async saveSession(session: BrainOpsDB['sessions']['value']) {
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
  async addToQueue(item: Omit<BrainOpsDB['queue']['value'], 'id'>) {
    await this.ensureDB();
    const id = `queue-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    return this.db!.put('queue', { ...item, id });
  }

  async getQueueItems(status?: BrainOpsDB['queue']['value']['status']) {
    await this.ensureDB();
    if (status) {
      return this.db!.getAllFromIndex('queue', 'status', status);
    }
    return this.db!.getAll('queue');
  }

  async updateQueueItem(id: string, updates: Partial<BrainOpsDB['queue']['value']>) {
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
    
    return this.db!.put('files', {
      id,
      name: file.name,
      type: file.type,
      size: file.size,
      data,
      timestamp: Date.now(),
      synced: false,
    });
  }

  async getFile(id: string) {
    await this.ensureDB();
    return this.db!.get('files', id);
  }

  async getUnsyncedFiles() {
    await this.ensureDB();
    return this.db!.getAllFromIndex('files', 'synced', false);
  }

  // Voice memo operations
  async saveVoiceMemo(blob: Blob, duration: number) {
    await this.ensureDB();
    const id = `voice-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    
    return this.db!.put('voiceMemos', {
      id,
      blob,
      duration,
      timestamp: Date.now(),
      synced: false,
    });
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
    return this.db!.getAllFromIndex('voiceMemos', 'synced', false);
  }

  // Utility methods
  private async ensureDB() {
    if (!this.db) {
      await this.initialize();
    }
  }

  async clearAll() {
    await this.ensureDB();
    const stores: (keyof BrainOpsDB)[] = ['messages', 'sessions', 'queue', 'files', 'voiceMemos'];
    
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
export const offlineStorage = new OfflineStorage();

// Export types
export type { BrainOpsDB };