# Pendências Web: plano de execução

Roteiro das frentes Web que sobraram da rodada de 2026-09-20. Os marcos concluídos estão no
[changelog-arquivo.md](changelog-arquivo.md) (entradas Web de 2026-09-12 a 2026-10-04):

- M0 (manifesto e pré-voo confiáveis), M2 (cinco campos DNA `unsigned char` + checagem RNA no
  Emscripten), M3 (índice de filtro, resize do bloom, resolução dinâmica sem GPU timer, medição em
  celular) e T5 (`perf-run.cjs`/`frame-time-perf.js`): concluídos.
- R1 (ABI dos callbacks de `Range.constraints`) e `aud` `METH_NOARGS`: corrigidos e validados no navegador.
- Áudio AudioWorklet (2026-10-04): ouvido sem problemas no PC e no celular.

A lista curta do que está aberto fica na seção Web do [roadmap](roadmap.md).

## Regras de trabalho

- Seguir `AGENTS.md`: uma peça autocontida por vez, build e execução pertinentes antes de dar como feito.
- Separar análise estática, teste automatizado, execução no navegador e aceite visual/auditivo do usuário.
- Não implementar marcos condicionais sem a condição de entrada.
- Push/PR só com pedido do usuário.

## Em aberto

### M1 — importar o pré-voo no editor

O relatório estruturado de shader/Python existe (`Module.onDiagnostic`, estágio e `structured: true`).
Falta o passo 5: importar o relatório de erros no editor pela UI. Hoje "Importar pré-voo Web" lê JSON
manual. Arquivos: `tools/web/package-web.py` (coleta) e `source/release/scripts/modules/range_web/preflight.py`.
O pré-voo só cobre caminhos executados: cena não visitada e shader não compilado ficam fora.

### SSAO na Web

Aguarda o usuário comparar o SSAO na Web com o desktop.

### M4 — fusão de filtros / bloom reduzido (adiado em 2026-09-23)

Celular físico (OPPO Reno14 5G) mediu p50 22 ms sem filtros 2D; picos do p95 são esporádicos.
Reabrir só se um jogo com filtros 2D medir mal. Se reabrir, uma alternativa por vez contra o baseline:

1. FXAA seguido de tonemap no mesmo passe, se adjacentes. Validar aparência (quantização/clamp).
2. Grayscale/sepia/invert compostos quando a sequência for conhecida. Não fundir shaders customizados.
3. Bloom móvel numa escala só (4 passes em vez de 8), como opção de qualidade explícita.

Não fundir blur H/V separável (22 amostras viram 121). Não fundir SSR, SSAO ou scatter por proximidade.
Aceite: GLSL compilado no navegador, comparação visual no jogo e ganho repetível de frame.

### M5 — áudio 3D pelo SDL/Audaspace (só se um jogo precisar)

Entrada: jogo que precise de posição, distância, cone ou Doppler, com cena reproduzível.

- `SoftwareDevice::SoftwareHandle::update` já faz o cálculo 3D para fontes mono.
- `LA_Launcher.cpp`: configuração 3D desligada no Web por `if (false)`.
- `AUD_Device.cpp`: setters 3D fazem cast para `I3DDevice` sem validar. Trocar índice de dispositivo
  por checagem de interface; proteger dispositivo nulo.
- `KX_SoundActuator.cpp`, `KX_Speaker.cpp`: listener, posição relativa, câmera.

Aceite com fones e fontes mono: esquerda/direita, distância, giro do listener, cone, Doppler, várias
vozes, loop/seek, troca de cena e pausa. Repetir no celular. Se bastar, não iniciar M6.

### M6 — backend OpenAL no Emscripten (só se M5 for insuficiente)

O Emscripten tem OpenAL 1.1 sobre Web Audio (`-lopenal`). EFX não existe por padrão.
`OpenALDevice.cpp` usa thread, sleep e join no streaming; exige atualização cooperativa.
Começar por prova pequena de playback/streaming.

Descartados nesta rodada: backend Web Audio próprio e NumPy só para `Sound.data()`/`buffer()`.

### R2 — isolamento e confirmação de saves (não iniciado)

`KX_PythonInit.cpp` (`pathGamePythonConfig`/`saveGamePythonConfig`) e
`source/source/blenderplayer/web_idbfs_prerun.js`.

- `/saves/game.save` é por origem: dois jogos na mesma origem podem colidir.
- A gravação no MEMFS acontece antes do `FS.syncfs` assíncrono; erro pode ficar só no console.

Proposta: identidade estável do jogo (independente da versão do build) e migração do caminho legado,
sem copiar/apagar save de dono ambíguo. Definir contrato de conclusão/erro do sync; leitura inicial
falha não pode levar a sobrescrever estado recuperável. Preservar a API antiga.

Validar: dois jogos na mesma origem, atualização do jogo, reload, erro de sync, armazenamento
indisponível e fechar a aba logo após salvar.

### R3 — sobras de áudio

Arquivo inexistente/corrompido já vira exceção Python (`-fexceptions` só nos alvos audaspace e no
link do RangeRuntime; `claude_r3_probe.py` termina em `[r3] TODOS`). Ainda sem sonda: `cache()`,
`reverse()`, `pause()`/`stop()`.

## Entrega por peça

Problema e resultado, arquivos alterados, comandos realmente executados, navegador/aparelho/cena,
e o que depende de aceite do usuário. Documentar conforme `AGENTS.md`.

Referências: [áudio no Emscripten](https://emscripten.org/docs/porting/Audio.html),
[web-audio-analysis.md](web-audio-analysis.md).
