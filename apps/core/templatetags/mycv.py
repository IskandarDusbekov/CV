from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()


@register.filter
def money(value):
    """19900.00 → "19 900" (bo'sh joy bilan ajratilgan, tiyinsiz)."""
    try:
        amount = int(Decimal(str(value)))
    except (InvalidOperation, TypeError, ValueError):
        return value
    return f"{amount:,}".replace(",", " ")
