from django import forms
from django.contrib.auth.models import User
from .models import XeDien, DonHang, KhoHang, CuaHang, PhienSac, UserProfile, Feedback,PhieuNhapKho, ChiTietPhieuNhap, YeuCauHoTro, LichLaiThu, KhuyenMai
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
    
    vai_tro = forms.ChoiceField(
        choices=NHAN_VIEN_ROLES, # Đảm bảo bạn đã khai báo biến này ở trên nhé
        label="Phân quyền (Vai trò)",
        widget=forms.Select(attrs={'class': 'form-select fw-bold text-success'})
    )

    # 1. THÊM TRƯỜNG CHỌN CHI NHÁNH VÀO FORM
    cua_hang = forms.ModelChoiceField(
        queryset=CuaHang.objects.all(),
        label="Chi nhánh làm việc",
        required=False, # Không bắt buộc vì Quản lý tổng không cần gắn chi nhánh
        empty_label="--- Chọn chi nhánh (Bỏ trống nếu là Sếp) ---",
        widget=forms.Select(attrs={'class': 'form-select text-primary'})
    )

    class Meta:
        model = User
        # Đưa thêm cua_hang vào danh sách fields
        fields = ['username', 'ho_ten', 'email', 'password', 'vai_tro', 'cua_hang', 'is_active']
        
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

    def __init__(self, *args, **kwargs):
        super(UserForm, self).__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            ho = self.instance.last_name or ""
            ten = self.instance.first_name or ""
            self.fields['ho_ten'].initial = f"{ho} {ten}".strip()
            
            try:
                self.fields['vai_tro'].initial = self.instance.userprofile.vai_tro
                # 2. LOAD CHI NHÁNH CŨ LÊN GIAO DIỆN KHI BẤM VÀO NÚT "SỬA"
                self.fields['cua_hang'].initial = self.instance.userprofile.cua_hang
            except UserProfile.DoesNotExist:
                self.fields['vai_tro'].initial = 'nhan_vien'
                self.fields['cua_hang'].initial = None

    def save(self, commit=True):
        user = super(UserForm, self).save(commit=False)
        
        ho_ten_full = self.cleaned_data.get('ho_ten', '').strip()
        if ho_ten_full:
            parts = ho_ten_full.rsplit(' ', 1) 
            if len(parts) == 2:
                user.last_name = parts[0]
                user.first_name = parts[1]
            else:
                user.last_name = parts[0]
                user.first_name = ""
        else:
            user.last_name = ""
            user.first_name = ""

        if self.cleaned_data.get('password'):
            user.set_password(self.cleaned_data['password'])

        vai_tro_chon = self.cleaned_data.get('vai_tro')
        if vai_tro_chon == 'admin':
            user.is_superuser = True
            user.is_staff = True
        elif vai_tro_chon in ['quan_ly', 'nhan_vien']:
            user.is_superuser = False
            user.is_staff = True 

        if commit:
            user.save()
            
            profile, created = UserProfile.objects.get_or_create(user=user)
            profile.vai_tro = vai_tro_chon
            # 3. LƯU CHI NHÁNH VÀO DATABASE
            profile.cua_hang = self.cleaned_data.get('cua_hang')
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
# Thêm class này lên trên đầu file forms.py (dưới phần import)
# Đảm bảo class này vẫn nằm ở trên
class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True

class XeDienForm(forms.ModelForm):
    # ĐÃ SỬA LỖI Ở ĐÂY: Đổi forms.ClearableFileInput thành MultipleFileInput
    hinh_anh = forms.FileField(
        widget=MultipleFileInput(attrs={'class': 'form-control', 'multiple': True}),
        required=False,
        label="Chọn tất cả hình ảnh sản phẩm"
    )

    class Meta:
        model = XeDien
        exclude = ['anh_phu_1', 'anh_phu_2', 'anh_phu_3'] # Loại bỏ các trường cũ
        
        # Bổ sung widgets để biến các trường True/False thành nút Switch giao diện đẹp
        widgets = {
            'noi_bat': forms.CheckboxInput(attrs={'class': 'form-check-input cursor-pointer'}),
            'sap_ve': forms.CheckboxInput(attrs={'class': 'form-check-input cursor-pointer'}),
            'moi_ve': forms.CheckboxInput(attrs={'class': 'form-check-input cursor-pointer'}),
            'ban_chay': forms.CheckboxInput(attrs={'class': 'form-check-input cursor-pointer'}),
        }


