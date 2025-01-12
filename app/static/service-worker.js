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

// Message handler for token storage
self.addEventListener('message', (event) => {
    if (event.data?.type === 'STORE_AUTH_TOKEN') {
        console.log('[SW] Processing token storage');
        
        caches.open(AUTH_CACHE)
            .then(cache => {
                const response = new Response(JSON.stringify({
                    token: event.data.token,
                    timestamp: new Date().toISOString()
                }));
                return cache.put('auth-token', response);
            })
            .then(() => {
                if (event.ports?.[0]) {
                    event.ports[0].postMessage({ success: true });
                }
            })
            .catch(error => {
                console.error('[SW] Storage error:', error);
                if (event.ports?.[0]) {
                    event.ports[0].postMessage({ success: false, error: error.message });
                }
            });
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
