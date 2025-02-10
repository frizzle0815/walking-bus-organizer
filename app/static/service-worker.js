const STATIC_CACHE = 'walking-bus-static-v1';
const DATA_CACHE = 'walking-bus-data-v1';
const AUTH_CACHE = 'walking-bus-auth-v1';

const AUTH_TOKEN_CACHE_KEY = 'auth-token';

const CACHE_VERSION = 'v6'; // Increment this when you update your service worker

const URLS_TO_CACHE = [
    '/',
    '/static/manifest.json',
    '/static/icons/icon-192x192.png',
    '/static/icons/icon-512x512.png',
    'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css',
    'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js',
    'https://cdn.jsdelivr.net/npm/axios/dist/axios.min.js',
    'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css'
];

// Installation handler
self.addEventListener('install', (event) => {
    console.log('[SW] Install event triggered');
    event.waitUntil(
        Promise.all([
            caches.open(STATIC_CACHE).then(cache => {
                console.log('[SW] Caching static resources');
                return cache.addAll(URLS_TO_CACHE);
            }),
            caches.open(DATA_CACHE).then(() => console.log('[SW] Data cache created')),
            caches.open(AUTH_CACHE).then(() => console.log('[SW] Auth cache created'))
        ]).then(() => console.log('[SW] Installation complete'))
    );
});

self.addEventListener('activate', (event) => {
 event.waitUntil(
     // Get all cache keys
     caches.keys().then(cacheNames => {
         return Promise.all(
             cacheNames.map(cacheName => {
                 // If cache name doesn't include current version, delete it
                 if (!cacheName.includes(CACHE_VERSION)) {
                     return caches.delete(cacheName);
                 }
             })
         );
     }).then(() => {
         // Claim control immediately
         return self.clients.claim();
     })
 );
});

// Message handler for token storage and removal
self.addEventListener('message', (event) => {
    console.log('[SW] Received message event:', event.data?.type);

    if (event.data?.type === 'STORE_AUTH_TOKEN') {
        console.log('[SW] Processing token storage');
        
        caches.open(AUTH_CACHE)
            .then(cache => {
                console.log('[SW] Cache opened successfully');
                const response = new Response(JSON.stringify({
                    token: event.data.token,
                    timestamp: new Date().toISOString()
                }));
                return cache.put(AUTH_TOKEN_CACHE_KEY, response);
            })
            .then(() => {
                console.log('[SW] Token stored successfully');
                if (event.ports?.[0]) {
                    event.ports[0].postMessage({ success: true });
                    console.log('[SW] Success message sent back');
                }
            })
            .catch(error => {
                console.error('[SW] Storage error:', error);
                if (event.ports?.[0]) {
                    event.ports[0].postMessage({
                        success: false,
                        error: error.message
                    });
                    console.log('[SW] Error message sent back');
                }
            });

    } else if (event.data?.type === 'CLEAR_AUTH_TOKEN') {
        console.log('[SW] Starting cache clearing');
        
        // Log existing caches before deletion
        caches.keys().then(keys => {
            console.log('[SW] Existing caches before deletion:', keys);
        });

        Promise.all([
            caches.open(STATIC_CACHE).then(cache => cache.keys().then(keys => Promise.all(keys.map(key => cache.delete(key))))),
            caches.open(DATA_CACHE).then(cache => cache.keys().then(keys => Promise.all(keys.map(key => cache.delete(key))))),
            caches.open(AUTH_CACHE).then(cache => cache.keys().then(keys => Promise.all(keys.map(key => cache.delete(key)))))
        ]).then(() => {
            console.log('[SW] All caches deleted successfully');
            if (event.ports?.[0]) {
                event.ports[0].postMessage({ success: true });
                console.log('[SW] Success message sent back');
            }
            console.log('[SW] Updating service worker registration');
            self.registration.update();
            
            // Verify cache deletion
            return caches.keys();
        }).then(remainingKeys => {
            console.log('[SW] Remaining caches after deletion:', remainingKeys);
        }).catch(error => {
            console.error('[SW] Clear error:', error);
            if (event.ports?.[0]) {
                event.ports[0].postMessage({
                    success: false,
                    error: error.message
                });
                console.log('[SW] Error message sent back');
            }
        });
    } else {
        console.log('[SW] Unknown message type received:', event.data?.type);
    }
});

// Push message handler
self.addEventListener('push', (event) => {
    console.log('[PUSH][START] Received push event', event);
    
    let payload;
    try {
        payload = event.data.json();
        console.log('[PUSH][PAYLOAD] Successfully parsed payload:', payload);
    } catch (e) {
        console.log('[PUSH][PARSE_ERROR] Failed to parse JSON, using text:', event.data.text());
        payload = {
            title: 'Walking Bus',
            body: event.data.text()
        };
    }
    
    const options = {
        body: payload.body,
        icon: '/static/icons/icon-192x192.png',
        badge: '/static/icons/icon-192x192.png',
        data: payload.data || {},
        tag: payload.tag,
        renotify: true,
        requireInteraction: payload.requireInteraction,
        actions: payload.actions
    };
    
    console.log('[PUSH][OPTIONS] Notification options:', options);

    event.waitUntil(
        self.registration.showNotification(payload.title, options)
            .then(() => console.log('[PUSH][SUCCESS] Notification shown successfully'))
            .catch(error => console.error('[PUSH][ERROR] Failed to show notification:', error))
    );
});

self.addEventListener('notificationclick', (event) => {
    event.notification.close();
    
    if (event.action) {
        // Handle specific actions
        console.log('Action clicked:', event.action);
    } else {
        // Default click behavior
        event.waitUntil(
            clients.matchAll({type: 'window'}).then(windowClients => {
                if (windowClients.length > 0) {
                    windowClients[0].focus();
                } else {
                    clients.openWindow('/');
                }
            })
        );
    }
});

// Modern static asset handling
async function handleStaticAsset(request) {
    const cache = await caches.open(STATIC_CACHE);
    const cachedResponse = await cache.match(request);
    
    if (cachedResponse) {
        return cachedResponse;
    }
    
    const networkResponse = await fetch(request);
    if (URLS_TO_CACHE.some(url => request.url.includes(url))) {
        await cache.put(request, networkResponse.clone());
    }
    return networkResponse;
}

// Fetch handler
self.addEventListener('fetch', event => {
    if (URLS_TO_CACHE.some(url => event.request.url.includes(url))) {
        event.respondWith(handleStaticAsset(event.request));
    }
});
