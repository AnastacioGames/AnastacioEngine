// Status follows the actual engine log, rather than an independent page timer.
(function () {
  const status = document.createElement('div');
  status.id = 'reverb-ab-status';
  status.style.cssText = 'position:fixed;top:12px;left:12px;z-index:10000;background:#172033;color:white;padding:16px;font:20px sans-serif;pointer-events:none;max-width:600px';
  status.textContent = 'Clique em Jogar. Seco / caverna alternam a cada 2 segundos.';
  document.body.appendChild(status);
  const original = console.log;
  console.log = function (...args) {
    const match = args.join(' ').match(/\[reverb-ab\] SWITCH phase=(\d+) state=(\w+)/);
    if (match) {
      status.textContent = (match[2] === 'SECO' ? 'A — SECO' : 'B — CAVERNA (reverb solicitado)') +
        ' · Som contínuo; 2 segundos por estado. Reverb solicitado no máximo, com decaimento de 10 s. O backend Web atual não oferece EFX; os estados podem soar iguais.';
      status.style.background = match[2] === 'SECO' ? '#172033' : '#493073';
    }
    original.apply(console, args);
  };
})();
