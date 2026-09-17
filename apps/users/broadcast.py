"""
Bot orqali ommaviy xabarlar (panel → «Xabar yuborish»).

Oqim: admin xabarni yozadi → «Menga sinov» bilan o'zida tekshiradi → «Yuborish» bosilganda qabul qiluvchilar
ro'yxati bir marta yoziladi (BroadcastRecipient) → bot jarayonidagi fon oqimi (worker_loop) ularni navbat bilan
yuboradi. Sayt so'rovi kutib qolmaydi, bot qayta ishga tushsa ham yuborish qolgan joyidan davom etadi.

Har bir xabarda: foydalanuvchining o'z rezyumesi PDF (sovg'a), bonus kredit, javob tugmalari
(«👍 Foydali bo'ldi» — kim nimani bosgani panelda ko'rinadi), «Saytni ochish» va «Do'stga ulashish».
"""
import json
import logging
import re
import threading
import time
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.db import close_old_connections
from django.db.models import F, Q
from django.utils import timezone
from django.utils.html import escape

from apps.core.models import ActivityLog, SiteSettings

from .models import Broadcast, BroadcastRecipient, UserProfile

logger = logging.getLogger("telegram_bot")

ALLOWED_TAGS = {"b", "strong", "i", "em", "u", "ins", "s", "strike", "del", "a", "code", "pre", "blockquote", "tg-spoiler"}
SEND_PAUSE = 0.05  # Telegram: sekundiga ~30 xabardan oshmaslik
CAPTION_LIMIT = 1000
TEXT_LIMIT = 3500


# ─── Kimga ────────────────────────────────────────────────────────────────────

def _selected_filter(raw):
    cond = Q(pk__in=[])
    # Faqat qator, vergul va nuqtali vergul ajratadi: «90 123 45 67» — bitta telefon
    for token in re.split(r"[\r\n,;]+", raw or ""):
        token = token.strip()
        if not token:
            continue
        if token.startswith("@"):
            cond |= Q(telegram_username__iexact=token[1:])
            continue
        digits = re.sub(r"\D", "", token)
        if not digits:
            cond |= Q(telegram_username__iexact=token)
        elif len(digits) > 15:
            continue
        elif len(digits) >= 9:
            # Telefon (oxirgi 9 raqami bo'yicha — +998 yozilgan-yozilmaganidan qat'i nazar) yoki Telegram ID
            cond |= Q(phone__endswith=digits[-9:]) | Q(telegram_id=int(digits))
        else:
            cond |= Q(user_id=int(digits))
    return cond


def audience_profiles(broadcast):
    """Xabar yetib borishi mumkin bo'lgan profillar: Telegram bog'langan, bloklanmagan, faol."""
    qs = UserProfile.objects.filter(telegram_id__isnull=False, is_blocked=False, user__is_active=True).select_related("user")
    if broadcast.audience == Broadcast.AUDIENCE_NOT_DOWNLOADED:
        downloaded = ActivityLog.objects.filter(action__in=["download_pdf", "download_docx"], user__isnull=False).values("user")
        qs = qs.filter(user__cv__isnull=False).exclude(user__in=downloaded)
    elif broadcast.audience == Broadcast.AUDIENCE_NO_CV:
        qs = qs.filter(user__cv__isnull=True)
    elif broadcast.audience == Broadcast.AUDIENCE_SELECTED:
        qs = qs.filter(_selected_filter(broadcast.selected_users))
    if broadcast.attach_cv:
        qs = qs.filter(user__cv__isnull=False)
    return qs.distinct().order_by("pk")


def people_payload(profiles, cvs_per_user=12):
    """Panel tanlagichi uchun: foydalanuvchilar va ularning rezyumelari (JSON)."""
    from apps.cv.models import CV
    from apps.cv.services import TEMPLATE_META, resolve_template_name

    profiles = list(profiles)
    by_user = {}
    cvs = CV.objects.filter(user__in=[p.user_id for p in profiles]).order_by(F("parent_id").asc(nulls_first=True), "-updated_at")
    for cv in cvs.only("id", "public_id", "user_id", "cv_json", "selected_template", "parent_id", "is_unlocked", "created_at", "tailor_report"):
        items = by_user.setdefault(cv.user_id, [])
        if len(items) >= cvs_per_user:
            continue
        data = cv.cv_json if isinstance(cv.cv_json, dict) else {}
        items.append({
            "id": cv.pk,
            "url": f"/cv/preview/{cv.public_id}/",
            "name": (data.get("full_name") or "Nomsiz")[:60],
            "title": (data.get("job_title") or "")[:60],
            "template": TEMPLATE_META[resolve_template_name(cv.selected_template)]["label"],
            "date": timezone.localtime(cv.created_at).strftime("%d.%m.%Y"),
            "tailored": (cv.tailor_report or {}).get("vacancy_title", "") if cv.parent_id else "",
            "unlocked": cv.is_unlocked,
        })
    return [{
        "id": p.user_id,
        "name": p.user.get_full_name() or p.user.username,
        "phone": p.phone,
        "tg": p.telegram_username,
        "telegram": bool(p.telegram_id),
        "blocked": p.is_blocked,
        "cvs": by_user.get(p.user_id, []),
    } for p in profiles]


