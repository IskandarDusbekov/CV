"""
PDF rendering for mycv.uz CV Builder.

Ekranda ko'rinadigan shablon (cv/partials/cv_template_<code>.html) PDF uchun ham aynan
o'zi ishlatiladi — shuning uchun PDF preview bilan bir xil chiqadi. Shablonlar A4 kengligida
(794px) yozilgan va ko'p sahifali chop etish uchun sozlangan.

Renderer: Playwright (headless Chromium). Fallback: WeasyPrint.

Public API
----------
render_cv_to_pdf(cv, user, base_url="", company_branding=None) -> bytes | None
render_html_to_pdf(html, base_url="")                          -> bytes | None
"""

import base64
import logging
import os

from django.template.loader import render_to_string

from .services import build_cv_context

logger = logging.getLogger(__name__)


def _photo_to_base64(cv) -> str:
    """Rasmni data-URI ga aylantiradi, shunda Chromium uni HTTP so'rovsiz ko'rsatadi."""
    if not cv or not getattr(cv, "photo", None):
        return ""
    try:
        photo_path = cv.photo.path
        if not os.path.exists(photo_path):
            return ""
        ext = os.path.splitext(photo_path)[1].lower().lstrip(".")
        mime = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "webp": "webp"}.get(ext, "jpeg")
        with open(photo_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        return f"data:image/{mime};base64,{b64}"
    except Exception as exc:
        logger.warning("Photo base64 conversion failed: %s", exc)
        return ""


def build_pdf_html(cv, user, company_branding=None) -> str:
    context = build_cv_context(cv, user)
    context["company_branding"] = company_branding if context["is_pro"] else None
    context["pdf_mode"] = True

    photo_b64 = _photo_to_base64(cv)
    if photo_b64:
        context["cv_data"]["photo_url"] = photo_b64

    return render_to_string("cv/pdf_wrapper.html", context)


class PdfRenderError(Exception):
    pass


def render_cv_to_pdf(cv, user, base_url: str = "", company_branding=None) -> bytes:
    """PDF baytlarini qaytaradi yoki sababi yozilgan PdfRenderError ko'taradi."""
    return render_html_to_pdf(build_pdf_html(cv, user, company_branding), base_url=base_url)


def render_html_to_pdf(html: str, base_url: str = "") -> bytes:
    errors = []
    try:
        return _run_in_thread(_render_playwright, html)
    except Exception as exc:
        logger.exception("Playwright PDF render failed")
        errors.append(f"Playwright: {exc!r}")

    pdf = _render_weasyprint(html, base_url=base_url or None)
    if pdf is not None:
        return pdf
    errors.append("WeasyPrint: ishlamadi")
    raise PdfRenderError(" | ".join(errors))


def _run_in_thread(func, *args):
    # Playwright Sync API asyncio loop ishlayotgan thread'da (ASGI, ba'zi IDE runner'lar) ishlamaydi —
    # shuning uchun har doim loop'siz alohida thread'da chaqiramiz.
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(func, *args).result(timeout=90)


def _render_playwright(html: str) -> bytes:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 794, "height": 1123})
            page.emulate_media(media="print")
            # Rasm data-URI, shriftlar absolyut URL — base_url talab qilinmaydi.
            page.set_content(html, wait_until="load", timeout=30000)
            try:
                # Google Fonts sekin yoki internet yo'q bo'lsa kutib qolmaymiz — zaxira shriftlar ishlaydi
                page.wait_for_load_state("networkidle", timeout=8000)
                page.evaluate("document.fonts.ready")
            except Exception:
                logger.warning("Fonts did not finish loading, rendering with fallback fonts")
            page.wait_for_timeout(150)
            return page.pdf(
                format="A4",
                print_background=True,
                prefer_css_page_size=True,
                margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
            )
        finally:
            browser.close()


def _render_weasyprint(html: str, base_url=None) -> bytes | None:
    try:
        import weasyprint
        return weasyprint.HTML(string=html, base_url=base_url or "/").write_pdf()
    except ImportError:
        logger.warning("WeasyPrint is not installed.")
        return None
    except Exception as exc:
        logger.warning("WeasyPrint PDF render failed: %s", exc)
        return None
