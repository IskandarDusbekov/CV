"""Boshqaruv paneli va Django admin bosh sahifasi uchun umumiy statistika."""
from datetime import timedelta

from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone


def _cost(qs):
    return qs.aggregate(s=Sum("cost_usd"))["s"] or 0


def dashboard_stats(days_back=14):
    from apps.core.models import ActivityLog, ContactMessage, ErrorLog, SiteSettings
    from apps.cv.models import CV, AIUsage
    from apps.users.models import PaymentRequest, UserProfile

    now = timezone.now()
    today = timezone.localtime(now).replace(hour=0, minute=0, second=0, microsecond=0)
    month = today.replace(day=1)
    site = SiteSettings.load()

    ai_month_cost = _cost(AIUsage.objects.filter(created_at__gte=month))
    approved = PaymentRequest.objects.filter(status=PaymentRequest.STATUS_APPROVED)

    days = [today - timedelta(days=i) for i in range(days_back - 1, -1, -1)]

    def per_day(qs, field="created_at", value=None):
        qs = qs.filter(**{f"{field}__gte": days[0]}).annotate(d=TruncDate(field)).values("d")
        rows = qs.annotate(n=Sum(value) if value else Count("id")).values_list("d", "n")
        return {d: n or 0 for d, n in rows}

    cvs = per_day(CV.objects.all())
    users = per_day(UserProfile.objects.all())
    revenue = per_day(approved, field="reviewed_at", value="amount")
    chart = [
        {"label": d.strftime("%d.%m"), "cvs": cvs.get(d.date(), 0), "users": users.get(d.date(), 0), "revenue": int(revenue.get(d.date(), 0))}
        for d in days
    ]
    peak = max([c["cvs"] for c in chart] + [c["users"] for c in chart] + [1])
    peak_rev = max([c["revenue"] for c in chart] + [1])
    for c in chart:
        c["cv_h"] = round(c["cvs"] / peak * 100)
        c["user_h"] = round(c["users"] / peak * 100)
        c["rev_h"] = round(c["revenue"] / peak_rev * 100)

    return {
        "users_total": UserProfile.objects.count(),
        "users_today": UserProfile.objects.filter(created_at__gte=today).count(),
        "users_online": UserProfile.objects.filter(last_seen__gte=now - timedelta(minutes=10)).count(),
        "users_blocked": UserProfile.objects.filter(is_blocked=True).count(),
        "cvs_total": CV.objects.count(),
        "cvs_today": CV.objects.filter(created_at__gte=today).count(),
        "cvs_unlocked": CV.objects.filter(is_unlocked=True).count(),
        "ai_today": AIUsage.objects.filter(created_at__gte=today).count(),
        "ai_failed_today": AIUsage.objects.filter(created_at__gte=today, success=False).count(),
        "ai_cost_today": _cost(AIUsage.objects.filter(created_at__gte=today)),
        "ai_cost_month": ai_month_cost,
        "ai_cost_month_uzs": int(float(ai_month_cost) * site.usd_to_uzs),
        "ai_cost_total": _cost(AIUsage.objects.all()),
        "payments_pending": PaymentRequest.objects.filter(status=PaymentRequest.STATUS_PENDING).count(),
        "revenue_today": approved.filter(reviewed_at__gte=today).aggregate(s=Sum("amount"))["s"] or 0,
        "revenue_month": approved.filter(reviewed_at__gte=month).aggregate(s=Sum("amount"))["s"] or 0,
        "revenue_total": approved.aggregate(s=Sum("amount"))["s"] or 0,
        "errors_open": ErrorLog.objects.filter(is_resolved=False).count(),
        "messages_new": ContactMessage.objects.filter(is_resolved=False).count(),
        "recent_errors": ErrorLog.objects.filter(is_resolved=False).select_related("user")[:5],
        "recent_activity": ActivityLog.objects.select_related("user")[:12],
        "chart": chart,
    }
