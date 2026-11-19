# G1_cloth_service Ayrıntılı Rehber

**Unitree Robotics Türkiye Resmi Distribütörü · [Robotlar.org](https://www.robotlar.org)** · [Ana sayfaya dön](../README.md) · [Türkçe dokunsal giysi rehberi](https://www.robotlar.org/tr/rehber/unitree-g1-dokunsal-giysi-rehberi)

Bu rehber, [unitreerobotics/G1_cloth_service](https://github.com/unitreerobotics/G1_cloth_service) deposunun (`271b054`) README dosyasına ve kaynak koduna dayanır. Kurulum, başlatma ve servis komutları orijinal depoyla aynıdır; sorun giderme bölümündeki ek komutlar standart Linux araçlarıdır. Komutları orijinal deponun kök klasöründe çalıştırın.

## İçindekiler

1. [Kurulum](#-kurulum)
2. [Derleme çıktıları](#-derleme-çıktıları)
3. [Başlatma](#-başlatma)
4. [Test aboneliği](#-test-aboneliği)
5. [Otomatik başlatma](#-otomatik-başlatma)
6. [SSS](#-sss)
7. [Sorun giderme](#-sorun-giderme)

## 📦 Kurulum

### Gereksinimler

| Bileşen | Değer |
|---|---|
| İşletim sistemi | Ubuntu 22.04 (çevrimdışı paketler bu sürüm içindir) |
| Mimari | `x86_64` / `amd64` PC ya da `aarch64` / `arm64` (NVIDIA Jetson Orin NX) |
| Derleyici | Sistemin varsayılan derleyicisi, C++17 |
| CMake | 3.10 ve üstü |
| Seri kitaplık | `libserialport-dev` |
| DDS | unitree_sdk2, depoda `3rd/unitree_sdk2` altında önceden derlenmiş gelir |

### apt ile kurulum

```bash
sudo apt update
sudo apt install libserialport-dev
cd ~
git clone https://github.com/unitreerobotics/G1_cloth_service
cd G1_cloth_service
bash build.sh
```

### Çevrimdışı .deb kurulumu

İnternete çıkmayan bir geliştirme bilgisayarında `3rd/serialport` klasöründeki paketleri kurun. Sıra önemlidir: önce `libserialport0`, sonra `libserialport-dev`.

```bash
# arm64 (NVIDIA Jetson Orin NX)
sudo dpkg -i 3rd/serialport/libserialport0_0.1.1-3_arm64.deb
sudo dpkg -i 3rd/serialport/libserialport-dev_0.1.1-3_arm64.deb

# amd64 / x86_64 PC
sudo dpkg -i 3rd/serialport/libserialport0_0.1.1-3_amd64.deb
sudo dpkg -i 3rd/serialport/libserialport-dev_0.1.1-3_amd64.deb
```

Hangi paketi seçeceğinizi mimariye bakarak belirleyin:

```bash
uname -m
```

`aarch64` çıktısında arm64, `x86_64` çıktısında amd64 paketlerini kurun.

## 🧱 Derleme çıktıları

`build.sh`, `build/` klasörünü silip yeniden oluşturur ve CMake ile derler. CMake, `CMAKE_SYSTEM_PROCESSOR` değeri `aarch64|arm64` ise `aarch64`, öteki durumlarda `x86_64` SDK kitaplıklarını seçer. Çalıştırılabilir dosyalar `bin/` klasörüne yazılır:

| Dosya | Görev |
|---|---|
| `bin/cloth_service` | Seri porttan okur, çerçeveleri birleştirir, `rt/jq_clothstate` konusuna yayınlar |
| `bin/JqDdsTest` | `rt/jq_clothstate` konusuna abone olur, hızı ve veriyi yazdırır |

`3rd/unitree_sdk2/include` klasörü yoksa CMake `local unitree_sdk2 not found` hatasıyla durur.

## 🚀 Başlatma

```bash
# servisi başlatın (seri port erişimi root ya da dialout grubu ister)
sudo ./bin/cloth_service
```

Açılış sırası kaynak koda (`src/main.cpp`) göre şöyledir:

1. Günlük yapılandırması `config/default_logconf.json` dosyasından okunur.
2. Servis `/sys/class/tty` altında VID `1a86`, PID `55d3` olan aygıtı arar. Aygıt yoksa 500 ms arayla 60 kez, yani en çok 30 saniye yeniden dener.
3. Aygıt bulunursa DDS alan kimliği 0 ile başlatılır ve yayıncı açılır.
4. Seri port 921600 baud ile açılır. Birleşen her ölçüm yayıncıya verilir.
5. Yayıncı her 0,01 saniyede (100 Hz) son ölçümü gönderir.

`SIGINT` (Ctrl+C) ya da `SIGTERM` geldiğinde servis portu kapatıp `Program exited` günlüğüyle çıkar.

## 🧪 Test aboneliği

```bash
# geri döngü (loopback, varsayılan) ya da belirli bir ağ arayüzü üzerinden abone olun
./bin/JqDdsTest
./bin/JqDdsTest eth0
```

İlk argüman ağ arayüzü adıdır. Argüman verilmezse araç geri döngü üzerinden, yani aynı makinedeki servise abone olur. Başka bir makineden dinlerken o makinenin servise bakan arayüz adını verin (`ip a` ile görebilirsiniz).

Araç saniyede bir şunları yazar:

- alınan toplam mesaj sayısı, saniyelik hız (Hz) ve yük boyutu (272 bayt)
- jiroskop dördeyi: `W`, `X`, `Y`, `Z`
- 16 satırlık tabloda 256 sensör değeri

Python ile aynı aboneliği kurmak için [python/ornek_dds_abone.py](../python/ornek_dds_abone.py) dosyasını kullanın:

```bash
cd python
python3 ornek_dds_abone.py eth0
```

## 🔁 Otomatik başlatma

`cloth_service` derlenip testten geçtikten sonra açılışta başlaması için:

```bash
bash setup_autostart.sh
```

Betik önce `bin/cloth_service` dosyasının ve `3rd/unitree_sdk2/thirdparty/lib/<mimari>` klasörünün varlığını denetler. Ardından `/etc/systemd/system/G1_cloth.service` birimini yazar, `daemon-reload`, `enable` ve `restart` komutlarını çalıştırır. Birimin ana ayarları:

| Ayar | Değer |
|---|---|
| `Type` | `simple` |
| `User` / `Group` | `unitree` / `dialout` |
| `WorkingDirectory` | `<depo>/bin` |
| `ExecStart` | `<depo>/bin/cloth_service` |
| `Restart` / `RestartSec` | `always` / `5` |
| `Environment` | `LD_LIBRARY_PATH=<depo>/3rd/unitree_sdk2/thirdparty/lib/<mimari>` |
| `StandardOutput` / `StandardError` | `journal+console` |
| `WantedBy` | `multi-user.target` |

Servisi yönetin:

```bash
sudo systemctl status G1_cloth.service      # durumu göster
sudo journalctl -u G1_cloth.service -f      # günlüğü canlı izle
sudo systemctl restart G1_cloth.service     # servisi yeniden başlat
sudo systemctl stop G1_cloth.service        # servisi durdur
sudo systemctl disable G1_cloth.service     # açılışta başlatmayı kapat
```

Geçmiş günlük dosyaları `/unitree/var/log/cloth_service` altında durur. `config/default_logconf.json` ayarı `FileAsync` türünde, 10485760 baytlık (10 MB) 3 dosyayla döner. `/unitree` altı için seviye `INFO`, kök için `WARNING`.

```bash
ls /unitree/var/log/cloth_service
```

## ❓ SSS

1. Servis `Serial device 1a86:55d3 not found` hatasıyla çıkıyor:
   - Algılama giysisi bağlı değil ya da kablo gevşek. `lsusb` ile (`1a86:55d3` satırını arayın) ve `ls /dev/ttyACM*` ile kontrol edin.
2. CMake `local unitree_sdk2 not found` hatası veriyor:
   - `3rd/unitree_sdk2` klasörü eksik ya da yarım. Depoyla gelen SDK'yı geri yükleyin.
3. `JqDdsTest` başka bir makinede veri almıyor:
   - İki makinenin aynı alt ağda olduğundan emin olun ve doğru ağ arayüzü adını (ör. `eth0`) ilk argüman olarak verin.

## 🔧 Sorun giderme

### Aygıt görünmüyor

```bash
lsusb | grep 1a86:55d3
ls /dev/ttyACM*
```

`lsusb` satırı varsa dönüştürücü tanınmıştır. Servis aygıtı sysfs üzerinden VID/PID ile bulduğu için düğüm adı `/dev/ttyACM0` dışında bir numara da olabilir. Satır yoksa kabloyu ve USB bağlantısını yeniden takın, ardından `lsusb` komutunu tekrarlayın.

### Seri port izni

Servisi `sudo` olmadan çalıştırmak için kullanıcınızı `dialout` grubuna ekleyin, sonra oturumu kapatıp yeniden açın:

```bash
sudo usermod -aG dialout $USER
groups
```

`groups` çıktısında `dialout` görünmelidir. Otomatik başlatma birimi zaten `Group=dialout` ile çalışır.

### Servis açılışta çıkıyor

```bash
sudo systemctl status G1_cloth.service
sudo journalctl -u G1_cloth.service -f
```

Birim `Restart=always` ve `RestartSec=5` ile her 5 saniyede yeniden başlar. Günlükte `Serial device 1a86:55d3 not found` satırı varsa aygıt bağlantısını, `Failed to open serial port` satırı varsa port iznini kontrol edin.

### Paylaşılan kitaplık hatası

Servisi elle başlatırken DDS kitaplıkları bulunamazsa `LD_LIBRARY_PATH` değerini otomatik başlatma birimindeki gibi ayarlayın:

```bash
sudo env LD_LIBRARY_PATH=$PWD/3rd/unitree_sdk2/thirdparty/lib/$(uname -m) ./bin/cloth_service
```

### Başka makinede veri yok

1. İki makinenin aynı alt ağda olduğunu `ip a` çıktısıyla doğrulayın.
2. `./bin/JqDdsTest eth0` komutunda `eth0` yerine gerçek arayüz adını verin.
3. Hız 100 Hz civarında ve yük 272 bayt olmalıdır. Hız 0 ise servisin aynı DDS alanında (alan kimliği 0) çalıştığını kontrol edin.

---

© 2026 **[www.robotlar.org](https://www.robotlar.org)** · Unitree Robotics Türkiye Resmi Distribütörü · Kaynak: [unitreerobotics/G1_cloth_service](https://github.com/unitreerobotics/G1_cloth_service) (BSD-3-Clause, Copyright (c) 2026, Unitree Robotics)
