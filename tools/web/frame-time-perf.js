(function () {
  if (new URLSearchParams(location.search).get('perf') !== '1') return;
  const samples = [], max = 600;
  let previous;
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
    return { count: a.length, p50_ms: q(.50), p95_ms: q(.95), min_ms: a[0] || 0, max_ms: a[a.length - 1] || 0 };
  };
  window.addEventListener('beforeunload', () => console.info('[perf]', JSON.stringify(window.__rangePerf())));
})();
