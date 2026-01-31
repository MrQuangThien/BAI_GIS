from django.urls import path
from .views import ban_do_tram_sac

urlpatterns = [
    path("map/", ban_do_tram_sac),
]
