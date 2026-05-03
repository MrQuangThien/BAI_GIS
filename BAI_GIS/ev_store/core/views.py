import json
from math import radians, sin, cos, sqrt, atan2
from datetime import timezone
import traceback
from functools import wraps 
import folium
from folium.plugins import LocateControl

from django.urls import reverse
from django.http import HttpResponse
import openpyxl
import datetime
from django.core.paginator import Paginator

from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib import messages
from django.core.mail import send_mail
from django.db.models import Q, Count, Sum, Avg, Max
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.dateparse import parse_datetime

from django.contrib.auth.forms import PasswordChangeForm

from .models import ThongBao, TramSac, XeDien, CuaHang, DonHang, DanhMuc, Feedback, KhoHang, PhienSac, AnhXeDien, PhieuNhapKho, ChiTietPhieuNhap, TinNhanChat, UserProfile, LichLaiThu, DanhGiaTram, KhuyenMai

from .forms import XeDienForm, UserForm, RegisterForm, DonHangForm, DonHangTaiQuayForm, FeedbackForm, UserProfileForm, PhieuNhapKhoForm, ChiTietPhieuNhapFormSet, UserUpdateForm, ProfileUpdateForm, EmailChangeForm, LichLaiThuForm, KhuyenMaiForm

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

    now = datetime.datetime.now() 
    voucher_public = KhuyenMai.objects.filter(
        chien_luoc='public',
        trang_thai=True,
        ngay_bat_dau__lte=now,
        ngay_ket_thuc__gte=now
    ).order_by('-id')

    danh_sach_voucher_da_luu = []
    hien_thi_khuyen_mai = False # Mặc định là ẨN khu vực ưu đãi

    if voucher_public.exists():
        hien_thi_khuyen_mai = True # Nếu có voucher đang chạy thì báo bật (HIỆN)
        
        if request.user.is_authenticated:
            profile, created = UserProfile.objects.get_or_create(user=request.user)
            # Lấy mảng ID các mã mà khách đã lưu
            danh_sach_voucher_da_luu = list(profile.voucher_da_luu.values_list('id', flat=True))
            
            # Tính toán: Trong số các mã Công Khai, khách đã lưu bao nhiêu cái?
            public_ids = list(voucher_public.values_list('id', flat=True))
            so_luong_da_luu = sum(1 for v_id in danh_sach_voucher_da_luu if v_id in public_ids)

            # ĐIỀU KIỆN VÀNG: Nếu số lượng mã khách lưu >= tổng số mã công khai -> ẨN KHU VỰC
            if so_luong_da_luu >= voucher_public.count():
                hien_thi_khuyen_mai = False

    context = {
        'xe_noi_bat': danh_sach_noi_bat, 
        'xe_sap_ve': xe_sap_ve, 
        'form': form,
        'voucher_public': voucher_public,
        'danh_sach_voucher_da_luu': danh_sach_voucher_da_luu, 
        'hien_thi_khuyen_mai': hien_thi_khuyen_mai, # Truyền biến quyết định Ẩn/Hiện ra HTML
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
    user_profile = getattr(request.user, 'userprofile', None)
    is_admin = request.user.is_superuser or (user_profile and user_profile.vai_tro == 'admin')

    # 1. BIẾN DÙNG CHUNG (Hạ tầng trạm sạc thường là thông tin chung toàn hệ thống)
    tong_so_tram = TramSac.objects.count()
    tram_hoat_dong = TramSac.objects.filter(trang_thai=True).count()
    tram_bao_tri = tong_so_tram - tram_hoat_dong
    tram_moi_nhat = TramSac.objects.all().order_by('-id')[:5]
    danh_muc_stats = DanhMuc.objects.annotate(so_luong_xe=Count('xedien'))

    # 2. PHÂN QUYỀN DỮ LIỆU KINH DOANH
    if is_admin:
        # Sếp tổng: Thấy tất cả
        tong_don_hang = DonHang.objects.count()
        doanh_thu = DonHang.objects.exclude(trang_thai='Huy').aggregate(Sum('so_tien_tra_truoc'))['so_tien_tra_truoc__sum'] or 0
        tong_khach_hang = User.objects.filter(is_staff=False).count()
    else:
        # Nhân viên: Chỉ thấy đơn hàng & doanh thu của chi nhánh mình
        cua_hang_nv = user_profile.cua_hang
        tong_don_hang = DonHang.objects.filter(cua_hang=cua_hang_nv).count()
        doanh_thu = DonHang.objects.filter(cua_hang=cua_hang_nv).exclude(trang_thai='Huy').aggregate(Sum('so_tien_tra_truoc'))['so_tien_tra_truoc__sum'] or 0
        
        # Nếu bảng Khách hàng không chia theo chi nhánh, có thể để mặc định hoặc ẩn đi bằng cách gán = 0
        tong_khach_hang = User.objects.filter(is_staff=False).count() 

    tong_feedback = Feedback.objects.count()

    context = {
        'tong_so_tram': tong_so_tram, 
        'tram_hoat_dong': tram_hoat_dong, 
        'tram_bao_tri': tram_bao_tri,
        'tram_moi_nhat': tram_moi_nhat, 
        'danh_muc_stats': danh_muc_stats,
        'tong_don_hang': tong_don_hang, 
        'tong_khach_hang': tong_khach_hang, 
        'tong_feedback': tong_feedback, 
        'doanh_thu': doanh_thu,
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
    
    # 1. Xử lý tìm kiếm
    if tu_khoa:
        tat_ca_xe = tat_ca_xe.filter(
            Q(ten_xe__icontains=tu_khoa) | 
            Q(hang_san_xuat__icontains=tu_khoa) |
            Q(danh_muc__ten_danh_muc__icontains=tu_khoa)
        )

    # 2. Xử lý phân trang (8 xe / trang)
    paginator = Paginator(tat_ca_xe, 10) 
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Truyền page_obj ra giao diện
    return render(request, 'xe/danh_sach_xe.html', {
        'page_obj': page_obj, 
        'tu_khoa': tu_khoa
    })

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
@login_required(login_url='login')
def tao_don_hang(request, xe_id):
    xe = get_object_or_404(XeDien, id=xe_id)
    loai_mac_dinh = 'B' if xe.sap_ve else 'A'
    
    if request.method == 'POST':
        form = DonHangForm(request.POST, xe=xe) 
        if form.is_valid():
            don_hang = form.save(commit=False)
            don_hang.xe = xe
            
            # --- ĐÃ FIX LOGIC TRỪ TIỀN KHUYẾN MÃI KHI LƯU VÀO DB ---
            # Lấy số tiền giảm giá từ hidden input do JS gửi lên
            try:
                tien_giam_gia = float(request.POST.get('tien_giam_gia', 0))
            except ValueError:
                tien_giam_gia = 0

            # Tính tổng tiền sau giảm (dùng max để đảm bảo tiền không bị âm)
            don_hang.tong_tien = max(0, xe.gia - tien_giam_gia) 

            if request.user.is_authenticated: 
                don_hang.khach_hang = request.user
                
            if don_hang.loai_don == 'DatCoc':
                don_hang.trang_thai = 'Deposit Paid'
                # Nếu tiền cọc 20tr mà được giảm giá thì cũng phải trừ đi
                don_hang.so_tien_tra_truoc = max(0, 20000000 - tien_giam_gia) 
            elif don_hang.loai_don == 'TraThang':
                don_hang.trang_thai = 'Paid'
                don_hang.so_tien_tra_truoc = don_hang.tong_tien # Trả đủ số tiền đã giảm
                
            don_hang.save()

            if don_hang.cua_hang:
                kho_chi_nhanh = KhoHang.objects.filter(xe=xe, cua_hang=don_hang.cua_hang).first()
                if kho_chi_nhanh and kho_chi_nhanh.so_luong > 0:
                    kho_chi_nhanh.so_luong -= 1
                    kho_chi_nhanh.save()
            
            # --- LOGIC GỬI EMAIL ---
            try:
                email_nhan = request.POST.get('email') or (request.user.email if request.user.is_authenticated else None)

                if email_nhan:
                    ngay_hen_str = don_hang.ngay_giao_xe.strftime('%d/%m/%Y') if don_hang.ngay_giao_xe else "Sẽ được thông báo sau"
                    tien_con_lai = don_hang.tong_tien - don_hang.so_tien_tra_truoc

                    chu_de = f"Xác nhận đặt hàng thành công - EV STORE"
                    noi_dung = f"Chào {don_hang.ho_ten},\n\n" \
                               f"Cảm ơn bạn đã đặt hàng tại EV STORE!\n" \
                               f"THÔNG TIN ĐƠN HÀNG:\n" \
                               f"- Sản phẩm: {xe.ten_xe}\n" \
                               f"- Ngày nhận/giao xe (dự kiến): {ngay_hen_str}\n" \
                               f"- Tổng giá trị xe (Sau KM): {don_hang.tong_tien:,.0f} VNĐ\n" \
                               f"- Đã thanh toán (Cọc): {don_hang.so_tien_tra_truoc:,.0f} VNĐ\n" \
                               f"- Cần thanh toán thêm: {tien_con_lai:,.0f} VNĐ\n\n" \
                               f"Chúng tôi sẽ sớm liên hệ qua SĐT {don_hang.so_dien_thoai} để hỗ trợ.\n\n" \
                               f"Trân trọng,\nĐội ngũ EV STORE."
                    
                    send_mail(chu_de, noi_dung, settings.EMAIL_HOST_USER, [email_nhan], fail_silently=False)
            except Exception as e: 
                print(f"LỖI GỬI EMAIL ĐẶT HÀNG: {e}") 

            ThongBao.objects.create(
                tieu_de=f"Đơn đặt hàng mới!",
                noi_dung=f"Khách hàng {don_hang.ho_ten} vừa đặt mua {don_hang.xe.ten_xe}.",
                loai='don_hang',
                cua_hang=don_hang.cua_hang
            )

            messages.success(request, "🎉 Đặt hàng thành công! Vui lòng kiểm tra email của bạn.")
            
            if request.user.is_authenticated:
                url_chuyen_huong = reverse('tai_khoan') + '?tab=orders'
                return redirect(url_chuyen_huong) 
            return redirect('trang_chu') 
            
    else:
        # TỰ ĐỘNG ĐIỀN THÔNG TIN KHÁCH HÀNG
        initial_data = {'loai_don': loai_mac_dinh}
        if request.user.is_authenticated:
            initial_data['ho_ten'] = f"{request.user.last_name} {request.user.first_name}".strip()
            initial_data['email'] = request.user.email
            if hasattr(request.user, 'userprofile'):
                initial_data['so_dien_thoai'] = request.user.userprofile.so_dien_thoai
                initial_data['dia_chi'] = request.user.userprofile.dia_chi

        form = DonHangForm(initial=initial_data, xe=xe)
        
    # ========================================================
    # BẮT ĐẦU: LỌC VOUCHER TỪ VÍ KHÁCH HÀNG HIỂN THỊ RA DROPDOWN
    # ========================================================
    danh_sach_voucher = []
    
    if request.user.is_authenticated:
        now = datetime.datetime.now()
        profile, created = UserProfile.objects.get_or_create(user=request.user)
        
        danh_sach_id_duoc_dung = []

        # 1. Voucher công khai ĐÃ ĐƯỢC LƯU VÀO VÍ
        saved_ids = profile.voucher_da_luu.filter(
            trang_thai=True, ngay_bat_dau__lte=now, ngay_ket_thuc__gte=now
        ).values_list('id', flat=True)
        danh_sach_id_duoc_dung.extend(list(saved_ids))

        # 2. Voucher Đặc quyền Thành viên (Private)
        private_ids = KhuyenMai.objects.filter(
            chien_luoc='private', trang_thai=True, ngay_bat_dau__lte=now, ngay_ket_thuc__gte=now
        ).values_list('id', flat=True)
        danh_sach_id_duoc_dung.extend(list(private_ids))

        # 3. Voucher Lái thử
        sdt_khach = profile.so_dien_thoai
        email_khach = request.user.email
        
        # Chỉ tạo điều kiện tìm kiếm khi khách có SĐT hoặc Email
        q_objects = Q()
        if sdt_khach:
            q_objects |= Q(so_dien_thoai=sdt_khach)
        if email_khach:
            q_objects |= Q(email=email_khach)
            
        # Nếu q_objects có dữ liệu (khách có SĐT hoặc Email)
        if q_objects:
            da_lai_thu = LichLaiThu.objects.filter(
                q_objects,
                trang_thai='hoan_thanh' # Đã khớp 100% với models.py của bạn
            ).exists()
            
            if da_lai_thu:
                # Lưu ý: Chữ 'lai_thu' ở đây phải khớp với mã bạn cài trong KhuyenMai models
                laithu_ids = KhuyenMai.objects.filter(
                    chien_luoc='lai_thu', 
                    trang_thai=True, 
                    ngay_bat_dau__lte=now, 
                    ngay_ket_thuc__gte=now
                ).values_list('id', flat=True)
                danh_sach_id_duoc_dung.extend(list(laithu_ids))

        # Kéo các voucher hợp lệ từ CSDL lên
        vouchers_tiem_nang = KhuyenMai.objects.filter(id__in=danh_sach_id_duoc_dung).distinct()

        # BƯỚC CUỐI: Cực kỳ quan trọng -> Chỉ hiện mã áp dụng cho mẫu xe đang mua
        for km in vouchers_tiem_nang:
            if not km.xe_ap_dung.exists() or xe in km.xe_ap_dung.all():
                danh_sach_voucher.append(km)
    # ========================================================
    # KẾT THÚC LOGIC LỌC VOUCHER
    # ========================================================

    return render(request, 'donhang/tao_don_hang.html', {
        'form': form, 
        'xe': xe, 
        'danh_sach_voucher': danh_sach_voucher # Đã truyền biến này ra giao diện
    })

@login_required
@phan_quyen(roles=['admin', 'quan_ly', 'nhan_vien'])
def danh_sach_don_hang(request):
    # Lấy các tham số lọc từ URL
    tu_khoa = request.GET.get('q', '')
    ngay_dat = request.GET.get('ngay_dat', '') # Nhận giá trị từ ô chọn ngày

    # 1. LOGIC PHÂN QUYỀN
    if request.user.is_superuser or (hasattr(request.user, 'userprofile') and request.user.userprofile.vai_tro == 'QuanLy'):
        danh_sach = DonHang.objects.all().order_by('-id')
    elif hasattr(request.user, 'userprofile') and request.user.userprofile.cua_hang:
        chi_nhanh_cua_nv = request.user.userprofile.cua_hang
        danh_sach = DonHang.objects.filter(cua_hang=chi_nhanh_cua_nv).order_by('-id')
    else:
        danh_sach = DonHang.objects.none()

    # 2. XỬ LÝ TÌM KIẾM THEO TÊN/SĐT
    if tu_khoa:
        danh_sach = danh_sach.filter(
            Q(ho_ten__icontains=tu_khoa) | 
            Q(so_dien_thoai__icontains=tu_khoa)
        )
    
    # 3. XỬ LÝ LỌC THEO NGÀY ĐẶT
    if ngay_dat:
        # Lọc trường ngay_tao dựa trên phần date (năm-tháng-ngày)
        danh_sach = danh_sach.filter(ngay_tao__date=ngay_dat)

    # 4. LOGIC PHÂN TRANG (10 đơn/trang)
    paginator = Paginator(danh_sach, 10) 
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # 5. TRUYỀN RA GIAO DIỆN
    context = {
        'page_obj': page_obj,
        'tu_khoa': tu_khoa,
        'ngay_dat': ngay_dat, # Truyền ngược lại để giữ giá trị trong ô input
    }
    
    return render(request, 'donhang/danh_sach.html', context)

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
        form = DonHangTaiQuayForm(request.POST, request_user=request.user)
        if form.is_valid():
            don_hang = form.save(commit=False)
            don_hang.nhan_vien_tao = request.user
            
            # BẢO MẬT KÉP: Nếu là nhân viên, ép cứng chi nhánh vào đơn hàng
            is_admin = request.user.is_superuser or (hasattr(request.user, 'userprofile') and request.user.userprofile.vai_tro == 'QuanLy')
            if not is_admin and hasattr(request.user, 'userprofile') and request.user.userprofile.cua_hang:
                don_hang.cua_hang = request.user.userprofile.cua_hang
            
            # Đảm bảo gán lại tổng tiền từ giá xe gốc trong DB để an toàn
            don_hang.tong_tien = don_hang.xe.gia
            
            # Hứng dữ liệu từ các Radio HTML
            don_hang.hinh_thuc_nhan = request.POST.get('phuong_thuc_nhan', 'tai_cua_hang')
            
            time_type = request.POST.get('thoi_gian_nhan')
            if time_type == 'ngay_khac':
                don_hang.ngay_giao_xe = request.POST.get('ngay_giao_xe')
            
            if don_hang.loai_don == 'DatCoc':
                don_hang.so_tien_tra_truoc = 20000000  # Chốt cứng 20 triệu
                don_hang.trang_thai = 'Deposit Paid'
            else:
                don_hang.so_tien_tra_truoc = don_hang.tong_tien
                don_hang.trang_thai = 'Paid'

            don_hang.save()
            messages.success(request, f'Đã chốt thành công đơn hàng xe {don_hang.xe.ten_xe}!')
            return redirect('danh_sach_don_hang')
    else:
        # 🔥 ĐÃ FIX LỖI: Truyền user vào ngay khi mới mở trang lên (GET request)
        form = DonHangTaiQuayForm(request_user=request.user)

        danh_sach_kho = KhoHang.objects.filter(so_luong__gt=0)
        
    return render(request, 'donhang/tao_moi.html', {'form': form, 'danh_sach_kho': danh_sach_kho})

@login_required(login_url='login')
def chi_tiet_don_khach(request, don_hang_id):
    don_hang = get_object_or_404(DonHang, id=don_hang_id, khach_hang=request.user)
    return render(request, 'donhang/chi_tiet_don_khach.html', {'don_hang': don_hang})


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
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    active_tab = request.GET.get('tab', 'profile') 
    danh_sach_don_hang = DonHang.objects.filter(khach_hang=request.user).order_by('-ngay_dat')
    
    sdt_khach = profile.so_dien_thoai
    email_khach = request.user.email
    
    # Lịch sử sạc pin
    from .models import PhienSac
    danh_sach_phien_sac = PhienSac.objects.filter(user=request.user).order_by('-thoi_gian_bat_dau')

    # --- ĐÃ FIX: Dùng Q() an toàn, tránh lỗi khi khách chưa nhập SĐT ---
    q_objects = Q()
    if sdt_khach:
        q_objects |= Q(so_dien_thoai=sdt_khach)
    if email_khach:
        q_objects |= Q(email=email_khach)
        
    if q_objects:
        danh_sach_lai_thu = LichLaiThu.objects.filter(q_objects).order_by('-ngay_tao')
    else:
        danh_sach_lai_thu = LichLaiThu.objects.none()

    # Xử lý logic Ví Voucher (Khuyến mãi)
    now = datetime.datetime.now()
    
    # 1. Voucher Đặc quyền thành viên
    voucher_private = KhuyenMai.objects.filter(
        chien_luoc='private', trang_thai=True,
        ngay_bat_dau__lte=now, ngay_ket_thuc__gte=now
    )

    # --- ĐÃ FIX: Đổi trạng thái thành 'hoan_thanh' cho khớp với models.py ---
    da_lai_thu = danh_sach_lai_thu.filter(trang_thai='hoan_thanh').exists() if danh_sach_lai_thu else False
    
    if da_lai_thu:
        voucher_laithu = KhuyenMai.objects.filter(
            chien_luoc='lai_thu', trang_thai=True,
            ngay_bat_dau__lte=now, ngay_ket_thuc__gte=now
        )
    else:
        voucher_laithu = []

    # 3. Voucher Công khai khách đã lưu
    voucher_da_luu = profile.voucher_da_luu.filter(trang_thai=True, ngay_ket_thuc__gte=now)

    # XỬ LÝ FORM POST
    if request.method == 'POST':
        if 'btn_cap_nhat_thong_tin' in request.POST:
            active_tab = 'profile'
            u_form = UserUpdateForm(request.POST, instance=request.user)
            p_form = ProfileUpdateForm(request.POST, request.FILES, instance=profile)
            pass_form = PasswordChangeForm(request.user)
            email_form = EmailChangeForm(request.user)
            
            if u_form.is_valid() and p_form.is_valid():
                u_form.save()
                p_form.save()
                messages.success(request, 'Thông tin tài khoản đã được cập nhật!')
                return redirect('tai_khoan')

        elif 'btn_doi_mat_khau' in request.POST:
            active_tab = 'security'
            u_form = UserUpdateForm(instance=request.user)
            p_form = ProfileUpdateForm(instance=profile)
            pass_form = PasswordChangeForm(request.user, request.POST)
            email_form = EmailChangeForm(request.user)
            
            if pass_form.is_valid():
                user = pass_form.save() 
                update_session_auth_hash(request, user) 
                messages.success(request, 'Mật khẩu của bạn đã được đổi thành công!')
                return redirect('tai_khoan')
            else:
                messages.error(request, 'Đổi mật khẩu thất bại. Vui lòng kiểm tra lại!')

        elif 'btn_doi_email' in request.POST:
            active_tab = 'email'
            u_form = UserUpdateForm(instance=request.user)
            p_form = ProfileUpdateForm(instance=profile)
            pass_form = PasswordChangeForm(request.user)
            email_form = EmailChangeForm(request.user, request.POST)
            
            if email_form.is_valid():
                request.user.email = email_form.cleaned_data['new_email']
                request.user.save()
                messages.success(request, 'Email đăng nhập đã được thay đổi thành công!')
                return redirect('tai_khoan')
            else:
                messages.error(request, 'Đổi Email thất bại. Vui lòng kiểm tra lại!')

    else:
        u_form = UserUpdateForm(instance=request.user)
        p_form = ProfileUpdateForm(instance=profile)
        pass_form = PasswordChangeForm(request.user)
        email_form = EmailChangeForm(request.user)

    # Đưa toàn bộ dữ liệu ra template
    context = {
        'u_form': u_form,
        'p_form': p_form,
        'pass_form': pass_form,
        'email_form': email_form,
        'active_tab': active_tab, 
        'danh_sach_don_hang': danh_sach_don_hang,
        'danh_sach_lai_thu': danh_sach_lai_thu,
        'danh_sach_phien_sac': danh_sach_phien_sac, 
        'voucher_private': voucher_private,         
        'voucher_laithu': voucher_laithu,           
        'voucher_da_luu': voucher_da_luu,           
    }
    
    return render(request, 'users/tai_khoan.html', context)

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
        
        # Bổ sung replace(',', '.') ở đây để chặn lỗi nhập dấu phẩy
        if lat: ch.lat = float(lat.replace(',', '.'))
        if lon: ch.lon = float(lon.replace(',', '.'))
        
        if 'hinh_anh' in request.FILES: 
            ch.hinh_anh = request.FILES.get('hinh_anh')
            
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
    user_profile = request.user.userprofile
    tu_khoa = request.GET.get('q', '')
    
    # 1. BƯỚC LỌC QUYỀN: Chỉ lấy dữ liệu theo đúng chi nhánh của nhân viên
    if request.user.is_superuser or user_profile.vai_tro == 'admin':
        # Admin thấy toàn bộ
        danh_sach = PhieuNhapKho.objects.all()
    else:
        # Nhân viên / Quản lý chỉ thấy phiếu của cửa hàng mình
        danh_sach = PhieuNhapKho.objects.filter(cua_hang=user_profile.cua_hang)
        
    # 2. BƯỚC SẮP XẾP: Đưa phiếu mới nhất lên đầu
    danh_sach = danh_sach.order_by('-ngay_nhap')
    
    # 3. BƯỚC TÌM KIẾM: Lọc tiếp trên danh sách đã được phân quyền ở trên
    if tu_khoa:
        danh_sach = danh_sach.filter(
            Q(cua_hang__ten_cua_hang__icontains=tu_khoa) |
            Q(nhan_vien_nhap__username__icontains=tu_khoa) |
            Q(ghi_chu__icontains=tu_khoa)
        )
        
    return render(request, 'kho/lich_su_nhap.html', {
        'danh_sach': danh_sach, 
        'tu_khoa': tu_khoa
    })

@login_required
@phan_quyen(roles=['admin', 'quan_ly', 'nhan_vien'])
def quan_ly_ton_kho(request):
    tu_khoa = request.GET.get('q', '')
    cua_hang_id = request.GET.get('cua_hang', '') 

    # 1. BẢNG TỒN KHO TỔNG (Ai cũng thấy để check chéo)
    danh_sach = KhoHang.objects.select_related('xe', 'cua_hang').all().order_by('-id')

    # Lọc theo thanh tìm kiếm (áp dụng cho bảng dưới)
    if tu_khoa:
        danh_sach = danh_sach.filter(
            Q(xe__ten_xe__icontains=tu_khoa) |
            Q(xe__hang_san_xuat__icontains=tu_khoa)
        )

    if cua_hang_id:
        danh_sach = danh_sach.filter(cua_hang_id=cua_hang_id)

    # 2. KHU VỰC CẢNH BÁO (Áp dụng phân quyền)
    canh_bao_het_hang = danh_sach.filter(so_luong__lte=3).order_by('so_luong')
    
    # Logic kiểm tra quyền: Nếu KHÔNG PHẢI là Admin thì chỉ hiện cảnh báo của chi nhánh mình
    user_profile = getattr(request.user, 'userprofile', None)
    is_admin = request.user.is_superuser or (user_profile and user_profile.vai_tro in ['admin', 'quan_ly', 'QuanLy'])
    chi_nhanh_nv = user_profile.cua_hang if user_profile else None

    if not is_admin and chi_nhanh_nv:
        canh_bao_het_hang = canh_bao_het_hang.filter(cua_hang=chi_nhanh_nv)

    cac_cua_hang = CuaHang.objects.all()

    # 3. TRUYỀN ĐÚNG TÊN BIẾN RA HTML NHƯ CODE CŨ CỦA BẠN
    return render(request, 'kho/bao_cao_ton_kho.html', {
        'kho': danh_sach,
        'tu_khoa': tu_khoa,
        'cac_cua_hang': cac_cua_hang,
        'cua_hang_chon': int(cua_hang_id) if cua_hang_id else '',
        'canh_bao_het_hang': canh_bao_het_hang
    })

@login_required
@phan_quyen(roles=['admin', 'quan_ly', 'nhan_vien'])
def xuat_excel_ton_kho(request):
    # 1. Bắt lại các tham số lọc từ URL để xuất đúng dữ liệu
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

    # 2. Tạo file Excel
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Ton Kho EV Store"

    # Tạo Dòng Tiêu đề (Header)
    ws.append(['Tên xe điện', 'Hãng sản xuất', 'Chi nhánh', 'Số lượng tồn', 'Đơn giá (VNĐ)', 'Tổng giá trị vốn (VNĐ)', 'Tình trạng'])

    # 3. Đổ dữ liệu vào Excel
    for item in danh_sach:
        # Tính tổng giá trị vốn
        tong_gia_tri = item.so_luong * item.xe.gia
        
        # Xác định tình trạng bằng chữ
        if item.so_luong == 0:
            tinh_trang = "Hết hàng"
        elif item.so_luong <= 3:
            tinh_trang = "Sắp hết"
        else:
            tinh_trang = "Sẵn sàng"

        ws.append([
            item.xe.ten_xe,
            item.xe.hang_san_xuat,
            item.cua_hang.ten_cua_hang,
            item.so_luong,
            item.xe.gia,
            tong_gia_tri,
            tinh_trang
        ])

    # 4. Cấu hình file tải về
    now = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"Bao_Cao_Ton_Kho_{now}.xlsx"
    
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    wb.save(response)
    
    return response

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

def bat_dau_sac(request, tram_id):
    # Khóa chặt bằng code thay vì chỉ dùng decorator
    if not request.user.is_authenticated:
        # Nếu gọi bằng AJAX thì trả về JSON lỗi
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'message': 'Vui lòng đăng nhập để sạc pin!'}, status=401)
        # Nếu truy cập URL bình thường thì đá về trang đăng nhập
        return redirect('login') 

    tram = get_object_or_404(TramSac, id=tram_id)
    
    PhienSac.objects.create(
        user=request.user, 
        tram_sac=tram, 
        thoi_gian_bat_dau=timezone.now()
    )
    
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
    # Dùng annotate để tự động tính Số lượng đánh giá và Điểm trung bình cho từng trạm
    trams = TramSac.objects.annotate(
        trung_binh_sao=Avg('danh_gia__so_sao'),  # 'danh_gia' là related_name bạn đặt ở bài trước
        so_luong_danh_gia=Count('danh_gia')
    ).all()
    
    data = []
    for t in trams:
        data.append({
            'id': t.id,
            'ten_tram': t.ten_tram,
            'lat': t.lat,
            'lon': t.lon,
            'dia_chi': t.dia_chi,
            'loai_sac': t.loai_sac,
            'cong_suat': t.cong_suat,
            'hinh_anh': t.hinh_anh.url if t.hinh_anh else '',
            
            # BỔ SUNG 2 DÒNG NÀY ĐỂ GỬI RA NGOÀI BẢN ĐỒ:
            'trung_binh_sao': round(t.trung_binh_sao, 1) if t.trung_binh_sao else 0,
            'so_luong_danh_gia': t.so_luong_danh_gia
        })
    return JsonResponse(data, safe=False)

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
            # 1. Lưu tin nhắn vào Database
            TinNhanChat.objects.create(khach_hang=request.user, nguoi_gui=request.user, noi_dung=noi_dung)
            
            # ==========================================
            # 2. LOGIC BƠM CHUÔNG THÔNG BÁO CHO ADMIN
            # ==========================================
            # Tìm xem đã có thông báo chat của khách này chưa (chỉ lấy cái chưa đọc)
            tb_chat, created = ThongBao.objects.get_or_create(
                tieu_de=f"Tin nhắn hỗ trợ từ {request.user.username}",
                loai='ho_tro',
                da_doc=False, 
                defaults={
                    'noi_dung': noi_dung[:50] + "...", # Lấy 50 chữ đầu làm tóm tắt
                    'cua_hang': None # Gửi lên tổng đài chung để admin nào cũng thấy
                }
            )
            
            # Nếu chuông đã reo rồi (khách chat liên tục), thì chỉ cập nhật dòng chat mới nhất
            if not created:
                tb_chat.noi_dung = noi_dung[:50] + "..."
                tb_chat.save()
            # ==========================================

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
        
        # 1. Tự động chuyển toàn bộ tin nhắn chat thành "Đã đọc"
        tin_nhans.filter(nguoi_gui__is_staff=False, da_doc=False).update(da_doc=True)

        # ==========================================
        # 2. TỰ ĐỘNG TẮT CHUÔNG THÔNG BÁO Ở NAVBAR
        # ==========================================
        khach = User.objects.get(id=khach_dang_chon)
        ThongBao.objects.filter(
            tieu_de=f"Tin nhắn hỗ trợ từ {khach.username}",
            loai='ho_tro',
            da_doc=False
        ).update(da_doc=True)
        # ==========================================

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

