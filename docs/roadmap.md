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
- **Erros de áudio no Web (R3)**: arquivo inexistente/corrompido em `aud` agora vira exceção Python (`-fexceptions` no
  audaspace; não abortam mais). `cache()`, `reverse()`, `pause()`/`stop()` com som válido conferidos em 2026-09-23. Custo em celular
  medido (M3, 2026-09-23): desprezível. Ver changelog de 2026-09-21. Rebuild Web limpo da `linux-sync` reverificado
  (sonda R3 `[r3] TODOS`); a branch `integracao` foi removida por estar contida nela.
- **Extração de erros de shader/Python no pré-voo (M1, encerrado)**: eventos estruturados do runtime
  (`Module.onDiagnostic`, relatório v2) para shader (estágio, material real, compile/link) e Python (tipo, texto,
  traceback, controller/componente/callback), testados no navegador; a heurística sobre o texto fica só como fallback.
  "Importar pré-voo Web" segue para JSON manual. Detalhes em [web-remaining-execution-plan.md](web-remaining-execution-plan.md).
- **Rodada Web de 2026-09-20 (M0-M3, R1, R3)**: M2 e as correções do M3 validados em runtime; R1 (ABI de
  constraints Python) integrado e verificado (nativo e Web); R3 (aborts de áudio sem exceções) **corrigido**
  no runtime Web (`FileManager` devolve leitor silencioso; sonda com 10 casos termina com `[r3] TODOS`;
  `codex/r3-audio-fix-new` superada). Bug de `aud` com `METH_NOARGS` corrigido em `ea2cfd04` (18 métodos) e
  validado no Edge headless em 2026-09-23 (`cache()`, `reverse()`, `handle.pause()/stop()` sem mismatch). Diagnosticos de shader
  trazem o nome real do material e cobrem falha de link (node-material não injetável). `frame-time-perf.js`
  (`?perf=1`, overlay, `perf-run.cjs`) integrado; `package-web.py --perf` inclui a sonda. Build de teste para celular publicado em
  <https://anastaciogames.github.io/AnastacioEngine/?perf=1> (branch `gh-pages`, First Person) em 2026-09-23.
  Regressões de áudio/bloom/resolução dinâmica/R1 repetidas após a mudança de áudio: todas OK (2026-09-23). Medição em celular
  físico (2026-09-23, OPPO Reno14 5G, Dimensity 8350, 12 GB, `?perf=1`): p50 22 ms, p95 55 ms, dpr 3, canvas
  640x480; lentidões periódicas que se recuperam sozinhas. Média aceitável; o M4 deve atacar os picos (p95:
  GC/Python/áudio/compilação de shader), não a resolução. Rodada 0.1.3 (mesmo aparelho, MP3 em loop via `aud`
  + sombra reconfigurada pelo usuário): música toca; p50 33 ms, p95 44 ms. A versão tinha `fps` 60→30 e
  sombra do Sun 2048→512 (clip 90→33,7, frustum 40→13): o p50 é o teto de 30 fps, não custo. A/B a 60 fps com
  a mesma sombra (0.1.4, `/musica/` e `/sem-musica/`): com música p50 22/p95 33 ms, sem música p50 22/p95 44 ms;
  o áudio MP3 não custa desempenho mensurável (diferença do p95 é variação entre rodadas). M3 do áudio fechado. **M4 adiado** (2026-09-23): o jogo medido não usa filtros 2D e os picos do p95 são
  esporádicos, não custo fixo de passe; reabrir só se um jogo com filtros medir mal no celular.
  Desktop (Chrome, `/musica/`, DPR 2): p50 18,1/p95 18,5 ms, sem picos; os picos são do celular. Console: aviso de
  `ScriptProcessorNode` obsoleto (áudio SDL; migrar para AudioWorklet no futuro) e um quadro de 104 ms na carga. Divisão vigente e pendências em
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
  tradução. Restam lacunas do catálogo do Blender 2.79 (pt_BR ~455, es ~511, ru ~1 124). Textos fixos dos layouts Python
  (`layout.label(text=...)` etc.): scan estático em `i18n_scan_labels.py` e traduções em `translations_labels.py`
  (2026-09-24; restam só nomes próprios, códigos e palavras iguais nas duas línguas). Textos em C fora do RNA
  (`IFACE_`/`TIP_`/`N_`): scan em `i18n_scan_c.py` e traduções em `translations_c.py` (2026-09-24; em pt/es restam
  códigos e nomes; no ru, 90 lacunas do catálogo russo do Blender). O russo (e o es) de `translations_ui.py`, `translations_labels.py` e `translations_c.py` precisa de revisão nativa.
