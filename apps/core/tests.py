from django.test import TestCase

# Create your tests here.


class GuidePageTests(TestCase):
    def test_guide_renders_all_questions_with_valid_faq_schema(self):
        import json
        import re

        from .guide import SECTIONS

        response = self.client.get("/qollanma/")
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        total = sum(len(s["items"]) for s in SECTIONS)
        self.assertEqual(html.count('data-qa>'), total)
        self.assertIn("Diplomsiz ish topsa bo&#x27;ladimi?", html)
        schema = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S).group(1))
        self.assertEqual(len(schema["mainEntity"]), total)
        self.assertNotIn("<", json.dumps(schema, ensure_ascii=False))

    def test_guide_linked_from_navigation(self):
        self.assertContains(self.client.get("/"), 'href="/qollanma/"')


CHROME = "Mozilla/5.0 (Linux; Android 13; SM-A515F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Mobile Safari/537.36"


class VisitAnalyticsTests(TestCase):
    def test_classify(self):
        from .analytics import classify, parse_device

        self.assertEqual(classify("Mozilla/5.0 (compatible; Googlebot/2.1)"), ("bot", "Google"))
        self.assertEqual(classify("TelegramBot (like TwitterBot)"), ("bot", "Telegram (havola ko'rinishi)"))
        self.assertEqual(classify("python-requests/2.31")[0], "bot")
        self.assertEqual(classify("")[0], "bot")
        self.assertEqual(classify(CHROME, "/.env")[0], "scanner")
        self.assertEqual(classify("sqlmap/1.7")[0], "scanner")
        self.assertEqual(classify(CHROME), ("unknown", ""))
        self.assertEqual(parse_device(CHROME), ("mobile", "Android", "Chrome"))

    def test_browser_becomes_human_after_js_and_funnel_is_tracked(self):
        from .models import PageView, Visitor

        r = self.client.get("/", HTTP_USER_AGENT=CHROME, HTTP_REFERER="https://t.me/some_channel")
        self.assertIn("tv", r.cookies)
        v = Visitor.objects.get()
        self.assertEqual((v.kind, v.source, v.landing_path, v.device), ("unknown", "telegram", "/", "mobile"))

        self.client.post("/t/p/", {"wd": "0"}, HTTP_USER_AGENT=CHROME)
        self.client.get("/cv/builder/", HTTP_USER_AGENT=CHROME)
        v.refresh_from_db()
        self.assertEqual((v.kind, v.pageviews, v.did_builder, v.last_path), ("human", 2, True, "/cv/builder/"))
        self.assertEqual(v.stage, "Yaratish sahifasida to'xtadi")
        self.assertEqual(PageView.objects.count(), 2)

    def test_headless_browser_is_bot(self):
        from .models import Visitor

        self.client.get("/", HTTP_USER_AGENT=CHROME)
        self.client.post("/t/p/", {"wd": "1"})
        self.assertEqual(Visitor.objects.get().kind, "bot")

    def test_cookieless_bot_does_not_create_many_visitors_and_scanner_detected(self):
        from .models import Visitor

        for _ in range(3):
            self.client_class().get("/", HTTP_USER_AGENT="Mozilla/5.0 (compatible; bingbot/2.0)")
        self.assertEqual(Visitor.objects.filter(kind="bot").count(), 1)
        scanner = self.client_class()
        for path in ("/.env", "/wp-admin/setup-config.php"):
            scanner.get(path, HTTP_USER_AGENT="Mozilla/5.0 zgrab/0.x")
        v = Visitor.objects.get(kind="scanner")
        self.assertEqual(v.views.count(), 2)

    def test_static_panel_and_admin_not_tracked(self):
        from .models import Visitor

        self.client.get("/robots.txt")
        self.client.get("/healthz/")
        self.client.get("/panel/")
        self.assertFalse(Visitor.objects.filter(kind="unknown").exists())

    def test_panel_visits_page(self):
        from django.contrib.auth import get_user_model

        from .models import Visitor

        self.client.get("/", HTTP_USER_AGENT=CHROME)
        self.client.post("/t/p/", {"wd": "0"})
        self.client_class().get("/.env", HTTP_USER_AGENT="curl/8")
        admin = get_user_model().objects.create_user(username="boss", is_staff=True)
        self.client.force_login(admin)
        for days in (1, 7, 30):
            r = self.client.get(f"/panel/tashriflar/?days={days}&kind=all")
            self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context["humans"], 1)
        self.assertEqual(r.context["scanners"], 1)
        self.assertIsInstance(r.context["bots"], int)
        self.assertEqual(r.context["stages"][0]["n"], 1)
        v = Visitor.objects.get(kind="human")
        self.assertContains(self.client.get(f"/panel/tashriflar/{v.pk}/"), "Faqat ko&#x27;rib ketdi")
        scanner = Visitor.objects.get(kind="scanner")
        self.client.post(f"/panel/tashriflar/{scanner.pk}/blok/")
        from .models import BlockedIP

        self.assertTrue(BlockedIP.objects.filter(ip=scanner.ip).exists())
