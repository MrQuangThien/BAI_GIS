import json
from math import radians, sin, cos, sqrt, atan2
from datetime import timezone
from functools import wraps 
import folium
from folium.plugins import LocateControl

from django.http import HttpResponse
import openpyxl

from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth import login, logout 
from django.contrib import messages
from django.core.mail import send_mail
from django.db.models import Q, Count, Sum, Avg, Max
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.dateparse import parse_datetime

from .models import TramSac, XeDien, CuaHang, DonHang, DanhMuc, Feedback, KhoHang, PhienSac, AnhXeDien, PhieuNhapKho, ChiTietPhieuNhap, TinNhanChat

from .forms import XeDienForm, UserForm, RegisterForm, DonHangForm, DonHangTaiQuayForm, FeedbackForm, UserProfileForm, PhieuNhapKhoForm, ChiTietPhieuNhapFormSet

# ==========================================
# 0. DECORATOR PHÂN QUYỀN
# ==========================================
def phan_quyen(roles=[]):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper_func(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')
            
            user_role = 'khach_hang' 
            try:
                user_role = request.user.userprofile.vai_tro
            except:
                if request.user.is_staff:
                    user_role = 'nhan_vien'

            if request.user.is_superuser: 
                user_role = 'admin'

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
    xe_noi_bat_qs = XeDien.objects.filter(noi_bat=True, trang_thai=True)
    danh_sach_noi_bat = list(xe_noi_bat_qs)
    for xe in danh_sach_noi_bat:
        tong_ton = xe.kho_hang.aggregate(Sum('so_luong'))['so_luong__sum'] or 0
        xe.het_hang = (tong_ton <= 0 and not xe.sap_ve)
        
    xe_sap_ve = XeDien.objects.filter(sap_ve=True, trang_thai=True)
    form = FeedbackForm() 
    
    context = {
        'xe_noi_bat': danh_sach_noi_bat, 
        'xe_sap_ve': xe_sap_ve, 
        'form': form
    }
    return render(request, 'pages/trang_chu.html', context)

def tim_kiem(request):
    tu_khoa = request.GET.get('q', '')
    if tu_khoa:
        ket_qua_xe = XeDien.objects.filter(
            Q(ten_xe__icontains=tu_khoa) |
            Q(hang_san_xuat__icontains=tu_khoa) |
            Q(danh_muc__ten_danh_muc__icontains=tu_khoa) |
            Q(mo_ta__icontains=tu_khoa)
        ).distinct()
    else:
        ket_qua_xe = XeDien.objects.none()
        
    return render(request, 'pages/tim_kiem.html', {
        'ket_qua_xe': ket_qua_xe, 
        'tu_khoa': tu_khoa
    })

def gioi_thieu(request):
    danh_sach_cua_hang = CuaHang.objects.all().order_by('id') 
    return render(request, 'pages/gioi_thieu.html', {'danh_sach_cua_hang': danh_sach_cua_hang})

def chi_tiet_cua_hang(request, pk):
    cua_hang = get_object_or_404(CuaHang, pk=pk)
    return render(request, 'pages/chi_tiet_cua_hang.html', {'ch': cua_hang})

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
    danh_sach_xe = XeDien.objects.filter(trang_thai=True)
    cac_phan_khuc = DanhMuc.objects.all() 
    cac_hang_xe = XeDien.objects.filter(trang_thai=True).values_list('hang_san_xuat', flat=True).distinct()

    # 1. NHẬN CÁC YÊU CẦU TỪ FORM
    sort_by = request.GET.get('sort', '')
    tieu_chi = request.GET.get('tieu_chi', '')
    pk_chon = request.GET.get('phan_khuc', '')
    hang_chon = request.GET.get('thuong_hieu', '')
    
    # Nhận thêm biến Khoảng giá
    khoang_gia = request.GET.get('khoang_gia', '')
    gia_min = request.GET.get('gia_min', '')
    gia_max = request.GET.get('gia_max', '')

    # 2. XỬ LÝ LỌC
    if pk_chon:
        danh_sach_xe = danh_sach_xe.filter(danh_muc_id=pk_chon)
    if hang_chon:
        danh_sach_xe = danh_sach_xe.filter(hang_san_xuat=hang_chon)

    # Lọc theo Tiêu chí
    if tieu_chi == 'noi_bat': danh_sach_xe = danh_sach_xe.filter(noi_bat=True)
    elif tieu_chi == 'moi_ve': danh_sach_xe = danh_sach_xe.filter(moi_ve=True)
    elif tieu_chi == 'ban_chay': danh_sach_xe = danh_sach_xe.filter(ban_chay=True)

    # LỌC THEO GIÁ TIỀN
    if khoang_gia == 'duoi_500':
        danh_sach_xe = danh_sach_xe.filter(gia__lt=500000000)
    elif khoang_gia == '500_1000':
        danh_sach_xe = danh_sach_xe.filter(gia__gte=500000000, gia__lte=1000000000)
    elif khoang_gia == '1000_2000':
        danh_sach_xe = danh_sach_xe.filter(gia__gte=1000000000, gia__lte=2000000000)
    elif khoang_gia == 'tren_2000':
        danh_sach_xe = danh_sach_xe.filter(gia__gt=2000000000)

    # Lọc theo mức giá tự nhập (Ghi đè khoảng giá nếu khách có tự nhập)
    if gia_min and gia_min.isdigit():
        danh_sach_xe = danh_sach_xe.filter(gia__gte=int(gia_min))
    if gia_max and gia_max.isdigit():
        danh_sach_xe = danh_sach_xe.filter(gia__lte=int(gia_max))

    # Sắp xếp
    if sort_by == 'gia_tang': danh_sach_xe = danh_sach_xe.order_by('gia') 
    elif sort_by == 'gia_giam': danh_sach_xe = danh_sach_xe.order_by('-gia') 
    else: danh_sach_xe = danh_sach_xe.order_by('-id') 

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'count': danh_sach_xe.count()})

    context = {
        'danh_sach_xe': danh_sach_xe,
        'cac_phan_khuc': cac_phan_khuc,
        'cac_hang_xe': cac_hang_xe,
        'pk_chon': int(pk_chon) if pk_chon else None,
        'hang_chon': hang_chon,
        'tieu_chi': tieu_chi,
        'sort_by': sort_by,
        'khoang_gia': khoang_gia, # Truyền ra HTML để giữ sáng nút
        'gia_min': gia_min,
        'gia_max': gia_max,
    }
    return render(request, 'xe/san_pham.html', context)

