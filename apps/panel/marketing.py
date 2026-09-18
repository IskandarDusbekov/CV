"""Panelning marketing bo'limlari: aksiyalar, takliflar, namunalar, shablonlar va SEO."""
from django.contrib import messages
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.models import SeoPage, SiteSettings
from apps.cv.models import CV, ResumeSample, TemplateSetting
from apps.cv.services import TEMPLATE_META, demo_template_context
from apps.users.models import Promo, PromoGrant, Referral

from .forms import PromoForm, SampleForm, SeoPageForm, SeoSettingsForm, TemplateSettingFormSet
from .views import _page, staff_required, superuser_required


# ─── Aksiyalar ────────────────────────────────────────────────────────────────

def _clear_promo_cache():
    from django.core.cache import cache

    cache.delete("banner_promo")


@superuser_required
def promos(request, pk=None):
    instance = get_object_or_404(Promo, pk=pk) if pk else None
    form = PromoForm(instance=instance)
    if request.method == "POST":
        form = PromoForm(request.POST, instance=instance)
        if form.is_valid():
            promo = form.save()
            _clear_promo_cache()
            messages.success(request, f"«{promo.name}» saqlandi.")
            return redirect("panel:promos")
        messages.error(request, "Formada xatolik bor.")
    elif instance is None:
        now = timezone.localtime().replace(minute=0, second=0, microsecond=0)
        form = PromoForm(initial={"starts_at": now, "ends_at": now + timezone.timedelta(days=7), "bonus_credits": 1,
                                  "banner_text": "🎁 Aksiya: ro'yxatdan o'ting va 1 ta rezyumeni tekin oching!"})

    now = timezone.now()
    items = Promo.objects.annotate(n=Count("grants"), credits=Sum("grants__credits")).order_by("-starts_at")
    for p in items:
        p.state = "running" if p.is_active and p.starts_at <= now <= p.ends_at else ("scheduled" if p.is_active and p.starts_at > now else "ended")
    return render(request, "panel/promos.html", {"form": form, "instance": instance, "items": items})


@superuser_required
@require_POST
def promo_delete(request, pk):
    promo = get_object_or_404(Promo, pk=pk)
    if promo.grants.exists():
        promo.is_active = False
        promo.save(update_fields=["is_active"])
        messages.warning(request, "Aksiya bo'yicha bonus berilgan — o'chirish o'rniga to'xtatildi.")
    else:
        promo.delete()
        messages.success(request, "O'chirildi.")
    _clear_promo_cache()
    return redirect("panel:promos")


# ─── Takliflar ────────────────────────────────────────────────────────────────

@staff_required
def referrals(request):
    qs = Referral.objects.select_related("inviter", "invitee", "inviter__profile", "invitee__profile")
    today = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    top = (Referral.objects.values("inviter", "inviter__first_name", "inviter__last_name", "inviter__profile__phone")
           .annotate(n=Count("id"), credits=Sum("inviter_credits")).order_by("-n")[:10])
    return render(request, "panel/referrals.html", {
        "page": _page(request, qs, 40),
        "total": qs.count(),
        "today": qs.filter(created_at__gte=today).count(),
        "credits": qs.aggregate(s=Sum("inviter_credits"))["s"] or 0,
        "top": top,
        "site": SiteSettings.load(),
    })


# ─── Namunalar ────────────────────────────────────────────────────────────────

@staff_required
def samples(request):
    items = ResumeSample.objects.all()
    return render(request, "panel/samples.html", {"items": items, "total_uses": sum(s.uses for s in items)})


@staff_required
def sample_edit(request, pk=None):
    instance = get_object_or_404(ResumeSample, pk=pk) if pk else None
    initial = {}
    from_cv = request.GET.get("from_cv")
    if instance is None and from_cv:
        cv = get_object_or_404(CV, public_id=from_cv)
        data = dict(cv.cv_json) if isinstance(cv.cv_json, dict) else {}
        initial = {"cv_json": data, "profession": data.get("job_title", ""), "template_code": cv.selected_template, "is_published": False}
    form = SampleForm(instance=instance, initial=initial)
    if request.method == "POST":
        form = SampleForm(request.POST, instance=instance)
        if form.is_valid():
            sample = form.save()
            messages.success(request, f"«{sample.profession}» saqlandi.")
            return redirect("panel:samples")
        messages.error(request, "Formada xatolik bor.")
    return render(request, "panel/sample_edit.html", {"form": form, "instance": instance})


@staff_required
@require_POST
def sample_delete(request, pk):
    get_object_or_404(ResumeSample, pk=pk).delete()
    messages.success(request, "Namuna o'chirildi.")
    return redirect("panel:samples")


