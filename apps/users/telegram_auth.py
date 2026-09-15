"""Telegram orqali parolsiz kirish: token yaratish, tasdiqlash va foydalanuvchini topish/yaratish."""
import hashlib
import hmac
import json
import re
import secrets
import time
from datetime import timedelta
from urllib.parse import parse_qsl

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from .models import TelegramLoginToken, UserProfile

User = get_user_model()


def normalize_phone(raw: str) -> str:
    """Har xil formatni +998XXXXXXXXX ko'rinishiga keltiradi."""
    digits = re.sub(r"\D", "", (raw or "").strip())
    if len(digits) == 9:
        digits = "998" + digits
    return "+" + digits if digits else ""


def bot_username() -> str:
    from apps.core.models import SiteSettings

    return SiteSettings.load().effective_bot_username or "tezrezyume_bot"


WEBAPP_INIT_DATA_MAX_AGE = 24 * 60 * 60


def verify_webapp_init_data(init_data: str, bot_token: str = "", max_age: int = WEBAPP_INIT_DATA_MAX_AGE):
    """Telegram Mini App `initData` imzosini tekshiradi va Telegram foydalanuvchisini qaytaradi.

    https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
    Imzo noto'g'ri, eskirgan yoki user yo'q bo'lsa None.
    """
    bot_token = bot_token or getattr(settings, "TELEGRAM_BOT_TOKEN", "")
    if not init_data or not bot_token:
        return None
    try:
        data = dict(parse_qsl(init_data, keep_blank_values=True, strict_parsing=True))
    except ValueError:
        return None
    received = data.pop("hash", "")
    if not received:
        return None

    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()

    def _sign(fields):
        check_string = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
        return hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()

    valid = hmac.compare_digest(_sign(data), received)
    if not valid and "signature" in data:
        # Telegram klientlarining bir qismi `signature` ni hash hisobiga kiritmaydi
        valid = hmac.compare_digest(_sign({k: v for k, v in data.items() if k != "signature"}), received)
    if not valid:
        return None

    try:
        auth_date = int(data.get("auth_date", "0"))
        user = json.loads(data.get("user") or "{}")
    except (ValueError, TypeError):
        return None
    if not auth_date or time.time() - auth_date > max_age or not isinstance(user, dict) or not user.get("id"):
        return None
    return user


def create_login_token(session_key: str = "", telegram_id=None) -> TelegramLoginToken:
    return TelegramLoginToken.objects.create(
        token=secrets.token_urlsafe(24),
        session_key=session_key,
        telegram_id=telegram_id,
        expires_at=timezone.now() + timedelta(minutes=TelegramLoginToken.TTL_MINUTES),
    )


def deep_link(token: TelegramLoginToken) -> str:
    return f"https://t.me/{bot_username()}?start={token.token}"


def get_active_token(value: str):
    return (
        TelegramLoginToken.objects.filter(token=value, expires_at__gt=timezone.now())
        .exclude(status=TelegramLoginToken.STATUS_USED)
        .first()
    )


def confirm_token(token: TelegramLoginToken, *, phone, telegram_id, first_name="", last_name="", username=""):
    token.phone = normalize_phone(phone)
    token.telegram_id = telegram_id
    token.first_name = (first_name or "")[:150]
    token.last_name = (last_name or "")[:150]
    token.telegram_username = (username or "")[:100]
    token.status = TelegramLoginToken.STATUS_CONFIRMED
    token.confirmed_at = timezone.now()
    token.save()
    return token


@transaction.atomic
def consume_token(token: TelegramLoginToken):
    """Tasdiqlangan tokenni ishlatib, foydalanuvchini qaytaradi (bo'lmasa yaratadi).

    Mavjud akkaunt avval Telegram ID, keyin telefon raqam bo'yicha qidiriladi —
    raqam mos kelsa o'sha akkauntga kiriladi.
    """
    token = TelegramLoginToken.objects.select_for_update().get(pk=token.pk)
    if token.status != TelegramLoginToken.STATUS_CONFIRMED or token.is_expired:
        return None

    user = get_or_create_user(
        phone=token.phone, telegram_id=token.telegram_id,
        first_name=token.first_name, last_name=token.last_name, username=token.telegram_username,
    )
    token.status = TelegramLoginToken.STATUS_USED
    token.save(update_fields=["status"])
    return user


@transaction.atomic
def get_or_create_user(*, phone="", telegram_id=None, first_name="", last_name="", username=""):
    """Telegram ID, keyin telefon bo'yicha akkauntni topadi yoki yaratadi va Telegram'ni bog'laydi."""
    phone = normalize_phone(phone) if phone else ""
    profile = None
    if telegram_id:
        profile = UserProfile.objects.select_related("user").filter(telegram_id=telegram_id).first()
    if not profile and phone:
        profile = UserProfile.objects.select_related("user").filter(phone=phone).first()

    if profile:
        user = profile.user
    else:
        base = "u" + phone.lstrip("+") if phone else f"tg{telegram_id}"
        uname, n = base, 1
        while User.objects.filter(username=uname).exists():
            uname = f"{base}_{n}"
            n += 1
        user = User(username=uname, first_name=first_name[:150], last_name=last_name[:150])
        user.set_unusable_password()
        user.save()
        profile, _ = UserProfile.objects.get_or_create(user=user)

    profile.phone = phone or profile.phone
    profile.phone_verified = bool(profile.phone)
    if telegram_id and not UserProfile.objects.filter(telegram_id=telegram_id).exclude(pk=profile.pk).exists():
        profile.telegram_id = telegram_id
    if username:
        profile.telegram_username = username[:100]
    profile.save()

    if not user.first_name and first_name:
        user.first_name = first_name[:150]
        user.last_name = last_name[:150]
        user.save(update_fields=["first_name", "last_name"])
    return user
