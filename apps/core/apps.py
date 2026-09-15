from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.core'
    verbose_name = "Sayt"

    def ready(self):
        from . import activity  # noqa: F401 — login/logout signal'larini ulaydi