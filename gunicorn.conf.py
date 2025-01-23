from gevent import monkey
import logging
monkey.patch_all()


# Worker lifecycle handlers
def on_starting(server):
    import os
    os.environ['GUNICORN_WORKER_ID'] = '0'
    logging.info(f"[MASTER] Setting initial worker ID: {os.environ.get('GUNICORN_WORKER_ID')}")


def post_fork(server, worker):
    """Set worker ID after fork"""
    import os
    import logging
    worker.worker_id = worker.age
    os.environ['GUNICORN_WORKER_ID'] = str(worker.age)
    logging.info(f"[WORKER] Post-fork worker {worker.age} with ID {worker.worker_id}")


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