def latest_cv(user):
    """Sovg'a uchun rezyume: avval asl (moslashtirilmagan) rezyumelar, eng oxirgi tahrirlangani."""
    from apps.cv.models import CV

    return CV.objects.filter(user=user).order_by(F("parent_id").asc(nulls_first=True), "-updated_at").first()


def chosen_cv(broadcast, user):
    """Panelda shu odam uchun tanlangan rezyume (faqat o'ziniki bo'lsa), aks holda eng oxirgisi."""
    from apps.cv.models import CV

    cv_id = (broadcast.selected_cvs or {}).get(str(user.pk)) if broadcast.audience == Broadcast.AUDIENCE_SELECTED else None
    if cv_id:
        cv = CV.objects.filter(pk=cv_id, user=user).first()
        if cv:
            return cv
    return latest_cv(user)


def start(broadcast):
    """Qabul qiluvchilar ro'yxatini muzlatib, yuborishni boshlaydi. Nechta odamga ketishini qaytaradi."""
    profiles = list(audience_profiles(broadcast))
    rows = [
        BroadcastRecipient(broadcast=broadcast, user=p.user, cv=chosen_cv(broadcast, p.user) if broadcast.attach_cv else None)
        for p in profiles
    ]
    BroadcastRecipient.objects.bulk_create(rows, ignore_conflicts=True, batch_size=500)
    Broadcast.objects.filter(pk=broadcast.pk).update(status=Broadcast.STATUS_SENDING, started_at=timezone.now())
    broadcast.refresh_from_db()
    return len(rows)


# ─── Xabar tarkibi ────────────────────────────────────────────────────────────

def validate_text(text):
    """Telegram qo'llamaydigan HTML teglari — xato matni, aks holda ''."""
    bad = sorted({t.lower() for t in re.findall(r"</?\s*([a-zA-Z][\w-]*)", text or "")} - ALLOWED_TAGS)
    if bad:
        return "Telegram bu teglarni qo'llamaydi: " + ", ".join(f"<{t}>" for t in bad) + ". Faqat <b>, <i>, <u>, <s>, <a>, <code> ishlating."
    return ""


def render_text(broadcast, user):
    name = user.first_name or user.get_full_name() or "do'st"
    return broadcast.text.replace("{ism}", escape(name)).replace("{kredit}", str(broadcast.bonus_credits)).strip()


def build_markup(broadcast, user, recipient_id, chosen=""):
    from .bot import _site_button
    from .growth import bot_referral_link

    rows = []
    options = broadcast.options
    if chosen:
        rows.append([{"text": f"✓ {chosen}", "callback_data": "bf:done"}])
    elif options:
        buttons = [{"text": label, "callback_data": f"bf:{recipient_id}:{i}"} for i, label in enumerate(options)]
        short = all(len(b["text"]) <= 18 for b in buttons)
        step = 2 if short else 1
        rows += [buttons[i:i + step] for i in range(0, len(buttons), step)]
    if broadcast.button_site:
        button = _site_button("🌐 Saytni ochish", "/users/dashboard/")
        if button:
            rows.append([button])
    if broadcast.button_share and SiteSettings.load().referral_enabled:
        link = bot_referral_link(user)
        if link:
            share = "https://t.me/share/url?" + urlencode({
                "url": link, "text": "Rezyumeni 2 daqiqada tayyorladim — tayyor namunalar va birinchi PDF bepul. Senga ham foydali bo'ladi 👇"})
            rows.append([{"text": "🤝 Do'stga ulashish", "url": share}])
    return {"inline_keyboard": rows} if rows else None


