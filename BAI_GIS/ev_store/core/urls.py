from django.urls import path
from .views import ban_do_tram_sac, get_nearest_tram, admin_dashboard, quan_ly_tram_sac, sua_xe, them_tram_sac, them_xe, trang_chu, xoa_tram_sac, sua_tram_sac,danh_sach_xe, xoa_xe
from django.contrib import admin  # <-- THÊM ĐÚNG DÒNG NÀY VÀO
from django.contrib.auth import views as auth_views
from . import views

admin.site.site_header = 'Hệ Thống Quản Trị EV Store'
admin.site.site_title = 'EV Store Admin'
admin.site.index_title = 'Bảng Điều Khiển'

urlpatterns = [
    path("map/", ban_do_tram_sac, name='ban_do_tram_sac'),
    path("api/nearest-tram/", get_nearest_tram, name='get_nearest_tram'),  # ← endpoint AJAX
    # ĐƯỜNG DẪN TỚI TRANG QUẢN TRỊ MỚI CỦA BẠN:
    path("dashboard/", admin_dashboard, name='admin_dashboard'),
   
   path('', views.trang_chu, name='trang_chu'),
    # Đường dẫn có chứa ID của xe, ví dụ: /xe/5/
    path('xe/<int:xe_id>/', views.chi_tiet_xe, name='chi_tiet_xe'),

    path("quan-ly-tram-sac/", quan_ly_tram_sac, name='quan_ly_tram_sac'),

    path("quan-ly-tram-sac/them/", them_tram_sac, name='them_tram_sac'),
    path("quan-ly-tram-sac/xoa/<int:tram_id>/", xoa_tram_sac, name='xoa_tram_sac'),

    path("quan-ly-tram-sac/sua/<int:tram_id>/", sua_tram_sac, name='sua_tram_sac'),
    path('danh_sach_xe/', danh_sach_xe, name='danh_sach_xe'),
   path('danh_sach_xe/them/', them_xe, name='them_xe'),
    
    # Sửa xe (Cần pk để biết sửa xe nào)
    path('danh_sach_xe/sua/<int:pk>/', sua_xe, name='sua_xe'),
    
    # Xóa xe (Cần pk để biết xóa xe nào)
    path('danh_sach_xe/xoa/<int:pk>/', xoa_xe, name='xoa_xe'),
    path('login/', auth_views.LoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('users/', views.list_user, name='list_user'),
    path('users/add/', views.them_user, name='them_user'),
    path('users/edit/<int:id>/', views.sua_user, name='sua_user'),
    path('users/delete/<int:id>/', views.xoa_user, name='xoa_user'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.dang_ky_view, name='register'),

    path('tim-kiem/', views.tim_kiem, name='tim_kiem'),
    path('danh-muc/<str:loai_xe>/', views.danh_muc_xe, name='danh_muc_xe'),
    path('tao-don-hang/<int:xe_id>/', views.tao_don_hang, name='tao_don_hang'),

    path('quan-ly-don-hang/', views.danh_sach_don_hang, name='danh_sach_don_hang'),
    path('quan-ly-don-hang/<int:don_id>/', views.chi_tiet_don_hang, name='chi_tiet_don_hang'),
    path('quan-ly-don-hang/tao-don-tai-quay/', views.tao_don_hang_offline, name='tao_don_hang_offline'),
    path('san-pham/', views.danh_sach_san_pham, name='danh_sach_san_pham'),
    path('quan-ly-danh-muc/', views.quan_ly_danh_muc, name='quan_ly_danh_muc'),
]