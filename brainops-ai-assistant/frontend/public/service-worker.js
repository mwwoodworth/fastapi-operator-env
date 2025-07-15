// BrainOps Assistant Service Worker - Offline Resilience
const CACHE_NAME = 'brainops-assistant-v1';
const STATIC_CACHE_NAME = 'brainops-static-v1';
const DYNAMIC_CACHE_NAME = 'brainops-dynamic-v1';

// Assets to cache for offline use
const STATIC_ASSETS = [
  '/',
  '/offline.html',
  '/manifest.json',
  '/favicon.ico',
  '/_next/static/css/app/globals.css',
];

// Install event - cache static assets
self.addEventListener('install', (event) => {
  console.log('[SW] Installing service worker...');
  event.waitUntil(
    caches.open(STATIC_CACHE_NAME).then((cache) => {
      console.log('[SW] Caching static assets');
      return cache.addAll(STATIC_ASSETS.filter(asset => !asset.includes('_next')));
    })
  );
  self.skipWaiting();
});

// Activate event - clean up old caches
self.addEventListener('activate', (event) => {
  console.log('[SW] Activating service worker...');
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames
          .filter((cacheName) => cacheName !== STATIC_CACHE_NAME && cacheName !== DYNAMIC_CACHE_NAME)
          .map((cacheName) => caches.delete(cacheName))
      );
    })
  );
  self.clients.claim();
});

// Fetch event - serve from cache when offline
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Skip non-GET requests
  if (request.method !== 'GET') {
    return;
  }

  // Handle API requests differently
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(handleAPIRequest(request));
    return;
  }

  // Network first, fallback to cache strategy for dynamic content
  if (request.headers.get('accept')?.includes('text/html')) {
    event.respondWith(
      fetch(request)
        .then((response) => {
          const responseToCache = response.clone();
          caches.open(DYNAMIC_CACHE_NAME).then((cache) => {
            cache.put(request, responseToCache);
          });
          return response;
        })
        .catch(() => {
          return caches.match(request).then((response) => {
            return response || caches.match('/offline.html');
          });
        })
    );
    return;
  }

  // Cache first strategy for static assets
  event.respondWith(
    caches.match(request).then((response) => {
      return response || fetch(request).then((response) => {
        return caches.open(DYNAMIC_CACHE_NAME).then((cache) => {
          cache.put(request, response.clone());
          return response;
        });
      });
    })
  );
});

// Handle API requests with offline queue
async function handleAPIRequest(request) {
  try {
    const response = await fetch(request);
    return response;
  } catch (error) {
    // Queue the request for later
    const requestData = {
      url: request.url,
      method: request.method,
      headers: Object.fromEntries(request.headers.entries()),
      body: await request.text(),
      timestamp: Date.now()
    };

    // Send message to client about queued request
    const clients = await self.clients.matchAll();
    clients.forEach(client => {
      client.postMessage({
        type: 'REQUEST_QUEUED',
        data: requestData
      });
    });

    // Return a synthetic response
    return new Response(
      JSON.stringify({
        success: false,
        offline: true,
        queued: true,
        message: 'Request queued for sync when online'
      }),
      {
        status: 503,
        headers: { 'Content-Type': 'application/json' }
      }
    );
  }
}

// Background sync for queued requests
self.addEventListener('sync', (event) => {
  if (event.tag === 'sync-queue') {
    event.waitUntil(syncQueuedRequests());
  }
});

async function syncQueuedRequests() {
  const clients = await self.clients.matchAll();
  clients.forEach(client => {
    client.postMessage({
      type: 'SYNC_STARTED'
    });
  });
}

// Listen for messages from the client
self.addEventListener('message', (event) => {
  if (event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});