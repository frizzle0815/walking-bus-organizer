# Gunicorn configuration
worker_class = 'gevent'
workers = 4
bind = "0.0.0.0:8000"
keepalive = 5

# Increase timeout for streaming connections
worker_connections = 1000
timeout = 300

# Add logging configuration
loglevel = "info"
accesslog = "-"  # "-" means stdout
errorlog = "-"   # "-" means stderr
access_log_format = '%({x-real-ip}i)s %(l)s %(t)s "%(r)s" %(s)s %(b)s'
