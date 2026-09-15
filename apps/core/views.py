from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from apps.cv.services import demo_template_context, template_choices
from apps.users.models import PricingPlan

from .activity import client_ip, log_activity
from .models import ContactMessage, Page, SiteSettings


def _plans():
    plans = PricingPlan.objects.filter(is_active=True).order_by("sort_order", "price")
    return {
        "credit_packs": plans.filter(scope=PricingPlan.SCOPE_CREDITS),
        "pro_plan": plans.filter(scope=PricingPlan.SCOPE_ACCOUNT).first(),
    }


def home(request):
    templates = [{**t, **demo_template_context(t["code"])} for t in template_choices()]
    return render(request, "core/home.html", {"templates": templates, **_plans()})


def pricing(request):
    return render(request, "core/pricing.html", _plans())


def page(request, slug):
    obj = get_object_or_404(Page, slug=slug, is_published=True)
    return render(request, "core/page.html", {"page": obj})


def contact(request):
    obj = Page.objects.filter(slug="aloqa", is_published=True).first()
    if request.method == "POST":
        name = request.POST.get("name", "").strip()[:120]
        contact_value = request.POST.get("contact", "").strip()[:150]
        text = request.POST.get("message", "").strip()[:4000]
        if request.POST.get("website"):  # bot-tuzoq maydon
            return redirect("contact")
        if not (name and contact_value and len(text) >= 5):
            messages.error(request, "Ism, aloqa ma'lumoti va xabarni to'ldiring.")
        else:
            msg = ContactMessage.objects.create(
                name=name, contact=contact_value, message=text, ip=client_ip(request),
                user=request.user if request.user.is_authenticated else None,
            )
            log_activity(request, "contact", message=msg.pk)
            _notify_admins(msg)
            messages.success(request, "Xabaringiz yuborildi! Tez orada javob beramiz.")
            return redirect("contact")
    return render(request, "core/contact.html", {"page": obj})


def _notify_admins(msg):
    try:
        from apps.users.bot import send_message

        for chat_id in SiteSettings.load().admin_chat_id_list:
            send_message(chat_id, f"✉️ <b>Yangi murojaat</b>\n👤 {msg.name} · {msg.contact}\n\n{msg.message[:1500]}")
    except Exception:
        pass
