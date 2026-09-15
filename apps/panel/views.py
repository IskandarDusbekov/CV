"""
Kundalik boshqaruv paneli (/panel/): to'lovlarni tasdiqlash, foydalanuvchilar, CV lar, AI xarajati,
xatolar, faollik, murojaatlar va sozlamalar. Kamroq kerak bo'ladigan narsalar Django admin da qoladi.
"""
from datetime import timedelta
from functools import wraps
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db.models import Avg, Count, F, Q, Sum
from django.db.models.functions import TruncDate
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.activity import log_activity
from apps.core.models import ActivityLog, BlockedIP, ContactMessage, ErrorLog, SiteSettings
from apps.core.stats import dashboard_stats
from apps.cv.models import CV, AIUsage
from apps.cv.services import TEMPLATE_META
from apps.users.models import PaymentRequest, PricingPlan, UserProfile

from .forms import NewPlanForm, PlanFormSet, SiteSettingsForm

User = get_user_model()


def staff_required(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            # Telegram orqali kirish: superuser «Panelga ruxsat» bergan foydalanuvchi ham shu yo'l bilan kiradi
            return redirect(f"{reverse('user_login')}?{urlencode({'next': request.get_full_path()})}")
        if not request.user.is_staff:
            raise Http404
        return view(request, *args, **kwargs)
    return wrapper


def superuser_required(view):
    """Karta raqami, narxlar va adminlar ro'yxati — faqat bosh admin (superuser) uchun."""
    @wraps(view)
    @staff_required
    def wrapper(request, *args, **kwargs):
        if not request.user.is_superuser:
            messages.error(request, "Bu bo'lim faqat bosh admin uchun.")
            return redirect("panel:dashboard")
        return view(request, *args, **kwargs)
    return wrapper


def _page(request, qs, per_page=30):
    return Paginator(qs, per_page).get_page(request.GET.get("page"))


def _back(request, fallback):
    return redirect(request.POST.get("next") or request.META.get("HTTP_REFERER") or fallback)


# ─── Bosh sahifa ──────────────────────────────────────────────────────────────

@staff_required
def dashboard(request):
    context = dashboard_stats()
    context["pending_payments"] = (
        PaymentRequest.objects.filter(status=PaymentRequest.STATUS_PENDING).select_related("user__profile", "plan")[:5]
    )
    return render(request, "panel/dashboard.html", context)


# ─── To'lovlar ────────────────────────────────────────────────────────────────

@staff_required
def payments(request):
    status = request.GET.get("status", PaymentRequest.STATUS_PENDING)
    qs = PaymentRequest.objects.select_related("user__profile", "plan", "reviewed_by")
    if status != "all":
        qs = qs.filter(status=status)
    q = request.GET.get("q", "").strip()
    if q:
        cond = Q(user__first_name__icontains=q) | Q(user__profile__phone__icontains=q) | Q(user__profile__telegram_username__icontains=q)
        if q.lstrip("#").isdigit():
            cond |= Q(pk=int(q.lstrip("#")))
        qs = qs.filter(cond)
    # "counts" nomi base shablondagi yon menyu hisoblagichi bilan to'qnashmasin
    status_counts = dict(PaymentRequest.objects.order_by().values_list("status").annotate(n=Count("id")))
    return render(request, "panel/payments.html", {
        "page": _page(request, qs.order_by("-receipt_at", "-created_at"), 20),
        "status": status,
        "q": q,
        "status_counts": status_counts,
        "statuses": PaymentRequest.STATUS_CHOICES,
    })


@staff_required
@require_POST
def payment_decide(request, pk):
    from apps.users.bot import notify_payment_result

    req = get_object_or_404(PaymentRequest.objects.select_related("plan", "user__profile"), pk=pk)
    action = request.POST.get("action")
    if action == "approve":
        done = req.approve(request.user)
        if done:
            log_activity(request, "payment_approved", user=req.user, payment=req.pk, plan=req.plan.name, amount=int(req.amount))
            messages.success(request, f"#{req.pk} tasdiqlandi — {req.user.get_full_name() or req.user.username}: {req.plan.name}")
    elif action == "reject":
        note = request.POST.get("note", "").strip() or "Chek ma'lumotlari mos kelmadi"
        done = req.reject(request.user, note=note)
        if done:
            log_activity(request, "payment_rejected", user=req.user, payment=req.pk, reason=note)
            messages.warning(request, f"#{req.pk} rad etildi: {note}")
    else:
        done = False
    if done:
        notify_payment_result(req)
    else:
        messages.error(request, f"#{req.pk} holati o'zgarmadi (allaqachon ko'rib chiqilgan).")
    return _back(request, reverse("panel:payments"))


@staff_required
def receipt(request, pk):
    req = get_object_or_404(PaymentRequest, pk=pk)
    if not req.receipt:
        raise Http404
    return FileResponse(req.receipt.open("rb"), filename=req.receipt.name.rsplit("/", 1)[-1])


# ─── Foydalanuvchilar ─────────────────────────────────────────────────────────

@staff_required
def users(request):
    qs = UserProfile.objects.select_related("user").annotate(cv_count=Count("user__cv", distinct=True))
    q = request.GET.get("q", "").strip()
    if q:
        cond = (Q(user__first_name__icontains=q) | Q(user__last_name__icontains=q) | Q(phone__icontains=q)
                | Q(telegram_username__icontains=q) | Q(user__username__icontains=q))
        if _is_ip(q):
            cond |= Q(last_ip=q)
        qs = qs.filter(cond)
    flt = request.GET.get("f", "")
    now = timezone.now()
    if flt == "pro":
        qs = qs.filter(premium_until__gte=now)
    elif flt == "credits":
        qs = qs.filter(credits__gt=0)
    elif flt == "blocked":
        qs = qs.filter(is_blocked=True)
    elif flt == "online":
        qs = qs.filter(last_seen__gte=now - timedelta(minutes=10))
    sort = request.GET.get("sort", "-created_at")
    if sort not in {"-created_at", "-last_seen", "-credits", "-cv_count"}:
        sort = "-created_at"
    return render(request, "panel/users.html", {
        "page": _page(request, qs.order_by(F(sort.lstrip("-")).desc(nulls_last=True))),
        "q": q, "f": flt, "sort": sort, "now": now,
    })


def _is_ip(value):
    import ipaddress

    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False


@staff_required
def user_detail(request, user_id):
    user = get_object_or_404(User.objects.select_related("profile"), pk=user_id)
    profile = user.profile
    ai = AIUsage.objects.filter(user=user)
    return render(request, "panel/user_detail.html", {
        "u": user,
        "profile": profile,
        "cvs": CV.objects.filter(user=user).order_by("-created_at")[:30],
        "payments": PaymentRequest.objects.filter(user=user).select_related("plan")[:20],
        "activity": ActivityLog.objects.filter(user=user)[:40],
        "ai_count": ai.count(),
        "ai_cost": ai.aggregate(s=Sum("cost_usd"))["s"] or 0,
        "paid_total": PaymentRequest.objects.filter(user=user, status=PaymentRequest.STATUS_APPROVED).aggregate(s=Sum("amount"))["s"] or 0,
        "ip_blocked": bool(profile.last_ip and BlockedIP.objects.filter(ip=profile.last_ip).exists()),
        "is_pro": bool(profile.premium_until and profile.premium_until >= timezone.now()),
        "pro_plan": PricingPlan.objects.filter(scope=PricingPlan.SCOPE_ACCOUNT, is_active=True).order_by("sort_order").first(),
    })


@staff_required
@require_POST
def user_action(request, user_id):
    user = get_object_or_404(User.objects.select_related("profile"), pk=user_id)
    profile = user.profile
    action = request.POST.get("action")

    if action == "credits":
        try:
            delta = int(request.POST.get("quick") or request.POST.get("amount") or 0)
        except ValueError:
            delta = 0
        new_value = max(0, profile.credits + delta)
        UserProfile.objects.filter(pk=profile.pk).update(credits=new_value)
        log_activity(request, "credits_changed", user=user, delta=delta, by=request.user.username)
        messages.success(request, f"Kreditlar: {profile.credits} → {new_value}")
    elif action == "pro":
        days = max(1, int(request.POST.get("days") or 30))
        start = max(timezone.now(), profile.premium_until) if profile.premium_until else timezone.now()
        profile.premium_until = start + timedelta(days=days)
        profile.current_plan = PricingPlan.objects.filter(scope=PricingPlan.SCOPE_ACCOUNT, is_active=True).order_by("sort_order").first()
        profile.save(update_fields=["premium_until", "current_plan", "updated_at"])
        log_activity(request, "pro_granted", user=user, days=days, by=request.user.username)
        messages.success(request, f"Pro {profile.premium_until:%d.%m.%Y} gacha berildi.")
    elif action == "remove_pro":
        profile.premium_until = None
        profile.current_plan = None
        profile.save(update_fields=["premium_until", "current_plan", "updated_at"])
        user.subscriptions.filter(status="active").update(status="cancelled")
        messages.success(request, "Pro olib tashlandi.")
    elif action == "block":
        if user.is_staff:
            messages.error(request, "Adminni bloklab bo'lmaydi.")
        else:
            profile.is_blocked = True
            profile.block_reason = request.POST.get("reason", "").strip() or "Admin tomonidan bloklandi"
            profile.save(update_fields=["is_blocked", "block_reason", "updated_at"])
            if request.POST.get("with_ip") and profile.last_ip:
                BlockedIP.objects.get_or_create(ip=profile.last_ip, defaults={"reason": f"{user.username} bilan bloklandi"})
            log_activity(request, "blocked", user=user, reason=profile.block_reason, by=request.user.username)
            messages.warning(request, "Foydalanuvchi bloklandi.")
    elif action == "unblock":
        profile.is_blocked = False
        profile.block_reason = ""
        profile.save(update_fields=["is_blocked", "block_reason", "updated_at"])
        if profile.last_ip:
            BlockedIP.objects.filter(ip=profile.last_ip).delete()
        log_activity(request, "unblocked", user=user, by=request.user.username)
        messages.success(request, "Blokdan chiqarildi.")
    elif action in {"make_staff", "remove_staff"}:
        if not request.user.is_superuser:
            messages.error(request, "Panelga ruxsatni faqat bosh admin beradi.")
        elif user.is_superuser:
            messages.error(request, "Bosh adminning ruxsatini bu yerdan o'zgartirib bo'lmaydi.")
        else:
            user.is_staff = action == "make_staff"
            user.save(update_fields=["is_staff"])
            if user.is_staff and profile.is_blocked:
                UserProfile.objects.filter(pk=profile.pk).update(is_blocked=False, block_reason="")
            log_activity(request, "staff_granted" if user.is_staff else "staff_removed", user=user, by=request.user.username)
            messages.success(request, "Panelga ruxsat berildi — Telegram orqali kirib «⚡ Panel» ni ochadi." if user.is_staff
                             else "Panelga ruxsat olib tashlandi.")
    return redirect("panel:user_detail", user_id=user.pk)


# ─── CV lar ───────────────────────────────────────────────────────────────────

@staff_required
def cvs(request):
    qs = CV.objects.select_related("user", "parent")
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(cv_json__full_name__icontains=q) | Q(cv_json__job_title__icontains=q)
                       | Q(user__profile__phone__icontains=q) | Q(user__first_name__icontains=q))
    flt = request.GET.get("f", "")
    if flt == "unlocked":
        qs = qs.filter(is_unlocked=True)
    elif flt == "tailored":
        qs = qs.filter(parent__isnull=False)
    elif flt == "anon":
        qs = qs.filter(user__isnull=True)
    template = request.GET.get("t", "")
    if template in TEMPLATE_META:
        qs = qs.filter(selected_template=template)
    return render(request, "panel/cvs.html", {
        "page": _page(request, qs.order_by("-created_at"), 40),
        "q": q, "f": flt, "t": template,
        "templates": [(code, meta["label"]) for code, meta in TEMPLATE_META.items()],
    })


