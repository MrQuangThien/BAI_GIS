
from django.contrib import admin
from .models import *

<<<<<<< HEAD
admin.site.register(CuaHang)
admin.site.register(XeDien)
admin.site.register(TramSac)
admin.site.register(PhienSac)
=======
# 1. Giao diện bảng cho Trạm Sạc
@admin.register(TramSac)
class TramSacAdmin(admin.ModelAdmin):
    # Các cột hiển thị ra ngoài
    list_display = ('ten_tram', 'cong_suat', 'loai_sac', 'trang_thai')
    # Thanh tìm kiếm
    search_fields = ('ten_tram', 'dia_chi')
    # Bộ lọc bên tay phải
    list_filter = ('trang_thai', 'loai_sac')
    # Có thể click vào tên trạm hoặc công suất để sửa
    list_display_links = ('ten_tram', 'cong_suat')
# 2. Giao diện bảng cho Xe Điện
@admin.register(XeDien)
class XeDienAdmin(admin.ModelAdmin):
    list_display = ('id',) # Tạm thời chỉ hiện ID để không bị lỗi

# 3. Giao diện cho Cửa Hàng
@admin.register(CuaHang)
class CuaHangAdmin(admin.ModelAdmin):
    list_display = ('id',) 

# 4. Giao diện cho Phiên Sạc
@admin.register(PhienSac)
class PhienSacAdmin(admin.ModelAdmin):
    list_display = ('id',)
>>>>>>> DEV