# ─── Shablonlar ───────────────────────────────────────────────────────────────

@superuser_required
def templates_view(request):
    for i, code in enumerate(TEMPLATE_META):
        TemplateSetting.objects.get_or_create(code=code, defaults={"sort_order": 200 + i})
    qs = TemplateSetting.objects.filter(code__in=list(TEMPLATE_META)).order_by("sort_order", "code")
    formset = TemplateSettingFormSet(queryset=qs)
    if request.method == "POST":
        formset = TemplateSettingFormSet(request.POST, queryset=qs)
        if formset.is_valid():
            formset.save()
            from django.core.cache import cache

            cache.delete("template_settings")
            messages.success(request, "Shablonlar saqlandi.")
            return redirect("panel:templates")
        messages.error(request, "Formada xatolik bor.")
    usage = dict(CV.objects.values_list("selected_template").annotate(n=Count("id")).values_list("selected_template", "n"))
    unlocked = dict(CV.objects.filter(Q(is_unlocked=True) | Q(free_pdf=True)).values_list("selected_template")
                    .annotate(n=Count("id")).values_list("selected_template", "n"))
    rows = [{"form": f, "code": f.instance.code, "meta": TEMPLATE_META[f.instance.code], "uses": usage.get(f.instance.code, 0),
             "downloads": unlocked.get(f.instance.code, 0), **demo_template_context(f.instance.code)} for f in formset.forms]
    return render(request, "panel/templates.html", {"formset": formset, "rows": rows})


# ─── «Baxtli foydalanuvchi» sovg'asi ──────────────────────────────────────────

@superuser_required
def lucky(request):
    from apps.cv.models import LuckyGift, LuckyGrant

    from .forms import LuckyGiftForm

    gift = LuckyGift.load()
    form = LuckyGiftForm(instance=LuckyGift.objects.get(pk=gift.pk))
    if request.method == "POST":
        form = LuckyGiftForm(request.POST, instance=LuckyGift.objects.get(pk=gift.pk))
        if form.is_valid():
            form.save()
            messages.success(request, "Saqlandi — o'zgarishlar darhol saytda ko'rinadi.")
            return redirect("panel:lucky")
        messages.error(request, "Formada xatolik bor.")
        gift = form.instance

    today = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    grants = LuckyGrant.objects.select_related("user__profile", "cv")
    answered = dict(grants.exclude(reaction="").order_by().values_list("reaction").annotate(c=Count("id")))
    reactions = [{"label": label, "n": answered.pop(label, 0)} for label in gift.options]
    reactions += [{"label": label, "n": n} for label, n in answered.items()]
    return render(request, "panel/lucky.html", {
        "form": form,
        "gift": gift,
        "total": grants.count(),
        "today": grants.filter(created_at__gte=today).count(),
        "downloaded": grants.filter(downloaded=True).count(),
        "reactions": reactions,
        "reactions_total": sum(r["n"] for r in reactions),
        "page": _page(request, grants, 30),
    })


# ─── SEO ──────────────────────────────────────────────────────────────────────

@superuser_required
def seo(request, pk=None):
    site = SiteSettings.objects.get(pk=SiteSettings.load().pk)
    settings_form = SeoSettingsForm(instance=site)
    page_instance = get_object_or_404(SeoPage, pk=pk) if pk else None
    page_form = SeoPageForm(instance=page_instance)
    if request.method == "POST":
        section = request.POST.get("section")
        if section == "settings":
            settings_form = SeoSettingsForm(request.POST, instance=site)
            if settings_form.is_valid():
                settings_form.save()
                messages.success(request, "SEO sozlamalari saqlandi.")
                return redirect("panel:seo")
        elif section == "page":
            page_form = SeoPageForm(request.POST, instance=page_instance)
            if page_form.is_valid():
                page_form.save()
                messages.success(request, "Sahifa sozlamasi saqlandi.")
                return redirect("panel:seo")
        elif section == "delete" and page_instance:
            page_instance.delete()
            messages.success(request, "O'chirildi.")
            return redirect("panel:seo")
        messages.error(request, "Formada xatolik bor.")
    host = f"{request.scheme}://{request.get_host()}"
    return render(request, "panel/seo.html", {
        "settings_form": settings_form, "page_form": page_form, "page_instance": page_instance,
        "pages": SeoPage.objects.all(), "sitemap_url": f"{host}/sitemap.xml", "host": host,
        "samples_count": ResumeSample.objects.filter(is_published=True).count(),
    })
