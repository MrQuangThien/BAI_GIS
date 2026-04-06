from django.db import models
from django import forms
from django.contrib.auth.models import User
from django.utils import timezone 
from ckeditor.fields import RichTextField
# ==========================================
#                  MODELS
# ==========================================

class CuaHang(models.Model):
    ten_cua_hang = models.CharField(max_length=255)
    dia_chi = models.TextField()
    bai_gioi_thieu = RichTextField(blank=True, null=True)
    so_dien_thoai = models.CharField(max_length=20)
    trang_thai = models.BooleanField(default=True)

    lat = models.FloatField(null=True, blank=True)
    lon = models.FloatField(null=True, blank=True)
    hinh_anh = models.ImageField(upload_to='cua_hang_images/', null=True, blank=True)

    def __str__(self):
        return self.ten_cua_hang
    
class DanhMuc(models.Model):
    ten_danh_muc = models.CharField(max_length=255, verbose_name="Tên danh mục")
    
    def __str__(self):
        return self.ten_danh_muc

class XeDien(models.Model):
    ten_xe = models.CharField(max_length=255)
    hang_san_xuat = models.CharField(max_length=255)
    dung_luong_pin = models.IntegerField()
    tam_di_chuyen = models.IntegerField()
    gia = models.BigIntegerField()
    trang_thai = models.BooleanField(default=True)
    cua_hang = models.ForeignKey(CuaHang, on_delete=models.CASCADE)
    danh_muc = models.ForeignKey(DanhMuc, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Danh mục sản phẩm")
    hinh_anh = models.ImageField(upload_to='xe_dien_images/', null=True, blank=True)
    noi_bat = models.BooleanField(default=False, verbose_name="Sản phẩm nổi bật")
    sap_ve = models.BooleanField(default=False, verbose_name="Sản phẩm sắp về")
    mo_ta = RichTextField(config_name='mini', blank=True, null=True, verbose_name="Mô tả chi tiết")
    
    anh_phu_1 = models.ImageField(upload_to='xe_dien_images/', blank=True, null=True, verbose_name="Ảnh phụ 1")
    anh_phu_2 = models.ImageField(upload_to='xe_dien_images/', blank=True, null=True, verbose_name="Ảnh phụ 2")
    anh_phu_3 = models.ImageField(upload_to='xe_dien_images/', blank=True, null=True, verbose_name="Ảnh phụ 3")

    def __str__(self):
        return self.ten_xe

class TramSac(models.Model):
    ten_tram = models.CharField(max_length=255)
    dia_chi = models.TextField()
    cong_suat = models.IntegerField()
    loai_sac = models.CharField(max_length=100)
    trang_thai = models.BooleanField(default=True)
    lat = models.FloatField()
    lon = models.FloatField()
    hinh_anh = models.ImageField(upload_to='tram_sac_images/', null=True, blank=True)

    def __str__(self):
        return self.ten_tram

# PHIÊN SẠC
class PhienSac(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    tram_sac = models.ForeignKey(TramSac, on_delete=models.CASCADE)
    thoi_gian_bat_dau = models.DateTimeField()
    thoi_gian_ket_thuc = models.DateTimeField(null=True, blank=True)
    dien_nang_tieu_thu = models.FloatField(default=0)
    tong_tien = models.DecimalField(max_digits=10, decimal_places=0, default=0, verbose_name="Tổng tiền (VNĐ)")
    trang_thai = models.CharField(
        max_length=20,
        choices=[
            ('Dang sac', 'Đang sạc'),
            ('Hoan thanh', 'Hoàn thành'),
        ],
        default='Dang sac'
    )

    def __str__(self):
        return f"{self.user} - {self.tram_sac.ten_tram}"

    @property
    def khoang_thoi_gian_sac(self):
        if not self.thoi_gian_bat_dau:
            return "Chưa bắt đầu"
        end_time = self.thoi_gian_ket_thuc if self.thoi_gian_ket_thuc else timezone.now()
        thoigian = end_time - self.thoi_gian_bat_dau
        total_seconds = int(thoigian.total_seconds())
        if total_seconds < 0:
            return "Vừa bắt đầu"
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours > 0:
            return f"{hours} giờ {minutes} phút"
        return f"{minutes} phút"

class DonHang(models.Model):
    LOAI_DON_CHOICES = [
        ('A', 'Đặt giữ xe online'),
        ('B', 'Đặt cọc online'),
        ('C', 'Mua online hoàn toàn'),
        ('D', 'Mua trực tiếp - Trả thẳng 100%'),
        ('E', 'Mua trực tiếp - Trả góp'),
    ]
    TRANG_THAI_CHOICES = [
        ('Pending', 'Pending (Đang chờ)'),
        ('Deposit Paid', 'Deposit Paid (Đã đặt cọc)'),
        ('Paid', 'Paid (Đã thanh toán)'),
        ('Cancelled', 'Đã hủy'),
    ]
    xe = models.ForeignKey(XeDien, on_delete=models.CASCADE)
    
    # --- ĐÃ CẬP NHẬT: Thêm related_name='don_mua' để tránh xung đột với nhan_vien_tao ---
    khach_hang = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='don_mua') 
    
    # --- ĐÃ THÊM: Lưu lại nhân viên nào thao tác tạo đơn này ---
    nhan_vien_tao = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='don_da_tao', verbose_name="Nhân viên tạo đơn")
    
    ho_ten = models.CharField(max_length=100, verbose_name="Họ và tên")
    so_dien_thoai = models.CharField(max_length=15, verbose_name="Số điện thoại")
    email = models.EmailField(verbose_name="Email nhận thông báo", blank=True, null=True) 
    dia_chi = models.TextField(verbose_name="Địa chỉ giao xe / Liên hệ")
    loai_don = models.CharField(max_length=1, choices=LOAI_DON_CHOICES, default='A')
    trang_thai = models.CharField(max_length=20, choices=TRANG_THAI_CHOICES, default='Pending')
    ngay_dat = models.DateTimeField(auto_now_add=True)
    tong_tien = models.DecimalField(max_digits=15, decimal_places=0, default=0)
    so_tien_tra_truoc = models.DecimalField(max_digits=15, decimal_places=0, default=0, verbose_name="Số tiền trả trước")

    def __str__(self):
        return f"Đơn #{self.id} - {self.ho_ten} - {self.xe.ten_xe}"


