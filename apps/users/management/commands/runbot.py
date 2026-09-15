"""
python manage.py runbot

Telegram botni long-polling rejimida ishga tushiradi.
Ctrl+C bilan to'xtatiladi.
"""
import django
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Telegram login botni ishga tushiradi"

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Bot ishga tushmoqda..."))
        import django
        django.setup()
        from apps.users.bot import run_polling
        run_polling()
