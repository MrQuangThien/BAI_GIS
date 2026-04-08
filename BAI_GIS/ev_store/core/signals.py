from django.contrib.auth.models import User
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from .models import UserProfile, DonHang, KhoHang

@receiver(post_save, sender=User)
def tao_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)

# 1. Bắt lấy trạng thái cũ của Đơn hàng trước khi nó bị thay đổi (Dùng để nhận diện lúc Admin bấm Hủy đơn)
@receiver(pre_save, sender=DonHang)
def luu_trang_thai_cu(sender, instance, **kwargs):
    if instance.pk:
        try:
            instance._old_trang_thai = DonHang.objects.get(pk=instance.pk).trang_thai
        except DonHang.DoesNotExist:
            instance._old_trang_thai = None
    else:
        instance._old_trang_thai = None

# 2. Xử lý Tự động Cộng/Trừ Kho
@receiver(post_save, sender=DonHang)
def cap_nhat_kho_hang(sender, instance, created, **kwargs):
    try:
        # TRƯỜNG HỢP A: Khách vừa tạo đơn mới -> Tìm kho đang có hàng để TRỪ 1 xe
        if created:
            # TÌM KHO THÔNG MINH: Lấy kho đầu tiên có chiếc xe này và số lượng >= 1
            kho = KhoHang.objects.filter(xe=instance.xe, so_luong__gte=1).first()
            if kho:
                kho.so_luong -= 1
                kho.save()
        
        # TRƯỜNG HỢP B: Admin chuyển trạng thái sang "Cancelled" -> CỘNG lại 1 xe
        elif hasattr(instance, '_old_trang_thai'):
            if instance._old_trang_thai != 'Cancelled' and instance.trang_thai == 'Cancelled':
                # Tìm bừa 1 kho bất kỳ đang phân phối dòng xe này để cất xe trả lại
                kho_tra_ve = KhoHang.objects.filter(xe=instance.xe).first()
                if kho_tra_ve:
                    kho_tra_ve.so_luong += 1
                    kho_tra_ve.save()

        # ========================================================
        # TỰ ĐỘNG CẬP NHẬT TRẠNG THÁI XE (DỪNG BÁN / MỞ BÁN)
        # Quét tổng tồn kho của chiếc xe này trên TOÀN HỆ THỐNG
        # ========================================================
        tong_ton = KhoHang.objects.filter(xe=instance.xe).aggregate(Sum('so_luong'))['so_luong__sum'] or 0

        if tong_ton <= 0 and not instance.xe.sap_ve:
            if instance.xe.trang_thai: # Chỉ lưu nếu trạng thái đang bật (tránh loop)
                instance.xe.trang_thai = False 
                instance.xe.save()
        elif tong_ton > 0:
            if not instance.xe.trang_thai:
                instance.xe.trang_thai = True  
                instance.xe.save()

    except Exception as e:
        print(f"Cảnh báo lỗi tín hiệu kho hàng: {e}")