def chi_tiet_xe(request, xe_id):
    xe = get_object_or_404(XeDien, id=xe_id)
    
    # Lấy chi tiết tồn kho ở từng chi nhánh
    chi_tiet_ton_kho = []
    tong_ton_kho = 0
    for ch in xe.cua_hang.all():
        kho = KhoHang.objects.filter(xe=xe, cua_hang=ch).first()
        so_luong = kho.so_luong if kho else 0
        tong_ton_kho += so_luong
        chi_tiet_ton_kho.append({
            'ten_cua_hang': ch.ten_cua_hang,
            'so_luong': so_luong
        })
        
    cho_phep_dat = True
    if not xe.sap_ve and tong_ton_kho <= 0:
        cho_phep_dat = False
        
    feedbacks = Feedback.objects.filter(xe=xe).order_by('-ngay_tao')
    trung_binh_sao = feedbacks.aggregate(Avg('danh_gia'))['danh_gia__avg'] or 0

   # ====================================================
    # LẤY 4 SẢN PHẨM CÙNG HÃNG SẢN XUẤT
    # ====================================================
    xe_tuong_tu = XeDien.objects.filter(
        hang_san_xuat=xe.hang_san_xuat,
        trang_thai=True
    ).exclude(id=xe.id).order_by('?')[:4] # Lấy ngẫu nhiên tối đa 4 xe
        
    context = {
        'xe': xe, 
        'tong_ton_kho': tong_ton_kho, 
        'chi_tiet_ton_kho': chi_tiet_ton_kho,
        'cho_phep_dat': cho_phep_dat, 
        'feedbacks': feedbacks, 
        'trung_binh_sao': round(trung_binh_sao, 1),
        'xe_tuong_tu': xe_tuong_tu # Nhớ truyền biến này ra HTML nhé
    }
    return render(request, 'xe/chi_tiet_xe.html', context)

