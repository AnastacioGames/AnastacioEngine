# Roadmap

Somente itens abertos, pendentes de validação ou explicitamente adiados ficam neste arquivo. Recursos
concluídos estão resumidos em [`../relatorio-melhorias-anastacioengine.md`](../relatorio-melhorias-anastacioengine.md)
e detalhados no [`changelog.md`](changelog.md). O histórico Web que antes ocupava este arquivo (bloqueios de
shader/GL, causas raiz de teclado/mouse/gamepad, IDBFS, cena de filtros) está nas entradas de 2026-09-12 a
2026-09-20 do changelog.

Auditado contra o git log e o changelog em 2026-09-20.

## Prioridade atual

### Web (WebGL/WebAssembly)

Estado: o runtime Web roda no navegador com render (luz GLSL, normal map `.dds`, sombras, filtros 2D), teclado,
mouse, gamepad, save (IDBFS), áudio (WAV/MP3/OGG e módulo `aud`), transição de cenas e Python. O validador
(marcos A–D), o pré-voo (marco E, automático depois do Exportar Web) e o empacotamento estão implementados; os
pacotes de teste 8201–8211 foram aceitos pelo usuário. Planos: [web-profile-validation-plan.md](web-profile-validation-plan.md),
[web-deploy.md](web-deploy.md), [android-web-export-roadmap.md](android-web-export-roadmap.md).

Aberto:

- **Patch do SDL2/Emscripten** (gate de timestamp do gamepad): versionado em `tools/web/patch-sdl2-gamepad.py`
  e aplicado no configure (`platform_web.cmake`). Gamepad físico conferido no navegador em 2026-09-20 (D-pad
  corrigido em `DEV_Joystick`, ver changelog). Controle sem mapeamento standard ("USB Joystick", D-pad como hat
  no eixo 9) e save (IDBFS) testados e aceitos pelo usuário em 2026-09-20 ([roteiro](web-sdl2-gamepad-test.md)).
- **Extração de erros de shader/Python no pré-voo**: checkpoint de shader comum implementado em
  `8251b0dc` (evento estruturado WebGL com operação/estágio/origem/log e relatório v2); Python,
  shaders especiais/filtros e teste em navegador continuam pendentes. A heurística permanece como fallback;
  "Importar pré-voo Web" segue para JSON manual. Roteiro e handoff em
  [web-remaining-execution-plan.md](web-remaining-execution-plan.md).
- **Rodada Web de 2026-09-20 (M0-M3, R1, R3)**: M2 e as correções do M3 validados em runtime; R1 (ABI de
  constraints Python) integrado e verificado (nativo e Web); R3 (aborts de áudio sem exceções) integrado, mas com
  segfault reproduzido em arquivo inválido encadeado com efeito (`Sound.file(x).volume()`), tarefa T3 do Codex (a branch `codex/r3-audio-fix-new` ainda nao checa o leitor nulo). Diagnosticos de shader agora trazem o nome real do material e cobrem falha de link (falta material de nos). Sonda `frame-time-perf.js` (`?perf=1`) integrada mas ainda nao ligada ao `index.html`. M4 recomendado adiar até
  medir p50/p95 em celular físico. Divisão vigente e pendências em
  [web-remaining-execution-plan.md](web-remaining-execution-plan.md).
- **Áudio 3D/efeitos OpenAL**: só se algum jogo precisar; `Sound.data()`/`buffer()` do `aud` indisponíveis por
  falta de numpy.
- **Filtros 2D**: refinamento visual e custo de múltiplos passes ficam para etapa posterior; tratar como
  opcionais na Internet.
- **`USE_RNA_RANGE_CHECK` no Emscripten (resolvido no M2)**: checagem reativada. Os cinco campos DNA
  (`fie_ima`, `seed1`/`seed2`, `skgen_subdivision_number`, `handle_vertex_size`) viraram `unsigned char`, com SDNA
  idêntico. Evidência em `docs/changelog.md` (2026-09-20). O MSVC nativo não executa essa checagem.

### Idioma (English, Português, Español, Русский)

Editor compilado com i18n e painel Web traduzido no Windows (ver changelog de 2026-09-20). Pendente:

- Conferir na janela real do Windows: Preferências > System > **International Fonts**, escolher **Language** e ligar
  **Interface**; ver fonte, acentos e o menu (Default, English, Português, Español, Русский; cirílico depende da fonte Roboto). Decidir se o padrão de fábrica deve vir
  com a tradução ligada (hoje segue o 2.79: desligada).
- Auditoria: `RangeEngine -b --python tools/tests/web_profile/i18n_audit.py -- <idioma> [saida.txt]` lista textos sem
  tradução. Restam lacunas do catálogo do Blender 2.79 (pt_BR ~455, es ~511, ru ~1 124) e os textos de `layout.label(text=...)`
  em Python/C fora do RNA (scan estático ainda por fazer). O russo (e o es) de `translations_ui.py` precisa de revisão nativa.
- Traduzir as mensagens das regras Web (`rules_files.py`, `rules_python.py`, `runtime.py`, `manifest.py`, `collect.py`,
  `preflight.py`), ainda em português, e os demais textos em português da Range fora do painel Web.
- Linux: recompilar o preset `linux-editor` (agora com `WITH_INTERNATIONAL=ON`, exige `libboost-locale`, já em
  `libboost-all-dev`), rodar `engine_i18n.py` e conferir o seletor na janela; confirmar que o pacote leva `locale/*/LC_MESSAGES/blender.mo`.
