# Gunicorn sozlamalari: gunicorn -c deploy/gunicorn.conf.py config.wsgi
import multiprocessing

bind = "unix:/run/mycv/gunicorn.sock"
workers = min(4, multiprocessing.cpu_count() * 2 + 1)
worker_class = "sync"
# PDF (Chromium) va AI so'rovlari 20–60 soniya olishi mumkin
timeout = 120
graceful_timeout = 30
max_requests = 500
max_requests_jitter = 50
accesslog = "-"
errorlog = "-"
loglevel = "info"