@login_required
@phan_quyen(roles=['admin', 'quan_ly'])
def danh_sach_xe(request):
    tu_khoa = request.GET.get('q', '')
    tat_ca_xe = XeDien.objects.all().order_by('-id')
    
    if tu_khoa:
        tat_ca_xe = tat_ca_xe.filter(
            Q(ten_xe__icontains=tu_khoa) | 
            Q(hang_san_xuat__icontains=tu_khoa) |
            Q(danh_muc__ten_danh_muc__icontains=tu_khoa)
        )
    return render(request, 'xe/danh_sach_xe.html', {'tat_ca_xe': tat_ca_xe, 'tu_khoa': tu_khoa})

@login_required
@phan_quyen(roles=['admin', 'quan_ly'])
def them_xe(request):
    if request.method == 'POST':
        post_data = request.POST.copy()
        file_data = request.FILES.copy()

        danh_sach_anh = request.FILES.getlist('hinh_anh')
        if 'hinh_anh' in file_data:
            del file_data['hinh_anh'] 

        form = XeDienForm(post_data, file_data)

        if form.is_valid():
            xe = form.save(commit=False)
            
            if danh_sach_anh:
                xe.hinh_anh = danh_sach_anh[0]
                
            xe.save() 

            if danh_sach_anh:
                for f in danh_sach_anh:
                    AnhXeDien.objects.create(xe=xe, image=f)

            danh_sach_ch = request.POST.getlist('cua_hang')
            if danh_sach_ch:
                xe.cua_hang.set(danh_sach_ch)

            messages.success(request, 'Thêm xe mới thành công!')
            return redirect('danh_sach_xe')
        else:
            print("=== LỖI FORM THÊM XE ===", form.errors)
    else:
        form = XeDienForm()
        
    return render(request, 'xe/xe_form.html', {'form': form, 'title': 'Thêm Xe Mới'})

@login_required
@phan_quyen(roles=['admin', 'quan_ly'])
def sua_xe(request, pk):
    xe = get_object_or_404(XeDien, pk=pk)
    if request.method == 'POST':
        post_data = request.POST.copy()
        file_data = request.FILES.copy()

        danh_sach_anh = request.FILES.getlist('hinh_anh')
        if 'hinh_anh' in file_data:
            del file_data['hinh_anh']

        form = XeDienForm(post_data, file_data, instance=xe)

        if form.is_valid():
            xe = form.save(commit=False)

            if danh_sach_anh:
                xe.hinh_anh = danh_sach_anh[0]
                xe.album_anh.all().delete()
                for f in danh_sach_anh:
                    AnhXeDien.objects.create(xe=xe, image=f)

            xe.save()

            danh_sach_ch = request.POST.getlist('cua_hang')
            if danh_sach_ch:
                xe.cua_hang.set(danh_sach_ch)
            else:
                xe.cua_hang.clear()

            messages.success(request, 'Cập nhật xe thành công!')
            return redirect('danh_sach_xe')
        else:
            print("=== LỖI FORM SỬA XE ===", form.errors)
    else:
        form = XeDienForm(instance=xe)
        
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
    target_id = request.GET.get('id')
    map_center = [10.7769, 106.7009] 
    zoom_level = 12 
    
    if target_id:
        try:
            tram_target = TramSac.objects.get(id=target_id)
            map_center = [float(tram_target.lat), float(tram_target.lon)]
            zoom_level = 18 
        except: pass

    m = folium.Map(location=map_center, zoom_start=zoom_level, tiles='CartoDB positron')
    
    for tram in trams:
        try:
            color = 'red' if str(tram.id) == target_id else 'blue'
            folium.Marker(
                location=[float(tram.lat), float(tram.lon)],
                popup=f"<b>{tram.ten_tram}</b><br>{tram.dia_chi}<br>Công suất: {tram.cong_suat} kW",
                tooltip=tram.ten_tram,
                icon=folium.Icon(color=color, icon='plug', prefix='fa')
            ).add_to(m)
        except: continue
        
    LocateControl(auto_start=False, keepCurrentPosition=True).add_to(m)
    
    context = {
        'map_html': m._repr_html_(), 
        'all_trams': list(trams.values('id', 'ten_tram', 'lat', 'lon', 'dia_chi'))
    }
    return render(request, 'tram_sac/map.html', context)

