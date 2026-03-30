from django import forms
from django.contrib.auth.models import User
from .models import XeDien

class UserForm(forms.ModelForm):
    password = forms.CharField(
        required=False, 
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Nhập mật khẩu mới'})
    )
    
    # Thêm các ô check quyền
    is_staff = forms.BooleanField(required=False, label="Quyền Nhân viên (Quản lý trạm/xe)")
    is_superuser = forms.BooleanField(required=False, label="Quyền Admin (Toàn quyền hệ thống)")

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'is_staff', 'is_superuser']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }