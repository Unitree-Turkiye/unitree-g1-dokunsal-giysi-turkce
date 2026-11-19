"""Unitree G1 dokunsal algılama giysisi için saf Python çözücü.

Bu modül, unitreerobotics/G1_cloth_service deposundaki C++ protokol kodunun
(include/JqProtocol.h, src/JqProtocol.cpp, src/cloth_service.cpp, src/JqDds.cpp)
Python karşılığıdır. Yalnız standart kütüphaneyi (struct, dataclasses) kullanır.

Seri çerçeve düzeni:
    [AA 55 03 99] + [sıra baytı] + [sensör tipi baytı] + [veri]

    sıra 0x01: ilk paket, 128 bayt veri (ilk 128 sensör değeri), çerçeve 134 bayt
    sıra 0x02: ikinci paket, 144 bayt veri (son 128 sensör değeri + 16 bayt
               jiroskop verisi), çerçeve 150 bayt

DDS yükü (konu rt/jq_clothstate, PointCloud2_.data, 272 bayt):
    data[0..15]   : dördey (quaternion), 4 adet float32 (w, x, y, z), little-endian
    data[16..271] : 256 sensör değeri, her biri 8 bit

Kaynak: https://github.com/unitreerobotics/G1_cloth_service (BSD-3-Clause,
Copyright (c) 2026, Unitree Robotics). Python çevirisi: EP Robot Teknoloji
(Robotlar.org), Unitree Robotics Türkiye Resmi Distribütörü.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Union

__all__ = [
    "BASLIK",
    "BASLIK_UZUNLUGU",
    "SIRA_ILK",
    "SIRA_IKINCI",
    "ILK_VERI_UZUNLUGU",
    "IKINCI_VERI_UZUNLUGU",
    "SENSOR_SAYISI",
    "JIROSKOP_BAYT",
    "ILK_CERCEVE_UZUNLUGU",
    "IKINCI_CERCEVE_UZUNLUGU",
    "DDS_YUK_UZUNLUGU",
    "TAMPON_SINIRI",
    "DDS_KONUSU",
    "Cerceve",
    "sensor_tipi_adi",
    "cerceveleri_ayikla",
    "birlestir",
    "dds_verisini_coz",
    "dds_verisi_olustur",
    "SeriAkisBirlestirici",
]

# JqProtocol.h sabitleri
BASLIK = bytes((0xAA, 0x55, 0x03, 0x99))
BASLIK_UZUNLUGU = 4

SIRA_ILK = 0x01
SIRA_IKINCI = 0x02

ILK_VERI_UZUNLUGU = 128     # ilk 128 sensör değeri
IKINCI_VERI_UZUNLUGU = 144  # son 128 sensör değeri + 16 bayt jiroskop
SENSOR_SAYISI = 256         # 128 + 128
JIROSKOP_BAYT = 16

ILK_CERCEVE_UZUNLUGU = BASLIK_UZUNLUGU + 1 + 1 + ILK_VERI_UZUNLUGU       # 134
IKINCI_CERCEVE_UZUNLUGU = BASLIK_UZUNLUGU + 1 + 1 + IKINCI_VERI_UZUNLUGU  # 150

# JqDds.hpp: GYRO_BYTES + SENSOR_BYTES
DDS_YUK_UZUNLUGU = JIROSKOP_BAYT + SENSOR_SAYISI  # 272

# extractFrames içindeki çöp girdi koruması
TAMPON_SINIRI = 4096

DDS_KONUSU = "rt/jq_clothstate"

_SENSOR_TIPLERI = {
    0x01: "LH (Left Hand)",
    0x02: "RH (Right Hand)",
    0x03: "LF (Left Foot)",
    0x04: "RF (Right Foot)",
    0x05: "WB (Whole Body)",
}

_SENSOR_TIPLERI_TR = {
    0x01: "sol el",
    0x02: "sağ el",
    0x03: "sol ayak",
    0x04: "sağ ayak",
    0x05: "tüm gövde",
}

BaytBenzeri = Union[bytes, bytearray, memoryview, Sequence[int]]


@dataclass
class Cerceve:
    """Tek bir seri çerçeve (C++ ``jq::JqFrame`` karşılığı).

    Alanlar:
        sira: paket sıra baytı (0x01 ya da 0x02)
        sensor_tipi: sensör tipi baytı (0x01 ile 0x05 arası)
        veri: başlık, sıra ve tip baytlarından sonraki veri baytları
    """

    sira: int = 0
    sensor_tipi: int = 0
    veri: bytes = field(default=b"")


def sensor_tipi_adi(tip: int, turkce: bool = False) -> str:
    """Sensör tipi baytının adını döndürür (C++ ``sensorTypeName`` karşılığı).

    Varsayılan çıktı kaynak koddaki İngilizce adla aynıdır, ör. ``"LH (Left Hand)"``.
    ``turkce=True`` verildiğinde Türkçe ad döner, ör. ``"sol el"``.
    Tanımlı tipler dışındaki değerler için ``"Unknown"`` (Türkçede ``"tanımsız"``) döner.
    """
    if turkce:
        return _SENSOR_TIPLERI_TR.get(tip, "tanımsız")
    return _SENSOR_TIPLERI.get(tip, "Unknown")


def _sira_icin_cerceve_uzunlugu(sira: int) -> int:
    """Sıra baytına göre toplam çerçeve uzunluğu; geçersiz sırada 0."""
    if sira == SIRA_ILK:
        return ILK_CERCEVE_UZUNLUGU
    if sira == SIRA_IKINCI:
        return IKINCI_CERCEVE_UZUNLUGU
    return 0


def _baslik_bul(tampon: bytearray) -> int:
    """Tampondaki ilk tam başlığın konumunu, yoksa -1 döndürür.

    C++ döngüsü ``i + HEADER_LEN <= buffer.size()`` koşuluyla yalnız tam
    dört baytlık eşleşmeyi arar; ``bytearray.find`` aynı sonucu verir.
    """
    return tampon.find(BASLIK)


def cerceveleri_ayikla(tampon: bytearray) -> List[Cerceve]:
    """Ham bayt akışı tamponundan tam çerçeveleri ayıklar.

    C++ ``jq::extractFrames`` işlevinin birebir karşılığıdır:

    1. Tamponda en az 6 bayt (başlık + sıra + tip) varken başlık aranır.
    2. Başlık yoksa bölünmüş başlık ihtimaline karşı son 3 bayt tutulur, gerisi atılır.
    3. Başlıktan önceki çöp baytlar atılır.
    4. Sıra baytı geçersizse yalnız başlığın ilk baytı atılır ve yeniden eşlenir.
    5. Çerçeve tamamlanmadıysa veri tamponda bekler.
    6. Tam çerçeve listeye eklenir ve tampondan silinir.
    7. Döngüden sonra tampon 4096 baytı aşarsa son 3 bayt dışında temizlenir.

    Tüketilen baytlar ``tampon`` üzerinden yerinde silinir; yarım veri kalır.
    Bu yüzden argüman ``bytearray`` olmalıdır.
    """
    if not isinstance(tampon, bytearray):
        raise TypeError("tampon bir bytearray olmalı (yerinde değiştirilir)")

    cerceveler: List[Cerceve] = []
    koru = BASLIK_UZUNLUGU - 1

    while len(tampon) >= BASLIK_UZUNLUGU + 2:
        # 1. Çerçeve başlığını bul.
        konum = _baslik_bul(tampon)
        if konum < 0:
            # Başlık bölünmüş olabilir: son (BASLIK_UZUNLUGU - 1) baytı tut.
            del tampon[:-koru]
            break

        if konum > 0:
            del tampon[:konum]

        # 2. Çerçeve uzunluğu için sıra baytı gerekir.
        if len(tampon) < BASLIK_UZUNLUGU + 1:
            break

        sira = tampon[BASLIK_UZUNLUGU]
        uzunluk = _sira_icin_cerceve_uzunlugu(sira)
        if uzunluk == 0:
            # Geçersiz sıra baytı: bu başlığı bırak ve yeniden eşle.
            del tampon[:1]
            continue

        # 3. Çerçevenin tamamını bekle.
        if len(tampon) < uzunluk:
            break

        cerceveler.append(
            Cerceve(
                sira=sira,
                sensor_tipi=tampon[BASLIK_UZUNLUGU + 1],
                veri=bytes(tampon[BASLIK_UZUNLUGU + 2:uzunluk]),
            )
        )
        del tampon[:uzunluk]

    # Çöp girdide sınırsız büyümeye karşı koruma.
    if len(tampon) > TAMPON_SINIRI:
        del tampon[:-koru]

    return cerceveler


def _dordey_coz(on_alti_bayt: BaytBenzeri) -> Dict[str, float]:
    """16 baytı little-endian 4 adet float32 olarak (w, x, y, z) çözer."""
    w, x, y, z = struct.unpack("<4f", bytes(on_alti_bayt))
    return {"w": w, "x": x, "y": y, "z": z}


def birlestir(ilk: Cerceve, ikinci: Cerceve) -> Optional[Dict[str, object]]:
    """İlk ve ikinci paketi tek ölçüme birleştirir (C++ ``jq::mergeFrames``).

    Koşullar kaynak kodla aynıdır: sıra baytları 0x01 ve 0x02, veri uzunlukları
    128 ve 144, iki paketin sensör tipi aynı. Koşul tutmazsa ``None`` döner.

    Dönen sözlük:
        ``sensor_tipi``: int
        ``sensorler``: 256 elemanlı int listesi (0-255)
        ``dordey``: ``{"w", "x", "y", "z"}`` float sözlüğü
    """
    if ilk.sira != SIRA_ILK or ikinci.sira != SIRA_IKINCI:
        return None
    if len(ilk.veri) != ILK_VERI_UZUNLUGU or len(ikinci.veri) != IKINCI_VERI_UZUNLUGU:
        return None
    if ilk.sensor_tipi != ikinci.sensor_tipi:
        return None

    sensorler = list(ilk.veri) + list(ikinci.veri[:ILK_VERI_UZUNLUGU])
    dordey = _dordey_coz(ikinci.veri[ILK_VERI_UZUNLUGU:ILK_VERI_UZUNLUGU + JIROSKOP_BAYT])
    return {"sensor_tipi": ilk.sensor_tipi, "sensorler": sensorler, "dordey": dordey}


def dds_verisini_coz(data: BaytBenzeri) -> Dict[str, object]:
    """``rt/jq_clothstate`` mesajının ``data`` dizisini çözer.

    ``data`` 272 bayt olmalıdır (unitree_sdk2_python ``PointCloud2_.data``
    alanı int listesi olarak gelir; bytes de kabul edilir). Servis yükte sensör
    tipini taşımaz; dönen sözlükte yalnız dördey ve sensör değerleri bulunur.

    Dönen sözlük:
        ``dordey``: ``{"w", "x", "y", "z"}`` float sözlüğü
        ``sensorler``: 256 elemanlı int listesi (0-255)
    """
    ham = bytes(data)
    if len(ham) != DDS_YUK_UZUNLUGU:
        raise ValueError(
            "DDS yükü %d bayt olmalı, %d bayt geldi" % (DDS_YUK_UZUNLUGU, len(ham))
        )
    return {
        "dordey": _dordey_coz(ham[:JIROSKOP_BAYT]),
        "sensorler": list(ham[JIROSKOP_BAYT:DDS_YUK_UZUNLUGU]),
    }


def dds_verisi_olustur(birlesik: Dict[str, object]) -> bytes:
    """Birleşik ölçümden 272 baytlık DDS yükü üretir (C++ ``JqDds::SetData``).

    Test ve simülasyon içindir: servisin yayınladığı ``data`` dizisiyle aynı
    düzeni kurar.
    """
    d = birlesik["dordey"]
    sensorler = birlesik["sensorler"]
    if len(sensorler) != SENSOR_SAYISI:
        raise ValueError("sensorler %d elemanlı olmalı" % SENSOR_SAYISI)
    return struct.pack("<4f", d["w"], d["x"], d["y"], d["z"]) + bytes(sensorler)


class SeriAkisBirlestirici:
    """Seri porttan gelen parçaları birleşik ölçümlere çevirir.

    C++ ``JqReceiver::onRawData`` mantığını izler: 0x01 paketi saklanır, ardından
    gelen 0x02 paketiyle birleştirilir. Birleştirme denemesinden sonra (başarılı
    ya da değil) saklanan ilk paket bırakılır. İlk paket olmadan gelen 0x02
    paketi yok sayılır.
    """

    def __init__(self) -> None:
        self.tampon = bytearray()
        self._ilk: Optional[Cerceve] = None

    def besle(self, parca: BaytBenzeri) -> List[Dict[str, object]]:
        """Yeni bayt parçasını ekler, tamamlanan birleşik ölçümleri döndürür."""
        self.tampon.extend(bytes(parca))
        sonuclar: List[Dict[str, object]] = []
        for cerceve in cerceveleri_ayikla(self.tampon):
            if cerceve.sira == SIRA_ILK:
                self._ilk = cerceve
            elif cerceve.sira == SIRA_IKINCI and self._ilk is not None:
                birlesik = birlestir(self._ilk, cerceve)
                if birlesik is not None:
                    sonuclar.append(birlesik)
                self._ilk = None
        return sonuclar

    def sifirla(self) -> None:
        """Tamponu ve saklanan ilk paketi temizler (C++ ``close`` karşılığı)."""
        self.tampon.clear()
        self._ilk = None
