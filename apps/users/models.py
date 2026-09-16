from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

User = get_user_model()


class PricingPlan(models.Model):
    BILLING_PERIOD_ONE_TIME = "one_time"
    BILLING_PERIOD_MONTHLY = "monthly"
    BILLING_PERIOD_YEARLY = "yearly"

    BILLING_PERIOD_CHOICES = [
        (BILLING_PERIOD_ONE_TIME, "One Time"),
        (BILLING_PERIOD_MONTHLY, "Monthly"),
        (BILLING_PERIOD_YEARLY, "Yearly"),
    ]

    # "credits" — kredit paketi (1 kredit = 1 CV ochish); "account" — muddatli Pro obuna
    SCOPE_CREDITS = "credits"
    SCOPE_ACCOUNT = "account"
    SCOPE_CHOICES = [
        (SCOPE_CREDITS, "Kredit paketi"),
        (SCOPE_ACCOUNT, "Pro obuna"),
    ]

    code = models.SlugField("Kod", max_length=50, unique=True)
    scope = models.CharField("Turi", max_length=20, choices=SCOPE_CHOICES, default=SCOPE_CREDITS)
    name = models.CharField("Nomi", max_length=120)
    description = models.TextField("Tavsif", blank=True)
    credits = models.PositiveIntegerField("Kreditlar soni", default=0, help_text="Kredit paketi uchun: nechta CV ochiladi")
    is_featured = models.BooleanField("Tavsiya etiladi", default=False)
    price = models.DecimalField("Narx", max_digits=12, decimal_places=2, default=Decimal("0.00"))
    currency = models.CharField(max_length=10, default="UZS")
    billing_period = models.CharField(
        max_length=20,
        choices=BILLING_PERIOD_CHOICES,
        default=BILLING_PERIOD_ONE_TIME,
    )
    duration_days = models.PositiveIntegerField(default=30)
    is_active = models.BooleanField(default=True)
    is_free = models.BooleanField(default=False)
    includes_pdf_export = models.BooleanField(default=False)
    includes_docx_export = models.BooleanField(default=False)
    includes_premium_templates = models.BooleanField(default=False)
    template_codes = models.JSONField(default=list, blank=True)
    # Aniq chegaralar. Pro: davr (duration_days) ichida; Bitta CV: shu CV uchun.
    max_cvs = models.PositiveIntegerField(default=0, help_text="Pro: davr ichida yangi CV yaratish soni")
    max_tailorings = models.PositiveIntegerField(default=0, help_text="Vakansiyaga moslashtirish soni")
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("sort_order", "price", "id")
        verbose_name = "Tarif / paket"
        verbose_name_plural = "Tariflar va paketlar"

    def __str__(self):
        return f"{self.name} — {int(self.price):,} so'm".replace(",", " ")

    @property
    def is_credit_pack(self):
        return self.scope == self.SCOPE_CREDITS

    @property
    def price_per_credit(self):
        return int(self.price / self.credits) if self.is_credit_pack and self.credits else None


