from django import forms
from django.contrib.auth.models import User
# Nhớ import Model XeDien vào form nhé
from .models import XeDien, DonHang

# Mở file core/forms.py ra và tìm class UserForm

class UserForm(forms.ModelForm):
    password = forms.CharField(
        required=False, 
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Nhập mật khẩu mới'})
    )
    is_staff = forms.BooleanField(required=False, label="Quyền Nhân viên")
    is_superuser = forms.BooleanField(required=False, label="Quyền Admin")

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'is_staff', 'is_superuser']
        
        # ĐÂY LÀ PHẦN QUAN TRỌNG NHẤT ĐỂ SỬA LỖI HIỂN THỊ
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tên người dùng'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Địa chỉ Email'}),
            # Chú ý: password đã được khai báo ở trên
        }


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

    # Kiểm tra mật khẩu khớp nhau
    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password and confirm_password and password != confirm_password:
            raise forms.ValidationError("Mật khẩu xác nhận không khớp!")
        return cleaned_data


# ==========================================
# ĐÂY LÀ PHẦN FORM XE ĐIỆN ĐÃ ĐƯỢC TỐI ƯU
# ==========================================
class XeDienForm(forms.ModelForm):
    class Meta:
        model = XeDien
        # Dùng '__all__' để lấy TẤT CẢ các trường (kể cả danh_muc, mo_ta, anh_phu...)
        fields = '__all__'
        
        widgets = {
            'ten_xe': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ví dụ: VinFast VF 8'}),
            'hang_san_xuat': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ví dụ: VinFast'}),
            'danh_muc': forms.Select(attrs={'class': 'form-select'}), # Đã bổ sung widget cho Danh mục
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

class DonHangTaiQuayForm(forms.ModelForm):
    class Meta:
        model = DonHang
        # Bao gồm cả trường so_tien_tra_truoc
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