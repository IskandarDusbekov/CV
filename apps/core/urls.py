from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("pricing/", views.pricing, name="pricing"),
    path("aloqa/", views.contact, name="contact"),
    path("biz-haqimizda/", views.page, {"slug": "biz-haqimizda"}, name="about"),
    path("sahifa/<slug:slug>/", views.page, name="page"),
]
