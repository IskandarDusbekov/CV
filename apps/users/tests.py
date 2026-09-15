from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.cv.models import CV
from apps.cv.services import DEMO_CV_JSON

from . import bot
from apps.core.models import ActivityLog, BlockedIP, ContactMessage, ErrorLog, SiteSettings

from .models import PaymentRequest, PricingPlan, TelegramLoginToken, UserProfile
from .telegram_auth import (
    confirm_token,
    consume_token,
    create_login_token,
    get_or_create_user,
    normalize_phone,
    verify_webapp_init_data,
)

User = get_user_model()


class PhoneTests(TestCase):
    def test_normalize(self):
        self.assertEqual(normalize_phone("90 123-45-67"), "+998901234567")
        self.assertEqual(normalize_phone("+998 (90) 123 45 67"), "+998901234567")
        self.assertEqual(normalize_phone("998901234567"), "+998901234567")


class TelegramLoginTests(TestCase):
    def _login_page_token(self):
        self.client.get(reverse("user_login"))
        return TelegramLoginToken.objects.get(token=self.client.session["tg_login_token"])

    def test_pending_then_confirmed_logs_in_and_creates_account(self):
        token = self._login_page_token()
        self.assertEqual(self.client.get(reverse("telegram_login_status")).json()["status"], "pending")

        confirm_token(token, phone="998901112233", telegram_id=555, first_name="Ali", last_name="Valiyev", username="ali")
        data = self.client.get(reverse("telegram_login_status")).json()

        self.assertEqual(data["status"], "ok")
        user = User.objects.get(profile__phone="+998901112233")
        self.assertEqual(user.first_name, "Ali")
        self.assertEqual(user.profile.telegram_id, 555)
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.id)

    def test_existing_account_matched_by_phone(self):
        existing = User.objects.create_user(username="old")
        UserProfile.objects.filter(user=existing).update(phone="+998901112233")
        token = self._login_page_token()
        confirm_token(token, phone="+998 90 111 22 33", telegram_id=777)

        self.client.get(reverse("telegram_login_status"))

        self.assertEqual(int(self.client.session["_auth_user_id"]), existing.id)
        self.assertEqual(User.objects.count(), 1)

    def test_other_session_cannot_consume_token_via_status(self):
        token = self._login_page_token()
        confirm_token(token, phone="998901112233", telegram_id=1)
        other = self.client_class()
        other.get(reverse("user_login"))
        self.assertNotEqual(other.get(reverse("telegram_login_status")).json()["status"], "ok")

    def test_magic_link_is_single_use(self):
        token = create_login_token()
        confirm_token(token, phone="998901112233", telegram_id=9)
        url = reverse("telegram_login_complete", args=[token.token])
        self.assertRedirects(self.client.get(url), reverse("user_dashboard"), fetch_redirect_response=False)
        self.client.logout()
        self.assertRedirects(self.client.get(url), reverse("user_login"), fetch_redirect_response=False)

    def test_anonymous_cvs_are_claimed_after_login(self):
        cv = CV.objects.create(raw_input_text="x", cv_json=DEMO_CV_JSON)
        session = self.client.session
        session["owned_cv_ids"] = [cv.id]
        session.save()
        token = self._login_page_token()
        confirm_token(token, phone="998901112233", telegram_id=3)
        self.client.get(reverse("telegram_login_status"))
        cv.refresh_from_db()
        self.assertIsNotNone(cv.user_id)


BOT_TOKEN = "123456:TEST"


