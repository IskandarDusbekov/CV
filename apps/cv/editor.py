"""Tayyor namunalar (SEO sahifalar) va rezyumeni qo'lda tahrirlash — AI'siz, bepul."""
import copy
import json
import re

from django.contrib import messages
from django.db.models import F
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.safestring import mark_safe
from django.views.decorators.http import require_POST

from apps.core.activity import log_activity

from .models import CV, ResumeSample
from .services import TEMPLATE_META, normalize_cv_data, resolve_template_name, template_is_pro

MAX_ITEMS = 12
ANON_SAMPLE_LIMIT = 10


# ─── Namunalar ────────────────────────────────────────────────────────────────

def _sample_context(sample):
    code = resolve_template_name(sample.template_code)
    return {
        "sample": sample,
        "cv_data": normalize_cv_data(sample.cv_json),
        "template_partial": f"cv/partials/cv_template_{code}.html",
        "template_label": TEMPLATE_META[code]["label"],
        "template_pro": template_is_pro(code),
        "show_watermark": False,
        "company_branding": None,
    }


def samples_list(request):
    samples = ResumeSample.objects.filter(is_published=True)
    items = [_sample_context(s) for s in samples]
    categories = sorted({s.category for s in samples if s.category})
    return render(request, "cv/samples_list.html", {"items": items, "categories": categories})


def sample_detail(request, slug):
    sample = get_object_or_404(ResumeSample, slug=slug, is_published=True)
    related = ResumeSample.objects.filter(is_published=True).exclude(pk=sample.pk)
    if sample.category:
        related = sorted(related, key=lambda s: s.category != sample.category)[:4]
    else:
        related = list(related[:4])
    host = f"{request.scheme}://{request.get_host()}"
    breadcrumbs = {
        "@context": "https://schema.org", "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Bosh sahifa", "item": f"{host}/"},
            {"@type": "ListItem", "position": 2, "name": "Rezyume namunalari", "item": f"{host}/namunalar/"},
            {"@type": "ListItem", "position": 3, "name": sample.profession, "item": f"{host}{sample.get_absolute_url()}"},
        ],
    }
    return render(request, "cv/sample_detail.html", {
        **_sample_context(sample),
        "paragraphs": [p.strip() for p in sample.intro.split("\n\n") if p.strip()],
        "related": [_sample_context(s) for s in related],
        "breadcrumbs_json": mark_safe(json.dumps(breadcrumbs, ensure_ascii=False).replace("<", "\\u003c")),
    })


@require_POST
def sample_use(request, slug):
    """Namunadan nusxa olib, tahrirlash sahifasini ochadi. AI ishlatilmaydi — bepul limitdan ham ketmaydi."""
    sample = get_object_or_404(ResumeSample, slug=slug, is_published=True)
    data = copy.deepcopy(sample.cv_json)
    user = request.user if request.user.is_authenticated else None
    if user is None:
        used = request.session.get("sample_cvs", 0)
        if used >= ANON_SAMPLE_LIMIT:
            messages.warning(request, "Ko'p namuna ochdingiz. Davom etish uchun Telegram orqali kiring — atigi 2 bosqich.")
            return redirect(f"/users/login/?next=/namunalar/{sample.slug}/")
        request.session["sample_cvs"] = used + 1
    else:
        # Telegram orqali kirganlarning ismi va raqami allaqachon bor
        profile = getattr(user, "profile", None)
        if user.get_full_name():
            data["full_name"] = user.get_full_name()
        if profile and profile.phone:
            data["phone"] = profile.phone
        data["email"] = ""

    cv = CV.objects.create(user=user, raw_input_text=f"[namuna: {sample.profession}]", target_job=sample.profession,
                           cv_json=data, selected_template=resolve_template_name(sample.template_code))
    if user is None:
        request.session["owned_cv_ids"] = request.session.get("owned_cv_ids", []) + [cv.id]
    ResumeSample.objects.filter(pk=sample.pk).update(uses=F("uses") + 1)
    log_activity(request, "cv_create", cv=str(cv.public_id), sample=sample.slug)
    from apps.core.analytics import mark_step

    mark_step(request, "generate")
    return redirect(f"/cv/edit/{cv.public_id}/?new=1")