# ─── AI xarajati ──────────────────────────────────────────────────────────────

@staff_required
def ai_usage(request):
    site = SiteSettings.load()
    now = timezone.now()
    today = timezone.localtime(now).replace(hour=0, minute=0, second=0, microsecond=0)
    month = today.replace(day=1)
    since = today - timedelta(days=29)

    def totals(qs):
        agg = qs.aggregate(cost=Sum("cost_usd"), n=Count("id"), tin=Sum("prompt_tokens"), tout=Sum("completion_tokens"))
        agg["cost"] = agg["cost"] or 0
        agg["uzs"] = int(float(agg["cost"]) * site.usd_to_uzs)
        agg["failed"] = qs.filter(success=False).count()
        return agg

    daily = dict(
        AIUsage.objects.filter(created_at__gte=since).annotate(d=TruncDate("created_at")).values("d")
        .annotate(c=Sum("cost_usd")).values_list("d", "c")
    )
    days = [since + timedelta(days=i) for i in range(30)]
    peak = max([float(v or 0) for v in daily.values()] + [0.000001])
    chart = [{"label": d.strftime("%d.%m"), "cost": daily.get(d.date(), 0) or 0, "h": round(float(daily.get(d.date(), 0) or 0) / peak * 100)} for d in days]

    month_qs = AIUsage.objects.filter(created_at__gte=month)
    return render(request, "panel/ai.html", {
        "site": site,
        "today": totals(AIUsage.objects.filter(created_at__gte=today)),
        "month": totals(month_qs),
        "all": totals(AIUsage.objects.all()),
        "chart": chart,
        "by_kind": month_qs.values("kind").annotate(n=Count("id"), cost=Sum("cost_usd"), avg_ms=Avg("duration_ms")).order_by("-cost"),
        "by_model": month_qs.values("model").annotate(n=Count("id"), cost=Sum("cost_usd")).order_by("-cost"),
        "top_users": month_qs.filter(user__isnull=False).values("user_id", "user__first_name", "user__username")
        .annotate(n=Count("id"), cost=Sum("cost_usd")).order_by("-cost")[:10],
        "failed": AIUsage.objects.filter(success=False).select_related("user")[:15],
    })


