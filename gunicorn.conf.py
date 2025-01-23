from gevent import monkey
monkey.patch_all()


# Worker lifecycle handlers
def on_starting(server):
    """Set up environment before any workers start"""
    import os
    os.environ['GUNICORN_WORKER_ID'] = '0'


def post_fork(server, worker):
    """Set worker ID after fork"""
    import os
    worker.worker_id = worker.age
    os.environ['GUNICORN_WORKER_ID'] = str(worker.age)


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
