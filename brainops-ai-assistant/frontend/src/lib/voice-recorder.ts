// Voice Recording Utility for Offline Voice Memos
import { offlineStorage } from './offline-storage';
import { offlineQueue } from './offline-queue';

export class VoiceRecorder {
  private mediaRecorder: MediaRecorder | null = null;
  private chunks: Blob[] = [];
  private stream: MediaStream | null = null;
  private startTime: number = 0;
  private isRecording = false;
  private recordingListeners: ((recording: boolean) => void)[] = [];

  constructor() {
    this.checkBrowserSupport();
  }

  // Check browser support
  private checkBrowserSupport() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      console.error('[VoiceRecorder] getUserMedia not supported');
      throw new Error('Voice recording not supported in this browser');
    }
  }

  // Initialize media recorder
  private async initializeRecorder() {
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      
      // Choose the best available codec
      const options = this.getRecorderOptions();
      this.mediaRecorder = new MediaRecorder(this.stream, options);

      this.mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          this.chunks.push(event.data);
        }
      };

      this.mediaRecorder.onstop = async () => {
        await this.handleRecordingComplete();
      };

      this.mediaRecorder.onerror = (event) => {
        console.error('[VoiceRecorder] Recording error:', event);
        this.stopRecording();
      };

    } catch (error) {
      console.error('[VoiceRecorder] Failed to initialize:', error);
      throw error;
    }
  }

  // Get optimal recorder options
  private getRecorderOptions(): MediaRecorderOptions {
    const mimeTypes = [
      'audio/webm;codecs=opus',
      'audio/webm',
      'audio/ogg;codecs=opus',
      'audio/mp4',
    ];

    for (const mimeType of mimeTypes) {
      if (MediaRecorder.isTypeSupported(mimeType)) {
        return { mimeType };
      }
    }

    return {}; // Use browser default
  }

  // Start recording
  async startRecording(): Promise<void> {
    if (this.isRecording) {
      console.warn('[VoiceRecorder] Already recording');
      return;
    }

    try {
      await this.initializeRecorder();
      
      if (!this.mediaRecorder) {
        throw new Error('Failed to initialize media recorder');
      }

      this.chunks = [];
      this.startTime = Date.now();
      this.mediaRecorder.start();
      this.isRecording = true;
      this.notifyListeners(true);

      console.log('[VoiceRecorder] Recording started');
    } catch (error) {
      console.error('[VoiceRecorder] Failed to start recording:', error);
      throw error;
    }
  }

  // Stop recording
  async stopRecording(): Promise<string | null> {
    if (!this.isRecording || !this.mediaRecorder) {
      console.warn('[VoiceRecorder] Not recording');
      return null;
    }

    return new Promise((resolve) => {
      // Set up one-time listener for completion
      const originalHandler = this.mediaRecorder!.onstop;
      this.mediaRecorder!.onstop = async () => {
        if (originalHandler) {
          await originalHandler.call(this.mediaRecorder, new Event('stop'));
        }
        const memoId = await this.handleRecordingComplete();
        resolve(memoId);
      };

      this.mediaRecorder.stop();
      this.isRecording = false;
      this.notifyListeners(false);

      // Stop all tracks
      if (this.stream) {
        this.stream.getTracks().forEach(track => track.stop());
        this.stream = null;
      }

      console.log('[VoiceRecorder] Recording stopped');
    });
  }

  // Handle recording completion
  private async handleRecordingComplete(): Promise<string | null> {
    if (this.chunks.length === 0) {
      console.warn('[VoiceRecorder] No audio data recorded');
      return null;
    }

    try {
      const duration = (Date.now() - this.startTime) / 1000; // in seconds
      const blob = new Blob(this.chunks, { 
        type: this.mediaRecorder?.mimeType || 'audio/webm' 
      });

      // Save to IndexedDB
      const memoId = await offlineStorage.saveVoiceMemo(blob, duration);
      console.log('[VoiceRecorder] Voice memo saved:', memoId);

      // Queue for transcription if online
      if (navigator.onLine) {
        await offlineQueue.enqueue({
          type: 'voice',
          payload: { voiceId: memoId },
        });
      } else {
        // Will be transcribed when back online
        console.log('[VoiceRecorder] Offline - memo will be transcribed when online');
      }

      return memoId;
    } catch (error) {
      console.error('[VoiceRecorder] Failed to save recording:', error);
      return null;
    }
  }

  // Local transcription using Web Speech API (if available)
  async transcribeLocally(audioBlob: Blob): Promise<string | null> {
    if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
      console.log('[VoiceRecorder] Speech recognition not available');
      return null;
    }

    try {
      // Convert blob to audio element for playback
      const audioUrl = URL.createObjectURL(audioBlob);
      const audio = new Audio(audioUrl);
      
      // Create speech recognition instance
      const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
      const recognition = new SpeechRecognition();
      
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.lang = 'en-US';

      return new Promise((resolve, reject) => {
        let finalTranscript = '';

        recognition.onresult = (event: any) => {
          for (let i = event.resultIndex; i < event.results.length; i++) {
            const transcript = event.results[i][0].transcript;
            if (event.results[i].isFinal) {
              finalTranscript += transcript + ' ';
            }
          }
        };

        recognition.onerror = (event: any) => {
          console.error('[VoiceRecorder] Recognition error:', event.error);
          reject(event.error);
        };

        recognition.onend = () => {
          resolve(finalTranscript.trim());
          URL.revokeObjectURL(audioUrl);
        };

        // Start recognition
        recognition.start();
        
        // Play audio (required for some browsers)
        audio.play().catch(console.error);
        
        // Stop recognition when audio ends
        audio.onended = () => {
          recognition.stop();
        };
      });
    } catch (error) {
      console.error('[VoiceRecorder] Local transcription failed:', error);
      return null;
    }
  }

  // Get all voice memos
  async getVoiceMemos() {
    return offlineStorage.db?.getAll('voiceMemos');
  }

  // Delete voice memo
  async deleteVoiceMemo(id: string) {
    return offlineStorage.db?.delete('voiceMemos', id);
  }

  // Add recording status listener
  onRecordingChange(callback: (recording: boolean) => void) {
    this.recordingListeners.push(callback);
  }

  // Notify listeners of recording status
  private notifyListeners(recording: boolean) {
    this.recordingListeners.forEach(cb => cb(recording));
  }

  // Get recording status
  getIsRecording(): boolean {
    return this.isRecording;
  }

  // Cleanup
  destroy() {
    if (this.isRecording) {
      this.stopRecording();
    }
  }
}

// Export singleton instance
export const voiceRecorder = new VoiceRecorder();