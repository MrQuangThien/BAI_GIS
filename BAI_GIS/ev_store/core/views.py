import json
from math import radians, sin, cos, sqrt, atan2
import folium
from folium.plugins import LocateControl

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.contrib.auth import login, logout 
from django.contrib import messages
from django.core.mail import send_mail
from django.db.models import Q, Count

# --- 1. IMPORT MODELS ---
from .models import TramSac, XeDien, CuaHang, XeDienForm, DonHang, DanhMuc

# --- 2. IMPORT FORMS ---
from .forms import UserForm, RegisterForm, DonHangForm, DonHangTaiQuayForm


# ==========================================
# 1. GIAO DIỆN TRANG CHỦ & CÁC TRANG CHUNG
# ==========================================
def trang_chu(request):
    xe_noi_bat = XeDien.objects.filter(noi_bat=True, trang_thai=True)
    xe_sap_ve = XeDien.objects.filter(sap_ve=True, trang_thai=True)
    context = {'xe_noi_bat': xe_noi_bat, 'xe_sap_ve': xe_sap_ve}
    # Đã sửa đường dẫn: pages/
    return render(request, 'pages/trang_chu.html', context)

def tim_kiem(request):
    tu_khoa = request.GET.get('q', '')
    if tu_khoa:
        ket_qua = XeDien.objects.filter(
            Q(ten_xe__icontains=tu_khoa) | Q(hang_san_xuat__icontains=tu_khoa)
        )
    else:
        ket_qua = XeDien.objects.none()
    # Đã sửa đường dẫn: pages/
    return render(request, 'pages/tim_kiem.html', {'ket_qua': ket_qua, 'tu_khoa': tu_khoa})

@login_required
@user_passes_test(lambda u: u.is_staff or u.is_superuser)
def admin_dashboard(request):
    tong_so_tram = TramSac.objects.count()
    tram_hoat_dong = TramSac.objects.filter(trang_thai=True).count()
    tram_bao_tri = tong_so_tram - tram_hoat_dong
    tram_moi_nhat = TramSac.objects.all().order_by('-id')[:5]
    danh_muc_stats = DanhMuc.objects.annotate(so_luong_xe=Count('xedien'))

    context = {
        'tong_so_tram': tong_so_tram, 'tram_hoat_dong': tram_hoat_dong,
        'tram_bao_tri': tram_bao_tri, 'tram_moi_nhat': tram_moi_nhat,
        'danh_muc_stats': danh_muc_stats,
    }
    # Đã sửa đường dẫn: pages/
    return render(request, 'pages/dashboard.html', context)


# ==========================================
# 2. GIAO DIỆN XE ĐIỆN & CỬA HÀNG (Dành cho cả Khách & Admin)
# ==========================================
def danh_sach_san_pham(request):
    danh_sach = XeDien.objects.filter(trang_thai=True)
    cac_hang_xe = XeDien.objects.values_list('hang_san_xuat', flat=True).distinct()
    cac_phan_khuc = DanhMuc.objects.all()
    
    hang_id = request.GET.get('thuong_hieu')
    pk_id = request.GET.get('phan_khuc')
    
    if hang_id: danh_sach = danh_sach.filter(hang_san_xuat__iexact=hang_id)
    if pk_id: danh_sach = danh_sach.filter(danh_muc__id=pk_id)
        
    context = {
        'danh_sach_xe': danh_sach, 'cac_hang_xe': cac_hang_xe,
        'cac_phan_khuc': cac_phan_khuc, 'hang_chon': hang_id,
        'pk_chon': int(pk_id) if pk_id else None,
    }
    # Đã sửa đường dẫn: xe/
    return render(request, 'xe/san_pham.html', context)

def chi_tiet_xe(request, xe_id):
    xe = get_object_or_404(XeDien, id=xe_id)
    # Đã sửa đường dẫn: xe/
    return render(request, 'xe/chi_tiet_xe.html', {'xe': xe})