def _init_data(user_id=777, auth_date=None, token=BOT_TOKEN, **extra):
    """Telegram klienti kabi imzolangan initData yasaydi."""
    import hashlib
    import hmac
    import json
    import time
    from urllib.parse import urlencode

    fields = {"auth_date": str(auth_date or int(time.time())), "query_id": "AAH",
              "user": json.dumps({"id": user_id, "first_name": "Ali", "username": "ali_tg"}), **extra}
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    check = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    fields["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(fields)


@override_settings(TELEGRAM_BOT_TOKEN=BOT_TOKEN)
class TelegramWebAppTests(TestCase):
    def _auth(self, init_data, next_url="/users/dashboard/"):
        return self.client.post(reverse("telegram_webapp_auth"), {"init_data": init_data, "next": next_url})

    def test_verify_accepts_valid_and_rejects_tampered_or_old(self):
        self.assertEqual(verify_webapp_init_data(_init_data(user_id=5))["id"], 5)
        self.assertEqual(verify_webapp_init_data(_init_data(user_id=5, signature="abc"))["id"], 5)
        self.assertIsNone(verify_webapp_init_data(_init_data(user_id=5).replace("ali_tg", "hacker")))
        self.assertIsNone(verify_webapp_init_data(_init_data(user_id=5, token="999:OTHER")))
        self.assertIsNone(verify_webapp_init_data(_init_data(user_id=5, auth_date=1_000_000)))
        self.assertIsNone(verify_webapp_init_data(""))

    def test_linked_account_logs_in(self):
        user = get_or_create_user(phone="998901112233", telegram_id=777)
        data = self._auth(_init_data(), next_url="/cv/builder/").json()
        self.assertEqual(data, {"status": "ok", "redirect": "/cv/builder/"})
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)
        # Qayta ochilganda qayta login yozilmaydi
        self.assertEqual(self._auth(_init_data()).json()["status"], "ok")
        self.assertEqual(ActivityLog.objects.filter(user=user, action__in=["login", "register"]).count(), 1)

    def test_unknown_telegram_user_needs_phone(self):
        self.assertEqual(self._auth(_init_data(user_id=1)).json()["status"], "need_phone")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_invalid_and_blocked(self):
        self.assertEqual(self._auth("hash=bad&auth_date=1").status_code, 403)
        user = get_or_create_user(phone="998901112233", telegram_id=777)
        UserProfile.objects.filter(user=user).update(is_blocked=True)
        self.assertEqual(self._auth(_init_data()).json()["status"], "blocked")

    def test_external_next_is_ignored(self):
        get_or_create_user(phone="998901112233", telegram_id=777)
        self.assertEqual(self._auth(_init_data(), next_url="https://evil.example/").json()["redirect"], "/users/dashboard/")

    def test_page_renders(self):
        r = self.client.get(reverse("telegram_webapp") + "?next=/cv/builder/")
        self.assertContains(r, "telegram-web-app.js")
        self.assertContains(r, "/cv/builder/")

    def test_old_bot_link_for_logged_in_user_goes_to_dashboard(self):
        user = get_or_create_user(phone="998901112233", telegram_id=777)
        self.client.force_login(user)
        r = self.client.get(reverse("telegram_login_complete", args=["eskirgan"]))
        self.assertRedirects(r, reverse("user_dashboard"), fetch_redirect_response=False)


@mock.patch.object(bot, "send_message")
class BotTests(TestCase):
    def _update(self, **message):
        base = {"chat": {"id": 42}, "from": {"id": 42, "first_name": "Ali", "username": "ali"}}
        bot._handle_update({"message": {**base, **message}})

    def test_start_with_token_then_contact_confirms(self, send):
        token = create_login_token(session_key="s")
        self._update(text=f"/start {token.token}")
        self._update(contact={"phone_number": "998901112233", "user_id": 42, "first_name": "Ali"})
        token.refresh_from_db()
        self.assertEqual(token.status, TelegramLoginToken.STATUS_CONFIRMED)
        self.assertEqual(token.phone, "+998901112233")

    @override_settings(SITE_URL="https://tezrezyume.uz")
    def test_plain_start_then_contact_sends_webapp_button_not_expiring_link(self, send):
        self._update(text="/start")
        self._update(contact={"phone_number": "+998901112233", "user_id": 42})
        self.assertTrue(UserProfile.objects.filter(telegram_id=42, phone="+998901112233").exists())
        self.assertFalse(TelegramLoginToken.objects.exists())
        sent = str(send.call_args_list)
        self.assertIn("'web_app': {'url': 'https://tezrezyume.uz/users/tg/?next=", sent)
        self.assertNotIn("/users/login/tg/", sent)

    @override_settings(SITE_URL="https://tezrezyume.uz")
    def test_start_for_linked_account_opens_site_without_asking_phone(self, send):
        get_or_create_user(phone="998901112233", telegram_id=42)
        self._update(text="/start")
        sent = str(send.call_args_list)
        self.assertIn("web_app", sent)
        self.assertNotIn("request_contact", sent)

    def test_foreign_contact_rejected(self, send):
        self._update(text="/start")
        self._update(contact={"phone_number": "+998901112233", "user_id": 999})
        self.assertFalse(TelegramLoginToken.objects.filter(status=TelegramLoginToken.STATUS_CONFIRMED).exists())


