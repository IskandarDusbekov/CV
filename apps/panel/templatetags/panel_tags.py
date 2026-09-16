from django import template

register = template.Library()

ACTION_COLORS = {
    "register": "blue", "login": "sky", "logout": "gray", "cv_create": "green", "cv_tailor": "violet",
    "cv_unlock": "amber", "download_pdf": "gray", "download_docx": "gray", "payment_request": "orange",
    "payment_approved": "green", "payment_rejected": "red", "blocked": "red", "unblocked": "green",
    "limit_reached": "amber", "credits_changed": "violet", "pro_granted": "violet", "staff_granted": "violet", "staff_removed": "amber", "contact": "sky",
    "referral": "green", "promo_bonus": "orange",
}
PAYMENT_COLORS = {"awaiting_receipt": "gray", "pending": "amber", "approved": "green", "rejected": "red", "cancelled": "gray"}


@register.simple_tag
def panel_counts():
    from apps.core.models import ContactMessage, ErrorLog
    from apps.users.models import PaymentRequest

    return {
        "payments": PaymentRequest.objects.filter(status=PaymentRequest.STATUS_PENDING).count(),
        "errors": ErrorLog.objects.filter(is_resolved=False).count(),
        "messages": ContactMessage.objects.filter(is_resolved=False).count(),
    }


@register.filter
def action_color(action):
    return ACTION_COLORS.get(action, "gray")


@register.filter
def payment_color(status):
    return PAYMENT_COLORS.get(status, "gray")


@register.simple_tag(takes_context=True)
def qs(context, **kwargs):
    """Joriy GET parametrlarini saqlab, berilganlarini almashtiradi (filtr va sahifalash uchun)."""
    params = context["request"].GET.copy()
    for key, value in kwargs.items():
        if value in (None, ""):
            params.pop(key, None)
        else:
            params[key] = value
    if "page" not in kwargs:
        params.pop("page", None)
    encoded = params.urlencode()
    return f"?{encoded}" if encoded else "?"


KIND_COLORS = {"human": "green", "bot": "blue", "scanner": "red", "unknown": "gray"}
DEVICE_ICONS = {"mobile": "📱", "tablet": "📟", "desktop": "💻"}


@register.filter
def kind_color(kind):
    return KIND_COLORS.get(kind, "gray")


@register.filter
def device_icon(device):
    return DEVICE_ICONS.get(device, "❔")


@register.filter
def source_label(source):
    from apps.core.analytics import SOURCE_LABELS

    return SOURCE_LABELS.get(source, source or "—")


@register.filter
def duration_short(delta):
    """timedelta → «45 s», «3 daq», «2 soat»."""
    try:
        seconds = int(delta.total_seconds())
    except AttributeError:
        return ""
    if seconds < 60:
        return f"{seconds} s"
    if seconds < 3600:
        return f"{seconds // 60} daq"
    return f"{seconds // 3600} soat"