def api_lay_tin_nhan_moi(request, khach_id):
    # Lấy tin nhắn và đánh dấu đã đọc ngầm
    tin_nhans = TinNhanChat.objects.filter(khach_hang_id=khach_id).order_by('thoi_gian')
    tin_nhans.filter(nguoi_gui__is_staff=False, da_doc=False).update(da_doc=True)

    data = []
    for tn in tin_nhans:
        data.append({
            'noi_dung': tn.noi_dung,
            'la_admin': tn.nguoi_gui.is_staff # Kiểm tra xem ai gửi
        })
    return JsonResponse({'tin_nhans': data})

@login_required(login_url='login')
def dang_ky_lai_thu(request, xe_id):
    xe_quan_tam = get_object_or_404(XeDien, id=xe_id)
    
    if request.method == 'POST':
        form = LichLaiThuForm(request.POST)
        if form.is_valid():
            lich = form.save(commit=False)
            lich.xe_quan_tam = xe_quan_tam 
            lich.save()
            
            # --- LOGIC GỬI EMAIL ---
            email_nhan = request.POST.get('email')
            if email_nhan: 
                subject = f"Xác nhận đăng ký xem xe {xe_quan_tam.ten_xe} thành công"
                message = f"""
                Chào {lich.ho_ten},
                Cảm ơn bạn đã quan tâm đến dòng xe {xe_quan_tam.ten_xe}.
                Lịch hẹn của bạn đã được ghi nhận:
                - Chi nhánh: {lich.cua_hang.ten_cua_hang if lich.cua_hang else 'Đang cập nhật'}
                - Ngày hẹn: {lich.ngay_hen.strftime('%d/%m/%Y') if lich.ngay_hen else 'Đang cập nhật'}
                - Ghi chú: {lich.ghi_chu}
                
                Nhân viên của EV Store sẽ liên hệ sớm nhất để xác nhận lịch với bạn.
                Trân trọng!
                """
                try:
                    send_mail(
                        subject,
                        message,
                        settings.EMAIL_HOST_USER, 
                        [email_nhan], 
                        fail_silently=False,
                    )
                except Exception as e:
                    print(f"LỖI GỬI EMAIL LÁI THỬ: {e}")

            ThongBao.objects.create(
                tieu_de="Yêu cầu lái thử mới",
                noi_dung=f"Khách hàng {lich.ho_ten} muốn lái thử {xe_quan_tam.ten_xe}.",
                loai='lai_thu',
                cua_hang=lich.cua_hang 
            )
            
            messages.success(request, "🎉 Đăng ký thành công! Vui lòng kiểm tra email xác nhận.")
            return redirect('chi_tiet_xe', xe_id=xe_id)
    else:
        # ĐÃ BỔ SUNG TỰ ĐỘNG ĐIỀN THÔNG TIN CHO FORM LÁI THỬ
        initial_data = {}
        if request.user.is_authenticated:
            initial_data['ho_ten'] = f"{request.user.last_name} {request.user.first_name}".strip()
            initial_data['email'] = request.user.email
            if hasattr(request.user, 'userprofile'):
                initial_data['so_dien_thoai'] = request.user.userprofile.so_dien_thoai
        
        form = LichLaiThuForm(initial=initial_data)
        
    return render(request, 'xe/dang_ky_lai_thu.html', {'form': form, 'xe': xe_quan_tam})

