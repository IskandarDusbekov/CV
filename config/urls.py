from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from apps.core import views as core_views
from apps.core.analytics import human_ping
from apps.users.growth import referral_redirect

urlpatterns = [
    # Django admin manzili .env dagi ADMIN_URL dan (productionda taxmin qilinmaydigan qiling)
    path(settings.ADMIN_URL, admin.site.urls),

    # kundalik boshqaruv paneli (faqat staff)
    path("panel/", include("apps.panel.urls")),

    path("robots.txt", core_views.robots_txt, name="robots_txt"),
    path("sitemap.xml", core_views.sitemap_xml, name="sitemap"),
    path("healthz/", core_views.healthz, name="healthz"),
    path("t/p/", human_ping, name="human_ping"),
    path("r/<str:code>/", referral_redirect, name="referral_redirect"),

    path("", include("apps.core.urls")),
    path("users/", include("apps.users.urls")),
    path("cv/", include("apps.cv.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
