from django.urls import path

from . import broadcasts, marketing, views

app_name = "panel"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("tolovlar/", views.payments, name="payments"),
    path("tolovlar/<int:pk>/qaror/", views.payment_decide, name="payment_decide"),
    path("tolovlar/<int:pk>/chek/", views.receipt, name="receipt"),
    path("foydalanuvchilar/", views.users, name="users"),
    path("foydalanuvchilar/<int:user_id>/", views.user_detail, name="user_detail"),
    path("foydalanuvchilar/<int:user_id>/amal/", views.user_action, name="user_action"),
    path("cv/", views.cvs, name="cvs"),
    path("ai/", views.ai_usage, name="ai"),
    path("xatolar/", views.errors, name="errors"),
    path("xatolar/hal/", views.errors_resolve, name="errors_resolve"),
    path("faollik/", views.activity, name="activity"),
    path("tashriflar/", views.visits, name="visits"),
    path("tashriflar/<uuid:pk>/", views.visitor_detail, name="visitor_detail"),
    path("tashriflar/<uuid:pk>/blok/", views.visitor_block_ip, name="visitor_block_ip"),
    path("murojaatlar/", views.contact_messages, name="messages"),
    path("murojaatlar/<int:pk>/", views.message_resolve, name="message_resolve"),
    path("sozlamalar/", views.settings_view, name="settings"),
    path("aksiyalar/", marketing.promos, name="promos"),
    path("aksiyalar/<int:pk>/", marketing.promos, name="promo_edit"),
    path("aksiyalar/<int:pk>/ochirish/", marketing.promo_delete, name="promo_delete"),
    path("takliflar/", marketing.referrals, name="referrals"),
    path("xabarlar/", broadcasts.broadcasts, name="broadcasts"),
    path("xabarlar/<int:pk>/", broadcasts.broadcast_detail, name="broadcast_detail"),
    path("xabarlar/<int:pk>/tahrir/", broadcasts.broadcasts, name="broadcast_edit"),
    path("xabarlar/<int:pk>/amal/", broadcasts.broadcast_action, name="broadcast_action"),
    path("namunalar/", marketing.samples, name="samples"),
    path("namunalar/yangi/", marketing.sample_edit, name="sample_new"),
    path("namunalar/<int:pk>/", marketing.sample_edit, name="sample_edit"),
    path("namunalar/<int:pk>/ochirish/", marketing.sample_delete, name="sample_delete"),
    path("shablonlar/", marketing.templates_view, name="templates"),
    path("seo/", marketing.seo, name="seo"),
    path("seo/<int:pk>/", marketing.seo, name="seo_page"),
]