@login_required
@phan_quyen(roles=['admin', 'quan_ly','nhan_vien'])
def quan_ly_lai_thu(request):
    user_profile = request.user.userprofile
    
    # 1. Phân quyền chi nhánh
    if request.user.is_superuser:
        danh_sach = LichLaiThu.objects.all()
    else:
        danh_sach = LichLaiThu.objects.filter(cua_hang=user_profile.cua_hang)

    # 2. Lấy các tham số lọc từ URL
    query_name = request.GET.get('q', '')       # Tìm theo tên/SĐT
    query_date = request.GET.get('ngay', '')    # Tìm theo ngày hẹn

    # 3. Áp dụng bộ lọc kép
    if query_name:
        danh_sach = danh_sach.filter(
            Q(ho_ten__icontains=query_name) | Q(so_dien_thoai__icontains=query_name)
        )
    
    if query_date:
        danh_sach = danh_sach.filter(ngay_hen=query_date)

    # Sắp xếp: Ưu tiên ngày gần nhất hiện lên trước
    danh_sach = danh_sach.order_by('ngay_hen', 'id')

    context = {
        'danh_sach': danh_sach,
        'query_name': query_name,
        'query_date': query_date,
        'now': datetime.datetime.now()
    }
    return render(request, 'xe/lich_lai_thu.html', context)

