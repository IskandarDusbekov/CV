"""O'sish vositalari: do'st taklifi (referral) va aksiyalar (promo).

Taklif qoidalari (suiiste'molga qarshi):
  * kredit faqat taklif havolasi orqali kelib, YANGI akkaunt ochgan odam uchun beriladi (akkaunt 2 soatdan eski bo'lmasin);
  * har bir yangi foydalanuvchi faqat bitta taklifga hisoblanadi (Referral.invitee — unique);
  * o'zini o'zi taklif qilib bo'lmaydi, bir xil telefon raqami ham hisobga olinmaydi;
  * bloklangan taklifchi bonus olmaydi, kuniga maksimal bonus soni sozlamalarda.
"""
import logging
import re
import secrets
import threading
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.db.models import F
from django.shortcuts import redirect
from django.utils import timezone

logger = logging.getLogger(__name__)

REF_COOKIE = "ref"
REF_COOKIE_AGE = 30 * 24 * 3600
NEW_ACCOUNT_WINDOW = timedelta(hours=2)
CODE_RE = re.compile(r"^[A-Za-z0-9]{4,16}$")


# ─── Taklif kodi ──────────────────────────────────────────────────────────────

def referral_code_for(user):
    from .models import UserProfile

    profile = user.profile
    if not profile.referral_code:
        alphabet = "abcdefghjkmnpqrstuvwxyz23456789"
        for _ in range(10):
            code = "".join(secrets.choice(alphabet) for _ in range(7))
            if not UserProfile.objects.filter(referral_code=code).exists():
                UserProfile.objects.filter(pk=profile.pk, referral_code__isnull=True).update(referral_code=code)
                profile.refresh_from_db(fields=["referral_code"])
                break
    return profile.referral_code


def valid_code(code):
    return bool(code and CODE_RE.match(code))


def referral_redirect(request, code):
    """/r/<kod>/ — qisqa taklif havolasi: kodni cookie'ga yozib, bosh sahifaga olib boradi."""
    response = redirect("/?utm_source=referral")
    if valid_code(code):
        response.set_cookie(REF_COOKIE, code, max_age=REF_COOKIE_AGE, httponly=True, samesite="Lax", secure=request.is_secure())
    return response


class ReferralCaptureMiddleware:
    """Istalgan sahifaga ?ref=kod bilan kelinsa ham kodni eslab qoladi."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        code = request.GET.get("ref", "")
        if valid_code(code) and request.COOKIES.get(REF_COOKIE) != code:
            response.set_cookie(REF_COOKIE, code, max_age=REF_COOKIE_AGE, httponly=True, samesite="Lax", secure=request.is_secure())
        return response


def _notify(chat_id, text):
    if not chat_id:
        return

    def run():
        try:
            from .bot import send_message

            send_message(chat_id, text)
        except Exception:
            logger.warning("Growth notify failed", exc_info=True)

    threading.Thread(target=run, daemon=True).start()


def apply_referral(user, code, via="site"):
    """Taklif bonusini beradi. Muvaffaqiyatli bo'lsa Referral qaytaradi, aks holda None."""
    from apps.core.activity import log_activity
    from apps.core.models import SiteSettings

    from .models import Referral, UserProfile

    site = SiteSettings.load()
    if not site.referral_enabled or not valid_code(code) or user is None:
        return None
    if timezone.now() - user.date_joined > NEW_ACCOUNT_WINDOW or Referral.objects.filter(invitee=user).exists():
        return None
    inviter_profile = UserProfile.objects.select_related("user").filter(referral_code=code).first()
    if inviter_profile is None or inviter_profile.user_id == user.pk or inviter_profile.is_blocked:
        return None
    invitee_profile = getattr(user, "profile", None)
    if invitee_profile and invitee_profile.phone and invitee_profile.phone == inviter_profile.phone:
        return None
    today = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    over_limit = Referral.objects.filter(inviter=inviter_profile.user, created_at__gte=today).count() >= site.referral_daily_limit
    inviter_credits = 0 if over_limit else site.referral_inviter_credits
    invitee_credits = site.referral_invitee_credits

    try:
        with transaction.atomic():
            ref = Referral.objects.create(inviter=inviter_profile.user, invitee=user, via=via,
                                          inviter_credits=inviter_credits, invitee_credits=invitee_credits)
            if inviter_credits:
                UserProfile.objects.filter(pk=inviter_profile.pk).update(credits=F("credits") + inviter_credits)
            if invitee_credits:
                UserProfile.objects.filter(user=user).update(credits=F("credits") + invitee_credits)
    except IntegrityError:  # parallel so'rov allaqachon yozgan
        return None

    log_activity(None, "referral", user=inviter_profile.user, invitee=user.pk, credits=inviter_credits, via=via)
    if inviter_credits:
        name = user.first_name or "Do'stingiz"
        _notify(inviter_profile.telegram_id,
                f"🎉 <b>{name}</b> sizning havolangiz orqali ro'yxatdan o'tdi!\n"
                f"Hisobingizga <b>+{inviter_credits} kredit</b> qo'shildi. Rahmat! 🙌")
    return ref


# ─── Aksiyalar ────────────────────────────────────────────────────────────────

def running_promos():
    from .models import Promo

    now = timezone.now()
    return Promo.objects.filter(is_active=True, starts_at__lte=now, ends_at__gte=now)


def apply_promos(user):
    """Joriy aksiyalar bo'yicha bonus kredit beradi (har bir aksiya uchun bir marta). Berilgan kreditlar yig'indisi."""
    from apps.core.activity import log_activity

    from .models import PromoGrant, UserProfile

    total = 0
    for promo in running_promos():
        if promo.audience == promo.AUDIENCE_NEW and not (promo.starts_at <= user.date_joined <= promo.ends_at):
            continue
        if not promo.bonus_credits:
            continue
        try:
            with transaction.atomic():
                PromoGrant.objects.create(promo=promo, user=user, credits=promo.bonus_credits)
                UserProfile.objects.filter(user=user).update(credits=F("credits") + promo.bonus_credits)
        except IntegrityError:
            continue
        total += promo.bonus_credits
        log_activity(None, "promo_bonus", user=user, promo=promo.name, credits=promo.bonus_credits)
    return total


def on_signed_in(request, user):
    """Saytga har kirishda: taklif cookie'si va aksiyalar. Foydalanuvchiga xabar matnini qaytaradi."""
    notes = []
    code = request.COOKIES.get(REF_COOKIE, "") if request is not None else ""
    ref = apply_referral(user, code, via="site") if code else None
    if ref and ref.invitee_credits:
        notes.append(f"Do'stingiz taklifi uchun +{ref.invitee_credits} kredit")
    bonus = apply_promos(user)
    if bonus:
        notes.append(f"🎁 Aksiya: hisobingizga +{bonus} kredit qo'shildi")
    return notes


def on_bot_user(user, telegram_id):
    """Bot orqali raqam yuborilganda (akkaunt shu yerda yaratilishi mumkin)."""
    from .models import PendingReferral

    pending = PendingReferral.objects.filter(telegram_id=telegram_id).first()
    if pending:
        apply_referral(user, pending.code, via="bot")
        pending.delete()
    return apply_promos(user)
