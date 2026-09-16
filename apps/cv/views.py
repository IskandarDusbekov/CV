import logging
import os
import re
from urllib.parse import quote

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core import signing
from django.db.models import F
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.core.activity import log_activity
from apps.core.analytics import mark_step
from apps.users.models import CompanyBranding, PricingPlan, UserProfile

from . import quotas
from .models import CV, AIUsage, ResumeSample
from .pdf import PdfRenderError, render_cv_to_pdf
from .services import (
    DEFAULT_TEMPLATE,
    TEMPLATE_META,
    AIError,
    PDF_NO_FREE,
    PDF_PRO_TEMPLATE,
    build_cv_context,
    claim_pdf_access,
    demo_template_context,
    pdf_access,
    generate_cv_from_text,
    resolve_template_name,
    tailor_cv_to_job,
    template_choices,
    user_can_download_docx,
    user_can_download_pdf,
    user_can_share_cv,
)

logger = logging.getLogger("apps.cv")
User = get_user_model()


def example(request):
    """'Bepul rezyume yaratish' dan keyin birinchi ko'rinadigan tayyor namuna."""
    templates = [{**t, **demo_template_context(t["code"])} for t in template_choices(DEFAULT_TEMPLATE)]
    return render(request, "cv/example.html", {"templates": templates, "quota": quotas.generate_quota(request)})


def builder(request):
    initial = resolve_template_name(request.GET.get("template", DEFAULT_TEMPLATE))
    profile = getattr(request.user, "profile", None) if request.user.is_authenticated else None
    return render(request, "cv/builder.html", {
        # Telegram orqali kirganlarda ism va raqam allaqachon bor — qayta yozdirmaymiz
        "prefill": {
            "name": request.user.get_full_name() if request.user.is_authenticated else "",
            "phone": getattr(profile, "phone", "") or "",
        },
        "initial_template": initial,
        "samples": ResumeSample.objects.filter(is_published=True)[:12],
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
        "missing_details": _missing_details(request, cv),
        **_referral_context(request),
    })
    return render(request, "cv/preview.html", context)


def _referral_context(request):
    from apps.core.models import SiteSettings
    from apps.users.growth import referral_code_for

    site = SiteSettings.load()
    if not (request.user.is_authenticated and site.referral_enabled):
        return {}
    url = request.build_absolute_uri(f"/r/{referral_code_for(request.user)}/")
    return {
        "referral_url": url,
        "referral_text": "Rezyumeni 2 daqiqada tayyorladim — tayyor namunalar va birinchi PDF bepul. Senga ham foydali bo'ladi 👇",
    }


# AI yozolmaydigan, lekin har kimda bor oddiy ma'lumotlar — yetishmasa preview'da so'raymiz
DETAIL_FIELDS = [
    {"name": "full_name", "label": "Ism va familiya", "type": "text", "placeholder": "Dilnoza Karimova", "autocomplete": "name"},
    {"name": "job_title", "label": "Qaysi lavozimga?", "type": "text", "placeholder": "SMM menejer", "autocomplete": "organization-title"},
    {"name": "phone", "label": "Telefon", "type": "tel", "placeholder": "+998 90 123 45 67", "autocomplete": "tel"},
    {"name": "email", "label": "Email", "type": "email", "placeholder": "ism@gmail.com", "autocomplete": "email"},
    {"name": "location", "label": "Shahar", "type": "text", "placeholder": "Toshkent", "autocomplete": "address-level2"},
]
_DETAILS_SKIPPED_KEY = "details_skipped"


def _missing_details(request, cv):
    if not (_can_access_private_cv(request, cv)) or str(cv.public_id) in request.session.get(_DETAILS_SKIPPED_KEY, []):
        return []
    data = cv.cv_json if isinstance(cv.cv_json, dict) else {}
    profile = getattr(request.user, "profile", None) if request.user.is_authenticated else None
    missing = []
    for field in DETAIL_FIELDS:
        if str(data.get(field["name"]) or "").strip():
            continue
        value = ""
        if field["name"] == "phone" and profile and profile.phone:
            value = profile.phone  # Telegram orqali tasdiqlangan raqam — bitta bosishda saqlanadi
        elif field["name"] == "full_name" and request.user.is_authenticated:
            value = request.user.get_full_name()
        missing.append({**field, "value": value})
    return missing


