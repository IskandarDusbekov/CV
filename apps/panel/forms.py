from django import forms
from django.forms import modelformset_factory

from apps.core.models import SiteSettings
from apps.users.models import PricingPlan


class StyledMixin:
    """Barcha maydonlarga panel uslubidagi `input` klassini beradi."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = (field.widget.attrs.get("class", "") + " input").strip()


class SiteSettingsForm(StyledMixin, forms.ModelForm):
    class Meta:
        model = SiteSettings
        exclude = ("updated_at",)
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
