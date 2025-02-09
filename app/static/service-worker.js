importScripts('https://cdn.jsdelivr.net/npm/idb@7/build/umd.js');
const { openDB } = idb;

self.CACHE_VERSION = 'v7'; // Increment this when you update your service worker

const STATIC_CACHE = 'walking-bus-static-v1';
const DATA_CACHE = 'walking-bus-data-v1';
const AUTH_CACHE = 'walking-bus-auth-v1';
const NOTIFICATION_CACHE = 'walking-bus-notifications-v1';
const SCHEDULE_DB_NAME = 'walking-bus-schedules';
const SCHEDULE_STORE_NAME = 'notification-schedules';
const STORAGE_KEY_PREFIX = 'walking-bus-notification-';

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


class NotificationStorageManager {
    constructor() {
        this.isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent);
    }

    async storeSchedule(participantData) {
        const { participantId, scheduleTime, busTime } = participantData;
        const notificationId = `notification-${participantId}-${busTime}`;
        const data = {
            id: notificationId,
            participantId,
            scheduleTime,
            busTime,
            processed: false
        };

        if (this.isIOS) {
            localStorage.setItem(
                `${STORAGE_KEY_PREFIX}${notificationId}`, 
                JSON.stringify(data)
            );
        } else {
            const db = await openDB(SCHEDULE_DB_NAME);
            await db.put(SCHEDULE_STORE_NAME, data);
        }
    }

    async getAllSchedules() {
        if (this.isIOS) {
            const schedules = [];
            for (let i = 0; i < localStorage.length; i++) {
                const key = localStorage.key(i);
                if (key.startsWith(STORAGE_KEY_PREFIX)) {
                    schedules.push(JSON.parse(localStorage.getItem(key)));
                }
            }
            return schedules;
        } else {
            const db = await openDB(SCHEDULE_DB_NAME);
            return db.getAll(SCHEDULE_STORE_NAME);
        }
    }

    async cleanupSchedules(participantIds) {
        if (this.isIOS) {
            for (let i = 0; i < localStorage.length; i++) {
                const key = localStorage.key(i);
                if (key.startsWith(STORAGE_KEY_PREFIX)) {
                    const data = JSON.parse(localStorage.getItem(key));
                    if (participantIds.includes(data.participantId)) {
                        localStorage.removeItem(key);
                    }
                }
            }
        } else {
            const db = await openDB(SCHEDULE_DB_NAME);
            const tx = db.transaction(SCHEDULE_STORE_NAME, 'readwrite');
            const store = tx.objectStore(SCHEDULE_STORE_NAME);
            const schedules = await store.getAll();
            
            for (const schedule of schedules) {
                if (participantIds.includes(schedule.participantId)) {
                    await store.delete(schedule.id);
                }
            }
            await tx.complete;
        }
    }
}

// Create instance
const storageManager = new NotificationStorageManager();


async function cleanupNotificationSchedules(participantIds) {
    await storageManager.cleanupSchedules(participantIds);
}


// Add this new scheduling system
async function scheduleNotification(participantData) {
    const { participantId, scheduleTime, busTime } = participantData;
    const notificationId = `notification-${participantId}-${busTime}`;

    // Store schedule data
    await storageManager.storeSchedule({
        id: notificationId,
        participantId,
        scheduleTime,
        busTime,
        processed: false
    });

    // Create timestamp trigger
    const scheduledTime = new Date(scheduleTime).getTime();
    
    try {
        await self.registration.showNotification('Walking Bus Erinnerung', {
            body: `Erinnerung für ${busTime}`,
            icon: '/static/icons/icon-192x192.png',
            badge: '/static/icons/icon-192x192.png',
            tag: notificationId,
            showTrigger: new TimestampTrigger(scheduledTime),
            data: {
                participantId,
                busTime,
                url: '/notifications'
            },
            actions: [
                {
                    action: 'toggle-status',
                    title: 'Status ändern'
                },
                {
                    action: 'okay',
                    title: 'Okay'
                }
            ]
        });
        
        console.log('[SW][NOTIFY] Notification scheduled for:', new Date(scheduledTime));
        return true;
    } catch (error) {
        console.error('[SW][NOTIFY] Scheduling failed:', error);
        return false;
    }
}


// Add background sync registration
async function registerBackgroundSync() {
    if ('periodicSync' in self.registration) {
        try {
            await self.registration.periodicSync.register('check-notifications', {
                minInterval: 12 * 60 * 60 * 1000 // 12 hours
            });
            console.log('[SYNC] Background sync registered successfully');
        } catch (error) {
            console.error('[SYNC] Background sync registration failed:', error);
        }
    }
}

// Add periodic sync event handler
self.addEventListener('periodicsync', (event) => {
    if (event.tag === 'check-notifications') {
        event.waitUntil(syncNotificationSchedules());
    }
});


