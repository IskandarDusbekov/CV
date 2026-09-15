from django.contrib import admin, messages
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.html import format_html

from .models import ActivityLog, BlockedIP, ContactMessage, ErrorLog, Page, SiteSettings


def badge(text, bg, fg):
    return format_html('<span style="background:{};color:{};padding:3px 9px;border-radius:999px;font-weight:700;font-size:12px;white-space:nowrap;">{}</span>', bg, fg, text)


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        ("Sayt", {"fields": ("site_name", "maintenance_message")}),
        ("💳 To'lov (bot orqali)", {
            "fields": ("card_number", "card_holder", "card_bank", "payment_instructions", "payment_notice"),
            "description": "Foydalanuvchi botda paket tanlaganda shu rekvizitlar ko'rsatiladi.",
        }),
        ("🤖 Telegram", {
            "fields": ("bot_username", "admin_chat_ids", "support_telegram"),
            "description": "Admin chat ID ni bilish uchun @userinfobot ga /start yozing. Bot tokeni xavfsizlik uchun .env da saqlanadi.",
        }),
        ("📞 Aloqa", {"fields": ("contact_phone", "contact_email", "contact_address", "working_hours")}),
        ("🎯 Bepul limitlar", {"fields": ("free_cv_limit", "free_tailor_limit", "tailor_per_unlocked_cv")}),
        ("✨ AI", {
            "fields": ("ai_model", "ai_price_input_per_1m", "ai_price_output_per_1m", "usd_to_uzs"),
            "description": "Narxlar AI xarajatini hisoblash uchun. OpenAI narxlari: platform.openai.com/docs/pricing",
        }),
    )

    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        obj = SiteSettings.load()
        return redirect(reverse("admin:core_sitesettings_change", args=[obj.pk]))


@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "is_published", "show_in_footer", "sort_order", "updated_at", "open_link")
    list_editable = ("is_published", "show_in_footer", "sort_order")
    prepopulated_fields = {"slug": ("title",)}

    @admin.display(description="Sahifa")
    def open_link(self, obj):
        return format_html('<a href="{}" target="_blank">Ochish ↗</a>', obj.get_absolute_url())


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("name", "contact", "short_message", "user", "status", "created_at")
    list_filter = ("is_resolved", "created_at")
    search_fields = ("name", "contact", "message")
    readonly_fields = ("name", "contact", "message", "user", "ip", "created_at")
    actions = ("mark_resolved",)

    @admin.display(description="Xabar")
    def short_message(self, obj):
        return obj.message[:80]

    @admin.display(description="Holat")
    def status(self, obj):
        return badge("Javob berildi", "#dcfce7", "#166534") if obj.is_resolved else badge("Yangi", "#fef3c7", "#92400e")

    @admin.action(description="Javob berildi deb belgilash")
    def mark_resolved(self, request, queryset):
        queryset.update(is_resolved=True)


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "action_badge", "user_link", "ip_link", "details", "path")
    list_filter = ("action", "created_at")
    search_fields = ("user__username", "user__first_name", "user__profile__phone", "ip", "meta")
    date_hierarchy = "created_at"
    list_per_page = 100
    actions = ("block_ips",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    @admin.display(description="Harakat", ordering="action")
    def action_badge(self, obj):
        colors = {
            "register": ("#dbeafe", "#1d4ed8"), "login": ("#e0f2fe", "#0369a1"), "logout": ("#f3f4f6", "#6b7280"),
            "cv_create": ("#dcfce7", "#166534"), "cv_tailor": ("#ede9fe", "#6d28d9"), "cv_unlock": ("#fef3c7", "#92400e"),
            "payment_request": ("#ffedd5", "#c2410c"), "payment_approved": ("#dcfce7", "#166534"),
            "payment_rejected": ("#fee2e2", "#b91c1c"), "blocked": ("#fee2e2", "#b91c1c"), "limit_reached": ("#fef9c3", "#854d0e"),
        }
        bg, fg = colors.get(obj.action, ("#f3f4f6", "#374151"))
        return badge(obj.get_action_display(), bg, fg)

    @admin.display(description="Foydalanuvchi")
    def user_link(self, obj):
        if not obj.user_id:
            return "anonim"
        return format_html('<a href="{}?user__id__exact={}">{}</a>', reverse("admin:core_activitylog_changelist"), obj.user_id,
                           obj.user.get_full_name() or obj.user.username)

    @admin.display(description="IP")
    def ip_link(self, obj):
        if not obj.ip:
            return "—"
        return format_html('<a href="{}?ip={}">{}</a>', reverse("admin:core_activitylog_changelist"), obj.ip, obj.ip)

    @admin.display(description="Tafsilot")
    def details(self, obj):
        return ", ".join(f"{k}: {v}" for k, v in (obj.meta or {}).items())[:120]

    @admin.action(description="Tanlangan yozuvlar IP larini bloklash")
    def block_ips(self, request, queryset):
        count = 0
        for ip in set(queryset.exclude(ip__isnull=True).values_list("ip", flat=True)):
            _, created = BlockedIP.objects.get_or_create(ip=ip, defaults={"reason": "Faollik jurnalidan bloklandi"})
            count += created
        self.message_user(request, f"{count} ta IP bloklandi.", messages.SUCCESS)


@admin.register(ErrorLog)
class ErrorLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "level_badge", "source", "short_message", "path", "user", "ip", "is_resolved")
    list_filter = ("is_resolved", "level", "source", "created_at")
    search_fields = ("message", "path", "traceback")
    readonly_fields = ("level", "source", "path", "method", "user", "ip", "message", "traceback_pre", "created_at")
    exclude = ("traceback",)
    date_hierarchy = "created_at"
    actions = ("mark_resolved",)

    def has_add_permission(self, request):
        return False

    @admin.display(description="Daraja")
    def level_badge(self, obj):
        return badge(obj.level, "#fee2e2", "#b91c1c") if obj.level in {"ERROR", "CRITICAL"} else badge(obj.level, "#fef3c7", "#92400e")

    @admin.display(description="Xabar")
    def short_message(self, obj):
        return obj.message[:100]

    @admin.display(description="Traceback")
    def traceback_pre(self, obj):
        return format_html('<pre style="white-space:pre-wrap;max-height:520px;overflow:auto;font-size:12px;">{}</pre>', obj.traceback or "—")

    @admin.action(description="Hal qilindi deb belgilash")
    def mark_resolved(self, request, queryset):
        queryset.update(is_resolved=True)


@admin.register(BlockedIP)
class BlockedIPAdmin(admin.ModelAdmin):
    list_display = ("ip", "reason", "created_at")
    search_fields = ("ip", "reason")
