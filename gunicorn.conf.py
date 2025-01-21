from gevent import monkey
monkey.patch_all()

# Gunicorn configuration
worker_class = 'gevent'
workers = 4
bind = "0.0.0.0:8000"
keepalive = 5

# Increase timeout for streaming connections
worker_connections = 1000
timeout = 300

# Add logging configuration
loglevel = "warning" # info oder warning
accesslog = "-"  # "-" means stdout
errorlog = "-"   # "-" means stderr
access_log_format = '%({X-Forwarded-For}i)s %(l)s %(t)s "%(r)s" %(s)s %(b)s'

# Preload app to ensure scheduler runs only once
preload_app = True
