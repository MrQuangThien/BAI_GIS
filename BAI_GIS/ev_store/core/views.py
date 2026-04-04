import json
from math import radians, sin, cos, sqrt, atan2
from datetime import timezone
from functools import wraps # Import thư viện hỗ trợ Decorator
import folium
from folium.plugins import LocateControl

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth import login, logout 
from django.contrib import messages
from django.core.mail import send_mail
from django.db.models import Q, Count, Sum, Avg
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.dateparse import parse_datetime

from .models import TramSac, XeDien, CuaHang, DonHang, DanhMuc, Feedback, KhoHang, PhienSac

from .forms import XeDienForm, UserForm, RegisterForm, DonHangForm, DonHangTaiQuayForm, FeedbackForm, UserProfileForm, PhieuNhapKhoForm, ChiTietPhieuNhapFormSet

# ==========================================
# 0. DECORATOR PHÂN QUYỀN (QUAN TRỌNG)
# ==========================================
# ==========================================
# 0. DECORATOR PHÂN QUYỀN (ĐÃ FIX LỖI TÀI KHOẢN CŨ)
# ==========================================
def phan_quyen(roles=[]):
    """
    Hàm chặn URL dựa trên vai trò. Trả về 404 nếu không có quyền.
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper_func(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')
            
            user_role = 'khach_hang' # Đặt mặc định là khách
            
            # Lấy vai trò thực tế
            try:
                user_role = request.user.userprofile.vai_tro
            except:
                # CỨU HỘ: Nếu tài khoản tạo từ trước không có Profile nhưng có quyền is_staff
                if request.user.is_staff:
                    user_role = 'nhan_vien'

            # Mặc định tài khoản Superuser của Django luôn là Admin tối cao
            if request.user.is_superuser: 
                user_role = 'admin'

            # Kiểm tra xem vai trò có nằm trong danh sách cho phép không
            if user_role in roles:
                return view_func(request, *args, **kwargs)
            else:
                return render(request, '404.html', status=404)
        return wrapper_func
    return decorator


# ==========================================
# 1. GIAO DIỆN TRANG CHỦ & CÁC TRANG CHUNG
# ==========================================
def trang_chu(request):
    xe_noi_bat = XeDien.objects.filter(noi_bat=True, trang_thai=True)
    xe_sap_ve = XeDien.objects.filter(sap_ve=True, trang_thai=True)
    form = FeedbackForm() 
    context = {'xe_noi_bat': xe_noi_bat, 'xe_sap_ve': xe_sap_ve, 'form': form}
    return render(request, 'pages/trang_chu.html', context)

def tim_kiem(request):
    tu_khoa = request.GET.get('q', '')
    if tu_khoa:
        ket_qua = XeDien.objects.filter(Q(ten_xe__icontains=tu_khoa) | Q(hang_san_xuat__icontains=tu_khoa))
    else:
        ket_qua = XeDien.objects.none()
    return render(request, 'pages/tim_kiem.html', {'ket_qua': ket_qua, 'tu_khoa': tu_khoa})

# Cả Admin và Quản lý đều được xem Dashboard tổng quan
@login_required
@phan_quyen(roles=['admin', 'quan_ly','nhan_vien'])
def admin_dashboard(request):
    tong_so_tram = TramSac.objects.count()
    tram_hoat_dong = TramSac.objects.filter(trang_thai=True).count()
    tram_bao_tri = tong_so_tram - tram_hoat_dong
    tram_moi_nhat = TramSac.objects.all().order_by('-id')[:5]
    danh_muc_stats = DanhMuc.objects.annotate(so_luong_xe=Count('xedien'))

    tong_don_hang = DonHang.objects.count()
    tong_khach_hang = User.objects.filter(is_staff=False).count()
    tong_feedback = Feedback.objects.count()
    doanh_thu = DonHang.objects.filter(trang_thai='Paid').aggregate(Sum('tong_tien'))['tong_tien__sum'] or 0

    context = {
        'tong_so_tram': tong_so_tram, 'tram_hoat_dong': tram_hoat_dong, 'tram_bao_tri': tram_bao_tri,
        'tram_moi_nhat': tram_moi_nhat, 'danh_muc_stats': danh_muc_stats,
        'tong_don_hang': tong_don_hang, 'tong_khach_hang': tong_khach_hang, 'tong_feedback': tong_feedback, 'doanh_thu': doanh_thu,
    }
    return render(request, 'pages/dashboard.html', context)


# ==========================================
# 2. GIAO DIỆN XE ĐIỆN & CỬA HÀNG
# ==========================================
def danh_sach_san_pham(request):
    danh_sach = XeDien.objects.filter(trang_thai=True)
    cac_hang_xe = XeDien.objects.values_list('hang_san_xuat', flat=True).distinct()
    cac_phan_khuc = DanhMuc.objects.all()
    
    hang_id = request.GET.get('thuong_hieu')
    pk_id = request.GET.get('phan_khuc')
    
    if hang_id: danh_sach = danh_sach.filter(hang_san_xuat__iexact=hang_id)
    if pk_id: danh_sach = danh_sach.filter(danh_muc__id=pk_id)
        
    context = {'danh_sach_xe': danh_sach, 'cac_hang_xe': cac_hang_xe, 'cac_phan_khuc': cac_phan_khuc, 'hang_chon': hang_id, 'pk_chon': int(pk_id) if pk_id else None}
    return render(request, 'xe/san_pham.html', context)

def chi_tiet_xe(request, xe_id):
    xe = get_object_or_404(XeDien, id=xe_id)
    tong_ton_kho = xe.kho_hang.aggregate(Sum('so_luong'))['so_luong__sum'] or 0
    cho_phep_dat = True
    if not xe.sap_ve and tong_ton_kho <= 0:
        cho_phep_dat = False
        
    feedbacks = Feedback.objects.filter(xe=xe).order_by('-ngay_tao')
    trung_binh_sao = feedbacks.aggregate(Avg('danh_gia'))['danh_gia__avg'] or 0
        
    context = {'xe': xe, 'tong_ton_kho': tong_ton_kho, 'cho_phep_dat': cho_phep_dat, 'feedbacks': feedbacks, 'trung_binh_sao': round(trung_binh_sao, 1)}
    return render(request, 'xe/chi_tiet_xe.html', context)

# Chỉ Admin và Quản lý sửa/xóa/xem xe
@login_required
@phan_quyen(roles=['admin', 'quan_ly'])
def danh_sach_xe(request):
    tat_ca_xe = XeDien.objects.all()
    return render(request, 'xe/danh_sach_xe.html', {'tat_ca_xe': tat_ca_xe})

@login_required
@phan_quyen(roles=['admin', 'quan_ly'])
def them_xe(request):
    form = XeDienForm(request.POST or None, request.FILES or None)
    if form.is_valid():
        form.save()
        return redirect('danh_sach_xe')
    return render(request, 'xe/xe_form.html', {'form': form, 'title': 'Thêm Xe Mới'})

@login_required
@phan_quyen(roles=['admin', 'quan_ly'])
def sua_xe(request, pk):
    xe = get_object_or_404(XeDien, pk=pk)
    form = XeDienForm(request.POST or None, request.FILES or None, instance=xe)
    if form.is_valid():
        form.save()
        return redirect('danh_sach_xe')
    return render(request, 'xe/xe_form.html', {'form': form, 'title': 'Chỉnh Sửa Xe'})

@login_required
@phan_quyen(roles=['admin', 'quan_ly'])
def xoa_xe(request, pk):
    xe = get_object_or_404(XeDien, pk=pk)
    if request.method == 'POST':
        xe.delete()
        return redirect('danh_sach_xe')
    return render(request, 'xe/xe_confirm_delete.html', {'xe': xe})


# ==========================================
# 3. GIAO DIỆN BẢN ĐỒ & TRẠM SẠC
# ==========================================
def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return round(R * c, 2)

def ban_do_tram_sac(request):
    trams = TramSac.objects.filter(trang_thai=True)
    m = folium.Map(location=[10.7769, 106.7009], zoom_start=12, tiles='CartoDB positron')
    for tram in trams:
        try:
            folium.Marker(
                location=[float(tram.lat), float(tram.lon)],
                popup=f"<b>{tram.ten_tram}</b><br>{tram.dia_chi}<br>Công suất: {tram.cong_suat} kW<br>Loại: {tram.loai_sac}",
                tooltip=tram.ten_tram,
                icon=folium.Icon(color='blue', icon='plug', prefix='fa')
            ).add_to(m)
        except: continue
    LocateControl(auto_start=False, keepCurrentPosition=True).add_to(m)
    return render(request, 'tram_sac/map.html', {'map_html': m._repr_html_(), 'all_trams': list(trams.values('id', 'ten_tram', 'lat', 'lon', 'dia_chi'))})

# Chỉ Admin và Quản lý 
@login_required
@phan_quyen(roles=['admin', 'quan_ly'])
def quan_ly_tram_sac(request):
    danh_sach_tram = TramSac.objects.all().order_by('-id')
    return render(request, 'tram_sac/quan_ly_tram_sac.html', {'danh_sach_tram': danh_sach_tram})

@login_required
@phan_quyen(roles=['admin', 'quan_ly'])
def them_tram_sac(request):
    if request.method == 'POST':
        TramSac.objects.create(
            ten_tram=request.POST.get('ten_tram'), dia_chi=request.POST.get('dia_chi'),
            cong_suat=request.POST.get('cong_suat'), loai_sac=request.POST.get('loai_sac'),
            lat=request.POST.get('lat'), lon=request.POST.get('lon'),
            trang_thai=(request.POST.get('trang_thai') == 'on'), hinh_anh=request.FILES.get('hinh_anh')
        )
    return redirect('quan_ly_tram_sac')

@login_required
@phan_quyen(roles=['admin', 'quan_ly'])
def xoa_tram_sac(request, tram_id):
    get_object_or_404(TramSac, id=tram_id).delete()
    return redirect('quan_ly_tram_sac')

@login_required
@phan_quyen(roles=['admin', 'quan_ly'])
def sua_tram_sac(request, tram_id):
    tram = get_object_or_404(TramSac, id=tram_id)
    if request.method == 'POST':
        tram.ten_tram = request.POST.get('ten_tram')
        tram.dia_chi = request.POST.get('dia_chi')
        tram.cong_suat = request.POST.get('cong_suat')
        tram.loai_sac = request.POST.get('loai_sac')
        tram.lat = request.POST.get('lat')
        tram.lon = request.POST.get('lon')
        tram.trang_thai = (request.POST.get('trang_thai') == 'on')
        if 'hinh_anh' in request.FILES: tram.hinh_anh = request.FILES.get('hinh_anh')
        tram.save()
    return redirect('quan_ly_tram_sac')


# ==========================================
# 4. QUẢN LÝ ĐƠN HÀNG (Cả 3 quyền đều được vào)
# ==========================================
def tao_don_hang(request, xe_id):
    xe = get_object_or_404(XeDien, id=xe_id)
    loai_mac_dinh = 'B' if xe.sap_ve else 'A'
    if request.method == 'POST':
        form = DonHangForm(request.POST, xe=xe) 
        if form.is_valid():
            don_hang = form.save(commit=False)
            don_hang.xe = xe
            if request.user.is_authenticated: don_hang.khach_hang = request.user
            if don_hang.loai_don == 'A':
                don_hang.trang_thai = 'Pending'
                don_hang.tong_tien = 0
            elif don_hang.loai_don == 'B':
                don_hang.trang_thai = 'Deposit Paid'
                don_hang.tong_tien = xe.gia * 10 / 100 
            elif don_hang.loai_don == 'C':
                don_hang.trang_thai = 'Paid'
                don_hang.tong_tien = xe.gia 
            don_hang.save()
            messages.success(request, "Đặt hàng thành công! Chúng tôi sẽ liên hệ với bạn sớm nhất.")
            return redirect('trang_chu') 
    else:
        form = DonHangForm(initial={'loai_don': loai_mac_dinh}, xe=xe)
    return render(request, 'donhang/tao_don_hang.html', {'form': form, 'xe': xe})

# Nhân viên được phép xử lý đơn hàng
@login_required
@phan_quyen(roles=['admin', 'quan_ly', 'nhan_vien'])
def danh_sach_don_hang(request):
    danh_sach = DonHang.objects.all().order_by('-ngay_dat')
    return render(request, 'donhang/danh_sach.html', {'danh_sach_don_hang': danh_sach})

@login_required
@phan_quyen(roles=['admin', 'quan_ly', 'nhan_vien'])
def chi_tiet_don_hang(request, don_id):
    don_hang = get_object_or_404(DonHang, id=don_id)
    if request.method == 'POST':
        trang_thai_moi = request.POST.get('trang_thai')
        if trang_thai_moi:
            don_hang.trang_thai = trang_thai_moi
            don_hang.save()
            messages.success(request, 'Cập nhật trạng thái đơn hàng thành công!')
            return redirect('chi_tiet_don_hang', don_id=don_hang.id)
    return render(request, 'donhang/chi_tiet.html', {'don_hang': don_hang, 'trang_thai_choices': DonHang.TRANG_THAI_CHOICES})

@login_required
@phan_quyen(roles=['admin', 'quan_ly', 'nhan_vien'])
def tao_don_hang_offline(request):
    if request.method == 'POST':
        form = DonHangTaiQuayForm(request.POST)
        if form.is_valid():
            don_hang = form.save(commit=False)
            
            # --- ĐÃ THÊM: Tự động gán nhân viên đang đăng nhập làm người tạo đơn ---
            don_hang.nhan_vien_tao = request.user
            
            if don_hang.loai_don == 'D': don_hang.so_tien_tra_truoc = 0
            don_hang.save()
            messages.success(request, f'Đã tạo đơn hàng thành công cho khách {don_hang.ho_ten}!')
            return redirect('danh_sach_don_hang')
    else: form = DonHangTaiQuayForm(initial={'loai_don': 'D', 'trang_thai': 'Paid'})
    return render(request, 'donhang/tao_moi.html', {'form': form})

@login_required(login_url='login')
def chi_tiet_don_hang_khach(request, don_hang_id):
    don_hang = get_object_or_404(DonHang, id=don_hang_id, khach_hang=request.user)
    return render(request, 'donhang/chi_tiet_khach.html', {'don_hang': don_hang})


# ==========================================
# 5. QUẢN LÝ USER VÀ AUTHENTICATION 
# ==========================================
# CÁC TRANG NÀY CHỈ DUY NHẤT ADMIN MỚI ĐƯỢC VÀO

@login_required
@phan_quyen(roles=['admin'])
def list_user(request):
    return render(request, 'users/list_user.html', {'users': User.objects.all()})

@login_required
@phan_quyen(roles=['admin'])
def them_user(request):
    if request.method == 'POST':
        form = UserForm(request.POST)
        if form.is_valid():
            # ĐÃ SỬA: Chỉ cần 1 lệnh form.save() là form tự lo liệu phân quyền và mật khẩu
            form.save() 
            return redirect('ql_nhan_vien')
    else: 
        form = UserForm()
    return render(request, 'users/them_user.html', {'form': form})

@login_required
@phan_quyen(roles=['admin'])
def sua_user(request, id):
    user = get_object_or_404(User, id=id)
    form = UserForm(request.POST or None, instance=user)
    if form.is_valid():
        # ĐÃ SỬA: Bỏ commit=False đi để form kích hoạt lưu UserProfile
        u = form.save() 
        return redirect('ql_nhan_vien' if u.is_staff else 'ql_khach_hang')
    return render(request, 'users/sua_user.html', {'form': form})

@login_required
@phan_quyen(roles=['admin'])
def xoa_user(request, id):
    user = get_object_or_404(User, id=id)
    is_staff = user.is_staff 
    if request.user.id != user.id: 
        user.delete()
        messages.success(request, "Đã xóa tài khoản thành công!")
    return redirect('ql_nhan_vien' if is_staff else 'ql_khach_hang')

@login_required
@phan_quyen(roles=['admin','quan_ly'])
def ql_nhan_vien(request):
    danh_sach = User.objects.filter(is_staff=True).order_by('-date_joined')
    context = {'danh_sach': danh_sach, 'title': 'Quản lý Nhân Viên', 'icon': 'bi-person-vcard', 'show_add_button': True}
    return render(request, 'users/list_user.html', context)

@login_required
@phan_quyen(roles=['admin'])
def ql_khach_hang(request):
    danh_sach = User.objects.filter(is_staff=False).order_by('-date_joined')
    context = {'danh_sach': danh_sach, 'title': 'Quản lý Khách Hàng', 'icon': 'bi-people', 'show_add_button': False}
    return render(request, 'users/list_user.html', context)

# --- Các trang đăng nhập / đăng xuất không bị ảnh hưởng ---
def dang_ky_view(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            user.save()
            login(request, user)
            return redirect('trang_chu')
    else: form = RegisterForm()
    return render(request, 'registration/register.html', {'form': form})

def logout_view(request):
    logout(request)
    messages.success(request, "Bạn đã đăng xuất thành công!")
    return redirect('trang_chu')

@login_required(login_url='login')
def tai_khoan(request):
    don_hang_list = DonHang.objects.filter(khach_hang=request.user).order_by('-ngay_dat')
    return render(request, 'users/tai_khoan.html', {'don_hang_list': don_hang_list})

@login_required
def profile(request):
    from .models import UserProfile
    user_profile, created = UserProfile.objects.get_or_create(user=request.user)
    form = UserProfileForm(request.POST or None, request.FILES or None, instance=user_profile)
    if form.is_valid():
        form.save()
        messages.success(request, "Cập nhật thành công")
        return redirect('profile')
    return render(request, 'user/profile.html', {'form': form})


# ==========================================
# 6. QUẢN LÝ DANH MỤC & 7. QUẢN LÝ CỬA HÀNG
# ==========================================
@login_required
@phan_quyen(roles=['admin', 'quan_ly'])
def quan_ly_danh_muc(request):
    danh_sach_dm = DanhMuc.objects.all().order_by('-id')
    return render(request, 'category/quan_ly_danh_muc.html', {'danh_sach_dm': danh_sach_dm})

@login_required
@phan_quyen(roles=['admin', 'quan_ly'])
def them_danh_muc(request):
    if request.method == 'POST':
        ten_dm = request.POST.get('ten_danh_muc')
        if ten_dm: DanhMuc.objects.create(ten_danh_muc=ten_dm)
    return redirect('quan_ly_danh_muc')

@login_required
@phan_quyen(roles=['admin', 'quan_ly'])
def sua_danh_muc(request, pk):
    dm = get_object_or_404(DanhMuc, pk=pk)
    if request.method == 'POST':
        ten_dm = request.POST.get('ten_danh_muc')
        if ten_dm: dm.ten_danh_muc = ten_dm; dm.save()
    return redirect('quan_ly_danh_muc')

@login_required
@phan_quyen(roles=['admin', 'quan_ly'])
def xoa_danh_muc(request, pk):
    dm = get_object_or_404(DanhMuc, pk=pk)
    if not dm.xedien_set.exists(): dm.delete()
    return redirect('quan_ly_danh_muc')

def danh_muc_xe(request, loai_xe):
    return render(request, 'xe/danh_muc.html', {'danh_sach': XeDien.objects.filter(trang_thai=True), 'loai_xe': loai_xe})

@login_required
@phan_quyen(roles=['admin', 'quan_ly'])
def quan_ly_cua_hang(request):
    return render(request, 'cua_hang/quan_ly_cua_hang.html', {'danh_sach_ch': CuaHang.objects.all().order_by('-id')})

@login_required
@phan_quyen(roles=['admin', 'quan_ly'])
def them_cua_hang(request):
    if request.method == 'POST':
        lat = request.POST.get('lat')
        lon = request.POST.get('lon')
        CuaHang.objects.create(
            ten_cua_hang=request.POST.get('ten_cua_hang'), dia_chi=request.POST.get('dia_chi'), so_dien_thoai=request.POST.get('so_dien_thoai'),
            lat=float(lat) if lat else None, lon=float(lon) if lon else None, hinh_anh=request.FILES.get('hinh_anh')
        )
    return redirect('quan_ly_cua_hang')

@login_required
@phan_quyen(roles=['admin', 'quan_ly'])
def sua_cua_hang(request, pk):
    ch = get_object_or_404(CuaHang, pk=pk)
    if request.method == 'POST':
        ch.ten_cua_hang = request.POST.get('ten_cua_hang')
        ch.dia_chi = request.POST.get('dia_chi')
        ch.so_dien_thoai = request.POST.get('so_dien_thoai')
        lat, lon = request.POST.get('lat'), request.POST.get('lon')
        if lat: ch.lat = float(lat)
        if lon: ch.lon = float(lon)
        if 'hinh_anh' in request.FILES: ch.hinh_anh = request.FILES.get('hinh_anh')
        ch.save()
    return redirect('quan_ly_cua_hang')

@login_required
@phan_quyen(roles=['admin', 'quan_ly'])
def xoa_cua_hang(request, pk):
    ch = get_object_or_404(CuaHang, pk=pk)
    if not ch.xedien_set.exists(): ch.delete()
    return redirect('quan_ly_cua_hang')


# ==========================================
# 8. KHO HÀNG (Cả 3 quyền đều vào được)
# ==========================================
@login_required
@phan_quyen(roles=['admin', 'quan_ly', 'nhan_vien'])
def quan_ly_kho(request):
    return render(request, 'kho/danh_sach.html', {'kho': KhoHang.objects.all()})


@login_required
@phan_quyen(roles=['admin', 'quan_ly', 'nhan_vien'])
def them_kho(request):
    if request.method == 'POST':
        form = PhieuNhapKhoForm(request.POST)
        formset = ChiTietPhieuNhapFormSet(request.POST)
        
        if form.is_valid() and formset.is_valid():
            # 1. Lưu Phiếu Nhập
            phieu = form.save(commit=False)
            phieu.nhan_vien_nhap = request.user
            phieu.save()
            
            # 2. Lưu Chi tiết & Tự động cộng vào Kho gốc
            chi_tiets = formset.save(commit=False)
            for ct in chi_tiets:
                ct.phieu_nhap = phieu
                ct.save()
                
                # CỘNG DỒN TỰ ĐỘNG:
                kho, created = KhoHang.objects.get_or_create(xe=ct.xe, cua_hang=phieu.cua_hang)
                kho.so_luong += ct.so_luong
                kho.save()
                
            # Xử lý các dòng bị user bấm Xóa trên form
            for obj in formset.deleted_objects:
                obj.delete()

            messages.success(request, f"Đã nhập lô hàng mới vào {phieu.cua_hang.ten_cua_hang} thành công!")
            return redirect('quan_ly_kho')
    else:
        form = PhieuNhapKhoForm()
        formset = ChiTietPhieuNhapFormSet()
        
    return render(request, 'kho/form.html', {'form': form, 'formset': formset})



# ==========================================
# 9. PHIÊN SẠC & FEEDBACK
# ==========================================
@login_required
def danh_sach_phien_sac(request):
    phien = PhienSac.objects.filter(user=request.user)
    return render(request, 'tram_sac/danh_sach.html', {'phien': phien})

@login_required
def bat_dau_sac(request, tram_id):
    tram = get_object_or_404(TramSac, id=tram_id)
    PhienSac.objects.create(user=request.user, tram_sac=tram, thoi_gian_bat_dau=timezone.now())
    return redirect('danh_sach_phien_sac')

@login_required(login_url='login')
def gui_feedback(request):
    form = FeedbackForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        xe_duoc_chon = form.cleaned_data.get('xe')
        da_danh_gia = Feedback.objects.filter(user=request.user, xe=xe_duoc_chon).exists()
        if da_danh_gia: return redirect('gui_feedback')
        fb = form.save(commit=False)
        fb.user = request.user
        fb.save()
        return redirect('chi_tiet_xe', xe_id=xe_duoc_chon.id) 
    return render(request, 'feedback/form.html', {'form': form})

@login_required
@phan_quyen(roles=['admin', 'quan_ly'])
def quan_ly_feedback(request):
    danh_sach = Feedback.objects.all().order_by('-id')
    return render(request, 'feedback/admin_feedback.html', {'feedbacks': danh_sach})

@login_required
@phan_quyen(roles=['admin', 'quan_ly'])
def xoa_feedback(request, feedback_id):
    get_object_or_404(Feedback, id=feedback_id).delete()
    return redirect('quan_ly_feedback')


# ==========================================
# CÁC API & TỰ ĐỘNG KHÔNG ĐỔI
# ==========================================
@receiver(post_save, sender=DonHang)
def tru_kho_khi_dat_hang(sender, instance, created, **kwargs):
    if created and instance.trang_thai in ['Deposit Paid', 'Paid']:  
        try:
            kho = KhoHang.objects.get(xe=instance.xe, cua_hang=instance.xe.cua_hang)
            if kho.so_luong >= 1:
                kho.so_luong -= 1
                kho.save()
                if kho.so_luong == 0:
                    instance.xe.trang_thai = False
                    instance.xe.save()
        except KhoHang.DoesNotExist: pass

@csrf_exempt
def get_nearest_tram(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            lat, lon = float(data.get('lat')), float(data.get('lon'))
            radius_km = float(data.get('radius', 20000)) / 1000
        except: return JsonResponse({'error': 'Invalid'}, status=400)

        nearby_trams = []
        for tram in TramSac.objects.filter(trang_thai=True):
            try:
                dist = haversine(lat, lon, float(tram.lat), float(tram.lon))
                if dist <= radius_km:
                    nearby_trams.append({
                        'ten_tram': tram.ten_tram, 'dia_chi': tram.dia_chi, 'cong_suat': tram.cong_suat,
                        'loai_sac': tram.loai_sac, 'lat': float(tram.lat), 'lon': float(tram.lon),
                        'hinh_anh': tram.hinh_anh.url if tram.hinh_anh else '', 'distance': round(dist, 2)
                    })
            except: continue
        nearby_trams.sort(key=lambda x: x['distance'])
        if nearby_trams: return JsonResponse({'trams': nearby_trams})
        return JsonResponse({'error': 'Không có trạm'}, status=404)
    return JsonResponse({'error': 'Method not allowed'}, status=405)

def tram_api(request):
    danh_sach_tram = [{'id': t.id, 'ten_tram': t.ten_tram, 'lat': float(t.lat), 'lon': float(t.lon), 'dia_chi': t.dia_chi, 'loai_sac': t.loai_sac, 'cong_suat': t.cong_suat, 'hinh_anh': t.hinh_anh.url if t.hinh_anh else ''} for t in TramSac.objects.filter(trang_thai=True)]
    return JsonResponse(danh_sach_tram, safe=False)

def cua_hang_api(request):
    danh_sach_ch = []
    for ch in CuaHang.objects.filter(trang_thai=True):
        try:
            danh_sach_ch.append({'id': ch.id, 'ten_cua_hang': ch.ten_cua_hang, 'lat': float(ch.lat), 'lon': float(ch.lon), 'dia_chi': ch.dia_chi, 'sdt': ch.so_dien_thoai, 'hinh_anh': ch.hinh_anh.url if hasattr(ch, 'hinh_anh') and ch.hinh_anh else ''})
        except: continue
    return JsonResponse(danh_sach_ch, safe=False)

@csrf_exempt 
def ket_thuc_sac_api(request):
    if request.method == 'POST':
        if not request.user.is_authenticated: return JsonResponse({'status': 'error', 'message': 'Vui lòng đăng nhập'})
        try:
            data = json.loads(request.body)
            tram = TramSac.objects.get(id=data['tram_id'])
            bat_dau, ket_thuc = parse_datetime(data['thoi_gian_bat_dau']), parse_datetime(data['thoi_gian_ket_thuc'])
            PhienSac.objects.create(user=request.user, tram_sac=tram, thoi_gian_bat_dau=bat_dau, thoi_gian_ket_thuc=ket_thuc, dien_nang_tieu_thu=data['tong_thoi_gian'], tong_tien=data['tong_tien'], trang_thai='Hoan thanh')
            return JsonResponse({'status': 'success', 'message': 'Đã lưu'})
        except Exception as e: return JsonResponse({'status': 'error', 'message': str(e)})
    return JsonResponse({'status': 'error'})

@login_required(login_url='login') 
def lich_su_sac(request):
    danh_sach_phien = PhienSac.objects.filter(user=request.user).order_by('-thoi_gian_bat_dau')
    return render(request, 'tram_sac/lich_su_sac.html', {'phien': danh_sach_phien})

@login_required(login_url='login')
def lich_su_sac_khach_hang(request):
    danh_sach_phien = PhienSac.objects.filter(user=request.user).order_by('-thoi_gian_bat_dau')
    return render(request, 'users/user_sac.html', {'phien': danh_sach_phien})