- Complemento dos catálogos `.po` ausente do MO instalado: 436 entradas pt_BR e 493 es foram carregadas por
  `translations_catalog.py` (2026-09-24). Na auditoria de fonte, as lacunas passaram de 1 279 para 1 030 (pt_BR) e
  de 1 336 para 1 089 (es); o restante inclui identificadores, ícones e termos técnicos/iguais ao inglês.
- Mensagens das regras Web traduzidas (2026-09-23, `translations_rules.py`; es/ru pedem revisão nativa). Textos em
  português dos operadores da Range (flowmenu: editor externo e assistente de componente; veículo; partículas)
  passaram ao inglês com tradução (2026-09-24, bloco `MESSAGES` de `translations_labels.py`), inclusive o addon opcional
  `addon_editor_shot_tool.py` (a cópia antiga em `tools/ProjetoCutscene` ficou como estava). As mensagens `self.report` do flowmenu e do veículo já passam por `tip_()`.
- Linux: recompilar o preset `linux-editor` (agora com `WITH_INTERNATIONAL=ON`, exige `libboost-locale`, já em
  `libboost-all-dev`), rodar `engine_i18n.py` e conferir o seletor na janela; confirmar que o pacote leva `locale/*/LC_MESSAGES/blender.mo`.
- Roteiros manuais citam os botões pelo nome em português; em inglês são Validate Web, Export Web, Open in browser.

### Linux x86_64

`RangeRuntime` e `RangeEngine` compilam e rodam em Linux nativo; pacote 0.4.0 publicado. Ver
[linux-build.md](linux-build.md). Pendente:

- **Pacote 0.4.0 quebrado no Linux** (`libpython3.11.so.1.0` nao encontrado; tooltip crasha o editor) —
  **ambos corrigidos e validados em Linux nativo 2026-09-21** (RUNPATH `$ORIGIN/lib`, e use-after-free de
  `ARegion` em `wm_tooltip.c` corrigido + testado em sessao grafica real; "Python Tooltips" agora vem marcado
  por padrao para exercitar o caminho de codigo, ver `linux-build.md`/`changelog.md`). A `linux-sync` foi
  testada no Linux pelo usuario em 2026-09-21 ("tudo ok"). **Pacote 0.4.1 publicado e corrigido em
  2026-09-22**: release anterior só continha `RangeEngine` (bug em `tools/linux/package-runtime.sh`, faltava
  `RangeRuntime`); script corrigido, os dois presets recompilados/reempacotados juntos e o asset do GitHub
  Release `v0.4.1` atualizado via `gh release upload --clobber`. Testado localmente com sessão gráfica real:
  `RangeEngine` abre sem erros e `RangeRuntime` carrega um `.range` de exemplo, detecta GPU/OpenGL (Mesa Intel
  RPL-P, OpenGL 4.6) e renderiza sem erros. Teste feito na própria máquina de build; portabilidade em máquina
  limpa ainda não verificada diretamente (apenas por RPATH `$ORIGIN` + `ldd` sem dependências faltando).
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
do editor (2026-09-20). Nomes passados para inglês em 2026-09-25 (`horario_sol` virou `sun_hour`); falta o usuário
conferir o File > New na janela do editor. Ver changelog, seções "World Status".

### Animation Events

Revisados em 2026-09-25 (crashes, threads, sensor, painel; ver changelog). Testes headless do editor e do runtime
passaram. Falta o usuário validar o painel na janela do editor e um jogo real com Animation Events (callback Python
e sensor Animation Event).

### Vehicle System / Vehicle Lab

[Plano 2](vehicle-system-plan-2.md): Fases B (direção em graus, direção sensível à velocidade, freio de mão,
volante visual), C (`has_drive`, torque/RPM, gearbox automático/manual) e A (`vehicle_com_offset` via compound
shape) já estão no código desde o snapshot 28775369. Falta validar cada uma no jogo real (usuário). Fase D
está fechada. O componente do demo `Vehicle` foi sincronizado com a versão com gearbox em 2026-09-24.

### Android / iOS

Android v1 concluído (2026-09-24): APK/AAB com WebView embutindo o pacote Web, validado em aparelho físico
(carga, desempenho, toque, save, ciclo de vida) e exportado pelo editor. Publicação na Play Console adiada
para o futuro por decisão do usuário. Marcos A0–A5 e critérios em [android-export-plan.md](android-export-plan.md). NDK congelado, reaberto somente
por limitação medida; bloqueios em [mobile-export-plan.md](mobile-export-plan.md). iOS fora do escopo.

