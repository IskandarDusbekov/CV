"""
Telegram bot — kirish va to'lovlar.

Ishga tushirish:
    python manage.py runbot

Kirish (kodsiz):
  saytdagi tugma → /start <token> → "📱 Raqamni yuborish" → sayt avtomatik kiradi.
  Botning o'zidan: «🌐 Saytni ochish» (Telegram Mini App) → initData imzosi bilan darhol kiradi,
  hech qanday eskiradigan havola yo'q.

To'lov (qo'lda, Click/Payme ulangungacha):
  /start pay_<kod> yoki "💳 Kredit sotib olish" → paket tanlanadi → karta rekvizitlari →
  foydalanuvchi chek (rasm/fayl) yuboradi → adminlarga yuboriladi → admin saytda yoki shu yerda
  tasdiqlaydi/rad etadi → foydalanuvchiga xabar boradi, kredit yoki Pro avtomatik qo'shiladi.

Do'st taklifi:
  "🎁 Do'st taklif qilish" yoki /taklif → t.me/<bot>?start=ref_<kod> havolasi. Do'st shu havola bilan kelib
  raqamini yuborsa, taklif qilganga kredit beriladi (qoidalar: apps/users/growth.py).

Karta raqami, egasi, admin chat ID lari va boshqalar admin paneldagi "Sayt sozlamalari" dan olinadi.
"""
import logging
import time
from datetime import timedelta
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.core.files.base import ContentFile
from django.urls import reverse
from django.utils import timezone

from apps.core.models import SiteSettings

from .models import PaymentRequest, PricingPlan, TelegramLoginToken, UserProfile
from .telegram_auth import confirm_token, get_active_token, get_or_create_user

logger = logging.getLogger("telegram_bot")

BOT_TOKEN: str = getattr(settings, "TELEGRAM_BOT_TOKEN", "")
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

BTN_BUY = "💳 Kredit sotib olish"
BTN_BALANCE = "📊 Balansim"
BTN_SITE = "🌐 Saytni ochish"
BTN_INVITE = "🎁 Do'st taklif qilish"
LEGACY_BTN_SITE = "🌐 Saytga o'tish"


# ─── Telegram API helpers ─────────────────────────────────────────────────────

def _post(method: str, **kwargs) -> dict:
    if not BOT_TOKEN:
        return {}
    try:
        r = requests.post(f"{BASE_URL}/{method}", json=kwargs, timeout=15)
        data = r.json()
        if not data.get("ok"):
            logger.warning("Telegram %s failed: %s", method, data.get("description"))
        return data
    except Exception as exc:
        logger.error("Telegram %s error: %s", method, exc)
        return {}


def send_message(chat_id: int, text: str, reply_markup: dict | None = None) -> dict:
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return _post("sendMessage", **payload)


def send_document(chat_id: int, content: bytes, filename: str, caption: str = "") -> bool:
    """Faylni chatga yuboradi (Mini App ichida yuklab bo'lmaganda ishlatiladi)."""
    if not BOT_TOKEN:
        return False
    try:
        r = requests.post(
            f"{BASE_URL}/sendDocument",
            data={"chat_id": chat_id, "caption": caption[:1000]},
            files={"document": (filename, content)},
            timeout=60,
        )
        ok = bool(r.json().get("ok"))
        if not ok:
            logger.warning("Telegram sendDocument failed: %s", r.text[:300])
        return ok
    except Exception as exc:
        logger.error("Telegram sendDocument error: %s", exc)
        return False


def _site_url(path: str = "") -> str:
    return getattr(settings, "SITE_URL", "").rstrip("/") + path


def _url_ok(url: str) -> bool:
    # Telegram inline tugmalarida localhost havolalarini qabul qilmaydi
    return url.startswith("https://") or (url.startswith("http://") and "localhost" not in url and "127.0.0.1" not in url)


def _site_button(text: str, path: str = "/users/dashboard/") -> dict | None:
    """Saytni Telegram Mini App sifatida ochadigan tugma — foydalanuvchi avtomatik kiradi.

    Mini App faqat https bilan ishlaydi; lokal muhitda oddiy havola qaytaramiz.
    """
    url = _site_url(reverse("telegram_webapp")) + "?" + urlencode({"next": path})
    if url.startswith("https://"):
        return {"text": text, "web_app": {"url": url}}
    plain = _site_url(path)
    return {"text": text, "url": plain} if _url_ok(plain) else None


