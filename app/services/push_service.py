from flask import current_app
import json
import time
from pywebpush import webpush, WebPushException
from sqlalchemy.exc import SQLAlchemyError
from ..models import db, PushSubscription, Participant, CalendarStatus, PushNotificationLog
from urllib.parse import urlparse
from .. import get_or_generate_vapid_keys, get_current_date, get_current_time, WEEKDAY_MAPPING
import os
import re
from datetime import datetime, timedelta

# Static configuration at module level
vapid_keys = get_or_generate_vapid_keys()
VAPID_CONFIG = {
    'private_key': vapid_keys['private_key'],
    'public_key': vapid_keys['public_key'],
    'claims': {
        "sub": f"mailto:{os.getenv('VAPID_EMAIL', 'default@example.com')}"
    }
}


class PushService:
    def __init__(self, walking_bus_id):
        self.walking_bus_id = walking_bus_id
        self.to_delete = set()
        
        # Debug logging for initialization
        current_app.logger.info(f"[PUSH][INIT] VAPID_CONFIG: {VAPID_CONFIG}")
        current_app.logger.info(f"[PUSH][INIT] Environment VAPID_EMAIL: {os.getenv('VAPID_EMAIL')}")
        current_app.logger.info(f"[PUSH][INIT] App config VAPID_EMAIL: {current_app.config.get('VAPID_EMAIL')}")
        
        self.vapid_private_key = VAPID_CONFIG['private_key']
        self.vapid_claims_sub = VAPID_CONFIG['claims']['sub']
        
        # Verify initialization
        current_app.logger.info(f"[PUSH][INIT] Set claims_sub to: {self.vapid_claims_sub}")

    def get_subscriptions(self):
        """Get all subscriptions for current walking bus"""
        subscriptions = PushSubscription.query.filter_by(
            walking_bus_id=self.walking_bus_id
        ).all()
        current_app.logger.info(f"[PUSH][SUBS] Found {len(subscriptions)} total subscriptions")
        return subscriptions

    def send_notification(self, subscription, notification_data):
        """Send single push notification with error handling"""
        # First clean up old logs
        self.cleanup_old_logs()
        try:
            # Log attempt
            current_app.logger.info(f"[PUSH][ATTEMPT] Sending to endpoint: {subscription.endpoint}")
            current_app.logger.info(f"[PUSH][DATA] Notification data prepared: {notification_data}")
            current_app.logger.info(f"[PUSH][SEND] Using claims_sub: {self.vapid_claims_sub}")
            
            vapid_claims = {
                "sub": self.vapid_claims_sub,
                "exp": int(time.time()) + 12 * 3600,
                "aud": self._get_endpoint_origin(subscription.endpoint)
            }
            current_app.logger.info(f"[PUSH][CONFIG] VAPID claims configured: {vapid_claims}")

            webpush(
                subscription_info={
                    "endpoint": subscription.endpoint,
                    "keys": {
                        "p256dh": subscription.p256dh,
                        "auth": subscription.auth
                    }
                },
                data=json.dumps(notification_data),
                vapid_private_key=self.vapid_private_key,
                vapid_claims=vapid_claims
            )

            enhanced_notification_data = notification_data.copy()
            enhanced_notification_data['subscription_info'] = {
                'endpoint': subscription.endpoint,
                'client_info': subscription.auth_token.client_info
            }

            # Rest of the method remains the same until log creation
            log_entry = PushNotificationLog(
                walking_bus_id=self.walking_bus_id,
                subscription_id=subscription.id,
                status_code=201,
                notification_type=enhanced_notification_data.get('data', {}).get('type'),
                notification_data=enhanced_notification_data,
                success=True
            )
            db.session.add(log_entry)
            db.session.commit()
            
            current_app.logger.info(f"[PUSH][SUCCESS] Sent notification to endpoint: {subscription.endpoint}")
            return True, None

        except WebPushException as e:
            error_str = str(e)
            status_match = re.search(r'(\d{3})\s+', error_str)
            status_code = int(status_match.group(1)) if status_match else None
            
            current_app.logger.error(f"[PUSH][ERROR] Full error details: {error_str}")
            
            # Log the error
            enhanced_notification_data = notification_data.copy()
            enhanced_notification_data['subscription_info'] = {
                'endpoint': subscription.endpoint,
                'client_info': subscription.auth_token.client_info
            }
            
            # Log the error with enhanced data
            log_entry = PushNotificationLog(
                walking_bus_id=self.walking_bus_id,
                subscription_id=subscription.id,
                status_code=status_code,
                error_message=error_str,
                notification_type=enhanced_notification_data.get('data', {}).get('type'),
                notification_data=enhanced_notification_data,
                success=False
            )
            db.session.add(log_entry)
            db.session.commit()

            # Handle specific status codes
            if status_code in (404, 410):
                # Subscription is expired or gone - mark for deletion
                self.to_delete.add(subscription.id)
                current_app.logger.info(f"[PUSH][DELETE] Marked subscription {subscription.id} for deletion - Status: {status_code}")
                
            elif status_code == 400:
                # Invalid request - likely VAPID issue
                self.to_delete.add(subscription.id)
                current_app.logger.error(f"[PUSH][ERROR] Invalid request for subscription {subscription.id} - VAPID may be invalid")
                
            elif status_code == 429:
                # Rate limit hit - extract retry after header
                retry_after = e.response.headers.get('Retry-After', '60')
                current_app.logger.warning(f"[PUSH][RATE_LIMIT] Rate limit hit. Retry after {retry_after} seconds")
                
            elif status_code == 413:
                # Payload too large
                current_app.logger.error(f"[PUSH][ERROR] Payload too large ({len(json.dumps(notification_data))} bytes)")

            return False, str(e)

    def cleanup_old_logs(self):
        """Delete push notification logs older than 7 days"""
        cutoff_date = datetime.now() - timedelta(days=7)
        
        deleted_count = PushNotificationLog.query.filter(
            PushNotificationLog.walking_bus_id == self.walking_bus_id,
            PushNotificationLog.timestamp < cutoff_date
        ).delete(synchronize_session=False)
        
        db.session.commit()
        current_app.logger.info(f"[PUSH][CLEANUP] Deleted {deleted_count} old notification logs")
        return deleted_count

    def prepare_schedule_notifications(self):
        """Prepare and send individual schedule notifications for each participant"""
        target_date = get_current_date()
        weekday = WEEKDAY_MAPPING[target_date.weekday()]
        
        subscriptions = self.get_subscriptions()
        results = []
        
        for subscription in subscriptions:
            participants = Participant.query.filter(
                Participant.id.in_(subscription.participant_ids),
                Participant.walking_bus_id == self.walking_bus_id
            ).all()
            
            for participant in participants:
                # Check if participant normally attends on this weekday
                normally_attends = getattr(participant, weekday, True)
                
                if normally_attends:
                    # Get calendar entry for this date
                    calendar_entry = CalendarStatus.query.filter_by(
                        participant_id=participant.id,
                        date=target_date,
                        walking_bus_id=self.walking_bus_id
                    ).first()
                    
                    # Determine actual status from calendar entry or default weekday setting
                    is_attending = calendar_entry.status if calendar_entry else normally_attends
                    
                    status_message = (
                        f"{participant.name} ist für heute ✅ angemeldet ✅"
                        if is_attending
                        else f"{participant.name} ist für heute ❌ abgemeldet ❌"
                    )
                    
                    notification_data = {
                        'title': 'Walking Bus Status',
                        'body': status_message,
                        'data': {
                            'type': 'schedule_reminder',
                            'participantId': participant.id,
                            'participantName': participant.name,
                            'currentStatus': is_attending,
                            'date': target_date.isoformat()
                        },
                        'tag': f'schedule-reminder-{participant.id}-{int(time.time())}',
                        'actions': [
                            {
                                'action': 'toggle_status',
                                'title': 'Abmelden' if is_attending else 'Anmelden'
                            },
                            {
                                'action': 'okay',
                                'title': 'OK'
                            }
                        ],
                        'requireInteraction': True
                    }
                    
                    success, error = self.send_notification(subscription, notification_data)
                    results.append({
                        'subscription_id': subscription.id,
                        'participant': participant.name,
                        'status': 'attending' if is_attending else 'not_attending',
                        'success': success,
                        'error': error
                    })
        
        cleanup_result = self.cleanup_expired_subscriptions()
        
        return {
            'notifications_sent': results,
            'cleanup': cleanup_result
        }

    def cleanup_expired_subscriptions(self):
        """Clean up expired subscriptions and maintain complete logging history"""
        if not self.to_delete:
            return 0
            
        try:
            # Mark notification logs for deleted subscriptions with timestamp
            current_time = get_current_time()
            log_update_count = PushNotificationLog.query.filter(
                PushNotificationLog.subscription_id.in_(self.to_delete)
            ).update({
                PushNotificationLog.subscription_deleted_at: current_time
            }, synchronize_session=False)
            
            current_app.logger.info(f"[PUSH][CLEANUP] Marked {log_update_count} notification logs for deleted subscriptions")

            # Delete subscriptions with detailed error handling
            deleted_count = PushSubscription.query.filter(
                PushSubscription.id.in_(self.to_delete)
            ).delete(synchronize_session=False)
            
            # Log deletion details
            current_app.logger.info(f"[PUSH][CLEANUP] Attempting to delete {len(self.to_delete)} subscriptions")
            current_app.logger.info(f"[PUSH][CLEANUP] Actually deleted {deleted_count} subscriptions")
            
            # Commit changes
            db.session.commit()
            
            # Verify deletion with remaining count
            remaining_count = PushSubscription.query.count()
            current_app.logger.info(f"[PUSH][VERIFY] Remaining subscriptions in database: {remaining_count}")
            
            # Additional verification of deleted IDs
            still_exist = PushSubscription.query.filter(
                PushSubscription.id.in_(self.to_delete)
            ).count()
            
            if still_exist:
                current_app.logger.warning(
                    f"[PUSH][CLEANUP] Warning: {still_exist} marked subscriptions still exist"
                )
            
            return {
                'deleted_count': deleted_count,
                'remaining_count': remaining_count,
                'log_updates': log_update_count,
                'verification': {
                    'marked_for_deletion': len(self.to_delete),
                    'still_exist': still_exist
                }
            }
                
        except SQLAlchemyError as e:
            db.session.rollback()
            current_app.logger.error(f"[PUSH][CLEANUP_ERROR] Failed to delete: {str(e)}")
            return {
                'error': str(e),
                'deleted_count': 0
            }


    @staticmethod
    def _get_endpoint_origin(endpoint):
        """Get origin from endpoint URL"""
        parsed = urlparse(endpoint)
        return f"{parsed.scheme}://{parsed.netloc}"