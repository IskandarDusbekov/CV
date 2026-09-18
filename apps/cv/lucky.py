"""
«Siz bugungi baxtli foydalanuvchimizsiz» sovg'asi.

Foydalanuvchi rezyumesini ochganda (agar sovg'a paneldan yoqilgan bo'lsa) unga bir marta sovg'a beriladi:
shu rezyumeni istalgan shablonda — Pro shablonlarda ham — PDF qilib yuklab oladi. Faylda doim sayt belgisi
qoladi, shuning uchun har bir sovg'a bepul reklama bo'lib ishlaydi.

Hamma narsa panel → «Sovg'a» bo'limidan boshqariladi: yoqish, kimga, matn, tugmalar va kunlik chegara.
"""
from django.db import IntegrityError
from django.utils import timezone

from .models import CV, LuckyGift, LuckyGrant


def _eligible(gift, user):
    profile = getattr(user, "profile", None)
    if profile is None or profile.is_blocked:
        return False
    if gift.audience == LuckyGift.AUDIENCE_NEW:
        return (timezone.now() - profile.created_at).days < gift.new_user_days
    if gift.audience == LuckyGift.AUDIENCE_NOT_PAID:
        paid = profile.has_active_premium or profile.credits or CV.objects.filter(user=user, is_unlocked=True).exists()
        return not paid
    return True


def grant_for(request, cv):
    """Shu rezyume uchun sovg'ani qaytaradi; shart bo'lsa yangisini beradi. Sovg'a yo'q bo'lsa — None."""
    user = request.user
    if not user.is_authenticated or cv.user_id != user.pk:
        return None
    grant = LuckyGrant.objects.filter(user=user).first()
    if grant is not None:
        return grant if grant.cv_id == cv.pk else None

    gift = LuckyGift.load()
    if not gift.is_active or not _eligible(gift, user):
        return None
    if gift.daily_limit:
        today = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
        if LuckyGrant.objects.filter(created_at__gte=today).count() >= gift.daily_limit:
            return None

    try:
        grant = LuckyGrant.objects.create(user=user, cv=cv, template_code=cv.selected_template)
    except IntegrityError:  # parallel so'rov allaqachon bergan
        return LuckyGrant.objects.filter(user=user, cv=cv).first()

    CV.objects.filter(pk=cv.pk).update(lucky_pdf=True)
    cv.lucky_pdf = True
    from apps.core.activity import log_activity

    log_activity(request, "lucky_gift", cv=str(cv.public_id))
    return grant


def context(request, cv):
    """Preview sahifasi uchun: sovg'a matni, tugmalari va berilgan sovg'a."""
    grant = grant_for(request, cv)
    if grant is None:
        return {}
    return {"lucky_gift": LuckyGift.load(), "lucky_grant": grant}


def save_reaction(request, cv, value):
    """Sovg'a ostidagi tugma bosilganda javobni yozadi. Qaytaradi: rahmat matni yoki ''."""
    gift = LuckyGift.load()
    grant = LuckyGrant.objects.filter(user=request.user, cv=cv).first()
    if grant is None or value not in gift.options:
        return ""
    if not grant.reaction:
        LuckyGrant.objects.filter(pk=grant.pk, reaction="").update(reaction=value, reacted_at=timezone.now())
    return gift.thanks_text


def mark_shown(request, cv):
    """Tabrik oynasi ko'rsatildi — ikkinchi marta ochilmaydi."""
    LuckyGrant.objects.filter(user=request.user, cv=cv, shown=False).update(shown=True)


def mark_downloaded(user, cv):
    if getattr(cv, "lucky_pdf", False) and getattr(user, "is_authenticated", False):
        LuckyGrant.objects.filter(user=user, cv=cv, downloaded=False).update(downloaded=True, template_code=cv.selected_template)
