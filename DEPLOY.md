# mycv.uz — VPS serverga joylash qo'llanmasi

Ubuntu **24.04 LTS** uchun yozilgan: Python 3.12, PostgreSQL, Nginx, Gunicorn, systemd va Let's Encrypt SSL.
Buyruqlarni ketma-ket bajaring. `mycv.uz` o'rniga o'z domeningizni yozing.

> **Tavsiya etilgan server:** 2 vCPU, 2–4 GB RAM, 30 GB disk.
> PDF Chromium orqali yaratiladi va har bir PDF uchun ~300 MB RAM kerak bo'ladi.

---

## 0. Oldindan tayyorlab qo'ying

| Nima | Qayerdan |
|---|---|
| Domen, A-yozuv server IP siga yo'naltirilgan | domen registratori paneli |
| `OPENAI_API_KEY` | https://platform.openai.com/api-keys |
| `TELEGRAM_BOT_TOKEN` | Telegram → @BotFather → `/newbot` |
| Admin Telegram chat ID | Telegram → @userinfobot → `/start` |

---

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

# Ilova uchun alohida foydalanuvchi
adduser --disabled-password --gecos "" mycv
usermod -aG www-data mycv
chmod 755 /home/mycv
```

## 2. PostgreSQL bazasi

```bash
sudo -u postgres psql
```

```sql
CREATE DATABASE mycv;
CREATE USER mycv WITH PASSWORD 'KUCHLI_PAROL';
ALTER ROLE mycv SET client_encoding TO 'utf8';
ALTER ROLE mycv SET timezone TO 'Asia/Tashkent';
GRANT ALL PRIVILEGES ON DATABASE mycv TO mycv;
ALTER DATABASE mycv OWNER TO mycv;
\q
```

## 3. Kodni yuklash

```bash
su - mycv
git clone https://github.com/SIZNING/REPO.git app
cd app
```

Git ishlatmasangiz, kompyuteringizdan yuklang (`venv`, `db.sqlite3`, `.env` ni yubormang):

```bash
# kompyuterda (PowerShell yoki Git Bash):
scp -r apps config templates static deploy manage.py requirements.txt .env.example mycv@SERVER_IP:/home/mycv/app/
```

## 4. Virtual muhit va kutubxonalar

```bash
cd /home/mycv/app
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
/home/mycv/app/venv/bin/python -m playwright install-deps chromium
su - mycv && cd app && source venv/bin/activate
```

## 5. `.env` sozlash

```bash
cp .env.example .env
nano .env
```

Albatta o'zgartiring:
- `SECRET_KEY` — `python -c "import secrets; print(secrets.token_urlsafe(50))"`
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
cp /home/mycv/app/deploy/mycv-web.service /etc/systemd/system/
cp /home/mycv/app/deploy/mycv-bot.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now mycv-web mycv-bot
systemctl status mycv-web mycv-bot --no-pager
```

## 8. Nginx va SSL

```bash
cp /home/mycv/app/deploy/nginx.conf /etc/nginx/sites-available/mycv
nano /etc/nginx/sites-available/mycv          # domenni o'zgartiring
ln -s /etc/nginx/sites-available/mycv /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

certbot --nginx -d mycv.uz -d www.mycv.uz --redirect -m email@misol.uz --agree-tos -n
```

SSL ishlashini tekshirgach, `.env` da `SECURE_HSTS_SECONDS=31536000` qo'yib, `systemctl restart mycv-web` qiling.

## 9. Admin paneldagi birinchi sozlamalar

`https://mycv.uz/admin/` ga kiring:

1. **Sayt sozlamalari** — karta raqami va egasi, bot username, **admin chat ID lari** (yangi cheklar shu yerga keladi), aloqa ma'lumotlari, bepul limitlar, AI modeli va narxlari.
2. **Tariflar va paketlar** — kredit paketlari (`1 ta CV`, `3 ta CV`…) va Pro narxlari.
3. **Sahifalar** — «Biz haqimizda» va «Aloqa» matnlari.
4. Botni sinab ko'ring: botga `/start` yozing → raqamni yuboring → `/tolov` → paket tanlang → test chek yuboring → admin panelda **To'lovlar** bo'limida tasdiqlang.

---

## Yangilash (keyingi deploylar)

```bash
su - mycv && cd app
git pull                     # yoki scp bilan yangi fayllar
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
exit
systemctl restart mycv-web mycv-bot
```

## Zaxira nusxa (backup)

```bash
# Baza (har kuni cron bilan)
sudo -u postgres pg_dump mycv | gzip > /root/backup/mycv-$(date +%F).sql.gz
# Media (rasmlar, cheklar)
tar czf /root/backup/media-$(date +%F).tar.gz -C /home/mycv/app media
```

Cron (`crontab -e`, root):

```
0 3 * * * mkdir -p /root/backup && sudo -u postgres pg_dump mycv | gzip > /root/backup/mycv-$(date +\%F).sql.gz && find /root/backup -mtime +14 -delete
```

## Loglar

```bash
journalctl -u mycv-web -f          # sayt
journalctl -u mycv-bot -f          # bot
tail -f /var/log/nginx/error.log   # nginx
```