class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    phone = models.CharField(max_length=30, blank=True, db_index=True)
    telegram_id = models.BigIntegerField(null=True, blank=True, unique=True)
    telegram_username = models.CharField(max_length=100, blank=True)
    current_plan = models.ForeignKey(
        PricingPlan,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="users_on_plan",
    )
    premium_until = models.DateTimeField(null=True, blank=True)
    credits = models.PositiveIntegerField("Kreditlar", default=0, help_text="1 kredit = 1 CV ni ochish")
    free_pdf_used = models.PositiveIntegerField("Ishlatilgan bepul PDF", default=0)
    referral_code = models.CharField("Taklif kodi", max_length=16, unique=True, null=True, blank=True)
    email_verified = models.BooleanField(default=False)
    phone_verified = models.BooleanField(default=False)
    is_blocked = models.BooleanField("Bloklangan", default=False)
    block_reason = models.CharField("Bloklash sababi", max_length=255, blank=True)
    last_seen = models.DateTimeField("Oxirgi faollik", null=True, blank=True)
    last_ip = models.GenericIPAddressField("Oxirgi IP", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "Foydalanuvchi profili"
        verbose_name_plural = "Foydalanuvchilar"

    def __str__(self):
        return self.user.get_username()

    @property
    def has_active_premium(self):
        if self.premium_until and self.premium_until >= timezone.now():
            return True
        return self.subscriptions.filter(
            status=UserSubscription.STATUS_ACTIVE,
            plan__scope=PricingPlan.SCOPE_ACCOUNT,
        ).filter(models.Q(expires_at__isnull=True) | models.Q(expires_at__gte=timezone.now())).exists()


class UserSubscription(models.Model):
    STATUS_PENDING = "pending"
    STATUS_ACTIVE = "active"
    STATUS_EXPIRED = "expired"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_ACTIVE, "Active"),
        (STATUS_EXPIRED, "Expired"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="subscriptions",
    )
    profile = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE,
        related_name="subscriptions",
    )
    plan = models.ForeignKey(
        PricingPlan,
        on_delete=models.PROTECT,
        related_name="subscriptions",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    starts_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(null=True, blank=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.user} - {self.plan.name} - {self.status}"

    def activate(self, save=True):
        self.status = self.STATUS_ACTIVE
        self.activated_at = timezone.now()
        if not self.expires_at:
            self.expires_at = self.starts_at + timedelta(days=self.plan.duration_days)

        profile = self.profile
        profile.current_plan = self.plan
        profile.premium_until = self.expires_at

        if save:
            self.save(update_fields=["status", "activated_at", "expires_at", "updated_at"])
            profile.save(update_fields=["current_plan", "premium_until", "updated_at"])

    @property
    def is_active(self):
        return self.status == self.STATUS_ACTIVE and (not self.expires_at or self.expires_at >= timezone.now())


class PaymentTransaction(models.Model):
    PROVIDER_CLICK = "click"
    PROVIDER_PAYME = "payme"

    STATUS_CREATED = "created"
    STATUS_PENDING = "pending"
    STATUS_PAID = "paid"
    STATUS_FAILED = "failed"
    STATUS_CANCELLED = "cancelled"
    STATUS_REFUNDED = "refunded"

    PURPOSE_SUBSCRIPTION = "subscription"
    PURPOSE_CV_UNLOCK = "cv_unlock"
    PURPOSE_PREMIUM_TEMPLATE = "premium_template"
    PURPOSE_PDF_EXPORT = "pdf_export"

    PROVIDER_CHOICES = [
        (PROVIDER_CLICK, "Click"),
        (PROVIDER_PAYME, "Payme"),
    ]

    STATUS_CHOICES = [
        (STATUS_CREATED, "Created"),
        (STATUS_PENDING, "Pending"),
        (STATUS_PAID, "Paid"),
        (STATUS_FAILED, "Failed"),
        (STATUS_CANCELLED, "Cancelled"),
        (STATUS_REFUNDED, "Refunded"),
    ]

    PURPOSE_CHOICES = [
        (PURPOSE_SUBSCRIPTION, "Subscription"),
        (PURPOSE_CV_UNLOCK, "CV Unlock"),
        (PURPOSE_PREMIUM_TEMPLATE, "Premium Template"),
        (PURPOSE_PDF_EXPORT, "PDF Export"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="payment_transactions",
    )
    plan = models.ForeignKey(
        PricingPlan,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transactions",
    )
    subscription = models.ForeignKey(
        UserSubscription,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments",
    )
    cv = models.ForeignKey(
        "cv.CV",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payment_transactions",
    )
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES)
    purpose = models.CharField(max_length=30, choices=PURPOSE_CHOICES, default=PURPOSE_SUBSCRIPTION)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_CREATED)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=10, default="UZS")
    merchant_transaction_id = models.CharField(max_length=120, unique=True)
    provider_transaction_id = models.CharField(max_length=120, blank=True, null=True, unique=True)
    provider_payment_url = models.URLField(blank=True)
    description = models.CharField(max_length=255, blank=True)
    raw_request = models.JSONField(default=dict, blank=True)
    raw_response = models.JSONField(default=dict, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.merchant_transaction_id} - {self.provider} - {self.status}"

    def mark_paid(self, save=True):
        self.status = self.STATUS_PAID
        self.paid_at = timezone.now()

        if save:
            self.save(update_fields=["status", "paid_at", "raw_response", "updated_at"])