- **Sensores (`bge.logic.motion`)**: antecipados por decisão do usuário (2026-09-23) e implementados no runtime Web;
  verificados com sensores emulados (`tools/web/verify-motion.cjs`) e aprovados no aparelho real dentro do APK
  (inclinação e `calibrate()`). `orientation`, taxa (~30 Hz) e latência (1–2 frames) conferidas no APK e no Chrome
  do mesmo aparelho em 2026-09-24.
- **APK WebView mínimo (A0b)**: template em `tools/android/webview-template/` rodando a cena `motion` no
  OPPO Find X3 Pro (2026-09-23): carga offline, WebGL 2, Python e sensores ok
  ([android-manual-tests.md](android-manual-tests.md)). Em 2026-09-24: botão "Tela cheia" escondido, Home/retorno e
  giro de 180° confirmados no aparelho; rotação em paisagem e retrato aprovada (proporção e câmera estáveis ao girar). First Person roda no APK
  (pointer lock do WebView neutralizado; ~60 fps parado, medidas variando). Controle por toque, música e save (IDBFS após fechar o
  app) aprovados. Comparação com o Chrome do aparelho medida (`tools/android/measure-device.py`, 3 rodadas por caso):
  APK 52–56 fps contra 36–45 no Chrome, sem frame acima de 34 ms. Sessão longa (10 min, cena padrão com filtros,
  Galaxy Tab S6 Lite) sem queda de fps nem vazamento (2026-09-24). Frames perdidos a 60 Hz no Find X3 Pro: custo de CPU
  do runtime (~20 ms por frame), não do WebView.
- **Export Android (A3/A4)**: módulo `range_web/android.py`, painel "Android (Range)" no editor e
  `tools/web/package-android.py` geram o APK debug a partir do pacote Web (2026-09-24, verificado no build e no editor
  em modo background). Aceito em 2026-09-24: APK do First Person gerado pelo painel e instalado no Find X3 Pro com
  "Instalar no celular". Release assinado implementado (chave fora do JSON e do git, verificado pelo `apksigner`).
  Release instalado e atualizado por cima no aparelho (v1→v2, mesma chave). Save preservado na atualização (cena `web-save`).
- AAB (2026-09-24): opção no release do painel e `package-android.py --aab`; AAB instalado pelo `bundletool`
  no Find X3 Pro e jogo rodando. Publicar numa faixa de teste da Play Console (conta do usuário) fica para o futuro.
- Controles por toque (A1): caminho em
  [android-touch-controls-plan.md](android-touch-controls-plan.md); T0 (ponte `Module.rangePad` → gamepad 0)
  verificada no navegador; T1 (overlay na página: stick, d-pad e botões, multitoque) verificada no navegador
  com toque emulado; T2 (alvo tecla: layouts `wasd` e `arrows`, origem separada do teclado físico) verificada
  no navegador e aceita pelo usuário no Edge do PC; T3 (layout no painel Web, herdado pelo Android; aviso
  WEB-INPUT-001; mapas `KeyMapping/*.json` do Input System passam a ir no pacote) verificada; T4 com a
  checklist conferida no navegador (`verify-touch.cjs` 25/25) e aprovada no Find X3 Pro (cena `pad`, layouts
  stick e `wasd`) e no First Person com o layout `wasd` (2026-09-24). A1 concluído. Extensão T5 (2026-09-24): layout
  `fps` (segundo stick move o mouse para olhar; botões espaço e clique) e áudio suspenso em segundo plano,
  verificados no navegador e aprovados pelo usuário no Find X3 Pro (APK 0.1.7 do First Person).

### Outros

- **Associação de arquivos**: abrir `.blend` e `.range` direto com os executáveis adequados (instalação/registro
  no Windows, duplo clique).
  Registro/remoção (`-r`/`-u`) e comandos do Registro validados em 2026-09-24; falta somente validar o duplo clique no Explorer.
- **Export presets (RangeArmor)**: falta o teste manual (projeto novo e antigo) do [plano](export-presets-plan.md).
  `company_name`, `icon_path` e toggles desktop já são gravados por `wm.py`, com extensão do schema
  registrada no plano; a pendência é de validação manual, não de implementação desses campos.
