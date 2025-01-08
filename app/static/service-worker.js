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

// Installation des Service Workers
self.addEventListener('install', (event) => {
    event.waitUntil(
        Promise.all([
            caches.open(STATIC_CACHE).then(cache => cache.addAll(URLS_TO_CACHE)),
            caches.open(DATA_CACHE),
            caches.open(AUTH_CACHE)
        ])
    );
});

// Activate event to clean up old caches
self.addEventListener('activate', (event) => {
    event.waitUntil(
        Promise.all([
            self.clients.claim(),
            caches.keys().then(cacheNames => {
                return Promise.all(
                    cacheNames.map(cacheName => {
                        if (![STATIC_CACHE, DATA_CACHE, AUTH_CACHE].includes(cacheName)) {
                            return caches.delete(cacheName);
                        }
                    })
                );
            })
        ])
    );
});

// Fetch event handling with authentication
self.addEventListener('fetch', (event) => {
    // Handle API requests
    if (event.request.url.includes('/api/')) {
        event.respondWith(
            fetch(event.request)
                .then(response => {
                    if (!response.ok) throw new Error('Network response was not ok');
                    const clonedResponse = response.clone();
                    caches.open(DATA_CACHE).then(cache => {
                        cache.put(event.request, clonedResponse);
                    });
                    return response;
                })
                .catch(() => {
                    return caches.match(event.request);
                })
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
                .then(cache => cache.match('auth-data'))
                .then(response => {
                    if (response) {
                        return response.json();
                    }
                    return null;
                })
                .then(authData => {
                    if (authData) {
                        // Attempt to revalidate authentication
                        return fetch('/validate-auth', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json'
                            },
                            body: JSON.stringify(authData)
                        });
                    }
                })
        );
    }
});
