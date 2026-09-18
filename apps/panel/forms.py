import re

from django import forms
from django.forms import modelformset_factory

from apps.core.models import SeoPage, SiteSettings
from apps.cv.models import LuckyGift, ResumeSample, TemplateSetting
from apps.cv.services import TEMPLATE_META
from apps.users.models import Broadcast, PricingPlan, Promo


class StyledMixin:
    """Barcha maydonlarga panel uslubidagi `input` klassini beradi."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = (field.widget.attrs.get("class", "") + " input").strip()


SEO_FIELDS = ("seo_default_title", "seo_default_description", "google_site_verification", "google_verification_file",
              "yandex_verification", "google_analytics_id", "yandex_metrika_id")


class SiteSettingsForm(StyledMixin, forms.ModelForm):
    class Meta:
        model = SiteSettings
        exclude = ("updated_at", *SEO_FIELDS)
        widgets = {"payment_instructions": forms.Textarea(attrs={"rows": 3})}


class PlanForm(StyledMixin, forms.ModelForm):
    class Meta:
        model = PricingPlan
        fields = ("name", "scope", "price", "credits", "duration_days", "max_cvs", "max_tailorings", "is_featured", "is_active", "sort_order")


PlanFormSet = modelformset_factory(PricingPlan, form=PlanForm, extra=0, can_delete=False)


class NewPlanForm(StyledMixin, forms.ModelForm):
    class Meta:
        model = PricingPlan
        fields = ("name", "code", "scope", "price", "credits", "duration_days", "max_cvs", "max_tailorings")
        help_texts = {"code": "Lotin harflari, masalan: kredit-5"}


class SeoSettingsForm(StyledMixin, forms.ModelForm):
    class Meta:
        model = SiteSettings
        fields = SEO_FIELDS
        widgets = {"seo_default_description": forms.Textarea(attrs={"rows": 2})}

    def clean_google_site_verification(self):
        # <meta name="google-site-verification" content="ABC" /> qo'yilsa ham faqat ABC ni olamiz
        value = self.cleaned_data["google_site_verification"].strip()
        match = re.search(r'content\s*=\s*["\']([^"\']+)["\']', value)
        return match.group(1).strip() if match else value

    def clean_google_verification_file(self):
        # «google-site-verification: google123.html», to'liq havola yoki fayl nomi — hammasidan fayl nomini ajratamiz
        value = self.cleaned_data["google_verification_file"].strip()
        if not value:
            return ""
        match = re.search(r"(google[0-9a-zA-Z_-]+\.html)", value)
        if not match:
            raise forms.ValidationError("Google bergan fayl nomini yozing, masalan: google1a2b3c4d5e6f.html")
        return match.group(1)


class SeoPageForm(StyledMixin, forms.ModelForm):
    class Meta:
        model = SeoPage
        fields = ("path", "title", "description", "noindex")


class PromoForm(StyledMixin, forms.ModelForm):
    starts_at = forms.DateTimeField(label="Boshlanishi", widget=forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
                                    input_formats=["%Y-%m-%dT%H:%M"])
    ends_at = forms.DateTimeField(label="Tugashi", widget=forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
                                  input_formats=["%Y-%m-%dT%H:%M"])

    class Meta:
        model = Promo
        fields = ("name", "starts_at", "ends_at", "audience", "bonus_credits", "banner_text", "show_banner", "is_active")

    def clean(self):
        data = super().clean()
        if data.get("starts_at") and data.get("ends_at") and data["ends_at"] <= data["starts_at"]:
            self.add_error("ends_at", "Tugash sanasi boshlanishidan keyin bo'lishi kerak.")
        return data


class BroadcastForm(StyledMixin, forms.ModelForm):
    class Meta:
        model = Broadcast
        fields = ("title", "audience", "selected_users", "selected_cvs", "text", "attach_cv", "bonus_credits", "feedback_options",
                  "button_site", "button_share")
        widgets = {
            "text": forms.Textarea(attrs={"rows": 7}),
            # Ikkalasini ham panel tanlagichi (qidirish → tanlash → rezyume) to'ldiradi
            "selected_users": forms.HiddenInput(),
            "selected_cvs": forms.HiddenInput(),
            "feedback_options": forms.Textarea(attrs={"rows": 3, "placeholder": "👍 Foydali bo'ldi\n👎 Kerak emas"}),
        }

    def clean_selected_cvs(self):
        """{"<user_id>": <cv_id>} — faqat shu foydalanuvchining o'z rezyumesi qoladi."""
        from apps.cv.models import CV

        raw = self.cleaned_data.get("selected_cvs") or {}
        pairs = {}
        if isinstance(raw, dict):
            for user_id, cv_id in raw.items():
                if str(user_id).isdigit() and str(cv_id).isdigit():
                    pairs[str(user_id)] = int(cv_id)
        owned = set(CV.objects.filter(pk__in=pairs.values()).values_list("pk", "user_id"))
        return {uid: cv for uid, cv in pairs.items() if (cv, int(uid)) in owned}

    def clean(self):
        from apps.users.broadcast import CAPTION_LIMIT, TEXT_LIMIT, validate_text

        data = super().clean()
        text = data.get("text", "")
        if data.get("audience") == Broadcast.AUDIENCE_SELECTED and not data.get("selected_users", "").strip():
            self.add_error("audience", "Kimga yuborilishini tanlang: pastdagi qidiruvdan foydalanuvchi qo'shing.")
        limit = CAPTION_LIMIT if data.get("attach_cv") else TEXT_LIMIT
        if len(text) > limit:
            self.add_error("text", f"Matn {limit} belgidan oshmasin (hozir {len(text)}). Fayl bilan yuborilganda Telegram izohi qisqa bo'ladi.")
        error = validate_text(text)
        if error:
            self.add_error("text", error)
        if (data.get("bonus_credits") or 0) > 10:
            self.add_error("bonus_credits", "Bir xabar bilan 10 kreditdan ko'p berib bo'lmaydi.")
        if len([line for line in data.get("feedback_options", "").splitlines() if line.strip()]) > Broadcast.MAX_OPTIONS:
            self.add_error("feedback_options", f"Ko'pi bilan {Broadcast.MAX_OPTIONS} ta tugma.")
        return data


