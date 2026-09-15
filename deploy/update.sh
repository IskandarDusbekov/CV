#!/usr/bin/env bash
# Serverda kodni yangilash: sudo bash /home/tezrezyume/app/deploy/update.sh
set -euo pipefail

APP_DIR=/home/tezrezyume/app
APP_USER=tezrezyume

echo "==> Kod yangilanmoqda"
sudo -u "$APP_USER" git -C "$APP_DIR" pull --ff-only

echo "==> Kutubxonalar, migratsiya, statik fayllar"
sudo -u "$APP_USER" bash -c "
  cd $APP_DIR
  source venv/bin/activate
  pip install -q -r requirements.txt
  python manage.py migrate --noinput
  python manage.py collectstatic --noinput -v 0
  python manage.py check --deploy --fail-level ERROR
"

echo "==> Xizmatlar qayta ishga tushirilmoqda"
systemctl restart tezrezyume-web tezrezyume-bot
sleep 3
systemctl is-active --quiet tezrezyume-web && echo "   sayt: ishlayapti" || { echo "   sayt: XATO"; journalctl -u tezrezyume-web -n 30 --no-pager; exit 1; }
systemctl is-active --quiet tezrezyume-bot && echo "   bot:  ishlayapti" || { echo "   bot:  XATO"; journalctl -u tezrezyume-bot -n 30 --no-pager; exit 1; }

curl -fsS http://127.0.0.1/healthz/ -H "Host: $(grep -m1 '^DJANGO_ALLOWED_HOSTS=' $APP_DIR/.env | cut -d= -f2 | cut -d, -f1)" >/dev/null \
  && echo "==> Tayyor ✅" || echo "==> Diqqat: /healthz/ javob bermadi — nginx va .env ni tekshiring"
