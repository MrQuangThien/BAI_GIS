from django import forms
from django.contrib.auth.models import User
from .models import XeDien, DonHang, KhoHang, PhienSac, UserProfile, Feedback,PhieuNhapKho, ChiTietPhieuNhap

from django.forms import inlineformset_factory

# ==========================================
# 1. QUẢN LÝ TÀI KHOẢN NHÂN VIÊN NỘI BỘ
# ==========================================

# Định nghĩa danh sách quyền chỉ dành cho nội bộ (Loại bỏ Khách Hàng)
NHAN_VIEN_ROLES = (
    ('admin', 'Admin'),
    ('quan_ly', 'Quản lý'),
    ('nhan_vien', 'Nhân viên'),
)

class UserForm(forms.ModelForm):
    ho_ten = forms.CharField(
        label="Họ và tên",
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ví dụ: Nguyễn Văn A'})
    )
    password = forms.CharField(
        label="Mật khẩu",
        required=False, 
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Nhập mật khẩu (để trống nếu không đổi)'})
    )
    
    # TRƯỜNG MỚI: Phân quyền vai trò
    vai_tro = forms.ChoiceField(
        choices=NHAN_VIEN_ROLES,
        label="Phân quyền (Vai trò)",
        widget=forms.Select(attrs={'class': 'form-select fw-bold text-success'})
    )

    class Meta:
        model = User
        # Đã loại bỏ is_staff và is_superuser ra khỏi form
        fields = ['username', 'ho_ten', 'email', 'password', 'vai_tro', 'is_active']
        
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tên đăng nhập viết liền không dấu'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Địa chỉ Email'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }
        labels = {
            'username': 'Tên đăng nhập',
            'email': 'Email liên hệ',
            'is_active': 'Trạng thái hoạt động (Mở/Khóa)'
        }

    # HÀM NÀY ĐỂ HIỂN THỊ DỮ LIỆU CŨ LÊN FORM
    def __init__(self, *args, **kwargs):
        super(UserForm, self).__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            # 1. Ghép Họ + Tên
            ho = self.instance.last_name or ""
            ten = self.instance.first_name or ""
            self.fields['ho_ten'].initial = f"{ho} {ten}".strip()
            
            # 2. Lấy Vai trò từ UserProfile
            try:
                self.fields['vai_tro'].initial = self.instance.userprofile.vai_tro
            except UserProfile.DoesNotExist:
                self.fields['vai_tro'].initial = 'nhan_vien'

    # HÀM NÀY ĐỂ LƯU VÀO CSDL
    def save(self, commit=True):
        user = super(UserForm, self).save(commit=False)
        
        # 1. Chẻ đôi "Họ và tên"
        ho_ten_full = self.cleaned_data.get('ho_ten', '').strip()
        if ho_ten_full:
            parts = ho_ten_full.rsplit(' ', 1) # Cắt chữ cuối cùng làm Tên
            if len(parts) == 2:
                user.last_name = parts[0]
                user.first_name = parts[1]
            else:
                user.last_name = parts[0]
                user.first_name = ""
        else:
            user.last_name = ""
            user.first_name = ""

        # 2. Xử lý mật khẩu (Chỉ mã hóa nếu có gõ pass mới)
        if self.cleaned_data.get('password'):
            user.set_password(self.cleaned_data['password'])

        # 3. Phân quyền tự động dựa trên Vai trò chọn ở giao diện
        vai_tro_chon = self.cleaned_data.get('vai_tro')
        if vai_tro_chon == 'admin':
            user.is_superuser = True
            user.is_staff = True
        elif vai_tro_chon in ['quan_ly', 'nhan_vien']:
            user.is_superuser = False
            user.is_staff = True # Phải là True để vào được màn hình quản trị

        if commit:
            user.save()
            
            # 4. Lưu quyền vào bảng Profile
            profile, created = UserProfile.objects.get_or_create(user=user)
            profile.vai_tro = vai_tro_chon
            profile.save()
            
        return user


# ==========================================
# 2. FORM ĐĂNG KÝ (DÀNH CHO KHÁCH HÀNG MỚI NGOÀI WEB)
# ==========================================
class RegisterForm(forms.ModelForm):
    password = forms.CharField(
        label="Mật khẩu",
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Nhập mật khẩu'})
    )
    confirm_password = forms.CharField(
        label="Xác nhận mật khẩu",
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Nhập lại mật khẩu'})
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'password']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tên đăng nhập'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Địa chỉ Email'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password and confirm_password and password != confirm_password:
            raise forms.ValidationError("Mật khẩu xác nhận không khớp!")
        return cleaned_data

    # Bổ sung hàm save để tự động gán quyền 'khach_hang' khi đăng ký
    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            user.save()
            profile = UserProfile.objects.create(user=user, vai_tro='khach_hang')
        return user


