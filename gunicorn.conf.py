# Gunicorn configuration
workers = 4
bind = "0.0.0.0:8000"
timeout = 120
keepalive = 5
worker_class = "sync"

# Add logging configuration
loglevel = "info"
accesslog = "-"  # "-" means stdout
errorlog = "-"   # "-" means stderr
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'