def _site_markup(text: str = "🌐 Saytni ochish", path: str = "/users/dashboard/") -> dict | None:
    button = _site_button(text, path)
    return {"inline_keyboard": [[button]]} if button else None


def _money(value) -> str:
    return f"{int(value):,}".replace(",", " ")


def _contact_keyboard() -> dict:
    return {"keyboard": [[{"text": "📱 Raqamni yuborish", "request_contact": True}]], "resize_keyboard": True, "one_time_keyboard": True}


def _main_keyboard() -> dict:
    rows = [[{"text": BTN_BUY}], [{"text": BTN_BALANCE}, {"text": BTN_SITE}]]
    if SiteSettings.load().referral_enabled:
        rows.append([{"text": BTN_INVITE}])
    return {"keyboard": rows, "resize_keyboard": True}


def _profile(telegram_id):
    return UserProfile.objects.select_related("user").filter(telegram_id=telegram_id).first()


# ─── Kirish ───────────────────────────────────────────────────────────────────

def _handle_start(chat_id: int, sender: dict, payload: str) -> None:
    user_id = sender["id"]
    if payload.startswith("pay"):
        code = payload[4:] if payload.startswith("pay_") else ""
        _show_packages(chat_id, user_id, highlight=code)
        return

    if payload.startswith("ref_"):
        # Do'st taklifi: raqam yuborilib akkaunt yaratilganda bonus beriladi
        from .growth import valid_code
        from .models import PendingReferral

        code = payload[4:]
        if valid_code(code) and not _profile(user_id):
            PendingReferral.objects.update_or_create(telegram_id=user_id, defaults={"code": code})
        payload = ""

    token = get_active_token(payload) if payload else None
    if token:
        token.telegram_id = user_id
        token.save(update_fields=["telegram_id"])

    profile = _profile(user_id)
    if profile and not token:
        # Akkaunt allaqachon bog'langan — raqam so'ramaymiz, saytni ochamiz
        send_message(chat_id, "👋 <b>Qaytganingizdan xursandmiz!</b>\nSaytni ochish uchun pastdagi tugmani bosing.",
                     reply_markup=_main_keyboard())
        markup = _site_markup()
        if markup:
            send_message(chat_id, "👇", reply_markup=markup)
        return

    send_message(
        chat_id,
        f"👋 <b>{SiteSettings.load().site_name} ga xush kelibsiz!</b>\n\n"
        "Kirish uchun pastdagi <b>📱 Raqamni yuborish</b> tugmasini bosing.\n"
        "Kod kiritish shart emas — raqamingiz tasdiqlanishi bilan saytga kirasiz.\n\n"
        "<i>Agar kirishni siz boshlamagan bo'lsangiz, raqam yubormang.</i>",
        reply_markup=_contact_keyboard(),
    )


def _handle_contact(chat_id: int, sender: dict, contact: dict) -> None:
    user_id = sender.get("id")
    if contact.get("user_id") != user_id:
        send_message(chat_id, "⚠️ Faqat <b>o'zingizning</b> raqamingizni yuboring — pastdagi tugmadan foydalaning.",
                     reply_markup=_contact_keyboard())
        return

    names = dict(
        phone=contact.get("phone_number", ""),
        first_name=contact.get("first_name") or sender.get("first_name", ""),
        last_name=contact.get("last_name") or sender.get("last_name", ""),
        username=sender.get("username", ""),
    )
    user = get_or_create_user(telegram_id=user_id, **names)
    if user.profile.is_blocked:
        send_message(chat_id, "⛔ Hisobingiz bloklangan. Savollar bo'lsa, yordam xizmatiga yozing.")
        return

    # Saytdagi kirish sahifasi kutib turgan bo'lsa — o'sha brauzer avtomatik kiradi
    token = (
        TelegramLoginToken.objects.filter(telegram_id=user_id, status=TelegramLoginToken.STATUS_PENDING, expires_at__gt=timezone.now())
        .exclude(session_key="").order_by("-created_at").first()
    )
    if token:
        confirm_token(token, telegram_id=user_id, **names)

    from .growth import on_bot_user

    text = "✅ <b>Raqamingiz tasdiqlandi!</b>"
    for note in on_bot_user(user, user_id):
        text += f"\n{note}"
    if token:
        text += "\nSaytdagi sahifa o'zi ochiladi. Telegram ichida ochish uchun pastdagi tugmani bosing."
    send_message(chat_id, text, reply_markup=_main_keyboard())
    markup = _site_markup("🔓 Saytni ochish")
    if markup:
        send_message(chat_id, "Saytga kirish tugmasi har doim ishlaydi — muddati tugamaydi 👇", reply_markup=markup)