- Roteiros manuais citam os botões pelo nome em português; em inglês são Validate Web, Export Web, Open in browser.

### Linux x86_64

`RangeRuntime` e `RangeEngine` compilam e rodam em Linux nativo; pacote 0.4.0 publicado. Ver
[linux-build.md](linux-build.md). Pendente:

- Validar a janela real do `RangeEngine` numa sessão gráfica (GHOST/X11, ícones, i18n, addons Python); só foi
  testado em `--background`.
- Portar `WITH_OPENCOLORIO` (API 1 → 2.x, dezenas de call sites em `intern/opencolorio`) e `WITH_CODEC_FFMPEG`
  do editor para OpenColorIO 2.x/FFmpeg 5+ (desligados no preset `linux-editor`; só o wrapper `audaspace` do
  FFmpeg foi ajustado).

### Cutscene nativo

Fases 0–2 e 4–5 implementadas; validação manual (Play → Stop → Play e standalone) aceita em 2026-09-20.
Aberto: Fase 3 (ícones PNG próprios, sem substituir os `ZOOMIN`/`ZOOMOUT`). Ver
[plano](cutscene-native-integration-plan.md) e [roteiro](cutscene-native-example.md).

### World Status

Causa raiz achada e corrigida em 2026-09-20 (o World do `startup.blend` não passava por `BKE_world_init`); as oito
propriedades aparecem em `scene.world.properties` num File > New. Painel Global Properties aceito pelo usuário na janela
do editor (2026-09-20). Ver changelog, seção "World Status".

### Vehicle System / Vehicle Lab

Executar o [plano 2](vehicle-system-plan-2.md) por marcos: Fase B (Steering & Brakes, incl. volante visual),
Fase C (Powertrain: drive type, torque/RPM, marchas), Fase A (Chassis: Center of Mass offset). Fase D está
fechada.

### Android / iOS

Sem decisão de implementação. Bloqueios conhecidos: `malloc_stats` ausente na Bionic, `GL/glu.h` ausente no
NDK e backend GHOST/APK inexistente. Ver [mobile-export-plan.md](mobile-export-plan.md).

### Outros

- **Associação de arquivos**: abrir `.blend` e `.range` direto com os executáveis adequados (instalação/registro
  no Windows, duplo clique).
- **Export presets (RangeArmor)**: falta o teste manual (projeto novo e antigo) do [plano](export-presets-plan.md).
  `company_name`, `icon_path` e toggle de plataforma não são gravados (whitelist do RangeArmor Panel); estender
  exige mudança no lado Godot, fora desta fase.
- **Auditoria de `source/blender`**: confirmar ou descartar os candidatos de
  [`relatorio-varredura-bugs-silenciosos.md`](relatorio-varredura-bugs-silenciosos.md), com reprodução,
  correção isolada e teste.
- **Release**: antes da próxima distribuição, declarar se o fork sai como GPLv2-or-later ou GPLv3 e incluir o
  arquivo de licença correspondente na raiz/pacote.

## Performance

- Investigar o custo residual de `MainRender` na cena de benchmark (GPU Skinning já descartado por A/B; nova
  hipótese começa por medição).
- Avaliar folhagem e LOD na cena real; impostor e bake de atlas já existem, o resto pode ser trabalho de asset.
- Vendorizar `Recast/`/`Detour/` a partir de `tools/recastnavigation-main` (a API de integração já usa
  `dtNavMesh`/`dtNavMeshQuery`; falta trazer a lib, com a varredura de bugs silenciosos).
- Navmesh dinâmica: hoje o navmesh é gerado uma vez (`mesh.navmesh_make`). Reagir a objetos móveis exige
  `DetourTileCache` e obstáculos temporários; escopo novo, não iniciado.

## Iluminação e gráficos

- **Resolução dinâmica**: opt-in em `Game Render Properties > Dynamic Resolution`; validada em cena GPU-bound
  (aceite de 2026-09-20).
- **CSM**: blend entre cascatas e debug tint já implementados; falta medir o custo de GPU dessas duas features.
- Avaliar antialiasing temporal somente com caso de uso e critérios de qualidade definidos.
- Aceitos como no-op no core profile (reabrir só com demanda concreta): motion blur legado, clipping de
  espelho/água e texto de debug via `BLF_draw`.

## Validações manuais pendentes

Aceitas pelo usuário em 2026-09-20 e removidas daqui: sombras no jogo real (Planos 1A e 5, múltiplas luzes),
migração de `maxphystep`, Sol/Lens Flare, splash e About, Outliner, barra da 3D View, aba Particles, gamepad no
menu ImGui e Runtime Property Sensors/Actuators. O stress de captura de vídeo e OpenAL foi cancelado por decisão do usuário. Ainda abertos:

- **Sombras**: registrar a origem dos avisos de textura sem nível-base vistos em `-d gpu` (desconhecida).
- **Profiler (Plano 2)**: opcionalmente conferir as categorias `CollisionDepth`/`TextureRenderers` como linhas
  separadas num relatório de benchmark.

## Fora do escopo atual

- Paralelização ampla do loop principal e remoção do GIL de Python.
- Atualização completa do Bullet apenas para obter solver multithread.
- Edição de cena durante o jogo com persistência automática.
- Reimplementação de recursos herdados listados no relatório de melhorias.
