from django.db import migrations, models

OLD, NEW = "mycv.uz", "tezrezyume.uz"


def rename_brand(apps, schema_editor):
    SiteSettings = apps.get_model("core", "SiteSettings")
    SiteSettings.objects.filter(site_name=OLD).update(site_name=NEW)
    SiteSettings.objects.filter(bot_username__in=["mycv_uz_bot", "@mycv_uz_bot"]).update(bot_username="tezrezyume_bot")

    Page = apps.get_model("core", "Page")
    for page in Page.objects.all():
        fields = [f for f in ("title", "subtitle", "body") if OLD in (getattr(page, f, "") or "")]
        for f in fields:
            setattr(page, f, getattr(page, f).replace(OLD, NEW))
        if fields:
            page.save(update_fields=fields)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0002_alter_activitylog_action"),
        ("users", "0010_alter_paymentrequest_receipt"),
    ]

    operations = [
        migrations.AlterField(
            model_name="sitesettings",
            name="site_name",
            field=models.CharField(default="tezrezyume.uz", max_length=100, verbose_name="Sayt nomi"),
        ),
        migrations.RunPython(rename_brand, migrations.RunPython.noop),
    ]