@login_required
@phan_quyen(roles=['admin', 'quan_ly'])
def quan_ly_tram_sac(request):
    tu_khoa = request.GET.get('q', '')
    danh_sach_tram = TramSac.objects.all().order_by('-id')
    if tu_khoa:
        danh_sach_tram = danh_sach_tram.filter(
            Q(ten_tram__icontains=tu_khoa) | Q(dia_chi__icontains=tu_khoa) | Q(loai_sac__icontains=tu_khoa)
        )
    return render(request, 'tram_sac/quan_ly_tram_sac.html', {'danh_sach_tram': danh_sach_tram, 'tu_khoa': tu_khoa})

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
# 4. QUẢN LÝ ĐƠN HÀNG
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
            
            try:
                email_nhan = getattr(don_hang, 'email', None) 
                if not email_nhan and request.user.is_authenticated:
                    email_nhan = request.user.email

                if email_nhan:
                    chu_de = f"Xác nhận đặt hàng thành công - Đơn hàng #{don_hang.id} - EV STORE"
                    noi_dung = f"""
                    Chào {don_hang.ho_ten},

                    Cảm ơn bạn đã tin tưởng và đặt hàng tại EV STORE!
                    Đây là email xác nhận đơn hàng của bạn.

                    THÔNG TIN ĐƠN HÀNG:
                    - Mã đơn hàng: #{don_hang.id}
                    - Sản phẩm: {xe.ten_xe}
                    - Số tiền phải thanh toán: {don_hang.tong_tien:,.0f} VNĐ

                    Chúng tôi sẽ sớm liên hệ với bạn qua số điện thoại {don_hang.so_dien_thoai} để tiến hành xác nhận và bàn giao xe.

                    Trân trọng,
                    Đội ngũ EV STORE.
                    """
                    send_mail(chu_de, noi_dung, settings.EMAIL_HOST_USER, [email_nhan], fail_silently=False)
            except Exception as e: print(f"Lỗi gửi email: {e}") 

            messages.success(request, "Đặt hàng thành công! Chúng tôi sẽ liên hệ với bạn sớm nhất.")
            return redirect('trang_chu') 
    else:
        form = DonHangForm(initial={'loai_don': loai_mac_dinh}, xe=xe)
    return render(request, 'donhang/tao_don_hang.html', {'form': form, 'xe': xe})

@login_required
@phan_quyen(roles=['admin', 'quan_ly', 'nhan_vien'])
def danh_sach_don_hang(request):
    tu_khoa = request.GET.get('q', '')
    danh_sach = DonHang.objects.all().order_by('-ngay_dat')
    if tu_khoa:
        danh_sach = danh_sach.filter(
            Q(ho_ten__icontains=tu_khoa) | Q(so_dien_thoai__icontains=tu_khoa) | Q(xe__ten_xe__icontains=tu_khoa) | Q(id__icontains=tu_khoa)
        )
    return render(request, 'donhang/danh_sach.html', {'danh_sach_don_hang': danh_sach, 'tu_khoa': tu_khoa})

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
            form.save() 
            return redirect('ql_nhan_vien')
    else: form = UserForm()
    return render(request, 'users/them_user.html', {'form': form})

@login_required
@phan_quyen(roles=['admin'])
def sua_user(request, id):
    user = get_object_or_404(User, id=id)
    form = UserForm(request.POST or None, instance=user)
    if form.is_valid():
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
    tu_khoa = request.GET.get('q', '')
    danh_sach = User.objects.filter(is_staff=True)
    if tu_khoa:
        danh_sach = danh_sach.filter(Q(username__icontains=tu_khoa) | Q(first_name__icontains=tu_khoa) | Q(last_name__icontains=tu_khoa))
    context = {'danh_sach': danh_sach, 'title': 'Quản lý Nhân Viên', 'icon': 'bi-person-vcard', 'show_add_button': True, 'tu_khoa': tu_khoa}
    return render(request, 'users/list_user.html', context)

