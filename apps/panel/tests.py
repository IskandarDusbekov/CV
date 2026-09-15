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
