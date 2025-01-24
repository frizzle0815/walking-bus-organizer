from gevent import monkey
monkey.patch_all()

# Gunicorn configuration
worker_class = 'gevent'
workers = 4
bind = "0.0.0.0:8000"
keepalive = 5

# Streaming settings
worker_connections = 1000
timeout = 300

# Logging configuration
loglevel = "warning" # info oder warning
accesslog = "-"
errorlog = "-"
access_log_format = '%({X-Forwarded-For}i)s %(l)s %(t)s "%(r)s" %(s)s %(b)s'