@mock.patch.object(bot, "_post", return_value={"ok": True, "result": {}})
@mock.patch.object(bot, "send_message")
class BotPaymentTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="buyer", first_name="Ali")
        UserProfile.objects.filter(user=self.user).update(telegram_id=42, phone="+998901112233")
        self.pack = PricingPlan.objects.get(code="kredit-3")
        site = SiteSettings.load()
        site.card_number = "8600 1234 5678 9012"
        site.admin_chat_ids = "777"
        site.save()

    def _msg(self, **message):
        base = {"chat": {"id": 42}, "from": {"id": 42, "first_name": "Ali"}}
        bot._handle_update({"message": {**base, **message}})

    def _callback(self, data, sender_id=42):
        bot._handle_update({"callback_query": {"id": "1", "data": data, "from": {"id": sender_id}, "message": {"chat": {"id": sender_id}}}})

    @mock.patch.object(bot, "_download_file", return_value=(b"img", "receipt.jpg"))
    def test_full_flow_select_pay_send_receipt_admin_approves(self, _dl, send, post):
        self._msg(text="/start pay_kredit-3")
        self.assertIn("kredit-3", str(send.call_args_list) + self.pack.code)
        self._callback(f"buy:{self.pack.id}")
        req = PaymentRequest.objects.get()
        self.assertEqual(req.status, PaymentRequest.STATUS_AWAITING)
        self.assertIn("8600 1234 5678 9012", str(send.call_args_list[-1]))

        self._msg(photo=[{"file_id": "small"}, {"file_id": "big"}], caption="to'ladim")
        req.refresh_from_db()
        self.assertEqual(req.status, PaymentRequest.STATUS_PENDING)
        self.assertTrue(req.receipt.name)
        self.assertTrue(any(c.args[0] == "sendPhoto" and c.kwargs.get("chat_id") == 777 for c in post.call_args_list))

        self._callback(f"approve:{req.pk}", sender_id=777)
        req.refresh_from_db()
        self.assertEqual(req.status, PaymentRequest.STATUS_APPROVED)
        self.assertEqual(UserProfile.objects.get(user=self.user).credits, 3)

        # qayta tasdiqlash ikki marta kredit qo'shmaydi
        self._callback(f"approve:{req.pk}", sender_id=777)
        self.assertEqual(UserProfile.objects.get(user=self.user).credits, 3)

    def test_non_admin_cannot_approve(self, send, post):
        req = PaymentRequest.objects.create(user=self.user, plan=self.pack, amount=self.pack.price, status=PaymentRequest.STATUS_PENDING)
        self._callback(f"approve:{req.pk}", sender_id=42)
        req.refresh_from_db()
        self.assertEqual(req.status, PaymentRequest.STATUS_PENDING)

    def test_receipt_without_selection_is_not_saved(self, send, post):
        self._msg(photo=[{"file_id": "x"}])
        self.assertFalse(PaymentRequest.objects.exists())

    def test_pro_approval_activates_premium(self, send, post):
        pro = PricingPlan.objects.get(scope=PricingPlan.SCOPE_ACCOUNT)
        req = PaymentRequest.objects.create(user=self.user, plan=pro, amount=pro.price, status=PaymentRequest.STATUS_PENDING)
        req.approve()
        self.assertTrue(UserProfile.objects.get(user=self.user).has_active_premium)

    def test_blocked_user_gets_refused(self, send, post):
        UserProfile.objects.filter(user=self.user).update(is_blocked=True)
        self._msg(text="/tolov")
        self.assertIn("bloklangan", str(send.call_args_list[-1]))


class AdminPanelTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("admin", "a@a.uz", "pass12345")
        self.client.force_login(self.admin)
        self.user = User.objects.create_user(username="buyer")
        self.pack = PricingPlan.objects.get(code="kredit-3")

    def test_dashboard_with_anonymous_activity_and_anonymous_cv(self):
        ActivityLog.objects.create(user=None, action="limit_reached", ip="1.2.3.4")
        cv = CV.objects.create(user=None, raw_input_text="x", cv_json=DEMO_CV_JSON)
        self.assertContains(self.client.get("/admin/"), "anonim")
        self.assertContains(self.client.get(reverse("cv_preview", args=[cv.public_id])), "anonim foydalanuvchi")

    def test_admin_pages_render(self):
        for url in ["/admin/", "/admin/users/paymentrequest/", "/admin/users/userprofile/", "/admin/cv/cv/", "/admin/cv/aiusage/",
                    "/admin/core/activitylog/", "/admin/core/errorlog/", "/admin/core/page/", "/admin/users/pricingplan/"]:
            self.assertEqual(self.client.get(url).status_code, 200, url)
        self.assertEqual(self.client.get("/admin/core/sitesettings/", follow=True).status_code, 200)

    @mock.patch("apps.users.bot.send_message")
    def test_approve_and_reject_buttons(self, send):
        req = PaymentRequest.objects.create(user=self.user, plan=self.pack, amount=self.pack.price, status=PaymentRequest.STATUS_PENDING)
        self.assertContains(self.client.get(f"/admin/users/paymentrequest/{req.pk}/change/"), "Tasdiqlash")
        self.client.post(reverse("admin:users_paymentrequest_approve", args=[req.pk]))
        req.refresh_from_db()
        self.assertEqual(req.status, PaymentRequest.STATUS_APPROVED)
        self.assertEqual(req.reviewed_by, self.admin)

        other = PaymentRequest.objects.create(user=self.user, plan=self.pack, amount=self.pack.price, status=PaymentRequest.STATUS_PENDING)
        self.client.post(reverse("admin:users_paymentrequest_reject", args=[other.pk]), {"admin_note": "Summa kam"})
        other.refresh_from_db()
        self.assertEqual((other.status, other.admin_note), (PaymentRequest.STATUS_REJECTED, "Summa kam"))
        self.assertEqual(UserProfile.objects.get(user=self.user).credits, 3)


class BlockingAndLoggingTests(TestCase):
    def test_blocked_user_is_logged_out(self):
        user = User.objects.create_user(username="bad")
        UserProfile.objects.filter(user=user).update(is_blocked=True, block_reason="Spam")
        self.client.force_login(user)
        response = self.client.get("/users/dashboard/")
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "Spam", status_code=403)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_blocked_ip(self):
        BlockedIP.objects.create(ip="127.0.0.1")
        self.assertEqual(self.client.get("/").status_code, 403)

    def test_login_is_logged(self):
        user = User.objects.create_user(username="u")
        self.client.force_login(user)
        self.client.logout()
        self.assertTrue(ActivityLog.objects.filter(user=user, action="logout").exists())

    def test_errors_are_saved(self):
        import logging

        logging.getLogger("apps.cv").error("Test xatolik")
        self.assertTrue(ErrorLog.objects.filter(message="Test xatolik").exists())

    def test_contact_form(self):
        self.client.post("/aloqa/", {"name": "Ali", "contact": "@ali", "message": "Salom, savol bor"})
        self.assertTrue(ContactMessage.objects.filter(name="Ali").exists())
        self.assertEqual(self.client.get("/biz-haqimizda/").status_code, 200)
