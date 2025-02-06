importScripts('https://cdn.jsdelivr.net/npm/idb@7/build/umd.js');
const { openDB } = idb;

const CACHE_VERSION = 'v5'; // Increment this when you update your service worker

const STATIC_CACHE = 'walking-bus-static-v1';
const DATA_CACHE = 'walking-bus-data-v1';
const AUTH_CACHE = `walking-bus-auth-v5`;
const NOTIFICATION_CACHE = 'walking-bus-notifications-v1';
const SCHEDULE_DB_NAME = 'walking-bus-schedules';
const SCHEDULE_STORE_NAME = 'notification-schedules';

const AUTH_TOKEN_CACHE_KEY = 'auth-token';

const URLS_TO_CACHE = [
    '/',
    '/static/manifest.json',
    '/static/icons/icon-192x192.png',
    '/static/icons/icon-512x512.png',
    'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css',
    'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js',
    'https://cdn.jsdelivr.net/npm/axios/dist/axios.min.js',
    'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css',
    'https://cdn.jsdelivr.net/npm/idb@7/build/umd.js'
];

// Installation handler
self.addEventListener('install', async (event) => {
    console.log('[SW] Install event triggered');

    // Log registration info using service worker context
    console.log('[SW] Registration scope:', self.registration.scope);
    console.log('[SW] Registration state:', self.registration.active?.state || 'installing');

    // Force waiting service worker to become active
    self.skipWaiting();

    event.waitUntil(
        Promise.all([
            // Static cache initialization with detailed logging
            caches.open(STATIC_CACHE).then(cache => {
                console.log('[SW] Static cache created');
                return cache.addAll(URLS_TO_CACHE).then(() => {
                    console.log('[SW] Static resources cached');
                });
            }),

            // Data cache initialization
            caches.open(DATA_CACHE).then(cache => {
                console.log('[SW] Data cache created');
                return cache;
            }),

            // Auth cache initialization
            caches.open(AUTH_CACHE).then(cache => {
                console.log('[SW] Auth cache created');
                return cache;
            }),

            // Notification cache initialization
            caches.open(NOTIFICATION_CACHE).then(cache => {
                console.log('[SW] Notification cache created');
                return cache;
            }),

            // IndexedDB initialization
            initializeScheduleDB()
        ]).then(() => {
            console.log('[SW] All caches initialized successfully');
        }).catch(error => {
            console.error('[SW] Cache initialization failed:', error);
            throw error; // Re-throw to ensure installation fails on error
        })
    );
});



// Initialize IndexedDB for notification schedules
async function initializeScheduleDB() {
    try {
        const db = await openDB(SCHEDULE_DB_NAME, 1, {
            upgrade(db) {
                if (!db.objectStoreNames.contains(SCHEDULE_STORE_NAME)) {
                    db.createObjectStore(SCHEDULE_STORE_NAME, { keyPath: 'id' });
                }
            }
        });
        console.log('[SW][DB] Database initialized successfully');
        return db;
    } catch (error) {
        console.error('[SW][DB] Database initialization failed:', error);
        throw error;
    }
}


// Handle notification scheduling
async function scheduleNotification(participantData) {
    const { participantId, scheduleTime, busTime } = participantData;
    
    // Create unique ID for this notification
    const notificationId = `notification-${participantId}-${busTime}`;
    
    // Store schedule in IndexedDB
    const db = await openDB(SCHEDULE_DB_NAME);
    await db.put(SCHEDULE_STORE_NAME, {
        id: notificationId,
        participantId,
        scheduleTime,
        busTime,
        processed: false
    });
}


// Check for pending notifications every minute
setInterval(async () => {
    if (Notification.permission === 'granted') {
        const now = new Date();
        const db = await openDB(SCHEDULE_DB_NAME);
        const pending = await db.getAll(SCHEDULE_STORE_NAME);
        
        for (const notification of pending) {
            if (!notification.processed && new Date(notification.scheduleTime) <= now) {
                await showParticipantNotification(notification);
                
                // Mark as processed
                notification.processed = true;
                await db.put(SCHEDULE_STORE_NAME, notification);
            }
        }
    }
}, 60000);


// Show notification with participant status
async function showParticipantNotification(notificationData) {
    try {
        const response = await fetch(`/api/notifications/participant-status/${notificationData.participantId}`);
        const data = await response.json();
        
        return self.registration.showNotification('Walking Bus Erinnerung', {
            body: `${data.participantName} ist für heute ${data.status ? 'angemeldet' : 'abgemeldet'}`,
            icon: '/static/icons/icon-192x192.png',
            badge: '/static/icons/icon-192x192.png',
            tag: notificationData.id,
            data: {
                participantId: notificationData.participantId,
                url: '/notifications'
            },
            actions: [
                {
                    action: 'toggle-status',
                    title: data.status ? 'Abmelden' : 'Anmelden'
                }
            ]
        });
    } catch (error) {
        console.error('Error showing notification:', error);
    }
}


async function syncNotificationSchedules() {
    console.log('[SW] Starting notification schedule sync');
    try {
        // Get auth token from cache for authenticated request
        const cache = await caches.open(AUTH_CACHE);
        const tokenResponse = await cache.match(AUTH_TOKEN_CACHE_KEY);
        if (!tokenResponse) {
            console.log('[SW] No auth token found, skipping sync');
            return;
        }
        const tokenData = await tokenResponse.json();
        
        // Fetch new schedules
        const response = await fetch('/api/notifications/schedules', {
            headers: {
                'Authorization': `Bearer ${tokenData.token}`
            }
        });
        const data = await response.json();
        
        // Update IndexedDB
        const db = await openDB(SCHEDULE_DB_NAME);
        const tx = db.transaction(SCHEDULE_STORE_NAME, 'readwrite');
        const store = tx.objectStore(SCHEDULE_STORE_NAME);
        
        // Clear old unprocessed schedules
        await store.clear();
        
        // Store new schedules
        for (const schedule of data.schedules) {
            await scheduleNotification(schedule);
        }
        
        console.log('[SW] Notification schedules synchronized successfully');
    } catch (error) {
        console.error('[SW] Schedule sync error:', error);
    }
}


