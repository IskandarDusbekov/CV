from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from apps.core import views as core_views

urlpatterns = [
    # Django admin manzili .env dagi ADMIN_URL dan (productionda taxmin qilinmaydigan qiling)
    path(settings.ADMIN_URL, admin.site.urls),

    # kundalik boshqaruv paneli (faqat staff)
    path("panel/", include("apps.panel.urls")),

    path("robots.txt", core_views.robots_txt, name="robots_txt"),
    path("healthz/", core_views.healthz, name="healthz"),

    path("", include("apps.core.urls")),
    path("users/", include("apps.users.urls")),
    path("cv/", include("apps.cv.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