# ─── Xatolar ──────────────────────────────────────────────────────────────────

@staff_required
def errors(request):
    show = request.GET.get("show", "open")
    qs = ErrorLog.objects.select_related("user")
    if show == "open":
        qs = qs.filter(is_resolved=False)
    grouped = (
        ErrorLog.objects.filter(is_resolved=False).values("source", "message").annotate(n=Count("id")).order_by("-n")[:8]
    )
    return render(request, "panel/errors.html", {"page": _page(request, qs, 25), "show": show, "grouped": grouped})


@staff_required
@require_POST
def errors_resolve(request):
    ids = request.POST.getlist("ids")
    if request.POST.get("all"):
        count = ErrorLog.objects.filter(is_resolved=False).update(is_resolved=True)
    else:
        count = ErrorLog.objects.filter(pk__in=ids).update(is_resolved=True)
    messages.success(request, f"{count} ta xato hal qilindi deb belgilandi.")
    return _back(request, reverse("panel:errors"))


# ─── Faollik ──────────────────────────────────────────────────────────────────

@staff_required
def activity(request):
    qs = ActivityLog.objects.select_related("user")
    action = request.GET.get("action", "")
    if action:
        qs = qs.filter(action=action)
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(ip=q) if _is_ip(q) else qs.filter(Q(user__first_name__icontains=q) | Q(user__profile__phone__icontains=q) | Q(user__username__icontains=q))
    return render(request, "panel/activity.html", {
        "page": _page(request, qs, 50), "action": action, "q": q, "actions": ActivityLog.ACTION_CHOICES,
    })


