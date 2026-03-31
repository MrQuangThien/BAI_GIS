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

# --- QUAN TRỌNG: Import đúng nơi bạn khai báo ---
from .models import TramSac, XeDien, CuaHang, XeDienForm 
from .forms import RegisterForm, UserForm

from django.db.models import Q
from django.shortcuts import render, get_object_or_404, redirect

# ==========================================
# 1. GIAO DIỆN TRANG CHỦ
# ==========================================
# 1. Hàm hiển thị danh sách sản phẩm ở trang chủ
# CẬP NHẬT hàm trang chủ để lấy đúng xe Nổi bật và Sắp về
def trang_chu(request):
    xe_noi_bat = XeDien.objects.filter(noi_bat=True)
    xe_sap_ve = XeDien.objects.filter(sap_ve=True)
    context = {
        'xe_noi_bat': xe_noi_bat,
        'xe_sap_ve': xe_sap_ve,
    }
    return render(request, 'trang_chu.html', context)

# -----------------------------------------
# THÊM 3 HÀM MỚI NÀY VÀO DƯỚI CÙNG
# -----------------------------------------

# 1. View Xử lý Tìm kiếm
def tim_kiem(request):
    tu_khoa = request.GET.get('q', '')
    if tu_khoa:
        # Tìm xe có Tên hoặc Hãng sản xuất chứa từ khóa người dùng gõ
        ket_qua = XeDien.objects.filter(
            Q(ten_xe__icontains=tu_khoa) | Q(hang_san_xuat__icontains=tu_khoa)
        )
    else:
        ket_qua = XeDien.objects.none()
    
    # Tạm thời trả về trang chủ nếu chưa có template tim_kiem.html
    return render(request, 'tim_kiem.html', {'ket_qua': ket_qua, 'tu_khoa': tu_khoa})

# 2. View Xử lý Danh mục
def danh_muc_xe(request, loai_xe):
    # Lọc xe theo loại (Tạm lấy tất cả, sau này bạn thêm trường loai_xe vào database thì filter sau)
    danh_sach = XeDien.objects.all() 
    return render(request, 'danh_muc.html', {'danh_sach': danh_sach, 'loai_xe': loai_xe})

# 3. View Xử lý form Đặt hàng / Đặt cọc
def tao_don_hang(request, xe_id):
    xe = get_object_or_404(XeDien, id=xe_id)
    # Lấy tham số type từ URL (ví dụ: type=preorder cho xe sắp về)
    loai_don = request.GET.get('type', 'normal') 
    
    return render(request, 'tao_don_hang.html', {'xe': xe, 'loai_don': loai_don})

# 2. Hàm hiển thị chi tiết 1 sản phẩm
def chi_tiet_xe(request, xe_id):
    # Tìm đúng con xe theo ID, không thấy thì báo lỗi 404
    xe = get_object_or_404(XeDien, id=xe_id)
    return render(request, 'chi_tiet_xe.html', {'xe': xe})
# ==========================================
# 2. GIAO DIỆN BẢN ĐỒ
# ==========================================
def haversine(lat1, lon1, lat2, lon2):
    """Tính khoảng cách km giữa 2 điểm (Haversine formula)"""
    R = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return round(R * c, 2)

def ban_do_tram_sac(request):
    trams = TramSac.objects.filter(trang_thai=True)
    default_lat, default_lon = 10.7769, 106.7009
    m = folium.Map(location=[default_lat, default_lon], zoom_start=12, tiles='CartoDB positron')

    for tram in trams:
        try:
            folium.Marker(
                location=[float(tram.lat), float(tram.lon)],
                popup=f"<b>{tram.ten_tram}</b><br>{tram.dia_chi}<br>Công suất: {tram.cong_suat} kW<br>Loại: {tram.loai_sac}",
                tooltip=tram.ten_tram,
                icon=folium.Icon(color='blue', icon='plug', prefix='fa')
            ).add_to(m)
        except (ValueError, TypeError):
            continue

    LocateControl(auto_start=False, keepCurrentPosition=True).add_to(m)
    all_trams = list(trams.values('id', 'ten_tram', 'lat', 'lon', 'dia_chi'))

    context = {
        'map_html': m._repr_html_(),
        'user_location_note': "Click nút định vị hoặc click trên bản đồ để chọn vị trí",
        'all_trams': all_trams,
    }
    return render(request, 'map.html', context)

