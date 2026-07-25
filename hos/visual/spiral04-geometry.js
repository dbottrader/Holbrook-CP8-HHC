// Repaired HOS Spiral04 geometry renderer derived from the 2025 Drive source.
// Frequency values are visual parameter namespaces, not physical or cryptographic claims.

const CONFIG = Object.freeze({
  viewportScale: 0.8,
  rate: 0.5,
  telemetryIntervalMs: 1000,
  historySize: 60,
  steps: 500,
  fadeAlpha: 0.95,
});

const state = {
  fx: 3.0,
  fy: 2.0,
  phase: Math.PI / 2,
  amplitude: 150,
  baseHue: 200,
  lastTimestamp: 0,
  time: 0,
  telemetryTimer: 0,
  dtHistory: [],
};

const telemetry = {
  frameTimeMs: 0,
  frameTimeVariance: 0,
  pathDensity: 0,
  hueRate: 0,
  lastHue: state.baseHue,
};

let mainCanvas;
let mainCtx;
let bufferCanvas;
let bufferCtx;
let viewWidth;
let viewHeight;
let dpr = 1;

function variance(values) {
  if (values.length < 2) return 0;
  const mean = values.reduce((sum, value) => sum + value, 0) / values.length;
  return values.reduce((sum, value) => sum + (value - mean) ** 2, 0) / values.length;
}

function resizeCanvas() {
  dpr = Math.max(1, Math.min(2, window.devicePixelRatio || 1));
  viewWidth = Math.max(320, window.innerWidth * CONFIG.viewportScale);
  viewHeight = Math.max(240, window.innerHeight * CONFIG.viewportScale);

  mainCanvas.width = Math.floor(viewWidth * dpr);
  mainCanvas.height = Math.floor(viewHeight * dpr);
  mainCanvas.style.width = `${viewWidth}px`;
  mainCanvas.style.height = `${viewHeight}px`;

  mainCtx.setTransform(dpr, 0, 0, dpr, 0, 0);

  bufferCanvas.width = Math.floor(viewWidth);
  bufferCanvas.height = Math.floor(viewHeight);
  bufferCtx.imageSmoothingEnabled = false;
}

function initializeCanvas() {
  mainCanvas = document.getElementById('hos-canvas');
  if (!mainCanvas) throw new Error('Missing #hos-canvas element');

  mainCtx = mainCanvas.getContext('2d');
  bufferCanvas = document.createElement('canvas');
  bufferCtx = bufferCanvas.getContext('2d');

  resizeCanvas();
  window.addEventListener('resize', resizeCanvas, { passive: true });
  requestAnimationFrame(draw);
}

function streamTelemetry() {
  const event = new CustomEvent('hos:telemetry', {
    detail: {
      ...telemetry,
      fx: state.fx,
      fy: state.fy,
      timestamp: new Date().toISOString(),
    },
  });
  window.dispatchEvent(event);
}

function draw(timestamp) {
  const rawDelta = state.lastTimestamp ? (timestamp - state.lastTimestamp) / 1000 : 0;
  const dt = Math.min(Math.max(rawDelta, 0), 0.1);
  state.lastTimestamp = timestamp;
  state.time += dt * CONFIG.rate;

  const frameTimeMs = dt * 1000;
  state.dtHistory.push(frameTimeMs);
  if (state.dtHistory.length > CONFIG.historySize) state.dtHistory.shift();
  telemetry.frameTimeMs = frameTimeMs;
  telemetry.frameTimeVariance = variance(state.dtHistory);

  bufferCtx.setTransform(1, 0, 0, 1, 0, 0);
  bufferCtx.globalCompositeOperation = 'copy';
  bufferCtx.globalAlpha = CONFIG.fadeAlpha;
  bufferCtx.drawImage(mainCanvas, 0, 0, viewWidth, viewHeight);
  bufferCtx.globalCompositeOperation = 'source-over';
  bufferCtx.globalAlpha = 1;

  const hue = state.baseHue + 5 * Math.sin(0.05 * state.time);
  telemetry.hueRate = dt > 0 ? Math.abs(hue - telemetry.lastHue) / dt : 0;
  telemetry.lastHue = hue;
  telemetry.pathDensity = 0;

  bufferCtx.setTransform(1, 0, 0, 1, viewWidth / 2, viewHeight / 2);
  bufferCtx.rotate(state.time * 0.005);
  bufferCtx.strokeStyle = `hsl(${hue}, 80%, 60%)`;
  bufferCtx.lineWidth = 1.5;
  bufferCtx.beginPath();

  const currentAmplitude = state.amplitude * (1 + 0.02 * Math.sin(0.02 * state.time));
  let previousX = Math.floor(currentAmplitude * Math.sin(state.phase));
  let previousY = 0;
  bufferCtx.moveTo(previousX, previousY);

  for (let i = 1; i < CONFIG.steps; i += 1) {
    const t = state.time + i * 0.01;
    const x = Math.floor(currentAmplitude * Math.sin(state.fx * t + state.phase));
    const y = Math.floor(currentAmplitude * Math.sin(state.fy * t));
    bufferCtx.lineTo(x, y);
    telemetry.pathDensity += Math.hypot(x - previousX, y - previousY);
    previousX = x;
    previousY = y;
  }

  bufferCtx.stroke();
  mainCtx.setTransform(dpr, 0, 0, dpr, 0, 0);
  mainCtx.clearRect(0, 0, viewWidth, viewHeight);
  mainCtx.drawImage(bufferCanvas, 0, 0, viewWidth, viewHeight);

  state.telemetryTimer += frameTimeMs;
  if (state.telemetryTimer >= CONFIG.telemetryIntervalMs) {
    streamTelemetry();
    state.telemetryTimer = 0;
  }

  requestAnimationFrame(draw);
}

document.addEventListener('DOMContentLoaded', initializeCanvas);