@login_required
@user_passes_test(lambda u: u.is_staff or u.is_superuser)
def danh_sach_xe(request):
    tat_ca_xe = XeDien.objects.all()
    # Đã sửa đường dẫn: xe/
    return render(request, 'xe/danh_sach_xe.html', {'tat_ca_xe': tat_ca_xe})

@login_required
@user_passes_test(lambda u: u.is_staff or u.is_superuser)
def them_xe(request):
    form = XeDienForm(request.POST or None, request.FILES or None)
    if form.is_valid():
        form.save()
        return redirect('danh_sach_xe')
    # Đã sửa đường dẫn: xe/
    return render(request, 'xe/xe_form.html', {'form': form, 'title': 'Thêm Xe Mới'})

@login_required
@user_passes_test(lambda u: u.is_staff or u.is_superuser)
def sua_xe(request, pk):
    xe = get_object_or_404(XeDien, pk=pk)
    form = XeDienForm(request.POST or None, request.FILES or None, instance=xe)
    if form.is_valid():
        form.save()
        return redirect('danh_sach_xe')
    # Đã sửa đường dẫn: xe/
    return render(request, 'xe/xe_form.html', {'form': form, 'title': 'Chỉnh Sửa Xe'})

@login_required
@user_passes_test(lambda u: u.is_staff or u.is_superuser)
def xoa_xe(request, pk):
    xe = get_object_or_404(XeDien, pk=pk)
    if request.method == 'POST':
        xe.delete()
        return redirect('danh_sach_xe')
    # Đã sửa đường dẫn: xe/
    return render(request, 'xe/xe_confirm_delete.html', {'xe': xe})


# ==========================================
# 3. GIAO DIỆN BẢN ĐỒ & TRẠM SẠC (GIS)
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
        except (ValueError, TypeError): continue

    LocateControl(auto_start=False, keepCurrentPosition=True).add_to(m)
    context = {'map_html': m._repr_html_(), 'all_trams': list(trams.values('id', 'ten_tram', 'lat', 'lon', 'dia_chi'))}
    # Đã sửa đường dẫn: tram_sac/
    return render(request, 'tram_sac/map.html', context)

@login_required
@user_passes_test(lambda u: u.is_staff or u.is_superuser)
def quan_ly_tram_sac(request):
    danh_sach_tram = TramSac.objects.all().order_by('-id')
    # Đã sửa đường dẫn: tram_sac/
    return render(request, 'tram_sac/quan_ly_tram_sac.html', {'danh_sach_tram': danh_sach_tram})

@login_required
@user_passes_test(lambda u: u.is_staff or u.is_superuser)
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
@user_passes_test(lambda u: u.is_staff or u.is_superuser)
def xoa_tram_sac(request, tram_id):
    get_object_or_404(TramSac, id=tram_id).delete()
    return redirect('quan_ly_tram_sac')

@login_required
@user_passes_test(lambda u: u.is_staff or u.is_superuser)
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

@csrf_exempt
def get_nearest_tram(request):
    # (API GIS: Không có render template nên giữ nguyên logic)
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


# ==========================================
# 4. QUẢN LÝ ĐƠN HÀNG
# ==========================================
# Tìm hàm tao_don_hang và cập nhật lại
def tao_don_hang(request, xe_id):
    xe = get_object_or_404(XeDien, id=xe_id)
    # Xác định loại mặc định dựa vào tình trạng xe
    loai_mac_dinh = 'B' if xe.sap_ve else 'A'

    if request.method == 'POST':
        # QUAN TRỌNG: Phải truyền xe=xe vào để Form biết đường xử lý
        form = DonHangForm(request.POST, xe=xe) 
        if form.is_valid():
            don_hang = form.save(commit=False)
            don_hang.xe = xe
            if request.user.is_authenticated: 
                don_hang.khach_hang = request.user

            # Xử lý trạng thái và tổng tiền
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
            # Có thể thêm dòng thông báo ở đây
            messages.success(request, "Đặt hàng thành công! Chúng tôi sẽ liên hệ với bạn sớm nhất.")
            return redirect('trang_chu') 
    else:
        # QUAN TRỌNG: Cũg phải truyền xe=xe vào đây
        form = DonHangForm(initial={'loai_don': loai_mac_dinh}, xe=xe)
    

    return render(request, 'donhang/tao_don_hang.html', {'form': form, 'xe': xe})

