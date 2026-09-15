from decimal import Decimal

from django.db import migrations


def seed_plans(apps, schema_editor):
    PricingPlan = apps.get_model("users", "PricingPlan")

    PricingPlan.objects.update_or_create(
        code="cv-bir-martalik",
        defaults={
            "name": "Bitta CV",
            "scope": "cv",
            "description": "Bitta CV uchun bir martalik to'lov: 7 ta shablon, PDF va Word, belgisiz — umrbod.",
            "price": Decimal("19900.00"),
            "billing_period": "one_time",
            "duration_days": 0,
            "includes_pdf_export": True,
            "includes_docx_export": True,
            "includes_premium_templates": True,
            "sort_order": 1,
            "is_active": True,
        },
    )

    # Mavjud oylik "premium" tarif Pro ga aylanadi. Narx bir martalik to'lovdan
    # sezilarli yuqori bo'lishi kerak, aks holda "Bitta CV" ma'nosiz bo'lib qoladi.
    pro = PricingPlan.objects.filter(code="premium").first()
    defaults = {
        "name": "Pro",
        "price": Decimal("49900.00"),
        "description": "Cheksiz CV, barcha shablonlar, PDF va Word, share link va kompaniya brendingi.",
        "scope": "account",
        "includes_pdf_export": True,
        "includes_docx_export": True,
        "includes_premium_templates": True,
        "sort_order": 2,
    }
    if pro:
        for key, value in defaults.items():
            setattr(pro, key, value)
        pro.save()
    else:
        PricingPlan.objects.create(
            code="pro-oylik",
            billing_period="monthly",
            duration_days=30,
            is_active=True,
            **defaults,
        )


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0004_telegramlogintoken_delete_phoneotp_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_plans, migrations.RunPython.noop),
    ]