// Show notification with participant status
async function showParticipantNotification(notificationData) {
    try {
        const registration = await self.registration;
        if (!registration.active) {
            throw new Error('No active service worker');
        }

        // Update processed status in storage
        const db = await openDB(SCHEDULE_DB_NAME);
        const tx = db.transaction(SCHEDULE_STORE_NAME, 'readwrite');
        const store = tx.objectStore(SCHEDULE_STORE_NAME);
        
        // Mark notification as processed
        await store.put({
            id: notificationData.id,
            participantId: notificationData.participantId,
            busTime: notificationData.busTime,
            processed: true,
            scheduleTime: new Date().toISOString()
        });
        
        await tx.complete;

        // Fetch participant status
        const response = await fetchWithAuth(`/api/notifications/participant-status/${notificationData.participantId}`);
        const data = await response.json();
        
        // Show the notification
        return self.registration.showNotification('Walking Bus Erinnerung', {
            body: `${data.participantName} ist für heute ${data.status ? 'angemeldet' : 'abgemeldet'}`,
            icon: '/static/icons/icon-192x192.png',
            badge: '/static/icons/icon-192x192.png',
            tag: notificationData.id,
            requireInteraction: true,
            data: {
                participantId: notificationData.participantId,
                url: '/notifications'
            },
            actions: [
                {
                    action: 'toggle-status',
                    title: data.status ? 'Abmelden' : 'Anmelden'
                },
                {
                    action: 'okay',
                    title: 'Okay'
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
        const response = await fetchWithAuth('/api/notifications/schedules');
        const data = await response.json();
        
        // Clear existing schedules
        const existingSchedules = await storageManager.getAllSchedules();
        for (const schedule of existingSchedules) {
            if (!schedule.processed) {
                // Cancel existing notification
                const notifications = await self.registration.getNotifications({
                    tag: schedule.id
                });
                notifications.forEach(n => n.close());
            }
        }
        
        // Schedule new notifications
        const results = await Promise.all(
            data.schedules.map(schedule => scheduleNotification(schedule))
        );
        
        console.log('[SW] Scheduled notifications:', results.filter(r => r).length);
        return true;
    } catch (error) {
        console.error('[SW] Schedule sync error:', error);
        return false;
    }
}


async function fetchWithAuth(url, options = {}) {
    console.log('[SW][FETCH] Starting authenticated request to:', url);
    
    try {
        let token = null;
        
        // Try Service Worker cache first
        const cache = await caches.open(AUTH_CACHE);
        const tokenResponse = await cache.match(AUTH_TOKEN_CACHE_KEY);
        
        if (tokenResponse) {
            const tokenData = await tokenResponse.json();
            token = tokenData.token;
            console.log('[SW][FETCH] Token retrieved from cache');
            
            // Make authenticated request
            options.headers = {
                ...options.headers,
                'Authorization': `Bearer ${token}`
            };
            
            console.log('[SW][FETCH] Sending request with auth header');
            return fetch(url, options);
        }
        
        throw new Error('No authentication token available');
    } catch (error) {
        console.error('[SW][FETCH] Error during authenticated request:', error);
        throw error;
    }
}



async function getAuthToken() {
    let token = null;
    
    // Try Service Worker cache first
    try {
        const cache = await caches.open('walking-bus-auth-v1');
        const response = await cache.match('static/auth-token');
        if (response) {
            const data = await response.json();
            token = data.token;
        }
    } catch (error) {
        console.log('[SW][AUTH] Cache access failed, trying localStorage');
    }
    
    // Fallback to localStorage via client
    if (!token) {
        const clients = await self.clients.matchAll();
        if (clients.length > 0) {
            const client = clients[0];
            token = await new Promise(resolve => {
                const channel = new MessageChannel();
                channel.port1.onmessage = event => resolve(event.data?.token);
                client.postMessage({type: 'GET_LOCAL_STORAGE_TOKEN'}, [channel.port2]);
            });
        }
    }
    
    return token;
}


// Handle notification clicks
self.addEventListener('notificationclick', async (event) => {
    event.notification.close();
    
    if (event.action === 'toggle-status') {
        try {
            await fetchWithAuth(`/api/participation/${event.notification.data.participantId}`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    date: new Date().toISOString().split('T')[0]
                })
            });
        } catch (error) {
            console.error('[SW][NOTIFY] Error toggling status:', error);
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
            // 1. First verify auth status
            checkAuthCache().then(token => {
                if (token) {
                    console.log('[SW][AUTH] Token verified, proceeding with activation');
                    return token;
                }
                throw new Error('No valid auth token found');
            }),

            // 2. Then setup notifications only if auth is valid
            (async () => {
                await syncNotificationSchedules();
                
                // Only register periodic sync if supported and notifications permitted
                if ('periodicSync' in self.registration && 
                    Notification.permission === 'granted') {
                    await self.registration.periodicSync.register('sync-notifications', {
                        minInterval: 24 * 60 * 60 * 1000 
                    });
                }
            })(),

            // 3. Finally claim clients when everything is ready
            self.clients.claim()
        ])
    );
});

