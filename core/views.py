from django.shortcuts import render
from .models import TramSac
import folium
from folium.plugins import LocateControl
from math import radians, sin, cos, sqrt, atan2

def haversine(lat1, lon1, lat2, lon2):
    """Tính khoảng cách km giữa 2 điểm (Haversine formula)"""
    R = 6371.0  # Bán kính Trái Đất (km)
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    distance = R * c
    return round(distance, 2)

def ban_do_tram_sac(request):
    trams = TramSac.objects.filter(trang_thai=True)
    
    # Vị trí mặc định (TP.HCM)
    default_lat, default_lon = 10.7769, 106.7009
    
    # Tạo bản đồ
    m = folium.Map(
        location=[default_lat, default_lon],
        zoom_start=12,
        tiles='CartoDB positron'
    )
    
    # Thêm marker cho tất cả trạm
    for tram in trams:
        folium.Marker(
            location=[tram.lat, tram.lon],
            popup=f"""
                <b>{tram.ten_tram}</b><br>
                {tram.dia_chi}<br>
                Công suất: {tram.cong_suat} kW<br>
                Loại: {tram.loai_sac}
            """,
            tooltip=tram.ten_tram,
            icon=folium.Icon(color='blue', icon='plug', prefix='fa')
        ).add_to(m)
    
    # Thêm LocateControl
    LocateControl(
        auto_start=False,
        keepCurrentPosition=True,
        strings={
            'title': 'Hiển thị vị trí của tôi',
            'popup': 'Bạn đang ở đây!'
        }
    ).add_to(m)
    
    # Tìm trạm gần nhất (dùng mặc định trước)
    nearest_tram = None
    min_distance = None
    
    if trams.exists():
        min_distance = float('inf')
        for tram in trams:
            dist = haversine(default_lat, default_lon, tram.lat, tram.lon)
            if dist < min_distance:
                min_distance = dist
                nearest_tram = tram
    
    # Truyền danh sách tất cả trạm (chỉ lấy các trường cần thiết)
    all_trams = list(trams.values('id', 'ten_tram', 'lat', 'lon', 'dia_chi'))
    
    map_html = m._repr_html_()
    
    context = {
        'map_html': map_html,
        'nearest_tram': nearest_tram,
        'min_distance': f"{min_distance} km" if min_distance is not None else "Chưa có dữ liệu",
        'user_location_note': "Click nút định vị để xem vị trí thật",
        'all_trams': all_trams,  # ← danh sách trạm để render nút
    }
    
    return render(request, 'map.html', context)

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt  # tạm dùng cho test (nên thay bằng token sau)
@csrf_exempt
def get_nearest_tram(request):
    if request.method == 'POST':
        try:
            lat = float(request.POST.get('lat'))
            lon = float(request.POST.get('lon'))
        except (TypeError, ValueError):
            return JsonResponse({'error': 'Invalid coordinates'}, status=400)

        trams = TramSac.objects.filter(trang_thai=True)
        if not trams.exists():
            return JsonResponse({'error': 'No charging stations found'}, status=404)

        nearest_tram = None
        min_distance = float('inf')

        for tram in trams:
            dist = haversine(lat, lon, tram.lat, tram.lon)
            if dist < min_distance:
                min_distance = dist
                nearest_tram = tram  # Giữ object để lấy lat/lon

        if nearest_tram:
            return JsonResponse({
                'nearest_tram': {
                    'ten_tram': nearest_tram.ten_tram,
                    'dia_chi': nearest_tram.dia_chi,
                    'cong_suat': nearest_tram.cong_suat,
                    'loai_sac': nearest_tram.loai_sac,
                    'lat': nearest_tram.lat,   # ← Thêm
                    'lon': nearest_tram.lon    # ← Thêm
                },
                'min_distance': f"{min_distance} km"
            })
        else:
            return JsonResponse({'error': 'No nearest tram found'}, status=404)

    return JsonResponse({'error': 'Invalid request method'}, status=405)