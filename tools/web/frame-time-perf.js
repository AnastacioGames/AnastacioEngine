(function () {
  if (new URLSearchParams(location.search).get('perf') !== '1') return;
  const samples = [], max = 600;
  let previous;
  const canvasInfo = () => {
    const canvas = document.querySelector('canvas');
    return { canvasWidth: canvas ? canvas.width : 0, canvasHeight: canvas ? canvas.height : 0 };
  };
  function tick(now) {
    if (previous !== undefined) {
      samples.push(now - previous);
      if (samples.length > max) samples.shift();
    }
    previous = now;
    window.requestAnimationFrame(tick);
  }
  window.requestAnimationFrame(tick);
  window.__rangePerf = function () {
    const a = samples.slice().sort((x, y) => x - y);
    const q = p => a.length ? a[Math.min(a.length - 1, Math.floor((a.length - 1) * p))] : 0;
    return Object.assign({ count: a.length, p50_ms: q(.50), p95_ms: q(.95), min_ms: a[0] || 0,
      max_ms: a[a.length - 1] || 0, userAgent: navigator.userAgent,
      devicePixelRatio: window.devicePixelRatio }, canvasInfo());
  };
  const overlay = document.createElement('pre');
  overlay.id = 'perf';
  overlay.style.cssText = 'position:fixed;right:0;top:0;margin:0;padding:6px;background:#000c;color:#0f0;' +
    'font:12px monospace;z-index:2147483647;pointer-events:none;white-space:pre-wrap';
  const installOverlay = () => {
    document.body.appendChild(overlay);
    setInterval(() => {
      const r = window.__rangePerf();
      overlay.textContent = 'perf count ' + r.count + '\\np50 ' + r.p50_ms.toFixed(2) + ' ms\\np95 ' +
        r.p95_ms.toFixed(2) + ' ms\\nDPR ' + r.devicePixelRatio + '\\ncanvas ' + r.canvasWidth + 'x' + r.canvasHeight;
    }, 2000);
  };
  if (document.body) installOverlay(); else document.addEventListener('DOMContentLoaded', installOverlay, { once: true });
  window.addEventListener('beforeunload', () => console.info('[perf]', JSON.stringify(window.__rangePerf())));
})();
