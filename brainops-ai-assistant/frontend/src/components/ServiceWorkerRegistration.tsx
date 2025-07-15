'use client';

import { useEffect } from 'react';
import toast from 'react-hot-toast';

export default function ServiceWorkerRegistration() {
  useEffect(() => {
    if (typeof window !== 'undefined' && 'serviceWorker' in navigator) {
      // Register service worker
      navigator.serviceWorker
        .register('/service-worker.js')
        .then((registration) => {
          console.log('[SW] Registration successful:', registration.scope);

          // Check for updates periodically
          setInterval(() => {
            registration.update();
          }, 60000); // Check every minute

          // Handle updates
          registration.addEventListener('updatefound', () => {
            const newWorker = registration.installing;
            if (newWorker) {
              newWorker.addEventListener('statechange', () => {
                if (newWorker.state === 'activated') {
                  toast.success('App updated! Refresh for latest version.', {
                    duration: 5000,
                    action: {
                      label: 'Refresh',
                      onClick: () => window.location.reload(),
                    },
                  });
                }
              });
            }
          });
        })
        .catch((error) => {
          console.error('[SW] Registration failed:', error);
        });

      // Handle service worker messages
      navigator.serviceWorker.addEventListener('message', (event) => {
        if (event.data.type === 'REQUEST_QUEUED') {
          console.log('[SW] Request queued for sync:', event.data.data);
        } else if (event.data.type === 'SYNC_STARTED') {
          console.log('[SW] Sync started');
        }
      });

      // Request persistent storage
      if ('storage' in navigator && 'persist' in navigator.storage) {
        navigator.storage.persist().then((granted) => {
          if (granted) {
            console.log('[Storage] Persistent storage granted');
          }
        });
      }

      // Request notification permission for sync updates
      if ('Notification' in window && Notification.permission === 'default') {
        Notification.requestPermission();
      }
    }
  }, []);

  return null;
}