from decimal import Decimal

from django.db import migrations


def to_credit_packages(apps, schema_editor):
    """Bir martalik "Bitta CV" tarifi o'rniga kredit paketlari."""
    PricingPlan = apps.get_model("users", "PricingPlan")
    PricingPlan.objects.filter(scope="cv").update(scope="credits", is_active=False)

    packs = [
        ("kredit-1", "1 ta CV", 1, Decimal("9000"), 1, False),
        ("kredit-3", "3 ta CV", 3, Decimal("19000"), 2, True),
        ("kredit-10", "10 ta CV", 10, Decimal("49000"), 3, False),
    ]
    for code, name, credits, price, order, featured in packs:
        PricingPlan.objects.update_or_create(code=code, defaults={
            "name": name, "scope": "credits", "credits": credits, "price": price,
            "billing_period": "one_time", "duration_days": 0, "sort_order": order,
            "is_featured": featured, "is_active": True, "max_tailorings": 5,
            "description": f"{credits} ta CV ni ochish: PDF + Word, muddatsiz",
            "includes_pdf_export": True, "includes_docx_export": True, "includes_premium_templates": True,
        })
    PricingPlan.objects.filter(scope="account").update(sort_order=10)


def seed_site(apps, schema_editor):
    SiteSettings = apps.get_model("core", "SiteSettings")
    Page = apps.get_model("core", "Page")
    SiteSettings.objects.get_or_create(pk=1)
    Page.objects.get_or_create(slug="biz-haqimizda", defaults={
        "title": "Biz haqimizda",
        "subtitle": "tezrezyume.uz — ish qidiruvchilar uchun AI yordamchi",
        "sort_order": 1,
        "body": "tezrezyume.uz — O'zbekistondagi ish qidiruvchilar uchun yaratilgan AI CV builder.\n\n"
                "Biz ishonamizki, yaxshi mutaxassis chiroyli rezyume yoza olmagani uchun ishdan qolmasligi kerak. "
                "Shuning uchun xizmatimiz oddiy: o'zingiz haqingizda erkin yozasiz — AI uni professional, "
                "ATS tizimlaridan o'tadigan CV ga aylantiradi.\n\n"
                "Bu matnni admin paneldagi «Sahifalar» bo'limidan o'zgartirishingiz mumkin.",
    })
    Page.objects.get_or_create(slug="aloqa", defaults={
        "title": "Aloqa",
        "subtitle": "Savol, taklif yoki muammo bo'lsa — yozing",
        "sort_order": 2,
        "body": "Odatda bir necha soat ichida javob beramiz.",
    })


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0008_alter_pricingplan_options_alter_userprofile_options_and_more"),
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(to_credit_packages, migrations.RunPython.noop),
        migrations.RunPython(seed_site, migrations.RunPython.noop),
    ]