class KhoHang(models.Model):
    xe = models.ForeignKey(XeDien, on_delete=models.CASCADE, related_name='kho_hang')
    cua_hang = models.ForeignKey(CuaHang, on_delete=models.CASCADE)
    so_luong = models.PositiveIntegerField(default=0, verbose_name="Số lượng tồn kho")
    ngay_cap_nhat = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('xe', 'cua_hang')
        verbose_name = "Kho hàng"
        verbose_name_plural = "Kho hàng"

    def __str__(self):
        return f"{self.xe.ten_xe} - {self.cua_hang.ten_cua_hang} ({self.so_luong} chiếc)"

# ==========================================
# THÊM QUYỀN VÀO USERPROFILE
# ==========================================
class UserProfile(models.Model):
    VAI_TRO_CHOICES = (
        ('admin', 'Admin'),
        ('quan_ly', 'Quản lý'),
        ('nhan_vien', 'Nhân viên'),
        ('khach_hang', 'Khách hàng'),
    )
    
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    so_dien_thoai = models.CharField(max_length=15, blank=True)
    dia_chi = models.TextField(blank=True)
    avatar = models.ImageField(upload_to='avatar/', null=True, blank=True)
    
    vai_tro = models.CharField(max_length=20, choices=VAI_TRO_CHOICES, default='khach_hang', verbose_name="Vai trò")

    def __str__(self):
        return self.user.username

class Feedback(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    xe = models.ForeignKey(XeDien, on_delete=models.CASCADE, null=True, blank=True)
    noi_dung = models.TextField()
    danh_gia = models.IntegerField(choices=[
        (1, '1 sao'), (2, '2 sao'), (3, '3 sao'), (4, '4 sao'), (5, '5 sao'),
    ], default=5)
    ngay_tao = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.danh_gia}⭐"

class NhanVien(User):
    class Meta:
        proxy = True 
        verbose_name = 'Nhân viên cửa hàng'
        verbose_name_plural = 'Quản lý Nhân viên'

class KhachHang(User):
    class Meta:
        proxy = True 
        verbose_name = 'Khách hàng'
        verbose_name_plural = 'Quản lý Khách hàng'

# ==========================================
# BẢNG PHIẾU NHẬP KHO (MỚI THÊM)
# ==========================================
class PhieuNhapKho(models.Model):
    cua_hang = models.ForeignKey(CuaHang, on_delete=models.CASCADE, verbose_name="Nhập vào chi nhánh")
    nhan_vien_nhap = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name="Nhân viên phụ trách")
    ngay_nhap = models.DateTimeField(auto_now_add=True)
    ghi_chu = models.TextField(blank=True, null=True, verbose_name="Ghi chú lô hàng")

    def __str__(self):
        return f"Phiếu nhập #{self.id} - {self.cua_hang.ten_cua_hang} ({self.ngay_nhap|date:'d/m/Y'})"

class ChiTietPhieuNhap(models.Model):
    phieu_nhap = models.ForeignKey(PhieuNhapKho, on_delete=models.CASCADE, related_name='chi_tiet')
    xe = models.ForeignKey(XeDien, on_delete=models.CASCADE)
    so_luong = models.PositiveIntegerField(verbose_name="Số lượng nhập")

    def __str__(self):
        return f"{self.xe.ten_xe} - {self.so_luong} chiếc"
    
    