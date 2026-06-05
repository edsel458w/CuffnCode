import multiprocessing as mp
import queue
import sys

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.animation import FuncAnimation
import numpy as np

from src import simulator, filter_worker, envelope_worker

# ── Ground-truth values for end-of-run verification ──────────────────────────
SYS_TRUE = simulator.SYS_TRUE
MAP_TRUE = simulator.MAP_TRUE
DIA_TRUE = simulator.DIA_TRUE


def _make_figure():
    fig = plt.figure(figsize=(11, 7), facecolor='#1a1a2e')
    fig.suptitle('CuffnCode — Parallel Blood Pressure Estimation\n'
                 'IFB 206 Komputasi Paralel', color='white', fontsize=13)

    gs = gridspec.GridSpec(3, 1, hspace=0.45, figure=fig)

    ax1 = fig.add_subplot(gs[0])   # raw + filtered signal
    ax2 = fig.add_subplot(gs[1])   # cuff pressure ramp
    ax3 = fig.add_subplot(gs[2])   # oscillation envelope + peaks

    for ax in (ax1, ax2, ax3):
        ax.set_facecolor('#0f0f23')
        ax.tick_params(colors='#aaaacc')
        for spine in ax.spines.values():
            spine.set_edgecolor('#333366')

    ax1.set_ylabel('Pressure (mmHg)', color='#aaaacc', fontsize=9)
    ax1.set_title('Raw Signal (grey)  vs  Filtered (cyan)', color='#aaaacc', fontsize=9)

    ax2.set_ylabel('Cuff (mmHg)', color='#aaaacc', fontsize=9)
    ax2.set_title('Cuff Pressure Deflation Ramp', color='#aaaacc', fontsize=9)

    ax3.set_ylabel('Oscillation (mmHg)', color='#aaaacc', fontsize=9)
    ax3.set_xlabel('Time (s)', color='#aaaacc', fontsize=9)
    ax3.set_title('Oscillation Envelope + Detected Peaks', color='#aaaacc', fontsize=9)

    return fig, ax1, ax2, ax3


