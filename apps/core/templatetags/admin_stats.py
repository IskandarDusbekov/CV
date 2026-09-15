from datetime import timedelta

from django import template
from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

register = template.Library()


@register.inclusion_tag("admin/_dashboard_stats.html")
def admin_dashboard_stats():
    from apps.core.models import ActivityLog, ContactMessage, ErrorLog, SiteSettings
    from apps.cv.models import CV, AIUsage
    from apps.users.models import PaymentRequest, UserProfile

    now = timezone.now()
    today = timezone.localtime(now).replace(hour=0, minute=0, second=0, microsecond=0)
    month = today.replace(day=1)
    site = SiteSettings.load()

    def cost(qs):
        return qs.aggregate(s=Sum("cost_usd"))["s"] or 0

    ai_month_cost = cost(AIUsage.objects.filter(created_at__gte=month))
    approved = PaymentRequest.objects.filter(status=PaymentRequest.STATUS_APPROVED)

    days = [today - timedelta(days=i) for i in range(13, -1, -1)]
    cv_by_day = dict(
        CV.objects.filter(created_at__gte=days[0]).annotate(d=TruncDate("created_at")).values("d").annotate(n=Count("id")).values_list("d", "n")
    )
    users_by_day = dict(
        UserProfile.objects.filter(created_at__gte=days[0]).annotate(d=TruncDate("created_at")).values("d").annotate(n=Count("id")).values_list("d", "n")
    )
    chart = [{"label": d.strftime("%d.%m"), "cvs": cv_by_day.get(d.date(), 0), "users": users_by_day.get(d.date(), 0)} for d in days]
    peak = max([c["cvs"] for c in chart] + [c["users"] for c in chart] + [1])
    for c in chart:
        c["cv_h"] = int(c["cvs"] / peak * 100)
        c["user_h"] = int(c["users"] / peak * 100)

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
        "ai_cost_today": cost(AIUsage.objects.filter(created_at__gte=today)),
        "ai_cost_month": ai_month_cost,
        "ai_cost_month_uzs": int(float(ai_month_cost) * site.usd_to_uzs),
        "ai_cost_total": cost(AIUsage.objects.all()),
        "payments_pending": PaymentRequest.objects.filter(status=PaymentRequest.STATUS_PENDING).count(),
        "revenue_month": approved.filter(reviewed_at__gte=month).aggregate(s=Sum("amount"))["s"] or 0,
        "revenue_total": approved.aggregate(s=Sum("amount"))["s"] or 0,
        "errors_open": ErrorLog.objects.filter(is_resolved=False).count(),
        "messages_new": ContactMessage.objects.filter(is_resolved=False).count(),
        "recent_errors": ErrorLog.objects.filter(is_resolved=False)[:5],
        "recent_activity": ActivityLog.objects.select_related("user")[:12],
        "chart": chart,
    }
