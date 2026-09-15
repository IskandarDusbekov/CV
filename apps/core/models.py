import uuid
from decimal import Decimal

from django.conf import settings
from django.core.cache import cache
from django.db import models
from django.utils import timezone


class SiteSettings(models.Model):
    """Kod yozmasdan admin paneldan boshqariladigan barcha sozlamalar (yagona yozuv)."""

    CACHE_KEY = "site_settings"

    # Sayt
    site_name = models.CharField("Sayt nomi", max_length=100, default="tezrezyume.uz")
    maintenance_message = models.CharField("E'lon (sayt tepasida)", max_length=300, blank=True,
                                           help_text="Bo'sh bo'lsa ko'rsatilmaydi")

    # To'lov (bot orqali qo'lda)
    card_number = models.CharField("Karta raqami", max_length=30, default="8600 0000 0000 0000")
    card_holder = models.CharField("Karta egasi", max_length=100, default="ISM FAMILIYA")
    card_bank = models.CharField("Bank / karta turi", max_length=100, blank=True, default="Uzcard")
    payment_instructions = models.TextField(
        "To'lov yo'riqnomasi (botda)", blank=True,
        default="To'lovni amalga oshirgach, chek skrinshotini shu yerga yuboring. 5–30 daqiqa ichida tekshiramiz.",
    )
    payment_notice = models.CharField(
        "Saytdagi to'lov izohi", max_length=300, blank=True,
        default="Click va Payme ulanmoqda — hozircha to'lov Telegram bot orqali qabul qilinadi.",
    )

    # Telegram
    bot_username = models.CharField("Bot username (@siz)", max_length=100, blank=True,
                                    help_text="Bo'sh bo'lsa .env dagi TELEGRAM_BOT_USERNAME ishlatiladi")
    admin_chat_ids = models.CharField("Admin Telegram chat ID lari", max_length=300, blank=True,
                                      help_text="Vergul bilan. Yangi chek va murojaatlar shu chatlarga yuboriladi.")
    support_telegram = models.CharField("Yordam uchun Telegram (@username)", max_length=100, blank=True)

    # Aloqa
    contact_phone = models.CharField("Telefon", max_length=50, blank=True)
    contact_email = models.EmailField("Email", blank=True)
    contact_address = models.CharField("Manzil", max_length=255, blank=True)
    working_hours = models.CharField("Ish vaqti", max_length=100, blank=True, default="Dush–Shan, 9:00–21:00")

    # Limitlar
    free_cv_limit = models.PositiveIntegerField("Bepul CV yaratish soni", default=2)
    free_tailor_limit = models.PositiveIntegerField("Bepul vakansiyaga moslashtirish soni", default=1)
    tailor_per_unlocked_cv = models.PositiveIntegerField("Ochilgan har bir CV uchun moslashtirish", default=5)

    # AI
    ai_model = models.CharField("OpenAI modeli", max_length=100, default="gpt-4.1-mini")
    ai_price_input_per_1m = models.DecimalField("Kirish narxi, $ / 1M token", max_digits=10, decimal_places=4, default=Decimal("0.40"))
    ai_price_output_per_1m = models.DecimalField("Chiqish narxi, $ / 1M token", max_digits=10, decimal_places=4, default=Decimal("1.60"))
    usd_to_uzs = models.PositiveIntegerField("1 $ = so'm (hisobotlar uchun)", default=12700)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Sayt sozlamalari"
        verbose_name_plural = "Sayt sozlamalari"

    def __str__(self):
        return "Sayt sozlamalari"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
        cache.delete(self.CACHE_KEY)

    @classmethod
    def load(cls):
        obj = cache.get(cls.CACHE_KEY)
        if obj is None:
            obj, _ = cls.objects.get_or_create(pk=1)
            cache.set(cls.CACHE_KEY, obj, 60)
        return obj

    @property
    def brand_base(self):
        """Logotip uchun: "tezrezyume.uz" → "tezrezyume"."""
        return self.site_name.rsplit(".", 1)[0] if "." in self.site_name else self.site_name

    @property
    def brand_tld(self):
        """Logotip uchun: "tezrezyume.uz" → ".uz"."""
        return "." + self.site_name.rsplit(".", 1)[1] if "." in self.site_name else ""

    @property
    def effective_bot_username(self):
        return (self.bot_username or getattr(settings, "TELEGRAM_BOT_USERNAME", "") or "").lstrip("@")

    @property
    def admin_chat_id_list(self):
        return [int(x) for x in self.admin_chat_ids.replace(" ", "").split(",") if x.lstrip("-").isdigit()]


