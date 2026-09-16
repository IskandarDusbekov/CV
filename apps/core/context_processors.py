def site(request):
    from .models import Page, SeoPage, SiteSettings

    settings_obj = SiteSettings.load()
    return {
        "site": settings_obj,
        "TELEGRAM_BOT_USERNAME": settings_obj.effective_bot_username,
        "FREE_CV_LIMIT": settings_obj.free_cv_limit,
        "FREE_TAILOR_LIMIT": settings_obj.free_tailor_limit,
        "footer_pages": Page.objects.filter(is_published=True, show_in_footer=True).only("slug", "title"),
        "seo_page": SeoPage.lookup(request.path),
        "canonical_url": f"{request.scheme}://{request.get_host()}{request.path}",
        "active_promo": _banner_promo(),
    }


def _banner_promo():
    from django.core.cache import cache

    from apps.users.growth import running_promos

    promo = cache.get("banner_promo", "none")
    if promo == "none":
        promo = running_promos().filter(show_banner=True).exclude(banner_text="").order_by("-starts_at").first()
        cache.set("banner_promo", promo, 60)
    return promo
