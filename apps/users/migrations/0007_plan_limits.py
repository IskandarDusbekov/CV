from django.db import migrations


def set_limits(apps, schema_editor):
    PricingPlan = apps.get_model("users", "PricingPlan")
    PricingPlan.objects.filter(scope="cv").update(max_cvs=1, max_tailorings=5)
    PricingPlan.objects.filter(scope="account").update(max_cvs=30, max_tailorings=50)


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0006_pricingplan_max_cvs_pricingplan_max_tailorings"),
    ]

    operations = [
        migrations.RunPython(set_limits, migrations.RunPython.noop),
    ]
