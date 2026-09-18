import json
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.core.models import ActivityLog, BlockedIP, ContactMessage, ErrorLog, SiteSettings
from apps.cv.models import CV, AIUsage
from apps.cv.services import DEMO_CV_JSON
from apps.users.models import PaymentRequest, PricingPlan, UserProfile

User = get_user_model()

PAGES = ["dashboard", "payments", "users", "cvs", "ai", "errors", "activity", "messages", "settings"]


class PanelAccessTests(TestCase):
    def test_anonymous_redirected_to_login(self):
        response = self.client.get(reverse("panel:dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith(reverse("user_login") + "?next="))

    def test_regular_user_gets_404(self):
        self.client.force_login(User.objects.create_user(username="u"))
        for name in PAGES:
            self.assertEqual(self.client.get(reverse(f"panel:{name}")).status_code, 404, name)


class StaffPermissionTests(TestCase):
    def setUp(self):
        self.boss = User.objects.create_user(username="boss", is_staff=True, is_superuser=True)
        self.helper = User.objects.create_user(username="helper")

    def test_superuser_grants_panel_access_to_telegram_user(self):
        self.client.force_login(self.boss)
        self.client.post(reverse("panel:user_action", args=[self.helper.pk]), {"action": "make_staff"})
        self.helper.refresh_from_db()
        self.assertTrue(self.helper.is_staff)
        self.assertTrue(ActivityLog.objects.filter(user=self.helper, action="staff_granted").exists())

        self.client.force_login(self.helper)
        self.assertEqual(self.client.get(reverse("panel:payments")).status_code, 200)
        self.assertNotContains(self.client.get(reverse("panel:dashboard")), reverse("panel:settings"))
        self.assertRedirects(self.client.get(reverse("panel:settings")), reverse("panel:dashboard"), fetch_redirect_response=False)
        self.assertContains(self.client.get(reverse("user_dashboard")), "Boshqaruv paneli")

        # Oddiy admin boshqalarga ruxsat bera olmaydi
        other = User.objects.create_user(username="other")
        self.client.post(reverse("panel:user_action", args=[other.pk]), {"action": "make_staff"})
        other.refresh_from_db()
        self.assertFalse(other.is_staff)

    def test_remove_staff(self):
        self.helper.is_staff = True
        self.helper.save()
        self.client.force_login(self.boss)
        self.client.post(reverse("panel:user_action", args=[self.helper.pk]), {"action": "remove_staff"})
        self.helper.refresh_from_db()
        self.assertFalse(self.helper.is_staff)


class PanelTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="boss", is_staff=True, is_superuser=True)
        self.client.force_login(self.admin)
        self.user = User.objects.create_user(username="buyer", first_name="Ali")
        UserProfile.objects.filter(user=self.user).update(phone="+998901112233", last_ip="10.0.0.5")
        self.pack = PricingPlan.objects.get(code="kredit-3")

    def _seed(self):
        cv = CV.objects.create(user=self.user, raw_input_text="x", cv_json=DEMO_CV_JSON)
        CV.objects.create(user=None, raw_input_text="x", cv_json=DEMO_CV_JSON, parent=cv, tailor_report={"vacancy_title": "Dev"})
        PaymentRequest.objects.create(user=self.user, plan=self.pack, amount=self.pack.price, status=PaymentRequest.STATUS_PENDING, receipt_caption="ok")
        AIUsage.objects.create(user=self.user, kind="generate", model="gpt", cost_usd=0.002, prompt_tokens=10, completion_tokens=5)
        AIUsage.objects.create(user=None, kind="tailor", success=False, error="timeout")
        ActivityLog.objects.create(user=None, action="limit_reached", ip="1.1.1.1", meta={"kind": "generate"})
        ErrorLog.objects.create(source="apps.cv", message="Boom", traceback="Traceback...")
        ContactMessage.objects.create(name="Vali", contact="@vali", message="Salom")

    def test_all_pages_render_with_data(self):
        self._seed()
        for name in PAGES:
            self.assertEqual(self.client.get(reverse(f"panel:{name}")).status_code, 200, name)
        self.assertEqual(self.client.get(reverse("panel:user_detail", args=[self.user.pk])).status_code, 200)
        self.assertContains(self.client.get(reverse("panel:users") + "?q=10.0.0.5"), "Ali")
        self.assertContains(self.client.get(reverse("panel:payments") + "?q=%23" + str(PaymentRequest.objects.get().pk)), "Ali")

    @mock.patch("apps.users.bot.send_message")
    def test_approve_and_reject(self, send):
        req = PaymentRequest.objects.create(user=self.user, plan=self.pack, amount=self.pack.price, status=PaymentRequest.STATUS_PENDING)
        self.client.post(reverse("panel:payment_decide", args=[req.pk]), {"action": "approve"})
        req.refresh_from_db()
        self.assertEqual((req.status, req.reviewed_by), (PaymentRequest.STATUS_APPROVED, self.admin))
        self.assertEqual(UserProfile.objects.get(user=self.user).credits, 3)

        other = PaymentRequest.objects.create(user=self.user, plan=self.pack, amount=self.pack.price, status=PaymentRequest.STATUS_PENDING)
        self.client.post(reverse("panel:payment_decide", args=[other.pk]), {"action": "reject", "note": "Summa kam"})
        other.refresh_from_db()
        self.assertEqual((other.status, other.admin_note), (PaymentRequest.STATUS_REJECTED, "Summa kam"))

    def test_credit_buttons_and_manual_amount(self):
        url = reverse("panel:user_action", args=[self.user.pk])
        self.client.post(url, {"action": "credits", "quick": "3", "amount": ""})
        self.client.post(url, {"action": "credits", "amount": "-1"})
        self.client.post(url, {"action": "credits", "amount": "-100"})
        self.assertEqual(UserProfile.objects.get(user=self.user).credits, 0)
        self.client.post(url, {"action": "credits", "quick": "3"})
        self.assertEqual(UserProfile.objects.get(user=self.user).credits, 3)

    def test_block_with_ip_and_unblock(self):
        url = reverse("panel:user_action", args=[self.user.pk])
        self.client.post(url, {"action": "block", "reason": "Spam", "with_ip": "1"})
        profile = UserProfile.objects.get(user=self.user)
        self.assertTrue(profile.is_blocked)
        self.assertTrue(BlockedIP.objects.filter(ip="10.0.0.5").exists())
        self.client.post(url, {"action": "unblock"})
        self.assertFalse(UserProfile.objects.get(user=self.user).is_blocked)
        self.assertFalse(BlockedIP.objects.exists())

    def test_cannot_block_staff(self):
        self.client.post(reverse("panel:user_action", args=[self.admin.pk]), {"action": "block"})
        self.assertFalse(UserProfile.objects.get(user=self.admin).is_blocked)

    def test_give_pro(self):
        self.client.post(reverse("panel:user_action", args=[self.user.pk]), {"action": "pro", "days": "30"})
        self.assertTrue(UserProfile.objects.get(user=self.user).has_active_premium)

    def test_save_settings_and_prices(self):
        response = self.client.get(reverse("panel:settings"))
        form = response.context["form"]
        data = {"section": "site"}
        for name, field in form.fields.items():
            value = form.initial.get(name, field.initial)
            if isinstance(value, bool):
                if value:
                    data[name] = "on"
            else:
                data[name] = "" if value is None else value
        data["card_number"] = "9860 0000 1111 2222"
        self.client.post(reverse("panel:settings"), data)
        self.assertEqual(SiteSettings.objects.get().card_number, "9860 0000 1111 2222")

        plans = response.context["plans"]
        pdata = {"section": "plans", "plans-TOTAL_FORMS": str(len(plans.forms)), "plans-INITIAL_FORMS": str(len(plans.forms))}
        for i, pf in enumerate(plans.forms):
            for name in pf.fields:
                value = pf.initial.get(name)
                key = f"plans-{i}-{name}"
                if isinstance(value, bool):
                    if value:
                        pdata[key] = "on"
                else:
                    pdata[key] = "" if value is None else value
            pdata[f"plans-{i}-id"] = pf.instance.pk
            if pf.instance.code == "kredit-3":
                pdata[f"plans-{i}-price"] = "15000"
        self.client.post(reverse("panel:settings"), pdata)
        self.assertEqual(int(PricingPlan.objects.get(code="kredit-3").price), 15000)

    def test_resolve_errors(self):
        e = ErrorLog.objects.create(source="x", message="m")
        self.client.post(reverse("panel:errors_resolve"), {"ids": [e.pk]})
        e.refresh_from_db()
        self.assertTrue(e.is_resolved)


def tg_ok(method, payload=None, files=None):
    return {"ok": True, "result": {"message_id": 1}}


class BroadcastTests(TestCase):
    def setUp(self):
        from apps.users.models import Broadcast

        self.Broadcast = Broadcast
        self.admin = User.objects.create_user(username="boss", first_name="Bosh", is_staff=True, is_superuser=True)
        self.client.force_login(self.admin)
        self.fresh = self._user("fresh", "Aziza", "998901110001", 101, cv=True)          # yaratgan, yuklamagan
        self.loader = self._user("loader", "Botir", "998901110002", 102, cv=True)        # yuklab olgan
        ActivityLog.objects.create(user=self.loader, action="download_pdf")
        self.empty = self._user("empty", "Dilnoza", "998901110003", 103, username_tg="dilnoza")  # rezyume yo'q
        self._user("webonly", "Eldor", "998901110004", None, cv=True)                   # Telegram yo'q
        blocked = self._user("blocked", "Farrux", "998901110005", 105, cv=True)
        UserProfile.objects.filter(user=blocked).update(is_blocked=True)

    def _user(self, username, first_name, phone, tg_id, cv=False, username_tg=""):
        user = User.objects.create_user(username=username, first_name=first_name)
        UserProfile.objects.filter(user=user).update(phone=f"+{phone}", telegram_id=tg_id, telegram_username=username_tg)
        if cv:
            CV.objects.create(user=user, raw_input_text="x", cv_json={**DEMO_CV_JSON, "full_name": f"{first_name} Test"})
        return user

    def _form(self, **kw):
        data = {"title": "Test", "audience": "all", "selected_users": "", "text": "Salom {ism}!", "bonus_credits": "0",
                "feedback_options": "", "button_site": "on"}
        data.update(kw)
        return {k: v for k, v in data.items() if v is not False}

    def test_audiences_only_reach_linked_active_users(self):
        from apps.users.broadcast import audience_profiles

        def names(**kw):
            return sorted(p.user.username for p in audience_profiles(self.Broadcast(**kw)))

        self.assertEqual(names(audience="all"), ["empty", "fresh", "loader"])
        self.assertEqual(names(audience="cv_not_downloaded"), ["fresh"])
        self.assertEqual(names(audience="no_cv"), ["empty"])
        self.assertEqual(names(audience="all", attach_cv=True), ["fresh", "loader"])
        self.assertEqual(names(audience="selected", selected_users=f"90 111 00 01, @DILNOZA\n{self.loader.pk}\n+998901110005"),
                         ["empty", "fresh", "loader"])  # bloklangan tanlansa ham yuborilmaydi

    def test_form_validation(self):
        url = reverse("panel:broadcasts")
        self.assertContains(self.client.post(url, self._form(text="<div>salom</div>")), "Telegram bu teglarni qo")
        self.assertContains(self.client.post(url, self._form(audience="selected")), "Kimga yuborilishini tanlang")
        self.assertContains(self.client.post(url, self._form(attach_cv="on", text="x" * 1100)), "1000 belgidan")
        self.assertFalse(self.Broadcast.objects.exists())
        self.assertEqual(self.client.get(url).status_code, 200)
        prefilled = self.client.get(url + f"?to={self.fresh.pk}")
        self.assertEqual([p["name"] for p in prefilled.context["picker_initial"]], ["Aziza"])

    def test_picker_search_and_chosen_cv_is_sent(self):
        from apps.users import broadcast as engine

        older = CV.objects.get(user=self.fresh)
        CV.objects.create(user=self.fresh, raw_input_text="x", cv_json={**DEMO_CV_JSON, "full_name": "Aziza Yangi"})
        foreign = CV.objects.get(user=self.loader)

        people = self.client.get(reverse("panel:broadcast_people") + "?q=90 111 00 01").json()["people"]
        self.assertEqual([(p["name"], len(p["cvs"])) for p in people], [("Aziza", 2)])
        self.assertEqual(people[0]["cvs"][0]["name"], "Aziza Yangi")  # eng yangisi birinchi
        self.assertEqual([p["name"] for p in self.client.get(reverse("panel:broadcast_people") + "?q=@dilnoza").json()["people"]], ["Dilnoza"])
        no_tg = self.client.get(reverse("panel:broadcast_people") + "?q=Eldor").json()["people"][0]
        self.assertFalse(no_tg["telegram"])

        # boshqa odamning rezyumesini tanlab bo'lmaydi — forma uni tashlab yuboradi
        self.client.post(reverse("panel:broadcasts"), self._form(
            audience="selected", selected_users=f"{self.fresh.pk}\n{self.loader.pk}", attach_cv="on",
            selected_cvs=json.dumps({str(self.fresh.pk): older.pk, str(self.loader.pk): CV.objects.get(user=self.fresh, cv_json__full_name="Aziza Yangi").pk})))
        b = self.Broadcast.objects.get()
        self.assertEqual(b.selected_cvs, {str(self.fresh.pk): older.pk})
        engine.start(b)
        cvs = dict(b.recipients.values_list("user_id", "cv_id"))
        self.assertEqual(cvs, {self.fresh.pk: older.pk, self.loader.pk: foreign.pk})  # tanlangani va avtomatik oxirgisi

        detail = self.client.get(reverse("panel:broadcast_detail", args=[b.pk]))
        self.assertContains(detail, "Aziza Test · ")
        self.assertContains(detail, "Avtomatik")

    @mock.patch("apps.users.bot._post")
    @mock.patch("apps.users.broadcast._render_pdf", return_value=b"%PDF-1.7")
    @mock.patch("apps.users.broadcast._api")
    def test_gift_cv_with_credit_feedback_and_blocked_user(self, api, _pdf, post):
        from apps.users.broadcast import handle_feedback, process_pending
        from apps.users.models import BroadcastRecipient

        blocked_bot = self._user("gone", "Gulnora", "998901110006", 106, cv=True)
        api.side_effect = lambda method, payload=None, files=None: (
            {"ok": False, "error_code": 403, "description": "Forbidden: bot was blocked by the user"}
            if payload["chat_id"] == 106 else tg_ok(method, payload, files))

        self.client.post(reverse("panel:broadcasts"), self._form(
            title="Sovg'a", audience="cv_not_downloaded", attach_cv="on", bonus_credits="1",
            text="🎁 <b>{ism}</b>, rezyumengiz sovg'a! +{kredit} kredit", feedback_options="👍 Foydali bo'ldi\n👎 Kerak emas"))
        b = self.Broadcast.objects.get()
        detail = self.client.get(reverse("panel:broadcast_detail", args=[b.pk]))
        self.assertContains(detail, "Yuborish (2)")
        self.assertContains(detail, "Foydali bo")

        self.client.post(reverse("panel:broadcast_action", args=[b.pk]), {"action": "start"})
        b.refresh_from_db()
        self.assertEqual((b.status, b.recipients.count()), ("sending", 2))
        api.assert_not_called()  # sayt so'rovi yubormaydi — bot fon oqimi yuboradi

        self.assertEqual(process_pending(pause=0), 2)
        b.refresh_from_db()
        self.assertEqual(b.status, "done")
        method, payload, files = api.call_args_list[0].args[0], api.call_args_list[0].args[1], api.call_args_list[0].kwargs["files"]
        self.assertEqual(method, "sendDocument")
        self.assertEqual(files["document"][0], "Aziza_Test_Rezyume_tezrezyume.uz.pdf")
        self.assertIn("<b>Aziza</b>, rezyumengiz sovg'a! +1 kredit", payload["caption"])
        buttons = [btn["text"] for row in payload["reply_markup"]["inline_keyboard"] for btn in row]
        self.assertEqual(buttons, ["👍 Foydali bo'ldi", "👎 Kerak emas"])

        sent = BroadcastRecipient.objects.get(user=self.fresh)
        gone = BroadcastRecipient.objects.get(user=blocked_bot)
        self.assertEqual((sent.status, gone.status), ("sent", "blocked"))
        self.assertEqual(UserProfile.objects.get(user=self.fresh).credits, 1)
        self.assertEqual(UserProfile.objects.get(user=blocked_bot).credits, 0)  # yetib bormagan — kredit yo'q
        self.assertTrue(ActivityLog.objects.filter(user=self.fresh, action="broadcast_bonus").exists())

        callback = {"id": "c1", "data": f"bf:{sent.pk}:0", "from": {"id": 101}, "message": {"message_id": 5, "chat": {"id": 101}}}
        handle_feedback({**callback, "from": {"id": 999}})  # begona odam bosa olmaydi
        sent.refresh_from_db()
        self.assertEqual(sent.response, "")
        handle_feedback(callback)
        handle_feedback({**callback, "data": f"bf:{sent.pk}:1"})  # fikrini o'zgartirib bo'lmaydi
        sent.refresh_from_db()
        self.assertEqual(sent.response, "👍 Foydali bo'ldi")
        edited = [c for c in post.call_args_list if c.args[0] == "editMessageReplyMarkup"][-1]
        self.assertEqual(edited.kwargs["reply_markup"]["inline_keyboard"][0][0]["text"], "✓ 👍 Foydali bo'ldi")
        self.assertContains(self.client.get(reverse("panel:broadcast_detail", args=[b.pk]) + "?s=answered"), "Aziza")

    @mock.patch("apps.users.broadcast._api", side_effect=tg_ok)
    def test_test_send_cancel_and_copy(self, api):
        from apps.users.broadcast import process_pending

        self.client.post(reverse("panel:broadcasts"), self._form(title="E'lon", bonus_credits="2"))
        b = self.Broadcast.objects.get()
        action = reverse("panel:broadcast_action", args=[b.pk])

        self.assertContains(self.client.post(action, {"action": "test"}, follow=True), "Telegram bilan bog")
        UserProfile.objects.filter(user=self.admin).update(telegram_id=1)
        self.assertContains(self.client.post(action, {"action": "test"}, follow=True), "Sinov xabari")
        self.assertEqual(api.call_args.args[1]["chat_id"], 1)
        self.assertEqual(UserProfile.objects.get(user=self.admin).credits, 0)  # sinovda kredit berilmaydi

        self.client.post(action, {"action": "start"})
        self.client.post(action, {"action": "cancel"})
        api.reset_mock()
        self.assertEqual(process_pending(pause=0), 0)
        api.assert_not_called()
        b.refresh_from_db()
        self.assertEqual(b.status, "cancelled")

        self.client.post(action, {"action": "copy"})
        self.assertEqual(self.Broadcast.objects.filter(status="draft", title="E'lon (nusxa)").count(), 1)

    def test_lucky_gift_page_saves_text_and_shows_stats(self):
        from apps.cv.models import LuckyGift, LuckyGrant

        cv = CV.objects.create(user=self.fresh, raw_input_text="x", cv_json=DEMO_CV_JSON, lucky_pdf=True)
        LuckyGrant.objects.create(user=self.fresh, cv=cv, reaction="🙏 Rahmat", downloaded=True)

        page = self.client.get(reverse("panel:lucky"))
        self.assertContains(page, "🙏 Rahmat")
        self.assertContains(page, "Aziza")

        self.client.post(reverse("panel:lucky"), {
            "is_active": "on", "audience": "new", "new_user_days": "5", "daily_limit": "50",
            "title": "Bugun sizning kuningiz!", "text": "Istalgan shablonda PDF oling.", "button_label": "Olish",
            "reactions": "😊 Zo'r\n🙂 Kerak emas", "thanks_text": "Rahmat!", "show_popup": "on", "confetti": "on"})
        gift = LuckyGift.load()
        self.assertEqual((gift.is_active, gift.audience, gift.title, gift.options), (True, "new", "Bugun sizning kuningiz!", ["😊 Zo'r", "🙂 Kerak emas"]))
        self.assertFalse(gift.sound)  # belgilanmagan katakcha — o'chadi
        self.assertContains(self.client.post(reverse("panel:lucky"), {
            "is_active": "on", "audience": "all", "new_user_days": "3", "daily_limit": "0", "title": "T", "text": "x",
            "button_label": "Olish", "reactions": "a\nb\nc\nd\ne", "thanks_text": "ok"}), "Ko&#x27;pi bilan 4 ta tugma")

    def test_only_superuser(self):
        helper = User.objects.create_user(username="helper", is_staff=True)
        self.client.force_login(helper)
        self.assertRedirects(self.client.get(reverse("panel:broadcasts")), reverse("panel:dashboard"), fetch_redirect_response=False)
