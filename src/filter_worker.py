import multiprocessing as mp
import numpy as np
from scipy.signal import butter, iirnotch, sosfilt, sosfilt_zi, zpk2sos

FS = 500
LP_CUTOFF = 10.0   # Hz — passes cardiac oscillation (1.2 Hz), kills HF noise
NOTCH_FREQ = 60.0  # Hz — Indonesian grid power-line frequency
NOTCH_Q = 30.0

SENTINEL = None


def _design_filters():
    sos_lp = butter(4, LP_CUTOFF / (FS / 2), btype='low', output='sos')

    # iirnotch returns (b, a); convert to sos for numerical stability
    b_n, a_n = iirnotch(NOTCH_FREQ / (FS / 2), NOTCH_Q)
    from scipy.signal import tf2zpk
    z, p, k = tf2zpk(b_n, a_n)
    sos_notch = zpk2sos(z, p, k)

    return sos_lp, sos_notch


def filter_process(raw_queue: mp.Queue, filtered_queue: mp.Queue, stop_event: mp.Event):
    sos_lp, sos_notch = _design_filters()

    zi_notch = None
    zi_lp = None

    while True:
        chunk = raw_queue.get()
        if chunk is SENTINEL:
            filtered_queue.put(SENTINEL)
            break

        raw_values = np.array([s[1] for s in chunk], dtype=np.float64)

        # Initialize filter states from first sample (avoids startup transient)
        if zi_notch is None:
            zi_notch = sosfilt_zi(sos_notch) * raw_values[0]
            zi_lp = sosfilt_zi(sos_lp) * raw_values[0]

        notched, zi_notch = sosfilt(sos_notch, raw_values, zi=zi_notch)
        filtered, zi_lp = sosfilt(sos_lp, notched, zi=zi_lp)

        out = [(chunk[i][0], float(filtered[i]), chunk[i][2]) for i in range(len(chunk))]
        filtered_queue.put(out)

    print("[Filter] Done.")
