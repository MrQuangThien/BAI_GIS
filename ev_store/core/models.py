from django.db import models

class CuaHang(models.Model):
    ten_cua_hang = models.CharField(max_length=255)
    dia_chi = models.TextField()
    so_dien_thoai = models.CharField(max_length=20)
    trang_thai = models.BooleanField(default=True)

    def __str__(self):
        return self.ten_cua_hang


class XeDien(models.Model):
    ten_xe = models.CharField(max_length=255)
    hang_san_xuat = models.CharField(max_length=255)
    dung_luong_pin = models.IntegerField()
    tam_di_chuyen = models.IntegerField()
    gia = models.BigIntegerField()
    trang_thai = models.BooleanField(default=True)
    cua_hang = models.ForeignKey(CuaHang, on_delete=models.CASCADE)

    def __str__(self):
        return self.ten_xe


class TramSac(models.Model):
    ten_tram = models.CharField(max_length=255)
    dia_chi = models.TextField()
    cong_suat = models.IntegerField()
    loai_sac = models.CharField(max_length=100)
    trang_thai = models.BooleanField(default=True)
    lat = models.FloatField()
    lon = models.FloatField()

    def __str__(self):
        return self.ten_tram


class PhienSac(models.Model):
    tram_sac = models.ForeignKey(TramSac, on_delete=models.CASCADE)
    thoi_gian_bat_dau = models.DateTimeField()
    thoi_gian_ket_thuc = models.DateTimeField()
    dien_nang_tieu_thu = models.FloatField()
