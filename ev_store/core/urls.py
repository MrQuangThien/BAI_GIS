from django.urls import path
from .views import ban_do_tram_sac, get_nearest_tram  # ← thêm view mới

urlpatterns = [
    path("map/", ban_do_tram_sac, name='ban_do_tram_sac'),
    path("api/nearest-tram/", get_nearest_tram, name='get_nearest_tram'),  # ← endpoint AJAX
]