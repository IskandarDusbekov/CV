from django.urls import path

from apps.cv import editor as cv_editor

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("pricing/", views.pricing, name="pricing"),
    path("aloqa/", views.contact, name="contact"),
    path("qollanma/", views.guide, name="guide"),
    path("qollanma/<slug:slug>/", views.guide_question, name="guide_question"),
    path("namunalar/", cv_editor.samples_list, name="samples"),
    path("namunalar/<slug:slug>/", cv_editor.sample_detail, name="sample_detail"),
    path("namunalar/<slug:slug>/boshlash/", cv_editor.sample_use, name="sample_use"),
    path("biz-haqimizda/", views.page, {"slug": "biz-haqimizda"}, name="about"),
    path("sahifa/<slug:slug>/", views.page, name="page"),
]
