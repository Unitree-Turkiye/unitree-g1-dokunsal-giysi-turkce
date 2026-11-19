"""rt/jq_clothstate konusuna abone olan örnek (unitree_sdk2_python).

GERÇEK ROBOTTA: bu dosyayı G1 EDU geliştirme bilgisayarında (cloth_service ile
aynı makinede) ya da o makineyle aynı alt ağdaki bir bilgisayarda çalıştırın.
Önce orijinal depodaki servisi derleyip başlatın:
    https://github.com/unitreerobotics/G1_cloth_service

Gereksinim: https://github.com/unitreerobotics/unitree_sdk2_python kurulu olmalı.

Kullanım:
    python3 ornek_dds_abone.py            # varsayılan arayüz
    python3 ornek_dds_abone.py eth0       # belirli ağ arayüzü

Çıktı, C++ test aracı JqDdsTest gibi saniyede bir alım hızını, dördeyi
(quaternion) ve 256 sensör değerini yazar.
"""

import sys
import threading
import time

from unitree_sdk2py.core.channel import ChannelSubscriber, ChannelFactoryInitialize
from unitree_sdk2py.idl.sensor_msgs.msg.dds_ import PointCloud2_

from g1_giysi import DDS_KONUSU, dds_verisini_coz

_kilit = threading.Lock()
_son_veri = None
_sayac = 0


def giysi_durumu_geldi(msg: PointCloud2_) -> None:
    """Her DDS mesajında çağrılır; yükü çözüp saklar."""
    global _son_veri, _sayac
    try:
        cozulmus = dds_verisini_coz(msg.data)
    except ValueError as hata:
        print("Atlanan mesaj:", hata)
        return
    with _kilit:
        _son_veri = cozulmus
        _sayac += 1


def main() -> None:
    ag_arayuzu = sys.argv[1] if len(sys.argv) > 1 else None
    # Servis DDS alan kimliği 0 ile yayın yapar (src/main.cpp: Init(0)).
    ChannelFactoryInitialize(0, ag_arayuzu)

    abone = ChannelSubscriber(DDS_KONUSU, PointCloud2_)
    abone.Init(giysi_durumu_geldi, 1)

    print("%s konusuna abone olundu, arayüz: %s" % (DDS_KONUSU, ag_arayuzu or "varsayılan"))
    print("Mesaj bekleniyor... (çıkmak için Ctrl+C)")

    onceki = 0
    try:
        while True:
            time.sleep(1.0)
            with _kilit:
                sayac = _sayac
                veri = _son_veri
            hiz = sayac - onceki
            onceki = sayac
            if veri is None:
                continue

            d = veri["dordey"]
            print("alınan %d mesaj, hız %d Hz" % (sayac, hiz))
            print("Dördey: W=%.6f X=%.6f Y=%.6f Z=%.6f" % (d["w"], d["x"], d["y"], d["z"]))
            print("Sensör değerleri (256 adet, 8 bit):")
            s = veri["sensorler"]
            for i in range(0, 256, 16):
                print("  [%3d] " % i + "".join("%4d" % v for v in s[i:i + 16]))
    except KeyboardInterrupt:
        abone.Close()


if __name__ == "__main__":
    main()
