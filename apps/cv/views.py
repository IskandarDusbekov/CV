import logging
import os
import re
from urllib.parse import quote

from django.conf import settings
from django.contrib import messages
from django.db.models import F
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.core.activity import log_activity
from apps.users.models import CompanyBranding, PricingPlan, UserProfile

from . import quotas
from .models import CV, AIUsage
from .pdf import PdfRenderError, render_cv_to_pdf
from .services import (
    DEFAULT_TEMPLATE,
    TEMPLATE_META,
    AIError,
    build_cv_context,
    demo_template_context,
    generate_cv_from_text,
    resolve_template_name,
    tailor_cv_to_job,
    template_choices,
    user_can_download_docx,
    user_can_download_pdf,
    user_can_share_cv,
)

logger = logging.getLogger("apps.cv")


def example(request):
    """'Bepul CV yaratish' dan keyin birinchi ko'rinadigan tayyor namuna."""
    templates = [{**t, **demo_template_context(t["code"])} for t in template_choices(DEFAULT_TEMPLATE)]
    return render(request, "cv/example.html", {"templates": templates, "quota": quotas.generate_quota(request)})


def builder(request):
    initial = resolve_template_name(request.GET.get("template", DEFAULT_TEMPLATE))
    return render(request, "cv/builder.html", {
        "initial_template": initial,
        "quota": quotas.generate_quota(request),
        "pro_plan": _active_plans(PricingPlan.SCOPE_ACCOUNT).first(),
    })


def preview(request, cv_id):
    cv = _private_cv(request, cv_id)
    context = build_cv_context(cv, request.user)
    context.update({
        "share_url": _build_share_url(request, cv) if cv.is_public_share_enabled and cv.share_token else "",
        "credit_packs": _active_plans(PricingPlan.SCOPE_CREDITS),
        "pro_plan": _active_plans(PricingPlan.SCOPE_ACCOUNT).first(),
        "user_credits": _credits(request.user),
        "login_url": f"{reverse('user_login')}?next={quote(request.path)}",
        "tailor_quota": quotas.tailor_quota(request, cv),
        "unlock_target": cv.root,
        "is_staff_view": request.user.is_staff and not _is_owner(request.user, cv),
    })
    return render(request, "cv/preview.html", context)


@require_POST
def unlock_with_credit(request, cv_id):
    """1 kredit sarflab CV ni (va uning moslashtirilgan versiyalarini) ochish."""
    cv = _private_cv(request, cv_id)
    if not request.user.is_authenticated:
        return redirect(f"{reverse('user_login')}?next={quote(reverse('cv_preview', args=[cv.public_id]))}")
    root = cv.root
    if root.is_unlocked:
        return redirect("cv_preview", cv_id=cv.public_id)

    # Atomar: kredit 0 dan kichik bo'lib ketmaydi, parallel so'rovlar ikki marta yechmaydi
    spent = UserProfile.objects.filter(user=request.user, credits__gt=0).update(credits=F("credits") - 1)
    if not spent:
        messages.warning(request, "Kreditingiz qolmagan. Botda paket sotib oling — tasdiqlangach avtomatik qo'shiladi.")
        return redirect(f"{reverse('cv_preview', args=[cv.public_id])}#unlock")

    if root.user_id is None:
        root.user = request.user
    root.unlock(save=False)
    root.save(update_fields=["user", "is_unlocked", "unlocked_at", "updated_at"])
    log_activity(request, "cv_unlock", cv=str(root.public_id))
    messages.success(request, "CV ochildi! Endi PDF va Word yuklab olishingiz mumkin.")
    return redirect("cv_preview", cv_id=cv.public_id)


