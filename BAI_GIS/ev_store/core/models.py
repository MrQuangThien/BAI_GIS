from django.db import models
from django import forms
from django.contrib.auth.models import User

# ==========================================
#                  MODELS
# ==========================================

class CuaHang(models.Model):
    ten_cua_hang = models.CharField(max_length=255)
    dia_chi = models.TextField()
    so_dien_thoai = models.CharField(max_length=20)
    trang_thai = models.BooleanField(default=True)

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
    mo_ta = models.TextField(verbose_name="Mô tả chi tiết", blank=True, null=True)
    
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

class PhienSac(models.Model):
    tram_sac = models.ForeignKey(TramSac, on_delete=models.CASCADE)
    thoi_gian_bat_dau = models.DateTimeField()
    thoi_gian_ket_thuc = models.DateTimeField()
    dien_nang_tieu_thu = models.FloatField()


class DonHang(models.Model):
    # Khai báo các lựa chọn cho Loại đơn và Trạng thái
    LOAI_DON_CHOICES = [
        ('A', 'Đặt giữ xe online'),
        ('B', 'Đặt cọc online'),
        ('C', 'Mua online hoàn toàn'),
        ('D', 'Mua trực tiếp - Trả thẳng 100%'), # Dành cho khách mua tại quầy
        ('E', 'Mua trực tiếp - Trả góp'),        # Dành cho khách mua tại quầy
    ]
    
    TRANG_THAI_CHOICES = [
        ('Pending', 'Pending (Đang chờ)'),
        ('Deposit Paid', 'Deposit Paid (Đã đặt cọc)'),
        ('Paid', 'Paid (Đã thanh toán)'),
        ('Cancelled', 'Đã hủy'),
    ]

    # Liên kết với Xe và Người dùng
    xe = models.ForeignKey(XeDien, on_delete=models.CASCADE)
    # Khách vãng lai vẫn mua được nên user có thể null
    khach_hang = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True) 
    
    # Thông tin khách hàng nhập vào form
    ho_ten = models.CharField(max_length=100, verbose_name="Họ và tên")
    so_dien_thoai = models.CharField(max_length=15, verbose_name="Số điện thoại")
    email = models.EmailField(verbose_name="Email nhận thông báo", blank=True, null=True) # Mở rộng thêm cho phép null nếu khách k có email
    dia_chi = models.TextField(verbose_name="Địa chỉ giao xe / Liên hệ")
    
    # Cấu hình đơn hàng
    loai_don = models.CharField(max_length=1, choices=LOAI_DON_CHOICES, default='A')
    trang_thai = models.CharField(max_length=20, choices=TRANG_THAI_CHOICES, default='Pending')
    
    # Tự động lưu ngày giờ đặt và tiền bạc
    ngay_dat = models.DateTimeField(auto_now_add=True)
    tong_tien = models.DecimalField(max_digits=15, decimal_places=0, default=0)
    
    # ---> ĐÃ THÊM: TRƯỜNG TIỀN TRẢ TRƯỚC BỊ THIẾU <---
    so_tien_tra_truoc = models.DecimalField(max_digits=15, decimal_places=0, default=0, verbose_name="Số tiền trả trước")

    def __str__(self):
        return f"Đơn #{self.id} - {self.ho_ten} - {self.xe.ten_xe}"

# ==========================================
#                  FORMS
# ==========================================

class XeDienForm(forms.ModelForm):
    class Meta:
        model = XeDien
        fields = '__all__'
        widgets = {
            'ten_xe': forms.TextInput(attrs={'class': 'form-control'}),
            'hang_san_xuat': forms.TextInput(attrs={'class': 'form-control'}),
            'dung_luong_pin': forms.NumberInput(attrs={'class': 'form-control'}),
            'tam_di_chuyen': forms.NumberInput(attrs={'class': 'form-control'}),
            'gia': forms.NumberInput(attrs={'class': 'form-control'}),
            'trang_thai': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'cua_hang': forms.Select(attrs={'class': 'form-select'}),
        }


# models.py
class KhoHang(models.Model):
    xe = models.ForeignKey(XeDien, on_delete=models.CASCADE, related_name='kho_hang')
    cua_hang = models.ForeignKey(CuaHang, on_delete=models.CASCADE)
    so_luong = models.PositiveIntegerField(default=0, verbose_name="Số lượng tồn kho")
    ngay_cap_nhat = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('xe', 'cua_hang')  # Mỗi xe chỉ có 1 bản ghi kho tại 1 cửa hàng
        verbose_name = "Kho hàng"
        verbose_name_plural = "Kho hàng"

    def __str__(self):
        return f"{self.xe.ten_xe} - {self.cua_hang.ten_cua_hang} ({self.so_luong} chiếc)"


class PhienSac(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    tram_sac = models.ForeignKey(TramSac, on_delete=models.CASCADE)
    thoi_gian_bat_dau = models.DateTimeField()
    thoi_gian_ket_thuc = models.DateTimeField(null=True, blank=True)
    dien_nang_tieu_thu = models.FloatField(default=0)
    
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

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    so_dien_thoai = models.CharField(max_length=15, blank=True)
    dia_chi = models.TextField(blank=True)
    avatar = models.ImageField(upload_to='avatar/', null=True, blank=True)

    def __str__(self):
        return self.user.username
rating = models.IntegerField(choices=[
    (1, '1 sao'),
    (2, '2 sao'),
    (3, '3 sao'),
    (4, '4 sao'),
    (5, '5 sao'),
], default=5)

noi_dung = models.TextField()
class Feedback(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    xe = models.ForeignKey(XeDien, on_delete=models.CASCADE, null=True, blank=True)
    noi_dung = models.TextField()
    danh_gia = models.IntegerField(default=5)  # 1-5 sao
    ngay_tao = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.danh_gia}⭐"
