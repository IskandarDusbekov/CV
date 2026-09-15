"""Faollik jurnali, xatoliklarni bazaga yozish va bloklash middleware'lari."""
import logging
import traceback

from django.contrib.auth import logout
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver
from django.shortcuts import render
from django.utils import timezone

logger = logging.getLogger(__name__)


def client_ip(request):
    if request is None:
        return None
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return (forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR")) or None


def log_activity(request, action, user=None, **meta):
    """Harakatni jurnalga yozadi. Hech qachon asosiy so'rovni buzmaydi."""
    from .models import ActivityLog

    try:
        if user is None and request is not None and getattr(request, "user", None) and request.user.is_authenticated:
            user = request.user
        ActivityLog.objects.create(
            user=user,
            action=action,
            ip=client_ip(request),
            user_agent=(request.META.get("HTTP_USER_AGENT", "")[:300] if request else ""),
            path=(request.path[:300] if request else ""),
            meta=meta,
        )
    except Exception:  # jurnal yozilmasa ham sayt ishlashda davom etadi
        logger.warning("Activity log failed", exc_info=True)


@receiver(user_logged_in)
def _on_login(sender, request, user, **kwargs):
    profile = getattr(user, "profile", None)
    is_new = bool(profile and (timezone.now() - profile.created_at).total_seconds() < 120)
    log_activity(request, "register" if is_new else "login", user=user)


@receiver(user_logged_out)
def _on_logout(sender, request, user, **kwargs):
    if user is not None:
        log_activity(request, "logout", user=user)


class DatabaseErrorHandler(logging.Handler):
    """ERROR darajadagi loglarni admin paneldagi "Xatoliklar" bo'limiga yozadi."""

    def emit(self, record):
        if getattr(record, "_from_db_handler", False):
            return
        try:
            from .models import ErrorLog

            request = getattr(record, "request", None)
            user = getattr(request, "user", None) if request is not None else None
            tb = ""
            if record.exc_info:
                tb = "".join(traceback.format_exception(*record.exc_info))
            ErrorLog.objects.create(
                level=record.levelname,
                source=record.name[:100],
                path=(getattr(request, "path", "") or "")[:300],
                method=getattr(request, "method", "") or "",
                user=user if getattr(user, "is_authenticated", False) else None,
                ip=client_ip(request) if request is not None else None,
                message=record.getMessage()[:5000],
                traceback=tb[:20000],
            )
        except Exception:
            pass  # bazaga yozib bo'lmasa (masalan migratsiyadan oldin) — jim o'tamiz


class BlockAndPresenceMiddleware:
    """Bloklangan foydalanuvchi/IP ni to'xtatadi va oxirgi faollik vaqtini yangilaydi."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from .models import BlockedIP

        ip = client_ip(request)
        if not request.path.startswith("/admin/"):
            if ip and BlockedIP.objects.filter(ip=ip).exists():
                return render(request, "core/blocked.html", {"reason": "IP manzilingiz bloklangan."}, status=403)

            user = getattr(request, "user", None)
            if user is not None and user.is_authenticated and not user.is_staff:
                profile = getattr(user, "profile", None)
                if profile and profile.is_blocked:
                    reason = profile.block_reason
                    logout(request)
                    return render(request, "core/blocked.html", {"reason": reason}, status=403)
                if profile and (not profile.last_seen or (timezone.now() - profile.last_seen).total_seconds() > 300):
                    type(profile).objects.filter(pk=profile.pk).update(last_seen=timezone.now(), last_ip=ip)

        return self.get_response(request)
