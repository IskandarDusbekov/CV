from datetime import timedelta

from django.contrib import admin, messages
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html

from apps.core.activity import log_activity
from apps.core.models import BlockedIP

from .models import (
    CompanyBranding,
    PaymentRequest,
    PaymentTransaction,
    PricingPlan,
    TelegramLoginToken,
    UserProfile,
    UserSubscription,
)


def badge(text, bg, fg):
    return format_html('<span style="background:{};color:{};padding:3px 9px;border-radius:999px;font-weight:700;font-size:12px;white-space:nowrap;">{}</span>', bg, fg, text)


def money(value):
    return f"{int(value or 0):,}".replace(",", " ")


# ─── Tariflar ─────────────────────────────────────────────────────────────────

@admin.register(PricingPlan)
class PricingPlanAdmin(admin.ModelAdmin):
    list_display = ("name", "scope", "price_display", "credits", "per_credit", "duration_days", "max_cvs", "max_tailorings",
                    "is_featured", "is_active", "sort_order", "sold")
    list_editable = ("is_featured", "is_active", "sort_order")
    list_filter = ("scope", "is_active")
    search_fields = ("name", "code")
    prepopulated_fields = {"code": ("name",)}
    fieldsets = (
        ("Asosiy", {"fields": ("name", "code", "scope", "description", "is_active", "is_featured", "sort_order")}),
        ("Narx", {"fields": ("price", "currency")}),
        ("🎟 Kredit paketi", {"fields": ("credits",), "description": "1 kredit = 1 CV ni ochish (PDF + Word, muddatsiz)."}),
        ("⭐ Pro obuna", {"fields": ("duration_days", "max_cvs", "max_tailorings"),
                          "description": "Davr (kun) ichida nechta CV yaratish va vakansiyaga moslashtirish mumkin."}),
    )

    @admin.display(description="Narx", ordering="price")
    def price_display(self, obj):
        return format_html("<b>{}</b> so'm", money(obj.price))

    @admin.display(description="1 CV narxi")
    def per_credit(self, obj):
        return f"{money(obj.price_per_credit)} so'm" if obj.price_per_credit else "—"

    @admin.display(description="Sotilgan")
    def sold(self, obj):
        return obj.payment_requests.filter(status=PaymentRequest.STATUS_APPROVED).count()


# ─── To'lovlar (bot orqali) ───────────────────────────────────────────────────

