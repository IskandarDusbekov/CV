from django.conf import settings
from django.contrib import messages
from django.db import connection
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import cache_control

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
    import json

    from django.utils.safestring import mark_safe

    from apps.cv.editor import _sample_context
    from apps.cv.models import ResumeSample

    templates = [{**t, **demo_template_context(t["code"])} for t in template_choices()]
    host = f"{request.scheme}://{request.get_host()}"
    site = SiteSettings.load()
    schema = [
        {"@context": "https://schema.org", "@type": "WebSite", "name": site.site_name, "url": f"{host}/", "inLanguage": "uz"},
        {"@context": "https://schema.org", "@type": "Organization", "name": site.site_name, "url": f"{host}/",
         "logo": f"{host}/static/brand/logo-mark-512.png"},
        {"@context": "https://schema.org", "@type": "SoftwareApplication", "name": site.site_name, "applicationCategory": "BusinessApplication",
         "operatingSystem": "Web", "url": f"{host}/", "inLanguage": ["uz", "ru", "en"],
         "description": site.seo_default_description,
         "offers": {"@type": "Offer", "price": "0", "priceCurrency": "UZS"}},
    ]
    return render(request, "core/home.html", {
        "templates": templates,
        "samples": [_sample_context(s) for s in ResumeSample.objects.filter(is_published=True)[:5]],
        "home_schema": mark_safe(json.dumps(schema, ensure_ascii=False).replace("<", "\\u003c")),
        **_plans(),
    })


def pricing(request):
    return render(request, "core/pricing.html", _plans())


def guide(request):
    import json

    from django.utils.safestring import mark_safe

    from .guide import SECTIONS, faq_schema

    from .guide import slugify_question

    sections = [{**s, "items": [{"q": q, "a": mark_safe(a), "n": f"{s['id']}-{i}", "slug": slugify_question(q)}
                                for i, (q, a) in enumerate(s["items"], 1)]}
                for s in SECTIONS]
    return render(request, "core/guide.html", {
        "sections": sections,
        "total": sum(len(s["items"]) for s in SECTIONS),
        # </script> ichida xavfsiz bo'lishi uchun "<" ni escape qilamiz
        "faq_schema": mark_safe(json.dumps(faq_schema(), ensure_ascii=False).replace("<", "\\u003c")),
    })


def guide_question(request, slug):
    """Qo'llanmadagi har bir savol — alohida sahifa: Google'da aynan shu savol bo'yicha chiqishi uchun."""
    import json

    from django.http import Http404
    from django.utils.safestring import mark_safe

    from .guide import find_question, plain_text, slugify_question

    item = find_question(slug)
    if item is None:
        raise Http404
    section = item["section"]
    siblings = [{"q": q, "slug": slugify_question(q)} for q, _ in section["items"] if slugify_question(q) != slug]
    answer_text = plain_text(item["a"])
    host = f"{request.scheme}://{request.get_host()}"
    schema = [
        {"@context": "https://schema.org", "@type": "FAQPage",
         "mainEntity": [{"@type": "Question", "name": item["q"], "acceptedAnswer": {"@type": "Answer", "text": answer_text}}]},
        {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Bosh sahifa", "item": f"{host}/"},
            {"@type": "ListItem", "position": 2, "name": "Qo'llanma", "item": f"{host}/qollanma/"},
            {"@type": "ListItem", "position": 3, "name": item["q"], "item": f"{host}/qollanma/{slug}/"},
        ]},
    ]
    return render(request, "core/guide_question.html", {
        "item": {**item, "a": mark_safe(item["a"])},
        "section": section,
        "siblings": siblings,
        "description": (answer_text[:152].rsplit(" ", 1)[0] + "…") if len(answer_text) > 155 else answer_text,
        "schema": mark_safe(json.dumps(schema, ensure_ascii=False).replace("<", "\\u003c")),
    })


def sitemap_xml(request):
    """Google va Yandex uchun barcha ochiq sahifalar ro'yxati."""
    from django.utils.html import escape

    from apps.cv.models import ResumeSample
    from apps.cv.services import ordered_templates

    from .guide import all_questions

    host = f"{request.scheme}://{request.get_host()}"
    urls = [("/", "1.0", "daily"), ("/namunalar/", "0.9", "weekly"), ("/cv/builder/", "0.9", "monthly"),
            ("/qollanma/", "0.9", "weekly"), ("/cv/templates/", "0.7", "monthly"), ("/pricing/", "0.6", "monthly"),
            ("/cv/namuna/", "0.6", "monthly"), ("/aloqa/", "0.3", "yearly")]
    urls += [(s.get_absolute_url(), "0.8", "monthly") for s in ResumeSample.objects.filter(is_published=True)]
    urls += [(f"/qollanma/{q['slug']}/", "0.7", "monthly") for q in all_questions()]
    urls += [(f"/cv/template-preview/{code}/", "0.5", "monthly") for code in ordered_templates()]
    urls += [(p.get_absolute_url(), "0.4", "monthly") for p in Page.objects.filter(is_published=True).exclude(slug="aloqa")]
    seen, body = set(), []
    for path, priority, freq in urls:
        if path in seen:
            continue
        seen.add(path)
        body.append(f"<url><loc>{escape(host + path)}</loc><changefreq>{freq}</changefreq><priority>{priority}</priority></url>")
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + "".join(body) + "</urlset>"
    return HttpResponse(xml, content_type="application/xml")


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


@cache_control(max_age=86400, public=True)
def robots_txt(request):
    lines = [
        "User-agent: *",
        f"Disallow: /{settings.ADMIN_URL}",
        "Disallow: /panel/",
        "Disallow: /users/",
        "Disallow: /cv/preview/",
        "Disallow: /cv/download/",
        "Disallow: /cv/dl/",
        "Disallow: /r/",
        "Disallow: /cv/share/",
        "Allow: /",
        "",
        f"Sitemap: {request.scheme}://{request.get_host()}/sitemap.xml",
    ]
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain")


def healthz(request):
    """Monitoring uchun: sayt va baza ishlayaptimi."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return JsonResponse({"status": "ok"})
    except Exception:
        return JsonResponse({"status": "db_error"}, status=503)


def _notify_admins(msg):
    try:
        from apps.users.bot import send_message

        for chat_id in SiteSettings.load().admin_chat_id_list:
            send_message(chat_id, f"✉️ <b>Yangi murojaat</b>\n👤 {msg.name} · {msg.contact}\n\n{msg.message[:1500]}")
    except Exception:
        pass