# ─── To'lov ───────────────────────────────────────────────────────────────────

def _show_packages(chat_id: int, telegram_id: int, highlight: str = "") -> None:
    profile = _profile(telegram_id)
    if not profile:
        send_message(chat_id, "To'lov qilish uchun avval hisobingizni bog'laymiz.\nPastdagi <b>📱 Raqamni yuborish</b> tugmasini bosing — so'ng paketni tanlaysiz.",
                     reply_markup=_contact_keyboard())
        return
    if profile.is_blocked:
        send_message(chat_id, "⛔ Hisobingiz bloklangan.")
        return

    site = SiteSettings.load()
    plans = list(PricingPlan.objects.filter(is_active=True, price__gt=0).order_by("sort_order", "price"))
    if not plans:
        send_message(chat_id, "Hozircha sotuvda paketlar yo'q.")
        return

    lines = ["💳 <b>Paketni tanlang</b>\n"]
    buttons = []
    for plan in plans:
        star = "⭐ " if plan.code == highlight or plan.is_featured else ""
        if plan.is_credit_pack:
            per = f" (1 rezyume = {_money(plan.price_per_credit)} so'm)" if plan.credits > 1 else ""
            lines.append(f"{star}<b>{plan.name}</b> — {_money(plan.price)} so'm{per}")
        else:
            lines.append(f"{star}<b>{plan.name}</b> — {_money(plan.price)} so'm / {plan.duration_days} kun "
                         f"({plan.max_cvs} ta rezyume, {plan.max_tailorings} ta moslashtirish)")
        buttons.append([{"text": f"{star}{plan.name} — {_money(plan.price)} so'm", "callback_data": f"buy:{plan.id}"}])

    lines.append(f"\nBalansingiz: <b>{profile.credits}</b> kredit")
    if site.payment_notice:
        lines.append(f"\n<i>{site.payment_notice}</i>")
    send_message(chat_id, "\n".join(lines), reply_markup={"inline_keyboard": buttons})


def _start_purchase(chat_id: int, telegram_id: int, plan_id: str) -> None:
    profile = _profile(telegram_id)
    plan = PricingPlan.objects.filter(pk=plan_id, is_active=True).first()
    if not profile or not plan:
        _show_packages(chat_id, telegram_id)
        return

    PaymentRequest.objects.filter(user=profile.user, status=PaymentRequest.STATUS_AWAITING).update(status=PaymentRequest.STATUS_CANCELLED)
    req = PaymentRequest.objects.create(user=profile.user, plan=plan, amount=plan.price, telegram_chat_id=chat_id)

    site = SiteSettings.load()
    what = f"{plan.credits} ta kredit (rezyume ochish)" if plan.is_credit_pack else f"Pro — {plan.duration_days} kun"
    send_message(
        chat_id,
        f"🧾 <b>Buyurtma #{req.pk}</b>: {plan.name}\n"
        f"Siz olasiz: {what}\n\n"
        f"💰 To'lov summasi: <b>{_money(plan.price)} so'm</b>\n\n"
        f"💳 Karta: <code>{site.card_number}</code>\n"
        f"👤 Egasi: <b>{site.card_holder}</b>"
        + (f"\n🏦 {site.card_bank}" if site.card_bank else "")
        + f"\n\n📸 {site.payment_instructions}",
        reply_markup={"inline_keyboard": [[{"text": "❌ Bekor qilish", "callback_data": f"cancel:{req.pk}"}]]},
    )


def _download_file(file_id: str):
    info = _post("getFile", file_id=file_id).get("result") or {}
    path = info.get("file_path")
    if not path:
        return None, None
    r = requests.get(f"https://api.telegram.org/file/bot{BOT_TOKEN}/{path}", timeout=30)
    r.raise_for_status()
    return r.content, path.rsplit("/", 1)[-1]


