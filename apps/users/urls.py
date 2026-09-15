from django.urls import path

from . import views

urlpatterns = [
    path("login/", views.login_view, name="user_login"),
    path("login/status/", views.telegram_login_status, name="telegram_login_status"),
    path("login/tg/<str:token>/", views.telegram_login_complete, name="telegram_login_complete"),
    path("login/dev-confirm/", views.debug_confirm_login, name="debug_confirm_login"),
    path("tg/", views.telegram_webapp, name="telegram_webapp"),
    path("tg/auth/", views.telegram_webapp_auth, name="telegram_webapp_auth"),
    path("signup/", views.signup_view, name="user_signup"),
    path("logout/", views.logout_view, name="user_logout"),
    path("dashboard/", views.dashboard, name="user_dashboard"),
    path("payments/", views.payments_view, name="payments"),
    # Click/Payme ulanganda ishlatiladi
    path("payments/callback/<str:provider>/", views.payment_callback, name="payment_callback"),
    path("branding/", views.branding_settings, name="branding_settings"),
]