// Handle notification clicks
self.addEventListener('notificationclick', async (event) => {
    event.notification.close();
    
    if (event.action === 'toggle-status') {
        try {
            await fetch(`/api/participation/${event.notification.data.participantId}`, {
                method: 'PATCH'
            });
        } catch (error) {
            console.error('Error toggling status:', error);
        }
    }
    
    // Open app on notification click
    const windowClients = await clients.matchAll({
        type: 'window',
        includeUncontrolled: true
    });
    
    if (windowClients.length > 0) {
        windowClients[0].focus();
    } else {
        clients.openWindow('/notifications');
    }
});


self.addEventListener('activate', (event) => {
    console.log('[SW][ACTIVATE] Service Worker activating');
    
    event.waitUntil(
        Promise.all([
            // Verbessertes Cache Management
            caches.keys().then(async cacheNames => {
                console.log('[SW][CACHE] Current caches:', cacheNames);
                return Promise.all(
                    cacheNames.map(cacheName => {
                        // Lösche ALLE alten Auth Caches die nicht zur aktuellen Version gehören
                        if (cacheName.includes('walking-bus-auth') && cacheName !== AUTH_CACHE) {
                            console.log('[SW][CACHE] Deleting old auth cache:', cacheName);
                            return caches.delete(cacheName);
                        }
                        // Lösche andere outdated caches
                        if (!cacheName.includes(CACHE_VERSION)) {
                            console.log('[SW][CACHE] Deleting outdated cache:', cacheName);
                            return caches.delete(cacheName);
                        }
                        console.log('[SW][CACHE] Keeping cache:', cacheName);
                    })
                );
            }),

            // Auth Cache Überprüfung
            checkAuthCache().then(token => {
                console.log('[SW][AUTH] Auth cache status during activation:', 
                    token ? 'Token present' : 'No token found');
            }),

            // Notification Sync Setup
            (async () => {
                console.log('[SW][NOTIFY] Setting up notification sync');
                try {
                    await syncNotificationSchedules();
                    
                    if ('periodicSync' in self.registration && 
                        Notification.permission === 'granted') {
                        try {
                            await self.registration.periodicSync.register('sync-notifications', {
                                minInterval: 24 * 60 * 60 * 1000 // 24 Stunden
                            });
                            console.log('[SW][NOTIFY] Periodic sync registered successfully');
                        } catch (error) {
                            console.log('[SW][NOTIFY] Periodic sync registration failed:', error.message);
                        }
                    } else {
                        console.log('[SW][NOTIFY] Periodic sync not available or notifications not permitted');
                    }
                } catch (error) {
                    console.log('[SW][NOTIFY] Initial sync failed:', error.message);
                }
            })(),

            // Client Control übernehmen
            self.clients.claim().then(() => {
                console.log('[SW][CLIENTS] Service Worker claimed clients');
            })
        ]).then(() => {
            console.log('[SW][ACTIVATE] Service Worker activation complete');
        })
    );
});

// Helper Funktion für Auth Cache Überprüfung
async function checkAuthCache() {
    const cache = await caches.open(AUTH_CACHE);
    const token = await cache.match(AUTH_TOKEN_CACHE_KEY);
    return token;
}



// Handle periodic sync events
self.addEventListener('periodicsync', (event) => {
    if (event.tag === 'sync-notifications') {
        event.waitUntil(syncNotificationSchedules());
    }
});


// Message handler for token storage and removal
self.addEventListener('message', (event) => {
    console.log('[SW] Received message event:', event.data?.type);

    if (event.data?.type === 'STORE_AUTH_TOKEN') {
        console.log('[SW][AUTH] Starting token storage process');
        
        const tokenData = {
            token: event.data.token,
            timestamp: new Date().toISOString(),
            version: CACHE_VERSION
        };

        caches.open(AUTH_CACHE)
            .then(cache => {
                console.log('[SW][AUTH] Cache opened successfully');
                const response = new Response(JSON.stringify(tokenData));
                return cache.put(AUTH_TOKEN_CACHE_KEY, response);
            })
            .then(() => checkAuthCache()) // Verifizierung der Speicherung
            .then(token => {
                console.log('[SW][AUTH] Token storage verified:', token ? 'success' : 'failed');
                if (event.ports?.[0]) {
                    event.ports[0].postMessage({ 
                        success: true,
                        timestamp: tokenData.timestamp 
                    });
                }
            })
            .catch(error => {
                console.error('[SW][AUTH] Storage error:', error);
                if (event.ports?.[0]) {
                    event.ports[0].postMessage({
                        success: false,
                        error: error.message
                    });
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

    } else if (event.data?.type === 'SYNC_NOTIFICATIONS') {
        // New handler for manual notification sync
        console.log('[SW] Manual notification sync requested');
        event.waitUntil(
            syncNotificationSchedules()
                .then(() => {
                    if (event.ports?.[0]) {
                        event.ports[0].postMessage({ success: true });
                        console.log('[SW] Sync completed successfully');
                    }
                })
                .catch(error => {
                    console.error('[SW] Sync error:', error);
                    if (event.ports?.[0]) {
                        event.ports[0].postMessage({
                            success: false,
                            error: error.message
                        });
                    }
                })
        );
    } else {
        console.log('[SW] Unknown message type received:', event.data?.type);
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