def main():
    raw_q = mp.Queue(maxsize=20)
    filtered_q = mp.Queue(maxsize=20)
    results_q = mp.Queue(maxsize=60)
    stop_event = mp.Event()

    p1 = mp.Process(target=simulator.acquisition_process,
                    args=(raw_q, stop_event), name='Acquisition', daemon=True)
    p2 = mp.Process(target=filter_worker.filter_process,
                    args=(raw_q, filtered_q, stop_event), name='Filter', daemon=True)
    p3 = mp.Process(target=envelope_worker.envelope_process,
                    args=(filtered_q, results_q, stop_event), name='Envelope', daemon=True)

    p1.start()
    p2.start()
    p3.start()
    print(f"[Main] Processes started — "
          f"Acquisition PID:{p1.pid}  Filter PID:{p2.pid}  Envelope PID:{p3.pid}")

    # ── Shared plot state ─────────────────────────────────────────────────────
    state = {
        'raw_t': [], 'raw_v': [],
        'filt_t': [], 'filt_v': [],
        'cuff_t': [], 'cuff_v': [],
        'osc_t': [], 'osc_v': [],
        'peaks_t': [], 'peaks_amp': [],
        'bp': None,
        'done': False,
    }

    fig, ax1, ax2, ax3 = _make_figure()

    line_raw,   = ax1.plot([], [], color='#555577', lw=0.8, label='raw')
    line_filt,  = ax1.plot([], [], color='#00e5ff', lw=1.2, label='filtered')
    line_cuff,  = ax2.plot([], [], color='#ff9800', lw=1.5)
    line_osc,   = ax3.plot([], [], color='#69ff47', lw=1.0)
    scat_peaks  = ax3.scatter([], [], color='#ff4081', zorder=5, s=40, label='peaks')

    bp_text = ax3.text(0.02, 0.92, '', transform=ax3.transAxes,
                       color='white', fontsize=9, verticalalignment='top',
                       bbox=dict(boxstyle='round', facecolor='#222244', alpha=0.8))

    ax1.legend(loc='upper right', fontsize=8, facecolor='#1a1a2e', labelcolor='white')
    ax3.legend(loc='upper right', fontsize=8, facecolor='#1a1a2e', labelcolor='white')

    def update(_frame):
        # Drain the results queue each animation tick
        try:
            while True:
                msg = results_q.get_nowait()
                if msg['type'] == 'done':
                    state['done'] = True
                    state['bp'] = msg['bp']
                    break

                state['osc_t'] = msg['all_t']
                state['osc_v'] = msg['oscillations']
                state['peaks_t'] = msg['peaks_t']
                state['peaks_amp'] = msg['peaks_amp']
                state['bp'] = msg['bp']

                for t, fval, cuff in msg['filtered_chunk']:
                    state['filt_t'].append(t)
                    state['filt_v'].append(fval)
                    state['cuff_t'].append(t)
                    state['cuff_v'].append(cuff)
        except queue.Empty:
            pass

        # Update line data
        if state['filt_t']:
            t_arr = np.array(state['filt_t'])
            line_filt.set_data(t_arr, state['filt_v'])
            line_cuff.set_data(np.array(state['cuff_t']), state['cuff_v'])

            for ax in (ax1, ax2):
                ax.set_xlim(0, max(t_arr[-1] + 1, 5))

            ax1.set_ylim(min(state['filt_v']) - 5, max(state['filt_v']) + 5)
            ax2.set_ylim(40, 190)

        if state['osc_t']:
            t_arr = np.array(state['osc_t'])
            line_osc.set_data(t_arr, state['osc_v'])
            ax3.set_xlim(0, max(t_arr[-1] + 1, 5))
            osc_arr = np.array(state['osc_v'])
            ax3.set_ylim(osc_arr.min() - 1, osc_arr.max() + 1)

        if state['peaks_t']:
            scat_peaks.set_offsets(
                np.column_stack([state['peaks_t'], state['peaks_amp']])
            )

        if state['bp']:
            bp = state['bp']
            sys_v = f"{bp['systolic']:.0f}" if bp['systolic'] else '?'
            map_v = f"{bp['MAP']:.0f}"
            dia_v = f"{bp['diastolic']:.0f}" if bp['diastolic'] else '?'
            bp_text.set_text(f"SYS: {sys_v}  MAP: {map_v}  DIA: {dia_v} mmHg")

        if state['done']:
            ani.event_source.stop()
            _print_summary(state['bp'])

        return line_raw, line_filt, line_cuff, line_osc, scat_peaks, bp_text

    ani = FuncAnimation(fig, update, interval=120, blit=False, cache_frame_data=False)
    plt.tight_layout(rect=[0, 0, 1, 0.94])
    plt.show()

    stop_event.set()
    p1.join(timeout=3)
    p2.join(timeout=3)
    p3.join(timeout=3)
    print("[Main] All processes joined.")


def _print_summary(bp):
    print("\n" + "=" * 48)
    print("  Blood Pressure Estimation Summary")
    print("=" * 48)
    if bp:
        sys_v = bp['systolic']
        map_v = bp['MAP']
        dia_v = bp['diastolic']
        print(f"  {'':20s}  {'Estimated':>9}  {'Expected':>9}")
        print(f"  {'Systolic (SYS)':20s}  {sys_v if sys_v else 'N/A':>9.0f}  {SYS_TRUE:>9.0f}")
        print(f"  {'Mean Arterial (MAP)':20s}  {map_v:>9.0f}  {MAP_TRUE:>9.0f}")
        print(f"  {'Diastolic (DIA)':20s}  {dia_v if dia_v else 'N/A':>9.0f}  {DIA_TRUE:>9.0f}")
    else:
        print("  Not enough oscillation peaks detected.")
    print("=" * 48 + "\n")


if __name__ == '__main__':
    mp.set_start_method('spawn')
    main()