@login_required
@phan_quyen(roles=['admin', 'quan_ly','nhan_vien'])
def xuat_excel_lai_thu(request):
    # Lấy dữ liệu theo tháng hiện tại
    now = datetime.datetime.now()
    user_profile = request.user.userprofile
    
    if request.user.is_superuser:
        data = LichLaiThu.objects.filter(ngay_hen__month=now.month, ngay_hen__year=now.year)
    else:
        data = LichLaiThu.objects.filter(cua_hang=user_profile.cua_hang, ngay_hen__month=now.month, ngay_hen__year=now.year)

    # Tạo file Excel
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"Bao_Cao_Lai_Thu_T{now.month}"

    # Header
    columns = ['Họ Tên', 'SĐT', 'Xe Quan Tâm', 'Chi Nhánh', 'Ngày Hẹn', 'Trạng Thái']
    ws.append(columns)

    for item in data:
        ws.append([
            item.ho_ten, 
            item.so_dien_thoai, 
            str(item.xe_quan_tam), 
            str(item.cua_hang), 
            item.ngay_hen.strftime('%d/%m/%Y'), 
            item.get_trang_thai_display()
        ])

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename=Bao_Cao_Lai_Thu_Thang_{now.month}.xlsx'
    wb.save(response)
    return response

def cap_nhat_trang_thai_lai_thu(request, lich_id):
    if request.method == 'POST':
        lich = get_object_or_404(LichLaiThu, id=lich_id)
        lich.trang_thai = request.POST.get('trang_thai')
        lich.save()
        
        # Sửa lại tên đường dẫn trả về cho đúng với file urls.py hiện tại
        return redirect('quan_ly_lai_thu')

