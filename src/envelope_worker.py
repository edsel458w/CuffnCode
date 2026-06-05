import multiprocessing as mp
import numpy as np
from scipy.signal import find_peaks

FS = 500
PEAK_MIN_DISTANCE = int(FS * 0.4)  # min 0.4 s between peaks (max 150 bpm)
PEAK_MIN_HEIGHT = 0.5              # mmHg — ignore sub-threshold ripple

# Standard oscillometric ratios
SYSTOLIC_RATIO = 0.50
DIASTOLIC_RATIO = 0.70

SENTINEL = None


def _estimate_bp(peaks_idx, envelope, cuff_at_peaks):
    if len(peaks_idx) < 3:
        return None

    peak_max_i = int(np.argmax(envelope))
    map_pressure = cuff_at_peaks[peak_max_i]
    max_amp = envelope[peak_max_i]

    # Systolic: highest cuff pressure where amplitude >= SYSTOLIC_RATIO * max
    sys_candidates = [
        cuff_at_peaks[i] for i in range(peak_max_i + 1)
        if envelope[i] >= SYSTOLIC_RATIO * max_amp
    ]
    systolic = max(sys_candidates) if sys_candidates else None

    # Diastolic: lowest cuff pressure after MAP where amplitude <= DIASTOLIC_RATIO * max
    dia_candidates = [
        cuff_at_peaks[i] for i in range(peak_max_i, len(peaks_idx))
        if envelope[i] <= DIASTOLIC_RATIO * max_amp
    ]
    diastolic = min(dia_candidates) if dia_candidates else None

    return {
        'systolic': systolic,
        'MAP': map_pressure,
        'diastolic': diastolic,
    }


def envelope_process(filtered_queue: mp.Queue, results_queue: mp.Queue, stop_event: mp.Event):
    acc_t = []
    acc_filtered = []
    acc_cuff = []
    bp_result = None

    while True:
        chunk = filtered_queue.get()
        if chunk is SENTINEL:
            results_queue.put({'type': 'done', 'bp': bp_result})
            break

        for t, fval, cuff in chunk:
            acc_t.append(t)
            acc_filtered.append(fval)
            acc_cuff.append(cuff)

        # Subtract slowly-varying baseline (the cuff ramp) to isolate oscillations
        baseline = np.array(acc_cuff)
        oscillations = np.array(acc_filtered) - baseline

        peaks_idx, _ = find_peaks(
            np.abs(oscillations),
            distance=PEAK_MIN_DISTANCE,
            height=PEAK_MIN_HEIGHT,
        )

        envelope = np.abs(oscillations[peaks_idx]) if len(peaks_idx) > 0 else np.array([])
        cuff_at_peaks = np.array(acc_cuff)[peaks_idx] if len(peaks_idx) > 0 else np.array([])

        if len(peaks_idx) >= 3:
            bp_result = _estimate_bp(peaks_idx, envelope, cuff_at_peaks)

        results_queue.put({
            'type': 'update',
            'filtered_chunk': chunk,
            'all_t': list(acc_t),
            'all_filtered': list(acc_filtered),
            'all_cuff': list(acc_cuff),
            'oscillations': oscillations.tolist(),
            'peaks_t': [acc_t[i] for i in peaks_idx],
            'peaks_amp': envelope.tolist(),
            'peaks_cuff': cuff_at_peaks.tolist(),
            'bp': bp_result,
        })

    print(f"[Envelope] Done. BP result: {bp_result}")
