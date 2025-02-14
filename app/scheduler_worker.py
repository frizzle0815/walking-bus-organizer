from app import create_app, db
from app.models import WalkingBus, WalkingBusSchedule, SchedulerJob, Participant
from app.services.push_service import PushService
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.pool import ProcessPoolExecutor
from apscheduler.jobstores.base import JobLookupError
from datetime import datetime, timedelta
from app.services.weather_service import WeatherService
import time
import pytz
import logging
from redis import Redis
import json
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('scheduler')

redis_url = os.environ.get('REDIS_URL')
redis_client = Redis.from_url(redis_url)

# Global scheduler instance
scheduler = None


def init_scheduler(app):
    """Initialize the APScheduler with database job store"""
    global scheduler
    
    if scheduler is None:
        logger.info("Initializing scheduler...")
        database_url = os.environ.get('DATABASE_URL')
        logger.info(f"Using database: {database_url}")
        
        jobstores = {
            'default': SQLAlchemyJobStore(url=database_url)
        }
        
        executors = {
            'default': ProcessPoolExecutor(
                max_workers=3
            )
        }
        
        scheduler = BackgroundScheduler(
            jobstores=jobstores,
            executors=executors,
            timezone=pytz.timezone('Europe/Berlin'),
            job_defaults={
                'max_instances': 1,
                'misfire_grace_time': 300  # 5 minute timeout
            }
        )
    
    return scheduler


def init_redis_listener(app):
    """Initialize Redis listener for schedule changes"""
    logger.info(f"Initializing Redis listener with URL: {redis_url}")
    
    pubsub = redis_client.pubsub()
    pubsub.subscribe('schedule_updates', 'test_notification_requests')
    return pubsub


def initialize_all_schedules():
    """Load and initialize all existing schedules on startup"""
    with app.app_context():
        buses = WalkingBus.query.all()
        for bus in buses:
            update_walking_bus_notifications(app, bus.id)


def handle_schedule_change(app, data):
    """Process schedule change notification"""
    try:
        bus_id = data['bus_id']
        logger.info(f"[REDIS] Received schedule update for bus {bus_id}")
        update_walking_bus_notifications(app, bus_id)
    except Exception as e:
        logger.error(f"[REDIS] Error handling schedule change: {e}")


def update_walking_bus_notifications(app, walking_bus_id=None):
    logger.info(f"[SCHEDULER] Starting update_walking_bus_notifications with walking_bus_id: {walking_bus_id}")
    
    with app.app_context():
        query = WalkingBus.query
        if walking_bus_id:
            query = query.filter_by(id=walking_bus_id)
        buses = query.all()
        logger.info(f"[SCHEDULER] Found {len(buses)} buses to process")

        for bus in buses:
            logger.info(f"[SCHEDULER] Processing bus {bus.id} ({bus.name})")
            schedule = WalkingBusSchedule.query.filter_by(walking_bus_id=bus.id).first()
            
            if not schedule:
                logger.warning(f"[SCHEDULER] No schedule found for bus {bus.id}, skipping")
                continue

            weekdays = ['monday', 'tuesday', 'wednesday', 'thursday', 
                       'friday', 'saturday', 'sunday']
                       
            for day in weekdays:
                job_id = f'notify_bus_{bus.id}_{day}'
                logger.debug(f"[SCHEDULER] Processing {day} for bus {bus.id}")
                
                # Remove job if day is inactive
                if not getattr(schedule, day):
                    logger.info(f"[SCHEDULER] Removing job for inactive day: {job_id}")
                    try:
                        scheduler.remove_job(job_id)
                    except JobLookupError:
                        logger.debug(f"Job {job_id} was not found - already removed or never existed")
                    SchedulerJob.query.filter_by(job_id=job_id).delete()
                    continue
                    
                start_time = getattr(schedule, f"{day}_start")
                if not start_time:
                    logger.warning(f"[SCHEDULER] No start time for {day}, skipping")
                    continue
                    
                # Calculate notification time; 55 minutes instead of 1 hour to include more accurate weather data
                notification_time = (
                    datetime.combine(datetime.today(), start_time) - 
                    timedelta(minutes=55)
                ).time()
                
                logger.info(f"[SCHEDULER] Setting up job {job_id} for {notification_time}")
                
                # Create job
                job = scheduler.add_job(
                    send_walking_bus_notifications,
                    'cron',
                    day_of_week=day[:3],
                    hour=notification_time.hour,
                    minute=notification_time.minute,
                    args=[bus.id],
                    id=job_id,
                    replace_existing=True
                )
                
                # Update database record
                scheduler_job = SchedulerJob.query.filter_by(job_id=job_id).first()
                if not scheduler_job:
                    logger.info(f"[SCHEDULER] Creating new scheduler job record: {job_id}")
                    scheduler_job = SchedulerJob(
                        walking_bus_id=bus.id,
                        job_id=job_id,
                        job_type='walking_bus_notification',
                        next_run_time=job.next_run_time
                    )
                    db.session.add(scheduler_job)
                else:
                    logger.info(f"[SCHEDULER] Updating existing scheduler job: {job_id}")
                    scheduler_job.next_run_time = job.next_run_time
                    
            db.session.commit()
            logger.info(f"[SCHEDULER] Completed processing for bus {bus.id}")

    logger.info("[SCHEDULER] Finished update_walking_bus_notifications")


