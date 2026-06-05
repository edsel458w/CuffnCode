import time
import math
import random
import multiprocessing as mp

FS = 500          # sample rate Hz
DEFLATION_RATE = 4.5  # mmHg/sec
CUFF_START = 180.0
CUFF_STOP = 50.0
CHUNK_SIZE = 50   # samples per queue push (~100 ms)

MAP_TRUE = 100.0   # ground-truth MAP (mmHg) — for verification
SYS_TRUE = 120.0   # ground-truth systolic
DIA_TRUE = 80.0    # ground-truth diastolic

A_MAX = 6.0        # peak oscillation amplitude (mmHg)
SIGMA = 22.0       # width of Gaussian envelope
OSC_FREQ = 1.2     # Hz (~72 bpm)
NOISE_STD = 0.3    # ADC noise std dev (mmHg)

SENTINEL = None


def _cuff_pressure(t):
    return CUFF_START - DEFLATION_RATE * t


def _oscillation_amplitude(cuff_p):
    return A_MAX * math.exp(-((cuff_p - MAP_TRUE) ** 2) / (2 * SIGMA ** 2))


def generate_oscillometric_signal(t, cuff_pressure):
    amp = _oscillation_amplitude(cuff_pressure)
    osc = amp * math.sin(2 * math.pi * OSC_FREQ * t)
    noise = random.gauss(0, NOISE_STD)
    return cuff_pressure + osc + noise


def acquisition_process(raw_queue: mp.Queue, stop_event: mp.Event):
    t = 0.0
    dt = 1.0 / FS
    chunk = []

    while not stop_event.is_set():
        cuff_p = _cuff_pressure(t)
        if cuff_p < CUFF_STOP:
            break

        sample = (t, generate_oscillometric_signal(t, cuff_p), cuff_p)
        chunk.append(sample)
        t += dt

        if len(chunk) >= CHUNK_SIZE:
            raw_queue.put(chunk)
            chunk = []
            time.sleep(CHUNK_SIZE / FS)

    if chunk:
        raw_queue.put(chunk)

    raw_queue.put(SENTINEL)
    print(f"[Acquisition] Done. Simulated {t:.1f} s of data.")
