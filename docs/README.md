# CuffnCode — Parallel Blood Pressure Simulation Dashboard

> Simulasi pengukuran tekanan darah berbasis komputasi paralel | IFB 206 Komputasi Paralel

---

## Daftar Isi

- [Deskripsi Proyek](#deskripsi-proyek)
- [Tujuan](#tujuan)
- [Fitur Utama](#fitur-utama)
- [Prasyarat Instalasi](#prasyarat-instalasi)
- [Panduan Git Clone](#panduan-git-clone)
- [Struktur Direktori](#struktur-direktori)
- [Penggunaan](#penggunaan)
- [Kontribusi](#kontribusi)
- [Kontributor](#kontributor)
- [Lisensi dan Penggunaan](#lisensi-dan-penggunaan)

---

## Deskripsi Proyek

CuffnCode adalah sistem simulasi pengukuran tekanan darah yang mengimplementasikan metode **osilometrik** menggunakan arsitektur pipeline paralel. Proyek ini dibangun untuk mata kuliah IFB 206 Komputasi Paralel dan terdiri dari dua bagian utama:

- **Python Pipeline** — tiga proses paralel (`multiprocessing`) yang meniru alur pemrosesan sinyal dari ADC hingga estimasi tekanan darah
- **Web Dashboard** — antarmuka browser berbasis Chart.js yang menjalankan simulasi pipeline secara lengkap tanpa backend

Sistem mensimulasikan cara kerja tensimeter digital: manset dipompa hingga ~180 mmHg kemudian dikempiskan perlahan, osilasi tekanan arteri pada dinding manset dideteksi, dan nilai **Sistolic (SYS)**, **Mean Arterial Pressure (MAP)**, serta **Diastolik (DIA)** dihitung secara real-time.

---

## Tujuan

1. Mengimplementasikan konsep **komputasi paralel** pada kasus nyata di bidang biomedis
2. Membangun pipeline data streaming menggunakan `mp.Queue` dengan mekanisme backpressure
3. Mensimulasikan pemrosesan sinyal fisiologis: filtering digital (notch + low-pass) dan deteksi puncak osilasi
4. Memvisualisasikan hasil komputasi paralel secara real-time melalui Python (`matplotlib`) maupun browser (Chart.js)
5. Menerapkan metode osilometrik standar untuk estimasi tekanan darah non-invasif

---

## Fitur Utama

### Python Pipeline
- Pipeline 3 proses paralel: **Akuisisi → Filter → Envelope/Deteksi Puncak → Visualisasi**
- Komunikasi antar-proses via `mp.Queue(maxsize=20)` untuk flow control
- Filter digital stateful: 60 Hz IIR notch (PLN Indonesia) + Butterworth low-pass 10 Hz
- Estimasi BP inkremental menggunakan rasio osilometrik (SYS ≥ 50% max, DIA ≤ 70% max)
- Visualisasi animasi real-time dengan `matplotlib.animation.FuncAnimation`

### Web Dashboard
- Simulasi pipeline berjalan sepenuhnya di browser — tidak perlu server
- Tiga chart real-time: Cuff Pressure, Filtered Signal, Oscillation Envelope + Peaks
- Panel estimasi tekanan darah dengan nilai SYS / MAP / DIA yang diperbarui inkremental
- Indikator status proses P1, P2, P3, dan Main dengan animasi pulse
- Desain aksesibel: `aria-live`, `aria-label` pada canvas, touch target ≥ 44px

### Hardware (Implementasi Fisik)
| Komponen | Spesifikasi |
|----------|-------------|
| Sensor tekanan | MPS20N0040D pressure bridge, 50–100 mV full-scale |
| AFE | AD620 instr. amp (gain ≈ 105) + TLC2272 level shift @ 1,5 V |
| MCU | STM32F411CE (Black Pill) — ADC → UART → PC |
| Bandwidth analog | ~1,2 kHz (diverifikasi TINA-TI) |

---

## Prasyarat Instalasi

### Untuk Web Dashboard
- Browser modern (Chrome 90+, Firefox 88+, Edge 90+)
- Tidak memerlukan instalasi apapun

### Untuk Python Pipeline
| Prasyarat | Versi Minimum |
|-----------|---------------|
| Python | 3.10 |
| numpy | 1.26 |
| scipy | 1.12 |
| matplotlib | 3.8 |

---

## Panduan Git Clone

**1. Clone repository**

```bash
git clone https://github.com/Student-Embedded-Control-and-AI-Fest/CuffnCode.git
cd CuffnCode
```

**2. (Opsional) Buat virtual environment**

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

**3. Install dependensi Python**

```bash
pip install -r src/requirements.txt
```

---

## Struktur Direktori

```
CuffnCode/
├── docs/
│   ├── index.html              # Web dashboard — buka langsung di browser
│   ├── README.md               # Dokumentasi proyek (file ini)
│   └── assets/
│       ├── style.css           # Stylesheet dark medical theme
│       └── simulation.js       # Pipeline simulasi lengkap (JavaScript)
├── src/
│   ├── __init__.py             # Package marker
│   ├── simulator.py            # P1 — Simulasi ADC & akuisisi sinyal
│   ├── filter_worker.py        # P2 — Filter digital (notch 60 Hz + LP 10 Hz)
│   ├── envelope_worker.py      # P3 — Deteksi puncak & estimasi BP
│   ├── main.py                 # Main process — visualisasi matplotlib
│   └── requirements.txt        # Dependensi Python
├── KiCad/                      # Skematik hardware
└── TINA-TI/                    # Simulasi rangkaian analog
```

---

## Penggunaan

### Web Dashboard

Buka file `docs/index.html` langsung di browser, kemudian klik **Start Simulation**.

Atau akses via GitHub Pages (jika diaktifkan pada repository).

### Python Pipeline

Jalankan dari direktori root repository:

```bash
python -m src.main
```

Tiga jendela grafik matplotlib akan muncul dan menampilkan:
- Sinyal mentah vs sinyal terfilter
- Rampa tekanan manset
- Envelope osilasi + puncak terdeteksi + estimasi SYS / MAP / DIA

Hasil akhir ditampilkan di terminal setelah simulasi selesai:

```
================================================
  Blood Pressure Estimation Summary
================================================
                        Estimated   Expected
  Systolic (SYS)              120        120
  Mean Arterial (MAP)         100        100
  Diastolic (DIA)              80         80
================================================
```

---

## Kontribusi

Proyek ini adalah tugas akademik untuk mata kuliah IFB 206 Komputasi Paralel. Kontribusi terbuka untuk perbaikan dokumentasi, optimasi pipeline, atau penambahan fitur visualisasi.

**Langkah kontribusi:**

1. Fork repository ini
2. Buat branch baru: `git checkout -b nama-fitur`
3. Commit perubahan: `git commit -m "Deskripsi perubahan"`
4. Push ke branch: `git push origin nama-fitur`
5. Buat Pull Request ke branch `main`

---

## Kontributor

Project ini dibuat untuk memenuhi tugas **Evaluasi 3 — Komputasi Paralel dan Sistem Terdistribusi**.

| Nama | NRP |
|------|-----|
| Edsel Sulthan Farrel | 152024166 |

---

## Lisensi dan Penggunaan

Project ini merupakan pengembangan tambahan dari repository CuffnCode.


