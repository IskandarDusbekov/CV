# Gunicorn sozlamalari: gunicorn -c deploy/gunicorn.conf.py config.wsgi
import os

bind = "unix:/run/tezrezyume/gunicorn.sock"
# Har bir worker ~80 MB, PDF paytida +~250 MB (Chromium). 1 GB RAM uchun 2 ta yetadi;
# 2 GB+ serverda .env ga GUNICORN_WORKERS=3 yozing.
workers = int(os.environ.get("GUNICORN_WORKERS", "2"))
worker_class = "sync"
# PDF (Chromium) va AI so'rovlari 20–60 soniya olishi mumkin
timeout = 120
graceful_timeout = 30
max_requests = 500
max_requests_jitter = 50
accesslog = "-"
errorlog = "-"
loglevel = "info"
