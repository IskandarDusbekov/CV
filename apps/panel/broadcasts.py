"""Panel → «Xabar yuborish»: bot orqali tanlangan yoki barcha foydalanuvchilarga xabar (faqat bosh admin)."""
import json
import re

from django.contrib import messages
from django.db.models import Count, F, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.views.decorators.http import require_POST

from apps.users import broadcast as engine
from apps.users.models import Broadcast, BroadcastRecipient, UserProfile

from .forms import BroadcastForm
from .views import _page, superuser_required

PRESETS = [
    {
        "key": "gift_cv",
        "label": "Rezyume sovg'a",
        "title": "Yuklamaganlarga rezyume sovg'a",
        "audience": Broadcast.AUDIENCE_NOT_DOWNLOADED,
        "attach_cv": True, "bonus_credits": 0, "button_site": True, "button_share": True,
        "text": "🎁 <b>{ism}, sizga sovg'a!</b>\n\nSaytimizda yaratgan rezyumengizni tayyor PDF qilib yubordik — <b>bepul</b>. "
                "Uni ish beruvchiga shu holicha yuborishingiz mumkin.\n\nRezyume foydali bo'ldimi?",
        "feedback_options": "👍 Foydali bo'ldi\n👎 Kerak emas",
    },
    {
        "key": "gift_credit",
        "label": "Kredit sovg'a",
        "title": "1 kredit sovg'a",
        "audience": Broadcast.AUDIENCE_ALL,
        "attach_cv": False, "bonus_credits": 1, "button_site": True, "button_share": True,
        "text": "🎁 <b>{ism}, hisobingizga {kredit} kredit qo'shildi!</b>\n\n1 kredit = 1 rezyume to'liq ochiladi: PDF + Word, "
                "barcha shablonlar, belgisiz. Hoziroq foydalaning 👇\n\nDo'stingizga ulashsangiz — u ro'yxatdan o'tganda sizga yana kredit beriladi.",
        "feedback_options": "",
    },
    {
        "key": "survey",
        "label": "So'rovnoma",
        "title": "So'rovnoma",
        "audience": Broadcast.AUDIENCE_ALL,
        "attach_cv": False, "bonus_credits": 0, "button_site": False, "button_share": False,
        "text": "{ism}, qisqa savol 🙌\n\n<b>Rezyumeni nima uchun yaratdingiz?</b>\nJavobingiz saytni yaxshilashga yordam beradi.",
        "feedback_options": "💼 Ish qidiryapman\n🎓 O'qish / amaliyot uchun\n👀 Shunchaki sinab ko'rdim",
    },
]


def _with_stats(qs):
    return qs.annotate(
        n=Count("recipients", distinct=True),
        n_sent=Count("recipients", filter=Q(recipients__status=BroadcastRecipient.STATUS_SENT), distinct=True),
        n_answers=Count("recipients", filter=~Q(recipients__response=""), distinct=True),
    )


@superuser_required
def broadcasts(request, pk=None):
    instance = get_object_or_404(Broadcast, pk=pk) if pk else None
    if instance and instance.status != Broadcast.STATUS_DRAFT:
        messages.warning(request, "Yuborilgan xabarni o'zgartirib bo'lmaydi — «Nusxa olish» bilan yangisini yarating.")
        return redirect("panel:broadcast_detail", pk=instance.pk)

    initial = {}
    if instance is None and request.GET.get("to"):
        initial = {"audience": Broadcast.AUDIENCE_SELECTED, "selected_users": request.GET["to"], "title": "Shaxsiy xabar"}
    form = BroadcastForm(instance=instance, initial=initial)
    if request.method == "POST":
        form = BroadcastForm(request.POST, instance=instance)
        if form.is_valid():
            obj = form.save(commit=False)
            if obj.created_by_id is None:
                obj.created_by = request.user
            if obj.audience != Broadcast.AUDIENCE_SELECTED:
                obj.selected_users, obj.selected_cvs = "", {}
            obj.save()
            messages.success(request, "Saqlandi. Endi «Menga sinov» bilan tekshirib, keyin yuboring.")
            return redirect("panel:broadcast_detail", pk=obj.pk)
        messages.error(request, "Formada xatolik bor.")

    return render(request, "panel/broadcasts.html", {
        "form": form,
        "instance": instance,
        "items": _with_stats(Broadcast.objects.all())[:50],
        "presets": PRESETS,
        "picker_initial": _picker_state(form["selected_users"].value(), form["selected_cvs"].value()),
    })


def _picker_state(selected_users, selected_cvs):
    """Formadagi tanlov (ID/telefon ro'yxati + rezyumelar) → tanlagich uchun boshlang'ich ro'yxat."""
    if isinstance(selected_cvs, str):
        try:
            selected_cvs = json.loads(selected_cvs or "{}")
        except ValueError:
            selected_cvs = {}
    if not (selected_users or "").strip():
        return []
    profiles = UserProfile.objects.select_related("user").filter(engine._selected_filter(selected_users)).order_by("pk")[:200]
    people = engine.people_payload(profiles)
    for person in people:
        cv_id = (selected_cvs or {}).get(str(person["id"]))
        match = next((c for c in person["cvs"] if c["id"] == cv_id), None)
        person["cv"] = match["id"] if match else None
        person["cv_label"] = (f"{match['name']} · {match['template']}" if match
                              else ("Avtomatik — eng oxirgisi" if person["cvs"] else "Rezyumesi yo'q"))
    return people