@login_required
@phan_quyen(roles=['admin', 'quan_ly', 'nhan_vien']) # Đảm bảo hàm decorator này giống hệ thống của bạn
def xuat_excel_nhap_kho(request):
    # Lấy toàn bộ chi tiết phiếu nhập, dùng select_related để truy vấn siêu tốc
    danh_sach = ChiTietPhieuNhap.objects.select_related(
        'phieu_nhap', 'xe', 'phieu_nhap__cua_hang', 'phieu_nhap__nhan_vien_nhap'
    ).all().order_by('-phieu_nhap__ngay_nhap')

    # Tạo file Excel
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Lich Su Nhap Kho"

    # Header (Đã loại bỏ các cột tiền tệ cho khớp với Model của bạn)
    ws.append([
        'Mã Phiếu', 'Ngày Nhập', 'Chi Nhánh Nhận', 'Người Lập Phiếu', 'Ghi Chú',
        'Tên Sản Phẩm', 'Hãng Sản Xuất', 'Số Lượng Nhập'
    ])

    # Đổ dữ liệu
    for item in danh_sach:
        # Chuẩn bị format các trường dữ liệu
        ma_phieu = f"#PN-{item.phieu_nhap.id:04d}"
        ngay_nhap_str = item.phieu_nhap.ngay_nhap.strftime('%d/%m/%Y %H:%M')
        nguoi_lap = item.phieu_nhap.nhan_vien_nhap.username if item.phieu_nhap.nhan_vien_nhap else "Hệ thống"
        ghi_chu = item.phieu_nhap.ghi_chu if item.phieu_nhap.ghi_chu else "Không có"

        ws.append([
            ma_phieu,
            ngay_nhap_str,
            item.phieu_nhap.cua_hang.ten_cua_hang,
            nguoi_lap,
            ghi_chu,
            item.xe.ten_xe,
            item.xe.hang_san_xuat,
            item.so_luong
        ])

    # Cấu hình file tải về với timestamp hiện tại
    now = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"Lich_Su_Nhap_Kho_{now}.xlsx"
    
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    wb.save(response)
    
    return response

@login_required
@phan_quyen(roles=['admin', 'quan_ly', 'nhan_vien']) 
def xuat_excel_don_hang(request):
    # Lấy tháng, năm hiện tại để làm mặc định
    now = datetime.datetime.now()
    thang = int(request.GET.get('thang', now.month))
    nam = int(request.GET.get('nam', now.year))
    cua_hang_id = request.GET.get('cua_hang', '')

    danh_sach_don = DonHang.objects.filter(ngay_dat__month=thang, ngay_dat__year=nam).order_by('-ngay_dat')

    # Phân quyền: Nhân viên chi nhánh nào chỉ xuất data chi nhánh đó
    if not request.user.is_superuser:
        danh_sach_don = danh_sach_don.filter(cua_hang=request.user.userprofile.cua_hang)
    elif cua_hang_id:
        danh_sach_don = danh_sach_don.filter(cua_hang_id=cua_hang_id)

    # 1. Khởi tạo file Excel
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"Doanh_Thu_T{thang}_{nam}"

    # 2. Tạo Header (Dòng tiêu đề)
    ws.append([
        'Mã Đơn', 'Ngày Đặt', 'Tên Khách Hàng', 'Số Điện Thoại', 
        'Sản Phẩm', 'Chi Nhánh Giao', 'Loại Đơn', 'Tổng Tiền Xe (VNĐ)', 
        'Đã Thu (VNĐ)', 'Số Còn Thiếu (VNĐ)', 'Trạng Thái'
    ])

    # 3. Lặp dữ liệu và đổ vào Excel
    for dh in danh_sach_don:
        # Xử lý format ngày tháng
        ngay_dat_str = dh.ngay_dat.strftime('%d/%m/%Y %H:%M') if dh.ngay_dat else ""
        
        # Xử lý text Loại Đơn (Dựa trên code đợt trước chúng ta đã tối ưu)
        loai_don_str = "Cọc Online (20Tr)" if dh.loai_don == 'DatCoc' else "Mua trả thẳng (100%)"
        
        # Tính số tiền còn thiếu
        tien_con_thieu = dh.tong_tien - dh.so_tien_tra_truoc

        ws.append([
            f"#DH{dh.id:04d}",
            ngay_dat_str,
            dh.ho_ten,
            dh.so_dien_thoai,
            dh.xe.ten_xe if dh.xe else "N/A",
            dh.cua_hang.ten_cua_hang if dh.cua_hang else "N/A",
            loai_don_str,
            dh.tong_tien,
            dh.so_tien_tra_truoc,
            tien_con_thieu,
            dh.trang_thai
        ])

    # 4. Trả file về cho trình duyệt
    filename = f"Tong_Ket_Don_Hang_Thang_{thang}_{nam}.xlsx"
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    wb.save(response)
    
    return response

