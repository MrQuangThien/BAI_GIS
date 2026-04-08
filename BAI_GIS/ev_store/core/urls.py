from django.urls import path
from django.contrib import admin
from django.contrib.auth import views as auth_views

# Gom tất cả các hàm view lại cho gọn gàng
from .views import (
    ban_do_tram_sac, get_nearest_tram, admin_dashboard, quan_ly_tram_sac, 
    sua_xe, them_tram_sac, them_xe, trang_chu, xoa_tram_sac, sua_tram_sac, 
    danh_sach_xe, xoa_xe, gui_feedback
)
from . import views

admin.site.site_header = 'Hệ Thống Quản Trị EV Store'
admin.site.site_title = 'EV Store Admin'
admin.site.index_title = 'Bảng Điều Khiển'

urlpatterns = [
    # ==================== TRANG CHỦ & BẢN ĐỒ ====================
    path('', views.trang_chu, name='trang_chu'),
    path('gioi-thieu/', views.gioi_thieu, name='gioi_thieu'),
    path('chi-nhanh/<int:pk>/', views.chi_tiet_cua_hang, name='chi_tiet_cua_hang'),
    path('chi-nhanh/<int:pk>/san-pham/', views.san_pham_tai_chi_nhanh, name='san_pham_tai_chi_nhanh'),
    path("map/", ban_do_tram_sac, name='ban_do_tram_sac'),
    path("api/nearest-tram/", get_nearest_tram, name='get_nearest_tram'),  # Endpoint AJAX
    # Thêm 2 dòng API này vào để phục vụ cho Bản đồ GIS
    path('api/trams/', views.tram_api, name='tram_api'),
    path('api/cua-hang/', views.cua_hang_api, name='cua_hang_api'),

    # ==================== SẢN PHẨM & TÌM KIẾM ====================
    path('san-pham/', views.danh_sach_san_pham, name='danh_sach_san_pham'),
    path('xe/<int:xe_id>/', views.chi_tiet_xe, name='chi_tiet_xe'),
    path('tim-kiem/', views.tim_kiem, name='tim_kiem'),
    path('danh-muc/<str:loai_xe>/', views.danh_muc_xe, name='danh_muc_xe'),

    # ==================== XÁC THỰC TÀI KHOẢN ====================
    path('login/', auth_views.LoginView.as_view(), name='login'),
    path('logout/', views.logout_view, name='logout'), # Sử dụng view tùy chỉnh của bạn
    path('register/', views.dang_ky_view, name='register'),
    path('xac-thuc-otp/', views.xac_thuc_otp, name='xac_thuc_otp'), 
    path('tai-khoan/', views.tai_khoan, name='tai_khoan'),
    path('tai-khoan/don-hang/<int:don_hang_id>/', views.chi_tiet_don_hang_khach, name='chi_tiet_don_hang_khach'),
    path('profile/', views.profile, name='profile'),

    # ==================== ĐẶT HÀNG & FEEDBACK ====================
    path('tao-don-hang/<int:xe_id>/', views.tao_don_hang, name='tao_don_hang'),
    path('feedback/', views.gui_feedback, name='gui_feedback'),

    # ============================================================
    #                 KHU VỰC QUẢN TRỊ (ADMIN DASHBOARD)
    # ============================================================
    path("dashboard/", admin_dashboard, name='admin_dashboard'),

    # Quản lý Xe
    path('danh_sach_xe/', danh_sach_xe, name='danh_sach_xe'),
    path('danh_sach_xe/them/', them_xe, name='them_xe'),
    path('danh_sach_xe/sua/<int:pk>/', sua_xe, name='sua_xe'),
    path('danh_sach_xe/xoa/<int:pk>/', xoa_xe, name='xoa_xe'),

    # Quản lý Trạm Sạc
    path("quan-ly-tram-sac/", quan_ly_tram_sac, name='quan_ly_tram_sac'),
    path("quan-ly-tram-sac/them/", them_tram_sac, name='them_tram_sac'),
    path("quan-ly-tram-sac/sua/<int:tram_id>/", sua_tram_sac, name='sua_tram_sac'),
    path("quan-ly-tram-sac/xoa/<int:tram_id>/", xoa_tram_sac, name='xoa_tram_sac'),

    # Quản lý Tài Khoản (Đã tách Khách & Nhân viên)
    path('users/', views.list_user, name='list_user'),
    path('users/add/', views.them_user, name='them_user'),
    path('users/edit/<int:id>/', views.sua_user, name='sua_user'),
    path('users/delete/<int:id>/', views.xoa_user, name='xoa_user'),
    path('quan-ly-khach-hang/', views.ql_khach_hang, name='ql_khach_hang'),
    path('quan-ly-nhan-vien/', views.ql_nhan_vien, name='ql_nhan_vien'),

    # Quản lý Đơn Hàng
    path('quan-ly-don-hang/', views.danh_sach_don_hang, name='danh_sach_don_hang'),
    path('quan-ly-don-hang/<int:don_id>/', views.chi_tiet_don_hang, name='chi_tiet_don_hang'),
    path('quan-ly-don-hang/tao-don-tai-quay/', views.tao_don_hang_offline, name='tao_don_hang_offline'),


    # Quản lý Danh Mục
    path('quan-ly-danh-muc/', views.quan_ly_danh_muc, name='quan_ly_danh_muc'),
    path('category/them/', views.them_danh_muc, name='them_danh_muc'),
    path('category/sua/<int:pk>/', views.sua_danh_muc, name='sua_danh_muc'),
    path('category/xoa/<int:pk>/', views.xoa_danh_muc, name='xoa_danh_muc'),

    # Quản lý Cửa Hàng
    path('cua-hang/', views.quan_ly_cua_hang, name='quan_ly_cua_hang'),
    path('cua-hang/them/', views.them_cua_hang, name='them_cua_hang'),
    path('cua-hang/sua/<int:pk>/', views.sua_cua_hang, name='sua_cua_hang'),
    path('cua-hang/xoa/<int:pk>/', views.xoa_cua_hang, name='xoa_cua_hang'),

    # Quản lý Kho Hàng
    # 1. Trang Lịch sử nhập kho (Mới thêm)
    path('quan-ly-phieu-nhap/', views.quan_ly_phieu_nhap, name='quan_ly_phieu_nhap'),
    path('them-phieu-nhap/', views.them_kho, name='them_kho'),
    path('tai-file-mau-excel/', views.tai_file_mau_excel, name='tai_file_mau_excel'),
    
    # 2. Trang Báo cáo tồn kho (Đã có sẵn, đổi tên path cho chuẩn)
    path('bao-cao-ton-kho/', views.quan_ly_ton_kho, name='quan_ly_ton_kho'),

    # Quản lý Phiên Sạc
    path('phien-sac/', views.danh_sach_phien_sac, name='danh_sach_phien_sac'),
    path('phien-sac/bat-dau/<int:tram_id>/', views.bat_dau_sac, name='bat_dau_sac'),

    # Quản lý Feedback
    path('admin/feedback/', views.quan_ly_feedback, name='quan_ly_feedback'),
    
    path('feedback/xoa/<int:feedback_id>/', views.xoa_feedback, name='xoa_feedback'),

    # API Lưu Phiên Sạc
    path('api/ket-thuc-sac/', views.ket_thuc_sac_api, name='ket_thuc_sac_api'),
    path('tram_sac/lich-su-sac/', views.lich_su_sac, name='lich_su_sac'),
    path('users/user_sac/', views.lich_su_sac_khach_hang, name='user_sac'),
    path('tim-kiem/', views.tim_kiem, name='tim_kiem'),
]