def _handle_receipt(chat_id: int, sender: dict, message: dict) -> None:
    profile = _profile(sender["id"])
    req = None
    if profile:
        req = (
            PaymentRequest.objects.filter(user=profile.user, status=PaymentRequest.STATUS_AWAITING,
                                          created_at__gte=timezone.now() - timedelta(days=2))
            .select_related("plan").order_by("-created_at").first()
        )
    if not req:
        send_message(chat_id, "Chekni qabul qilish uchun avval paketni tanlang 👇")
        _show_packages(chat_id, sender["id"])
        return

    if message.get("photo"):
        file_id, kind = message["photo"][-1]["file_id"], "photo"
    else:
        doc = message["document"]
        if (doc.get("file_size") or 0) > 10 * 1024 * 1024:
            send_message(chat_id, "Fayl juda katta (10 MB gacha). Skrinshot yuboring.")
            return
        file_id, kind = doc["file_id"], "document"

    try:
        content, name = _download_file(file_id)
    except Exception as exc:
        logger.error("Receipt download failed: %s", exc)
        content, name = None, None
    if content:
        req.receipt.save(f"req{req.pk}_{name}", ContentFile(content), save=False)
    req.receipt_caption = (message.get("caption") or "")[:500]
    req.status = PaymentRequest.STATUS_PENDING
    req.receipt_at = timezone.now()
    req.save()

    send_message(chat_id, f"✅ Chek qabul qilindi (buyurtma #{req.pk}).\nTekshirib chiqamiz va natijani shu yerga yozamiz.",
                 reply_markup=_main_keyboard())
    _notify_admins_new_receipt(req, file_id, kind)

    from apps.core.activity import log_activity

    log_activity(None, "payment_request", user=req.user, payment=req.pk, plan=req.plan.name, amount=int(req.amount))


def _notify_admins_new_receipt(req: PaymentRequest, file_id: str, kind: str) -> None:
    site = SiteSettings.load()
    profile = req.user.profile
    caption = (
        f"🧾 <b>Yangi chek #{req.pk}</b>\n"
        f"👤 {req.user.get_full_name() or req.user.username} · {profile.phone}"
        + (f" · @{profile.telegram_username}" if profile.telegram_username else "")
        + f"\n📦 {req.plan.name} — <b>{_money(req.amount)} so'm</b>"
        + (f"\n💬 {req.receipt_caption}" if req.receipt_caption else "")
    )
    admin_url = _site_url(reverse("admin:users_paymentrequest_change", args=[req.pk]))
    buttons = [[{"text": "✅ Tasdiqlash", "callback_data": f"approve:{req.pk}"},
                {"text": "❌ Rad etish", "callback_data": f"reject:{req.pk}"}]]
    if _url_ok(admin_url):
        buttons.append([{"text": "🔎 Admin panelda ochish", "url": admin_url}])
    method, field = ("sendPhoto", "photo") if kind == "photo" else ("sendDocument", "document")
    for admin_chat in site.admin_chat_id_list:
        _post(method, chat_id=admin_chat, caption=caption, parse_mode="HTML", reply_markup={"inline_keyboard": buttons}, **{field: file_id})


def notify_payment_result(req: PaymentRequest) -> None:
    """Admin tasdiqlagan/rad etgan to'lov haqida foydalanuvchiga xabar (saytdan ham chaqiriladi)."""
    chat_id = req.telegram_chat_id or getattr(req.user.profile, "telegram_id", None)
    if not chat_id:
        return
    if req.status == PaymentRequest.STATUS_APPROVED:
        if req.plan.is_credit_pack:
            text = (f"🎉 <b>To'lov tasdiqlandi!</b> (#{req.pk})\n"
                    f"Hisobingizga <b>{req.plan.credits} kredit</b> qo'shildi. Balans: <b>{req.user.profile.credits}</b>.\n\n"
                    "Saytda rezyume sahifasida «Kredit bilan ochish» tugmasini bosing.")
        else:
            until = req.user.profile.premium_until
            text = (f"🎉 <b>Pro faollashtirildi!</b> (#{req.pk})\n"
                    + (f"Amal qiladi: <b>{until:%d.%m.%Y}</b> gacha." if until else ""))
        send_message(chat_id, text, reply_markup=_site_markup())
    elif req.status == PaymentRequest.STATUS_REJECTED:
        send_message(chat_id, f"❌ <b>To'lov tasdiqlanmadi</b> (#{req.pk})\n"
                              f"Sabab: {req.admin_note or 'chek ma`lumotlari mos kelmadi'}\n\n"
                              "Xato deb o'ylasangiz, yordam xizmatiga yozing.")


