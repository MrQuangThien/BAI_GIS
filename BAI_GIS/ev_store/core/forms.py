from django import forms
from django.contrib.auth.models import User
from .models import XeDien, TramSac  # Đảm bảo đã import model XeDien

class UserForm(forms.ModelForm):
    password = forms.CharField(
        required=False, 
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Để trống nếu không đổi'})
    )
    is_staff = forms.BooleanField(required=False, label="Quyền Nhân viên")
    is_superuser = forms.BooleanField(required=False, label="Quyền Admin")

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'is_staff', 'is_superuser']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }

# ĐÂY LÀ PHẦN ĐANG THIẾU CỦA BẠN:
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