def luu_danh_gia_api(request):
    # BƯỚC 1: Chặn ngay nếu chưa đăng nhập
    if not request.user.is_authenticated:
        return JsonResponse({
            'status': 'error', 
            'message': 'Vui lòng đăng nhập để đánh giá trạm sạc.'
        }, status=401) # Mã 401: Unauthorized (Chưa xác thực)

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            tram_id = data.get('tram_id')
            so_sao = int(data.get('so_sao'))
            
            tram = TramSac.objects.get(id=tram_id)
            
            # BƯỚC 2: Lưu thẳng request.user vì chắc chắn 100% đã đăng nhập
            DanhGiaTram.objects.create(
                khach_hang=request.user,
                tram_sac=tram,
                so_sao=so_sao
            )
            return JsonResponse({'status': 'success', 'message': 'Lưu đánh giá thành công'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})
            
    return JsonResponse({'status': 'error', 'message': 'Sai phương thức'})

# Hàm này để load giao diện trang quản lý đánh giá
@login_required
@phan_quyen(roles=['admin', 'quan_ly'])
def quan_ly_danh_gia(request):
    danh_sach = DanhGiaTram.objects.select_related('khach_hang', 'tram_sac').all().order_by('-ngay_danh_gia')
    return render(request, 'tram_sac/quan_ly_danh_gia.html', {'danh_sach': danh_sach})

@login_required
@phan_quyen(roles=['admin', 'quan_ly'])
def xoa_danh_gia(request, danh_gia_id):
    # Đảm bảo chỉ nhận lệnh POST để bảo mật, chống việc gõ URL bậy bạ để xóa
    if request.method == 'POST':
        danh_gia = get_object_or_404(DanhGiaTram, id=danh_gia_id)
        danh_gia.delete()
        
    return redirect('quan_ly_danh_gia')

