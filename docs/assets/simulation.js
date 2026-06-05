// CuffnCode — Parallel BP Simulation
// Mirrors the Python pipeline in src/ (simulator.py → filter_worker.py → envelope_worker.py → main.py)

// ── SIMULATION PARAMETERS ──────────────────────────────────────────────────
const FS         = 200;
const DEFLATION  = 4.5;   // mmHg/sec
const CUFF_START = 180;
const CUFF_STOP  = 50;
const MAP_TRUE   = 100;
const A_MAX      = 6.0;
const SIGMA      = 22.0;
const OSC_FREQ   = 1.2;   // Hz (~72 bpm)
const NOISE_STD  = 0.3;
const ANIM_SPEED = 6;     // samples per animation frame
const WINDOW     = 400;   // visible samples in sliding-window charts

// ── UTILITIES ──────────────────────────────────────────────────────────────
function gaussNoise(std) {
  const u1 = Math.max(1e-10, Math.random());
  return std * Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * Math.random());
}

function cuffP(t)   { return CUFF_START - DEFLATION * t; }
function oscAmp(cp) { return A_MAX * Math.exp(-Math.pow(cp - MAP_TRUE, 2) / (2 * SIGMA * SIGMA)); }

// 1st-order IIR low-pass — browser equivalent of scipy Butterworth LP
function makeLPF(cutoff) {
  const rc = 1 / (2 * Math.PI * cutoff);
  const dt = 1 / FS;
  const a  = dt / (rc + dt);
  let prev = null;
  return x => { prev = prev === null ? x : a * x + (1 - a) * prev; return prev; };
}

// ── PROCESS 1: DATA ACQUISITION (simulator.py) ────────────────────────────
function precompute() {
  const lpf  = makeLPF(10);
  const data = [];
  const dt   = 1 / FS;
  let t = 0;
  while (cuffP(t) > CUFF_STOP) {
    const cp  = cuffP(t);
    const raw = cp + oscAmp(cp) * Math.sin(2 * Math.PI * OSC_FREQ * t) + gaussNoise(NOISE_STD);
    const flt = lpf(raw);
    data.push({ t: +t.toFixed(4), raw, flt, cp, osc: flt - cp });
    t += dt;
  }
  return data;
}

// ── PROCESS 3: PEAK DETECTION (envelope_worker.py) ────────────────────────
function detectPeaks(data) {
  const minDist = Math.round(FS * 0.4);
  const peaks   = [];
  const vals    = data.map(d => Math.abs(d.osc));
  for (let i = 1; i < vals.length - 1; i++) {
    if (vals[i] > 0.5 && vals[i] > vals[i - 1] && vals[i] > vals[i + 1]) {
      if (!peaks.length || i - peaks[peaks.length - 1] >= minDist) peaks.push(i);
    }
  }
  return peaks;
}

// ── BP ESTIMATION (oscillometric ratios) ──────────────────────────────────
function estimateBP(data, peaks) {
  if (peaks.length < 3) return null;
  const env   = peaks.map(i => Math.abs(data[i].osc));
  const cuffs = peaks.map(i => data[i].cp);
  const maxA  = Math.max(...env);
  const maxI  = env.indexOf(maxA);
  const MAP   = cuffs[maxI];
  let sys = null, dia = null;
  for (let i = 0; i <= maxI; i++)
    if (env[i] >= 0.50 * maxA) sys = Math.max(sys !== null ? sys : 0, cuffs[i]);
  for (let i = maxI; i < peaks.length; i++)
    if (env[i] <= 0.70 * maxA) dia = Math.min(dia !== null ? dia : 999, cuffs[i]);
  return { sys, MAP, dia };
}

// ── CHART SETUP ───────────────────────────────────────────────────────────
const BASE_OPTS = {
  animation: false,
  responsive: true,
  maintainAspectRatio: true,
  plugins: {
    legend:  { labels: { color: '#8888aa', font: { size: 11 } } },
    tooltip: { enabled: false },
  },
  scales: {
    x: { ticks: { color: '#555577', maxTicksLimit: 8, font: { size: 10 } }, grid: { color: '#1a1a35' } },
    y: { ticks: { color: '#555577', font: { size: 10 } },                   grid: { color: '#1a1a35' } },
  },
};

function mkAxisOpts(xLabel, yLabel, yMin, yMax) {
  return {
    x: { ...BASE_OPTS.scales.x, title: { display: true, text: xLabel, color: '#555577', font: { size: 10 } } },
    y: { ...BASE_OPTS.scales.y, min: yMin, max: yMax, title: { display: true, text: yLabel, color: '#555577', font: { size: 10 } } },
  };
}

function mkLineChart(id, label, color, yLabel, yMin, yMax) {
  return new Chart(document.getElementById(id).getContext('2d'), {
    type: 'line',
    data: {
      labels: [],
      datasets: [{ label, data: [], borderColor: color, borderWidth: 1.8, pointRadius: 0, fill: false }],
    },
    options: { ...BASE_OPTS, scales: mkAxisOpts('Time (s)', yLabel, yMin, yMax) },
  });
}

let chartCuff, chartSignal, chartEnv;