Barcha `ERROR` darajadagi xatolar admin panelning **Xatoliklar** bo'limiga ham yoziladi (qayerda, kimda, traceback bilan).

---

## Tez-tez uchraydigan xatolar va yechimlar

| Belgisi | Sababi | Yechim |
|---|---|---|
| **502 Bad Gateway** | gunicorn ishlamayapti | `journalctl -u mycv-web -n 50` — odatda `.env` xatosi yoki kutubxona yetishmaydi. Tuzatib `systemctl restart mycv-web` |
| `ImproperlyConfigured: Productionda SECRET_KEY ni...` | `DEBUG=False`, lekin `SECRET_KEY` o'rnatilmagan | `.env` ga `SECRET_KEY=...` yozing |
| **400 Bad Request** | domen `DJANGO_ALLOWED_HOSTS` da yo'q | `.env` ga domenni qo'shing, restart |
| **403 CSRF verification failed** (forma/admin) | `DJANGO_CSRF_TRUSTED_ORIGINS` da `https://` li domen yo'q | `https://mycv.uz` ni qo'shing, restart |
| Sahifa cheksiz qayta yo'naltiriladi | `SECURE_SSL_REDIRECT=True`, nginx `X-Forwarded-Proto` yubormayapti | `deploy/nginx.conf` dagi `proxy_set_header X-Forwarded-Proto $scheme;` qatori borligini tekshiring |
| CSS/JS yuklanmaydi (sayt «yalang'och») | `collectstatic` qilinmagan yoki nginx fayllarni o'qiy olmaydi | `python manage.py collectstatic --noinput`, `chmod 755 /home/mycv` |
| `collectstatic`: `MissingFileError ... bootstrap.bundle.min.js.map` | hash'li Manifest storage yoqilgan | `settings.py` da `whitenoise.storage.CompressedStaticFilesStorage` bo'lishi kerak (loyihada shunday) |
| **PDF yaratishda xatolik** | Chromium yoki uning tizim kutubxonalari yo'q | `python -m playwright install chromium` (mycv foydalanuvchisi) va `playwright install-deps chromium` (root) |
| PDF `Timeout` / server qotib qoladi | RAM yetmaydi | `deploy/gunicorn.conf.py` da `workers = 2`, swap qo'shing: `fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile` |
| **504 Gateway Timeout** (AI yoki PDF) | nginx javobni kutmaydi | `proxy_read_timeout 130s` borligini tekshiring |
| Bot javob bermaydi, logda `409 Conflict` | bot boshqa joyda ham ishlayapti (masalan, kompyuteringizda) | Bitta token bilan faqat **bitta** `runbot` ishlashi mumkin — lokal botni to'xtating |
| Bot: `TELEGRAM_BOT_TOKEN sozlanmagan` | `.env` o'qilmayapti | `EnvironmentFile=` yo'lini va `.env` dagi tokenni tekshiring |
| Botdagi «Saytga kirish» tugmasi chiqmaydi | `SITE_URL` `https://` emas yoki localhost | `SITE_URL=https://mycv.uz` |
| Yangi cheklar adminga kelmaydi | «Admin chat ID lari» bo'sh yoki admin botga `/start` bosmagan | ID ni @userinfobot dan oling va botga `/start` yozing |
| AI: `AI hozir javob bermadi` | OpenAI kaliti noto'g'ri, balans tugagan yoki model nomi xato | Admin → Xatoliklar dagi matnni o'qing. Admin → Sayt sozlamalari → `ai_model` ni tekshiring |
| `psycopg.OperationalError: password authentication failed` | DB paroli mos emas | `.env` dagi `DB_PASSWORD` ni 2-bosqich bilan solishtiring |
| `permission denied for schema public` | PostgreSQL 15+ da bazaga egalik berilmagan | `ALTER DATABASE mycv OWNER TO mycv;` |
| Rasm yoki chek yuklanmaydi (`413`) | nginx fayl hajmini cheklaydi | `client_max_body_size 12M;` |
| Migratsiya: `UNIQUE constraint failed: cv_cv.public_id` | eski migratsiya qo'lda o'zgartirilgan | `0008` migratsiyasi UUID larni o'zi to'ldiradi — faylni o'zgartirmang, `migrate` ni qayta ishga tushiring |

## Xavfsizlik bo'yicha eslatmalar

- `.env` faylini hech qachon git ga qo'shmang (`.gitignore` da bor).
- Admin panel manzilini o'zgartirish tavsiya etiladi: `config/urls.py` da `admin/` → masalan `boshqaruv-7x/`.
- CV manzillari UUID bilan (`/cv/preview/3f2c…/`), shuning uchun raqamni o'zgartirib boshqa CV ni ochib bo'lmaydi.
- To'lov cheklari `/media/receipts/` orqali ochilmaydi — ular faqat admin panelda ko'rinadi.
- Shubhali foydalanuvchi yoki IP ni admin paneldan bloklang: **Foydalanuvchilar → ⛔ Bloklash** yoki **Bloklangan IP lar**.
