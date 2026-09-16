import json

from django.conf import settings as django_settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponseBadRequest, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from apps.cv.models import CV, AIUsage
from apps.cv.quotas import generate_quota
from apps.cv.services import TEMPLATE_META, normalize_cv_data, resolve_template_name

from apps.core.models import SiteSettings

from .models import CompanyBranding, PaymentRequest, PaymentTransaction, PricingPlan, TelegramLoginToken, UserProfile
from .services import activate_transaction, fail_transaction
from .telegram_auth import (
    bot_username,
    confirm_token,
    consume_token,
    create_login_token,
    deep_link,
    get_active_token,
    verify_webapp_init_data,
)

_SESSION_TOKEN_KEY = "tg_login_token"
_SESSION_NEXT_KEY = "login_next"


# ─── LOGIN (Telegram, parolsiz va kodsiz) ─────────────────────────────────────

def login_view(request):
    if request.user.is_authenticated:
        return redirect("user_dashboard")

    next_url = request.GET.get("next", "")
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        request.session[_SESSION_NEXT_KEY] = next_url

    token = _session_token(request)
    if token is None:
        if not request.session.session_key:
            request.session.save()
        TelegramLoginToken.objects.filter(expires_at__lt=timezone.now()).delete()
        token = create_login_token(session_key=request.session.session_key)
        request.session[_SESSION_TOKEN_KEY] = token.token

    return render(request, "users/login.html", {
        "deep_link": deep_link(token),
        "bot_username": bot_username(),
        "ttl_seconds": max(0, int((token.expires_at - timezone.now()).total_seconds())),
        "debug_login": django_settings.DEBUG,
        "signup_mode": request.GET.get("mode") == "signup",
    })


def signup_view(request):
    # Ro'yxatdan o'tish va kirish bitta oqim (Telegram), faqat sarlavha boshqacha
    params = request.GET.copy()
    params["mode"] = "signup"
    return redirect(f"{reverse('user_login')}?{params.urlencode()}")


@require_GET
def telegram_login_status(request):
    value = request.session.get(_SESSION_TOKEN_KEY)
    token = TelegramLoginToken.objects.filter(token=value).first() if value else None

    if token is None or token.status == TelegramLoginToken.STATUS_USED:
        return JsonResponse({"status": "missing"})
    if token.is_expired:
        return JsonResponse({"status": "expired"})
    if token.status == TelegramLoginToken.STATUS_PENDING:
        return JsonResponse({"status": "pending", "opened": bool(token.telegram_id)})
    if token.session_key != request.session.session_key:
        return JsonResponse({"status": "missing"})

    user = consume_token(token)
    if user is None:
        return JsonResponse({"status": "expired"})
    return JsonResponse({"status": "ok", "redirect": _finish_login(request, user)})


@require_GET
def telegram_login_complete(request, token):
    """Eski bot xabarlaridagi bir martalik havola (endi bot Mini App tugmasini yuboradi)."""
    obj = TelegramLoginToken.objects.filter(token=token).first()
    user = consume_token(obj) if obj else None
    if user is None:
        if request.user.is_authenticated:
            return redirect("user_dashboard")
        messages.info(request, "Bu havola eskirgan. Botdagi «Saytni ochish» tugmasini bosing — u har doim ishlaydi.")
        return redirect("user_login")
    return redirect(_finish_login(request, user))


# ─── TELEGRAM MINI APP ────────────────────────────────────────────────────────

