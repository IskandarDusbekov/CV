from django.urls import path
from . import views

# CV manzillarida ketma-ket raqam emas, UUID: /cv/preview/3f2c…/ — boshqa CV larni taxmin qilib bo'lmaydi
urlpatterns = [
    path('templates/', views.templates_showcase, name='templates_showcase'),
    path('template-preview/<str:code>/', views.template_preview, name='template_preview'),
    path('namuna/', views.example, name='cv_example'),
    path('builder/', views.builder, name='cv_builder'),
    path('generate/', views.generate_cv, name='generate_cv'),
    path('preview/<uuid:cv_id>/', views.preview, name='cv_preview'),
    path('unlock/<uuid:cv_id>/', views.unlock_with_credit, name='unlock_cv'),
    path('tailor/<uuid:cv_id>/', views.tailor_cv, name='tailor_cv'),
    path('details/<uuid:cv_id>/', views.save_details, name='cv_details'),
    path('share/<str:token>/', views.shared_preview, name='shared_cv_preview'),
    path('template/<uuid:cv_id>/change/', views.change_template, name='change_cv_template'),
    path('share/<uuid:cv_id>/toggle/', views.toggle_share_link, name='toggle_cv_share_link'),
    path('download/<uuid:cv_id>/', views.download_pdf, name='download_pdf'),
    path('download/<uuid:cv_id>/inline/', views.download_pdf, {'inline': True}, name='view_pdf'),
    path('download/<uuid:cv_id>/docx/', views.download_docx, name='download_docx'),
    path('download/<uuid:cv_id>/<str:fmt>/link/', views.download_link, name='download_link'),
    path('download/<uuid:cv_id>/<str:fmt>/telegram/', views.send_to_telegram, name='send_to_telegram'),
    path('dl/<str:token>/', views.signed_download, name='signed_download'),
    path('photo/<uuid:cv_id>/upload/', views.upload_photo, name='upload_cv_photo'),
    path('photo/<uuid:cv_id>/remove/', views.remove_photo, name='remove_cv_photo'),
]