def gift_filename(cv):
    data = cv.cv_json if isinstance(cv.cv_json, dict) else {}
    name = re.sub(r"[^\w\-]+", "_", data.get("full_name", ""), flags=re.UNICODE).strip("_") or "Rezyume"
    site = re.sub(r"[^\w.\-]+", "", SiteSettings.load().site_name) or "tezrezyume.uz"
    return f"{name}_Rezyume_{site}.pdf"


# ─── Telegram ─────────────────────────────────────────────────────────────────

def _api(method, payload=None, files=None):
    token = getattr(settings, "TELEGRAM_BOT_TOKEN", "")
    if not token:
        return {"ok": False, "description": "TELEGRAM_BOT_TOKEN sozlanmagan"}
    url = f"https://api.telegram.org/bot{token}/{method}"
    try:
        if files:
            data = {k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v) for k, v in payload.items() if v is not None}
            response = requests.post(url, data=data, files=files, timeout=90)
        else:
            response = requests.post(url, json={k: v for k, v in payload.items() if v is not None}, timeout=20)
        return response.json()
    except Exception as exc:
        return {"ok": False, "description": f"Tarmoq xatosi: {exc}"[:300]}


def deliver(chat_id, text, markup=None, pdf=None, filename=""):
    """Bitta xabarni yuboradi (429 da kutib qayta urinadi). Qaytaradi: Telegram javobi (dict)."""
    for _ in range(3):
        if pdf is not None:
            result = _api("sendDocument", {"chat_id": chat_id, "caption": text[:1024], "parse_mode": "HTML", "reply_markup": markup},
                          files={"document": (filename, pdf, "application/pdf")})
        else:
            result = _api("sendMessage", {"chat_id": chat_id, "text": text, "parse_mode": "HTML",
                                          "disable_web_page_preview": True, "reply_markup": markup})
        retry = (result.get("parameters") or {}).get("retry_after")
        if result.get("error_code") == 429 and retry:
            time.sleep(min(int(retry), 60) + 1)
            continue
        return result
    return result


def _render_pdf(cv):
    from apps.cv.pdf import render_cv_to_pdf

    return render_cv_to_pdf(cv, cv.user, force_watermark=True)


def send_one(recipient):
    broadcast, user = recipient.broadcast, recipient.user
    profile = user.profile
    if not profile.telegram_id or profile.is_blocked:
        return _finish(recipient, BroadcastRecipient.STATUS_FAILED, "Telegram bog'lanmagan yoki bloklangan")

    pdf = filename = None
    if broadcast.attach_cv:
        cv = recipient.cv or latest_cv(user)
        if cv is None:
            return _finish(recipient, BroadcastRecipient.STATUS_FAILED, "Rezyumesi yo'q")
        try:
            pdf, filename = _render_pdf(cv), gift_filename(cv)
        except Exception as exc:
            logger.warning("Broadcast PDF failed for CV %s: %s", cv.pk, exc)
            return _finish(recipient, BroadcastRecipient.STATUS_FAILED, f"PDF yaratilmadi: {exc}")

    result = deliver(profile.telegram_id, render_text(broadcast, user), build_markup(broadcast, user, recipient.pk), pdf, filename)
    if result.get("ok"):
        _finish(recipient, BroadcastRecipient.STATUS_SENT)
        if broadcast.bonus_credits:
            UserProfile.objects.filter(pk=profile.pk).update(credits=F("credits") + broadcast.bonus_credits)
            from apps.core.activity import log_activity

            log_activity(None, "broadcast_bonus", user=user, credits=broadcast.bonus_credits, broadcast=broadcast.pk)
        return recipient
    description = result.get("description") or "Noma'lum xato"
    blocked = result.get("error_code") == 403
    return _finish(recipient, BroadcastRecipient.STATUS_BLOCKED if blocked else BroadcastRecipient.STATUS_FAILED, description)


def _finish(recipient, status, error=""):
    recipient.status = status
    recipient.error = error[:300]
    recipient.sent_at = timezone.now()
    recipient.save(update_fields=["status", "error", "sent_at"])
    return recipient