def _handle_callback(callback: dict) -> None:
    data = callback.get("data") or ""
    sender = callback.get("from") or {}
    chat_id = (callback.get("message") or {}).get("chat", {}).get("id") or sender.get("id")
    _post("answerCallbackQuery", callback_query_id=callback.get("id"))
    action, _, value = data.partition(":")

    if action == "buy":
        _start_purchase(chat_id, sender["id"], value)
    elif action == "cancel":
        profile = _profile(sender["id"])
        if profile:
            PaymentRequest.objects.filter(pk=value, user=profile.user, status=PaymentRequest.STATUS_AWAITING).update(status=PaymentRequest.STATUS_CANCELLED)
        send_message(chat_id, "Buyurtma bekor qilindi.", reply_markup=_main_keyboard())
    elif action in {"approve", "reject"}:
        _admin_decision(chat_id, sender, action, value)


def _admin_decision(chat_id: int, sender: dict, action: str, req_id: str) -> None:
    site = SiteSettings.load()
    if sender.get("id") not in site.admin_chat_id_list and chat_id not in site.admin_chat_id_list:
        return
    req = PaymentRequest.objects.select_related("plan", "user__profile").filter(pk=req_id).first()
    if not req:
        return
    admin_profile = _profile(sender["id"])
    admin_user = admin_profile.user if admin_profile else None

    from apps.core.activity import log_activity

    if action == "approve":
        if not req.approve(admin_user):
            send_message(chat_id, f"#{req.pk} allaqachon tasdiqlangan.")
            return
        log_activity(None, "payment_approved", user=req.user, payment=req.pk, by=sender.get("username", ""))
        send_message(chat_id, f"✅ #{req.pk} tasdiqlandi: {req.user.get_full_name() or req.user.username} — {req.plan.name}")
    else:
        if not req.reject(admin_user, note="Chek tasdiqlanmadi"):
            send_message(chat_id, f"#{req.pk} tasdiqlangan — rad etib bo'lmaydi.")
            return
        log_activity(None, "payment_rejected", user=req.user, payment=req.pk, by=sender.get("username", ""))
        send_message(chat_id, f"❌ #{req.pk} rad etildi. Sababni admin panelda o'zgartirishingiz mumkin.")
    notify_payment_result(req)


def _show_balance(chat_id: int, telegram_id: int) -> None:
    profile = _profile(telegram_id)
    if not profile:
        send_message(chat_id, "Hisob bog'lanmagan. <b>📱 Raqamni yuborish</b> tugmasini bosing.", reply_markup=_contact_keyboard())
        return
    lines = [f"📊 <b>Balans</b>\nKreditlar: <b>{profile.credits}</b>"]
    if profile.has_active_premium and profile.premium_until:
        lines.append(f"Pro: <b>{profile.premium_until:%d.%m.%Y}</b> gacha")
    pending = PaymentRequest.objects.filter(user=profile.user, status=PaymentRequest.STATUS_PENDING).count()
    if pending:
        lines.append(f"Tekshirilayotgan to'lovlar: {pending}")
    send_message(chat_id, "\n".join(lines), reply_markup=_main_keyboard())


def _show_invite(chat_id: int, telegram_id: int) -> None:
    profile = _profile(telegram_id)
    if not profile:
        send_message(chat_id, "Avval hisobingizni bog'laymiz. <b>📱 Raqamni yuborish</b> tugmasini bosing.", reply_markup=_contact_keyboard())
        return
    site = SiteSettings.load()
    if not site.referral_enabled:
        send_message(chat_id, "Do'st taklif qilish hozircha o'chirilgan.", reply_markup=_main_keyboard())
        return

    from django.db.models import Sum

    from .growth import bot_referral_link
    from .models import Referral

    link = bot_referral_link(profile.user)
    if not link:
        send_message(chat_id, "Taklif havolasi hozircha mavjud emas.", reply_markup=_main_keyboard())
        return
    made = Referral.objects.filter(inviter=profile.user)
    earned = made.aggregate(s=Sum("inviter_credits"))["s"] or 0
    text = (
        "🎁 <b>Do'stlaringizni taklif qiling</b>\n\n"
        f"Havolangiz orqali kelgan har bir do'stingiz raqamini yuborib ro'yxatdan o'tsa — sizga <b>+{site.referral_inviter_credits} kredit</b>"
        " (1 kredit = 1 rezyume to'liq ochiladi).\n\n"
        f"🔗 Havolangiz:\n{link}\n\n"
        f"Taklif qilganlar: <b>{made.count()}</b> · olingan kredit: <b>{earned}</b>"
    )
    share = "https://t.me/share/url?" + urlencode({
        "url": link,
        "text": "Rezyumeni 2 daqiqada tayyorladim — tayyor namunalar va birinchi PDF bepul. Senga ham foydali bo'ladi 👇",
    })
    send_message(chat_id, text, reply_markup={"inline_keyboard": [[{"text": "✈️ Do'stlarga yuborish", "url": share}]]})


