"""
python manage.py sendbroadcasts

Navbatdagi bot xabarlarini hoziroq yuboradi. Odatda kerak emas — `runbot` ularni o'zi fon oqimida yuboradi;
bot ishlamayotgan joyda (masalan, lokal kompyuterda) qo'lda yuborish uchun.
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Paneldan yuborilgan bot xabarlarini navbatdagi qabul qiluvchilarga yuboradi"

    def handle(self, *args, **options):
        from apps.users.broadcast import process_pending

        sent = process_pending()
        self.stdout.write(self.style.SUCCESS(f"Yuborildi: {sent}"))