function initCharts() {
  chartCuff   = mkLineChart('chartCuff',   'Cuff Pressure',  '#ff9800', 'Pressure (mmHg)', 40, 190);
  chartSignal = mkLineChart('chartSignal', 'Filtered Signal', '#00e5ff', 'Pressure (mmHg)', 40, 190);

  chartEnv = new Chart(document.getElementById('chartEnv').getContext('2d'), {
    data: {
      labels: [],
      datasets: [
        { type: 'line',    label: 'Oscillation', data: [], borderColor: '#69ff47', borderWidth: 1.5, pointRadius: 0, fill: false, yAxisID: 'y' },
        { type: 'scatter', label: 'Peaks',        data: [], backgroundColor: '#ff4081', pointRadius: 5, pointHoverRadius: 7,         yAxisID: 'y' },
      ],
    },
    options: { ...BASE_OPTS, scales: mkAxisOpts('Time (s)', 'Oscillation (mmHg)', undefined, undefined) },
  });
}

// ── ANIMATION STATE ───────────────────────────────────────────────────────
let simData = [], allPeaks = [], frameIdx = 0, animId = null, running = false;

function startSim() {
  if (running) return;
  running = true;
  document.getElementById('btnStart').disabled = true;
  document.getElementById('btnReset').disabled = false;
  setStatus('Initializing simulation…');

  setTimeout(() => {
    simData  = precompute();
    allPeaks = detectPeaks(simData);
    frameIdx = 0;
    setChip('chip1', 'active');
    setStatus('Running — cuff deflating from 180 → 50 mmHg…');
    requestAnimationFrame(tick);
  }, 80);
}

function tick() {
  const end  = Math.min(frameIdx + ANIM_SPEED, simData.length);
  const prog = frameIdx / simData.length;

  if (prog > 0.02) setChip('chip2', 'active');
  if (prog > 0.05) { setChip('chip3', 'active'); setChip('chipM', 'main-active'); }

  // Sliding window
  const winStart = Math.max(0, end - WINDOW);
  const vis      = simData.slice(winStart, end);
  const tLabels  = vis.map(d => d.t.toFixed(1));

  // Cuff chart (full history, always growing)
  const cuffSlice = simData.slice(0, end);
  chartCuff.data.labels             = cuffSlice.map(d => d.t.toFixed(1));
  chartCuff.data.datasets[0].data   = cuffSlice.map(d => d.cp);
  chartCuff.update('none');

  // Signal chart (sliding window)
  chartSignal.data.labels           = tLabels;
  chartSignal.data.datasets[0].data = vis.map(d => d.flt);
  chartSignal.update('none');

  // Envelope chart (sliding window + peaks scatter)
  chartEnv.data.labels              = tLabels;
  chartEnv.data.datasets[0].data   = vis.map(d => d.osc);
  chartEnv.data.datasets[1].data   = allPeaks
    .filter(p => p >= winStart && p < end)
    .map(p => ({ x: simData[p].t.toFixed(1), y: simData[p].osc }));
  chartEnv.update('none');

  // Incremental BP estimation
  const curPeaks = allPeaks.filter(p => p < end);
  const bp = estimateBP(simData, curPeaks);
  if (bp) updateBP(bp, curPeaks.length);

  frameIdx = end;
  if (frameIdx < simData.length) {
    animId = requestAnimationFrame(tick);
  } else {
    onDone(bp);
  }
}

function updateBP(bp, peakCount) {
  if (bp.sys !== null) document.getElementById('valSys').textContent = Math.round(bp.sys);
  if (bp.MAP !== null) document.getElementById('valMap').textContent = Math.round(bp.MAP);
  if (bp.dia !== null) document.getElementById('valDia').textContent = Math.round(bp.dia);
  document.getElementById('bpNote').textContent = `${peakCount} peaks detected`;
}

function onDone(bp) {
  running = false;
  document.getElementById('btnStart').disabled = false;
  const sys = bp && bp.sys ? Math.round(bp.sys) : '?';
  const map = bp && bp.MAP ? Math.round(bp.MAP) : '?';
  const dia = bp && bp.dia ? Math.round(bp.dia) : '?';
  setStatus(`Done ✓  Estimated: SYS ${sys}  MAP ${map}  DIA ${dia} mmHg  (expected: 120 / 100 / 80)`);
  document.getElementById('bpNote').textContent = 'Measurement complete ✓';
}

function resetSim() {
  if (animId) cancelAnimationFrame(animId);
  running = false; frameIdx = 0; simData = []; allPeaks = [];

  ['chip1', 'chip2', 'chip3', 'chipM'].forEach(id => {
    document.getElementById(id).className = 'proc-chip';
  });
  ['valSys', 'valMap', 'valDia'].forEach(id => {
    document.getElementById(id).textContent = '---';
  });
  document.getElementById('bpNote').textContent = 'Waiting for oscillation peaks…';
  setStatus('Ready — press Start to begin.');

  [chartCuff, chartSignal].forEach(c => {
    c.data.labels = [];
    c.data.datasets.forEach(d => d.data = []);
    c.update('none');
  });
  chartEnv.data.labels = [];
  chartEnv.data.datasets.forEach(d => d.data = []);
  chartEnv.update('none');

  document.getElementById('btnStart').disabled = false;
  document.getElementById('btnReset').disabled = true;
}

function setChip(id, cls) {
  const el = document.getElementById(id);
  if (!el.classList.contains(cls)) el.className = 'proc-chip ' + cls;
}
function setStatus(msg) { document.getElementById('statusMsg').textContent = msg; }

// ── BOOT ──────────────────────────────────────────────────────────────────
initCharts();
