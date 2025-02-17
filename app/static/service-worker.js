const STATIC_CACHE = 'walking-bus-static-v1';

const CACHE_VERSION = 'v20'; // Increment this when you update your service worker

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


async function fetchWithAuth(url, options = {}) {
    console.log('[SW][FETCH] Starting authenticated request');
    
    const response = await fetch(url, {
        ...options,
        credentials: 'include',  // This ensures cookies are sent with the request
        headers: {
            ...options.headers,
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
    });

    if (response.status === 401) {
        // Notify main thread about auth error
        const clients = await self.clients.matchAll();
        clients.forEach(client => {
            client.postMessage({
                type: 'AUTH_ERROR',
                status: 401
            });
        });
        throw new Error('[SW][FETCH] Authentication failed');
    }

    return response;
}


async function checkAndRestoreSubscription() {
    console.log('[SW] Checking for existing subscription in database');
    
    try {
        // Initial delay to ensure auth is ready
        await new Promise(resolve => setTimeout(resolve, 1000));
        
        // Check if user had subscriptions using cookie auth
        const response = await fetchWithAuth('/api/notifications/subscription');
        const data = await response.json();
        
        // Handle inactive subscription
        if (data && data.subscription && !data.subscription.is_active) {
            console.log('[SW] Found paused subscription, attempting to restore');
            
            // Get VAPID key for push subscription
            const vapidResponse = await fetchWithAuth('/api/notifications/vapid-key');
            const vapidKey = await vapidResponse.text();
            
            // Create new push subscription
            const subscription = await self.registration.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: vapidKey
            });
            
            // Store new subscription with existing participantIds
            await fetchWithAuth('/api/notifications/subscription', {
                method: 'POST',
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
