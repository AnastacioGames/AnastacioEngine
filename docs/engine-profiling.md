# Profiler da engine (`KX_EngineProfiler`)

Ferramenta de diagnóstico de performance da própria engine (não é o profile do overlay de debug do jogo).
Mede etapas nomeadas do frame na CPU e na GPU e grava um arquivo de texto com médias e picos.
Código: `source/source/gameengine/Ketsji/KX_EngineProfiler.h/.cpp`.

## Como ligar

**Pelo overlay (jeito normal):** com o jogo rodando e o profile de debug à mostra, marque
**Record engine profile** logo abaixo da tabela "Profile". Aparece `REC` e o caminho do arquivo
(padrão: `range_profile.txt` na pasta de trabalho). **GPU sync** liga o modo sync. Passar o mouse mostra a
dica no idioma da interface (en, pt_BR, es, ru). Desmarque para parar; ligar de novo reinicia as médias
com uma linha `START`.

**Por variável de ambiente** (já sai gravando desde o início, útil para travadas no carregamento):

| Variável | Efeito |
|---|---|
| `RANGE_PROFILE=<arquivo>` | liga o profiler e anexa as linhas nesse arquivo. Sem ela o custo é um branch por ponto de medição. |
| `RANGE_PROFILE_SPIKE_MS=<ms>` | limite mínimo para um frame contar como pico (padrão 25). |
| `RANGE_PROFILE_SYNC=1` | faz `glFinish` no fim do frame (`endframe.gpu_sync`). Sem ele, a espera pela GPU aparece dentro da etapa que bloqueou (normalmente `endframe.imgui` ou `endframe.swap`). Com ele, o FPS cai um pouco. |

Exemplo (PowerShell): `$env:RANGE_PROFILE="prof.txt"; AnastacioRuntime.exe jogo.range`.
Rodadas de ~10 s bastam; os primeiros 30 frames (carregamento) são ignorados.

## Como ler

- `AVG ...`: média de 120 frames (~2 s), picos incluídos. Primeiro vêm as categorias do profile da engine
  (`Physics`, `Logic`, `Shadows`…), depois `cpu:` e `gpu:` com as etapas nomeadas, em ms por frame.
- `SPIKE ...`: frame acima de `RANGE_PROFILE_SPIKE_MS` e com mais do dobro da média recente. Traz as
  mesmas colunas desse frame, as cenas adicionadas (`added:`) e os contadores de GPU (shaders compilados,
  texturas criadas, uploads de imagem) com quantos frames se passaram desde o último de cada tipo.
- Os tempos de `gpu:` são lidos 2 frames depois. Na média isso não importa; num pico, olhe também as
  linhas vizinhas.
- As etapas se aninham pelo nome: `launcher.render` contém `render.*`, que contém `render.endframe`, que
  contém `endframe.*`. `frame.outside` é o tempo fora do `NextFrame` da engine (render + eventos).

## Adicionar uma medição

```cpp
#include "KX_EngineProfiler.h"

{
	RANGE_PROFILE_SCOPE("physics.vehicles");   // tempo do resto do bloco
	...
}

KX_EngineProfiler::Sections prof;               // etapas em sequência
...
RANGE_PROFILE_MARK(prof, "minha.etapa1");       // só CPU
...
RANGE_PROFILE_MARK_GPU(prof, "minha.etapa2");   // CPU + timestamp de GPU (só dentro do render)
```

`RANGE_PROFILE_ADD("nome", ms)` soma um tempo medido à mão. Contadores em C ficam em
`GPU_profile_counters` (`GPU_shader.h`). Use nomes `area.etapa`; o limite é de 64 etapas.

## Log de tempo das animações (`RANGE_ANIM_LOG`)

Para bugs de animação que pulam, correm rápido demais ou não tocam. Com `RANGE_ANIM_LOG=<arquivo>` a engine grava,
com o tempo real desde a abertura do processo:

- `===== START`: cada início de jogo (P no editor), com tic rate, fps das animações e os relógios da engine;
- `F`: cada quadro, com o delta real, os passos de lógica e os relógios `frameT` (onde as actions começam) e
  `animT` (onde elas tocam), que devem andar juntos;
- `PLAY` / `DONE`: cada action iniciada e quanto tempo levou até terminar;
- `TIMESCALE`: mudanças de velocidade do jogo.

No Windows, `tools/debug/abrir_engine_log_animacao.bat` abre o editor com o log em `debug-logs/anim_log.txt`.
Desligado, o custo é um teste de booleano por chamada. Achou o bug do P em 2026-10-08: `animT` começava com o valor
da engine anterior (membro não inicializado).
