
from django.contrib import admin
from .models import *


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