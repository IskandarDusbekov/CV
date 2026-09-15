from django.db import models
from django.contrib.auth import get_user_model
import secrets
import uuid

User = get_user_model()


class CV(models.Model):
    TEMPLATE_CHOICES = [
        ('ats_modern', 'ATS Zamonaviy'),
        ('ats',       'ATS Standart'),
        ('classic',   'Klassik'),
        ('modern',    'Zamonaviy'),
        ('creative',  'Kreativ'),
        ('executive', 'Executive'),
        ('minimal',   'Minimal'),
        ('dark',      'Dark Mode'),
        ('elegant',   'Elegant'),
        ('free_classic',   'Free Classic (legacy)'),
        ('premium_modern', 'Premium Modern (legacy)'),
    ]

    # URL larda ketma-ket raqam o'rniga taxmin qilib bo'lmaydigan UUID ishlatiladi
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    raw_input_text = models.TextField()
    target_job = models.CharField(max_length=255, blank=True)
    cv_json = models.JSONField()
    selected_template = models.CharField(max_length=50, choices=TEMPLATE_CHOICES, default='classic')
    photo = models.ImageField(upload_to='cv_photos/', blank=True, null=True)
    share_token = models.CharField(max_length=64, unique=True, blank=True, null=True)
    is_public_share_enabled = models.BooleanField(default=False)
    # Bir martalik to'lov bilan ochilgan CV: barcha shablonlar, PDF + Word, watermark'siz
    is_unlocked = models.BooleanField(default=False)
    unlocked_at = models.DateTimeField(null=True, blank=True)
    # Vakansiyaga moslashtirilgan nusxa: asl CV, e'lon matni va AI hisoboti
    parent = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="tailored_versions")
    job_description = models.TextField(blank=True)
    tailor_report = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "CV"
        verbose_name_plural = "CV lar"

    def __str__(self):
        full_name = self.cv_json.get('full_name', 'No name') if self.cv_json else 'No name'
        return f"{full_name} - {self.id}"

    @property
    def root(self):
        return self.parent if self.parent_id else self

    def unlock(self, save=True):
        from django.utils import timezone

        self.is_unlocked = True
        self.unlocked_at = timezone.now()
        if save:
            self.save(update_fields=["is_unlocked", "unlocked_at", "updated_at"])

    @property
    def is_tailored(self):
        return bool(self.parent_id)

    def ensure_share_token(self, save=True):
        if not self.share_token:
            self.share_token = secrets.token_urlsafe(24)
            if save:
                self.save(update_fields=["share_token", "updated_at"])
        return self.share_token


class AIUsage(models.Model):
    """Har bir AI chaqiruvi — bepul/Pro limitlarini hisoblash uchun."""

    KIND_GENERATE = "generate"
    KIND_TAILOR = "tailor"
    KIND_CHOICES = [(KIND_GENERATE, "CV yaratish"), (KIND_TAILOR, "Vakansiyaga moslashtirish")]

    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name="ai_usages")
    session_key = models.CharField(max_length=64, blank=True, db_index=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    cv = models.ForeignKey(CV, on_delete=models.SET_NULL, null=True, blank=True, related_name="ai_usages")
    model = models.CharField(max_length=100, blank=True)
    prompt_tokens = models.PositiveIntegerField(default=0)
    completion_tokens = models.PositiveIntegerField(default=0)
    cost_usd = models.DecimalField("Narx, $", max_digits=10, decimal_places=6, default=0)
    duration_ms = models.PositiveIntegerField(default=0)
    success = models.BooleanField(default=True, db_index=True)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "AI so'rovi"
        verbose_name_plural = "AI so'rovlari"

    def __str__(self):
        return f"{self.kind} · {self.user or self.ip or self.session_key[:8]}"
