from django import forms
from django.contrib.auth.models import User
# Nhớ import Model XeDien vào form nhé
from .models import XeDien 

class UserForm(forms.ModelForm):
    password = forms.CharField(
        required=False, 
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Nhập mật khẩu mới'})
    )
    is_staff = forms.BooleanField(required=False, label="Quyền Nhân viên (Quản lý trạm/xe)")
    is_superuser = forms.BooleanField(required=False, label="Quyền Admin (Toàn quyền hệ thống)")

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'is_staff', 'is_superuser']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tên người dùng'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Địa chỉ Email'}),
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
# ĐÂY LÀ PHẦN FORM XE ĐIỆN VỪA ĐƯỢC BỔ SUNG
# ==========================================
class XeDienForm(forms.ModelForm):
    class Meta:
        model = XeDien
        # Bổ sung hinh_anh, noi_bat, sap_ve vào danh sách
        fields = ['ten_xe', 'hang_san_xuat', 'dung_luong_pin', 'tam_di_chuyen', 'gia', 'trang_thai', 'cua_hang', 'hinh_anh', 'noi_bat', 'sap_ve']
        
        # Thêm class 'form-control' và 'form-check-input' để giao diện đẹp chuẩn Bootstrap
        widgets = {
            'ten_xe': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ví dụ: VinFast VF 8'}),
            'hang_san_xuat': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ví dụ: VinFast'}),
            'dung_luong_pin': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ví dụ: 88 kWh'}),
            'tam_di_chuyen': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ví dụ: 400 km'}),
            'gia': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Nhập giá bán (VNĐ)'}),
            'cua_hang': forms.Select(attrs={'class': 'form-select'}),
            'hinh_anh': forms.FileInput(attrs={'class': 'form-control'}),
            'trang_thai': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'noi_bat': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'sap_ve': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'mo_ta': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Nhập mô tả chi tiết của xe...'}),
            'anh_phu_1': forms.FileInput(attrs={'class': 'form-control'}),
            'anh_phu_2': forms.FileInput(attrs={'class': 'form-control'}),
            'anh_phu_3': forms.FileInput(attrs={'class': 'form-control'}),
        }