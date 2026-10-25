from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("api/compile", views.api_compile, name="compile"),
    path("api/example/<str:name>", views.api_example, name="example"),
    path("reportes/<str:name>", views.download_report, name="report"),
]