# ==========================================
# 3. CÁC FORM SẢN PHẨM & KINH DOANH
# ==========================================
class XeDienForm(forms.ModelForm):
    class Meta:
        model = XeDien
        fields = '__all__'
        widgets = {
            'ten_xe': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ví dụ: VinFast VF 8'}),
            'hang_san_xuat': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ví dụ: VinFast'}),
            'danh_muc': forms.Select(attrs={'class': 'form-select'}), 
            'dung_luong_pin': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ví dụ: 88'}),
            'tam_di_chuyen': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ví dụ: 400'}),
            'gia': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Nhập giá bán (VNĐ)'}),
            'cua_hang': forms.Select(attrs={'class': 'form-select'}),
            'hinh_anh': forms.FileInput(attrs={'class': 'form-control mb-2'}),
            'trang_thai': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'noi_bat': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'sap_ve': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'mo_ta': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Nhập mô tả chi tiết của xe...'}),
            'anh_phu_1': forms.FileInput(attrs={'class': 'form-control'}),
            'anh_phu_2': forms.FileInput(attrs={'class': 'form-control'}),
            'anh_phu_3': forms.FileInput(attrs={'class': 'form-control'}),
        }

class DonHangForm(forms.ModelForm):
    class Meta:
        model = DonHang
        fields = ['ho_ten', 'so_dien_thoai', 'email', 'dia_chi', 'loai_don']
        widgets = {
            'ho_ten': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nhập họ tên của bạn'}),
            'so_dien_thoai': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ví dụ: 0901234567'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email để nhận xác nhận'}),
            'dia_chi': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Nhập địa chỉ của bạn'}),
            'loai_don': forms.Select(attrs={'class': 'form-select fw-bold text-success'}),
        }
    def __init__(self, *args, **kwargs):
        self.xe = kwargs.pop('xe', None) 
        super(DonHangForm, self).__init__(*args, **kwargs)
        if self.xe and self.xe.sap_ve:
            self.fields['loai_don'].choices = [('B', 'Đặt cọc giữ chỗ trước (10% giá trị xe)')]
        else:
            self.fields['loai_don'].choices = [
                ('A', 'Đặt giữ xe online (Thanh toán sau)'),
                ('B', 'Đặt cọc online (10% giá trị xe)'),
                ('C', 'Mua online hoàn toàn (Thanh toán 100%)'),
            ]

class DonHangTaiQuayForm(forms.ModelForm):
    class Meta:
        model = DonHang
        fields = ['xe', 'ho_ten', 'so_dien_thoai', 'email', 'dia_chi', 'loai_don', 'tong_tien', 'so_tien_tra_truoc', 'trang_thai']
        widgets = {
            'xe': forms.Select(attrs={'class': 'form-select fw-bold text-success'}),
            'ho_ten': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tên khách hàng'}),
            'so_dien_thoai': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ví dụ: 0901234567'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Bỏ trống nếu không có'}),
            'dia_chi': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'loai_don': forms.Select(attrs={'class': 'form-select fw-bold', 'id': 'id_loai_don'}),
            'tong_tien': forms.NumberInput(attrs={'class': 'form-control text-danger fw-bold'}),
            'so_tien_tra_truoc': forms.NumberInput(attrs={'class': 'form-control text-primary fw-bold'}),
            'trang_thai': forms.Select(attrs={'class': 'form-select'}),
        }
    def __init__(self, *args, **kwargs):
        super(DonHangTaiQuayForm, self).__init__(*args, **kwargs)

        self.fields['loai_don'].choices = [

            ('D', 'Thanh toán 100% nhận xe ngay'),
            ('E', 'Đặt cọc tại quầy (Tiền mặt/Quẹt thẻ)'),
        ]

        self.fields['trang_thai'].choices = [


            ('Paid', 'Đã thanh toán đủ'),
            ('Deposit Paid', 'Đã đặt cọc'),
        ]


# Form thông tin chung của Phiếu Nhập
class PhieuNhapKhoForm(forms.ModelForm):
    class Meta:
        model = PhieuNhapKho
        fields = ['cua_hang', 'ghi_chu']
        widgets = {
            'cua_hang': forms.Select(attrs={'class': 'form-select fw-bold text-success'}),
            'ghi_chu': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Ví dụ: Nhập hàng đợt 1 tháng 4...'})
        }

# Form Chi tiết từng chiếc xe
class ChiTietPhieuNhapForm(forms.ModelForm):
    class Meta:
        model = ChiTietPhieuNhap
        fields = ['xe', 'so_luong']
        widgets = {
            'xe': forms.Select(attrs={'class': 'form-select fw-bold'}),
            'so_luong': forms.NumberInput(attrs={'class': 'form-control text-center fw-bold text-primary', 'min': 1})
        }

# Khởi tạo Formset cho phép nhập nhiều dòng cùng lúc
ChiTietPhieuNhapFormSet = inlineformset_factory(
    PhieuNhapKho, ChiTietPhieuNhap, form=ChiTietPhieuNhapForm,
    extra=1, # Mặc định hiện 1 dòng trống
    can_delete=True # Cho phép bấm nút xóa dòng
)

class PhienSacForm(forms.ModelForm):
    class Meta:
        model = PhienSac
        fields = '__all__'

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['so_dien_thoai', 'dia_chi', 'avatar']

class FeedbackForm(forms.ModelForm):
    class Meta:
        model = Feedback
        fields = ['xe', 'noi_dung', 'danh_gia']