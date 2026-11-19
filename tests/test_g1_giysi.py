"""g1_giysi çözücüsü için sentetik çerçeveli testler.

Çalıştırma (depo kökünden):
    python3 -I -m unittest discover -s tests
"""

import os
import struct
import sys
import unittest

_PYTHON_KLASORU = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "python")
sys.path.insert(0, os.path.normpath(_PYTHON_KLASORU))

import g1_giysi as g  # noqa: E402


def ilk_cerceve(tip=0x05, baslangic=0):
    veri = bytes((baslangic + i) % 256 for i in range(128))
    return g.BASLIK + bytes((g.SIRA_ILK, tip)) + veri


def ikinci_cerceve(tip=0x05, baslangic=128, dordey=(1.0, 0.0, 0.0, 0.0)):
    sensor = bytes((baslangic + i) % 256 for i in range(128))
    return g.BASLIK + bytes((g.SIRA_IKINCI, tip)) + sensor + struct.pack("<4f", *dordey)


class SabitTesti(unittest.TestCase):
    def test_uzunluklar(self):
        self.assertEqual(g.ILK_CERCEVE_UZUNLUGU, 134)
        self.assertEqual(g.IKINCI_CERCEVE_UZUNLUGU, 150)
        self.assertEqual(g.DDS_YUK_UZUNLUGU, 272)
        self.assertEqual(len(ilk_cerceve()), 134)
        self.assertEqual(len(ikinci_cerceve()), 150)

    def test_sensor_tipi_adi(self):
        self.assertEqual(g.sensor_tipi_adi(0x01), "LH (Left Hand)")
        self.assertEqual(g.sensor_tipi_adi(0x02), "RH (Right Hand)")
        self.assertEqual(g.sensor_tipi_adi(0x03), "LF (Left Foot)")
        self.assertEqual(g.sensor_tipi_adi(0x04), "RF (Right Foot)")
        self.assertEqual(g.sensor_tipi_adi(0x05), "WB (Whole Body)")
        self.assertEqual(g.sensor_tipi_adi(0x09), "Unknown")
        self.assertEqual(g.sensor_tipi_adi(0x01, turkce=True), "sol el")
        self.assertEqual(g.sensor_tipi_adi(0x05, turkce=True), "tüm gövde")


class AyiklamaTesti(unittest.TestCase):
    def test_iki_tam_cerceve(self):
        tampon = bytearray(ilk_cerceve() + ikinci_cerceve())
        cerceveler = g.cerceveleri_ayikla(tampon)
        self.assertEqual([c.sira for c in cerceveler], [1, 2])
        self.assertEqual(len(cerceveler[0].veri), 128)
        self.assertEqual(len(cerceveler[1].veri), 144)
        self.assertEqual(len(tampon), 0)

    def test_bytearray_zorunlu(self):
        with self.assertRaises(TypeError):
            g.cerceveleri_ayikla(bytes(ilk_cerceve()))

    def test_bolunmus_baslik(self):
        cerceve = ilk_cerceve()
        tampon = bytearray(b"\x10\x20\x30\x40" + cerceve[:2])
        self.assertEqual(g.cerceveleri_ayikla(tampon), [])
        # Başlık bulunamadı: son 3 bayt korunur (ilk 2 başlık baytı dahil).
        self.assertEqual(bytes(tampon), b"\x40" + cerceve[:2])
        tampon.extend(cerceve[2:])
        cerceveler = g.cerceveleri_ayikla(tampon)
        self.assertEqual(len(cerceveler), 1)
        self.assertEqual(cerceveler[0].veri, cerceve[6:])
        self.assertEqual(len(tampon), 0)

    def test_parca_parca_besleme(self):
        akis = ilk_cerceve() + ikinci_cerceve()
        tampon = bytearray()
        toplam = []
        for i in range(0, len(akis), 7):
            tampon.extend(akis[i:i + 7])
            toplam.extend(g.cerceveleri_ayikla(tampon))
        self.assertEqual([c.sira for c in toplam], [1, 2])

    def test_cop_bayt(self):
        tampon = bytearray(b"\x00\xff\xaa\x55\x12" * 5 + ilk_cerceve())
        cerceveler = g.cerceveleri_ayikla(tampon)
        self.assertEqual(len(cerceveler), 1)
        self.assertEqual(cerceveler[0].sensor_tipi, 0x05)
        self.assertEqual(len(tampon), 0)

    def test_gecersiz_sira_bayti(self):
        bozuk = g.BASLIK + bytes((0x07, 0x05)) + bytes(10)
        tampon = bytearray(bozuk + ikinci_cerceve())
        cerceveler = g.cerceveleri_ayikla(tampon)
        self.assertEqual(len(cerceveler), 1)
        self.assertEqual(cerceveler[0].sira, g.SIRA_IKINCI)

    def test_yarim_cerceve_bekler(self):
        cerceve = ikinci_cerceve()
        tampon = bytearray(cerceve[:100])
        self.assertEqual(g.cerceveleri_ayikla(tampon), [])
        self.assertEqual(len(tampon), 100)

    def test_4096_bayt_korumasi(self):
        # Geçerli başlık ve sıra baytı, ardından 5000 bayt sıfır: ilk 134 bayt
        # çerçeve olur, kalan büyük çöp bloğundan yalnız son 3 bayt tutulur.
        tampon = bytearray(ilk_cerceve()[:6])
        tampon.extend(b"\x00" * 5000)
        cerceveler = g.cerceveleri_ayikla(tampon)
        self.assertEqual(len(cerceveler), 1)
        self.assertLessEqual(len(tampon), 3)

    def test_4096_koruma_yarim_cercevede(self):
        tampon = bytearray(b"\x00" * 4100)
        g.cerceveleri_ayikla(tampon)
        self.assertEqual(len(tampon), 3)


