const CACHE_NAME = 'walking-bus-cache-v1';
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

// Cache Namen für verschiedene Ressourcen
const STATIC_CACHE = 'walking-bus-static-v1';
const DATA_CACHE = 'walking-bus-data-v1';

// Installation des Service Workers
self.addEventListener('install', (event) => {
 event.waitUntil(
     Promise.all([
         caches.open(STATIC_CACHE),
         caches.open(DATA_CACHE)
     ])
 );
});

// Abfangen von Fetch-Requests
self.addEventListener('fetch', (event) => {
 if (event.request.url.includes('/api/')) {
     event.respondWith(
         fetch(event.request)
             .then(response => {
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
 }
});