class DonHangForm(forms.ModelForm):
    class Meta:
        model = DonHang
        # ĐÃ SỬA: Bổ sung ngay_giao_xe và loai_don vào cuối danh sách
        fields = ['ho_ten', 'so_dien_thoai', 'email', 'hinh_thuc_nhan', 'dia_chi', 'cua_hang', 'ngay_giao_xe', 'loai_don']
        widgets = {
            'ho_ten': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nhập họ tên của bạn'}),
            'so_dien_thoai': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ví dụ: 0901234567'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email để nhận xác nhận'}),
            
            # ĐÃ THÊM: Widget dạng nút chọn Radio
            'hinh_thuc_nhan': forms.RadioSelect(attrs={'class': 'form-check-input'}),
            
            'dia_chi': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Nhập số nhà, tên đường, phường/xã...'}),
            'cua_hang': forms.Select(attrs={'class': 'form-select fw-bold border-success', 'required': 'required'}),
            'ngay_giao_xe': forms.DateInput(attrs={'type': 'date', 'class': 'form-control fw-bold text-primary', 'required': 'required'}), 
            'loai_don': forms.Select(attrs={'class': 'form-select fw-bold text-success'}),
        }

    def __init__(self, *args, **kwargs):
        self.xe = kwargs.pop('xe', None) 
        super(DonHangForm, self).__init__(*args, **kwargs)
        
        if self.xe:
            # --- ĐÃ SỬA: CHIA LOGIC CHO XE SẮP VỀ VÀ XE SẴN CÓ ---
            if self.xe.sap_ve:
                # Trường hợp 1: Xe Sắp về (Pre-order) -> Cho phép chọn tất cả chi nhánh đang hoạt động
                self.fields['cua_hang'].queryset = CuaHang.objects.filter(trang_thai=True)
                self.fields['cua_hang'].empty_label = "--- Chọn chi nhánh bạn muốn nhận xe ---"
            else:
                # Trường hợp 2: Xe Sẵn có -> Lọc khắt khe, chỉ hiện chi nhánh tồn kho > 0
                kho_xe_co_san = KhoHang.objects.filter(xe=self.xe, so_luong__gt=0)
                danh_sach_id_cua_hang = kho_xe_co_san.values_list('cua_hang_id', flat=True)
                self.fields['cua_hang'].queryset = CuaHang.objects.filter(id__in=danh_sach_id_cua_hang)
                self.fields['cua_hang'].empty_label = "--- Vui lòng chọn chi nhánh còn hàng ---"
            # ----------------------------------------------------

            # Xử lý loại đơn giữ nguyên...
            if self.xe.sap_ve:
                self.fields['loai_don'].choices = [
                    ('DatCoc', 'Đặt cọc Online (20.000.000 VNĐ)')
                ]
            else:
                self.fields['loai_don'].choices = [
                    ('DatCoc', 'Đặt cọc Online (20.000.000 VNĐ)'),
                    ('TraThang', 'Mua Online hoàn toàn (Thanh toán 100%)'),
                ]