@superuser_required
def broadcast_people(request):
    """Tanlagich qidiruvi: ism, telefon, @username yoki ID bo'yicha — rezyumelari bilan."""
    q = request.GET.get("q", "").strip()
    qs = UserProfile.objects.select_related("user")
    if q:
        term = q.lstrip("@")
        cond = (Q(user__first_name__icontains=term) | Q(user__last_name__icontains=term) | Q(user__username__icontains=term)
                | Q(telegram_username__icontains=term))
        digits = re.sub(r"\D", "", q)
        if digits:
            cond |= Q(phone__contains=digits[-9:])
            if len(digits) <= 9:
                cond |= Q(user_id=int(digits))
        full = q.split()
        if len(full) >= 2:
            cond |= Q(user__first_name__icontains=full[0], user__last_name__icontains=full[-1])
        qs = qs.filter(cond)
    qs = qs.order_by(F("telegram_id").desc(nulls_last=True), "-last_seen", "-created_at")[:20]
    return JsonResponse({"people": engine.people_payload(qs)})


@superuser_required
def broadcast_detail(request, pk):
    obj = get_object_or_404(_with_stats(Broadcast.objects.select_related("created_by")), pk=pk)
    recipients = obj.recipients.select_related("user__profile", "cv")
    status_counts = dict(recipients.order_by().values_list("status").annotate(c=Count("id")))
    answered = dict(recipients.exclude(response="").order_by().values_list("response").annotate(c=Count("id")))
    answers = [{"label": label, "n": answered.pop(label, 0)} for label in obj.options]
    answers += [{"label": label, "n": n} for label, n in answered.items()]  # tugma nomi keyin o'zgargan bo'lsa ham ko'rinsin

    flt = request.GET.get("s", "")
    if flt in dict(BroadcastRecipient.STATUS_CHOICES):
        recipients = recipients.filter(status=flt)
    elif flt == "answered":
        recipients = recipients.exclude(response="")

    preview_markup = engine.build_markup(obj, request.user, "t") or {"inline_keyboard": []}
    return render(request, "panel/broadcast_detail.html", {
        "b": obj,
        "status_counts": status_counts,
        "answers": answers,
        "answers_total": sum(a["n"] for a in answers),
        "audience_count": engine.audience_profiles(obj).count() if obj.status == Broadcast.STATUS_DRAFT else None,
        "preview_text": mark_safe(engine.render_text(obj, request.user)),
        "preview_buttons": preview_markup["inline_keyboard"],
        "page": _page(request, recipients, 40),
        "s": flt,
        "statuses": BroadcastRecipient.STATUS_CHOICES,
        "pending": status_counts.get(BroadcastRecipient.STATUS_PENDING, 0),
        "selected_people": _picker_state(obj.selected_users, obj.selected_cvs) if obj.audience == Broadcast.AUDIENCE_SELECTED else [],
    })


@superuser_required
@require_POST
def broadcast_action(request, pk):
    obj = get_object_or_404(Broadcast, pk=pk)
    action = request.POST.get("action")

    if action == "test":
        ok, note = engine.send_test(obj, request.user)
        (messages.success if ok else messages.error)(request, note)
    elif action == "start" and obj.status == Broadcast.STATUS_DRAFT:
        count = engine.start(obj)
        if count:
            messages.success(request, f"Yuborish boshlandi: {count} kishi. Bot navbat bilan yuboradi — sahifa o'zi yangilanadi.")
        else:
            Broadcast.objects.filter(pk=obj.pk).update(status=Broadcast.STATUS_DRAFT, started_at=None)
            messages.warning(request, "Bu shartlarga mos, Telegram bog'langan foydalanuvchi topilmadi.")
    elif action == "cancel" and obj.status == Broadcast.STATUS_SENDING:
        Broadcast.objects.filter(pk=obj.pk).update(status=Broadcast.STATUS_CANCELLED, finished_at=timezone.now())
        messages.warning(request, "To'xtatildi. Yuborilganlar qaytarilmaydi.")
    elif action == "copy":
        fields = {f: getattr(obj, f) for f in BroadcastForm.Meta.fields}
        copy = Broadcast.objects.create(**{**fields, "title": f"{obj.title} (nusxa)"}, created_by=request.user)
        messages.success(request, "Nusxa yaratildi — o'zgartirib yuborishingiz mumkin.")
        return redirect("panel:broadcast_edit", pk=copy.pk)
    elif action == "delete" and obj.status != Broadcast.STATUS_SENDING:
        obj.delete()
        messages.success(request, "O'chirildi.")
        return redirect("panel:broadcasts")
    return redirect("panel:broadcast_detail", pk=obj.pk)