@login_required
def danh_sach_don_hang(request):
    danh_sach = DonHang.objects.all().order_by('-ngay_dat')
    # Giữ nguyên đường dẫn đã chuẩn: donhang/
    return render(request, 'donhang/danh_sach.html', {'danh_sach_don_hang': danh_sach})

@login_required
def chi_tiet_don_hang(request, don_id):
    don_hang = get_object_or_404(DonHang, id=don_id)
    if request.method == 'POST':
        trang_thai_moi = request.POST.get('trang_thai')
        if trang_thai_moi:
            don_hang.trang_thai = trang_thai_moi
            don_hang.save()
            messages.success(request, 'Cập nhật trạng thái đơn hàng thành công!')
            return redirect('chi_tiet_don_hang', don_id=don_hang.id)

    # Giữ nguyên đường dẫn đã chuẩn: donhang/
    return render(request, 'donhang/chi_tiet.html', {'don_hang': don_hang, 'trang_thai_choices': DonHang.TRANG_THAI_CHOICES})

@login_required
def tao_don_hang_offline(request):
    if request.method == 'POST':
        form = DonHangTaiQuayForm(request.POST)
        if form.is_valid():
            don_hang = form.save(commit=False)
            if don_hang.loai_don == 'D': don_hang.so_tien_tra_truoc = 0
            don_hang.save()
            messages.success(request, f'Đã tạo đơn hàng thành công cho khách {don_hang.ho_ten}!')
            return redirect('danh_sach_don_hang')
    else:
        form = DonHangTaiQuayForm(initial={'loai_don': 'D', 'trang_thai': 'Paid'})
    # Giữ nguyên đường dẫn đã chuẩn: donhang/
    return render(request, 'donhang/tao_moi.html', {'form': form})


