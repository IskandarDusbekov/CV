from django.contrib import admin
from django.db.models import Count, Sum
from django.urls import reverse
from django.utils.html import format_html

from apps.core.models import SiteSettings

from .models import CV, AIUsage


@admin.register(CV)
class CVAdmin(admin.ModelAdmin):
    list_display = ("full_name", "job_title", "owner", "selected_template", "unlocked_badge", "tailored_badge", "created_at", "open_links")
    list_filter = ("selected_template", "is_unlocked", "is_public_share_enabled", "created_at")
    search_fields = ("public_id", "cv_json__full_name", "cv_json__job_title", "user__username", "user__profile__phone", "raw_input_text")
    readonly_fields = ("public_id", "user", "parent", "open_links", "created_at", "updated_at", "unlocked_at", "share_token", "tailor_report")
    date_hierarchy = "created_at"
    list_select_related = ("user",)
    list_per_page = 50
    fieldsets = (
        ("CV", {"fields": ("open_links", "public_id", "user", "selected_template", "is_unlocked", "unlocked_at", "is_public_share_enabled", "share_token")}),
        ("Foydalanuvchi yozgani", {"fields": ("raw_input_text", "target_job"), "classes": ("collapse",)}),
        ("Vakansiyaga moslashtirish", {"fields": ("parent", "job_description", "tailor_report"), "classes": ("collapse",)}),
        ("AI natija (JSON)", {"fields": ("cv_json",), "classes": ("collapse",)}),
        ("Vaqt", {"fields": ("created_at", "updated_at")}),
    )

    @admin.display(description="Ism")
    def full_name(self, obj):
        return (obj.cv_json or {}).get("full_name", "—")

    @admin.display(description="Lavozim")
    def job_title(self, obj):
        return (obj.cv_json or {}).get("job_title", "")[:40]

    @admin.display(description="Egasi", ordering="user__first_name")
    def owner(self, obj):
        if not obj.user_id:
            return "anonim"
        return obj.user.get_full_name() or obj.user.username

    @admin.display(description="Ochiq", ordering="is_unlocked")
    def unlocked_badge(self, obj):
        return "✅" if obj.is_unlocked else ""

    @admin.display(description="Moslashtirilgan")
    def tailored_badge(self, obj):
        return (obj.tailor_report or {}).get("vacancy_title", "🎯") if obj.parent_id else ""

    @admin.display(description="Ko'rish")
    def open_links(self, obj):
        return format_html(
            '<a href="{}" target="_blank">👁 Ko\'rish</a> &nbsp; <a href="{}" target="_blank">PDF</a> &nbsp; <a href="{}">Word</a>',
            reverse("cv_preview", args=[obj.public_id]), reverse("view_pdf", args=[obj.public_id]), reverse("download_docx", args=[obj.public_id]),
        )


@admin.register(AIUsage)
class AIUsageAdmin(admin.ModelAdmin):
    list_display = ("created_at", "kind", "who", "model", "prompt_tokens", "completion_tokens", "cost_display", "duration", "success_badge", "cv_link")
    list_filter = ("kind", "success", "model", "created_at")
    search_fields = ("user__username", "user__profile__phone", "ip", "error")
    date_hierarchy = "created_at"
    list_per_page = 100
    change_list_template = "admin/cv/aiusage/change_list.html"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        response = super().changelist_view(request, extra_context)
        try:
            qs = response.context_data["cl"].queryset
        except (AttributeError, KeyError):
            return response
        totals = qs.aggregate(cost=Sum("cost_usd"), prompt=Sum("prompt_tokens"), completion=Sum("completion_tokens"), n=Count("id"))
        cost = totals["cost"] or 0
        response.context_data["ai_totals"] = {
            **totals,
            "cost": cost,
            "cost_uzs": int(float(cost) * SiteSettings.load().usd_to_uzs),
            "failed": qs.filter(success=False).count(),
        }
        return response

    @admin.display(description="Kim")
    def who(self, obj):
        return obj.user.get_full_name() or obj.user.username if obj.user_id else (obj.ip or "anonim")

    @admin.display(description="Narx", ordering="cost_usd")
    def cost_display(self, obj):
        return f"${obj.cost_usd:.5f}"

    @admin.display(description="Vaqt")
    def duration(self, obj):
        return f"{obj.duration_ms / 1000:.1f} s"

    @admin.display(description="Natija", ordering="success")
    def success_badge(self, obj):
        return "✅" if obj.success else format_html('<span title="{}">❌ xato</span>', obj.error[:300])

    @admin.display(description="CV")
    def cv_link(self, obj):
        if not obj.cv_id:
            return "—"
        return format_html('<a href="{}" target="_blank">ochish</a>', reverse("cv_preview", args=[obj.cv.public_id]))
