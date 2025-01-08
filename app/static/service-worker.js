const CACHE_NAME = 'walking-bus-cache-v1';
const STATIC_CACHE = 'walking-bus-static-v1';
const DATA_CACHE = 'walking-bus-data-v1';
const AUTH_CACHE = 'walking-bus-auth-v1';

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

// Handle messages from the client
self.addEventListener('message', (event) => {
 console.log('[SW] Message received:', event.data?.type);
 
 if (event.data?.type === 'STORE_AUTH_TOKEN') {
     console.log('[SW] Processing token storage');
     
     caches.open(AUTH_CACHE)
         .then(cache => {
             console.log('[SW] Cache opened');
             const response = new Response(JSON.stringify({
                 token: event.data.token,
                 timestamp: new Date().toISOString()
             }));
             return cache.put('auth-token', response);
         })
         .then(() => {
             console.log('[SW] Token stored successfully');
             if (event.ports && event.ports[0]) {
                 event.ports[0].postMessage({ success: true });
             }
         })
         .catch(error => {
             console.error('[SW] Storage error:', error);
             if (event.ports && event.ports[0]) {
                 event.ports[0].postMessage({ success: false, error: error.message });
             }
         });
 }
});

// Installation des Service Workers
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

// Activate event to clean up old caches
// Add storage persistence check
self.addEventListener('activate', (event) => {
 console.log('[SW] Activate event triggered');
 event.waitUntil(
     Promise.all([
         self.clients.claim().then(() => console.log('[SW] Clients claimed')),
         caches.keys().then(cacheNames => {
             console.log('[SW] Checking caches:', cacheNames);
             return Promise.all(
                 cacheNames.map(cacheName => {
                     if (![STATIC_CACHE, DATA_CACHE, AUTH_CACHE].includes(cacheName)) {
                         console.log('[SW] Deleting old cache:', cacheName);
                         return caches.delete(cacheName);
                     }
                 })
             );
         })
     ]).then(() => console.log('[SW] Activation complete'))
 );
});


// Fetch event handling with authentication
self.addEventListener('fetch', (event) => {
    // Handle API requests and authenticated routes
    if (event.request.url.includes('/api/') || event.request.url.endsWith('/')) {
        event.respondWith(
            caches.open(AUTH_CACHE)
                .then(cache => cache.match('auth-token'))
                .then(tokenResponse => {
                    if (tokenResponse) {
                        return tokenResponse.json().then(data => {
                            const authenticatedRequest = new Request(event.request.url, {
                                method: event.request.method,
                                headers: {
                                    ...Object.fromEntries(event.request.headers),
                                    'Authorization': `Bearer ${data.token}`
                                },
                                mode: 'cors',
                                credentials: 'include'
                            });
                            
                            return fetch(authenticatedRequest)
                                .then(response => {
                                    if (!response.ok) throw new Error('Network response was not ok');
                                    const clonedResponse = response.clone();
                                    if (event.request.url.includes('/api/')) {
                                        caches.open(DATA_CACHE).then(cache => {
                                            cache.put(event.request, clonedResponse);
                                        });
                                    }
                                    return response;
                                })
                                .catch(() => caches.match(event.request));
                        });
                    }
                    return fetch(event.request);
                })
                .catch(() => fetch(event.request))
        );
        return;
    }

    // Handle static assets
    if (URLS_TO_CACHE.some(url => event.request.url.includes(url))) {
        event.respondWith(
            caches.match(event.request)
                .then(response => response || fetch(event.request))
        );
        return;
    }

    // Handle all other requests
    event.respondWith(
        fetch(event.request)
            .catch(() => {
                return caches.match(event.request)
                    .then(response => {
                        if (response) return response;
                        if (event.request.mode === 'navigate') {
                            return caches.match('/');
                        }
                        return new Response('Not found', {
                            status: 404,
                            statusText: 'Not found'
                        });
                    });
            })
    );
});

// Background sync for offline functionality
self.addEventListener('sync', (event) => {
    if (event.tag === 'sync-auth') {
        event.waitUntil(
            caches.open(AUTH_CACHE)
                .then(cache => cache.match('auth-token'))
                .then(response => {
                    if (response) {
                        return response.json();
                    }
                    return null;
                })
                .then(authData => {
                    if (authData) {
                        return fetch('/validate-auth', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                                'Authorization': `Bearer ${authData.token}`
                            },
                            body: JSON.stringify(authData)
                        });
                    }
                })
        );
    }
});