@require_POST
def save_details(request, cv_id):
    """Preview'dagi «yetishmayotgan ma'lumotlar» formasi: AI'siz, to'g'ridan-to'g'ri rezyumega yoziladi."""
    cv = _private_cv(request, cv_id, staff_ok=False)
    if request.POST.get("action") == "skip":
        skipped = request.session.get(_DETAILS_SKIPPED_KEY, [])
        request.session[_DETAILS_SKIPPED_KEY] = (skipped + [str(cv.public_id)])[-50:]
        return redirect("cv_preview", cv_id=cv.public_id)

    updates = {}
    for field in DETAIL_FIELDS:
        value = re.sub(r"\s+", " ", request.POST.get(field["name"], "")).strip()[:120]
        if value:
            updates[field["name"]] = value
    if updates:
        # Kontaktlar asl rezyume va uning moslashtirilgan versiyalarida bir xil bo'lishi kerak
        root = cv.root
        family = [root, *CV.objects.filter(parent=root)]
        for item in family:
            data = dict(item.cv_json) if isinstance(item.cv_json, dict) else {}
            for key, value in updates.items():
                if key == "job_title" and item.pk != cv.pk and data.get(key):
                    continue  # moslashtirilgan versiyaning lavozim nomini buzmaymiz
                data[key] = value
            item.cv_json = data
            item.save(update_fields=["cv_json", "updated_at"])
        messages.success(request, "Saqlandi — rezyumega qo'shildi.")
    return redirect("cv_preview", cv_id=cv.public_id)


@require_POST
def unlock_with_credit(request, cv_id):
    """1 kredit sarflab rezyumeni (va uning moslashtirilgan versiyalarini) ochish."""
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
    mark_step(request, "unlock")
    messages.success(request, "Rezyume ochildi! Endi PDF va Word yuklab olishingiz mumkin.")
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

    messages.success(request, "Tayyor! Rezyume vakansiyaga moslashtirildi — asl nusxa o'zgarmadi.")
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
    if not claim_pdf_access(request.user, cv):
        messages.warning(request, _pdf_denied_message(request.user, cv))
        return redirect(f"{reverse('cv_preview', args=[cv.public_id])}#download")

    try:
        pdf_file = render_cv_to_pdf(cv, request.user, company_branding=_get_company_branding(request.user))
    except PdfRenderError as exc:
        logger.error("PDF render failed for CV %s: %s", cv.public_id, exc, extra={"request": request})
        detail = f"\n\n{exc}\n\nPlaywright brauzeri o'rnatilmagan bo'lsa: python -m playwright install chromium" if settings.DEBUG else ""
        return HttpResponse(f"PDF yaratishda xatolik yuz berdi. Iltimos, qayta urinib ko'ring.{detail}",
                            status=500, content_type="text/plain; charset=utf-8")

    log_activity(request, "download_pdf", cv=str(cv.public_id), template=cv.selected_template)
    mark_step(request, "download")
    disposition = "inline" if (inline or request.GET.get("inline")) else "attachment"
    return _file_response(pdf_file, "application/pdf", _filename(cv, "pdf"), disposition)


def download_docx(request, cv_id):
    cv = _downloadable_cv(request, cv_id)
    if isinstance(cv, HttpResponse):
        return cv
    if not user_can_download_docx(request.user, cv):
        messages.warning(request, "Word fayl kredit paketi yoki Pro bilan ochiladi. PDF'ni bepul shablonda yuklab olishingiz mumkin.")
        return redirect(f"{reverse('cv_preview', args=[cv.public_id])}#unlock")

    from .docx_export import render_cv_to_docx

    content = render_cv_to_docx(cv, request.user)
    log_activity(request, "download_docx", cv=str(cv.public_id), template=cv.selected_template)
    mark_step(request, "download")
    return _file_response(
        content,
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        _filename(cv, "docx"),
        "attachment",
    )


# ─── Telegram Mini App ichida yuklab olish ────────────────────────────────────
# Telegram ichki brauzeri `Content-Disposition: attachment` faylni saqlay olmaydi. Shuning uchun:
#  1) Telegram.WebApp.downloadFile — cookie'siz ishlaydigan, 10 daqiqalik imzolangan havola bilan;
#  2) eski Telegram versiyalarida — faylni bot orqali chatga yuborish.

_DL_SALT = "cv-download-link"
_DL_MAX_AGE = 10 * 60
_DL_TYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def _pdf_denied_message(user, cv):
    state = pdf_access(user, cv)
    if state == PDF_PRO_TEMPLATE:
        return "Bu Pro shablon. Bepul PDF uchun «Bepul» belgili shablonni tanlang yoki rezyumeni kredit bilan oching."
    if state == PDF_NO_FREE:
        return "Bepul PDF boshqa rezyumengizga ishlatilgan. Bu rezyumeni kredit yoki Pro bilan oching."
    return "Yuklab olish uchun rezyumeni kredit yoki Pro bilan oching."


def _build_file(cv, user, fmt):
    if fmt == "docx":
        from .docx_export import render_cv_to_docx

        return render_cv_to_docx(cv, user)
    return render_cv_to_pdf(cv, user, company_branding=_get_company_branding(user))


def _owned_downloadable(request, cv_id, fmt):
    if fmt not in _DL_TYPES:
        raise Http404
    if not request.user.is_authenticated:
        return None, JsonResponse({"error": "Avval kiring."}, status=401)
    cv = _private_cv(request, cv_id)
    if fmt == "docx":
        if not user_can_download_docx(request.user, cv):
            return None, JsonResponse({"error": "Word fayl kredit paketi yoki Pro bilan ochiladi."}, status=403)
    elif not claim_pdf_access(request.user, cv):
        return None, JsonResponse({"error": _pdf_denied_message(request.user, cv)}, status=403)
    return cv, None