@admin.register(PaymentRequest)
class PaymentRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "created_at", "user_link", "phone", "plan", "amount_display", "status_badge", "receipt_thumb", "reviewed_by")
    list_filter = ("status", "plan", "created_at")
    search_fields = ("id", "user__username", "user__first_name", "user__profile__phone", "user__profile__telegram_username")
    date_hierarchy = "created_at"
    readonly_fields = ("user", "plan", "amount", "status", "receipt_preview", "receipt_caption", "telegram_chat_id",
                       "created_at", "receipt_at", "reviewed_by", "reviewed_at", "review_buttons")
    fields = ("review_buttons", "user", "plan", "amount", "status", "receipt_preview", "receipt_caption", "admin_note",
              "created_at", "receipt_at", "reviewed_by", "reviewed_at")
    actions = ("approve_selected", "reject_selected")
    list_per_page = 50

    def get_ordering(self, request):
        return ("-receipt_at", "-created_at")

    def has_add_permission(self, request):
        return False

    def get_urls(self):
        return [
            path("<int:pk>/approve/", self.admin_site.admin_view(self.approve_view), name="users_paymentrequest_approve"),
            path("<int:pk>/reject/", self.admin_site.admin_view(self.reject_view), name="users_paymentrequest_reject"),
            path("<int:pk>/receipt/", self.admin_site.admin_view(self.receipt_view), name="users_paymentrequest_receipt"),
        ] + super().get_urls()

    def receipt_view(self, request, pk):
        """Chek faylini faqat admin uchun beradi (to'g'ridan-to'g'ri /media/ havolasi productionda yopiq)."""
        from django.http import FileResponse, Http404

        req = get_object_or_404(PaymentRequest, pk=pk)
        if not req.receipt:
            raise Http404
        return FileResponse(req.receipt.open("rb"), filename=req.receipt.name.rsplit("/", 1)[-1])

    def _receipt_url(self, obj):
        return reverse("admin:users_paymentrequest_receipt", args=[obj.pk])

    # --- ko'rinish ---
    @admin.display(description="Foydalanuvchi")
    def user_link(self, obj):
        return format_html('<a href="{}">{}</a>', reverse("admin:users_userprofile_change", args=[obj.user.profile.pk]),
                           obj.user.get_full_name() or obj.user.username)

    @admin.display(description="Telefon")
    def phone(self, obj):
        return obj.user.profile.phone

    @admin.display(description="Summa", ordering="amount")
    def amount_display(self, obj):
        return format_html("<b>{}</b> so'm", money(obj.amount))

    @admin.display(description="Holat", ordering="status")
    def status_badge(self, obj):
        colors = {
            PaymentRequest.STATUS_AWAITING: ("#f3f4f6", "#6b7280"),
            PaymentRequest.STATUS_PENDING: ("#fef3c7", "#92400e"),
            PaymentRequest.STATUS_APPROVED: ("#dcfce7", "#166534"),
            PaymentRequest.STATUS_REJECTED: ("#fee2e2", "#b91c1c"),
            PaymentRequest.STATUS_CANCELLED: ("#f3f4f6", "#9ca3af"),
        }
        bg, fg = colors.get(obj.status, ("#f3f4f6", "#374151"))
        return badge(obj.get_status_display(), bg, fg)

    @admin.display(description="Chek")
    def receipt_thumb(self, obj):
        if not obj.receipt:
            return "—"
        if obj.receipt.name.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
            return format_html('<a href="{0}" target="_blank"><img src="{0}" style="height:44px;border-radius:6px;"></a>', self._receipt_url(obj))
        return format_html('<a href="{}" target="_blank">📎 fayl</a>', self._receipt_url(obj))

    @admin.display(description="Chek")
    def receipt_preview(self, obj):
        if not obj.receipt:
            return "Chek hali yuborilmagan"
        if obj.receipt.name.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
            return format_html('<a href="{0}" target="_blank"><img src="{0}" style="max-height:520px;max-width:100%;border-radius:10px;border:1px solid #ddd;"></a>', self._receipt_url(obj))
        return format_html('<a href="{}" target="_blank">📎 Chek faylini ochish</a>', self._receipt_url(obj))

    @admin.display(description="Qaror")
    def review_buttons(self, obj):
        if obj.status in {PaymentRequest.STATUS_APPROVED, PaymentRequest.STATUS_REJECTED, PaymentRequest.STATUS_CANCELLED}:
            return format_html("{} — {} {}", obj.get_status_display(), obj.reviewed_by or "", obj.reviewed_at.strftime("%d.%m.%Y %H:%M") if obj.reviewed_at else "")
        profile = obj.user.profile
        what = f"+{obj.plan.credits} kredit" if obj.plan.is_credit_pack else f"Pro {obj.plan.duration_days} kun"
        return format_html(
            '<div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;">'
            '<button type="submit" formaction="{}" class="btn btn-success" style="padding:8px 18px;font-weight:700;">✅ Tasdiqlash ({})</button>'
            '<button type="submit" formaction="{}" class="btn btn-danger" style="padding:8px 18px;font-weight:700;" '
            'onclick="return confirm(\'Rad etilsinmi? Sabab «Rad etish sababi» maydonidan olinadi.\')">❌ Rad etish</button>'
            '<span style="color:#666;">Hozirgi balans: {} kredit</span></div>',
            reverse("admin:users_paymentrequest_approve", args=[obj.pk]), what,
            reverse("admin:users_paymentrequest_reject", args=[obj.pk]), profile.credits,
        )

    # --- qarorlar ---
    def _decide(self, request, req, approve, note=""):
        from .bot import notify_payment_result

        if approve:
            done = req.approve(request.user)
            action = "payment_approved"
        else:
            done = req.reject(request.user, note=note)
            action = "payment_rejected"
        if done:
            log_activity(request, action, user=req.user, payment=req.pk, plan=req.plan.name, amount=int(req.amount))
            notify_payment_result(req)
        return done

    def approve_view(self, request, pk):
        req = get_object_or_404(PaymentRequest, pk=pk)
        if request.method == "POST" and self._decide(request, req, True):
            messages.success(request, f"#{req.pk} tasdiqlandi, foydalanuvchiga botda xabar yuborildi.")
        else:
            messages.warning(request, f"#{req.pk} holati o'zgarmadi.")
        return redirect(reverse("admin:users_paymentrequest_changelist") + "?status__exact=pending")

    def reject_view(self, request, pk):
        req = get_object_or_404(PaymentRequest, pk=pk)
        note = request.POST.get("admin_note", "").strip() if request.method == "POST" else ""
        if request.method == "POST" and self._decide(request, req, False, note=note or "Chek ma'lumotlari mos kelmadi"):
            messages.success(request, f"#{req.pk} rad etildi, foydalanuvchiga sabab yuborildi.")
        else:
            messages.warning(request, f"#{req.pk} holati o'zgarmadi.")
        return redirect(reverse("admin:users_paymentrequest_changelist") + "?status__exact=pending")

    @admin.action(description="✅ Tanlanganlarni tasdiqlash")
    def approve_selected(self, request, queryset):
        count = sum(1 for req in queryset.select_related("plan", "user__profile") if self._decide(request, req, True))
        self.message_user(request, f"{count} ta to'lov tasdiqlandi.", messages.SUCCESS)

    @admin.action(description="❌ Tanlanganlarni rad etish")
    def reject_selected(self, request, queryset):
        count = sum(1 for req in queryset.select_related("plan", "user__profile")
                    if self._decide(request, req, False, note="Chek ma'lumotlari mos kelmadi"))
        self.message_user(request, f"{count} ta to'lov rad etildi.", messages.SUCCESS)