class CompanyBranding(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='company_branding',
    )
    name = models.CharField(max_length=100, verbose_name="Kompaniya nomi")
    tagline = models.CharField(max_length=200, blank=True, verbose_name="Qisqa tavsif")
    website = models.URLField(blank=True, verbose_name="Veb-sayt")
    logo = models.ImageField(upload_to='branding/', null=True, blank=True, verbose_name="Logo")
    footer_text = models.CharField(
        max_length=300,
        blank=True,
        help_text="Bo'sh qoldirsangiz avtomatik yaratiladi",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def get_footer_display(self):
        if self.footer_text:
            return self.footer_text
        parts = [self.name]
        if self.tagline:
            parts.append(self.tagline)
        if self.website:
            parts.append(self.website)
        return "  ·  ".join(filter(None, parts))

    def __str__(self):
        return f"{self.user.username} → {self.name}"

    class Meta:
        verbose_name = "Kompaniya brendingi"
        verbose_name_plural = "Kompaniya brendinglari"


class TelegramLoginToken(models.Model):
    """
    Telegram orqali parolsiz kirish.

    Sayt token yaratadi → foydalanuvchi botda Start bosadi → kontaktini ulashadi →
    bot tokenni "confirmed" qiladi → sayt (polling yoki bot yuborgan havola) login qiladi.
    """

    TTL_MINUTES = 10

    STATUS_PENDING = "pending"
    STATUS_CONFIRMED = "confirmed"
    STATUS_USED = "used"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Kutilmoqda"),
        (STATUS_CONFIRMED, "Tasdiqlandi"),
        (STATUS_USED, "Ishlatildi"),
    ]

    token = models.CharField(max_length=64, unique=True)
    session_key = models.CharField(max_length=64, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    telegram_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    telegram_username = models.CharField(max_length=100, blank=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField()

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.phone or '—'} · {self.status}"

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at


def receipt_upload_path(instance, filename):
    # Taxmin qilib bo'lmaydigan nom: cheklar faqat admin panel orqali ko'rsatiladi (nginx da /media/receipts/ yopiq)
    import os
    import uuid

    ext = os.path.splitext(filename)[1].lower()[:8] or ".jpg"
    return f"receipts/{timezone.now():%Y/%m}/{uuid.uuid4().hex}{ext}"


class PaymentRequest(models.Model):
    """Telegram bot orqali qo'lda to'lov: foydalanuvchi paket tanlaydi, kartaga o'tkazadi, chek yuboradi,
    admin saytda tasdiqlaydi yoki rad etadi."""

    STATUS_AWAITING = "awaiting_receipt"
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_AWAITING, "Chek kutilmoqda"),
        (STATUS_PENDING, "Tekshirilmoqda"),
        (STATUS_APPROVED, "Tasdiqlandi"),
        (STATUS_REJECTED, "Rad etildi"),
        (STATUS_CANCELLED, "Bekor qilindi"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="payment_requests",
                             verbose_name="Foydalanuvchi")
    plan = models.ForeignKey(PricingPlan, on_delete=models.PROTECT, related_name="payment_requests", verbose_name="Paket")
    amount = models.DecimalField("Summa", max_digits=12, decimal_places=2)
    status = models.CharField("Holat", max_length=20, choices=STATUS_CHOICES, default=STATUS_AWAITING, db_index=True)
    telegram_chat_id = models.BigIntegerField(null=True, blank=True)
    receipt = models.FileField("Chek", upload_to=receipt_upload_path, blank=True)
    receipt_caption = models.CharField("Chek izohi", max_length=500, blank=True)
    admin_note = models.CharField("Rad etish sababi / izoh", max_length=500, blank=True,
                                  help_text="Rad etsangiz foydalanuvchiga botda shu matn yuboriladi")
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name="reviewed_payments", verbose_name="Tekshirgan admin")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    receipt_at = models.DateTimeField("Chek yuborilgan", null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "To'lov (bot orqali)"
        verbose_name_plural = "To'lovlar (bot orqali)"

    def __str__(self):
        return f"#{self.pk} {self.user} · {self.plan.name} · {self.get_status_display()}"

    def approve(self, admin_user=None):
        """Kredit qo'shadi yoki Pro ni faollashtiradi. Qayta chaqirilsa ikki marta qo'shmaydi."""
        from django.db import transaction

        with transaction.atomic():
            locked = PaymentRequest.objects.select_for_update().get(pk=self.pk)
            if locked.status == self.STATUS_APPROVED:
                return False
            profile, _ = UserProfile.objects.select_for_update().get_or_create(user=locked.user)
            if locked.plan.is_credit_pack:
                profile.credits += locked.plan.credits
                profile.save(update_fields=["credits", "updated_at"])
            else:
                start = max(timezone.now(), profile.premium_until) if profile.premium_until else timezone.now()
                sub = UserSubscription.objects.create(
                    user=locked.user, profile=profile, plan=locked.plan, starts_at=timezone.now(),
                    expires_at=start + timedelta(days=locked.plan.duration_days),
                    notes=f"Bot to'lovi #{locked.pk}",
                )
                sub.activate(save=True)
            locked.status = self.STATUS_APPROVED
            locked.reviewed_by = admin_user
            locked.reviewed_at = timezone.now()
            locked.save(update_fields=["status", "reviewed_by", "reviewed_at"])
        self.refresh_from_db()
        return True

    def reject(self, admin_user=None, note=""):
        if self.status == self.STATUS_APPROVED:
            return False
        self.status = self.STATUS_REJECTED
        self.admin_note = note or self.admin_note
        self.reviewed_by = admin_user
        self.reviewed_at = timezone.now()
        self.save(update_fields=["status", "admin_note", "reviewed_by", "reviewed_at"])
        return True


@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)
        return

    UserProfile.objects.get_or_create(user=instance)


