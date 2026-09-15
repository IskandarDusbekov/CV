"""Telegram orqali parolsiz kirish: token yaratish, tasdiqlash va foydalanuvchini topish/yaratish."""
import re
import secrets
from datetime import timedelta

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
