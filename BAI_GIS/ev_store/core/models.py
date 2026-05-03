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
    danh_muc = models.ForeignKey(DanhMuc, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Danh mục sản phẩm")
    hinh_anh = models.ImageField(upload_to='xe_dien_images/', null=True, blank=True, verbose_name="Ảnh đại diện")
    noi_bat = models.BooleanField(default=False, verbose_name="Sản phẩm nổi bật")
    sap_ve = models.BooleanField(default=False, verbose_name="Sản phẩm sắp về")
    mo_ta = RichTextField(config_name='mini', blank=True, null=True, verbose_name="Mô tả chi tiết")
    cua_hang = models.ManyToManyField(CuaHang, related_name='danh_sach_xe', blank=True, verbose_name="Có tại chi nhánh")
    moi_ve = models.BooleanField(default=False, verbose_name="Hàng mới về")
    ban_chay = models.BooleanField(default=False, verbose_name="Bán chạy nhất")
    
    def __str__(self):
        return self.ten_xe
    

class AnhXeDien(models.Model):
    xe = models.ForeignKey(XeDien, on_delete=models.CASCADE, related_name='album_anh')
    image = models.ImageField(upload_to='xe_dien_images/')

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
    dien_nang_tieu_thu = models.FloatField(default=0, verbose_name="Điện năng (kWh)")
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
        # Tránh lỗi nếu user bị xóa (null)
        ten_khach = self.user.username if self.user else "Khách vãng lai"
        return f"{ten_khach} - {self.tram_sac.ten_tram}"

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

    # THÊM HÀM NÀY ĐỂ TỰ ĐỘNG TÍNH TIỀN KHI LƯU
    def save(self, *args, **kwargs):
        # Chỉ tính tiền khi phiên sạc đã có thời gian kết thúc
        if self.thoi_gian_bat_dau and self.thoi_gian_ket_thuc:
            thoigian = self.thoi_gian_ket_thuc - self.thoi_gian_bat_dau
            so_phut_sac = thoigian.total_seconds() / 60

            # Đảm bảo thời gian sạc hợp lệ (> 0)
            if so_phut_sac > 0:
                # Lấy công suất từ trạm (giả sử bảng TramSac có trường cong_suat)
                # Nếu không có trường này, bạn có thể gán cứng = 60
                cong_suat = getattr(self.tram_sac, 'cong_suat', 60) 
                
                # Tính số kWh = (Số phút / 60) * Công suất trạm
                # Dùng round(, 1) để làm tròn 1 chữ số thập phân (VD: 31.0 kWh)
                self.dien_nang_tieu_thu = round((so_phut_sac / 60) * cong_suat, 1)
                
                # Tính tổng tiền = Số kWh * 3.500đ
                self.tong_tien = int(self.dien_nang_tieu_thu * 3500)
                
                # Tự động chuyển trạng thái thành Hoàn thành khi có thời gian kết thúc
                self.trang_thai = 'Hoan thanh'

        # Gọi hàm save gốc của Django để lưu vào Database
        super().save(*args, **kwargs)

class KhuyenMai(models.Model):
    LOAI_KM_CHOICES = (
        ('tien_mat', 'Giảm tiền mặt'),
        ('phan_tram', 'Giảm phần trăm'),
        ('qua_tang', 'Quà tặng kèm'),
    )
    CHIEN_LUOC_CHOICES = (
        ('public', 'Hiển thị công khai (Trang chủ)'),
        ('private', 'Đặc quyền thành viên (Ví Voucher)'),
        ('lai_thu', 'Tặng kín sau khi lái thử'),
    )
    LOAI_DON_CHOICES = (
        ('Tat_ca', 'Áp dụng cho mọi loại đơn'),
        ('Tra_thang', 'Chỉ áp dụng khi Thanh toán 100%'),
        ('Dat_coc', 'Chỉ áp dụng cho Đặt cọc'),
    )

    loai_don_ap_dung = models.CharField(max_length=20, choices=LOAI_DON_CHOICES, default='Tat_ca', verbose_name="Loại đơn áp dụng")
    ma_code = models.CharField(max_length=50, unique=True)
    ten_chuong_trinh = models.CharField(max_length=255)
    loai_khuyen_mai = models.CharField(max_length=50, choices=LOAI_KM_CHOICES)
    gia_tri = models.DecimalField(max_digits=15, decimal_places=0, default=0)
    chien_luoc = models.CharField(max_length=20, choices=CHIEN_LUOC_CHOICES, default='public') # MỚI THÊM
    ngay_bat_dau = models.DateTimeField()
    ngay_ket_thuc = models.DateTimeField()
    trang_thai = models.BooleanField(default=True)
    xe_ap_dung = models.ManyToManyField('XeDien', blank=True, help_text="Để trống nếu muốn áp dụng cho TẤT CẢ các xe. Trái lại, chỉ áp dụng cho xe được chọn.")
    mo_ta_qua_tang = models.CharField(
        max_length=255, 
        blank=True, 
        null=True, 
        help_text="Nhập mô tả quà tặng nếu loại khuyến mãi là 'Quà tặng kèm' (VD: Tặng sạc di động 2.2kW)"
    )

    def is_valid(self):
        now = timezone.now()
        return self.trang_thai and self.ngay_bat_dau <= now <= self.ngay_ket_thuc
    
class DonHang(models.Model):
    LOAI_DON_CHOICES = [
    ('TraThang', 'Thanh toán 100% nhận xe'),
    ('DatCoc', 'Đặt cọc giữ xe (20.000.000 VNĐ)'),
]
    TRANG_THAI_CHOICES = [
        ('Pending', 'Pending (Đang chờ)'),
        ('Deposit Paid', 'Deposit Paid (Đã đặt cọc)'),
        ('Paid', 'Paid (Đã thanh toán)'),
        ('Cancelled', 'Đã hủy'),
    ]

    HINH_THUC_NHAN_CHOICES = [
        ('Tai_cua_hang', 'Nhận xe tại cửa hàng'),
        ('Giao_tan_noi', 'Giao xe tận nơi'),
    ]
    hinh_thuc_nhan = models.CharField(max_length=20, choices=HINH_THUC_NHAN_CHOICES, default='Tai_cua_hang', verbose_name="Hình thức nhận xe")

    ngay_giao_xe = models.DateField(null=True, blank=True, verbose_name="Ngày hẹn giao/nhận xe")

    xe = models.ForeignKey(XeDien, on_delete=models.CASCADE)

    cua_hang = models.ForeignKey(CuaHang, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Chi nhánh nhận xe")
    
    # --- ĐÃ CẬP NHẬT: Thêm related_name='don_mua' để tránh xung đột với nhan_vien_tao ---
    khach_hang = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='don_mua') 
    
    # --- ĐÃ THÊM: Lưu lại nhân viên nào thao tác tạo đơn này ---
    nhan_vien_tao = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='don_da_tao', verbose_name="Nhân viên tạo đơn")
    
    ho_ten = models.CharField(max_length=100, verbose_name="Họ và tên")
    so_dien_thoai = models.CharField(max_length=15, verbose_name="Số điện thoại")
    email = models.EmailField(verbose_name="Email nhận thông báo", blank=True, null=True) 
    dia_chi = models.TextField(verbose_name="Địa chỉ giao xe / Liên hệ")
    loai_don = models.CharField(max_length=20, choices=LOAI_DON_CHOICES, default='A')
    trang_thai = models.CharField(max_length=20, choices=TRANG_THAI_CHOICES, default='Pending')
    ngay_dat = models.DateTimeField(auto_now_add=True)
    tong_tien = models.DecimalField(max_digits=15, decimal_places=0, default=0)
    so_tien_tra_truoc = models.DecimalField(max_digits=15, decimal_places=0, default=0, verbose_name="Số tiền trả trước")
    khuyen_mai = models.ForeignKey(KhuyenMai, on_delete=models.SET_NULL, null=True, blank=True)
    tien_giam_gia = models.DecimalField(max_digits=15, decimal_places=0, default=0)
    
    def __str__(self):
        return f"Đơn #{self.id} - {self.ho_ten} - {self.xe.ten_xe}"
    
    @property
    def so_tien_con_lai(self):
        # Hệ thống tự động lấy Tổng tiền trừ đi Tiền đã cọc
        tong = self.tong_tien or 0
        da_tra = self.so_tien_tra_truoc or 0
        return tong - da_tra

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
    cua_hang = models.ForeignKey('CuaHang', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Chi nhánh làm việc")
    vai_tro = models.CharField(max_length=20, choices=VAI_TRO_CHOICES, default='khach_hang', verbose_name="Vai trò")
    avatar = models.ImageField(upload_to='avatars/', default='avatars/default.png', null=True, blank=True, verbose_name="Ảnh đại diện")
    voucher_da_luu = models.ManyToManyField('KhuyenMai', blank=True, related_name='nguoi_dung_da_luu')

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
    
class YeuCauHoTro(models.Model):
    khach_hang = models.ForeignKey(User, on_delete=models.CASCADE, related_name='cac_yeu_cau')
    tieu_de = models.CharField(max_length=255, verbose_name="Tiêu đề cần hỗ trợ")
    noi_dung_hoi = models.TextField(verbose_name="Nội dung câu hỏi")
    noi_dung_tra_loi = models.TextField(blank=True, null=True, verbose_name="Nhân viên trả lời")
    ngay_gui = models.DateTimeField(auto_now_add=True)
    trang_thai = models.BooleanField(default=False, verbose_name="Đã xử lý") 

    def __str__(self):
        return f"Hỗ trợ: {self.tieu_de} - {self.khach_hang.username}"
    
class TinNhanChat(models.Model):
    khach_hang = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_cua_khach')
    nguoi_gui = models.ForeignKey(User, on_delete=models.CASCADE, related_name='nguoi_gui_tin_nhan') 
    noi_dung = models.TextField()
    thoi_gian = models.DateTimeField(auto_now_add=True)
    da_doc = models.BooleanField(default=False)

    class Meta:
        ordering = ['thoi_gian'] # Sắp xếp tin nhắn cũ ở trên, mới ở dưới
        
    def __str__(self):
        return f"{self.nguoi_gui.username}: {self.noi_dung[:20]}"
    
class LichLaiThu(models.Model):
    TRANG_THAI_CHOICES = [
        ('cho_xac_nhan', 'Chờ xác nhận'),
        ('da_xac_nhan', 'Đã xác nhận lịch'),
        ('hoan_thanh', 'Khách đã đến showroom'),
        ('huy', 'Đã hủy / Khách không đến'),
    ]
    
    ho_ten = models.CharField(max_length=100, verbose_name="Họ tên khách hàng")
    so_dien_thoai = models.CharField(max_length=15, verbose_name="Số điện thoại")
    email = models.EmailField(blank=True, null=True, verbose_name="Email")
    
    xe_quan_tam = models.ForeignKey(XeDien, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Dòng xe quan tâm")
    cua_hang = models.ForeignKey(CuaHang, on_delete=models.SET_NULL, null=True, verbose_name="Chi nhánh đăng ký đến")
    
    ngay_hen = models.DateField(verbose_name="Ngày hẹn đến")
    ghi_chu = models.TextField(blank=True, null=True, verbose_name="Ghi chú của khách")
    
    trang_thai = models.CharField(max_length=20, choices=TRANG_THAI_CHOICES, default='cho_xac_nhan', verbose_name="Trạng thái")
    ngay_tao = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Lịch Lái Thử / Xem Xe"
        verbose_name_plural = "Lịch Lái Thử / Xem Xe"

    def __str__(self):
        return f"{self.ho_ten} - {self.xe_quan_tam} ({self.ngay_hen.strftime('%d/%m/%Y')})"
    
class DanhGiaTram(models.Model):
    khach_hang = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Khách hàng")
    tram_sac = models.ForeignKey('TramSac', on_delete=models.CASCADE, related_name='danh_gia', verbose_name="Trạm sạc")
    so_sao = models.IntegerField(default=5, verbose_name="Số sao")
    noi_dung = models.TextField(blank=True, null=True, verbose_name="Nội dung bình luận")
    ngay_danh_gia = models.DateTimeField(auto_now_add=True, verbose_name="Ngày đánh giá")

    def __str__(self):
        ten_khach = self.khach_hang.username if self.khach_hang else "Khách vãng lai"
        return f"{ten_khach} - {self.tram_sac.ten_tram} ({self.so_sao} Sao)"
    
class ThongBao(models.Model):
    LOAI_THONG_BAO = (
        ('don_hang', 'Đơn hàng mới'),
        ('lai_thu', 'Đăng ký lái thử'),
        ('ho_tro', 'Tin nhắn hỗ trợ'),
        ('he_thong', 'Hệ thống'),
    )

    tieu_de = models.CharField(max_length=255, verbose_name="Tiêu đề")
    noi_dung = models.TextField(verbose_name="Nội dung")
    loai = models.CharField(max_length=20, choices=LOAI_THONG_BAO, default='he_thong')
    
    # Nếu cua_hang = Null -> Sếp tổng mới thấy. Nếu có cua_hang -> Nhân viên chi nhánh đó thấy
    cua_hang = models.ForeignKey('CuaHang', on_delete=models.CASCADE, null=True, blank=True, related_name='cac_thong_bao')
    
    da_doc = models.BooleanField(default=False, verbose_name="Đã đọc")
    ngay_tao = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-ngay_tao'] # Luôn xếp thông báo mới nhất lên đầu

    def __str__(self):
        return self.tieu_de

class GioiThieuCuaHang(models.Model):
    tieu_de = models.CharField(max_length=200, default="Giới thiệu về EV STORE")
    # Trường nội dung sẽ chứa toàn bộ HTML từ CKEditor
    noi_dung = models.TextField() 
    ngay_cap_nhat = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Giới thiệu tổng quát"