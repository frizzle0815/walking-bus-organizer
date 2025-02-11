from flask import current_app
import json
import time
from pywebpush import webpush, WebPushException
from sqlalchemy.exc import SQLAlchemyError
from ..models import db, PushSubscription, Participant, CalendarStatus
from urllib.parse import urlparse
from .. import get_or_generate_vapid_keys, get_current_date, WEEKDAY_MAPPING
import os

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
            
            current_app.logger.info(f"[PUSH][SUCCESS] Sent notification to endpoint: {subscription.endpoint}")
            return True, None

        except WebPushException as e:
            error_str = str(e)
            current_app.logger.error(f"[PUSH][ERROR] Full error details: {error_str}")
            
            if "410" in error_str:
                status_code = 410
                error_body = error_str.split("Response body:", 1)[1].strip() if "Response body:" in error_str else "Unknown"
                current_app.logger.error(f"[PUSH][ERROR] Parsed status code: {status_code}")
                current_app.logger.error(f"[PUSH][ERROR] Parsed error body: {error_body}")
                
                self.to_delete.add(subscription.id)
                current_app.logger.info(f"[PUSH][DELETE] Marked subscription {subscription.id} for deletion")
            
            return False, str(e)

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
        """Clean up expired subscriptions and return count"""
        if not self.to_delete:
            return 0
            
        try:
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