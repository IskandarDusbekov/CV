from django import template

from apps.core.stats import dashboard_stats

register = template.Library()


@register.inclusion_tag("admin/_dashboard_stats.html")
def admin_dashboard_stats():
    return dashboard_stats()