def send_test(broadcast, admin_user):
    """Xabarni adminning o'ziga yuboradi (kredit berilmaydi, javob yozilmaydi). Qaytaradi: (ok, izoh)."""
    profile = getattr(admin_user, "profile", None)
    if not profile or not profile.telegram_id:
        return False, "Sizning akkauntingiz Telegram bilan bog'lanmagan — botga /start bosib raqamingizni yuboring."
    pdf = filename = None
    note = ""
    if broadcast.attach_cv:
        sample = audience_profiles(broadcast).first()
        cv = chosen_cv(broadcast, sample.user) if sample else latest_cv(admin_user)
        if cv is None:
            return False, "Namuna uchun rezyume topilmadi."
        try:
            pdf, filename = _render_pdf(cv), gift_filename(cv)
        except Exception as exc:
            return False, f"PDF yaratilmadi: {exc}"
        if cv.user_id != admin_user.pk:
            note = f" Fayl namunasi: {cv.user.get_full_name() or cv.user.username} rezyumesi."
    markup = build_markup(broadcast, admin_user, "t")
    result = deliver(profile.telegram_id, render_text(broadcast, admin_user), markup, pdf, filename)
    if result.get("ok"):
        return True, "Sinov xabari Telegram'ingizga yuborildi." + note
    return False, f"Telegram xabarni qabul qilmadi: {result.get('description')}"


# ─── Fon oqimi ────────────────────────────────────────────────────────────────

def process_pending(pause=SEND_PAUSE):
    """Yuborilayotgan barcha xabarlarning navbatdagi qabul qiluvchilariga yuboradi. Nechta yuborilganini qaytaradi."""
    done = 0
    for broadcast in Broadcast.objects.filter(status=Broadcast.STATUS_SENDING).order_by("started_at"):
        queue = BroadcastRecipient.objects.filter(broadcast=broadcast, status=BroadcastRecipient.STATUS_PENDING).select_related(
            "broadcast", "user__profile", "cv__user")
        # Kichik bo'laklar bilan: har bo'lakdan oldin panelda «To'xtatish» bosilmaganini tekshiramiz
        while Broadcast.objects.filter(pk=broadcast.pk, status=Broadcast.STATUS_SENDING).exists():
            batch = list(queue[:20])
            if not batch:
                break
            for recipient in batch:
                try:
                    send_one(recipient)
                except Exception as exc:
                    logger.exception("Broadcast send failed")
                    _finish(recipient, BroadcastRecipient.STATUS_FAILED, str(exc))
                done += 1
                if pause:
                    time.sleep(pause)
        Broadcast.objects.filter(pk=broadcast.pk, status=Broadcast.STATUS_SENDING).exclude(
            recipients__status=BroadcastRecipient.STATUS_PENDING).update(status=Broadcast.STATUS_DONE, finished_at=timezone.now())
    return done


def worker_loop(interval=5):
    while True:
        try:
            process_pending()
        except Exception:
            logger.exception("Broadcast worker error")
        finally:
            close_old_connections()
        time.sleep(interval)


def start_worker():
    thread = threading.Thread(target=worker_loop, name="broadcast-worker", daemon=True)
    thread.start()
    return thread


# ─── Javob tugmalari ──────────────────────────────────────────────────────────

def handle_feedback(callback):
    """«bf:<qabul_qiluvchi>:<tugma>» bosilganda: javobni yozadi, rahmat aytadi, tugmalarni tanlangan javobga almashtiradi."""
    from .bot import _post

    data = callback.get("data") or ""
    sender = callback.get("from") or {}
    message = callback.get("message") or {}
    parts = data.split(":")

    def answer(text):
        _post("answerCallbackQuery", callback_query_id=callback.get("id"), text=text)

    if data == "bf:done":
        return answer("Javobingiz qabul qilingan. Rahmat!")
    if len(parts) != 3 or not parts[2].isdigit():
        return answer("")
    if parts[1] == "t":
        return answer("Sinov xabari: haqiqiy yuborishda javob shu yerda yoziladi.")
    if not parts[1].isdigit():
        return answer("")

    recipient = BroadcastRecipient.objects.select_related("broadcast", "user__profile").filter(pk=int(parts[1])).first()
    if recipient is None or recipient.user.profile.telegram_id != sender.get("id"):
        return answer("")
    options = recipient.broadcast.options
    index = int(parts[2])
    if index >= len(options):
        return answer("")
    if not recipient.response:
        BroadcastRecipient.objects.filter(pk=recipient.pk, response="").update(response=options[index], responded_at=timezone.now())
        recipient.refresh_from_db(fields=["response"])
    answer("Rahmat! Javobingiz qabul qilindi 🙏")
    if message.get("message_id"):
        _post("editMessageReplyMarkup", chat_id=message.get("chat", {}).get("id"), message_id=message["message_id"],
              reply_markup=build_markup(recipient.broadcast, recipient.user, recipient.pk, chosen=recipient.response)
              or {"inline_keyboard": []})
