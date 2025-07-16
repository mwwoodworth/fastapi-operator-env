export function registerServiceWorker() {
  if (typeof window !== 'undefined' && 'serviceWorker' in navigator && window.workbox) {
    window.workbox.register();
  }
}

export async function checkForUpdates() {
  if (typeof window !== 'undefined' && 'serviceWorker' in navigator && window.workbox) {
    const registration = await navigator.serviceWorker.ready;
    registration.update();
  }
}

export function isPWAInstalled(): boolean {
  if (typeof window === 'undefined') return false;
  
  // Check for display mode
  const isStandalone = window.matchMedia('(display-mode: standalone)').matches;
  
  // Check for iOS
  const isInStandaloneMode = ('standalone' in window.navigator) && (window.navigator as { standalone?: boolean }).standalone;
  
  return isStandalone || (isInStandaloneMode ?? false);
}

export interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{
    outcome: 'accepted' | 'dismissed';
    platform: string;
  }>;
}

let deferredPrompt: BeforeInstallPromptEvent | null = null;

export function initPWAPrompt() {
  if (typeof window === 'undefined') return;
  
  window.addEventListener('beforeinstallprompt', (e: Event) => {
    e.preventDefault();
    deferredPrompt = e as BeforeInstallPromptEvent;
  });
}

export async function showInstallPrompt(): Promise<boolean> {
  if (!deferredPrompt) return false;
  
  deferredPrompt.prompt();
  const { outcome } = await deferredPrompt.userChoice;
  deferredPrompt = null;
  
  return outcome === 'accepted';
}

export function canShowInstallPrompt(): boolean {
  return deferredPrompt !== null;
}