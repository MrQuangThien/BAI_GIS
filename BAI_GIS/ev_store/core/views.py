import json
from math import radians, sin, cos, sqrt, atan2
import folium
from folium.plugins import LocateControl

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required, user_passes_test
# SỬA DÒNG NÀY: Import User chuẩn của Django
from django.contrib.auth.models import User 

from .models import TramSac, XeDien, CuaHang
from .models import XeDien, TramSac, CuaHang, XeDienForm, UserForm
# ==========================================
# 1. GIAO DIỆN TRANG CHỦ (Dùng trang_chu.html)
# ==========================================
def trang_chu(request):
    context = {
        'so_tram_sac': TramSac.objects.filter(trang_thai=True).count(),
        'tieu_de': 'EV Store - Xe Điện & Trạm Sạc',
    }
    return render(request, 'trang_chu.html', context)


# ==========================================
# 2. GIAO DIỆN BẢN ĐỒ (Dùng map.html)
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

from django.shortcuts import render, redirect, get_object_or_404
from .models import XeDien, XeDienForm

# ==========================================
# 3. GIAO DIỆN TRANG QUẢN TRỊ (Dùng dashboard.html)

def is_admin(user):
    return user.is_superuser

def is_staff(user):
    return user.is_staff or user.is_superuser




# ==========================================
@login_required
@user_passes_test(is_staff)
def admin_dashboard(request):
    # Đếm số liệu thống kê
    tong_so_tram = TramSac.objects.count()
    tram_hoat_dong = TramSac.objects.filter(trang_thai=True).count()
    tram_bao_tri = tong_so_tram - tram_hoat_dong
    
    # Lấy danh sách 5 trạm mới nhất đưa ra bảng
    tram_moi_nhat = TramSac.objects.all().order_by('-id')[:5]

    context = {
        'tong_so_tram': tong_so_tram,
        'tram_hoat_dong': tram_hoat_dong,
        'tram_bao_tri': tram_bao_tri,
        'tram_moi_nhat': tram_moi_nhat,
    }
    
    # Dòng này chính là lệnh báo cho Python biết phải lôi file dashboard.html ra để dùng
    return render(request, 'dashboard.html', context)
@login_required
@user_passes_test(is_staff)

def quan_ly_tram_sac(request):
    # Lấy toàn bộ danh sách trạm sạc, sắp xếp trạm mới nhất lên đầu
    danh_sach_tram = TramSac.objects.all().order_by('-id')
    
    context = {
        'danh_sach_tram': danh_sach_tram,
    }
    return render(request, 'quan_ly_tram_sac.html', context)
@login_required
@user_passes_test(is_staff)
def them_tram_sac(request):
    if request.method == 'POST':
        # Lấy dữ liệu từ form HTML gửi lên
        ten_tram = request.POST.get('ten_tram')
        dia_chi = request.POST.get('dia_chi')
        cong_suat = request.POST.get('cong_suat')
        loai_sac = request.POST.get('loai_sac')
        lat = request.POST.get('lat')
        lon = request.POST.get('lon')
        # Checkbox: nếu tích thì là 'on' (True), không tích là rỗng (False)
        trang_thai = request.POST.get('trang_thai') == 'on'

        # Lưu vào Database
        TramSac.objects.create(
            ten_tram=ten_tram,
            dia_chi=dia_chi,
            cong_suat=cong_suat,
            loai_sac=loai_sac,
            lat=lat,
            lon=lon,
            trang_thai=trang_thai
        )
        # Lưu xong tự động load lại trang danh sách
        return redirect('quan_ly_tram_sac')
        
    return redirect('quan_ly_tram_sac')
@login_required
@user_passes_test(is_staff)
def xoa_tram_sac(request, tram_id):
    # Tìm trạm theo ID, nếu có thì xóa
    tram = get_object_or_404(TramSac, id=tram_id)
    tram.delete()
    return redirect('quan_ly_tram_sac')
@login_required
@user_passes_test(is_staff)
def sua_tram_sac(request, tram_id):
    # Tìm trạm cần sửa theo ID
    tram = get_object_or_404(TramSac, id=tram_id)
    
    if request.method == 'POST':
        # Cập nhật thông tin mới từ form
        tram.ten_tram = request.POST.get('ten_tram')
        tram.dia_chi = request.POST.get('dia_chi')
        tram.cong_suat = request.POST.get('cong_suat')
        tram.loai_sac = request.POST.get('loai_sac')
        tram.lat = request.POST.get('lat')
        tram.lon = request.POST.get('lon')
        tram.trang_thai = request.POST.get('trang_thai') == 'on'
        
        # Lưu đè lên dữ liệu cũ
        tram.save()
        return redirect('quan_ly_tram_sac')
        
    return redirect('quan_ly_tram_sac')
@login_required
@user_passes_test(is_staff)
def danh_sach_xe(request):
    tat_ca_xe = XeDien.objects.all()
    # Đảm bảo tên file ở đây khớp chính xác với tên file trong thư mục
    return render(request, 'danh_sach_xe.html', {'tat_ca_xe': tat_ca_xe})
@login_required
@user_passes_test(is_staff)
def them_xe(request):
    form = XeDienForm(request.POST or None)
    if form.is_valid():
        form.save()
        return redirect('danh_sach_xe')
    return render(request, 'xe_form.html', {'form': form, 'title': 'Thêm Xe Mới'})

# Sửa xe
@login_required
@user_passes_test(is_staff)
def sua_xe(request, pk):
    xe = get_object_or_404(XeDien, pk=pk)
    form = XeDienForm(request.POST or None, instance=xe)
    if form.is_valid():
        form.save()
        return redirect('danh_sach_xe')
    return render(request, 'xe_form.html', {'form': form, 'title': 'Chỉnh Sửa Xe'})

# Xóa xe
@login_required
@user_passes_test(is_staff)
def xoa_xe(request, pk):
    xe = get_object_or_404(XeDien, pk=pk)
    if request.method == 'POST':
        xe.delete()
        return redirect('danh_sach_xe')
    return render(request, 'xe_confirm_delete.html', {'xe': xe})
def list_user(request):
    users = User.objects.all()
    return render(request, 'users/list_user.html', {'users': users})


@login_required
@user_passes_test(is_admin)
def list_user(request):
    # Bây giờ User.objects sẽ hoạt động vì đã import đúng từ django.contrib.auth
    users = User.objects.all()
    return render(request, 'users/list_user.html', {'users': users})

@login_required
@user_passes_test(is_admin)
def them_user(request):
    if request.method == 'POST':
        form = UserForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password']) # Mã hóa mật khẩu
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
        # Ngăn tự xóa chính mình
        return redirect('list_user')
    user.delete()
    return redirect('list_user')