def send_walking_bus_notifications(bus_id):
    """Execute notifications for a specific walking bus"""
    logger.info(f"[SCHEDULER] Starting notifications for bus {bus_id}")
    
    # Create app context since this runs in a separate thread
    app = create_app()

    with app.app_context():
        try:
            # Try weather update but continue if it fails
            try:
                weather_service = WeatherService()
                update_result = weather_service.update_weather()
                if update_result["success"]:
                    weather_service.update_weather_calculations()
                logger.info("[SCHEDULER] Weather update completed successfully")
            except Exception as e:
                logger.error(f"[SCHEDULER] Weather update failed: {str(e)}")
                # Continue with notifications despite weather error
            
            # Now send notifications with fresh weather data
            push_service = PushService(bus_id)
            result = push_service.prepare_schedule_notifications()
            logger.info(f"[SCHEDULER] Notification completed for bus {bus_id}: {result}")
            return True
            
        except Exception as e:
            logger.error(f"[SCHEDULER] Error sending notifications for bus {bus_id}: {str(e)}")
            return False
        finally:
            # Ensure cleanup
            db.session.remove()


def handle_test_notification(app, job_key):
    """Process a test notification job from Redis"""
    logger.info(f"[TEST] Processing notification job: {job_key}")
    
    # Get job data from Redis
    job_data = redis_client.get(job_key)
    if not job_data:
        logger.warning(f"[TEST] Job data not found for key: {job_key}")
        return
    
    job_data = json.loads(job_data)
    scheduled_time = datetime.now(pytz.timezone('Europe/Berlin')) + timedelta(minutes=2)
    
    # Create unique job ID
    job_id = f"test_notification_{job_data['walking_bus_id']}_{int(time.time())}"
    
    # Schedule the job
    scheduler.add_job(
        send_test_notifications,
        'date',
        run_date=scheduled_time,
        id=job_id,
        args=[job_data['walking_bus_id'], job_data['participant_ids']],
        replace_existing=True
    )
    
    logger.info(f"[TEST] Scheduled job {job_id} for {scheduled_time}")


def send_test_notifications(walking_bus_id, participant_ids):
    """Execute test notifications"""
    logger.info(f"[TEST] Executing test notifications for bus {walking_bus_id}")
    
    app = create_app()
    with app.app_context():
        try:
            push_service = PushService(walking_bus_id)
            
            # Get participants
            participants = Participant.query.filter(
                Participant.id.in_(participant_ids),
                Participant.walking_bus_id == walking_bus_id
            ).all()
            
            results = []
            for subscription in push_service.get_subscriptions():
                matching_participants = [p for p in participants 
                                      if p.id in set(subscription.participant_ids)]
                                      
                if not matching_participants:
                    continue
                    
                for participant in matching_participants:
                    notification_data = {
                        'title': 'Walking Bus Test',
                        'body': f'Test Benachrichtigung erfolgreich für: {participant.name}',
                        'data': {
                            'type': 'test',
                            'participantIds': [participant.id]
                        },
                        'tag': f'test-notification-{participant.id}-{int(time.time())}',
                        'actions': [{
                            'action': 'okay',
                            'title': 'OK'
                        }],
                        'requireInteraction': True
                    }
                    
                    success, error = push_service.send_notification(subscription, notification_data)
                    results.append({
                        'participant': participant.name,
                        'success': success,
                        'error': error
                    })
            
            logger.info(f"[TEST] Notification results: {results}")
            return results
            
        except Exception as e:
            logger.error(f"[TEST] Error sending notifications: {str(e)}")
            return False
        finally:
            db.session.remove()


if __name__ == '__main__':
    # Create Flask app instance with enhanced configuration
    app = create_app()
    
    with app.app_context():
        try:
            scheduler = init_scheduler(app)
            scheduler.start()
            logger.info('Scheduler started successfully')
            
            pubsub = init_redis_listener(app)
            logger.info('Redis listener initialized')
            
            for message in pubsub.listen():
                if message['type'] == 'message':
                    data = json.loads(message['data'])
                    logger.info(f"[REDIS] Received message: {data}")
                    
                    channel = message.get('channel', b'').decode('utf-8')
                    if channel == 'test_notification_requests':
                        handle_test_notification(app, data['job_key'])
                    elif channel == 'schedule_updates':
                        handle_schedule_change(app, data)
                    
        except Exception as e:
            logger.error(f"Critical error in scheduler worker: {e}")
            raise
        finally:
            if scheduler:
                scheduler.shutdown()
            if 'pubsub' in locals():
                pubsub.close()
