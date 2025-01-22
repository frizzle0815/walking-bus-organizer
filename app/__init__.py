from flask import Flask, request
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from datetime import datetime, timedelta, time
import os
import pytz
import logging
import secrets
import subprocess
import json
from logging.handlers import RotatingFileHandler
from zoneinfo import ZoneInfo
from redis import Redis
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.combining import OrTrigger
from apscheduler.triggers.cron import CronTrigger

db = SQLAlchemy()
migrate = Migrate()
scheduler = BackgroundScheduler()


# Define the application's timezone
DEFAULT_TIMEZONE = 'Europe/Berlin'
DEFAULT_REDIS_URL = 'redis://localhost:6379'
timezone_name = os.getenv('APP_TIMEZONE', DEFAULT_TIMEZONE)
redis_url = os.getenv('REDIS_URL', DEFAULT_REDIS_URL)
redis_client = Redis.from_url(redis_url)

try:
    TIMEZONE = ZoneInfo(timezone_name)
except Exception:
    TIMEZONE = pytz.timezone(timezone_name)

# Centralized weekday mapping
WEEKDAY_MAPPING = {
    0: 'monday',
    1: 'tuesday',
    2: 'wednesday',
    3: 'thursday',
    4: 'friday',
    5: 'saturday',
    6: 'sunday'
}


def get_git_revision():
    # First check for build-time revision file
    if os.path.exists('git_revision.txt'):
        with open('git_revision.txt', 'r') as f:
            revision = f.read().strip()
            return {'short': revision[:7], 'full': revision}
    
    # Fallback to git command for development
    try:
        short_hash = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD']).decode('ascii').strip()
        full_hash = subprocess.check_output(['git', 'rev-parse', 'HEAD']).decode('ascii').strip()
        return {'short': short_hash, 'full': full_hash}
    except:
        return {'short': 'unknown', 'full': 'unknown'}


def get_current_time():
    """Get current time in application timezone"""
    return datetime.now(TIMEZONE)


def get_current_date():
    """Get current date in application timezone"""
    return get_current_time().date()


class RequestFormatter(logging.Formatter):
    def format(self, record):
        if request:
            record.client_ip = request.headers.get('X-Forwarded-For', '').split(',')[0].strip() or request.remote_addr
        else:
            record.client_ip = '-'
        return f"[{self.formatTime(record)}] [{record.client_ip}] {record.getMessage()}"


def reconfigure_weather_scheduler(app):
    with app.app_context():
        if scheduler.running:
            scheduler.remove_job('weather_update')
            
        from .services.weather_service import WeatherService
        from .models import WalkingBusSchedule
        weather_service = WeatherService()
        
        def perform_weather_update():
            success = weather_service.update_weather()
            if success:
                redis_client.publish('status_updates', json.dumps({
                    "type": "weather_update",
                    "timestamp": get_current_time().isoformat(),
                    "status": "success"
                }))
                app.logger.info("[SCHEDULER] Weather update successful")
            else:
                app.logger.warning("[SCHEDULER] Weather update failed")

        # Get all schedules and log initial scan
        schedules = WalkingBusSchedule.query.all()
        app.logger.info(f"[SCHEDULER] Reconfiguring scheduler with {len(schedules)} walking bus schedules")
        
        earliest_time = time(23, 59)
        latest_time = time(0, 0)
        active_days = set()
        
        # Log schedule analysis
        for schedule in schedules:
            app.logger.info(f"[SCHEDULER] Analyzing schedule for walking bus {schedule.walking_bus_id}")
            for day in WEEKDAY_MAPPING.values():
                if getattr(schedule, day):
                    active_days.add(day[:3].lower())
                    day_start = getattr(schedule, f"{day}_start")
                    day_end = getattr(schedule, f"{day}_end")
                    app.logger.info(f"[SCHEDULER] {day}: {day_start} - {day_end}")
                    
                    earliest_time = min(earliest_time, day_start)
                    latest_time = max(latest_time, day_end)
        
        minutely_window_start = (earliest_time.hour - 1)
        minutely_window_end = latest_time.hour
        active_days_str = ','.join(sorted(active_days))
        
        # Log final scheduler configuration
        app.logger.info(f"""[SCHEDULER] New configuration:
            Active Days: {active_days_str}
            Minutely Updates: {minutely_window_start}:00 - {minutely_window_end}:00
            Earliest Schedule: {earliest_time}
            Latest Schedule: {latest_time}
        """)
        
        scheduler.add_job(
            func=perform_weather_update,
            trigger=OrTrigger([
                CronTrigger(
                    day_of_week=active_days_str,
                    hour=f'{minutely_window_start}-{minutely_window_end}',
                    minute='*'
                ),
                CronTrigger(
                    day_of_week='mon-sun',
                    hour='*',
                    minute='0'
                )
            ]),
            id='weather_update'
        )

        print(f"[SCHEDULER-DEBUG] Found {len(schedules)} schedules")
        print(f"[SCHEDULER-DEBUG] Active days: {active_days_str}")
        print(f"[SCHEDULER-DEBUG] Time window: {minutely_window_start}:00 - {minutely_window_end}:00")
        
        if not scheduler.running:
            scheduler.start()
            app.logger.info("[SCHEDULER] Weather update scheduler started")
        else:
            app.logger.info("[SCHEDULER] Weather update scheduler reconfigured")


def create_app():
    app = Flask(__name__)

    # 1. Basic Configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or secrets.token_hex(32)
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=365)
    app.config['SESSION_COOKIE_SECURE'] = True
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Strict'
    app.config['BUS_CONFIG_TIMESTAMP'] = datetime.now(TIMEZONE).timestamp()
    
    # 2. Database Configuration
    database_url = os.getenv('DATABASE_URL', 'postgresql://walkingbus:password@localhost:5432/walkingbus')
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # 3. Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)

    # 4. Configure logging
    if not app.debug:
        if not os.path.exists('logs'):
            os.mkdir('logs')
        
        file_handler = RotatingFileHandler('logs/walking_bus.log', maxBytes=10240, backupCount=10)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(console_formatter)
        
        app.logger.addHandler(file_handler)
        app.logger.addHandler(console_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('Walking Bus startup')

    # 5. Register middleware
    @app.before_request
    def validate_session():
        pwa_paths = {
            'manifest.json',
            'service-worker.js',
            'static/icons/',
            'static/manifest.json'
        }
        if any(path in request.path for path in pwa_paths) or \
           (request.endpoint and 'static' in request.endpoint):
            return None

    @app.after_request
    def capture_auth_token(response):
        if 'X-Auth-Token' in response.headers:
            response.headers['Access-Control-Expose-Headers'] = 'X-Auth-Token'
        return response

    # 6. Initialize scheduler
    with app.app_context():
        def init_scheduler():
            # Only initialize scheduler in main process, not in reloader
            if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
                reconfigure_weather_scheduler(app)
        init_scheduler()

    # 7. Register blueprints
    from .routes import bp
    app.register_blueprint(bp)

    return app
