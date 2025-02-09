class NotificationManager {
    constructor() {
        this.vapidPublicKey = null;
    }

    async init() {
        console.log('[NOTIFICATIONS] Initializing NotificationManager');
        if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
            throw new Error('Push notifications are not supported');
        }
        await this.getVapidKey();
    }

    async initializeServiceWorker() {
        console.log('[NOTIFICATIONS] Starting Service Worker initialization');
        const registration = await navigator.serviceWorker.register('/static/service-worker.js');
    
        if (registration.installing) {
            console.log('[NOTIFICATIONS] Service Worker installing');
            await new Promise(resolve => {
                registration.installing.addEventListener('statechange', e => {
                    if (e.target.state === 'activated') {
                        console.log('[NOTIFICATIONS] Service Worker activated');
                        resolve();
                    }
                });
            });
        }
    
        return registration.active;  // Return active worker instead of registration
    }

    async getVapidKey() {
        const response = await fetchWithAuth('/api/notifications/vapid-key');
        this.vapidPublicKey = await response.text();
    }

    async checkSubscription() {
        await this.initializeServiceWorker();
        const registration = await navigator.serviceWorker.ready;
        const subscription = await registration.pushManager.getSubscription();
        return !!subscription;
    }

    async subscribeUserToPush(participantIds) {
        try {
            console.log('[NOTIFICATIONS] Starting subscription process');
            
            const permission = await Notification.requestPermission();
            console.log('[NOTIFICATIONS] Permission status:', permission);
            
            if (permission !== 'granted') {
                throw new Error('Notification permission denied');
            }
    
            if ('serviceWorker' in navigator) {
                console.log('[NOTIFICATIONS] Service Worker available, starting initialization');
                navigator.serviceWorker.register('/static/service-worker.js')
                .then(registration => {
                    console.log('[NOTIFICATIONS] Service Worker registered:', registration);
                })
                .catch(error => {
                    console.error('[NOTIFICATIONS] Service Worker registration failed:', error);
                });
                
                const activeWorker = await this.initializeServiceWorker();
                console.log('[NOTIFICATIONS] Service Worker initialized:', activeWorker.state);
                
                const registration = await navigator.serviceWorker.ready;
                console.log('[NOTIFICATIONS] Creating push subscription');
                
                const subscription = await registration.pushManager.subscribe({
                    userVisibleOnly: true,
                    applicationServerKey: this.vapidPublicKey
                });
                console.log('[NOTIFICATIONS] Push subscription created');
    
                await fetchWithAuth('/api/notifications/subscription', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        subscription: subscription,
                        participantIds: participantIds
                    })
                });
                
                return true;
            }
        } catch (error) {
            console.error('[NOTIFICATIONS] Error:', error);
            throw error;
        }
    }
    
    

    async unsubscribeFromPush() {
        await this.initializeServiceWorker();
        const registration = await navigator.serviceWorker.ready;
        const subscription = await registration.pushManager.getSubscription();
        
        if (subscription) {
            await subscription.unsubscribe();
            
            await fetchWithAuth('/api/notifications/subscription', {
                method: 'DELETE',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    endpoint: subscription.endpoint
                })
            });
            
            return true;
        }
        return false;
    }

    async getCurrentSubscriptionDetails() {
        await this.initializeServiceWorker();
        const registration = await navigator.serviceWorker.ready;
        const subscription = await registration.pushManager.getSubscription();
        
        if (subscription) {
            const response = await fetchWithAuth('/api/notifications/subscription');
            return await response.json();
        }
        return null;
    }
}

const notificationManager = new NotificationManager();