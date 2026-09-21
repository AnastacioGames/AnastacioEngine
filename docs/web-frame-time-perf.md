# Medição Web de frame-time

`tools/web/frame-time-perf.js` é um instrumento opcional para pacotes Web. Inclua-o como script auxiliar no HTML do pacote e abra a página com `?perf=1`; sem esse parâmetro não instala nenhum hook.

Enquanto ativo, coleta até 600 intervalos de `requestAnimationFrame`. No console, `__rangePerf()` retorna `count`, `p50_ms`, `p95_ms`, `min_ms` e `max_ms`. Ao sair da página, o mesmo objeto é impresso com o prefixo `[perf]`.

O p95 deve ser comparado entre execuções com a mesma cena, resolução, escala e navegador; a ferramenta mede o intervalo observado no navegador, não tempo de GPU isolado.