@require_POST
def download_link(request, cv_id, fmt):
    """Mini App uchun: `Telegram.WebApp.downloadFile` ga beriladigan qisqa muddatli havola."""
    cv, error = _owned_downloadable(request, cv_id, fmt)
    if error:
        return error
    token = signing.TimestampSigner(salt=_DL_SALT).sign(f"{cv.public_id}:{fmt}:{request.user.pk}")
    mark_step(request, "download")
    return JsonResponse({
        "url": request.build_absolute_uri(reverse("signed_download", args=[token])),
        "file_name": _filename(cv, fmt),
    })


def signed_download(request, token):
    try:
        value = signing.TimestampSigner(salt=_DL_SALT).unsign(token, max_age=_DL_MAX_AGE)
        public_id, fmt, user_id = value.split(":")
    except (signing.BadSignature, ValueError):
        return HttpResponse("Havola eskirgan. Saytda yuklab olish tugmasini qayta bosing.", status=410,
                            content_type="text/plain; charset=utf-8")
    cv = get_object_or_404(CV.objects.select_related("parent", "user"), public_id=public_id)
    user = get_object_or_404(User.objects.select_related("profile"), pk=user_id, is_active=True)
    profile = getattr(user, "profile", None)
    allowed = (cv.user_id == user.pk or user.is_staff) and not (profile and profile.is_blocked)
    can = user_can_download_docx(user, cv) if fmt == "docx" else user_can_download_pdf(user, cv)
    if fmt not in _DL_TYPES or not allowed or not can:
        raise Http404
    try:
        content = _build_file(cv, user, fmt)
    except PdfRenderError as exc:
        logger.error("PDF render failed for CV %s: %s", cv.public_id, exc, extra={"request": request})
        return HttpResponse("Faylni tayyorlashda xatolik. Qayta urinib ko'ring.", status=500, content_type="text/plain; charset=utf-8")
    log_activity(request, f"download_{fmt}", user=user, cv=str(cv.public_id), via="telegram_app")
    response = _file_response(content, _DL_TYPES[fmt], _filename(cv, fmt), "attachment")
    # web.telegram.org faylni o'z sahifasidan yuklaydi
    response["Access-Control-Allow-Origin"] = "https://web.telegram.org"
    return response


@require_POST
def send_to_telegram(request, cv_id, fmt):
    """Faylni bot orqali foydalanuvchining Telegram chatiga yuboradi."""
    cv, error = _owned_downloadable(request, cv_id, fmt)
    if error:
        return error
    chat_id = getattr(getattr(request.user, "profile", None), "telegram_id", None)
    if not chat_id:
        return JsonResponse({"error": "Hisobingiz Telegram'ga bog'lanmagan. Botga /start yozing."}, status=400)
    try:
        content = _build_file(cv, request.user, fmt)
    except PdfRenderError as exc:
        logger.error("PDF render failed for CV %s: %s", cv.public_id, exc, extra={"request": request})
        return JsonResponse({"error": "Faylni tayyorlashda xatolik. Qayta urinib ko'ring."}, status=500)

    from apps.users.bot import send_document

    if not send_document(chat_id, content, _filename(cv, fmt), caption=f"📄 {cv.cv_json.get('full_name', '')} — rezyume"):
        return JsonResponse({"error": "Telegram'ga yuborib bo'lmadi. Botni bloklamaganingizni tekshiring."}, status=502)
    log_activity(request, f"download_{fmt}", cv=str(cv.public_id), via="telegram_chat")
    mark_step(request, "download")
    return JsonResponse({"ok": True})


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
        raise Http404("Rezyume topilmadi.")
    if not user_can_share_cv(request.user, cv):
        messages.warning(request, "Ommaviy havola rezyume ochilgandan so'ng ishlaydi.")
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
    mark_step(request, "generate")
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
    raise Http404("Rezyume topilmadi.")


def _downloadable_cv(request, cv_id):
    cv = _private_cv(request, cv_id)
    if not request.user.is_authenticated:
        messages.info(request, "Yuklab olish uchun Telegram orqali kiring — atigi 2 bosqich.")
        return redirect(f"{reverse('user_login')}?next={quote(reverse('cv_preview', args=[cv.public_id]))}")
    return cv


def _filename(cv, ext):
    name = cv.cv_json.get("full_name", "") if isinstance(cv.cv_json, dict) else ""
    name = re.sub(r"[^\w\-]+", "_", name, flags=re.UNICODE).strip("_") or "resume"
    return f"{name}_Rezyume.{ext}"


def _file_response(content, content_type, filename, disposition):
    response = HttpResponse(content, content_type=content_type)
    ascii_name = filename.encode("ascii", "ignore").decode() or f"Rezyume.{filename.rsplit('.', 1)[-1]}"
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
