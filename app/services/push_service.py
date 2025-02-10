from flask import current_app
import json
import time
from pywebpush import webpush, WebPushException
from sqlalchemy.exc import SQLAlchemyError
from ..models import db, PushSubscription
from urllib.parse import urlparse


class PushService:
    def __init__(self, walking_bus_id):
        self.walking_bus_id = walking_bus_id
        self.to_delete = set()
        self.vapid_private_key = current_app.config['VAPID_PRIVATE_KEY']
        self.vapid_claims_sub = current_app.config['VAPID_CLAIMS']['sub']

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