class DonHangTaiQuayForm(forms.ModelForm):
    class Meta:
        model = DonHang
        fields = ['xe', 'ho_ten', 'so_dien_thoai', 'email', 'dia_chi', 'loai_don', 'tong_tien', 'so_tien_tra_truoc', 'trang_thai','cua_hang']
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
            'cua_hang': forms.Select(attrs={'class': 'form-select fw-bold border-primary text-primary'}),
        }
        
    def __init__(self, *args, **kwargs):
        self.request_user = kwargs.pop('request_user', None)
        super(DonHangTaiQuayForm, self).__init__(*args, **kwargs)

        xe_co_san = XeDien.objects.filter(sap_ve=False)
        self.fields['xe'].queryset = XeDien.objects.none()
        
        if self.request_user:
            is_admin = self.request_user.is_superuser or (hasattr(self.request_user, 'userprofile') and self.request_user.userprofile.vai_tro == 'QuanLy')
            
            if is_admin:
                self.fields['cua_hang'].queryset = CuaHang.objects.all()
                self.fields['cua_hang'].required = True
                self.fields['cua_hang'].empty_label = "--- Vui lòng chọn chi nhánh xuất xe ---"
                self.fields['xe'].queryset = xe_co_san 
            else:
                chi_nhanh_nv = getattr(self.request_user.userprofile, 'cua_hang', None)
                if chi_nhanh_nv:
                    self.fields['cua_hang'].queryset = CuaHang.objects.filter(id=chi_nhanh_nv.id)
                    self.fields['cua_hang'].initial = chi_nhanh_nv
                    self.fields['cua_hang'].widget.attrs.update({
                        'style': 'pointer-events: none; background-color: #e9ecef; color: #6c757d;',
                        'tabindex': '-1',
                        'readonly': 'readonly'
                    })
                    
                    # 🔥 ĐÃ SỬA: Chỉ lấy ID của những xe CÓ SỐ LƯỢNG > 0
                    xe_ids_trong_kho = KhoHang.objects.filter(cua_hang=chi_nhanh_nv, so_luong__gt=0).values_list('xe_id', flat=True)
                    self.fields['xe'].queryset = xe_co_san.filter(id__in=xe_ids_trong_kho)

        self.fields['loai_don'].choices = [
            ('TraThang', 'Thanh toán 100% nhận xe'),
            ('DatCoc', 'Đặt cọc giữ xe (20.000.000 VNĐ)'),
        ]

        # Cập nhật lại trạng thái nếu cần
        self.fields['trang_thai'].choices = [
            ('Paid', 'Đã thanh toán đủ'),
            ('Deposit Paid', 'Đã đặt cọc'),
        ]
        
    def clean(self):
        cleaned_data = super().clean()
        cua_hang = cleaned_data.get('cua_hang')
        xe = cleaned_data.get('xe')

        if cua_hang and xe:
            # 🔥 ĐÃ SỬA: Bảo vệ kép, chặn Admin nếu chọn xe đã hết số lượng
            co_trong_kho = KhoHang.objects.filter(cua_hang=cua_hang, xe=xe, so_luong__gt=0).exists()
            if not co_trong_kho:
                self.add_error('xe', f'⚠️ LỖI: Chi nhánh "{cua_hang.ten_cua_hang}" hiện đã hết hàng dòng xe "{xe.ten_xe}". Vui lòng chọn xe khác!')

        return cleaned_data

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
        
        # 1. Ẩn đi các trường mà hệ thống tự động tính toán
        exclude = ['dien_nang', 'tong_tien']
        
        # 2. Trang bị bộ chọn Lịch & Giờ (DateTime Picker) chuẩn HTML5 cho các ô thời gian
        widgets = {
            'tram_sac': forms.Select(attrs={'class': 'form-select fw-semibold'}),
            'khach_hang': forms.Select(attrs={'class': 'form-select'}),
            'thoi_gian_bat_dau': forms.DateTimeInput(attrs={
                'class': 'form-control', 
                'type': 'datetime-local' # Biến ô text thành bộ chọn ngày giờ xịn sò
            }),
            'thoi_gian_ket_thuc': forms.DateTimeInput(attrs={
                'class': 'form-control', 
                'type': 'datetime-local'
            }),
            'trang_thai': forms.Select(attrs={'class': 'form-select'}),
            # Nếu bạn có trường ghi chú, có thể thêm vào đây:
            # 'ghi_chu': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        # BỔ SUNG vai_tro VÀ cua_hang VÀO ĐÂY
        fields = ['so_dien_thoai', 'dia_chi', 'avatar', 'vai_tro', 'cua_hang']
        
        # Đổi tên nhãn cho đẹp mắt trên giao diện
        labels = {
            'so_dien_thoai': 'Số điện thoại liên hệ',
            'dia_chi': 'Địa chỉ hiện tại',
            'avatar': 'Ảnh đại diện (Avatar)',
            'vai_tro': 'Phân quyền (Vai trò)',
            'cua_hang': 'Chi nhánh trực thuộc (Bỏ trống nếu là Sếp tổng)',
        }

class FeedbackForm(forms.ModelForm):
    class Meta:
        model = Feedback
        fields = ['xe', 'noi_dung', 'danh_gia']


class YeuCauHoTroForm(forms.ModelForm):
    class Meta:
        model = YeuCauHoTro
        fields = ['tieu_de', 'noi_dung_hoi']
        widgets = {
            'tieu_de': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ví dụ: Cần tư vấn thủ tục mua trả góp VF8...'}),
            'noi_dung_hoi': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Viết chi tiết câu hỏi của bạn tại đây...'}),
        }

# ==========================================
# 4. FORM DÀNH CHO TRANG QUẢN LÝ TÀI KHOẢN CÁ NHÂN
# ==========================================
class UserUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['last_name', 'first_name', 'email']

class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['so_dien_thoai', 'dia_chi', 'avatar']

class EmailChangeForm(forms.Form):
    new_email = forms.EmailField(
        label="Địa chỉ Email mới", 
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Nhập email mới của bạn'})
    )
    password = forms.CharField(
        label="Mật khẩu hiện tại", 
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Nhập mật khẩu để xác nhận'})
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super(EmailChangeForm, self).__init__(*args, **kwargs)

    def clean_password(self):
        password = self.cleaned_data.get('password')
        # Kiểm tra xem mật khẩu nhập vào có khớp với tài khoản đang đăng nhập không
        if not self.user.check_password(password):
            raise forms.ValidationError("Mật khẩu hiện tại không chính xác!")
        return password

    def clean_new_email(self):
        new_email = self.cleaned_data.get('new_email')
        # Kiểm tra xem email mới này đã có ai đăng ký chưa
        if User.objects.filter(email=new_email).exclude(pk=self.user.pk).exists():
            raise forms.ValidationError("Email này đã được sử dụng bởi tài khoản khác!")
        return new_email
    
class LichLaiThuForm(forms.ModelForm):
    class Meta:
        model = LichLaiThu
        fields = ['ho_ten', 'so_dien_thoai', 'email', 'cua_hang', 'ngay_hen', 'ghi_chu']
        widgets = {
            'ho_ten': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ví dụ: Nguyễn Văn A', 'required': True}),
            'so_dien_thoai': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ví dụ: 0901234567', 'required': True}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Để nhận thông báo xác nhận'}),
            'cua_hang': forms.Select(attrs={'class': 'form-select fw-bold border-primary text-primary', 'required': True}),
            'ngay_hen': forms.DateInput(attrs={'type': 'date', 'class': 'form-control fw-bold text-success', 'required': True}),
            'ghi_chu': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Bạn muốn yêu cầu màu xe nào, hay muốn nhân viên gọi tư vấn vào giờ nào?'}),
        }

    def __init__(self, *args, **kwargs):
        super(LichLaiThuForm, self).__init__(*args, **kwargs)
        # Chỉ hiển thị danh sách các chi nhánh
        self.fields['cua_hang'].queryset = CuaHang.objects.all()
        self.fields['cua_hang'].empty_label = "--- Chọn chi nhánh bạn muốn đến xem ---"

class KhuyenMaiForm(forms.ModelForm):
    class Meta:
        model = KhuyenMai
        fields = ['ma_code', 'ten_chuong_trinh', 'loai_khuyen_mai', 'gia_tri', 'mo_ta_qua_tang', 'loai_don_ap_dung', 'chien_luoc', 'ngay_bat_dau', 'ngay_ket_thuc', 'trang_thai', 'xe_ap_dung']
        widgets = {
            'ngay_bat_dau': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'ngay_ket_thuc': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'ma_code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'VD: VINFAST50'}),
            'ten_chuong_trinh': forms.TextInput(attrs={'class': 'form-control'}),
            'loai_khuyen_mai': forms.Select(attrs={'class': 'form-select'}),
            'chien_luoc': forms.Select(attrs={'class': 'form-select'}),
            'gia_tri': forms.NumberInput(attrs={'class': 'form-control'}),
            'mo_ta_qua_tang': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'VD: Tặng sạc di động 2.2kW'}),
            'loai_don_ap_dung': forms.Select(attrs={'class': 'form-select'}),
            'trang_thai': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'xe_ap_dung': forms.SelectMultiple(attrs={'class': 'form-select', 'size': '4'}),
        }