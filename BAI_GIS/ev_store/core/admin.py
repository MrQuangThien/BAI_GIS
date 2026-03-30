
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
