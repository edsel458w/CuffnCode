# CuffnCode — Parallel Blood Pressure Simulation Dashboard

Dashboard simulasi pengukuran tekanan darah berbasis metode osilometrik, dibangun sebagai tugas besar mata kuliah **IFB 206 Komputasi Paralel**. Proyek ini mensimulasikan pipeline pemrosesan sinyal paralel menggunakan Python `multiprocessing`, dengan visualisasi real-time melalui web dashboard berbasis Chart.js.

---

## Gambaran Proyek

Sistem meniru cara kerja tensimeter digital (sphygmomanometer osilometrik):
1. Manset dipompa hingga ~180 mmHg, lalu dikempiskan perlahan (4,5 mmHg/detik)
2. Osilasi tekanan arteri terdeteksi pada dinding manset selama proses deflasi
3. Nilai **SYS / MAP / DIA** dihitung dari amplitudo puncak osilasi menggunakan rasio standar

---

## Arsitektur Pipeline Paralel

```
simulator.py  ──raw_queue──►  filter_worker.py  ──filtered_queue──►  envelope_worker.py  ──results_queue──►  main.py
   [P1]                            [P2]                                     [P3]                               [Main]
ADC simulation             60 Hz notch + 10 Hz LP                    Peak detection + BP                  Visualisasi
```

Setiap proses berjalan secara independen dan berkomunikasi melalui `mp.Queue(maxsize=20)` untuk flow control / backpressure.

### P1 — `simulator.py` (Akuisisi)

Mensimulasikan output ADC dari sensor tekanan:
- Sample rate: **500 Hz**, dikirim dalam chunk 50 sampel (~100 ms/chunk)
- Model sinyal: rampa tekanan manset + osilasi Gaussian + noise Gaussian
- Nilai ground-truth: SYS = 120 mmHg, MAP = 100 mmHg, DIA = 80 mmHg

### P2 — `filter_worker.py` (Filter Digital)

Memproses sinyal mentah dari `raw_queue`:
- **60 Hz IIR notch filter** — menghilangkan interferensi jala-jala listrik (PLN Indonesia)
- **4th-order Butterworth low-pass 10 Hz** — mempertahankan osilasi jantung (~1,2 Hz), membuang noise HF
- Filter bersifat stateful (`sosfilt_zi`) sehingga tidak ada transien di batas chunk

### P3 — `envelope_worker.py` (Deteksi Puncak & BP)

Memproses sinyal terfilter dari `filtered_queue`:
- Memisahkan komponen osilasi dari rampa manset (baseline subtraction)
- Mendeteksi puncak osilasi dengan `scipy.signal.find_peaks` (jarak minimum 0,4 detik)
- Estimasi tekanan darah menggunakan rasio osilometrik standar:
  - **Sistolic (SYS)**: puncak pertama dengan amplitudo ≥ 50% dari amplitudo maksimum
  - **MAP**: puncak dengan amplitudo maksimum
  - **Diastolik (DIA)**: puncak pertama setelah MAP dengan amplitudo ≤ 70% dari maksimum

### Main — `main.py` (Visualisasi)

Mengonsumsi `results_queue` dan menampilkan tiga grafik real-time via `matplotlib.animation.FuncAnimation`:
- Sinyal mentah vs sinyal terfilter
- Rampa tekanan manset
- Envelope osilasi + puncak terdeteksi + estimasi BP

---

## Web Dashboard (`docs/`)

Dashboard berbasis browser sebagai alternatif visualisasi yang dapat diakses tanpa instalasi Python.

| File | Deskripsi |
|------|-----------|
| `index.html` | Halaman utama dashboard |
| `assets/style.css` | Stylesheet — dark medical theme, Inter + JetBrains Mono |
| `assets/simulation.js` | Simulasi pipeline lengkap di JavaScript (tanpa backend) |

**Fitur dashboard:**
- Simulasi pipeline P1→P2→P3→Main berjalan langsung di browser
- Tiga chart real-time: Cuff Pressure, Filtered Signal, Oscillation Envelope + Peaks
- Panel BP dengan nilai SYS / MAP / DIA yang diperbarui inkremental
- Indikator status proses paralel (P1, P2, P3, Main) dengan animasi pulse
- Aksesibel: `aria-live` pada status message, `aria-label` pada canvas, touch target ≥ 44px

---

## Hardware (Implementasi Fisik)

| Komponen | Spesifikasi |
|----------|-------------|
| Sensor tekanan | MPS20N0040D pressure bridge, 50–100 mV full-scale |
| AFE | AD620 instrumentation amp (gain ≈ 105) + TLC2272 level shift @ 1,5 V |
| MCU | STM32F411CE (Black Pill) — ADC → UART → PC |
| Bandwidth analog | ~1,2 kHz (diverifikasi dengan TINA-TI) |

Skematik KiCad dan file simulasi TINA-TI tersedia di folder `KiCad/` dan `TINA-TI/`.

---

## Cara Menjalankan

### Web Dashboard (tanpa instalasi)

Buka `docs/index.html` langsung di browser, atau akses via GitHub Pages.

### Python Pipeline

```bash
# Install dependencies
pip install -r src/requirements.txt

# Jalankan dari root repo
python -m src.main
```

> Python 3.10+ diperlukan. Pada Windows gunakan `spawn` start method (sudah dikonfigurasi di `main.py`).

---

## Struktur Repo

```
CuffnCode/
├── docs/
│   ├── index.html          # Web dashboard
│   ├── assets/
│   │   ├── style.css       # Stylesheet
│   │   └── simulation.js   # Simulasi JS
│   └── README.md           # File ini
├── src/
│   ├── simulator.py        # P1 — Akuisisi / ADC simulation
│   ├── filter_worker.py    # P2 — Digital filter (notch + LP)
│   ├── envelope_worker.py  # P3 — Deteksi puncak & estimasi BP
│   ├── main.py             # Main process — matplotlib visualisasi
│   └── requirements.txt
├── KiCad/                  # Skematik hardware
└── TINA-TI/                # Simulasi rangkaian analog
```

---

## Mata Kuliah

**IFB 206 Komputasi Paralel** — Institut Teknologi Bandung  
Topik: pemrograman paralel dengan Python `multiprocessing`, pipeline berbasis antrian, sinkronisasi proses.
