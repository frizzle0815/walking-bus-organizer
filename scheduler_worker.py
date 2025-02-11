from app import create_app, db
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.pool import ProcessPoolExecutor
import pytz
import logging
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('scheduler')

def init_scheduler(app):
    """Initialize the APScheduler with database job store"""
    logger.info("Initializing scheduler...")
    
    database_url = app.config.get('SQLALCHEMY_DATABASE_URI')
    logger.info(f"Using database: {database_url}")
    
    jobstores = {
        'default': SQLAlchemyJobStore(url=database_url)
    }
    
    executors = {
        'default': ProcessPoolExecutor(max_workers=3)
    }
    
    scheduler = BackgroundScheduler(
        jobstores=jobstores,
        executors=executors,
        timezone=pytz.timezone('Europe/Berlin')
    )
    
    return scheduler

if __name__ == '__main__':
    # Create Flask app instance
    app = create_app()
    
    with app.app_context():
        # Initialize scheduler
        scheduler = init_scheduler(app)
        
        # Start the scheduler
        scheduler.start()
        logger.info('Scheduler started successfully')
        
        try:
            # Keep the script running
            while True:
                pass
        except (KeyboardInterrupt, SystemExit):
            scheduler.shutdown()
            logger.info('Scheduler shutdown complete')