def _safe_next(request, value, default="/users/dashboard/"):
    if value and url_has_allowed_host_and_scheme(value, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return value
    return default


@require_GET
def telegram_webapp(request):
    """Botdagi «Saytni ochish» tugmasi ochadigan sahifa: initData bilan avtomatik kiradi."""
    return render(request, "users/tg_app.html", {
        "next_url": _safe_next(request, request.GET.get("next", "")),
        "bot_username": bot_username(),
    })


@require_POST
def telegram_webapp_auth(request):
    """Mini App initData ni tekshiradi va Telegram ID bo'yicha akkauntga kiritadi."""
    tg_user = verify_webapp_init_data(request.POST.get("init_data", ""))
    if tg_user is None:
        return JsonResponse({"status": "invalid"}, status=403)

    next_url = _safe_next(request, request.POST.get("next", ""))
    profile = UserProfile.objects.select_related("user").filter(telegram_id=tg_user["id"]).first()
    if profile is None:
        # Raqam hali ulashilmagan: sahifa requestContact so'raydi, bot akkauntni yaratadi
        return JsonResponse({"status": "need_phone"})
    if profile.is_blocked:
        return JsonResponse({"status": "blocked"}, status=403)

    user = profile.user
    if tg_user.get("username") and tg_user["username"] != profile.telegram_username:
        UserProfile.objects.filter(pk=profile.pk).update(telegram_username=tg_user["username"][:100])
    if request.user.is_authenticated and request.user.pk == user.pk:
        request.session["in_telegram"] = True
        return JsonResponse({"status": "ok", "redirect": next_url})

    request.session[_SESSION_NEXT_KEY] = next_url
    redirect_url = _finish_login(request, user)
    # Sahifalar Telegram ichida ekanini bilsin: yuklab olish Mini App usuli bilan ishlaydi
    request.session["in_telegram"] = True
    return JsonResponse({"status": "ok", "redirect": redirect_url})


@require_POST
def debug_confirm_login(request):
    """Faqat DEBUG: Telegram botsiz lokal sinov uchun tokenni tasdiqlash."""
    if not django_settings.DEBUG:
        raise Http404
    token = _session_token(request)
    phone = request.POST.get("phone", "").strip()
    if token is None or not phone:
        messages.error(request, "Telefon raqamni kiriting.")
        return redirect("user_login")
    confirm_token(token, phone=phone, telegram_id=None, first_name="Test")
    return redirect("user_login")


def logout_view(request):
    if request.user.is_authenticated:
        logout(request)
    return redirect("home")


def _session_token(request):
    value = request.session.get(_SESSION_TOKEN_KEY)
    token = get_active_token(value) if value else None
    if token and token.session_key and token.session_key != request.session.session_key:
        return None
    return token


def _finish_login(request, user):
    owned_cv_ids = request.session.get("owned_cv_ids", [])
    next_url = request.session.get(_SESSION_NEXT_KEY) or reverse("user_dashboard")

    # Kirishdan oldingi AI ishlatishlar akkauntga yoziladi — login qilib limitni yangilab bo'lmaydi
    if request.session.session_key:
        AIUsage.objects.filter(session_key=request.session.session_key, user__isnull=True).update(user=user)

    login(request, user, backend="django.contrib.auth.backends.ModelBackend")

    # Login'dan oldin anonim yaratilgan CV larni akkauntga biriktiramiz
    if owned_cv_ids:
        CV.objects.filter(id__in=owned_cv_ids, user__isnull=True).update(user=user)
    request.session.pop(_SESSION_TOKEN_KEY, None)
    request.session.pop(_SESSION_NEXT_KEY, None)
    messages.success(request, f"Xush kelibsiz, {user.first_name or user.username}!")

    from .growth import on_signed_in

    for note in on_signed_in(request, user):
        messages.success(request, note)
    return next_url


# ─── DASHBOARD ────────────────────────────────────────────────────────────────

@login_required
def dashboard(request):
    profile = getattr(request.user, "profile", None)
    cvs = list(CV.objects.filter(user=request.user).select_related("parent").order_by("-created_at"))
    items = []
    for cv in cvs:
        data = normalize_cv_data(cv.cv_json)
        if cv.photo:
            data["photo_url"] = cv.photo.url
        code = resolve_template_name(cv.selected_template)
        items.append({
            "cv": cv,
            "cv_data": data,
            "template_partial": f"cv/partials/cv_template_{code}.html",
            "template_label": TEMPLATE_META[code]["label"],
            "unlocked": cv.is_unlocked or bool(cv.parent_id and cv.parent.is_unlocked),
        })

    return render(request, "users/dashboard.html", {
        "profile": profile,
        "is_pro": bool(profile and profile.has_active_premium),
        "items": items,
        "cv_count": len(cvs),
        "unlocked_count": sum(1 for item in items if item["unlocked"]),
        "payment_requests": PaymentRequest.objects.filter(user=request.user).select_related("plan")[:6],
        "pro_plan": _plans(PricingPlan.SCOPE_ACCOUNT).first(),
        "quota": generate_quota(request),
        **_referral_stats(request),
    })


def _referral_stats(request):
    from django.db.models import Sum

    from apps.cv.views import _referral_context

    from .models import Referral

    ctx = _referral_context(request)
    if ctx:
        made = Referral.objects.filter(inviter=request.user)
        ctx.update(referral_count=made.count(), referral_credits=made.aggregate(s=Sum("inviter_credits"))["s"] or 0)
    return ctx


# ─── PAYMENTS (Telegram bot orqali) ───────────────────────────────────────────

def _plans(scope):
    return PricingPlan.objects.filter(is_active=True, scope=scope).order_by("sort_order", "price")


def payments_view(request):
    """Paketlar ro'yxati: har biri botga `?start=pay_<kod>` havolasi bilan ochiladi."""
    site = SiteSettings.load()
    bot = site.effective_bot_username
    plans = PricingPlan.objects.filter(is_active=True).order_by("sort_order", "price")
    return render(request, "users/payments.html", {
        "site": site,
        "bot_username": bot,
        "packs": [(p, f"https://t.me/{bot}?start=pay_{p.code}") for p in plans if p.is_credit_pack],
        "pro_plans": [(p, f"https://t.me/{bot}?start=pay_{p.code}") for p in plans if not p.is_credit_pack],
        "has_telegram": bool(request.user.is_authenticated and getattr(request.user.profile, "telegram_id", None)),
        "payment_requests": PaymentRequest.objects.filter(user=request.user).select_related("plan")[:10]
        if request.user.is_authenticated else [],
    })


@csrf_exempt
@require_POST
def payment_callback(request, provider):
    provider = provider.strip().lower()
    if provider not in {PaymentTransaction.PROVIDER_CLICK, PaymentTransaction.PROVIDER_PAYME}:
        return HttpResponseBadRequest("Unknown provider")

    payload = _parse_callback_payload(request)
    merchant_id = payload.get("merchant_transaction_id") or payload.get("merchant_trans_id") or payload.get("transaction_id")
    action = _resolve_provider_action(provider, payload)
    provider_txn_id = payload.get("provider_transaction_id") or payload.get("payment_id") or payload.get("id")

    if not merchant_id:
        return JsonResponse({"ok": False, "error": "merchant_transaction_id required"}, status=400)

    txn = PaymentTransaction.objects.filter(merchant_transaction_id=merchant_id, provider=provider).first()
    if not txn:
        return JsonResponse({"ok": False, "error": "not found"}, status=404)

    if provider_txn_id and not txn.provider_transaction_id:
        txn.provider_transaction_id = str(provider_txn_id)

    if action in {"paid", "success", "completed", "confirm"}:
        txn.save(update_fields=["provider_transaction_id", "updated_at"])
        activate_transaction(txn, payload=payload)
        return JsonResponse({"ok": True, "status": "paid"})

    if action in {"failed", "cancelled", "canceled", "error"}:
        txn.save(update_fields=["provider_transaction_id", "updated_at"])
        fail_transaction(txn, payload=payload)
        return JsonResponse({"ok": True, "status": "failed"})

    txn.raw_response = payload
    txn.status = PaymentTransaction.STATUS_PENDING
    txn.save(update_fields=["provider_transaction_id", "raw_response", "status", "updated_at"])
    return JsonResponse({"ok": True, "status": "pending"})


# ─── BRANDING ─────────────────────────────────────────────────────────────────

@login_required
def branding_settings(request):
    profile = getattr(request.user, "profile", None)
    if not (profile and profile.has_active_premium):
        messages.warning(request, "Kompaniya brendingi faqat Pro tarifda mavjud.")
        return redirect("pricing")

    branding, _ = CompanyBranding.objects.get_or_create(user=request.user, defaults={"name": ""})

    if request.method == "POST":
        branding.name = request.POST.get("name", "").strip()
        branding.tagline = request.POST.get("tagline", "").strip()
        branding.website = request.POST.get("website", "").strip()
        branding.footer_text = request.POST.get("footer_text", "").strip()
        if "logo" in request.FILES:
            branding.logo = request.FILES["logo"]
        branding.save()
        messages.success(request, "Brending saqlandi!")
        return redirect("branding_settings")

    return render(request, "users/branding_settings.html", {"branding": branding})


# ─── HELPERS ──────────────────────────────────────────────────────────────────

def _parse_callback_payload(request):
    if "application/json" in (request.content_type or ""):
        try:
            return json.loads(request.body.decode("utf-8")) if request.body else {}
        except json.JSONDecodeError:
            return {}
    return request.POST.dict()


def _resolve_provider_action(provider, payload):
    status = (payload.get("status") or payload.get("action") or "").strip().lower()
    if provider == PaymentTransaction.PROVIDER_CLICK:
        error_code = str(payload.get("error", "")).strip()
        click_action = str(payload.get("action", "")).strip().lower()
        if error_code in {"0", ""} and click_action in {"1", "2", "prepare", "complete", "confirm"}:
            return "paid"
        if error_code and error_code != "0":
            return "failed"
    return status