class BirlestirmeTesti(unittest.TestCase):
    def ayikla(self, ham):
        return g.cerceveleri_ayikla(bytearray(ham))

    def test_birlestir_ve_dordey(self):
        dordey = (0.5, -0.25, 0.125, 0.75)
        ilk, ikinci = self.ayikla(ilk_cerceve(0x03, 0) + ikinci_cerceve(0x03, 128, dordey))
        sonuc = g.birlestir(ilk, ikinci)
        self.assertIsNotNone(sonuc)
        self.assertEqual(sonuc["sensor_tipi"], 0x03)
        self.assertEqual(sonuc["sensorler"], list(range(256)))
        d = sonuc["dordey"]
        self.assertEqual((d["w"], d["x"], d["y"], d["z"]), dordey)

    def test_eslesmeyen_sensor_tipi(self):
        ilk, ikinci = self.ayikla(ilk_cerceve(0x01) + ikinci_cerceve(0x02))
        self.assertIsNone(g.birlestir(ilk, ikinci))

    def test_sira_ters(self):
        ilk, ikinci = self.ayikla(ilk_cerceve() + ikinci_cerceve())
        self.assertIsNone(g.birlestir(ikinci, ilk))

    def test_akis_birlestirici(self):
        akis = g.SeriAkisBirlestirici()
        # İlk paketsiz ikinci paket yok sayılır.
        self.assertEqual(akis.besle(ikinci_cerceve()), [])
        # Tipi eşleşmeyen çift atılır ve ilk paket bırakılır.
        self.assertEqual(akis.besle(ilk_cerceve(0x01) + ikinci_cerceve(0x02)), [])
        sonuc = akis.besle(b"\x99" + ilk_cerceve(0x05) + ikinci_cerceve(0x05))
        self.assertEqual(len(sonuc), 1)
        self.assertEqual(sonuc[0]["sensor_tipi"], 0x05)


class DdsTesti(unittest.TestCase):
    def test_272_bayt_cozum(self):
        dordey = (0.9, 0.1, -0.2, 0.3)
        yuk = struct.pack("<4f", *dordey) + bytes(range(256))
        self.assertEqual(len(yuk), 272)
        sonuc = g.dds_verisini_coz(list(yuk))  # SDK data alanı int listesi
        self.assertEqual(sonuc["sensorler"], list(range(256)))
        beklenen = struct.unpack("<4f", struct.pack("<4f", *dordey))
        d = sonuc["dordey"]
        self.assertEqual((d["w"], d["x"], d["y"], d["z"]), beklenen)

    def test_yanlis_uzunluk(self):
        with self.assertRaises(ValueError):
            g.dds_verisini_coz(bytes(271))

    def test_seri_den_dds_ye_gidis_donus(self):
        dordey = (1.0, 0.0, 0.0, 0.0)
        ilk, ikinci = g.cerceveleri_ayikla(
            bytearray(ilk_cerceve(0x05, 10) + ikinci_cerceve(0x05, 138, dordey))
        )
        birlesik = g.birlestir(ilk, ikinci)
        yuk = g.dds_verisi_olustur(birlesik)
        self.assertEqual(len(yuk), 272)
        cozum = g.dds_verisini_coz(yuk)
        self.assertEqual(cozum["sensorler"], birlesik["sensorler"])
        self.assertEqual(cozum["dordey"], birlesik["dordey"])


if __name__ == "__main__":
    unittest.main()
