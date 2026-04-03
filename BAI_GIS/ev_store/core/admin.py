
from django.contrib import admin
from .models import *

from django.contrib.auth.models import User, Group
from django.contrib.auth.admin import UserAdmin

@admin.register(TramSac)
class TramSacAdmin(admin.ModelAdmin):
    # Các cột hiển thị ra ngoài
    list_display = ('ten_tram', 'cong_suat', 'loai_sac', 'trang_thai')
    # Thanh tìm kiếm
    search_fields = ('ten_tram', 'dia_chi')
 
    list_filter = ('trang_thai', 'loai_sac')

    list_display_links = ('ten_tram', 'cong_suat')

@admin.register(XeDien)
class XeDienAdmin(admin.ModelAdmin):
    list_display = ('id',) 


@admin.register(CuaHang)
class CuaHangAdmin(admin.ModelAdmin):
    list_display = ('id',) 


@admin.register(PhienSac)
class PhienSacAdmin(admin.ModelAdmin):
    list_display = ('id',)

# CẤU HÌNH GIAO DIỆN QUẢN LÝ ĐƠN HÀNG
@admin.register(DonHang)
class DonHangAdmin(admin.ModelAdmin):
    # Các cột sẽ hiển thị ngoài danh sách
    list_display = ('id', 'ho_ten', 'so_dien_thoai', 'xe', 'loai_don', 'trang_thai', 'tong_tien', 'ngay_dat')
    
    # Cho phép Admin sửa nhanh trạng thái ngay ngoài danh sách mà không cần bấm vào trong
    list_editable = ('trang_thai',)
    
    # Bộ lọc ở cột bên phải
    list_filter = ('loai_don', 'trang_thai', 'ngay_dat')
    
    # Thanh tìm kiếm
    search_fields = ('ho_ten', 'so_dien_thoai', 'email', 'xe__ten_xe')
    
    # Chỉ đọc, không cho phép sửa ngày đặt hàng
    readonly_fields = ('ngay_dat',)
    
    # Số dòng trên mỗi trang
    list_per_page = 20

admin.site.register(DanhMuc)

# 1. Gỡ bỏ menu User và Group mặc định của Django cho đỡ rối mắt
admin.site.unregister(User)
admin.site.unregister(Group) 

# 2. Đăng ký menu Quản lý Nhân Viên
@admin.register(NhanVien)
class NhanVienAdmin(UserAdmin):
    # Ghi đè hàm lấy dữ liệu: Chỉ lấy những người có quyền Staff
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.filter(is_staff=True)
        
    # (Tùy chọn) Đặt mặc định khi tạo mới Nhân viên thì tự auto tick is_staff
    def save_model(self, request, obj, form, change):
        if not obj.pk: # Nếu là tạo mới
            obj.is_staff = True
        super().save_model(request, obj, form, change)

# 3. Đăng ký menu Quản lý Khách Hàng
@admin.register(KhachHang)
class KhachHangAdmin(UserAdmin):
    # Ghi đè hàm lấy dữ liệu: Chỉ lấy những người KHÔNG có quyền Staff
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.filter(is_staff=False)
        
    # Bỏ bớt các quyền phân quyền phức tạp đi vì khách hàng không cần
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Thông tin cá nhân', {'fields': ('first_name', 'last_name', 'email')}),
        ('Ngày tháng', {'fields': ('date_joined', 'last_login')}),
    )