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