class LuckyGiftForm(StyledMixin, forms.ModelForm):
    class Meta:
        model = LuckyGift
        fields = ("is_active", "audience", "new_user_days", "daily_limit", "title", "text", "reactions", "thanks_text")
        widgets = {"text": forms.Textarea(attrs={"rows": 5}), "reactions": forms.Textarea(attrs={"rows": 4})}

    def clean_reactions(self):
        lines = [line.strip() for line in self.cleaned_data["reactions"].splitlines() if line.strip()]
        if len(lines) > LuckyGift.MAX_REACTIONS:
            raise forms.ValidationError(f"Ko'pi bilan {LuckyGift.MAX_REACTIONS} ta tugma.")
        return "\n".join(lines)


class TemplateSettingForm(StyledMixin, forms.ModelForm):
    class Meta:
        model = TemplateSetting
        fields = ("is_pro", "is_active", "sort_order")


TemplateSettingFormSet = modelformset_factory(TemplateSetting, form=TemplateSettingForm, extra=0, can_delete=False)


class SampleForm(StyledMixin, forms.ModelForm):
    template_code = forms.ChoiceField(label="Shablon", choices=[(c, m["label"]) for c, m in TEMPLATE_META.items()])
    cv_json = forms.JSONField(label="Rezyume ma'lumotlari (JSON)", widget=forms.Textarea(attrs={"rows": 18, "spellcheck": "false"}),
                              help_text="full_name, job_title, phone, email, location, summary, skills[], languages[], experience[], education[], projects[]")

    class Meta:
        model = ResumeSample
        fields = ("profession", "slug", "category", "template_code", "seo_title", "seo_description", "intro", "is_published", "sort_order", "cv_json")
        widgets = {"intro": forms.Textarea(attrs={"rows": 5}), "seo_description": forms.Textarea(attrs={"rows": 2})}

    def clean_cv_json(self):
        data = self.cleaned_data["cv_json"]
        if not isinstance(data, dict) or not str(data.get("full_name", "")).strip():
            raise forms.ValidationError("JSON obyekt bo'lishi va full_name bo'lishi kerak.")
        return data