@require_POST
def tailor_cv(request, cv_id):
    cv = _private_cv(request, cv_id, staff_ok=False)

    job_description = request.POST.get("job_description", "").strip()
    if len(job_description) < 80:
        messages.error(request, "Vakansiya matnini to'liqroq qo'ying — talablar va vazifalar bilan.")
        return redirect("cv_preview", cv_id=cv.public_id)

    quota = quotas.tailor_quota(request, cv)
    if not quota.allowed:
        log_activity(request, "limit_reached", kind="tailor")
        messages.warning(request, quota.message)
        return redirect("cv_preview", cv_id=cv.public_id)

    root = cv.root
    try:
        new_json, report, meta = tailor_cv_to_job(cv.cv_json, job_description[:8000])
    except AIError as exc:
        quotas.record(request, AIUsage.KIND_TAILOR, cv=root, meta=exc.meta, error=str(exc))
        logger.error("AI tailor failed: %s", exc, extra={"request": request})
        messages.error(request, "AI hozir moslashtira olmadi, bir daqiqadan so'ng qayta urinib ko'ring.")
        return redirect("cv_preview", cv_id=cv.public_id)

    tailored = CV.objects.create(
        user=cv.user,
        parent=root,
        raw_input_text=root.raw_input_text,
        target_job=report.get("vacancy_title") or cv.target_job,
        cv_json=new_json,
        selected_template=cv.selected_template,
        photo=cv.photo.name if cv.photo else None,
        job_description=job_description,
        tailor_report=report,
    )
    quotas.record(request, AIUsage.KIND_TAILOR, cv=root, meta=meta)
    log_activity(request, "cv_tailor", cv=str(tailored.public_id), vacancy=report.get("vacancy_title", ""))
    if not request.user.is_authenticated:
        request.session["owned_cv_ids"] = request.session.get("owned_cv_ids", []) + [tailored.id]

    messages.success(request, "Tayyor! CV vakansiyaga moslashtirildi — asl nusxa o'zgarmadi.")
    return redirect("cv_preview", cv_id=tailored.public_id)


def shared_preview(request, token):
    cv = get_object_or_404(CV, share_token=token, is_public_share_enabled=True)
    context = build_cv_context(cv, cv.user)
    context["company_branding"] = _get_company_branding(cv.user) if context["is_pro"] else None
    return render(request, "cv/shared_preview.html", context)


def download_pdf(request, cv_id, inline=False):
    cv = _downloadable_cv(request, cv_id)
    if isinstance(cv, HttpResponse):
        return cv
    if not user_can_download_pdf(request.user, cv):
        messages.warning(request, "Yuklab olish uchun CV'ni kredit yoki Pro bilan oching.")
        return redirect("cv_preview", cv_id=cv.public_id)

    try:
        pdf_file = render_cv_to_pdf(cv, request.user, company_branding=_get_company_branding(request.user))
    except PdfRenderError as exc:
        logger.error("PDF render failed for CV %s: %s", cv.public_id, exc, extra={"request": request})
        detail = f"\n\n{exc}\n\nPlaywright brauzeri o'rnatilmagan bo'lsa: python -m playwright install chromium" if settings.DEBUG else ""
        return HttpResponse(f"PDF yaratishda xatolik yuz berdi. Iltimos, qayta urinib ko'ring.{detail}",
                            status=500, content_type="text/plain; charset=utf-8")

    log_activity(request, "download_pdf", cv=str(cv.public_id), template=cv.selected_template)
    disposition = "inline" if (inline or request.GET.get("inline")) else "attachment"
    return _file_response(pdf_file, "application/pdf", _filename(cv, "pdf"), disposition)


def download_docx(request, cv_id):
    cv = _downloadable_cv(request, cv_id)
    if isinstance(cv, HttpResponse):
        return cv
    if not user_can_download_docx(request.user, cv):
        messages.warning(request, "Yuklab olish uchun CV'ni kredit yoki Pro bilan oching.")
        return redirect("cv_preview", cv_id=cv.public_id)

    from .docx_export import render_cv_to_docx

    content = render_cv_to_docx(cv, request.user)
    log_activity(request, "download_docx", cv=str(cv.public_id), template=cv.selected_template)
    return _file_response(
        content,
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        _filename(cv, "docx"),
        "attachment",
    )