- **Auditoria de `source/blender`**: confirmar ou descartar os candidatos de
  [`relatorio-varredura-bugs-silenciosos.md`](relatorio-varredura-bugs-silenciosos.md), com reprodução,
  correção isolada e teste.
  Reauditoria concluída em 2026-09-24: os 26 itens têm correção ou descarte registrado; a única validação
  ainda manual é GPU-001, que requer uma sessão interativa já aberta para testar `gl_load()`.
- **Build sem rastreio de headers**: o Ninja do `build/` não registra dependências de `.h` (prefixo do MSVC em
  português, ver `AGENTS.md`). Reconfigurar com `VSLANG=1033` e fazer um clean rebuild completo.
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

- **Compatibilidade UPBGE 0.2.5b adiada:** ao abrir um `.blend` dessa versão, migrar somente quando
  `upbgeversionfile != 0` e o arquivo ainda não tiver versão Range. Há duas conversões verificadas que não
  devem ser misturadas à correção dos Mouse Logic Bricks: (1) em `World.skytype`, mover `Sky Texture` do bit
  `1 << 3` para `WO_SKYTEX` (`1 << 5`) e `Zenith Up` do bit `1 << 4` para `WO_ZENUP` (`1 << 6`); (2) em
  `Lamp.shadow_filter`, converter PCF `1 → 3`, PCF Bail `2 → 4` e PCF Jitter `3 → 5`, pois Range inseriu
  Clipping e Dithering antes desses filtros. Comparação feita contra `tools/arquivo_upbge.blend` na UPBGE
  oficial 0.2.5b e o source `tools/upbge-0.2.5b-source/`.
- **Sombra em materiais Principled/PBR no `BLENDER_GAME` — funcionando** (validado em 2026-09-23 no
  `projects-teste/pbr-baseline/shadow_ibl_test.range`): shadow map simples (sem CSM/VSM) nos 3 primeiros slots
  de luz, com Point/Spot corretos (direção, atenuação, cone) e loop de até 8 luzes. Ver changelog de 2026-09-23.
  Pendente, opcional: comparar lado a lado com material legado sob as mesmas luzes (o chão satura com energia
  somada 5,6 e a sombra fica fraca) e ver o efeito de `ProcessLighting(true)` agora rodar para todo material com
  nodes em uma cena maior. `node_bsdf_diffuse`/`node_bsdf_glossy` ainda tratam toda luz como direcional e sem
  sombra.
- **Principled/PBR no Web**: luzes de cena e sombra portadas para o perfil CORE (`unflightsource[]`, changelog de
  2026-09-23); aceite visual do usuário no navegador com GPU real em 2026-09-23 (brilhos das luzes e sombras
  das esferas corretos). Falta só reconferir o desktop.
- Lembrete de limitação de engine (não é bug, é arquitetura herdada): Point/Local lights nunca geram shadow
  buffer GLSL aqui (`gpu_material.c:3997` só cobre `LA_SPOT`/`LA_SUN`); só Sun (`RAY_SHADOW`) e Spot
  (`BUFFER_SHADOW`) projetam sombra.
- **Light probes** (reflection probes/irradiance volumes): não existem; o IBL atual (`059766dc`) é global, um
  único céu/HDRI pra cena toda, sem componente local por objeto. Avaliar só depois de resolver a sombra do
  Principled acima.
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

- **Drop de OBJ na Vista 3D**: confirmar na janela real que arrastar um `.obj` importa o modelo sem diálogo;
  o operador e o importador passaram em execução automatizada, mas o gesto de arrastar ainda não foi testado.
- **Sombras**: registrar a origem dos avisos de textura sem nível-base vistos em `-d gpu` (desconhecida).
- **Game Settings, FXAA e LOD (2026-09-25)**: conferir no jogo real os painéis novos das abas Render e Scene,
  os ajustes de FXAA e o LOD com Billboard/Invisible.
- **Foliage no Web (2026-09-25)**: conferir num build Web que um material com Foliage Shader compila
  (troca `grass == 1` → `grass > 0.5` no vertex shader) e que o vento anima. No desktop foi aceito pelo usuário.
- **Profiler (Plano 2)**: opcionalmente conferir as categorias `CollisionDepth`/`TextureRenderers` como linhas
  separadas num relatório de benchmark.

## Fora do escopo atual

- Paralelização ampla do loop principal e remoção do GIL de Python.
- Atualização completa do Bullet apenas para obter solver multithread.
- Edição de cena durante o jogo com persistência automática.
- Reimplementação de recursos herdados listados no relatório de melhorias.
