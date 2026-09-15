"""
AI limitlari — kim nechta CV yaratishi va vakansiyaga moslashtirishi mumkin.
Barcha raqamlar admin paneldan o'zgaradi (Sayt sozlamalari va Tariflar).

  Bepul          : site.free_cv_limit ta CV, site.free_tailor_limit ta moslashtirish (umumiy)
  Ochilgan CV    : shu CV uchun site.tailor_per_unlocked_cv ta moslashtirish (kredit bilan ochilgan)
  Pro            : obuna davri ichida plan.max_cvs ta CV va plan.max_tailorings ta moslashtirish

Anonim foydalanuvchi sessiya va IP bo'yicha hisoblanadi. Faqat muvaffaqiyatli AI so'rovlari sanaladi.
"""
from dataclasses import dataclass
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from apps.core.activity import client_ip
from apps.core.models import SiteSettings

from .models import AIUsage

ANON_IP_WINDOW = timedelta(hours=24)


@dataclass
class Quota:
    allowed: bool
    used: int
    limit: int
    tier: str            # "free" | "cv" | "pro"
    message: str = ""

    @property
    def remaining(self):
        return max(0, self.limit - self.used)


def _ensure_session(request):
    if not request.session.session_key:
        request.session.save()
    return request.session.session_key


def _pro_plan_and_start(user):
    """Faol Pro tarif va joriy davr boshlanishi (limitlar shu sanadan hisoblanadi)."""
    if not getattr(user, "is_authenticated", False):
        return None, None
    profile = getattr(user, "profile", None)
    if not profile or not profile.has_active_premium:
        return None, None

    from apps.users.models import PricingPlan, UserSubscription

    sub = (
        UserSubscription.objects.filter(user=user, status=UserSubscription.STATUS_ACTIVE, plan__scope=PricingPlan.SCOPE_ACCOUNT)
        .filter(Q(expires_at__isnull=True) | Q(expires_at__gte=timezone.now()))
        .select_related("plan").order_by("-starts_at").first()
    )
    if sub:
        return sub.plan, sub.starts_at
    plan = profile.current_plan
    days = plan.duration_days if plan else 30
    start = (profile.premium_until - timedelta(days=days)) if profile.premium_until else timezone.now() - timedelta(days=days)
    return plan, start


def _usage(request, kind):
    """Joriy foydalanuvchiga tegishli muvaffaqiyatli AIUsage yozuvlari."""
    qs = AIUsage.objects.filter(kind=kind, success=True)
    session_key = _ensure_session(request)
    if request.user.is_authenticated:
        return qs.filter(Q(user=request.user) | Q(session_key=session_key))
    ip = client_ip(request)
    cond = Q(session_key=session_key, user__isnull=True)
    if ip:
        cond |= Q(ip=ip, user__isnull=True, created_at__gte=timezone.now() - ANON_IP_WINDOW)
    return qs.filter(cond)


def generate_quota(request):
    plan, start = _pro_plan_and_start(request.user)
    if plan:
        limit = plan.max_cvs or 30
        used = _usage(request, AIUsage.KIND_GENERATE).filter(created_at__gte=start).count()
        return Quota(used < limit, used, limit, "pro",
                     "" if used < limit else f"Pro davri uchun {limit} ta CV limiti tugadi. Keyingi davrda yangilanadi.")

    limit = SiteSettings.load().free_cv_limit
    used = _usage(request, AIUsage.KIND_GENERATE).count()
    message = "" if used < limit else (
        f"Bepul {limit} ta CV limiti tugadi. Mavjud CV'ingizni kredit bilan oching yoki ko'p CV uchun Pro oling."
    )
    return Quota(used < limit, used, limit, "free", message)


def tailor_quota(request, cv):
    plan, start = _pro_plan_and_start(request.user)
    if plan:
        limit = plan.max_tailorings or 50
        used = _usage(request, AIUsage.KIND_TAILOR).filter(created_at__gte=start).count()
        return Quota(used < limit, used, limit, "pro",
                     "" if used < limit else f"Pro davri uchun {limit} ta moslashtirish limiti tugadi.")

    site = SiteSettings.load()
    root = cv.root
    if root.is_unlocked:
        limit = site.tailor_per_unlocked_cv
        used = AIUsage.objects.filter(kind=AIUsage.KIND_TAILOR, success=True).filter(Q(cv=root) | Q(cv__parent=root)).count()
        return Quota(used < limit, used, limit, "cv",
                     "" if used < limit else f"Bu CV uchun {limit} ta moslashtirish limiti tugadi. Pro bilan ko'proq.")

    limit = site.free_tailor_limit
    used = _usage(request, AIUsage.KIND_TAILOR).count()
    return Quota(used < limit, used, limit, "free",
                 "" if used < limit else f"Bepul moslashtirish ishlatildi. CV'ni kredit bilan ochsangiz yana {site.tailor_per_unlocked_cv} ta beriladi.")


def record(request, kind, cv=None, meta=None, error=""):
    meta = meta or {}
    AIUsage.objects.create(
        user=request.user if request.user.is_authenticated else None,
        session_key=_ensure_session(request),
        ip=client_ip(request),
        kind=kind,
        cv=cv,
        model=meta.get("model", ""),
        prompt_tokens=meta.get("prompt_tokens", 0),
        completion_tokens=meta.get("completion_tokens", 0),
        cost_usd=meta.get("cost_usd", 0),
        duration_ms=meta.get("duration_ms", 0),
        success=not error,
        error=error[:2000],
    )
