# Gunicorn configuration for EC2 production deployment
# Used by: gunicorn -c gunicorn.conf.py app:app

import multiprocessing

# Bind to Unix socket — Nginx will proxy to this
bind = "unix:/tmp/lostfound.sock"

# Number of worker processes
# Formula: (2 x CPU cores) + 1
# t2.micro has 1 vCPU → 3 workers
workers = multiprocessing.cpu_count() * 2 + 1

# Worker class
worker_class = "sync"

# Timeout (seconds) — kill worker if it takes longer than this
timeout = 120

# Keep-alive connections
keepalive = 5

# Logging
accesslog = "/home/ubuntu/lostfound-cloud/logs/gunicorn_access.log"
errorlog  = "/home/ubuntu/lostfound-cloud/logs/gunicorn_error.log"
loglevel  = "info"

# Process naming
proc_name = "lostfound_gunicorn"

# Reload on code change (disable in production, enable for debugging)
reload = False