@csrf_exempt
def get_nearest_tram(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            lat = float(data.get('lat'))
            lon = float(data.get('lon'))
            radius_km = float(data.get('radius', 20000)) / 1000
        except (TypeError, ValueError, json.JSONDecodeError):
            return JsonResponse({'error': 'Invalid coordinates'}, status=400)

        trams = TramSac.objects.filter(trang_thai=True)
        if not trams.exists():
            return JsonResponse({'error': 'No charging stations found'}, status=404)

        nearby_trams = []
        for tram in trams:
            try:
                dist = haversine(lat, lon, float(tram.lat), float(tram.lon))
                if dist <= radius_km:
                    nearby_trams.append({
                        'ten_tram': tram.ten_tram,
                        'dia_chi': tram.dia_chi,
                        'cong_suat': tram.cong_suat,
                        'loai_sac': tram.loai_sac,
                        'lat': float(tram.lat),
                        'lon': float(tram.lon),
                        # ĐÃ SỬA LẠI: Lấy đường dẫn URL của file ảnh tải lên
                       'hinh_anh': tram.hinh_anh.url if tram.hinh_anh else '',
                        'distance': round(dist, 2)
                    })
            except (ValueError, TypeError):
                continue

        nearby_trams.sort(key=lambda x: x['distance'])

        if nearby_trams:
            return JsonResponse({'trams': nearby_trams})
        else:
            return JsonResponse({'error': 'Không có trạm nào trong bán kính này'}, status=404)

    return JsonResponse({'error': 'Invalid request method'}, status=405)


# ==========================================
# 3. GIAO DIỆN TRANG QUẢN TRỊ
# ==========================================
def is_admin(user):
    return user.is_superuser

def is_staff(user):
    return user.is_staff or user.is_superuser

@login_required
@user_passes_test(is_staff)
def admin_dashboard(request):
    tong_so_tram = TramSac.objects.count()
    tram_hoat_dong = TramSac.objects.filter(trang_thai=True).count()
    tram_bao_tri = tong_so_tram - tram_hoat_dong
    tram_moi_nhat = TramSac.objects.all().order_by('-id')[:5]

    context = {
        'tong_so_tram': tong_so_tram,
        'tram_hoat_dong': tram_hoat_dong,
        'tram_bao_tri': tram_bao_tri,
        'tram_moi_nhat': tram_moi_nhat,
    }
    return render(request, 'dashboard.html', context)

@login_required
@user_passes_test(is_staff)
def quan_ly_tram_sac(request):
    danh_sach_tram = TramSac.objects.all().order_by('-id')
    return render(request, 'quan_ly_tram_sac.html', {'danh_sach_tram': danh_sach_tram})

@login_required
@user_passes_test(is_staff)
def them_tram_sac(request):
    if request.method == 'POST':
        ten_tram = request.POST.get('ten_tram')
        dia_chi = request.POST.get('dia_chi')
        cong_suat = request.POST.get('cong_suat')
        loai_sac = request.POST.get('loai_sac')
        lat = request.POST.get('lat')
        lon = request.POST.get('lon')
        trang_thai = request.POST.get('trang_thai') == 'on'
        
        # ĐÃ SỬA LẠI: Lấy file từ request.FILES thay vì request.POST
        hinh_anh = request.FILES.get('hinh_anh')

        TramSac.objects.create(
            ten_tram=ten_tram,
            dia_chi=dia_chi,
            cong_suat=cong_suat,
            loai_sac=loai_sac,
            lat=lat,
            lon=lon,
            trang_thai=trang_thai,
            hinh_anh=hinh_anh 
        )
        return redirect('quan_ly_tram_sac')
        
    return redirect('quan_ly_tram_sac')

@login_required
@user_passes_test(is_staff)
def xoa_tram_sac(request, tram_id):
    tram = get_object_or_404(TramSac, id=tram_id)
    tram.delete()
    return redirect('quan_ly_tram_sac')

@login_required
@user_passes_test(is_staff)
def sua_tram_sac(request, tram_id):
    tram = get_object_or_404(TramSac, id=tram_id)
    
    if request.method == 'POST':
        tram.ten_tram = request.POST.get('ten_tram')
        tram.dia_chi = request.POST.get('dia_chi')
        tram.cong_suat = request.POST.get('cong_suat')
        tram.loai_sac = request.POST.get('loai_sac')
        tram.lat = request.POST.get('lat')
        tram.lon = request.POST.get('lon')
        tram.trang_thai = request.POST.get('trang_thai') == 'on'
        
        # ĐÃ SỬA LẠI: Kiểm tra xem user có tải file ảnh mới lên không, có thì mới lưu đè
        if 'hinh_anh' in request.FILES:
            tram.hinh_anh = request.FILES.get('hinh_anh')
        
        tram.save()
        return redirect('quan_ly_tram_sac')
        
    return redirect('quan_ly_tram_sac')


# ==========================================
# 4. QUẢN LÝ XE ĐIỆN VÀ USER
# ==========================================
@login_required
@user_passes_test(is_staff)
def danh_sach_xe(request):
    tat_ca_xe = XeDien.objects.all()
    return render(request, 'danh_sach_xe.html', {'tat_ca_xe': tat_ca_xe})

@login_required
@user_passes_test(is_staff)
def them_xe(request):
    # NHỚ CÓ request.FILES Ở ĐÂY
    form = XeDienForm(request.POST or None, request.FILES or None)
    if form.is_valid():
        form.save()
        return redirect('danh_sach_xe')
    return render(request, 'xe_form.html', {'form': form, 'title': 'Thêm Xe Mới'})


def sua_xe(request, pk):
    xe = get_object_or_404(XeDien, pk=pk)
    # NHỚ CÓ request.FILES Ở ĐÂY
    form = XeDienForm(request.POST or None, request.FILES or None, instance=xe)
    if form.is_valid():
        form.save()
        return redirect('danh_sach_xe')
    return render(request, 'xe_form.html', {'form': form, 'title': 'Chỉnh Sửa Xe'})

@login_required
@user_passes_test(is_staff)
def xoa_xe(request, pk):
    xe = get_object_or_404(XeDien, pk=pk)
    if request.method == 'POST':
        xe.delete()
        return redirect('danh_sach_xe')
    return render(request, 'xe_confirm_delete.html', {'xe': xe})

@login_required
@user_passes_test(is_admin)
def list_user(request):
    users = User.objects.all()
    return render(request, 'users/list_user.html', {'users': users})

@login_required
@user_passes_test(is_admin)
def them_user(request):
    if request.method == 'POST':
        form = UserForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            user.save()
            return redirect('list_user')
    else:
        form = UserForm()
    return render(request, 'users/them_user.html', {'form': form})

@login_required
@user_passes_test(is_admin)
def sua_user(request, id):
    user = get_object_or_404(User, id=id)
    form = UserForm(request.POST or None, instance=user)
    if form.is_valid():
        u = form.save(commit=False)
        if form.cleaned_data.get('password'):
            u.set_password(form.cleaned_data['password'])
        u.save()
        return redirect('list_user')
    return render(request, 'users/sua_user.html', {'form': form})

@login_required
@user_passes_test(is_admin)
def xoa_user(request, id):
    user = get_object_or_404(User, id=id)
    if request.user.id == user.id:
        return redirect('list_user')
    user.delete()
    return redirect('list_user')

def logout_view(request):
    logout(request)
    messages.success(request, "Bạn đã đăng xuất thành công!")
    return redirect('trang_chu')

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
        
    return render(request, 'register.html', {'form': form})