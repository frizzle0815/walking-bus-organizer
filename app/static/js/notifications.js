class NotificationManager {
    constructor() {
        this.vapidPublicKey = null;
    }

    async init() {
        if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
            throw new Error('Push notifications are not supported');
        }
        await this.getVapidKey();
    }

    async getVapidKey() {
        const response = await fetchWithAuth('/api/notifications/vapid-key');
        this.vapidPublicKey = await response.text();
    }

    async checkSubscription() {
        const registration = await navigator.serviceWorker.ready;
        const subscription = await registration.pushManager.getSubscription();
        return !!subscription;
    }

    async subscribeUserToPush(participantIds) {
        try {
            const permission = await Notification.requestPermission();
            if (permission !== 'granted') {
                throw new Error('Notification permission denied');
            }

            const registration = await navigator.serviceWorker.ready;
            const subscription = await registration.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: this.vapidPublicKey
            });

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
        } catch (error) {
            console.error('[NOTIFICATIONS] Subscription failed:', error);
            throw error;
        }
    }

    async unsubscribeFromPush() {
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