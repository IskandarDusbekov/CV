from django.urls import path

from . import views

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
]