# ==========================================
# 5. QUẢN LÝ USER VÀ AUTHENTICATION
# ==========================================
def dang_ky_view(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            user.save()
            login(request, user)
            return redirect('trang_chu')
    else:
        form = RegisterForm()
    # Đã sửa đường dẫn: registration/
    return render(request, 'registration/register.html', {'form': form})

def logout_view(request):
    logout(request)
    messages.success(request, "Bạn đã đăng xuất thành công!")
    return redirect('trang_chu')

@login_required
@user_passes_test(lambda u: u.is_superuser)
def list_user(request):
    # Giữ nguyên đường dẫn đã chuẩn: users/
    return render(request, 'users/list_user.html', {'users': User.objects.all()})

@login_required
@user_passes_test(lambda u: u.is_superuser)
def them_user(request):
    if request.method == 'POST':
        form = UserForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            user.save()
            return redirect('list_user')
    else: form = UserForm()
    # Giữ nguyên đường dẫn đã chuẩn: users/
    return render(request, 'users/them_user.html', {'form': form})

@login_required
@user_passes_test(lambda u: u.is_superuser)
def sua_user(request, id):
    user = get_object_or_404(User, id=id)
    form = UserForm(request.POST or None, instance=user)
    if form.is_valid():
        u = form.save(commit=False)
        if form.cleaned_data.get('password'): u.set_password(form.cleaned_data['password'])
        u.save()
        return redirect('list_user')
    # Giữ nguyên đường dẫn đã chuẩn: users/
    return render(request, 'users/sua_user.html', {'form': form})

@login_required
@user_passes_test(lambda u: u.is_superuser)
def xoa_user(request, id):
    user = get_object_or_404(User, id=id)
    if request.user.id != user.id: user.delete()
    return redirect('list_user')


# ==========================================
# 6. QUẢN LÝ DANH MỤC (CATEGORY)
# ==========================================
@login_required
@user_passes_test(lambda u: u.is_staff or u.is_superuser)
def quan_ly_danh_muc(request):
    danh_sach_dm = DanhMuc.objects.all().order_by('-id')
    return render(request, 'category/quan_ly_danh_muc.html', {'danh_sach_dm': danh_sach_dm})

@login_required
@user_passes_test(lambda u: u.is_staff or u.is_superuser)
def them_danh_muc(request):
    if request.method == 'POST':
        ten_dm = request.POST.get('ten_danh_muc')
        if ten_dm:
            DanhMuc.objects.create(ten_danh_muc=ten_dm)
            messages.success(request, f'Đã thêm kiểu dáng "{ten_dm}" thành công!')
    return redirect('quan_ly_danh_muc')

@login_required
@user_passes_test(lambda u: u.is_staff or u.is_superuser)
def sua_danh_muc(request, pk):
    dm = get_object_or_404(DanhMuc, pk=pk)
    if request.method == 'POST':
        ten_dm = request.POST.get('ten_danh_muc')
        if ten_dm:
            dm.ten_danh_muc = ten_dm
            dm.save()
            messages.success(request, 'Cập nhật tên kiểu dáng thành công!')
    return redirect('quan_ly_danh_muc')

@login_required
@user_passes_test(lambda u: u.is_staff or u.is_superuser)
def xoa_danh_muc(request, pk):
    dm = get_object_or_404(DanhMuc, pk=pk)
    # Kiểm tra xem có xe nào đang dùng danh mục này không
    if dm.xedien_set.exists():
        messages.error(request, f'Không thể xóa "{dm.ten_danh_muc}" vì đang có xe thuộc kiểu dáng này!')
    else:
        dm.delete()
        messages.success(request, 'Đã xóa kiểu dáng xe khỏi hệ thống!')
    return redirect('quan_ly_danh_muc')


def danh_muc_xe(request, loai_xe):
    danh_sach = XeDien.objects.filter(trang_thai=True)
    # Đã sửa đường dẫn: xe/
    return render(request, 'xe/danh_muc.html', {'danh_sach': danh_sach, 'loai_xe': loai_xe})

# ==========================================
# 7. QUẢN LÝ CỬA HÀNG (CHI NHÁNH)
# ==========================================
@login_required
@user_passes_test(lambda u: u.is_staff or u.is_superuser)
def quan_ly_cua_hang(request):
    danh_sach_ch = CuaHang.objects.all().order_by('-id')
    return render(request, 'cua_hang/quan_ly_cua_hang.html', {'danh_sach_ch': danh_sach_ch})

@login_required
@user_passes_test(lambda u: u.is_staff or u.is_superuser)
def them_cua_hang(request):
    if request.method == 'POST':
        ten = request.POST.get('ten_cua_hang')
        dia_chi = request.POST.get('dia_chi')
        so_dien_thoai = request.POST.get('so_dien_thoai')
        if ten:
            CuaHang.objects.create(ten_cua_hang=ten, dia_chi=dia_chi, so_dien_thoai=so_dien_thoai)
            messages.success(request, f'Đã thêm chi nhánh "{ten}" thành công!')
    return redirect('quan_ly_cua_hang')

@login_required
@user_passes_test(lambda u: u.is_staff or u.is_superuser)
def sua_cua_hang(request, pk):
    ch = get_object_or_404(CuaHang, pk=pk)
    if request.method == 'POST':
        ch.ten_cua_hang = request.POST.get('ten_cua_hang')
        ch.dia_chi = request.POST.get('dia_chi')
        ch.so_dien_thoai = request.POST.get('so_dien_thoai')
        ch.save()
        messages.success(request, 'Cập nhật thông tin chi nhánh thành công!')
    return redirect('quan_ly_cua_hang')

@login_required
@user_passes_test(lambda u: u.is_staff or u.is_superuser)
def xoa_cua_hang(request, pk):
    ch = get_object_or_404(CuaHang, pk=pk)
    if ch.xedien_set.exists():
        messages.error(request, f'Không thể xóa "{ch.ten_cua_hang}" vì đang có xe lưu kho tại đây!')
    else:
        ch.delete()
        messages.success(request, 'Đã xóa chi nhánh thành công!')
    return redirect('quan_ly_cua_hang')