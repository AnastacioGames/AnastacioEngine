# Medição Web de frame-time

`tools/web/frame-time-perf.js` é um instrumento opcional para pacotes Web. Inclua-o como script auxiliar no HTML do pacote e abra a página com `?perf=1`; sem esse parâmetro não instala nenhum hook.

Enquanto ativo, coleta até 600 intervalos de `requestAnimationFrame`. Um overlay no canto superior direito atualiza a cada dois segundos; `__rangePerf()` retorna também `userAgent`, `devicePixelRatio` e as dimensões do canvas. Ao sair da página, o mesmo objeto é impresso com o prefixo `[perf]`.

Para uma execução automatizada em Edge isolado, use `D:\\emsdk\\node\\24.19.0_64bit\\node.exe tools/web/perf-run.cjs <pacote>`. O pacote precisa já incluir este script conforme a proposta em `web-perf-hook-proposal.md`.

O p95 deve ser comparado entre execuções com a mesma cena, resolução, escala e navegador; a ferramenta mede o intervalo observado no navegador, não tempo de GPU isolado.
