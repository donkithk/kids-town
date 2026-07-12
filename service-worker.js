/* ============================================
   Kids Town PWA — Service Worker
   Version: 2.1.0
   Scope: /kids/
   ============================================ */

const CACHE_NAME = 'kids-town-v8';
const STATIC_CACHE = 'kids-town-static-v8';

// Files to precache on install
const PRECACHE_URLS = [
  '/kids/',
  '/kids/index.html',
  '/kids/manifest.json',
  '/kids/icon-192.png',
  '/kids/icon-512.png',
  '/kids/icon.svg',
  '/kids/audio.js'
];

// ── Install: precache app shell ──────────────────────────────
self.addEventListener('install', event => {
  console.log('[SW] Installing v2.0.1');
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      return cache.addAll(PRECACHE_URLS);
    }).then(() => {
      return self.skipWaiting();
    })
  );
});

// ── Activate: clean old caches ───────────────────────────────
self.addEventListener('activate', event => {
  console.log('[SW] Activating');
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(name => {
          if (name !== CACHE_NAME && name !== STATIC_CACHE) {
            console.log('[SW] Deleting old cache:', name);
            return caches.delete(name);
          }
        })
      );
    }).then(() => {
      return self.clients.claim();
    })
  );
});

// ── Fetch: caching strategy ──────────────────────────────────
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  const isKidsTown = url.pathname.startsWith('/kids/') || url.pathname === '/kids';
  const isApi = url.pathname.startsWith('/api/') || url.pathname.startsWith('/kids/api/');
  const isStatic =
    url.pathname.match(/\.(png|jpg|jpeg|gif|svg|ico|js|css|woff2?)$/);

  // API calls: network-first with timeout, fallback to cache
  if (isApi) {
    event.respondWith(networkFirstWithTimeout(event.request));
    return;
  }

  // Static assets: cache-first
  if (isStatic) {
    event.respondWith(cacheFirst(event.request));
    return;
  }

  // Navigation / HTML pages: network-first
  if (isKidsTown) {
    event.respondWith(networkFirst(event.request));
    return;
  }

  // Everything else: network-only
  return;
});

// ── Cache-first strategy ─────────────────────────────────────
async function cacheFirst(request) {
  const cached = await caches.match(request);
  if (cached) {
    return cached;
  }
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(STATIC_CACHE);
      cache.put(request, response.clone());
    }
    return response;
  } catch (err) {
    console.warn('[SW] cacheFirst failed:', request.url, err.message);
    return new Response('', { status: 503, statusText: 'Offline' });
  }
}

// ── Network-first strategy ───────────────────────────────────
async function networkFirst(request) {
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(CACHE_NAME);
      cache.put(request, response.clone());
    }
    return response;
  } catch (err) {
    const cached = await caches.match(request);
    if (cached) {
      console.log('[SW] Serving from cache (offline):', request.url);
      return cached;
    }
    console.warn('[SW] networkFirst failed, no cache:', request.url);
    return new Response('', { status: 503, statusText: 'Offline' });
  }
}

// ── Network-first with timeout ───────────────────────────────
async function networkFirstWithTimeout(request) {
  const timeout = 10000; // 10 seconds for mobile

  try {
    const response = await Promise.race([
      fetch(request),
      new Promise((_, reject) =>
        setTimeout(() => reject(new Error('timeout')), timeout)
      )
    ]);
    if (response.ok) {
      const cache = await caches.open(CACHE_NAME);
      cache.put(request, response.clone());
    }
    return response;
  } catch (err) {
    const cached = await caches.match(request);
    if (cached) {
      console.log('[SW] API serving from cache (offline):', request.url);
      return cached;
    }
    // Return a cached response or fallback
    return new Response(
      JSON.stringify({ error: 'offline', message: '請檢查網絡連線' }),
      {
        status: 200,
        headers: { 'Content-Type': 'application/json' }
      }
    );
  }
}