@login_required
@phan_quyen(roles=['admin'])
def ql_khach_hang(request):
    tu_khoa = request.GET.get('q', '')
    danh_sach = User.objects.filter(is_staff=False)
    if tu_khoa:
        danh_sach = danh_sach.filter(Q(username__icontains=tu_khoa) | Q(email__icontains=tu_khoa))
    context = {'danh_sach': danh_sach, 'title': 'Quản lý Khách Hàng', 'icon': 'bi-people', 'show_add_button': False, 'tu_khoa': tu_khoa}
    return render(request, 'users/list_user.html', context)

import random 
def dang_ky_view(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            user.is_active = False 
            user.save()
            
            otp = str(random.randint(100000, 999999))
            request.session['otp'] = otp
            request.session['user_id'] = user.id
            
            email_nhan = user.email
            if email_nhan:
                chu_de = "Mã Xác Thực Đăng Ký Tài Khoản - EV STORE"
                noi_dung = f"""
                Chào {user.username},
                Cảm ơn bạn đã đăng ký tài khoản tại EV STORE.
                Mã xác thực (OTP) của bạn là: {otp}
                Mã này dùng để kích hoạt tài khoản. Vui lòng không chia sẻ cho người khác!
                """
                try: send_mail(chu_de, noi_dung, settings.EMAIL_HOST_USER, [email_nhan], fail_silently=False)
                except Exception as e: print(f"Lỗi gửi mail: {e}")
            return redirect('xac_thuc_otp')
    else: form = RegisterForm()
    return render(request, 'registration/register.html', {'form': form})

def xac_thuc_otp(request):
    if request.method == 'POST':
        otp_nhap = request.POST.get('otp')
        otp_thuc = request.session.get('otp')
        user_id = request.session.get('user_id')

        if otp_nhap and otp_nhap == otp_thuc:
            try:
                user = User.objects.get(id=user_id)
                user.is_active = True
                user.save()
                login(request, user)
                del request.session['otp']
                del request.session['user_id']
                messages.success(request, "Xác thực email thành công! Chào mừng bạn đến với EV STORE.")
                return redirect('trang_chu')
            except User.DoesNotExist:
                messages.error(request, "Không tìm thấy người dùng. Vui lòng đăng ký lại!")
        else: messages.error(request, "Mã OTP không chính xác. Vui lòng kiểm tra lại email!")
    return render(request, 'registration/xac_thuc_otp.html')

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
    tu_khoa = request.GET.get('q', '')
    danh_sach_dm = DanhMuc.objects.all().order_by('-id')
    if tu_khoa: danh_sach_dm = danh_sach_dm.filter(ten_danh_muc__icontains=tu_khoa)
    return render(request, 'category/quan_ly_danh_muc.html', {'danh_sach_dm': danh_sach_dm, 'tu_khoa': tu_khoa})

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
        lat, lon = request.POST.get('lat'), request.POST.get('lon')
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
        ch.bai_gioi_thieu = request.POST.get('bai_gioi_thieu')
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
# 8. KHO HÀNG (ĐÃ TÁCH LÀM 2 HÀM RIÊNG)
# ==========================================
@login_required
@phan_quyen(roles=['admin', 'quan_ly', 'nhan_vien'])
def quan_ly_phieu_nhap(request):
    tu_khoa = request.GET.get('q', '')
    danh_sach = PhieuNhapKho.objects.all().order_by('-ngay_nhap')
    
    if tu_khoa:
        danh_sach = danh_sach.filter(
            Q(cua_hang__ten_cua_hang__icontains=tu_khoa) |
            Q(nhan_vien_nhap__username__icontains=tu_khoa) |
            Q(ghi_chu__icontains=tu_khoa)
        )
    return render(request, 'kho/lich_su_nhap.html', {'danh_sach': danh_sach, 'tu_khoa': tu_khoa})

@login_required
@phan_quyen(roles=['admin', 'quan_ly', 'nhan_vien'])
def quan_ly_ton_kho(request):
    tu_khoa = request.GET.get('q', '')
    cua_hang_id = request.GET.get('cua_hang', '') 

    danh_sach = KhoHang.objects.select_related('xe', 'cua_hang').all().order_by('-id')

    if tu_khoa:
        danh_sach = danh_sach.filter(
            Q(xe__ten_xe__icontains=tu_khoa) |
            Q(xe__hang_san_xuat__icontains=tu_khoa)
        )

    if cua_hang_id:
        danh_sach = danh_sach.filter(cua_hang_id=cua_hang_id)

    canh_bao_het_hang = danh_sach.filter(so_luong__lte=3).order_by('so_luong')
    cac_cua_hang = CuaHang.objects.all()

    return render(request, 'kho/bao_cao_ton_kho.html', {
        'kho': danh_sach,
        'tu_khoa': tu_khoa,
        'cac_cua_hang': cac_cua_hang,
        'cua_hang_chon': int(cua_hang_id) if cua_hang_id else '',
        'canh_bao_het_hang': canh_bao_het_hang
    })

@login_required
@phan_quyen(roles=['admin', 'quan_ly', 'nhan_vien'])
def them_kho(request):
    if request.method == 'POST':
        if 'excel_file' in request.FILES:
            try:
                cua_hang_id = request.POST.get('cua_hang_excel')
                cua_hang = get_object_or_404(CuaHang, id=cua_hang_id)
                excel_file = request.FILES['excel_file']
                
                wb = openpyxl.load_workbook(excel_file)
                sheet = wb.active
                so_xe_da_nhap = 0 
                
                phieu = PhieuNhapKho.objects.create(
                    cua_hang=cua_hang,
                    nhan_vien_nhap=request.user,
                    ghi_chu=f"Nhập tự động từ file: {excel_file.name}"
                )
                
                print("==== BẮT ĐẦU ĐỌC EXCEL ====")
                for i, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
                    if not row or row[0] is None:
                        continue

                    xe_id_raw = row[0]
                    so_luong_raw = row[2] if len(row) >= 3 else (row[1] if len(row) >= 2 else 0)
                    
                    try:
                        xe_id = int(float(str(xe_id_raw).strip())) if str(xe_id_raw).strip() else 0
                        so_luong = int(float(str(so_luong_raw).strip())) if str(so_luong_raw).strip() else 0
                    except (ValueError, TypeError):
                        continue 
                        
                    if xe_id <= 0 or so_luong <= 0: 
                        continue 
                    
                    try:
                        xe = XeDien.objects.get(id=xe_id)
                        
                        ChiTietPhieuNhap.objects.create(phieu_nhap=phieu, xe=xe, so_luong=so_luong)
                        so_xe_da_nhap += 1
                        
                        kho, created = KhoHang.objects.get_or_create(xe=xe, cua_hang=cua_hang)
                        kho.so_luong += so_luong
                        kho.save()
                        
                        cap_nhat_xe = False
                        if not xe.trang_thai: xe.trang_thai = True; cap_nhat_xe = True
                        if xe.sap_ve: xe.sap_ve = False; cap_nhat_xe = True
                        if cap_nhat_xe: xe.save()
                        
                        print(f" -> OK: Đã nhập {so_luong} chiếc {xe.ten_xe}")
                            
                    except XeDien.DoesNotExist:
                        print(f" -> LỖI: Không tìm thấy xe có ID = {xe_id} tại dòng {i}")
                        continue 
                
                print(f"==== KẾT THÚC. Tổng số dòng thành công: {so_xe_da_nhap} ====")

                if so_xe_da_nhap == 0:
                    phieu.delete() 
                    messages.warning(request, "Lỗi: File Excel không có dữ liệu hợp lệ! Bạn kiểm tra xem đã gõ số lượng vào Cột C chưa nhé.")
                    return redirect('them_kho')
                
                messages.success(request, f"Đã nhập kho từ Excel thành công! (Cập nhật {so_xe_da_nhap} mẫu xe)")
                return redirect('quan_ly_phieu_nhap')
                
            except Exception as e:
                messages.error(request, f"Lỗi xử lý file Excel: {e}")
                return redirect('them_kho')
        else:
            form = PhieuNhapKhoForm(request.POST)
            formset = ChiTietPhieuNhapFormSet(request.POST)
            
            if form.is_valid() and formset.is_valid():
                phieu = form.save(commit=False)
                phieu.nhan_vien_nhap = request.user
                phieu.save()
                
                chi_tiets = formset.save(commit=False)
                for ct in chi_tiets:
                    ct.phieu_nhap = phieu
                    ct.save()
                    
                    kho, created = KhoHang.objects.get_or_create(xe=ct.xe, cua_hang=phieu.cua_hang)
                    kho.so_luong += ct.so_luong
                    kho.save()
                    
                    cap_nhat_xe = False
                    if not ct.xe.trang_thai and ct.so_luong > 0:
                        ct.xe.trang_thai = True
                        cap_nhat_xe = True
                    if ct.xe.sap_ve and ct.so_luong > 0:
                        ct.xe.sap_ve = False
                        cap_nhat_xe = True
                    if cap_nhat_xe:
                        ct.xe.save()
                        
                for obj in formset.deleted_objects: obj.delete()
                messages.success(request, f"Đã nhập lô hàng thủ công vào {phieu.cua_hang.ten_cua_hang} thành công!")
                return redirect('quan_ly_phieu_nhap')
    else:
        form = PhieuNhapKhoForm()
        formset = ChiTietPhieuNhapFormSet()
        
    return render(request, 'kho/form.html', {'form': form, 'formset': formset})

# ==========================================
# 9. PHIÊN SẠC & FEEDBACK
# ==========================================
@login_required
@phan_quyen(roles=['admin', 'quan_ly']) 
def danh_sach_phien_sac(request):
    tu_khoa = request.GET.get('q', '')
    phien = PhienSac.objects.all().order_by('-thoi_gian_bat_dau')
    if tu_khoa:
        phien = phien.filter(Q(tram_sac__ten_tram__icontains=tu_khoa) | Q(tram_sac__dia_chi__icontains=tu_khoa) | Q(user__username__icontains=tu_khoa))
    return render(request, 'tram_sac/danh_sach.html', {'phien': phien, 'tu_khoa': tu_khoa})

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
        if Feedback.objects.filter(user=request.user, xe=xe_duoc_chon).exists(): return redirect('gui_feedback')
        fb = form.save(commit=False)
        fb.user = request.user
        fb.save()
        return redirect('chi_tiet_xe', xe_id=xe_duoc_chon.id) 
    return render(request, 'feedback/form.html', {'form': form})

@login_required
@phan_quyen(roles=['admin', 'quan_ly'])
def quan_ly_feedback(request):
    tu_khoa = request.GET.get('q', '')
    danh_sach = Feedback.objects.all().order_by('-id')
    if tu_khoa:
        danh_sach = danh_sach.filter(Q(user__username__icontains=tu_khoa) | Q(xe__ten_xe__icontains=tu_khoa) | Q(noi_dung__icontains=tu_khoa))
    return render(request, 'feedback/admin_feedback.html', {'feedbacks': danh_sach, 'tu_khoa': tu_khoa})

@login_required
@phan_quyen(roles=['admin', 'quan_ly'])
def xoa_feedback(request, feedback_id):
    get_object_or_404(Feedback, id=feedback_id).delete()
    return redirect('quan_ly_feedback')


# ==========================================
# 10. CÁC API & HỆ THỐNG LIVE CHAT
# ==========================================
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

def san_pham_tai_chi_nhanh(request, pk):
    chi_nhanh = get_object_or_404(CuaHang, pk=pk)
    danh_sach_xe_goc = chi_nhanh.danh_sach_xe.filter(trang_thai=True)
    
    # 2. KIỂM TRA XEM TẠI ĐÚNG CHI NHÁNH NÀY CÒN XE KHÔNG
    danh_sach_xe = []
    for xe in danh_sach_xe_goc:
        kho = KhoHang.objects.filter(xe=xe, cua_hang=chi_nhanh).first()
        xe.ton_kho_tai_chi_nhanh = kho.so_luong if kho else 0 # Gắn thêm biến tạm
        danh_sach_xe.append(xe)
        
    return render(request, 'pages/san_pham_chi_nhanh.html', {
        'chi_nhanh': chi_nhanh,
        'danh_sach_xe': danh_sach_xe
    })

@login_required
@phan_quyen(roles=['admin', 'quan_ly', 'nhan_vien'])
def tai_file_mau_excel(request):
    wb = openpyxl.Workbook()
    sheet = wb.active
    sheet.title = "Mau_Nhap_Kho"
    sheet.append(["ID Xe (KHÔNG SỬA)", "Tên Dòng Xe (Chỉ để xem)", "Số Lượng Nhập"])

    xe_dien_list = XeDien.objects.filter(trang_thai=True).order_by('id')
    for xe in xe_dien_list:
        sheet.append([xe.id, xe.ten_xe, ""]) 

    sheet.column_dimensions['A'].width = 20
    sheet.column_dimensions['B'].width = 40
    sheet.column_dimensions['C'].width = 20

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename=Mau_Nhap_Kho_EVStore.xlsx'
    wb.save(response)
    
    return response

# 1. API ĐỂ KHUNG CHAT CỦA KHÁCH TỰ ĐỘNG TẢI TIN NHẮN
@login_required
def api_load_chat(request):
    tin_nhans = TinNhanChat.objects.filter(khach_hang=request.user).order_by('thoi_gian')
    data = []
    for tn in tin_nhans:
        data.append({
            'noi_dung': tn.noi_dung,
            'is_admin': tn.nguoi_gui.is_staff,
        })
    return JsonResponse({'messages': data})

# 2. API ĐỂ KHÁCH GỬI TIN NHẮN TỪ KHUNG CHAT
@login_required
@csrf_exempt
def gui_ho_tro_nhanh(request):
    if request.method == 'POST':
        noi_dung = request.POST.get('noi_dung')
        if noi_dung:
            TinNhanChat.objects.create(khach_hang=request.user, nguoi_gui=request.user, noi_dung=noi_dung)
            return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error'})

# 3. GIAO DIỆN QUẢN LÝ CHAT DÀNH CHO ADMIN
@login_required
@phan_quyen(roles=['admin', 'quan_ly', 'nhan_vien'])
def quan_ly_ho_tro(request):
    # Lấy danh sách khách & ĐẾM số tin nhắn khách gửi mà admin chưa đọc
    danh_sach_khach = User.objects.filter(chat_cua_khach__isnull=False).annotate(
        tin_moi_nhat=Max('chat_cua_khach__thoi_gian'),
        so_tin_chua_doc=Count('chat_cua_khach', filter=Q(chat_cua_khach__da_doc=False, chat_cua_khach__nguoi_gui__is_staff=False))
    ).distinct().order_by('-tin_moi_nhat')
    
    khach_dang_chon = request.GET.get('khach_id')
    tin_nhans = []
    
    if khach_dang_chon:
        tin_nhans = TinNhanChat.objects.filter(khach_hang_id=khach_dang_chon).order_by('thoi_gian')
        # Khi admin bấm vào xem -> Tự động chuyển toàn bộ tin của khách này thành "Đã đọc"
        tin_nhans.filter(nguoi_gui__is_staff=False, da_doc=False).update(da_doc=True)

    # Khi Admin gõ câu trả lời và bấm Gửi
    if request.method == 'POST':
        noi_dung = request.POST.get('noi_dung')
        if noi_dung and khach_dang_chon:
            khach = User.objects.get(id=khach_dang_chon)
            TinNhanChat.objects.create(khach_hang=khach, nguoi_gui=request.user, noi_dung=noi_dung)
            return redirect(f"{request.path}?khach_id={khach_dang_chon}")

    return render(request, 'ho_tro/quan_ly_chat.html', {
        'danh_sach_khach': danh_sach_khach,
        'khach_dang_chon': int(khach_dang_chon) if khach_dang_chon else None,
        'tin_nhans': tin_nhans
    })