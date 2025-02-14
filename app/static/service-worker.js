const STATIC_CACHE = 'walking-bus-static-v1';
const DATA_CACHE = 'walking-bus-data-v1';
const AUTH_CACHE = 'walking-bus-auth-v1';

const AUTH_TOKEN_CACHE_KEY = 'auth-token';

const CACHE_VERSION = 'v19'; // Increment this when you update your service worker

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
            caches.open(AUTH_CACHE).then(() => console.log('[SW] Auth cache created')),
            self.skipWaiting()
        ]).then(() => console.log('[SW] Installation complete'))
    );
});


self.addEventListener('activate', (event) => {
    event.waitUntil(
        Promise.all([
            self.clients.claim(),
            self.registration.navigationPreload?.enable(),
            checkAndRestoreSubscription()
        ])
    );
});


// Message handler for token storage and removal
self.addEventListener('message', (event) => {
    console.log('[SW] Received message event:', event.data?.type);

    switch (event.data?.type) {
        case 'CHECK_SUBSCRIPTION':
            event.waitUntil(checkAndRestoreSubscription());
            break;

        case 'GET_AUTH_TOKEN':
            console.log('[SW] Processing token retrieval request');
            getTokenFromCache()
                .then(token => {
                    console.log('[SW] Cache token retrieval completed:', token ? 'Found' : 'Not found');
                    event.ports?.[0]?.postMessage({ token });
                })
                .catch(error => {
                    console.error('[SW] Cache token retrieval error:', error);
                    event.ports?.[0]?.postMessage({ token: null, error: error.message });
                });
            break;

        case 'STORE_AUTH_TOKEN':
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
                    event.ports?.[0]?.postMessage({ success: true });
                    console.log('[SW] Success message sent back');
                })
                .catch(error => {
                    console.error('[SW] Storage error:', error);
                    event.ports?.[0]?.postMessage({
                        success: false,
                        error: error.message
                    });
                    console.log('[SW] Error message sent back');
                });
            break;

        case 'CLEAR_AUTH_TOKEN':
            console.log('[SW] Starting cache clearing');
            caches.keys().then(keys => {
                console.log('[SW] Existing caches before deletion:', keys);
            });

            Promise.all([
                caches.open(STATIC_CACHE).then(cache => 
                    cache.keys().then(keys => 
                        Promise.all(keys.map(key => cache.delete(key)))
                    )
                ),
                caches.open(DATA_CACHE).then(cache => 
                    cache.keys().then(keys => 
                        Promise.all(keys.map(key => cache.delete(key)))
                    )
                ),
                caches.open(AUTH_CACHE).then(cache => 
                    cache.keys().then(keys => 
                        Promise.all(keys.map(key => cache.delete(key)))
                    )
                )
            ])
            .then(() => {
                console.log('[SW] All caches deleted successfully');
                event.ports?.[0]?.postMessage({ success: true });
                console.log('[SW] Success message sent back');
                console.log('[SW] Updating service worker registration');
                self.registration.update();
                return caches.keys();
            })
            .then(remainingKeys => {
                console.log('[SW] Remaining caches after deletion:', remainingKeys);
            })
            .catch(error => {
                console.error('[SW] Clear error:', error);
                event.ports?.[0]?.postMessage({
                    success: false,
                    error: error.message
                });
                console.log('[SW] Error message sent back');
            });
            break;

        case 'SKIP_WAITING':
            console.log('[SW] Skip waiting command received');
            self.skipWaiting();
            break;

        default:
            console.log('[SW] Unknown message type received:', event.data?.type);
    }
});

// triggered in base.html
self.addEventListener('periodicsync', (event) => {
    console.log('[SW][SYNC] Received sync event', event);
    if (event.tag === 'keep-alive') {
        event.waitUntil(
            // Dummy Response ohne echten Netzwerkaufruf
            Promise.resolve(new Response('', {
                status: 204,
                statusText: 'No Content'
            }))
        );
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
        badge: '/static/icons/bus-simple-solid.png',
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
    const data = event.notification.data;
    
    // Handle only toggle_status action
    if (event.action === 'toggle_status') {
        handleStatusToggle(data);
    } else if (!event.action) {
        // Only open/focus app when main notification is clicked (no action)
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
    // Any other action (like 'okay') just closes the notification with no further action
});

// Separate function for status toggle logic
async function handleStatusToggle(data) {
    if (!data) return;
    
    const { participantId, currentStatus, date, participantName } = data;
    try {
        // First update the participation status
        const response = await fetchWithAuth(`/api/participation/${participantId}`, {
            method: 'PATCH',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                date: date,
                status: !currentStatus
            })
        });

        // Then trigger the Redis status update
        await fetchWithAuth('/api/trigger-update', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                date: date
            })
        });

        const title = response.ok ? 'Status geändert' : 'Fehler ⚠️';
        const message = response.ok ?
            ((!currentStatus) ? `${participantName} erfolgreich angemeldet` : `${participantName} erfolgreich abgemeldet`) :
            `Status für ${participantName} konnte nicht geändert werden ⚠️ Bitte Änderung in der App durchführen.`;
           
        // Enhanced notification options matching push notification style
        self.registration.showNotification(title, {
            body: message,
            icon: '/static/icons/icon-192x192.png',  // Same icon as push notifications
            badge: '/static/icons/bus-simple-solid.png', // Same badge as push notifications
            tag: `status-change-${participantId}-${Date.now()}`,
            requireInteraction: false,
            renotify: true
        });
    } catch (error) {
        // Also enhance error notification
        self.registration.showNotification('Netzwerkfehler ⚠️', {
            body: `Verbindung zum Server fehlgeschlagen für ${participantName} ⚠️ Bitte Änderung in der App durchführen.`,
            icon: '/static/icons/icon-192x192.png',
            badge: '/static/icons/bus-simple-solid.png',
            tag: `status-change-error-${participantId}-${Date.now()}`,
            requireInteraction: false,
            renotify: true
        });
    }
}


