from django.contrib import admin
from django.urls import include, path

from core.views import error, not_found, ping, slow

urlpatterns = [
    path("admin/", admin.site.urls),
    path("nocturne/", include("nocturne.urls")),
    path("ping/", ping),
    path("slow/", slow),
    path("error/", error),
    path("not-found/", not_found),
]