// Helper Funktion für Auth Cache Überprüfung
async function checkAuthCache() {
    let token = null;
    
    // 1. Check Service Worker Cache
    try {
        const cache = await caches.open(AUTH_CACHE);
        const tokenResponse = await cache.match(AUTH_TOKEN_CACHE_KEY);
        if (tokenResponse) {
            const data = await tokenResponse.json();
            token = data.token;
            console.log('[SW][AUTH] Token found in cache');
            return tokenResponse;
        }
    } catch (error) {
        console.log('[SW][AUTH] Cache check failed:', error);
    }

    // 2. Check localStorage via client
    try {
        const clients = await self.clients.matchAll();
        if (clients.length > 0) {
            const client = clients[0];
            const response = await new Promise(resolve => {
                const channel = new MessageChannel();
                channel.port1.onmessage = event => {
                    resolve(event.data?.token);
                };
                client.postMessage({type: 'GET_LOCAL_STORAGE_TOKEN'}, [channel.port2]);
            });
            
            if (response) {
                console.log('[SW][AUTH] Token found in localStorage');
                return new Response(JSON.stringify({token: response}));
            }
        }
    } catch (error) {
        console.log('[SW][AUTH] localStorage check failed:', error);
    }

    return null;
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

    if (event.data?.type === 'SHOW_TEST_NOTIFICATION') {
        console.log('[SW] Showing test notification');
        self.registration.showNotification('Test Benachrichtigung', {
            body: 'Die Benachrichtigungen funktionieren!',
            icon: '/static/icons/icon-192x192.png',
            badge: '/static/icons/icon-192x192.png',
            tag: 'test-notification',
            actions: [
                {
                    action: 'okay',
                    title: 'Okay'
                }
            ]
        }).then(() => {
            console.log('[SW] Test notification shown successfully');
            if (event.ports?.[0]) {
                event.ports[0].postMessage({ success: true });
            }
        }).catch(error => {
            console.error('[SW] Test notification error:', error);
            if (event.ports?.[0]) {
                event.ports[0].postMessage({
                    success: false,
                    error: error.message
                });
            }
        });
    } else if (event.data?.type === 'STORE_AUTH_TOKEN') {
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
            .then(() => checkAuthCache())
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

    } else if (event.data?.type === 'CLEANUP_NOTIFICATIONS') {
        const removedParticipants = event.data.participants;
        console.log('[SW] Starting notification cleanup for participants:', removedParticipants);
        
        cleanupNotificationSchedules(removedParticipants).then(() => {
            console.log('[SW] Notification cleanup completed successfully');
            if (event.ports?.[0]) {
                event.ports[0].postMessage({ success: true });
            }
        }).catch(error => {
            console.error('[SW] Cleanup error:', error);
            if (event.ports?.[0]) {
                event.ports[0].postMessage({
                    success: false,
                    error: error.message
                });
            }
        });

    } else if (event.data?.type === 'SYNC_NOTIFICATIONS') {
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

    } else if (event.data?.type === 'GET_NOTIFICATION_SCHEDULES') {
        console.log('[SW] Fetching notification schedules');
        
        storageManager.getAllSchedules()
            .then(schedules => {
                // Send schedules directly without trying to fetch participant data
                if (event.ports?.[0]) {
                    event.ports[0].postMessage({
                        schedules: schedules
                    });
                }
            })
            .catch(error => {
                console.error('[SW] Schedule fetch error:', error);
                if (event.ports?.[0]) {
                    event.ports[0].postMessage({
                        schedules: [],
                        error: error.message
                    });
                }
            });

    } else {
        console.log('[SW] Unknown message type received:', event.data?.type);
    }
});


async function cleanupNotificationSchedules(participantIds) {
    console.log('[SW][CLEANUP] Starting cleanup for participants:', participantIds);
    
    const db = await openDB(SCHEDULE_DB_NAME);
    const tx = db.transaction(SCHEDULE_STORE_NAME, 'readwrite');
    const store = tx.objectStore(SCHEDULE_STORE_NAME);
    
    // Get all schedules
    const schedules = await store.getAll();
    console.log('[SW][CLEANUP] Current schedules:', schedules);
    
    let deletedCount = 0;
    // Delete schedules for removed participants
    for (const schedule of schedules) {
        if (participantIds.includes(schedule.participantId)) {
            await store.delete(schedule.id);
            deletedCount++;
        }
    }
    
    await tx.complete;
    console.log('[SW][CLEANUP] Deleted', deletedCount, 'schedules');
}


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