# ─── Tahrirlash ───────────────────────────────────────────────────────────────

def _clean(value, limit=200):
    return re.sub(r"[ \t]+", " ", str(value or "")).strip()[:limit]


def _lines(value, limit=300, max_items=20):
    parts = re.split(r"[\r\n]+", str(value or ""))
    return [_clean(p.lstrip("•-–— "), limit) for p in parts if _clean(p.lstrip("•-–— "))][:max_items]


def _csv_or_lines(value, max_items=30):
    parts = re.split(r"[\r\n,;]+", str(value or ""))
    return [_clean(p, 80) for p in parts if _clean(p)][:max_items]


def _indexed(post, prefix):
    indexes = sorted({int(m.group(1)) for key in post for m in [re.match(rf"^{prefix}-(\d+)-", key)] if m})
    return indexes[:MAX_ITEMS]


def parse_editor_post(post, previous):
    data = {k: v for k, v in (previous or {}).items() if k.startswith("_")}
    for field in ("full_name", "job_title", "email", "phone", "location", "github", "linkedin"):
        data[field] = _clean(post.get(field), 150)
    data["summary"] = _clean(post.get("summary"), 1500)
    data["skills"] = _csv_or_lines(post.get("skills"))
    data["languages"] = _lines(post.get("languages"), 80, 10)
    data["experience"] = [
        item for item in (
            {
                "position": _clean(post.get(f"exp-{i}-position"), 150),
                "company": _clean(post.get(f"exp-{i}-company"), 150),
                "duration": _clean(post.get(f"exp-{i}-duration"), 60),
                "responsibilities": _lines(post.get(f"exp-{i}-responsibilities"), 300, 10),
            } for i in _indexed(post, "exp")
        ) if item["position"] or item["company"] or item["responsibilities"]
    ]
    data["education"] = [
        item for item in (
            {
                "institution": _clean(post.get(f"edu-{i}-institution"), 200),
                "degree": _clean(post.get(f"edu-{i}-degree"), 200),
                "year": _clean(post.get(f"edu-{i}-year"), 60),
            } for i in _indexed(post, "edu")
        ) if item["institution"] or item["degree"]
    ]
    data["projects"] = [
        item for item in (
            {
                "title": _clean(post.get(f"proj-{i}-title"), 150),
                "description": _clean(post.get(f"proj-{i}-description"), 500),
                "technologies": _csv_or_lines(post.get(f"proj-{i}-technologies"), 10),
            } for i in _indexed(post, "proj")
        ) if item["title"] or item["description"]
    ]
    return data


def edit_cv(request, cv_id):
    from .views import _private_cv

    cv = _private_cv(request, cv_id, staff_ok=False)
    if request.method == "POST":
        data = parse_editor_post(request.POST, cv.cv_json if isinstance(cv.cv_json, dict) else {})
        if not data["full_name"]:
            messages.error(request, "Ism va familiyani yozing.")
        else:
            old_name = _clean((cv.cv_json or {}).get("full_name", "") if isinstance(cv.cv_json, dict) else "").lower()
            fields = ["cv_json", "updated_at"]
            if cv.free_pdf and not cv.is_unlocked and old_name and data["full_name"].lower() != old_name:
                # Bepul PDF bitta odamning rezyumesi uchun: ismni almashtirib boshqa rezyume qilib bo'lmaydi
                cv.free_pdf = False
                fields.append("free_pdf")
            cv.cv_json = data
            cv.save(update_fields=fields)
            log_activity(request, "cv_edit", cv=str(cv.public_id))
            messages.success(request, "Saqlandi ✅")
            return redirect("cv_preview", cv_id=cv.public_id)

    raw = cv.cv_json if isinstance(cv.cv_json, dict) else {}
    normalized = normalize_cv_data(raw)
    return render(request, "cv/editor.html", {
        "cv": cv,
        "d": {**normalized, "full_name": raw.get("full_name", ""), "job_title": raw.get("job_title", "")},
        "skills_text": "\n".join(normalized["skills"]),
        "languages_text": "\n".join(normalized["languages"]),
        "is_new": request.GET.get("new") == "1",
    })