class Referral(models.Model):
    """Do'st taklifi: taklif qilingan odam ro'yxatdan o'tgandagina kredit beriladi (har bir odam uchun bir marta)."""

    inviter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="referrals_made")
    invitee = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="referral_received")
    inviter_credits = models.PositiveIntegerField(default=0)
    invitee_credits = models.PositiveIntegerField(default=0)
    via = models.CharField(max_length=20, blank=True)  # site / bot
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "Taklif"
        verbose_name_plural = "Takliflar"

    def __str__(self):
        return f"{self.inviter} → {self.invitee}"


class PendingReferral(models.Model):
    """Bot orqali kelgan taklif: raqam yuborilib akkaunt yaratilguncha saqlanadi."""

    telegram_id = models.BigIntegerField(unique=True)
    code = models.CharField(max_length=16)
    created_at = models.DateTimeField(auto_now_add=True)


class Promo(models.Model):
    """Aksiya: belgilangan sanalarda ro'yxatdan o'tgan (yoki kirgan) har bir foydalanuvchiga bonus kredit."""

    AUDIENCE_NEW = "new"
    AUDIENCE_ALL = "all"
    AUDIENCE_CHOICES = [
        (AUDIENCE_NEW, "Shu sanalarda ro'yxatdan o'tganlar"),
        (AUDIENCE_ALL, "Shu sanalarda kirgan barcha foydalanuvchilar"),
    ]

    name = models.CharField("Nomi", max_length=120, help_text="Masalan: Bitiruvchilar haftaligi")
    starts_at = models.DateTimeField("Boshlanishi")
    ends_at = models.DateTimeField("Tugashi")
    audience = models.CharField("Kimga", max_length=10, choices=AUDIENCE_CHOICES, default=AUDIENCE_NEW)
    bonus_credits = models.PositiveIntegerField("Bonus kredit", default=1, help_text="1 kredit = 1 rezyume PDF + Word, barcha shablonlar")
    banner_text = models.CharField("Saytdagi e'lon matni", max_length=200, blank=True,
                                   help_text="Masalan: 🎁 20-sentabrgacha ro'yxatdan o'tganlarga 2 ta rezyume tekin!")
    show_banner = models.BooleanField("E'lonni sayt tepasida ko'rsatish", default=True)
    is_active = models.BooleanField("Faol", default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-starts_at",)
        verbose_name = "Aksiya"
        verbose_name_plural = "Aksiyalar"

    def __str__(self):
        return self.name

    @property
    def is_running(self):
        now = timezone.now()
        return self.is_active and self.starts_at <= now <= self.ends_at


class PromoGrant(models.Model):
    promo = models.ForeignKey(Promo, on_delete=models.CASCADE, related_name="grants")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="promo_grants")
    credits = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [models.UniqueConstraint(fields=["promo", "user"], name="one_grant_per_promo_user")]
