from django.db import migrations

PAIRS = [
    ("ta CV ni ochish", "ta rezyumeni ochish"),
    ("Bitta CV", "Bitta rezyume"),
    ("Cheksiz CV", "Cheksiz rezyume"),
    ("AI CV builder", "AI rezyume yaratuvchi"),
    ("o'tadigan CV ga", "o'tadigan rezyumega"),
    ("ta CV", "ta rezyume"),
]


def _replace(text):
    for old, new in PAIRS:
        text = text.replace(old, new)
    return text


def forwards(apps, schema_editor):
    """Bazadagi tarif nomlari va sahifa matnlarida "CV" o'rniga "rezyume"."""
    PricingPlan = apps.get_model("users", "PricingPlan")
    for plan in PricingPlan.objects.all():
        name, desc = _replace(plan.name), _replace(plan.description or "")
        if (name, desc) != (plan.name, plan.description or ""):
            plan.name, plan.description = name, desc
            plan.save(update_fields=["name", "description"])

    Page = apps.get_model("core", "Page")
    for page in Page.objects.all():
        title, subtitle, body = _replace(page.title), _replace(page.subtitle), _replace(page.body)
        if (title, subtitle, body) != (page.title, page.subtitle, page.body):
            page.title, page.subtitle, page.body = title, subtitle, body
            page.save(update_fields=["title", "subtitle", "body"])


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0010_alter_paymentrequest_receipt"),
        ("core", "0003_tezrezyume_brand"),
    ]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