def templates_showcase(request):
    templates = [{**t, **demo_template_context(t["code"])} for t in template_choices()]
    return render(request, "cv/templates_showcase.html", {"templates": templates})


def template_preview(request, code):
    code = resolve_template_name(code)
    context = demo_template_context(code)
    context.update({
        "is_ats_template": TEMPLATE_META[code]["ats"],
        "tagline": TEMPLATE_META[code]["tagline"],
        "all_templates": template_choices(code),
    })
    return render(request, "cv/template_preview.html", context)


@require_POST
def upload_photo(request, cv_id):
    cv = _private_cv(request, cv_id, staff_ok=False)
    photo_file = request.FILES.get("photo")
    if not photo_file:
        return JsonResponse({"error": "Rasm tanlanmadi"}, status=400)
    if not _is_valid_image(photo_file):
        return JsonResponse({"error": "Faqat JPG/PNG/WEBP, maksimal 5 MB"}, status=400)

    if cv.photo:
        try:
            cv.photo.delete(save=False)
        except Exception:
            pass

    cv.photo = photo_file
    cv.save(update_fields=["photo", "updated_at"])
    return JsonResponse({"success": True, "photo_url": cv.photo.url})


@require_POST
def remove_photo(request, cv_id):
    cv = _private_cv(request, cv_id, staff_ok=False)
    if cv.photo:
        try:
            cv.photo.delete(save=False)
        except Exception:
            pass
        cv.photo = None
        cv.save(update_fields=["photo", "updated_at"])
    return JsonResponse({"success": True})


@require_POST
def toggle_share_link(request, cv_id):
    cv = get_object_or_404(CV, public_id=cv_id)
    if not _is_owner(request.user, cv):
        raise Http404("CV topilmadi.")
    if not user_can_share_cv(request.user, cv):
        messages.warning(request, "Ommaviy havola CV ochilgandan so'ng ishlaydi.")
        return redirect("cv_preview", cv_id=cv.public_id)

    if request.POST.get("action", "enable").strip().lower() == "disable":
        cv.is_public_share_enabled = False
        cv.save(update_fields=["is_public_share_enabled", "updated_at"])
        messages.success(request, "Ommaviy havola o'chirildi.")
    else:
        cv.ensure_share_token(save=False)
        cv.is_public_share_enabled = True
        cv.save(update_fields=["share_token", "is_public_share_enabled", "updated_at"])
        messages.success(request, "Ommaviy havola yoqildi.")

    return redirect("cv_preview", cv_id=cv.public_id)


@require_POST
def change_template(request, cv_id):
    cv = _private_cv(request, cv_id, staff_ok=False)
    # Har qanday shablonni ko'rish bepul — yuklab olishda huquq tekshiriladi
    cv.selected_template = resolve_template_name(request.POST.get("template_code", ""))
    cv.save(update_fields=["selected_template", "updated_at"])
    log_activity(request, "cv_template", cv=str(cv.public_id), template=cv.selected_template)
    return redirect("cv_preview", cv_id=cv.public_id)