# ─── Router ───────────────────────────────────────────────────────────────────

def _handle_update(update: dict) -> None:
    if update.get("callback_query"):
        _handle_callback(update["callback_query"])
        return

    message = update.get("message") or {}
    chat_id = message.get("chat", {}).get("id")
    sender = message.get("from") or {}
    if not chat_id or not sender.get("id"):
        return

    profile = _profile(sender["id"])
    if profile and profile.is_blocked:
        send_message(chat_id, "⛔ Hisobingiz bloklangan.")
        return

    if message.get("contact"):
        _handle_contact(chat_id, sender, message["contact"])
        return
    if message.get("photo") or message.get("document"):
        _handle_receipt(chat_id, sender, message)
        return

    text = (message.get("text") or "").strip()
    if text.startswith("/start"):
        parts = text.split(maxsplit=1)
        _handle_start(chat_id, sender, parts[1].strip() if len(parts) > 1 else "")
    elif text in {BTN_BUY, "/tolov", "/buy"}:
        _show_packages(chat_id, sender["id"])
    elif text in {BTN_BALANCE, "/balans"}:
        _show_balance(chat_id, sender["id"])
    elif text in {BTN_INVITE, "/taklif"}:
        _show_invite(chat_id, sender["id"])
    elif text in {BTN_SITE, LEGACY_BTN_SITE, "/sayt"}:
        markup = _site_markup(f"🌐 {SiteSettings.load().site_name}")
        send_message(chat_id, "Saytni ochish 👇" if markup else _site_url("/"), reply_markup=markup)
    elif profile:
        send_message(chat_id, "Quyidagi tugmalardan birini tanlang 👇", reply_markup=_main_keyboard())
    else:
        send_message(chat_id, "Kirish uchun pastdagi <b>📱 Raqamni yuborish</b> tugmasini bosing.", reply_markup=_contact_keyboard())


# ─── Polling loop ─────────────────────────────────────────────────────────────

def run_polling() -> None:
    if not BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN sozlanmagan! .env faylini tekshiring.")
        return

    _post("deleteWebhook")
    _post("setMyCommands", commands=[
        {"command": "start", "description": "Boshlash / kirish"},
        {"command": "tolov", "description": "Kredit yoki Pro sotib olish"},
        {"command": "balans", "description": "Balansim"},
        {"command": "taklif", "description": "Do'st taklif qilish — bonus kredit"},
        {"command": "sayt", "description": "Saytni ochish"},
    ])
    menu = _site_button("Sayt")
    if menu and "web_app" in menu:
        # Chat pastidagi «Sayt» tugmasi — Mini App, har doim kirgan holda ochiladi
        _post("setChatMenuButton", menu_button={"type": "web_app", "text": "Sayt", "web_app": menu["web_app"]})
    logger.info("Telegram bot ishga tushdi (long polling)...")
    offset = 0

    while True:
        try:
            r = requests.get(
                f"{BASE_URL}/getUpdates",
                params={"offset": offset, "timeout": 30, "allowed_updates": '["message","callback_query"]'},
                timeout=40,
            )
            data = r.json()
            if not data.get("ok"):
                logger.warning("getUpdates failed: %s", data)
                time.sleep(5)
                continue

            for update in data.get("result", []):
                offset = update["update_id"] + 1
                try:
                    _handle_update(update)
                except Exception:
                    logger.exception("Update handling error")

        except requests.exceptions.Timeout:
            continue
        except KeyboardInterrupt:
            logger.info("Bot to'xtatildi.")
            break
        except Exception as exc:
            logger.error("Polling error: %s", exc)
            time.sleep(5)
