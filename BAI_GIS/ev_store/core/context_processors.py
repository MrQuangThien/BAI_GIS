from .models import ThongBao

def thong_bao_admin(request):
    # 1. Nếu chưa đăng nhập, không trả về gì cả
    if not request.user.is_authenticated or not hasattr(request.user, 'userprofile'):
        return {}

    user_profile = request.user.userprofile
    is_admin = request.user.is_superuser or user_profile.vai_tro in ['admin', 'quan_ly']

    # 2. Logic Phân quyền Chuông thông báo
    if is_admin:
        # Sếp tổng: Thấy tất cả các thông báo chưa đọc trên toàn quốc
        thong_bao_list = ThongBao.objects.filter(da_doc=False)[:5] # Lấy 5 cái mới nhất
        so_luong = ThongBao.objects.filter(da_doc=False).count()
    else:
        # Nhân viên: Chỉ thấy thông báo của chi nhánh mình HOẶC thông báo chung (cua_hang=Null)
        cua_hang_nv = user_profile.cua_hang
        thong_bao_list = ThongBao.objects.filter(
            da_doc=False
        ).filter(
            cua_hang=cua_hang_nv
        ) | ThongBao.objects.filter(da_doc=False, cua_hang__isnull=True)
        
        thong_bao_list = thong_bao_list.order_by('-ngay_tao')[:5]
        
        so_luong = ThongBao.objects.filter(da_doc=False, cua_hang=cua_hang_nv).count() + \
                   ThongBao.objects.filter(da_doc=False, cua_hang__isnull=True).count()

    # 3. Bơm 2 biến này ra MỌI trang HTML
    return {
        'tb_list': thong_bao_list,
        'tb_count': so_luong
    }