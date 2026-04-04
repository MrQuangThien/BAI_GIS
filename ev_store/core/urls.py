from django.urls import path
<<<<<<< HEAD
from .views import ban_do_tram_sac

urlpatterns = [
    path("map/", ban_do_tram_sac),
]
=======
from .views import ban_do_tram_sac, get_nearest_tram, admin_dashboard, quan_ly_tram_sac, them_tram_sac, xoa_tram_sac, sua_tram_sac
from django.contrib import admin  # <-- THÊM ĐÚNG DÒNG NÀY VÀO

admin.site.site_header = 'Hệ Thống Quản Trị EV Store'
admin.site.site_title = 'EV Store Admin'
admin.site.index_title = 'Bảng Điều Khiển'

urlpatterns = [
    path("map/", ban_do_tram_sac, name='ban_do_tram_sac'),
    path("api/nearest-tram/", get_nearest_tram, name='get_nearest_tram'),  # ← endpoint AJAX
    # ĐƯỜNG DẪN TỚI TRANG QUẢN TRỊ MỚI CỦA BẠN:
    path("dashboard/", admin_dashboard, name='admin_dashboard'),

    path("quan-ly-tram-sac/", quan_ly_tram_sac, name='quan_ly_tram_sac'),

    path("quan-ly-tram-sac/them/", them_tram_sac, name='them_tram_sac'),
    path("quan-ly-tram-sac/xoa/<int:tram_id>/", xoa_tram_sac, name='xoa_tram_sac'),

    path("quan-ly-tram-sac/sua/<int:tram_id>/", sua_tram_sac, name='sua_tram_sac'),

]
>>>>>>> DEV
