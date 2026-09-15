def site(request):
    from .models import Page, SiteSettings

    settings_obj = SiteSettings.load()
    return {
        "site": settings_obj,
        "TELEGRAM_BOT_USERNAME": settings_obj.effective_bot_username,
        "FREE_CV_LIMIT": settings_obj.free_cv_limit,
        "FREE_TAILOR_LIMIT": settings_obj.free_tailor_limit,
        "footer_pages": Page.objects.filter(is_published=True, show_in_footer=True).only("slug", "title"),
    }