# ─── Foydalanuvchilar ─────────────────────────────────────────────────────────

class PaymentRequestInline(admin.TabularInline):
    model = PaymentRequest
    fk_name = "user"
    extra = 0
    fields = ("created_at", "plan", "amount", "status")
    readonly_fields = fields
    can_delete = False
    show_change_link = True

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user_link", "phone", "telegram", "credits", "pro_badge", "cv_count", "status_badge", "last_seen", "last_ip", "created_at")
    list_filter = ("is_blocked", "created_at", "last_seen")
    search_fields = ("user__username", "user__first_name", "user__last_name", "phone", "telegram_username", "last_ip")
    readonly_fields = ("user", "telegram_id", "created_at", "updated_at", "last_seen", "last_ip", "links")
    date_hierarchy = "created_at"
    actions = ("block_users", "unblock_users", "add_1_credit", "add_3_credits", "grant_30_days_pro", "remove_pro", "block_last_ips")
    list_per_page = 50
    fieldsets = (
        ("Foydalanuvchi", {"fields": ("user", "links", "phone", "telegram_id", "telegram_username")}),
        ("Balans", {"fields": ("credits", "current_plan", "premium_until")}),
        ("Bloklash", {"fields": ("is_blocked", "block_reason")}),
        ("Faollik", {"fields": ("last_seen", "last_ip", "created_at", "updated_at")}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user", "current_plan").annotate(_cvs=Count("user__cv"))

    @admin.display(description="Foydalanuvchi", ordering="user__first_name")
    def user_link(self, obj):
        return format_html('<b>{}</b>', obj.user.get_full_name() or obj.user.username)

    @admin.display(description="Telegram")
    def telegram(self, obj):
        return f"@{obj.telegram_username}" if obj.telegram_username else ("✓" if obj.telegram_id else "—")

    @admin.display(description="CV", ordering="_cvs")
    def cv_count(self, obj):
        return format_html('<a href="{}?user__id__exact={}">{}</a>', reverse("admin:cv_cv_changelist"), obj.user_id, obj._cvs)

    @admin.display(description="Pro")
    def pro_badge(self, obj):
        if obj.premium_until and obj.premium_until >= timezone.now():
            return badge(f"{obj.premium_until:%d.%m.%Y} gacha", "#dcfce7", "#166534")
        return "—"

    @admin.display(description="Holat", ordering="is_blocked")
    def status_badge(self, obj):
        return badge("Bloklangan", "#fee2e2", "#b91c1c") if obj.is_blocked else badge("Faol", "#dcfce7", "#166534")

    @admin.display(description="Havolalar")
    def links(self, obj):
        return format_html(
            '<a href="{}?user__id__exact={}">📄 CV lari</a> &nbsp;·&nbsp; <a href="{}?user__id__exact={}">🕓 Faolligi</a>'
            ' &nbsp;·&nbsp; <a href="{}?user__id__exact={}">💳 To\'lovlari</a> &nbsp;·&nbsp; <a href="{}?user__id__exact={}">✨ AI so\'rovlari</a>',
            reverse("admin:cv_cv_changelist"), obj.user_id, reverse("admin:core_activitylog_changelist"), obj.user_id,
            reverse("admin:users_paymentrequest_changelist"), obj.user_id, reverse("admin:cv_aiusage_changelist"), obj.user_id,
        )

    def save_model(self, request, obj, form, change):
        if change and "is_blocked" in form.changed_data:
            log_activity(request, "blocked" if obj.is_blocked else "unblocked", user=obj.user, by=request.user.username)
        super().save_model(request, obj, form, change)

    @admin.action(description="⛔ Bloklash")
    def block_users(self, request, queryset):
        for profile in queryset.select_related("user"):
            log_activity(request, "blocked", user=profile.user, by=request.user.username)
        queryset.update(is_blocked=True, block_reason="Admin tomonidan bloklandi")

    @admin.action(description="✅ Blokdan chiqarish")
    def unblock_users(self, request, queryset):
        queryset.update(is_blocked=False, block_reason="")

    @admin.action(description="⛔ Oxirgi IP larini ham bloklash")
    def block_last_ips(self, request, queryset):
        count = 0
        for ip in queryset.exclude(last_ip__isnull=True).values_list("last_ip", flat=True):
            count += BlockedIP.objects.get_or_create(ip=ip, defaults={"reason": "Foydalanuvchi bilan birga bloklandi"})[1]
        self.message_user(request, f"{count} ta IP bloklandi.", messages.SUCCESS)

    def _add_credits(self, request, queryset, n):
        from django.db.models import F

        queryset.update(credits=F("credits") + n)
        self.message_user(request, f"{queryset.count()} ta foydalanuvchiga {n} kredit qo'shildi.", messages.SUCCESS)

    @admin.action(description="🎟 +1 kredit")
    def add_1_credit(self, request, queryset):
        self._add_credits(request, queryset, 1)

    @admin.action(description="🎟 +3 kredit")
    def add_3_credits(self, request, queryset):
        self._add_credits(request, queryset, 3)

    @admin.action(description="⭐ 30 kunlik Pro berish")
    def grant_30_days_pro(self, request, queryset):
        plan = PricingPlan.objects.filter(scope=PricingPlan.SCOPE_ACCOUNT, is_active=True).order_by("sort_order").first()
        queryset.update(current_plan=plan, premium_until=timezone.now() + timedelta(days=30))
        self.message_user(request, "Pro berildi.", messages.SUCCESS)

    @admin.action(description="Pro ni olib tashlash")
    def remove_pro(self, request, queryset):
        queryset.update(current_plan=None, premium_until=None)


@admin.register(UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "plan", "status", "starts_at", "expires_at", "notes")
    list_filter = ("status", "plan")
    search_fields = ("user__username", "user__first_name", "user__profile__phone")


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    """Click/Payme ulanganda ishlatiladi."""
    list_display = ("merchant_transaction_id", "user", "provider", "amount", "status", "created_at")
    list_filter = ("provider", "status")
    readonly_fields = ("raw_request", "raw_response")


@admin.register(CompanyBranding)
class CompanyBrandingAdmin(admin.ModelAdmin):
    list_display = ("user", "name", "tagline", "is_active")


@admin.register(TelegramLoginToken)
class TelegramLoginTokenAdmin(admin.ModelAdmin):
    list_display = ("id", "phone", "telegram_username", "status", "created_at", "confirmed_at")
    list_filter = ("status",)
    search_fields = ("phone", "telegram_username")
    readonly_fields = ("token", "session_key")