class Page(models.Model):
    """Biz haqimizda, Aloqa va boshqa matnli sahifalar."""

    slug = models.SlugField("URL (slug)", unique=True, help_text="Masalan: biz-haqimizda, aloqa")
    title = models.CharField("Sarlavha", max_length=200)
    subtitle = models.CharField("Qisqa tavsif", max_length=300, blank=True)
    body = models.TextField("Matn", blank=True, help_text="Oddiy matn. Bo'sh qator — yangi paragraf.")
    show_in_footer = models.BooleanField("Footerda ko'rsatish", default=True)
    is_published = models.BooleanField("Chop etilgan", default=True)
    sort_order = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("sort_order", "title")
        verbose_name = "Sahifa"
        verbose_name_plural = "Sahifalar"

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        if self.slug in {"biz-haqimizda", "aloqa"}:
            return f"/{self.slug}/"
        return f"/sahifa/{self.slug}/"


class ContactMessage(models.Model):
    name = models.CharField("Ism", max_length=120)
    contact = models.CharField("Telefon / Telegram / email", max_length=150)
    message = models.TextField("Xabar")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    is_resolved = models.BooleanField("Javob berildi", default=False)
    admin_note = models.TextField("Admin izohi", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "Murojaat"
        verbose_name_plural = "Murojaatlar"

    def __str__(self):
        return f"{self.name} · {self.created_at:%d.%m.%Y}"


class ActivityLog(models.Model):
    """Kim, qachon, qaysi IP dan, nima qildi."""

    ACTION_CHOICES = [
        ("register", "Ro'yxatdan o'tdi"),
        ("login", "Kirdi"),
        ("logout", "Chiqdi"),
        ("cv_create", "CV yaratdi"),
        ("cv_tailor", "Vakansiyaga moslashtirdi"),
        ("cv_unlock", "CV ni kredit bilan ochdi"),
        ("cv_template", "Shablon almashtirdi"),
        ("download_pdf", "PDF yuklab oldi"),
        ("download_docx", "Word yuklab oldi"),
        ("payment_request", "To'lov cheki yubordi"),
        ("payment_approved", "To'lov tasdiqlandi"),
        ("payment_rejected", "To'lov rad etildi"),
        ("contact", "Murojaat yubordi"),
        ("blocked", "Bloklandi"),
        ("unblocked", "Blokdan chiqarildi"),
        ("credits_changed", "Kreditlari o'zgartirildi"),
        ("pro_granted", "Pro berildi"),
        ("staff_granted", "Panelga ruxsat berildi"),
        ("staff_removed", "Panel ruxsati olindi"),
        ("limit_reached", "Limitga yetdi"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="activity_logs")
    action = models.CharField("Harakat", max_length=30, choices=ACTION_CHOICES, db_index=True)
    ip = models.GenericIPAddressField(null=True, blank=True, db_index=True)
    user_agent = models.CharField(max_length=300, blank=True)
    path = models.CharField(max_length=300, blank=True)
    meta = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "Faollik"
        verbose_name_plural = "Faollik jurnali"

    def __str__(self):
        return f"{self.get_action_display()} · {self.user or self.ip}"


class ErrorLog(models.Model):
    level = models.CharField(max_length=20, default="ERROR")
    source = models.CharField("Manba (logger)", max_length=100, blank=True)
    path = models.CharField(max_length=300, blank=True)
    method = models.CharField(max_length=10, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    message = models.TextField()
    traceback = models.TextField(blank=True)
    is_resolved = models.BooleanField("Hal qilindi", default=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "Xatolik"
        verbose_name_plural = "Xatoliklar"

    def __str__(self):
        return self.message[:80]


class BlockedIP(models.Model):
    ip = models.GenericIPAddressField(unique=True)
    reason = models.CharField("Sabab", max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Bloklangan IP"
        verbose_name_plural = "Bloklangan IP lar"

    def __str__(self):
        return self.ip


class Visitor(models.Model):
    """Saytga kelgan bitta tashrifchi (brauzer cookie'si yoki IP+brauzer bo'yicha)."""

    KIND_HUMAN = "human"
    KIND_BOT = "bot"
    KIND_SCANNER = "scanner"
    KIND_UNKNOWN = "unknown"
    KIND_CHOICES = [
        (KIND_HUMAN, "Real odam"),
        (KIND_BOT, "Bot"),
        (KIND_SCANNER, "Skaner"),
        (KIND_UNKNOWN, "Aniqlanmagan"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kind = models.CharField("Turi", max_length=10, choices=KIND_CHOICES, default=KIND_UNKNOWN, db_index=True)
    bot_name = models.CharField("Bot nomi", max_length=60, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="visits")
    ip = models.GenericIPAddressField(null=True, blank=True, db_index=True)
    ua_hash = models.CharField(max_length=16, blank=True, db_index=True)
    user_agent = models.CharField(max_length=300, blank=True)
    device = models.CharField("Qurilma", max_length=10, blank=True)
    browser = models.CharField(max_length=30, blank=True)
    os = models.CharField(max_length=30, blank=True)
    source = models.CharField("Manba", max_length=40, blank=True, db_index=True)
    referrer = models.CharField(max_length=300, blank=True)
    utm_campaign = models.CharField(max_length=100, blank=True)
    landing_path = models.CharField("Kirgan sahifa", max_length=300, blank=True)
    last_path = models.CharField("Oxirgi sahifa", max_length=300, blank=True)
    pageviews = models.PositiveIntegerField(default=0)
    in_telegram = models.BooleanField("Telegram Mini App", default=False)

    # Voronka: nimalar qildi
    did_builder = models.BooleanField("Yaratishni ochdi", default=False)
    did_generate = models.BooleanField("Rezyume yaratdi", default=False)
    did_login = models.BooleanField("Kirdi", default=False)
    did_unlock = models.BooleanField("Ochdi (to'lov)", default=False)
    did_download = models.BooleanField("Yukladi", default=False)

    first_seen = models.DateTimeField(default=timezone.now, db_index=True)
    last_seen = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ("-last_seen",)
        verbose_name = "Tashrifchi"
        verbose_name_plural = "Tashrifchilar"
        indexes = [models.Index(fields=["first_seen", "kind"])]

    def __str__(self):
        return f"{self.get_kind_display()} · {self.ip or ''}"

    STAGES = [
        ("did_download", "PDF/Word yukladi"),
        ("did_unlock", "Ochdi, yuklamadi"),
        ("did_login", "Kirdi, to'lamadi"),
        ("did_generate", "Rezyume yaratdi, kirmadi"),
        ("did_builder", "Yaratish sahifasida to'xtadi"),
    ]

    @property
    def stage(self):
        for field, label in self.STAGES:
            if getattr(self, field):
                return label
        return "Faqat ko'rib ketdi"

    @property
    def duration(self):
        return self.last_seen - self.first_seen


class PageView(models.Model):
    visitor = models.ForeignKey(Visitor, on_delete=models.CASCADE, related_name="views")
    path = models.CharField(max_length=300)
    method = models.CharField(max_length=8, default="GET")
    status = models.PositiveSmallIntegerField(default=200)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "Sahifa ko'rish"
        verbose_name_plural = "Sahifa ko'rishlar"
