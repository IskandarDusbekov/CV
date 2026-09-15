# tezrezyume.uz — VPS serverga joylash qo'llanmasi

Ubuntu **24.04 LTS** uchun yozilgan: Python 3.12, PostgreSQL, Nginx, Gunicorn, systemd va Let's Encrypt SSL.
Buyruqlarni ketma-ket bajaring. `tezrezyume.uz` o'rniga o'z domeningizni yozing.

> **Server:** boshlash uchun 1 vCPU / 1 GB RAM yetadi (swap 2 GB bo'lishi shart — 1-bosqich).
> Kuniga ~100+ PDF yuklab olinsa yoki `free -h` da swap doim band tursa — 2 GB RAM ga o'ting va `.env` ga `GUNICORN_WORKERS=3` yozing.
> PDF Chromium orqali yaratiladi va har bir PDF paytida ~250 MB RAM qo'shimcha ketadi.

---

## 0. Oldindan tayyorlab qo'ying

| Nima | Qayerdan |
|---|---|
| Domen, A-yozuv server IP siga yo'naltirilgan | domen registratori paneli |
| `OPENAI_API_KEY` | https://platform.openai.com/api-keys |
| `TELEGRAM_BOT_TOKEN` | Telegram → @BotFather → `/newbot` |
| Admin Telegram chat ID | Telegram → @userinfobot → `/start` |

---

## 0.5. Domenni serverga ulash (DNS)

Domen sotib olgan joyingizda (registrator paneli → DNS) ikkita yozuv qo'shing:

| Turi | Nomi (Host) | Qiymati | TTL |
|---|---|---|---|
| A | `@` | `SERVER_IP` | 3600 |
| A | `www` | `SERVER_IP` | 3600 |

Tekshirish (kompyuterda): `nslookup tezrezyume.uz` — server IP si chiqishi kerak. Odatda 5–30 daqiqa, ba'zan 24 soatgacha tarqaladi.
SSL (8-bosqich) faqat DNS tarqalgandan keyin ishlaydi.

## 1. Serverni tayyorlash (root sifatida)

```bash
ssh root@SERVER_IP

apt update && apt upgrade -y
apt install -y python3 python3-venv python3-dev build-essential git nginx \
               postgresql postgresql-contrib libpq-dev certbot python3-certbot-nginx ufw

# Firewall
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw --force enable

# Swap 2 GB (1 GB RAM li serverda PDF paytida xotira tugab qolmasligi uchun)
swapoff -a
rm -f /swap.img /swapfile
fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
sed -i '/^\/swap.img/d' /etc/fstab
echo 'vm.swappiness=10' > /etc/sysctl.d/99-swap.conf && sysctl --system >/dev/null
free -h   # Swap: 2.0Gi ko'rinishi kerak

# Vaqt zonasi
timedatectl set-timezone Asia/Tashkent

# Ilova uchun alohida foydalanuvchi
adduser --disabled-password --gecos "" tezrezyume
usermod -aG www-data tezrezyume
chmod 755 /home/tezrezyume
```

## 2. PostgreSQL bazasi

```bash
sudo -u postgres psql
```

```sql
CREATE DATABASE tezrezyume;
CREATE USER tezrezyume WITH PASSWORD 'KUCHLI_PAROL';
ALTER ROLE tezrezyume SET client_encoding TO 'utf8';
ALTER ROLE tezrezyume SET timezone TO 'Asia/Tashkent';
GRANT ALL PRIVILEGES ON DATABASE tezrezyume TO tezrezyume;
ALTER DATABASE tezrezyume OWNER TO tezrezyume;
\q
```

## 3. Kodni yuklash

```bash
su - tezrezyume
git clone https://github.com/SIZNING/REPO.git app
cd app
```

Git ishlatmasangiz, kompyuteringizdan yuklang (`venv`, `db.sqlite3`, `.env` ni yubormang):

```bash
# kompyuterda (PowerShell yoki Git Bash):
scp -r apps config templates static deploy manage.py requirements.txt .env.example tezrezyume@SERVER_IP:/home/tezrezyume/app/
```

## 4. Virtual muhit va kutubxonalar

```bash
cd /home/tezrezyume/app
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip wheel
pip install -r requirements.txt

# PDF uchun Chromium
python -m playwright install chromium
```

Chromium tizim kutubxonalarini root bilan o'rnating (bir marta):

```bash
exit   # root ga qaytish
/home/tezrezyume/app/venv/bin/python -m playwright install-deps chromium
su - tezrezyume && cd app && source venv/bin/activate
```

## 5. `.env` sozlash

```bash
cp .env.example .env
nano .env
```

Albatta o'zgartiring:
- `SECRET_KEY` — `python -c "import secrets; print(secrets.token_urlsafe(50))"`
- `ADMIN_URL` — Django admin manzili, masalan `boshqaruv-7k2x` (kundalik ish uchun `/panel/` bor)
- `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, `SITE_URL`
- `DB_PASSWORD` — 2-bosqichdagi parol
- `OPENAI_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_BOT_USERNAME`

```bash
chmod 600 .env
```

## 6. Baza, statik fayllar, admin

```bash
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
mkdir -p media && chmod 775 media

# Tekshiruv — xato bo'lmasligi kerak
python manage.py check --deploy
```

## 7. Gunicorn va bot (systemd)

```bash
exit   # root
cp /home/tezrezyume/app/deploy/tezrezyume-web.service /etc/systemd/system/
cp /home/tezrezyume/app/deploy/tezrezyume-bot.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now tezrezyume-web tezrezyume-bot
systemctl status tezrezyume-web tezrezyume-bot --no-pager
```

## 8. Nginx va SSL

```bash
cp /home/tezrezyume/app/deploy/nginx.conf /etc/nginx/sites-available/tezrezyume
nano /etc/nginx/sites-available/tezrezyume          # domenni o'zgartiring
ln -s /etc/nginx/sites-available/tezrezyume /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

certbot --nginx -d tezrezyume.uz -d www.tezrezyume.uz --redirect -m email@misol.uz --agree-tos -n
```

SSL ishlashini tekshirgach, `.env` da `SECURE_HSTS_SECONDS=31536000` qo'yib, `systemctl restart tezrezyume-web` qiling.

## 9. Birinchi sozlamalar

Kundalik ish — **`https://tezrezyume.uz/panel/`** (6-bosqichdagi superuser login/paroli bilan kiring):

1. **Sozlamalar va narxlar** → **Sayt nomi** ga domeningizni yozing (masalan `tezrezyume.uz`) — logotip, sarlavhalar, CV dagi belgi va bot matnlari shu nomdan olinadi.
2. Shu sahifada — karta raqami va egasi, bot username, **admin chat ID lari** (yangi cheklar shu yerga keladi), aloqa ma'lumotlari, limitlar, AI modeli; yuqoridagi jadvalda narxlar.
3. Botni sinab ko'ring: botga `/start` → raqamni yuboring → `/tolov` → paket tanlang → test chek yuboring → panelda **To'lovlar** da tasdiqlang.

Kam ishlatiladigan narsalar (sahifalar matni, brendinglar) — `https://tezrezyume.uz/ADMIN_URL/` (Django admin).

---

## Yangilash (keyingi deploylar)

Kompyuterda o'zgarishlarni GitHub ga yuboring (`git push`), keyin serverda bitta buyruq:

```bash
sudo bash /home/tezrezyume/app/deploy/update.sh
```

Skript: `git pull` → kutubxonalar → migratsiya → statik fayllar → tekshiruv → sayt va botni qayta ishga tushirish → `/healthz/` ni tekshirish.

Private repo bo'lsa, serverda bir marta deploy key qo'shing:

```bash
sudo -u tezrezyume ssh-keygen -t ed25519 -N "" -f /home/tezrezyume/.ssh/id_ed25519
cat /home/tezrezyume/.ssh/id_ed25519.pub   # GitHub → repo → Settings → Deploy keys → Add
sudo -u tezrezyume git -C /home/tezrezyume/app remote set-url origin git@github.com:SIZNING/REPO.git
```

## Monitoring

`https://tezrezyume.uz/healthz/` — sayt va baza ishlasa `{"status": "ok"}` qaytaradi. Uni bepul UptimeRobot yoki BetterStack ga qo'shing — sayt tushib qolsa SMS/Telegram xabar keladi.

## Zaxira nusxa (backup)

```bash
# Baza (har kuni cron bilan)
sudo -u postgres pg_dump tezrezyume | gzip > /root/backup/tezrezyume-$(date +%F).sql.gz
# Media (rasmlar, cheklar)
tar czf /root/backup/media-$(date +%F).tar.gz -C /home/tezrezyume/app media
```

Cron (`crontab -e`, root):

```
0 3 * * * mkdir -p /root/backup && sudo -u postgres pg_dump tezrezyume | gzip > /root/backup/tezrezyume-$(date +\%F).sql.gz && find /root/backup -mtime +14 -delete
```

## Loglar

```bash
journalctl -u tezrezyume-web -f          # sayt
journalctl -u tezrezyume-bot -f          # bot
tail -f /var/log/nginx/error.log   # nginx
```

Barcha `ERROR` darajadagi xatolar admin panelning **Xatoliklar** bo'limiga ham yoziladi (qayerda, kimda, traceback bilan).

---

## Tez-tez uchraydigan xatolar va yechimlar

| Belgisi | Sababi | Yechim |
|---|---|---|
| **502 Bad Gateway** | gunicorn ishlamayapti | `journalctl -u tezrezyume-web -n 50` — odatda `.env` xatosi yoki kutubxona yetishmaydi. Tuzatib `systemctl restart tezrezyume-web` |
| `ImproperlyConfigured: Productionda SECRET_KEY ni...` | `DEBUG=False`, lekin `SECRET_KEY` o'rnatilmagan | `.env` ga `SECRET_KEY=...` yozing |
| **400 Bad Request** | domen `DJANGO_ALLOWED_HOSTS` da yo'q | `.env` ga domenni qo'shing, restart |
| **403 CSRF verification failed** (forma/admin) | `DJANGO_CSRF_TRUSTED_ORIGINS` da `https://` li domen yo'q | `https://tezrezyume.uz` ni qo'shing, restart |
| Sahifa cheksiz qayta yo'naltiriladi | `SECURE_SSL_REDIRECT=True`, nginx `X-Forwarded-Proto` yubormayapti | `deploy/nginx.conf` dagi `proxy_set_header X-Forwarded-Proto $scheme;` qatori borligini tekshiring |
| CSS/JS yuklanmaydi (sayt «yalang'och») | `collectstatic` qilinmagan yoki nginx fayllarni o'qiy olmaydi | `python manage.py collectstatic --noinput`, `chmod 755 /home/tezrezyume` |
| `update.sh: $'\r': command not found` | fayl Windows qator oxiri (CRLF) bilan kelgan | `.gitattributes` buni oldini oladi; bir martalik: `sed -i 's/\r$//' deploy/*.sh deploy/*.service` |
| Admin panel 404 | `ADMIN_URL` o'zgargan | `.env` dagi `ADMIN_URL` manzilidan kiring; kundalik ish uchun `/panel/` |
| `collectstatic`: `MissingFileError ... bootstrap.bundle.min.js.map` | hash'li Manifest storage yoqilgan | `settings.py` da `whitenoise.storage.CompressedStaticFilesStorage` bo'lishi kerak (loyihada shunday) |
| **PDF yaratishda xatolik** | Chromium yoki uning tizim kutubxonalari yo'q | `python -m playwright install chromium` (tezrezyume foydalanuvchisi) va `playwright install-deps chromium` (root) |
| PDF `Timeout` / server qotib qoladi | RAM yetmaydi | `free -h` bilan tekshiring; swap 2 GB ekanini (1-bosqich) va `.env` da `GUNICORN_WORKERS=2` ekanini tekshiring. Baribir yetmasa — 2 GB RAM li tarifga o'ting |
| **504 Gateway Timeout** (AI yoki PDF) | nginx javobni kutmaydi | `proxy_read_timeout 130s` borligini tekshiring |
| Bot javob bermaydi, logda `409 Conflict` | bot boshqa joyda ham ishlayapti (masalan, kompyuteringizda) | Bitta token bilan faqat **bitta** `runbot` ishlashi mumkin — lokal botni to'xtating |
| Bot: `TELEGRAM_BOT_TOKEN sozlanmagan` | `.env` o'qilmayapti | `EnvironmentFile=` yo'lini va `.env` dagi tokenni tekshiring |
| Botdagi «Saytga kirish» tugmasi chiqmaydi | `SITE_URL` `https://` emas yoki localhost | `SITE_URL=https://tezrezyume.uz` |
| Yangi cheklar adminga kelmaydi | «Admin chat ID lari» bo'sh yoki admin botga `/start` bosmagan | ID ni @userinfobot dan oling va botga `/start` yozing |
| AI: `AI hozir javob bermadi` | OpenAI kaliti noto'g'ri, balans tugagan yoki model nomi xato | Admin → Xatoliklar dagi matnni o'qing. Admin → Sayt sozlamalari → `ai_model` ni tekshiring |
| `psycopg.OperationalError: password authentication failed` | DB paroli mos emas | `.env` dagi `DB_PASSWORD` ni 2-bosqich bilan solishtiring |
| `permission denied for schema public` | PostgreSQL 15+ da bazaga egalik berilmagan | `ALTER DATABASE tezrezyume OWNER TO tezrezyume;` |
| Rasm yoki chek yuklanmaydi (`413`) | nginx fayl hajmini cheklaydi | `client_max_body_size 12M;` |
| Migratsiya: `UNIQUE constraint failed: cv_cv.public_id` | eski migratsiya qo'lda o'zgartirilgan | `0008` migratsiyasi UUID larni o'zi to'ldiradi — faylni o'zgartirmang, `migrate` ni qayta ishga tushiring |

## Xavfsizlik bo'yicha eslatmalar

- `.env` faylini hech qachon git ga qo'shmang (`.gitignore` da bor).
- Django admin manzilini `.env` dagi `ADMIN_URL` bilan taxmin qilib bo'lmaydigan qiling. `/panel/` faqat staff foydalanuvchilarga ochiladi.
- Superuser parolini kuchli qiling: `python manage.py changepassword admin`.
- CV manzillari UUID bilan (`/cv/preview/3f2c…/`), shuning uchun raqamni o'zgartirib boshqa CV ni ochib bo'lmaydi.
- To'lov cheklari `/media/receipts/` orqali ochilmaydi — ular faqat admin panelda ko'rinadi.
- Shubhali foydalanuvchi yoki IP ni admin paneldan bloklang: **Foydalanuvchilar → ⛔ Bloklash** yoki **Bloklangan IP lar**.
