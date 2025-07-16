'use client';

import { useEffect } from 'react';
import { registerServiceWorker, initPWAPrompt } from '@/lib/pwa';

export function PWAInit() {
  useEffect(() => {
    registerServiceWorker();
    initPWAPrompt();
  }, []);

  return null;
}