@login_required
def doc_thong_bao(request, thong_bao_id):
    # Tìm thông báo
    tb = get_object_or_404(ThongBao, id=thong_bao_id)
    
    # Đánh dấu đã đọc
    if not tb.da_doc:
        tb.da_doc = True
        tb.save()
        
    # Chuyển hướng thông minh dựa vào loại thông báo
    if tb.loai == 'don_hang':
        return redirect('danh_sach_don_hang')
    elif tb.loai == 'lai_thu':
        return redirect('quan_ly_lai_thu')
    elif tb.loai == 'ho_tro':
        return redirect('quan_ly_ho_tro')
    else:
        return redirect('admin_dashboard')

# 2. HÀM ĐÁNH DẤU TẤT CẢ ĐÃ ĐỌC (QUÉT SẠCH CHUÔNG)
@login_required
def danh_dau_tat_ca(request):
    user_profile = request.user.userprofile
    is_admin = request.user.is_superuser or user_profile.vai_tro in ['admin', 'quan_ly']

    if is_admin:
        # Sếp tổng: Quét sạch toàn bộ
        ThongBao.objects.filter(da_doc=False).update(da_doc=True)
    else:
        # Nhân viên: Chỉ quét sạch của chi nhánh mình và thông báo chung
        ThongBao.objects.filter(da_doc=False, cua_hang=user_profile.cua_hang).update(da_doc=True)
        ThongBao.objects.filter(da_doc=False, cua_hang__isnull=True).update(da_doc=True)

    # Làm xong thì quay lại trang hiện tại (không bị nhảy đi trang khác)
    truoc_do = request.META.get('HTTP_REFERER', 'admin_dashboard')
    return redirect(truoc_do)

def kiem_tra_ma_km(request):
    if request.method == 'POST':
        ma_code = request.POST.get('ma_code')
        loai_don = request.POST.get('loai_don') # ĐÓN THÔNG TIN LOẠI ĐƠN TỪ FRONTEND
        
        try:
            xe_id = int(request.POST.get('xe_id'))
            gia_xe = float(request.POST.get('gia_xe', 0))
        except (ValueError, TypeError):
            return JsonResponse({'success': False, 'message': 'Dữ liệu xe không hợp lệ!'})

        try:
            now = datetime.datetime.now()
            km = KhuyenMai.objects.filter(
                ma_code=ma_code, trang_thai=True,
                ngay_bat_dau__lte=now, ngay_ket_thuc__gte=now
            ).first()

            if not km:
                return JsonResponse({'success': False, 'message': 'Mã đã hết hạn hoặc chưa tới thời gian sử dụng!'})

            # --- BẮT ĐẦU: KIỂM TRA LOẠI ĐƠN (CỌC HAY TRẢ THẲNG) ---
            if km.loai_don_ap_dung == 'Tra_thang' and loai_don != 'TraThang':
                return JsonResponse({'success': False, 'message': 'Mã này chỉ áp dụng khi Thanh toán 100% giá trị xe!'})
            
            if km.loai_don_ap_dung == 'Dat_coc' and loai_don != 'DatCoc':
                return JsonResponse({'success': False, 'message': 'Mã này chỉ áp dụng cho đơn Đặt cọc giữ chỗ!'})
            # --- KẾT THÚC KIỂM TRA LOẠI ĐƠN ---

            if km.xe_ap_dung.exists():
                if not km.xe_ap_dung.filter(id=xe_id).exists():
                    return JsonResponse({'success': False, 'message': 'Rất tiếc, mã này không áp dụng cho mẫu xe bạn đang chọn!'})

            try:
                gia_tri_km = float(km.gia_tri) if km.gia_tri else 0.0
            except (ValueError, TypeError):
                gia_tri_km = 0.0

            if km.loai_khuyen_mai == 'phan_tram':
                tien_giam = (gia_xe * gia_tri_km) / 100.0
                ghi_chu = ""
            elif km.loai_khuyen_mai == 'tien_mat':
                tien_giam = gia_tri_km
                ghi_chu = ""
            elif km.loai_khuyen_mai == 'qua_tang':
                tien_giam = 0.0
                ghi_chu = km.mo_ta_qua_tang if km.mo_ta_qua_tang else km.ten_chuong_trinh
            else:
                tien_giam = 0.0
                ghi_chu = ""

            return JsonResponse({
                'success': True,
                'message': 'Áp dụng mã thành công!',
                'tien_giam': float(tien_giam),
                'khuyen_mai_id': km.id,
                'ghi_chu': ghi_chu
            })

        except Exception as e:
            print("=== LỖI HỆ THỐNG API KHUYẾN MÃI ===")
            print(traceback.format_exc()) 
            return JsonResponse({'success': False, 'message': 'Có lỗi khi tính toán giá trị mã!'})

@login_required
@phan_quyen(roles=['admin', 'quan_ly'])
def quan_ly_voucher(request):
    danh_sach = KhuyenMai.objects.all().order_by('-id')
    # Đã sửa: Trỏ trực tiếp đến file trong thư mục templates gốc
    return render(request, 'voucher/quan_ly_voucher.html', {'danh_sach': danh_sach})

@login_required
@phan_quyen(roles=['admin', 'quan_ly'])
def them_sua_voucher(request, pk=None):
    obj = get_object_or_404(KhuyenMai, pk=pk) if pk else None
    if request.method == 'POST':
        form = KhuyenMaiForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, 'Lưu chương trình khuyến mãi thành công!')
            return redirect('quan_ly_voucher')
    else:
        form = KhuyenMaiForm(instance=obj)
    
    # Đã sửa: Trỏ trực tiếp đến file trong thư mục templates gốc
    return render(request, 'voucher/form_voucher.html', {'form': form, 'is_edit': pk is not None})

@login_required
@phan_quyen(roles=['admin', 'quan_ly'])
def xoa_voucher(request, pk):
    obj = get_object_or_404(KhuyenMai, pk=pk)
    obj.delete()
    messages.success(request, 'Đã xóa mã khuyến mãi!')
    return redirect('quan_ly_voucher')

@login_required
def luu_voucher_ajax(request):
    if request.method == 'POST':
        voucher_id = request.POST.get('voucher_id')
        khuyen_mai = get_object_or_404(KhuyenMai, id=voucher_id)
        profile = request.user.userprofile

        # ĐÃ FIX: Chỉ kiểm tra và lưu, KHÔNG XÓA
        if khuyen_mai in profile.voucher_da_luu.all():
            return JsonResponse({'success': True, 'message': 'Bạn đã lưu mã này rồi!'})
        else:
            profile.voucher_da_luu.add(khuyen_mai)
            return JsonResponse({'success': True, 'message': 'Lưu mã thành công!'})