async function getTokenFromIndexedDB() {
    console.log('[SW][AUTH][IndexedDB] Attempting to retrieve token');
    const db = await new Promise((resolve, reject) => {
        const request = indexedDB.open('WalkingBusAuth', 1);
        request.onerror = () => {
            console.error('[SW][AUTH][IndexedDB] Error opening database:', request.error);
            reject(request.error);
        }
        request.onsuccess = () => {
            console.log('[SW][AUTH][IndexedDB] Database opened successfully');
            resolve(request.result);
        }
    });
    
    const tx = db.transaction('tokens', 'readonly');
    const store = tx.objectStore('tokens');
    const tokenData = await store.get('current-token');
    console.log('[SW][AUTH][IndexedDB] Token retrieved:', tokenData ? 'Found' : 'Not found');
    return tokenData?.token;
}

function getTokenFromLocalStorage() {
    console.log('[SW][AUTH][LocalStorage] Attempting to retrieve token');
    const token = self.localStorage?.getItem('auth_token');
    console.log('[SW][AUTH][LocalStorage] Token retrieved:', token ? 'Found' : 'Not found');
    return token;
}

async function getTokenFromCache() {
    console.log('[SW][AUTH][Cache] Attempting to retrieve token');
    const cache = await caches.open('walking-bus-auth-v1');
    const response = await cache.match('auth-token');
    if (response) {
        const data = await response.json();
        console.log('[SW][AUTH][Cache] Token found in cache');
        return data.token;
    }
    console.log('[SW][AUTH][Cache] No token found in cache');
    return null;
}


async function fetchWithAuth(url, options = {}) {
    console.log('[SW][AUTH][FETCH] Starting authenticated request');
    
    let token;
    
    // Try IndexedDB first
    token = await getTokenFromIndexedDB();
    if (!token) {
        // If no token in IndexedDB, try localStorage
        token = getTokenFromLocalStorage();
        if (!token) {
            // Last resort: check cache
            token = await getTokenFromCache();
        }
    }

    if (!token) {
        throw new Error('[SW][AUTH][FETCH] No authentication token available');
    }

    const response = await fetch(url, {
        ...options,
        headers: {
            ...options.headers,
            'Authorization': `Bearer ${token}`
        }
    });

    if (response.status === 401) {
        throw new Error('[SW][AUTH][FETCH] Authentication failed');
    }

    return response;
}


async function checkAndRestoreSubscription() {
    console.log('[SW] Checking for existing subscription in database');
    
    try {
        await new Promise(resolve => setTimeout(resolve, 1000));
        
        // Check if we have a token before proceeding
        const token = await getTokenFromIndexedDB() || 
                     getTokenFromLocalStorage() || 
                     await getTokenFromCache();
                     
        if (!token) {
            console.log('[SW] No auth token available yet, skipping subscription check');
            return;
        }
        // Check if user had subscriptions
        const response = await fetchWithAuth('/api/notifications/subscription');
        const data = await response.json();
        
        // Add check for subscription status
        if (data && data.subscription && !data.subscription.is_active) {
            console.log('[SW] Found paused subscription, attempting to restore');
            
            // Get VAPID key and create new subscription
            const vapidResponse = await fetchWithAuth('/api/notifications/vapid-key');
            const vapidKey = await vapidResponse.text();
            
            const subscription = await self.registration.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: vapidKey
            });
            
            // Store new subscription with existing participantIds
            await fetchWithAuth('/api/notifications/subscription', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    subscription: subscription,
                    participantIds: data.participantIds
                })
            });
            
            console.log('[SW] Successfully restored push subscription');
        } else if (data && data.participantIds && data.participantIds.length > 0) {
            console.log('[SW] Found active subscription, no restoration needed');
        }
    } catch (error) {
        console.error('[SW] Error restoring subscription:', error);
    }
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