# ─── Murojaatlar ──────────────────────────────────────────────────────────────

@staff_required
def contact_messages(request):
    show = request.GET.get("show", "open")
    qs = ContactMessage.objects.select_related("user")
    if show == "open":
        qs = qs.filter(is_resolved=False)
    return render(request, "panel/messages.html", {"page": _page(request, qs, 20), "show": show})


@staff_required
@require_POST
def message_resolve(request, pk):
    msg = get_object_or_404(ContactMessage, pk=pk)
    msg.is_resolved = request.POST.get("reopen") != "1"
    msg.admin_note = request.POST.get("note", msg.admin_note)[:2000]
    msg.save(update_fields=["is_resolved", "admin_note"])
    return _back(request, reverse("panel:messages"))


# ─── Sozlamalar va narxlar ────────────────────────────────────────────────────

@superuser_required
def settings_view(request):
    site = SiteSettings.load()
    site = SiteSettings.objects.get(pk=site.pk)
    form = SiteSettingsForm(instance=site)
    plans = PlanFormSet(queryset=PricingPlan.objects.order_by("scope", "sort_order", "price"), prefix="plans")
    new_plan = NewPlanForm(prefix="new")

    if request.method == "POST":
        section = request.POST.get("section")
        if section == "site":
            form = SiteSettingsForm(request.POST, instance=site)
            if form.is_valid():
                form.save()
                messages.success(request, "Sozlamalar saqlandi.")
                return redirect(f"{reverse('panel:settings')}#site")
        elif section == "plans":
            plans = PlanFormSet(request.POST, queryset=PricingPlan.objects.order_by("scope", "sort_order", "price"), prefix="plans")
            if plans.is_valid():
                plans.save()
                messages.success(request, "Narxlar saqlandi.")
                return redirect(f"{reverse('panel:settings')}#plans")
        elif section == "new_plan":
            new_plan = NewPlanForm(request.POST, prefix="new")
            if new_plan.is_valid():
                plan = new_plan.save(commit=False)
                plan.billing_period = "one_time" if plan.scope == PricingPlan.SCOPE_CREDITS else "monthly"
                plan.includes_pdf_export = plan.includes_docx_export = plan.includes_premium_templates = True
                plan.save()
                messages.success(request, f"«{plan.name}» qo'shildi.")
                return redirect(f"{reverse('panel:settings')}#plans")
        messages.error(request, "Formada xatolik bor — qizil maydonlarni tekshiring.")

    return render(request, "panel/settings.html", {"form": form, "plans": plans, "new_plan": new_plan})
