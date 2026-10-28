# Performance Report

Ferramenta da engine (vai no editor publicado) para qualquer jogo: **Game > Performance > Play and Measure**
roda a cena no `AnastacioRuntime` com o trace ligado e, quando o jogo fecha, gera `report.html` e abre no
navegador. Inspirada no Range Trace (que continua sendo a ferramenta do RolimaRacer, ver `range-trace.md`) e
usando o mesmo motor de gravação (`CM_Trace`).

- Código: `source/release/scripts/startup/bl_operators/anastacio_performance_report.py` (operadores e pasta),
  `source/release/scripts/modules/anastacio_perf_report.py` (análise + HTML; roda também fora do editor:
  `python anastacio_perf_report.py <pasta>`), menu em `bl_ui/space_info.py` (`INFO_MT_game_performance`).
- Relatórios em `<config do usuário>/datafiles/performance_reports/<jogo>-<data>-<hora>/`
  (`trace.jsonl`, `shaders.txt`, `profile.txt`, `settings.json`, `summary.json`, `report.html`). **Open Last Report** e
  **Open Reports Folder** ficam no submenu **Reports**.
- **Simulate Weak PC** (submenu): roda o Measure com a GPU N vezes mais lenta; ver `weak-pc-simulator.md`.
  O relatório traz **GPU time by step** (tempo de GPU por etapa + estimativa numa GPU fraca).
- Cena salva roda do próprio arquivo (caminhos relativos do jogo funcionam); com mudanças não salvas, uma cópia
  `_performance_report_<pid>.range` na mesma pasta, apagada no fim.
- Módulos ligados: `load,usage,frames,work,scripts,runtime` + `RANGE_SHADER_LOG`.
  - `scripts` (novo): tempo por frame de cada componente Python (por classe) e controller Python (por script).
  - `runtime` (novo): memória do processo a cada segundo, sons iniciados (Sound actuator, speaker, World Sound)
    e cenas adicionadas/removidas.
- Relatório: cartões com cor (verde/amarelo/vermelho), **O que fazer** (recomendações automáticas), comparação
  com o relatório anterior do mesmo jogo, gráfico do frame com picos, cenas e sons, memória, onde vai o tempo,
  scripts, picos (com script mais pesado e cargas do momento), cargas durante o jogo, shaders, carregamento por
  cena, carregado mas nunca desenhado, sons e contadores por frame.
- A inicialização (até 60 frames seguidos sem pico) aparece no topo e não conta nos números.
- Visual: cabeçalho com veredito (roda liso / vale olhar / precisa de ajustes), barra de navegação fixa entre seções,
  tema claro e escuro (segue o sistema; botão no canto alterna e lembra a escolha no navegador).
- Traduções pt_BR/es/ru em `modules/range_web/translations_perf.py` (es/ru pedem revisão nativa); o relatório sai
  no idioma da interface do editor.
