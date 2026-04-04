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
        kho = KhoHang.objects.get(xe=instance.xe, cua_hang=instance.xe.cua_hang)
        
        # TRƯỜNG HỢP A: Khách vừa tạo đơn mới (Bất kể giữ chỗ, cọc hay mua thẳng) -> Trừ 1 xe
        if created:
            if kho.so_luong >= 1:
                kho.so_luong -= 1
                kho.save()
        
        # TRƯỜNG HỢP B: Admin chuyển trạng thái đơn hàng sang "Cancelled" (Đã hủy) -> Trả lại 1 xe
        elif hasattr(instance, '_old_trang_thai'):
            if instance._old_trang_thai != 'Cancelled' and instance.trang_thai == 'Cancelled':
                kho.so_luong += 1
                kho.save()

        # Tự động cập nhật cờ "trang_thai" chung của Xe
        if kho.so_luong == 0 and not instance.xe.sap_ve:
            instance.xe.trang_thai = False # Hết hàng
            instance.xe.save()
        elif kho.so_luong > 0:
            instance.xe.trang_thai = True  # Còn hàng
            instance.xe.save()

    except KhoHang.DoesNotExist:
        print(f"Cảnh báo: Không tìm thấy kho hàng hợp lệ cho xe {instance.xe.ten_xe}")