@require_POST
def generate_cv(request):
    text = request.POST.get("text", "").strip()[:6000]
    target_job = request.POST.get("target_job", "").strip()
    language = request.POST.get("language", "auto").strip()
    enrich = request.POST.get("enrich", "0") == "1"
    template_code = resolve_template_name(request.POST.get("selected_template", DEFAULT_TEMPLATE).strip())

    if len(text) < 20:
        return JsonResponse({"error": "Bir-ikki gap bo'lsa ham yozing: ismingiz, nima ish qilgansiz, nimalarni bilasiz."}, status=400)

    quota = quotas.generate_quota(request)
    if not quota.allowed:
        log_activity(request, "limit_reached", kind="generate")
        return JsonResponse({"error": quota.message, "limit_reached": True}, status=403)

    try:
        result, meta = generate_cv_from_text(text, target_job, language=language, enrich=enrich)
    except AIError as exc:
        quotas.record(request, AIUsage.KIND_GENERATE, meta=exc.meta, error=str(exc))
        logger.error("AI generate failed: %s", exc, extra={"request": request})
        return JsonResponse({"error": "AI hozir javob bermadi, bir daqiqadan so'ng qayta urinib ko'ring."}, status=502)

    cv = CV.objects.create(
        raw_input_text=text,
        target_job=target_job,
        cv_json=result,
        selected_template=template_code,
        user=request.user if request.user.is_authenticated else None,
    )
    photo_file = request.FILES.get("photo")
    if photo_file and _is_valid_image(photo_file):
        cv.photo = photo_file
        cv.save(update_fields=["photo", "updated_at"])

    quotas.record(request, AIUsage.KIND_GENERATE, cv=cv, meta=meta)
    log_activity(request, "cv_create", cv=str(cv.public_id), name=result.get("full_name", ""))
    if not request.user.is_authenticated:
        owned_ids = request.session.get("owned_cv_ids", [])
        owned_ids.append(cv.id)
        request.session["owned_cv_ids"] = owned_ids

    return JsonResponse({"success": True, "redirect_url": reverse("cv_preview", args=[cv.public_id])})


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _active_plans(scope):
    return PricingPlan.objects.filter(is_active=True, scope=scope).order_by("sort_order", "price")


def _credits(user):
    if not getattr(user, "is_authenticated", False):
        return 0
    return getattr(getattr(user, "profile", None), "credits", 0)


def _private_cv(request, cv_id, staff_ok=True):
    cv = get_object_or_404(CV.objects.select_related("parent", "user"), public_id=cv_id)
    if _can_access_private_cv(request, cv) or (staff_ok and request.user.is_staff):
        return cv
    raise Http404("CV topilmadi.")


def _downloadable_cv(request, cv_id):
    cv = _private_cv(request, cv_id)
    if not request.user.is_authenticated:
        messages.info(request, "Yuklab olish uchun Telegram orqali kiring — atigi 2 bosqich.")
        return redirect(f"{reverse('user_login')}?next={quote(reverse('cv_preview', args=[cv.public_id]))}")
    return cv


def _filename(cv, ext):
    name = cv.cv_json.get("full_name", "") if isinstance(cv.cv_json, dict) else ""
    name = re.sub(r"[^\w\-]+", "_", name, flags=re.UNICODE).strip("_") or "resume"
    return f"{name}_CV.{ext}"


def _file_response(content, content_type, filename, disposition):
    response = HttpResponse(content, content_type=content_type)
    ascii_name = filename.encode("ascii", "ignore").decode() or f"CV.{filename.rsplit('.', 1)[-1]}"
    response["Content-Disposition"] = f"{disposition}; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"
    response["Content-Length"] = len(content)
    return response


def _is_valid_image(f):
    ext = os.path.splitext(f.name)[1].lower()
    return ext in {".jpg", ".jpeg", ".png", ".webp"} and f.size <= 5 * 1024 * 1024


def _get_company_branding(user):
    if not getattr(user, "is_authenticated", False):
        return None
    return CompanyBranding.objects.filter(user=user, is_active=True).first()


def _is_owner(user, cv):
    return bool(getattr(user, "is_authenticated", False) and cv.user_id and user.id == cv.user_id)


def _can_access_private_cv(request, cv):
    if _is_owner(request.user, cv):
        return True
    if cv.user_id:
        return False
    return cv.id in request.session.get("owned_cv_ids", [])


def _build_share_url(request, cv):
    if not cv.share_token:
        return ""
    return request.build_absolute_uri(reverse("shared_cv_preview", args=[cv.share_token]))
