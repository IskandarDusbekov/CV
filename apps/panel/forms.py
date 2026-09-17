from django import forms
from django.forms import modelformset_factory

from apps.core.models import SeoPage, SiteSettings
from apps.cv.models import ResumeSample, TemplateSetting
from apps.cv.services import TEMPLATE_META
from apps.users.models import Broadcast, PricingPlan, Promo


class StyledMixin:
    """Barcha maydonlarga panel uslubidagi `input` klassini beradi."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = (field.widget.attrs.get("class", "") + " input").strip()


SEO_FIELDS = ("seo_default_title", "seo_default_description", "google_site_verification", "yandex_verification",
              "google_analytics_id", "yandex_metrika_id")


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
        fields = ("title", "audience", "selected_users", "text", "attach_cv", "bonus_credits", "feedback_options", "button_site", "button_share")
        widgets = {
            "text": forms.Textarea(attrs={"rows": 7}),
            "selected_users": forms.Textarea(attrs={"rows": 3, "placeholder": "+998901234567\n@username\n15"}),
            "feedback_options": forms.Textarea(attrs={"rows": 3, "placeholder": "👍 Foydali bo'ldi\n👎 Kerak emas"}),
        }

    def clean(self):
        from apps.users.broadcast import CAPTION_LIMIT, TEXT_LIMIT, validate_text

        data = super().clean()
        text = data.get("text", "")
        if data.get("audience") == Broadcast.AUDIENCE_SELECTED and not data.get("selected_users", "").strip():
            self.add_error("selected_users", "Kimga yuborilishini yozing.")
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
