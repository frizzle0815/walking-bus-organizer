from gevent import monkey
import logging
monkey.patch_all()


# Worker lifecycle handlers
def on_starting(server):
    import os
    os.environ['GUNICORN_WORKER_ID'] = '0'
    logging.info(f"[MASTER] Setting initial worker ID: {os.environ.get('GUNICORN_WORKER_ID')}")


def worker_ready(worker):
    """Called when worker is ready to accept requests"""
    import os
    import logging
    from app import create_app, reconfigure_weather_scheduler
    
    if worker.age == 0:  # Only in first worker
        app = create_app()
        with app.app_context():
            logging.info(f"[WORKER-0] Initializing scheduler in ready worker")
            reconfigure_weather_scheduler(app)


def post_fork(server, worker):
    """Set worker ID after fork"""
    import os
    import logging
    # First worker gets ID 0, others increment from there
    worker_id = worker.age - 1 if worker.age > 0 else 0
    os.environ['GUNICORN_WORKER_ID'] = str(worker_id)
    logging.info(f"[WORKER] Post-fork worker {worker.age} assigned ID {worker_id}")


def worker_int(worker):
    """Clean shutdown of worker"""
    from app import scheduler
    if scheduler.running:
        scheduler.shutdown()


def worker_abort(worker):
    """Emergency shutdown of worker"""
    from app import scheduler
    if scheduler.running:
        scheduler.shutdown()


# Gunicorn configuration
worker_class = 'gevent'
workers = 4
bind = "0.0.0.0:8000"
keepalive = 5

# Streaming settings
worker_connections = 1000
timeout = 300

# Logging configuration
loglevel = "info"  # Changed to info for better visibility
accesslog = "-"
errorlog = "-"
access_log_format = '%({X-Forwarded-For}i)s %(l)s %(t)s "%(r)s" %(s)s %(b)s'

# Application loading
preload_app = True
