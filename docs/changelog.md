# Changelog — AnastacioEngine

Registro histórico do que foi feito, alterado ou adicionado no fork. Entradas antigas preservam o contexto
da época e podem conter hipóteses corrigidas em entradas posteriores. Para o estado vigente, consulte
`docs/roadmap.md` e `relatorio-melhorias-anastacioengine.md`.

**Como está organizado.** Este arquivo guarda as entradas mais recentes (novas entradas vão no topo, como sempre). O histórico mais antigo está em `docs/changelog/`, dividido em arquivos de até ~70 KB para caber na leitura de uma IA. Quando este arquivo passar de ~60 KB, mova as entradas mais antigas para um novo arquivo em `docs/changelog/` e acrescente uma linha na tabela abaixo.

Para achar uma entrada por assunto: `grep -rn "^## .*termo" docs/changelog.md docs/changelog/`.
Entradas antigas não estão em ordem cronológica estrita; a data no título é a referência.

## 2026-09-28 - Navmesh dinâmica: build em tiles opt-in (passos 2-3)

- Property de jogo booleana `dynamic_navmesh` no objeto navmesh: `KX_NavMeshObject::BuildNavMeshTiled()`
  reconstrói a navmesh em tiles (48 células) com `DetourTileCache`, a partir dos triângulos do próprio navmesh e
  de `gm.recastData`. Sem erosão, filtro de inclinação nem de bordas: a superfície já foi gerada erodida.
- Sem a property, o caminho estático é o mesmo de antes; sem DNA nova. Property não booleana ou falha no build
  dinâmico: aviso no console e fallback para o estático.
- Painel Physics (NAVMESH): aviso se `dynamic_navmesh` não é booleana, se o mesh está vazio, e nota de que os
  caminhos podem diferir levemente do estático.
- Teste (plano 20x20 + caixa): estático, dinâmico e property INT; caminhos dinâmicos contornam a caixa, com
  comprimento até ~0.6 diferente do estático; property INT cai no estático. Obstáculos em runtime ainda não.

## 2026-09-28 - Recast/Detour: cópia vendorizada já está em dia com o upstream

- Upstream baixado em `tools/recastnavigation-upstream` (commit `9f4ce64`, 2026-02-27; pasta ignorada no git).
- Comparação com `source/extern/recastnavigation`: todos os fontes de `Recast/` e `Detour/` são iguais ao
  upstream, exceto patches locais — `buildMeshAdjacency()` não-static (usado pela `recast-capi`), retorno de
  erro em vez de "Data can be corrupted" ao passar de 0xffff vértices/polígonos, checagens de alocação nula em
  `rcBuildContours`/`dtCreateNavMeshData` e guarda de `m_tiles` nulo em `dtNavMesh`.
- O item do roadmap ("cópia antiga do Blender 2.79") estava errado e saiu. Continua em aberto só a navmesh
  dinâmica, que precisaria vendorizar `DetourTileCache` (disponível no upstream baixado).

## 2026-09-28 - Python: `setTimeScale()` valida o valor

- `bge.logic.setTimeScale()` agora levanta `ValueError` para negativo, NaN e infinito, que corrompiam o
  acumulador de tempo (`KX_KetsjiEngine`). 0 continua aceito como "pausa", para não quebrar scripts; a RNA
  segue com mínimo 0,001 na interface.
- Verificado no `RangeRuntime`: 0 e 2 aceitos; -1, nan e inf rejeitados.

## 2026-09-28 - Build: Ninja volta a rastrear headers (VSLANG=1033)

- Causa: `msvc_deps_prefix` em português (`Observação: incluindo arquivo:`) não batia com a saída do `cl`, e o
  Ninja não registrava nenhuma dependência de `.h`.
- Pacote de idioma inglês instalado no Visual Studio; `build/` reconfigurado com `VSLANG=1033` (prefixo agora
  `Note: including file:`) e rebuild completo de C/C++ via `ninja install` (3078 passos, sem erro; cubins CUDA
  preservados renomeando só o `.ninja_deps`).
- Verificado: `ninja -t deps` lista 228 headers para `KX_ShadowRenderer.cpp.obj`; tocar `KX_GameObject.h`
  gera 96 passos no `ninja -n RangeRuntime`, incluindo esse objeto. `RangeEngine` e `RangeRuntime` (com
  `ValidationProject.range`) abrem.
- Comando de build do `AGENTS.md` e do skill `build-anastacio` agora começa com `set VSLANG=1033&&`.

## 2026-09-27 - Release 0.4.3: pacote Linux

- Linux alcança a 0.4.3: `RangeEngine` e `RangeRuntime` recompilados com o fix do loop de tempo (Fixed Timestep
  fora da interface, `FrameOver()` com v-sync) e o splash novo (reembutido via `datatoc`).
- Pacote `AnastacioEngine-0.4.3-linux-x86_64.tar.xz` (editor + runtime) gerado por `package-runtime.sh`.
  Validado extraindo numa pasta temporária: `RangeEngine -b` com ambiente limpo acha o Python 3.11.9 embutido.
- Testes do pacote extraído (Intel RPL-P, Mesa 25.2, monitor 144 Hz, X11), comparando com o pacote 0.4.2. Cena
  com script que mede o intervalo entre frames e conta passos de lógica por frame (`scene.pre_draw`), 8 s,
  640x360:
  - tic 60 e 144, v-sync ligado/desligado: 60,0/144,1 fps e 1,000 passo por frame nos dois, exceto tic 144 com
    v-sync na 0.4.2 (1 frame com 2 passos e pico de 13,8 ms); na 0.4.3, 0 frames irregulares, pico de 7,3 ms.
  - tic 60 com picos de 30 ms a cada 20 frames: sem v-sync os dois dão 60 fps; com v-sync a 0.4.3 dá 57,6 fps
    (não recupera o atraso, efeito esperado do fix) e a 0.4.2, 60 fps.
  - Sem erros nos logs. Uma cena demo (`Chuva com nuvens.range`) roda sem erro. O `RangeRuntime` ignora
    SIGTERM (só sai com SIGKILL), igual na 0.4.2: não é regressão.
  - Editor com janela: splash novo aparece (a imagem nova está no binário, a antiga não).
- Splash fora do centro no Linux: ele é criado com o tamanho de janela salvo no startup (2494x1371 aqui) e o
  gerenciador de janelas redimensiona depois (1854x1131). O listener de resize dos popups centralizados
  marcava a região, mas o refresh não rodava porque `can_refresh` ficava `false`. Corrigido em
  `ui_popup_block_create` (`interface_region_popup.c`): popups `UI_BLOCK_BOUNDS_POPUP_CENTER` agora podem ser
  reconstruídos. Conferido com printf temporário: o splash é recentralizado para 1854x1131. O zip Windows
  0.4.3 não foi recompilado com este fix.
- Pendente: o texto de versão do splash está fixo em "AnastacioEngine 0.4.0 Release Candidate"
  (`get_version_string_splash_screen`), em todas as plataformas.

## 2026-09-27 - Loop de tempo: teste automático e zip 0.4.3 atualizado

- Teste automático no `RangeRuntime`: cena simples com um script que mede o intervalo entre frames e conta
  passos de lógica por frame desenhado (`scene.pre_draw`), 8 s por caso, janela 640x360, monitor de 165 Hz (AMD
  RX 6800M). Comparado com o zip anterior da 0.4.3 (antes do fix):
  - tic rate 60, com e sem limite de FPS, flag antiga ligada e desligada, v-sync ligado e desligado: os dois dão
    60,0 fps, 1 passo por frame e nenhum engasgo. O motor sempre marca o ritmo pelo tic rate (sleep), então
    60 Hz num monitor de 165 Hz não mostra o bug do v-sync.
  - tic rate 165 (igual ao monitor) com a flag antiga ligada: o antigo teve 1 a 3 frames de 12 ms sem passo de
    lógica (0,998 passo/frame); o novo teve 0 engasgos e 1,000 passo/frame.
  - tic rate 60 com picos de 30 ms a cada 20 frames: sem v-sync os dois ficam iguais (60 fps, recuperam o
    atraso). Com v-sync o novo não recupera mais (57,7 fps médios, cada pico perde ~13 ms), que é o efeito
    esperado do fix do Kitsuy; o antigo recuperava, mas teve um travão de 111 ms num dos casos.
  - Logs sem erro em todos os casos.
- Zip `AnastacioEngine-0.4.3-windows-x64.zip` refeito a partir do anterior trocando só `RangeEngine.exe`,
  `RangeRuntime.exe` e `2.79/scripts/startup/bl_ui/properties_game.py` (os mesmos 4.657 arquivos, mesmo
  `blender.crt.manifest` da 0.4.2 e mesmos cubins). Validado extraindo em `D:\t043`: `RangeEngine -b` sai com 0,
  Cycles lista CPU e OpenCL, `RangeRuntime` roda os casos acima. Tag `v0.4.3` movida para este commit.
- Falta o teste no jogo real (roadmap).

## 2026-09-26 - Loop de tempo: Fixed Timestep desligado e fix de v-sync (revisão do Kitsuy)

- **Fixed Timestep (Plano 8) desligado.** No modo fixo o `NextFrame()` rodava `m_simulationPipeline->Update()`
  até `m_maxLogicFrame` vezes por frame, mas a física de taxa fixa só aguenta 1 passo (causa provável do crash
  nesse modo). A investigação achou mais problemas no mesmo modo: o sleep antigo continuava ditando o ritmo, então
  os passos alternavam entre 0 e 2 (engasgo); num frame com 0 passos o `ClearInputs()` apagava a tecla; nos passos
  extras `m_logicTime`/`m_frameTime`/`m_animationsTime` não avançavam (só `FrameTiming()` avança, 1x por frame)
  enquanto a física andava 2x; o `JUSTACTIVATED` disparava duas vezes. Mudança: o checkbox saiu de
  `properties_game.py`, `LA_Launcher.cpp` passa sempre `SetUseFixedTimestep(false)` e a descrição RNA virou
  "Deprecated". O bit `GAME_USE_FIXED_TIMESTEP` fica no DNA: arquivos antigos abrem iguais e rodam no modo normal.
  O código do acumulador fica inerte; só o comentário do `.h` mudou (sem mudança de layout).
- **V-sync em `FrameOver()`.** Com v-sync, o tempo em que `SwapBuffers()` fica bloqueado entrava em `m_deltatime`
  e acumulava em `m_overframetime` como se fosse atraso. Agora, com `GetSwapControl() != VSYNC_OFF`,
  `m_overframetime` é zerado. Sem v-sync a lógica antiga fica igual, inclusive o `m_deltaTime` do ramo negativo,
  que aguarda resposta do Kitsuy (roadmap).
- **Comentário errado corrigido** em `KX_RenderPipeline.cpp` (e anotado na entrada antiga do changelog):
  `m_frameTime` não passa pelo acumulador, então chuva/nuvens/flare não ficam mais lentos com o Time Scale.
- `KX_SimulationPipeline.cpp` não mudou. Todo o código é compartilhado; vale para Windows, Linux e Web.
- Build incremental de `RangeEngine` e `RangeRuntime` sem erro. Falta o teste no jogo real (roadmap).

## 2026-09-26 - Release 0.4.3: pacote Windows (splash novo)

- So Windows; o Linux segue na 0.4.2. Muda o splash (embutido no `RangeEngine.exe` via `datatoc`) e os addons
  `ant_landscape`/`io_export_after_effects` (`is <numero>` -> `==`).
- Montado na maquina AMD, sem CUDA Toolkit: `build/bin` daqui nao tem cubins. Os 8 cubins
  (`kernel_`/`filter_sm_75/86/89/120`) vieram do zip 0.4.2, com o codigo dos kernels sem mudanca desde entao.
  A lista de arquivos do zip 0.4.2 serviu de referencia: 4.657 arquivos, os mesmos.
- **`blender.crt.manifest` desta maquina estava errado:** o CMake o regenerou em 12/09 com hashes de DLLs
  `api-ms-win-*` de outro SDK, mas as DLLs da `build/bin/blender.crt/` sao de abril (40 de 49 hashes nao
  batiam, e faltavam 5 DLLs no manifesto). O pacote usa o manifesto da 0.4.2, cujos 54 hashes batem com as
  DLLs. Conferir isso antes de empacotar em qualquer maquina.
- Validado extraindo o zip: `RangeEngine -b` sai com 0, Cycles lista CPU e OpenCL (RX 6800M), `RangeRuntime`
  roda um `.range`. A extracao falhou num caminho muito longo (pasta temporaria funda, arquivo `.cl` do Cycles
  com nome grande); em caminho curto extrai tudo. A nota do release recomenda caminho curto.

## 2026-09-26 - Docs: checagem automatica e guia para contribuir

- `tools/check_docs.py`: confere links locais, referencias `arquivo:linha` (arquivo existe e tem a linha) e os
  mapas de codigo (metodo ainda perto da linha citada, tamanho do arquivo). Sai com 1 em erro; `--fix` grava
  linhas, tamanhos e o `HEAD` conferido nos mapas. Na primeira rodada achou 1 link quebrado
  (`ketsji-engine-modernization-plan.md` apontava para um relatorio externo nunca versionado) e 5 tamanhos
  com 1 linha a mais (o script antigo contava a linha vazia final).
- `CONTRIBUTING.md` e `.github/ISSUE_TEMPLATE/bug_report.yml`: o modelo de bug pede versao, sistema, placa de
  video/driver e dispositivo do Cycles.

## 2026-09-26 - Docs: arquitetura atualizada para o estado atual

- `architecture.md`: mapa do repositório, loop Web (`emscripten_set_main_loop_arg`), caminho editor → `.blend`
  → conversor, export Web/Android em `range_web`, Cycles, `m_debugRenderer` e linha do `main()` corrigida.
- `code-map-*.md`: números de linha e tamanhos reconferidos com o código; índices `local-knowledge/index-*.md`
  regerados. Resumos de IA local marcados como não revisados (tinham "UPBGE = Unreal ...").
- `maintenance-guide.md`: stubs do player, GLSL ES da Web e traduções de texto novo. `docs/README.md` com
  ordem de leitura e sem o link para o inexistente `vehicle-test-guide.md`.

## 2026-09-27 - Release 0.4.2: pacote Windows

- `AnastacioEngine-0.4.2-windows-x64.zip` (159 MB) e `.sha256` anexados a `v0.4.2`, que ate entao so tinha o
  pacote Linux. Feito na maquina NVIDIA (CUDA 13.4): cubins sm_75/86/89/120 dentro de
  `2.79/scripts/addons/cycles/lib/`; Embree e OpenCL ligados.
- Montado conforme `distribution-0.1.md`: `blender.crt/` + so `ucrtbase.dll` solto, sem `.pdb`/`.lib`/`.map`
  de build, `datatoc`/`makes*`, logs, `demos/`, `rangearmor/` e `imgui.ini`. RangeArmor sem versao nova.
- Copia extraida numa pasta limpa: render Cycles em `-b` com CUDA (RTX 5060 Laptop) OK; `RangeRuntime.exe`
  abre um `.blend` de jogo e roda sem crash.
- Pegadinha: com o notebook fora da tomada a RTX 5060 some (Cycles lista so a CPU e `nvidia-smi` falha com
  "insufficient permissions"). Ligar a fonte antes de testar CUDA.

## 2026-09-26 - Windows: Cycles OpenCL testado na AMD

- Maquina AMD (RX 6800M + Radeon integrada do Ryzen 9 5900HX), preset `v142-ninja` sem CUDA Toolkit: o
  configure desliga os cubins sozinho e o CUDA fica so por dynload.
- O RX 6800M aparece duas vezes na lista (mesmo PCI `03:00.0`, a segunda com `_ID_2`): cada GPU tem seu
  driver AMD (32.0.21045 e 31.0.21923), cada um registra um `amdocl64.dll` e os dois enxergam o 6800M.
  Marcar so uma entrada.
- Usuario confirmou render com GPU (OpenCL) pela interface.
- Render em `-b` (cena padrao, 128 amostras, 50%): 1a vez 24,5 s (compila ~9 kernels split), depois 7,7 s;
  CPU 1,4 s com os tiles padrao.
- Bake de AO (chao sob cubo) com OpenCL: mesmos valores da CPU (min/max/media); 0,79 s contra 0,26 s depois
  de compilar o kernel `bake` (28 s na 1a vez). O bake imprime `Split kernel error: failed to load
  kernel_path_init`, sem efeito no resultado.

## 2026-09-26 - Cycles: cubins CUDA para RTX 20/30/40/50

- Preset `v142-ninja`: `CYCLES_CUDA_BINARIES_ARCH=sm_75;sm_86;sm_89;sm_120` (sm_75 e o minimo do CUDA 13).
  Cada arch leva ~12 min e ~9 MB (sm_120 ~28 MB). So sm_120 testado em hardware real (RTX 5060).
- Removidos de `build/bin/.../cycles/lib` cubins antigos de 2023 (sm_30 a sm_70), sobras de outro build.

## 2026-09-26 - Windows: Cycles com CUDA no build principal

- Preset `v142-ninja` liga Cycles com Embree, CUDA (binarios `sm_120`) e OpenCL no `build/`.
- CUDA 13.0 nao aceita o MSVC 14.51 do VS 18; instalado o CUDA 13.4 em `D:` (o instalador so deixa escolher
  a unidade sem versao anterior instalada). Cache reapontado com `cmake -U "CUDA_*" -DCUDA_TOOLKIT_ROOT_DIR=...`.
- O nvcc 13 usa C++20 por padrao e a STL do MSVC 14.5x da static_assert (`aligned_storage`, `result_of`);
  `-std=c++17` adicionado aos flags do kernel.
- `kernel_sm_120.cubin` nao e dependencia do `RangeEngine`: compilar `cycles_kernel_cuda` antes.
- Teste: `RangeEngine -b` renderiza a cena padrao na RTX 5060 com os kernels pre-compilados (512 amostras,
  7,1 s).
- Usuario confirmou render com GPU (CUDA) pela interface do editor.
- Bake de AO (chao sob cubo) com CUDA: mesmos valores da CPU (min/max/media), 0,86 s contra 1,80 s.
- Addons `ant_landscape` e `io_export_after_effects`: `is <numero>` trocado por `==` (SyntaxWarning no Python 3.11).

## 2026-09-26 - Linux: pacote testado em maquina limpa

- Teste num container Ubuntu 24.04 minimo (`ubuntu-base` + `unshare`, sem Docker nem sudo); roteiro em
  `docs/linux-build.md`.
- Defeito: `package-runtime.sh` punha a stdlib em `python311/lib`, mas o executavel procura em
  `<versao>/python`. Sem `/opt/anastacio-python311` o Python falhava com `No module named 'encodings'`,
  e isso afeta o 0.4.1 publicado. O script agora copia para `2.79/python`, garante o libpython em `lib/`,
  confere a stdlib e tira `datatoc`, `makesdna`, `makesrna`, `msgfmt` e `imgui.ini` do pacote.
- Depois da correcao: `RangeEngine -b` renderiza a cena de teste com Cycles e o `RangeRuntime` acha o
  Python embutido. As bibliotecas do sistema continuam fora do pacote; a lista de pacotes de runtime esta
  em `linux-build.md`.

## 2026-09-26 - Linux: i18n validado no editor

- `build-linux-editor/` com `WITH_INTERNATIONAL=ON`: `engine_i18n.py` 36 ok (pt_BR, es, ru_RU; catalogo do
  Blender e dicionarios da Range). Os `blender.mo` saem em `bin/2.79/datafiles/locale/`, e o
  `package-runtime.sh` copia o `bin` inteiro. Pela janela, o usuario trocou o idioma para pt_BR e conferiu
  menus e acentos.
- Roadmap: removido o item "validar a janela real do `RangeEngine`"; o editor ja vinha sendo usado com janela
  no Linux (Cycles, Standalone, preferencias).

## 2026-09-26 - Cycles: Embree 4 e OpenCL no editor Linux

- Embree: o Ubuntu 24.04 so tem o Embree 4, e o Cycles era escrito para o 3. `FindEmbree.cmake` acha
  `embree4/rtcore.h` e a `libembree4` compartilhada; `intern/cycles/CMakeLists.txt` define `WITH_EMBREE4`
  (sem `EMBREE_STATIC_LIB`). No codigo, headers `embree4/`, `RTCRayQueryContext` no lugar de
  `RTCIntersectContext`, e `kernel_embree_intersect1`/`kernel_embree_occluded1` (`kernel/bvh/bvh_embree.h`)
  passam o contexto por `RTCIntersectArguments`/`RTCOccludedArguments`. O Embree 3 do Windows segue igual.
- `bvh_embree.cpp`: o bloco `RTC_VERSION >= 30900` (flags de vizinho das curvas lineares) usava uma variavel
  inexistente e tratava todo o cabelo como uma curva so; nunca tinha compilado. Reescrito com um flag por
  segmento, curva a curva.
- OpenCL: `cycles_device` nao linkava o `extern_clew`, e o `RangeRuntime` falhava com `clewInit` indefinido;
  agora linka quando `WITH_CYCLES_DEVICE_OPENCL`. Este Cycles so aceita OpenCL em GPUs AMD
  (`OpenCLInfo::device_supported`), entao a RTX 5060 nao aparece em OpenCL; nao foi testado em AMD.
- Preset `linux-editor`: `WITH_CYCLES_EMBREE=ON` e `WITH_CYCLES_DEVICE_OPENCL=ON`; `quickstart-editor.sh`
  instala `libembree-dev`. OSL continua desligado: sem pacote no Ubuntu 24.04 e esta versao espera OSL 1.9.
- Teste: cubo com 300 fios de cabelo e uma copia linkada, CPU, 32 amostras, Embree ligado e desligado: as
  duas imagens batem (diferenca media 0,03/255, so ruido de amostragem). Depois de instalar o `libembree-dev`
  do sistema, o usuario testou pela interface: Embree (Render > Performance > Use Embree) e CUDA (primeiro
  render recompilou o kernel sm_120) funcionando.

## 2026-09-26 - Cycles: CUDA na RTX 5060 (sm_120) com CUDA 13

- `kernel_config.h`: o kernel CUDA so conhecia arquiteturas ate 7.x e parava com "Unknown or unsupported CUDA
  architecture". Nova faixa 8.x a 12.x (Ampere a Blackwell) com os limites do 7.x e 16 blocos por SM.
- `util_math.h`: o CUDA 13 removeu o `saturate()` que o nvcc trazia pronto; agora e definido com `__saturatef`
  quando `__CUDACC_VER_MAJOR__ >= 13` (CUDA mais antigo segue usando o dele).
- Preset `linux-editor`: `WITH_CYCLES_DEVICE_CUDA=ON` e `WITH_CUDA_DYNLOAD=ON`. Sem dynload o CMake do player
  quebrava (`target_link_libraries(${target} ...)` com variavel indefinida; corrigido para `RangeRuntime`).
- Teste: render `-b` na GPU com CUDA 13.0: primeira compilacao do kernel ~4 min, depois o render sai em < 1 s
  e a imagem confere. As duas correcoes do kernel valem tambem para o Windows com CUDA 13 e placas 8.x+.

## 2026-09-26 - Cycles: um editor Linux so, com Cycles

O preset `linux-editor` passa a ter `WITH_CYCLES=ON` (so CPU; OSL, Embree, CUDA e OpenCL desligados) e a sandbox `build-linux-cycles/` deixa de existir. O menu de engine nao listava "Cycles Render": ele depende do add-on `cycles`, que o build sem Cycles remove das preferencias (`resources.c`), e nada o religava. Agora um build com Cycles faz `BKE_addon_ensure(&U.addons, "cycles")` no mesmo ponto. O `build-linux-editor/` antigo guardava no cache a deteccao do OpenEXR 2.0 e falhava em `ImathBox.h`; apagar as entradas `OPENEXR_*`/`IMATH_*` do cache resolveu. Teste: build ok; em `-b` com as preferencias do usuario o add-on carrega e `scene.cycles` existe; `cycles-smoke-render.py` a 64 amostras renderiza certo. Pela interface, o usuario renderizou com F12 e com a viewport em Rendered.

No mesmo preset, `WITH_PLAYER=ON`: o botao Standalone do editor Linux dava "Player path ... RangeRuntime not found", porque o runtime so saia no `build-linux/`. Ligar o player no build do editor quebrava o link com dezenas de simbolos (`CLG_*`, `build_*`, `BKE_autotrack_*`, `LA_BlenderLauncher`...): as libs do editor entravam como dependencias transitivas depois do `--end-group`. `blenderplayer/CMakeLists.txt` agora poe `BLENDER_LINK_LIBS` dentro do grupo no Linux, e o stub `builtin_keyingsets` em `stubs.c` ganhou o mesmo `#ifndef WITH_BLENDER` dos outros stubs com versao real. Teste: build ok; `RangeRuntime pbr_variants.blend` abre com OpenGL 4.6 sem erros. `RangeRuntime` sem argumentos da segfault tambem no `build-linux/`, entao o bug ja existia antes (nao investigado).

## 2026-09-26 - Cycles: editor Linux renderiza com Cycles (CPU)

Sandbox `build-linux-cycles/` = preset `linux-editor` com `WITH_CYCLES=ON` (sem OSL, Embree, CUDA e OpenCL). O `RangeEngine` nao linkava: faltavam os simbolos `google::*` (glog/gflags) usados por `util_logging.cpp`, `blender_python.cpp` e outros. `cycles_util` nao declarava essa dependencia; no MSVC a ordem das `.lib` nao importa, mas o `ld` do Linux resolve estaticas na ordem. `intern/cycles/util/CMakeLists.txt` agora poe `${GLOG_LIBRARIES}`/`${GFLAGS_LIBRARIES}` no `LIB` quando `WITH_CYCLES_LOGGING`. Teste: `tools/linux/cycles-smoke-render.py` (esfera, chao, lampada pontual) em modo `-b`; `--debug-cycles` confirma sessao, device CPU com 16 threads e BVH8; 1 amostra sai com ruido e 128 amostras sai limpa com sombra e rebatimento de cor (0,7 s). GTest do Cycles recompilado: 177/177. Falta abrir o editor com janela e renderizar pela interface (F12 e viewport em modo Rendered), e testar CUDA na NVIDIA desta maquina.

## 2026-09-26 - Cycles: testes GTest validados no Linux

`GTestTesting.cmake`: o bloco `UNIX AND NOT APPLE` linkava `bf_intern_libc_compat` em `${TARGET_NAME}` (variavel inexistente), o que quebrava a configuracao de qualquer teste no Linux; agora usa `${NAME}_test`. No Windows o bloco nao roda, por isso passou. Build separado `build-linux-gtest/` com `WITH_CYCLES=ON` e `WITH_GTESTS=ON` (sem OSL/Embree/CUDA/OpenCL); faltavam `libopenexr-dev`, `libpugixml-dev` e `libtiff-dev`, e no OpenEXR 3.1 foi preciso apontar `OPENEXR_HALF_LIBRARY` para `libImath.so` e `OPENEXR_ILMIMF_LIBRARY` para `libOpenEXR.so`. O codigo compilou sem ajustes. Teste: 10 binarios `cycles_*_test`, 177/177 passando (graph_finalize 61, util_path 41, util_string 38, util_ies 13, util_image 8, util_time 5, render_tile 4, render_light_ies 3, util_task 2, util_aligned_malloc 2). Receita em `docs/linux-build.md`. O editor com Cycles esta na entrada acima.

## 2026-09-26 - Themes > Global Theme: UI atualiza numa etapa só

`rna_userdef.c`: marcar "User Interface" em Copy Global Theme To fazia `tui = tglobal_ui`, mas no `tglobal_ui` só o `wcol_regular` tinha a cor global; os outros widgets (`wcol_tool`, `wcol_num`, `wcol_option`...) ficavam com a cópia antiga. O resto só atualizava ao mexer num valor de "All Widget Colors" (Roundness, Shade...), que espalhava o `wcol_regular` por todos os widgets. Os "Widget State Colors" globais nunca propagavam sozinhos. Agora os dois caminhos (e o `wcol_state`) usam `rna_theme_global_ui_apply`, que espalha o `wcol_regular` por todos os widgets do `tglobal_ui` e copia para o `tui`. Teste: build ok; script em modo batch: com a caixa desmarcada, muda cor, Roundness e state color globais; ao marcar, `wcol_num`/`wcol_option` e `wcol_state` já saem iguais ao global, e mudar uma state color depois também propaga. Falta conferir o visual no editor.

## 2026-09-26 - Text Editor: barra lateral em painéis

`space_text.py`: a sidebar (N) virou os painéis View (Line Numbers / Word Wrap / Syntax Highlight como ícones numa linha, Highlight Line), subpainel Margin (fechado, `bl_parent_id`), Editor (Font Size, Tab Width, Tabs as Spaces, Live Edit) e Find & Replace (campos com conta-gotas ao lado, opções numa linha). Nenhuma opção removida. O cabeçalho continua forçando as três opções de View ligadas a cada redesenho (comportamento antigo). Teste: registro dos painéis em modo batch e conferido pelo usuário no editor.

## 2026-09-26 - Outliner: pasta "fora do jogo" (layer 20) e Group a partir da coleção

Primeira ligação das coleções com o jogo, sobre o sistema de layers (não é a reescrita do Blender 2.8, que trocaria layers, Groups e o conversor do BGE).

- **Caixa "In game"** à esquerda do olho em cada pasta (como o exclude do 2.8), também em Collection > Toggle Not in Game (`outliner.collection_game_exclude`). Desmarcada (`SCECOL_GAME_EXCLUDE`), os objetos da pasta, das subpastas e os filhos deles vão para o layer 20 (`SCECOL_GAME_LAYER`) e começam **inativos** no jogo, prontos para o Add Object. O layer anterior fica em `Base.collection_lay` (era `pad`) e volta quando a caixa é marcada de novo ou o objeto sai da pasta.
- **Layer 20 visível no editor:** ao desmarcar, o layer 20 é ligado na cena para os objetos não sumirem. O conversor (`BL_BlenderDataConversion.cpp`) tira o layer 20 dos layers ativos sempre que a cena tem alguma pasta fora do jogo, então o que for posto nele à mão também começa inativo nesse caso.
- **Sincronia:** `BKE_scene_collections_game_sync` roda em toda operação de pasta (mover, arrastar, apagar) e no início do jogo pelo editor (pega objetos que ganharam pai depois).
- **Create Group from Collection** (`outliner.collection_to_group`): cria um Group com o nome da pasta e os objetos mostrados nela, para instância de grupo.
- **Cabeçalho:** o botão de nova coleção passou para o lado do menu Collection.
- **Teste:** build ok. Script no editor: Cube na pasta, desmarca → layer 20 e layer 20 da cena ligado; marca → volta ao layer 1; Group "Collection" com o Cube; salvar e reabrir mantém o layer 20. Conferido pelo usuário no editor.

## 2026-09-25 - Outliner: coleções só para organizar (sem Group, sem mudar parent)

Pastas no modo Current Scene do Outliner, parecidas com as coleções do Blender 2.8, mas **só organizacionais**: não mudam parent, camadas, Groups nem nada no jogo.

- **Dados:** `SceneCollection` (nome, `uid`, subcoleções) em `Scene.collections`. `Base.collection_uid` diz a pasta de cada objeto (0 = raiz). Usa uid e não ponteiro, então cópia de cena, apagar objeto e undo não precisam de remapeamento. Arquivos antigos abrem com tudo na raiz. Funções em `scene.c` (`BKE_scene_collection_*`), leitura/escrita em `readfile.c`/`writefile.c`.
- **Árvore:** elemento `TSE_SCENE_COLLECTION` (id = cena, nr = uid, para o aberto/fechado persistir). Os objetos raiz entram na pasta depois de `outliner_make_hierarchy`, ou seja, **filho sempre aparece sob o pai**, e a coleção só vale para objetos sem pai. Ao mover um objeto, os descendentes recebem a mesma coleção.
- **Botões olho/seleção/render** da pasta aplicam a todos os objetos mostrados dentro (filhos e subcoleções inclusos).
- **Operadores:** `outliner.collection_new` (dentro da pasta selecionada), `collection_delete` (objetos e subpastas sobem para o pai), `collection_objects_select`, `collection_move_objects` (menu; também em "Move to Collection" no menu de contexto do objeto). Arrastar objeto para pasta ou para a área vazia (raiz), arrastar o ícone da pasta para dentro de outra ou para a raiz. Duplo clique renomeia (nome único na cena). Menu **Collection** e botão de nova pasta no cabeçalho do Outliner.
- **Stub:** `WM_menu_name_call` acrescentado a `blenderplayer/bad_level_call_stubs/stubs.c`; sem ele o `RangeRuntime` não linkava.
- **Teste:** build limpo de `RangeEngine` e `RangeRuntime` ok; `tools/arquivo_upbge.blend` abre com o `Base` novo. Falta teste no editor.
- **Também em All Scenes** (modo padrão do `startup.blend`; antes as pastas só existiam em Current Scene e nada aparecia): pastas dentro de cada cena, operadores e arrastar usam a cena da pasta (o drop de pasta leva o nome da cena na propriedade `scene`). Botão de nova coleção no canto direito do cabeçalho, como no Blender 2.8. Teste: build ok; `outliner.collection_new` em All Scenes no `startup.blend` (batch) cria a pasta.

## 2026-09-25 - Compatibilidade UPBGE: logic bricks revisados; corrige estouro na cor do sensor

Comparado `tools/upbge-0.2.5b-source` com a Range (DNA, RNA e `BL_Convert*` de sensores, controladores e atuadores; API Python de `GameLogic`).

- **Corrigido:** `blo_do_versions_range()` copiava 4 bytes (`copy_v4_v4_uchar`) para `bSensor.color[3]`, o último campo da struct (200 bytes): 1 byte escrito fora do bloco em todo sensor de arquivo UPBGE aberto. Agora `copy_v3_v3_char`.
- **Já compatível, sem ação:** fora o Mouse Sensor (migrado em `32f66eef`), a Range só acrescentou valores de enum e flags (2D Filter 14-19, `ACT_OBJECT_NORMAL_SET`, `ACT_EDOB_CHANGE_COLOR`, `ACT_EDOB_ADD_FROM_PROP`/`_PROP_GLOBAL`, `SENS_ANIMATIONEVENT`, `SENS_DELTATIME`/`SENS_SHOW_DESCR`); campos novos lidos como zero mantêm o comportamento antigo (Delay `repeat_times`/`use_delta`, `use_dt`, `debug` de Near/Radar/Ray, runtime do Property Sensor/Actuator, `saveloc`/`extension_name`). Atributos Python de `SCA_PythonKeyboard/Mouse/Joystick` continuam existindo em `Ketsji/KX_Python*`.
- **Teclas:** `wm_event_types.h` do UPBGE 0.2.5b é idêntico ao da Range; Keyboard Sensors antigos não precisam de migração. (`Ketsji` e `windowmanager` do UPBGE v0.2.5b copiados do GitHub para `tools/upbge-0.2.5b-source`, que é ignorado pelo git.)
- **Save/Load globalDict (Game Actuator e `logic.save/loadGlobalDict`):** o UPBGE gravava `jogo.bgeconf`, a Range grava `jogo.save`. `pathGamePythonConfig` agora tira `.blend` como já tirava `.range` (antes: `jogo.blend.save`), e `loadGamePythonConfig` lê `jogo.bgeconf` quando não há `.save` e não há nome/extensão próprios; o próximo save vai para o `.save`. Corrigido também o nome de save próprio (`saveloc`), que cortava o caminho com `sizeof` de ponteiro/array em vez do tamanho do nome do arquivo.
- **Teste:** `RangeEngine -b tools/arquivo_upbge.blend`: 8 Mouse Sensors com tipos corretos (wheel up/down, movement), cor aplicada, sem aviso de memória. `RangeRuntime` com `.blend` + `.bgeconf` (marshal) e `loadGlobalDict()`: `globalDict` carregado.

## 2026-09-25 - startup.blend de fábrica atualizado

- `source/release/datafiles/startup.blend` substituído pelo `startup.blend` salvo por Fabio pela UI (`%APPDATA%\RangeEngine\Blender\2.79\config\startup.blend`). O anterior ficou em `startup.blend1`.
- Screens: Asset Browser, Game Dev, Game Play, Script (antes só Game Dev e Game Play). Texto embutido `03_jogador_celular.py` no lugar de `02_component_properties.py`. Objetos e imagens empacotadas iguais aos de antes.
- **Teste:** `RangeEngine -b --factory-startup` lista as 4 screens e o texto novo. `RangeEngine` e `RangeRuntime` compilam.

## 2026-09-25 - Screens: Ctrl+Seta parava de navegar depois de apagar uma screen

- **Sintoma:** ao apagar uma screen (ex.: "Game Play") e criar outra pelo **+**, Ctrl+→/← deixava de trocar de screen, sem erro.
- **Causa:** as abas de screen (`uiTemplateScreenTabs`) chamam `SCREEN_OT_screen_set` com `screen_name`. Essa propriedade era guardada como "last properties" e os itens de keymap Ctrl+→/← a recarregavam. Com `screen_name` preenchido, o operador vai para a screen com esse nome e ignora `delta`. Enquanto a screen existia, isso parecia navegação normal. Depois de apagada, o nome não achava nada e o operador era cancelado.
- **Correção:** `screen_name` e `delta` agora têm `PROP_SKIP_SAVE` em `screen_ops.c`.
- A remoção da screen estava correta: o `screen delete 0000000000000000` no log `wm.event` aparece só porque a referência do notifier é zerada quando o ID é liberado.
- **Teste:** RangeEngine com `--log "wm.*"`. Depois de apagar a screen, criar outra e clicar numa aba, Ctrl+→ gera `screen_set(delta=1)` e troca de screen (confirmado pelo usuário).

## 2026-09-25 - Asset Browser (modo Assets do File Browser, arrastar para a Vista 3D)

Feito como no Blender: o File Browser ganhou um modo de navegação (`SpaceFile.browse_mode`, DNA novo), sem editor novo.

- **Como abrir:** entrada "Asset Browser" no menu de tipo de editor (subtipo no `EditorTypeItem` de `area.c`, valor `tipo | subtipo << 8`), ou Window > Asset Browser, que abre uma janela flutuante (`SCREEN_OT_asset_browser_show`, tipo `WM_WINDOW_ASSETS` em `WM_window_open_temp`).
- **Modo Assets:** lista o conteúdo dos `.blend` da pasta em vista plana (`FILE_LOADLIB`, recursão 1), só Objects, Groups e Materials, em miniaturas. `ED_fileselect_browse_mode_params_ensure` impõe esses parâmetros a cada refresh, e a lista é recriada quando o tipo dela (`filelist_type_get`) não bate. Um diálogo de arquivo aberto na área (`sfile->op`) sempre ganha do modo Assets.
- **Bibliotecas:** nova categoria do fsmenu, gravada na seção `[AssetLibraries]` do `bookmarks.txt`. Operadores `file.asset_library_add` (pasta atual ou `directory`; dentro de um `.blend` usa a pasta dele) e `file.asset_library_remove`. RNA: `asset_libraries` / `asset_libraries_active`.
- **Arrastar para a Vista 3D:** `VIEW3D_OT_asset_drop` faz append ou link e põe o objeto ou grupo no ponto do drop. Material vai para o objeto sob o cursor (ou o ativo). Duplo clique no asset (`file.asset_add`) adiciona no cursor 3D. O botão Append/Link (`params.use_link`) vale para Groups e Materials; Objects são sempre append. No modo Assets, só itens de asset podem ser arrastados; new folder, rename e delete ficam bloqueados.
- **Previews:** `file.asset_previews_generate` roda o `wm.previews_batch_generate` em todos os `.blend` da biblioteca, sem diálogo (botão "Generate Previews" no painel Asset Libraries).
- **UI Python:** header próprio do modo Assets (View, pai/refresh, tipo de vista, Append/Link, filtros Object/Group/Material, busca). Painéis Asset Libraries e Folder na aba Assets. Os painéis de Bookmarks e o Advanced Filter só aparecem no modo Files.
- **Limitação do 2.79:** ao dar append num objeto filho, o pai não vem junto (`expand_object` não expande `ob->parent`).
- **Testes automatizados** (scratchpad, `-b` e GUI com timer):
  - drop de objeto, grupo e material (append e link) e os erros esperados;
  - troca de modo, adicionar e remover biblioteca (o `bookmarks.txt` fica limpo);
  - desenho da UI sem erro de Python;
  - janela flutuante abre em modo Assets;
  - previews 128×128 gerados para os 5 assets da biblioteca de teste.
  - `RangeEngine` e `RangeRuntime` compilam.

## 2026-09-25 - Material: Subsurface Scattering no modo jogo

- O SSS do GLSL (`set_sss`) lê só Enabled, Scale e RGB Radius; a tonalidade vem da cor Diffuse.
- Painel no modo jogo: presets escondidos (calibrados para o render e mudam o Color, que o jogo ignora);
  RGB Radius exibido pela nova propriedade RNA `game_radius` (mesmo campo `sss_radius`, sem unidade "m").
- Shader: Scale <= 0 é tratado como 0.001, evitando divisão por zero no `pow` (pixels pretos/NaN).
- Lâmpadas com Diffuse desligado não somam mais SSS (antes somavam). Única mudança visual possível em cenas antigas.
- Removida a função morta `set_sss2` do GLSL. Dica do `game_radius` traduzida (pt_BR/es/ru).
- Teste: `.blend` com SSS, Scale 0, lâmpada Point e Sun sem Diffuse roda no RangeRuntime sem erro de shader.

## 2026-09-25 - Material: painel Options do modo jogo

Só interface e textos, sem mudar como o jogo desenha nem o que o `.blend` guarda:

- Escondidos no modo jogo, porque o motor não lê: `Invert Z Depth` (`MA_ZINV`, só `zbuf.c`) e `Light Group Exclusive` (`MA_GROUP_NOLAY`, só `convertblender.c`). Continuam no painel do render antigo.
- Light Group/Local ficavam cinza em todo material que não fosse Halo: o `sub.active` do Point Size pegava a coluna inteira. Agora "Halo Options" só aparece em material Halo.
- Z Offset não fica mais cinza sem Z Transparency: o jogo aplica o offset em qualquer material (`KX_BlenderMaterial`, `SetPolygonOffset`).
- Aviso quando Geometry Instancing e GPU Skinning estão ligados juntos (`BL_BlenderShader::UseInstancing` desliga o instancing nesse caso).
- Tooltips no RNA de `offset_z`, `pass_index` (chega ao shader pelo nó Object Info) e `use_full_sky` (só com céu Atmospheric e sem textura de ambiente), com traduções PT-BR/ES/RU.

## 2026-09-25 - Material: painel Transparency do modo jogo

Só interface e textos, sem mudar como o jogo desenha nem o que o `.blend` guarda. O painel agora mostra o que o motor faz de fato (`KX_BlenderMaterial`, `RAS_BucketManager`, `gpu_material.c`):

- `Alpha Blend` (Game Settings) aparece no topo, como "Blend". É ele que escolhe a passada de render (sólida ou alpha, com ou sem ordenação). Z Transparency só transforma um Opaque em Alpha Blend sem ordenação; Mask/Raytrace não. Com Enabled + Mask/Raytrace + Opaque o material é misturado na passada sólida, sem ordenar e gravando profundidade. O painel avisa essa combinação.
- Alpha fica ativo também com Enabled desligado quando Blend não é Opaque (o alpha chega ao shader nesse caso). Specular só fica ativo com Z/Raytrace e sem Shadeless, que é quando `alpha_spec_correction` é aplicado.
- Depth Transparency: checkbox primeiro e o fator renomeado para "Fade Distance" (é uma distância em unidades da cena), ativo só com Enabled e um modo com mistura (Alpha, Add, Sort). Fora disso, avisa que não tem efeito. Com Enabled desligado e Blend ligado, o motor ainda copia a textura de profundidade todo frame sem usar.
- Tooltips de `use_depth_transparency`/`depth_transp_factor` corrigidos no RNA, com traduções PT-BR/ES/RU.
- Não mexido, anotado: a pré-passada de profundidade para Clip/Alpha to Coverage (`ALPHA_DEPTH_CUTOUT_BUCKET`) nunca roda, porque esses materiais não passam em `IsAlpha()` e vão para o bucket sólido.

## 2026-09-25 - Material: Shader Sources (Vertex/Fragment GLSL)

- `library_query.c`: `Material.vertcode`/`fragcode` (os Texts de `script_vert`/`script_frag`) não eram percorridos por `BKE_library_foreach_ID_link`, e `ID_MA` não declarava uso de `ID_TXT`. Apagar o Text usado como shader deixava o material com um ponteiro para memória liberada, e a próxima compilação chamava `txt_to_buf()` nele. Agora os dois ponteiros são registrados com `IDWALK_CB_NOP`, a mesma convenção do RNA, que não conta usuários de Text. Teste em background: remover o Text zera `script_vert` no material e na cópia, `users` fica estável na cópia/remoção e save/reload está correto.
- Vazamentos: os buffers de `txt_to_buf()` eram liberados dentro do codegen, e não eram liberados quando o material não tinha saída (`used == false`) nem no vertex de material do tipo World. Agora `gpu_material_construct_end` libera os dois depois de `GPU_generate_pass`, e `code_generate_fragment`/`vertex` recebem `const char *`.
- Painel Shading: "Vertex:/Fragment:" eram alinhados aos campos por `separator(factor=3.2)`, o que desalinhava com outra escala de UI. Agora é uma linha por par (`split`) com `template_ID` (botões New/Open, que já atribuem o Text ao campo). A seção não fica mais cinza com Shadeless, porque o GLSL do usuário é aplicado antes do ramo Shadeless em `GPU_shaderesult_set`.
- Pendente: editar o texto do shader não recompila o material; é preciso reatribuir o Text.

## 2026-09-25 - Custom Viewport da câmera

- Camera Presets (lista de câmeras reais) escondidos no Range Engine; Size e Fit do sensor continuam visíveis porque definem o FOV no jogo (`RAS_FramingManager::ComputeFrustum`).
- Range Engine: o tipo da câmera mostra só Perspective/Orthographic (o conversor trata qualquer tipo que não seja `CAM_PERSP` como ortográfico) e avisa se a câmera já estiver em Panoramic. Com Stereo ligado no jogo, o painel Camera mostra "Focal Distance" (`dof_distance`, usado por `RAS_Rasterizer::GetFrustumMatrix`; 0 = 30 × Eye Separation), que tinha ficado inacessível ao esconder o Depth of Field. Display e Safe Areas continuam: não afetam o jogo, mas ajudam a enquadrar a câmera no editor.
- O viewport em pixels era calculado uma única vez na conversão, a partir do tamanho visível do canvas. Com isso, ficava errado depois de redimensionar a janela, com a escala de resolução dinâmica (o render usa `GetRenderWidth`) e no estéreo. Agora `KX_Camera` guarda os ratios (`RAS_CameraData::m_viewportRatios`), e `UpdateViewport()` resolve o retângulo a cada frame, contra a área de render daquele frame e olho, invalidando a projeção só quando ele muda. `setViewport()` do Python continua em pixels fixos.
- Os ratios são carregados mesmo com o viewport desligado, então `useViewport = True` pelo Python usa os valores do editor em vez de um retângulo 0x0.
- Ratios iguais (largura ou altura zero) passam a ser tratados como inválidos, igual aos invertidos.
- RNA: `use_viewport` tinha nome e tooltip copiados de "Show Frustum"; os ratios agora ficam limitados a 0..1. O painel avisa quando Left/Bottom não é menor que Right/Top.
- Painel Custom Viewport redesenhado: caixa de presets (Full Screen, Picture-in-Picture, metades Left/Right/Top/Bottom e os 4 quadrantes) pelo novo operador `camera.game_viewport_preset` (`bl_operators/camera.py`); ratios em pares Horizontal (Left/Right) e Vertical (Bottom/Top); linha "Result" com o tamanho em pixels na resolução do jogo, com o mesmo arredondamento do motor. Traduções em PT-BR, ES e RU.

## 2026-09-25 - Aba Camera em painéis nativos

- `properties_data_camera.py`: as seções deixaram de ser botões de expansão dentro de um único painel e viraram painéis com a seta nativa. Camera (aberto) reúne Lens, Shift & Clipping e Sensor; Depth of Field, Display, Safe Areas, Culling & LOD (Game: LOD, Culling, Shadow Cascade Cache e Optimization Reference), Custom Viewport (Game) e Stereoscopy (Render com multiview) começam fechados.
- Safe Areas e Custom Viewport passaram o checkbox para dentro ("Enabled"). As propriedades `show_expanded_cam_*` deixaram de ser definidas; arquivos que as tenham guardam só IDProperties sem uso.
- Traduções de "Lens:" e "Culling & LOD" em PT-BR, ES e RU. Registro conferido em `RangeEngine --background`.
- Depth of Field, Display e Safe Areas com o conteúdo em caixas com título. Depth of Field fica escondido no Range Engine (`BLENDER_GAME`): é só prévia do compositor do viewport (o High Quality pesa o editor) e o jogo não aplica o efeito; o runtime lê só `YF_dofdist` como distância focal do estéreo.

## 2026-09-25 - Painéis: Foliage próprio, checkbox dentro do conteúdo, Vehicle dividido

- `properties_material.py`: as opções de Foliage saíram de Game Settings para o painel `MATERIAL_PT_game_foliage` ("Foliage Shader", fechado por padrão), com o checkbox `use_foliage` no cabeçalho e duas caixas: Wind (Grass, Strength, Turbulence) e Optimization (Stop Beyond Distance, Wind Distance). As propriedades RNA não mudaram.
- `translations_ui.py`: "Wind:", "Optimization:" e "Stop Beyond Distance" em PT-BR, ES e RU.
- Aba Physics (Game): os painéis visíveis de Physics e Collision Bounds são os de `flowmenu/custom_pt_physics.py` (o `flowmenu` desregistra os de `properties_game.py`). Collision Bounds passou o checkbox para dentro ("Enabled") nas duas versões, e Create Obstacle também. Create Obstacle ganhou `bl_idname = "PHYSICS_PT_game_obstacle_create"`, para que arquivos com a posição antiga salva também o mostrem por último. O `flowmenu` e o addon `easy_ragdoll_RangeEngine` o re-registram depois dos próprios painéis, porque painel novo entra na ordem de registro (`BLI_addtail` em `rna_Panel_register`).
- Aba Vehicle dividida em painéis: Vehicle (checkbox "Enabled", Chassis: Steering Wheel e Center of Mass Offset), Engine (Drive Type e Power), Wheels, Gearbox e Player Component. Os painéis de ajuste só aparecem para Rigid Body/Dynamic e ficam apagados até o veículo ser ativado. Traduções dos textos novos em PT-BR, ES e RU.
- Registro em background (`RangeEngine --background`): todos os painéis novos registram sem erro e o id antigo `PHYSICS_PT_game_obstacles` não existe mais.
- Aba Material sem checkbox no título: Transparency (Render e Game), Mirror, Subsurface Scattering, Flare e Foliage Shader agora mostram o checkbox como primeira linha do conteúdo, com o texto "Enabled", e o restante fica apagado quando ele está desligado.

## 2026-09-25 - Foliage: correções do vento (Web, instancing, precisão, arquivos antigos)

- `gpu_shader_vertex.glsl`: `grass == 1` (float com int) não compilava em GLSL ES 3.00 (Web); agora `grass > 0.5`.
- O vento roda no espaço da malha, antes do instancing e do skinning. Antes rodava depois de `position *= instmat`, então em grama instanciada o corte `z < 0.1` comparava o Z do mundo e a base também balançava.
- Instancing nunca chamava `GPU_material_bind_uniforms()`, então `unfoliageparams` ficava zerado e folhagem instanciada não balançava. `GPU_material_bind()` agora envia os parâmetros para materiais com instancing. A distância do vento é testada no shader por instância (novo `unfoliagecamera`), e cada instância recebe fase de ruído própria (`ininstposition.xy`).
- Precisão: o tempo `time * turbulence` é reduzido com `fmod` para o período 256 no CPU, e o hash do ruído usa `mod(st, 256)`. A troca de período fica contínua, e o `sin` do hash não recebe mais valores enormes em sessões longas.
- Sem câmera ativa, `BL_BlenderShader::BindProg` passa `NULL` e o limite de distância é ignorado (antes media a partir da origem). A referência agora é definida antes do bind.
- `versioning_range.c`: arquivos sem `Material.foliage_distance` recebem 50 m. `foliage_distance <= 0` também desliga o limite, em vez de parar todo o vento.
- Build: `RangeRuntime` e `RangeEngine` compilados. Testado e aceito pelo usuário no desktop em 2026-09-25; o build Web ainda não foi testado (pendência no roadmap).
- Sem mudança: sombras (override shaders) não recebem o vento; normais não são recalculadas; corte seco no limite da distância.

## 2026-09-25 - Cycles OpenCL: validação funcional inicial na AMD

- `build_opencl_validate/` foi configurado isoladamente com `WITH_CYCLES_DEVICE_OPENCL=ON`; em modo serial, `cycles_kernel`, `cycles_device` e `RangeEngine` compilaram e linkaram. O `build/` principal não foi alterado.
- No executável isolado, `_cycles.get_device_types()` confirmou OpenCL ativo e `_cycles.available_devices('OPENCL')` enumerou a RX 6800M e a Radeon integrada. `_cycles.opencl_compile()` com zero argumentos e com índice não numérico retornou `False` e o processo terminou normalmente, validando CYC-006 nos dois casos exercitados.
- Permanecem pendentes apenas cenários de recurso alto/especiais: cópia OpenCL acima de 2 GiB (CYC-007) e a compilação em processo separado com caminho/nome contendo apóstrofo, barra e quebra de linha (CYC-010).

| Arquivo | Datas | Entradas | Tamanho |
|---|---|---|---|
| [este arquivo](changelog.md) (entradas recentes) | 2026-09-25 a 2026-09-25 | 33 | 42 KB |
| [13_2026-09-24_a_2026-09-24.md](changelog/13_2026-09-24_a_2026-09-24.md) | 2026-09-24 a 2026-09-24 | 22 | 30 KB |
| [12_2026-09-23_a_2026-09-23.md](changelog/12_2026-09-23_a_2026-09-23.md) | 2026-09-23 a 2026-09-23 | 9 | 13 KB |
| [11_2026-09-22_a_2026-09-20.md](changelog/11_2026-09-22_a_2026-09-20.md) | 2026-09-22 a 2026-09-20 | 25 | 39 KB |
| [10_2026-09-20_a_2026-09-20.md](changelog/10_2026-09-20_a_2026-09-20.md) | 2026-09-20 a 2026-09-20 | 12 | 19 KB |
| [01_2026-09-20_a_2026-09-14.md](changelog/01_2026-09-20_a_2026-09-14.md) | 2026-09-20 a 2026-09-14 | 45 | 69 KB |
| [02_2026-09-14_a_2026-09-11.md](changelog/02_2026-09-14_a_2026-09-11.md) | 2026-09-14 a 2026-09-11 | 24 | 71 KB |
| [03_2026-09-12_a_2026-08-23.md](changelog/03_2026-09-12_a_2026-08-23.md) | 2026-09-12 a 2026-08-23 | 49 | 90 KB |
| [04_2026-08-24_a_2026-08-24.md](changelog/04_2026-08-24_a_2026-08-24.md) | 2026-08-24 a 2026-08-24 | 4 | 81 KB |
| [05_2026-08-25_a_2026-08-24.md](changelog/05_2026-08-25_a_2026-08-24.md) | 2026-08-25 a 2026-08-24 | 2 | 68 KB |
| [06_2026-08-31_a_2026-08-26.md](changelog/06_2026-08-31_a_2026-08-26.md) | 2026-08-31 a 2026-08-26 | 7 | 71 KB |
| [07_2026-09-02_a_2026-08-31.md](changelog/07_2026-09-02_a_2026-08-31.md) | 2026-09-02 a 2026-08-31 | 23 | 69 KB |
| [08_2026-09-06_a_2026-09-02.md](changelog/08_2026-09-06_a_2026-09-02.md) | 2026-09-06 a 2026-09-02 | 26 | 68 KB |
| [09_2026-09-17_a_2026-09-06.md](changelog/09_2026-09-17_a_2026-09-06.md) | 2026-09-17 a 2026-09-06 | 51 | 71 KB |

## 2026-09-25 - Cycles: upscale em `util_image_resize_pixels`

- `util/util_image_impl.h`: o ramo `scale_factor > 1` alocava a saída e deixava os pixels sem preencher (`TODO`). Agora interpola linearmente por eixo, mapeando centros de pixel e prendendo nas bordas; componentes são interpolados separadamente e o valor volta ao tipo de origem (`uchar`, `uint16_t`, `half`, `float`). Entrada vazia gera saída zerada.
- Imagem 2D (profundidade 1) continua com profundidade 1 no upscale; antes a conta dava profundidade `scale_factor` e transformaria a textura em volume. O downscale já resultava em 1 e não muda.
- O único chamador (`render/image.cpp`) só reduz escala, então o fluxo de render atual não muda; a correção vale para quem reutilizar a API.
- Teste novo `test/util_image_test.cpp` (8 casos: cópia com escala 1, downscale box, upscale 2D, gradiente linear, 4 componentes, escala 1,5 em volume, `uchar`, entrada vazia). Em `build_gtest/`: 8/8 com a correção; com o header anterior, os 6 casos de upscale falham. `cycles_render` recompila sem erro.
- Subdivisão (FVar, `ATTR_ELEMENT_VERTEX_MOTION`), CUDA e OpenCL não foram tocados.

## 2026-09-25 - Cycles: testes de regressão CPU para CYC-001 a CYC-005

- GTest do Cycles volta a configurar e linkar: `GTestTesting.cmake` apontava `WORKING_DIRECTORY` para o alvo `blender`, que não existe desde a troca para `RangeEngine`; o `CMakeLists.txt` de `intern/cycles/test` agora linka `PUGIXML_LIBRARIES` e `WEBP_LIBRARIES`, dependências do OpenImageIO que no Windows só chegavam via OSL/imbuf. Nada muda com `WITH_GTESTS=OFF`.
- Testes novos em `source/intern/cycles/test/`:
  - `util_path_test.cpp` (CYC-001/004): ida e volta de `path_write_binary()`/`path_read_binary()`, escrita em diretório retorna `false`, leitura de arquivo ausente ou vazio retorna `false` com vetor limpo, e `path_file_size()` devolve o sentinela `(size_t)-1`.
  - `util_ies_test.cpp` (CYC-002): contagens zero, negativas, acima de 4.096, grade acima de 1.048.576 e números que estouram `long` são rejeitados; tilt negativo ou acima do limite também; a grade máxima 4096×256 continua aceita; falha limpa um perfil carregado antes.
  - `render_tile_test.cpp` (CYC-003): `TileManager` em 65.536² calcula `total_pixel_samples` (com e sem denoising e com prévia progressiva) e `resolution_divider` = 1024 sem overflow.
  - `render_light_ies_test.cpp` (CYC-005): tabela de offsets de `device_update_ies()` com slot inválido (-1), slot removido no meio e slots finais descartados, usando device CPU.
- Validação em `build_gtest/` separado (cópia do cache de `build/` com `WITH_GTESTS=ON`): `cycles_util_path_test` 41/41, `cycles_util_ies_test` 13/13, `cycles_render_tile_test` 4/4, `cycles_render_light_ies_test` 3/3; o `cycles_render_graph_finalize_test` já existente também passa (61/61).
- Fora do alcance em CPU/memória comum: escrita parcial real (CYC-001, exige injeção de falha no `fwrite`), remoção do arquivo entre `fopen` e `stat` (CYC-004, o Windows não apaga arquivo aberto), alocação de `RenderBuffers` em 65.536² (CYC-003, dezenas de GiB) e soma de IES acima de `INT_MAX` (CYC-005, gigabytes de perfis). Esses ramos seguem validados só por leitura.
- CYC-011: `IESTextParser` agora termina o `vector<char>` com `'\0'` antes de usar `strstr`, `strtod` e `eof()`. Antes, um IES que terminasse no último número podia provocar leitura além do fim. O teste `valid_type_c_without_trailing_newline` cobre essa entrada válida sem quebra de linha final.

## 2026-09-25 - Cycles OpenCL: compilação externa aceita nomes e caminhos especiais

- A expressão Python usada pela compilação OpenCL separada deixou de usar string bruta e passou a serializar barras invertidas, apóstrofos e quebras de linha. Antes, o “escape” de apóstrofo não inseria barra em C++, tornando inválido o `--python-expr` para determinados nomes de dispositivo ou caminhos de cache.
- Validação: `opencl_util.cpp` recompilado no MSVC; o caminho `WITH_OPENCL` continua pendente de execução em build separado.

## 2026-09-25 - Cycles CUDA: carga de kernels e cópia de buffer grande (CYC-008, CYC-009); rede marcada como insegura

- CYC-008: `CUDADevice::load_kernels()` guardava o resultado dos dois módulos na mesma variável; um cubin de render com falha e um de filtro carregado retornavam `true` e levavam `reserve_local_memory()` a lançar kernel com `CUfunction` não inicializado. Agora a carga exige os dois módulos, e `reserve_local_memory()` para se a busca da função ou a ocupação falhar.
- CYC-009: `CUDADevice::mem_copy_from()` passa a multiplicar em `size_t` (mesmo padrão de CYC-007 no OpenCL); cópias de 2 GiB ou mais davam overflow de `int`.
- Revisão estática de `device_cuda.cpp`, `.cu` e `device_network.cpp`: o device de rede ficou registrado como não suportado e inseguro no `docs/relatorio-varredura-cycles.md` (não compila, trava sem `stop` e desreferencia nulo em erro de recepção; o protocolo não tem autenticação). `WITH_CYCLES_NETWORK` continua `OFF`. A falta de suporte a sm_80+ e a CUDA atual entrou como backlog de portabilidade.
- Validação: build separado `build_cuda/` com `WITH_CYCLES_DEVICE_CUDA=ON` e `WITH_CUDA_DYNLOAD=ON` (cuew, sem toolkit NVIDIA); `ninja cycles_device extern_cuew` compilou e linkou sem avisos em `device_cuda.cpp`. O `build/` compartilhado não foi tocado. Sem execução em GPU.

## 2026-09-25 - Cycles OpenCL: cópia de buffer preserva tamanhos grandes

- `OpenCLDevice::mem_copy_from()` agora converte para `size_t` antes de multiplicar elemento, linha, largura e altura. Antes, uma região acima de `INT_MAX` podia sofrer overflow de `int` e passar offset/tamanho incorretos a `clEnqueueReadBuffer()`.
- Validação: `opencl_split.cpp` recompilado no MSVC. A configuração vigente desativa OpenCL; a compilação e o teste do ramo `WITH_OPENCL` ficam pendentes para um build separado.

## 2026-09-25 - Cycles OpenCL: API de compilação rejeita argumentos inválidos

- `device_opencl_compile_kernel()` agora valida que `_cycles.opencl_compile()` recebeu exatamente seis parâmetros e converte o índice de dispositivo sem lançar exceção: texto vazio/não numérico, valor negativo e valor acima de `INT_MAX` retornam `false`. Antes, a entrada Python inválida podia acessar um vetor fora dos limites ou deixar `std::stoi()` encerrar o processo auxiliar de compilação.
- Validação: `opencl_util.cpp` recompilado no MSVC. O build vigente está com OpenCL desligado, então a execução do ramo `WITH_OPENCL` segue pendente de uma configuração própria com OpenCL habilitado.

## 2026-09-25 - Cycles: leitura binária e produtos largura × altura (CYC-004, CYC-003)

- CYC-004: `path_read_binary()` (`util/util_path.cpp`) não passa mais o `(size_t)-1` de `path_file_size()` (stat
  falhou depois do `fopen()`) para `vector::resize()`; retorna `false` com o vetor vazio, também quando o `fread()`
  lê menos bytes. Header inalterado.
- CYC-003: produtos de dimensão passam a `size_t`/`uint64_t`/`int64_t` antes de multiplicar: alocação e cópia do
  buffer em `render/buffers.cpp` (`size` e os laços de `get_denoising_pass_rect`/`get_pass_rect` viraram `size_t`;
  a média do passe Render Time divide em `double`), `get_divider`, contagem de pixel samples em `render/tile.cpp` e o
  vetor de pixels da tile em `blender/blender_session.cpp`. Com 65.536 × 65.536 (limite da RNA) o `int` estourava.
- Validação: os quatro `.obj` compilados no MSVC (compilação só desses objetos, para não pegar o trabalho em
  andamento do Codex no IES). Depois que o Codex terminou, `RangeEngine` relinkado com todo o Cycles e render de
  teste (320×240, 16 amostras, tiles 64×64, cena padrão): saída idêntica pixel a pixel à do binário anterior.

## 2026-09-25 - Sensor Actuator detecta actuators de disparo único

- `SCA_ActuatorSensor::Evaluate` só olhava `IsActive()` no início do frame seguinte. Actuators que ativam e
  desativam no mesmo frame (Property, Message, Add Object, Scene, Game...) já estavam inativos nesse momento, e o
  sensor disparava com `positive=0` (nunca ficava positivo; um AND ligado a ele não fazia nada). O `m_midresult`
  gravado em `Update()` era descartado. Agora o resultado é `IsActive() || m_midresult`, e o `Init` zera o
  `m_midresult`. Código igual ao do Blender/UPBGE original.
- Validação: `RangeRuntime` recompilado; jogo headless gerado por script (`RangeEngine -b`) com Motion (contínuo),
  Property (um disparo), Property disparado 4 frames seguidos e sensor invertido. Antes: Property só gerava
  `positive=0`. Depois: Motion positivo do frame 7 ao 17 (igual antes); Property positivo 1 frame (27→28);
  disparos seguidos ficam positivos sem piscar (34→37); invertido correto.
- Validação no editor: `RangeEngine` relinkado depois do Cycles do Codex; o mesmo jogo, mais um sensor Actuator
  vigiando um Property e outro vigiando um Message, cada um ligado a AND → Property, rodado pelo
  `VIEW3D_OT_game_start` (o P) na janela real. Log igual ao do runtime, e cada AND disparou uma vez
  (`hitProp=1`, `hitMsg=1`).

## 2026-09-25 - Cycles: escrita binária não reporta mais sucesso falso

- `path_write_binary()` em `source/intern/cycles/util/util_path.cpp` agora exige que `fwrite()` grave todos os bytes e que `fclose()` conclua sem erro. Antes, cache binário parcial por disco cheio, quota, I/O interrompido ou falha no flush podia ser aceito como sucesso. A API preserva a assinatura e os chamadores OpenCL já propagam o `bool` retornado.
- Validação: `util_path.cpp` recompilado e `lib/cycles_util.lib` relinkada no ambiente MSVC; `git diff --check` passou. Não há alteração de header/DNA.

## 2026-09-25 - Cycles: parser IES limita contagens antes de alocar

- `IESFile::parse()` preserva os contadores textuais como `long` até validá-los. Perfis IES com eixos zero/negativos, mais de 4.096 ângulos por eixo ou mais de 1.048.576 intensidades agora são rejeitados antes de `reserve()`/`resize()`; a contagem de `TILT=INCLUDE` recebe o mesmo teto. Isso evita conversão de `-1` para `size_t` e alocações excessivas por arquivo corrompido ou embutido.
- O teto de amostras considera que o processamento pode espelhar a tabela horizontal até quatro vezes, mantendo uma IES individual abaixo dos limites de `int`. A soma/offset entre múltiplas IES foi tratada na entrada seguinte (CYC-005).

## 2026-09-25 - Cycles: empacotamento IES não trunca tabela nem offsets

- `LightManager::device_update_ies()` agora calcula a soma de tabelas IES e os índices de slot em `size_t`, e só converte para `int` depois de confirmar que a tabela de offsets e os dados cabem em `INT_MAX`, formato exigido pelo kernel. Isso remove overflow na soma e offset negativo/truncado ao empacotar muitos perfis.
- Quando a capacidade é excedida, a engine envia uma tabela de offsets `-1`: os nós IES afetados não amostram um perfil, mas a renderização não usa memória ou offsets corrompidos. `light.cpp` recompilado e `lib/cycles_render.lib` relinkada no MSVC.

## 2026-09-25 - Animation Events revisados (crashes, threads, sensor, painel)

- Revisão do sistema herdado da Range. **Editor**: o evento agora conta como usuário da Action (`id_us_plus`/`min`
  em `object.c`, `newlibadr_us` no `readfile.c`, `IDWALK_CB_USER` no `library_query.c`, `expand_doit` no append).
  Antes, apagar a Action deixava ponteiro solto (crash ao desenhar o painel) e uma Action usada só pelo evento
  sumia ao salvar. Operadores (`object_animation_event.c`) validam índices e cancelam em vez de crashar, usam a cena
  ativa (antes `G.main->scene.first`), mandam notifier; ▲ no primeiro evento não troca mais com o elemento-base
  escondido (índice 0), que fazia o evento sumir. Remover evento libera os triggers.
- **Runtime**: `BL_Action::Update` roda nas threads do pool de animação e o `KX_Scene::UpdateAnimations` lia/limpava
  a mesma fila de eventos na thread principal ao mesmo tempo. Agora os callbacks rodam depois de
  `BLI_task_pool_work_and_wait`, no mesmo frame. Trigger dispara quando a reprodução cruza o frame (antes: janela
  de ±2 frames + lista "já disparados" por valor de frame, que engolia dois triggers no mesmo frame e zerava todas
  as Actions do objeto); trata loop, ping-pong, sentido reverso e objetos culled; `setActionFrame` não dispara o que
  pulou. `KX_AnimationEvent` guarda dados por valor (acabou vazamento de `new char[64]`/vetores), mantém referência
  própria da função Python e não compartilha proxy com a cópia; evento sem Python Event não gera erro no log;
  `animationEventManager` sem manager retorna `None` com refcount certo; manager não vazava mais uma referência na
  conversão.
- **Sensor Animation Event**: sensor de objeto criado por AddObject apontava para o evento do original (nunca
  disparava) — `KX_GameObject::ReParentLogic` religa. Detecção por contador de disparos (antes comparava o último
  frame e perdia disparos seguidos; com um trigger em loop disparava só uma vez). Conversão não chama mais
  `GetEvent` em manager nulo (`this &&`, UB no clang de Web/Android).
- **Painel**: Action e Python Event em cima, linha Triggers com Add Trigger, aviso com ícone de informação, ▲/▼
  desativados nas pontas, disponível também em Empty/Camera/Lamp.
- **Validação**: compilou (`RangeEngine` + `RangeRuntime`, sem mudança de DNA). Teste headless de 27 checagens dos
  operadores/contagem de usuários/salvar-recarregar passou. Teste no runtime com Action em loop 1-20, triggers em
  1, 10, 10 e 20, callback Python e sensor, num objeto e numa cópia por AddObject: cada trigger disparou 12-13
  vezes nos dois objetos e o sensor pulsou 24/25 vezes. Não verificado: o painel na janela do editor.

## 2026-09-25 - World Status com nomes em inglês

- As 8 World Properties automáticas viraram `rain_enabled`, `rain_intensity`, `clouds_enabled`, `mist_enabled`,
  `mist_density`, `sun_hour`, `cloud_type`, `player_under_cover` (`world.c`, `BL_ConvertProperties.cpp`).
  `horario_sol` virou `sun_hour`, que o runtime já lê para o World Sun automático.
- O `startup.blend` embutido guardava os nomes em português, e o File > New mostrava os dois conjuntos.
  `BKE_world_status_props_ensure` agora renomeia o nome antigo (mantendo o valor) ou o remove quando o novo já
  existe. `.blend` do usuário não são alterados. `RangeEngine -b --factory-startup` lista só as 8 em inglês.
- Painel World: Colors em 4 colunas; Moon Size e Brightness separados.

## 2026-09-25 - Aba Input nas Propriedades (Input System saiu das Preferências)

- O Input System (mapas `KeyMapping/*.json` ao lado do `.range`) era uma seção das Preferências da engine, mas os
  mapas são do projeto e vão no pacote Web/APK. Agora fica numa aba própria **Input** no editor de Propriedades
  (`BCONTEXT_INPUT = 18`, ícone de controle, depois de Export Game), no mesmo padrão da aba Export
  (`DNA_space_types.h`, `buttons_context.c`, `space_buttons.c`, `rna_space.c`, `space_properties.py`). A seção
  das Preferências só avisa que o painel mudou de lugar.
- `bl_ui/properties_input.py`: layout em árvore que abre e fecha, para caber na coluna estreita. Cada mapa abre e
  mostra as ações (Input Tables); cada ação abre e mostra tipo de retorno, ligações e processadores. Um mapa ou ação
  aberto por vez; mapa ou ação recém-criado já abre. Painel "On-screen Controls (Web/Android)" com o layout de toque
  e as ações que ele não aperta (WEB-INPUT-001).
- Correção: o painel antigo registrava propriedades no `WindowManager` durante o desenho, o que o RNA bloqueia
  ("can't set in readonly state"); abrir uma ligação dava erro e sumiam as ligações, os processadores e o botão de
  salvar. Agora o desenho só marca `update_binding_properties` e o handler `scene_update_post`
  (`input_sync_handler`) cria as propriedades e faz o salvamento pedido ao remover uma ligação.
- Traduções pt/es/ru dos textos novos (`INPUT_PANELS` em `translations_labels.py`); "Bindings:" em pt vira "Ligações:".
- Testado no editor com screenshot: criar mapa, ação e ligação (d-pad do joystick 0 como Vector2D), salvar e remover
  a ligação, conferindo o `.json` em cada passo. O motor e o formato do `.json` não mudaram.

## 2026-09-25 - Template de componente "03 Jogador Celular" (teclado, gamepad e controle na tela)

- Novo `release/scripts/templates_components/03_jogador_celular.py`, em Text Editor > Templates > Components.
  É o exemplo recomendado para quem não programa: anexa ao jogador e ajusta `Speed`, `Jump Speed`,
  `Move Relative To Object` e `Stick Deadzone` no painel. Anda com WASD/setas, stick esquerdo ou d-pad do gamepad 0
  e pula com Espaço ou botão A; o controle na tela (layouts `stick` e `dpad`) chega como gamepad 0, então o mesmo
  código serve ao PC, ao controle USB e ao celular. O comentário do topo é o passo a passo e explica que em
  `activeButtons` o botão A é 0 (no Input System é 1).
- Chão por `collisionCallbacks` (contato abaixo do centro com normal quase vertical), não por velocidade vertical
  perto de zero: depois de cair, a física deixa ~0,18→0,02 de velocidade por ~10 quadros e o pulo era ignorado.
  Objeto sem física anda, e o console avisa que ele não pula (sem traceback).
- Teste no `RangeRuntime.exe` (Windows) com cena gerada por script e input simulado no componente: componente
  carregado do `.range`, 3,33 m em 40 quadros com `Speed` 5, pulo 1 quadro após tocar o chão (0,49→1,29 m em
  10 quadros), sem pulo duplo no ar. Teclado, gamepad e toque reais não foram apertados nesse teste. Linux não
  testado; o template é só Python e usa a numeração SDL dos botões, igual nas duas plataformas.

## 2026-09-25 - Export Game: painéis RangeArmor, Web e Android divididos em caixas

- `SCENE_PT_rangearmor_export`: caixas Platforms / Package Info / Export, com dicas (Web e Android têm painéis
  próprios; campos vazios mantêm o padrão do RangeArmor Panel; o `.blend` precisa estar em `<projeto>/data/`).
- `properties_web.py`: caixas Package / Touch Controls / Validation / Export / Browser Test. O relatório da validação
  fica dentro da caixa Validation; "Pré-voo" e "Abrir após exportar" lado a lado.
- `properties_android.py`: caixas App / Build / Release Signing (só com tipo Release) / Tools / Build and Install.
  Versão e código da versão em linhas separadas (o label "Versão do app" ficava cortado).
- Traduções que as capturas revelaram erradas: o tipo de build aparecia como "Liberar" (`.mo` do Blender traduzindo
  "Release") e o runtime Web como "Em execução" (chave genérica "Runtime"). Os itens do enum viraram
  "Debug (testing)" / "Release (players)" e a propriedade `runtime_id` virou "Web runtime", sem mudar identificadores.
  "Product Name" e "Company Name" ganharam tradução. Tudo em `EXPORT_PANELS` de `translations_labels.py`.
- Teste: capturas dos três painéis em pt_BR, es e ru_RU sem traceback; `engine_i18n.py` 36 ok.

## 2026-09-25 - Aba Export Game no editor de Propriedades

- Nova aba `BCONTEXT_EXPORT = 17` (ícone EXPORT) logo depois de Cutscene, no grupo de cima do cabeçalho
  (`DNA_space_types.h`, `rna_space.c`, `buttons_context.c` usa o caminho de cena, `space_buttons.c` desenha o
  contexto `"export"`, `space_properties.py` inclui `'EXPORT'` em `top_context`).
- Os painéis Export (RangeArmor), Web (Range) e Android (Range) saíram da aba Scene e passaram a usar
  `bl_context = "export"`. Traduções da aba em `translations_ui.py`.
- Docs com o caminho antigo (`Properties > Scene > Web (Range)`) atualizados.

## 2026-09-25 - Game Settings > Audio e Scene > Units: labels e dicas

- Audio: "Speed of Sound (m/s)" e "Doppler Factor" no lugar de "Speed"/"Doppler", com dica de que o `LA_Launcher`
  lê esses valores da cena inicial. `audio3d_update` virou "Speaker Update Skip (frames)", com dica de que vale só
  para objetos Speaker e 0 = todo quadro.
- Units: o label do sistema de unidades dizia "Length:" e virou "Unit System:". No Game Engine aparece a dica de que
  as unidades só mudam a exibição no editor (o jogo sempre usa 1 unidade = 1 m) e um aviso quando há Unit Scale
  diferente de 1.
- Traduções pt_BR/es/ru em `translations_labels.py`.

## 2026-09-25 - Build: Ninja não rastreia headers (MSVC em português) e crash ao dar play

- Sintoma: depois de adicionar membros em `KX_GameObject.h` (billboard do LOD), dar play no editor e no RangeRuntime
  fechava a engine (`EXCEPTION_ACCESS_VIOLATION` em `KX_ShadowRenderer::Render`).
- Causa: `msvc_deps_prefix` em `build/CMakeFiles/rules.ninja` é `Observação: incluindo arquivo:`; a saída do MSVC chega
  em outra codificação, o prefixo não bate e o Ninja não registra nenhuma dependência de header. Só os `.cpp` editados
  foram recompilados; `KX_ShadowRenderer.obj` ficou com o layout antigo do `KX_GameObject`.
- Contorno aplicado: apagados os 307 `.obj` de `build/source/gameengine/**` e recompilado (329/329). Engine abre sem
  crash, cena com Sun e sombra roda 120 quadros no RangeRuntime, teste de LOD passa.
- Regra registrada em `AGENTS.md` e `docs/build-notes.md`. Correção definitiva pendente: reconfigurar com `VSLANG=1033`.
  Mudanças antigas em headers da parte C podem ter deixado `.obj` desatualizados; um clean rebuild resolve.

## 2026-09-25 - LOD: billboard restaura a rotação e nível Invisible sem Occlusion Culling

- `KX_GameObject::UpdateLod`: o nível com Billboard girava o objeto para a câmera e nunca devolvia a rotação ao voltar
  para um nível sem billboard. Novos membros `m_lodBillboardActive`/`m_lodBillboardOrientation` guardam a orientação
  ao entrar no billboard e a restauram ao sair.
- `KX_Scene::CalculateVisibleMeshes`: o nível "Invisible Mesh" só escondia o objeto com Occlusion Culling (DBVT)
  ligado. Nova `CullInvisibleLods` aplicada nos caminhos sem frustum culling e sem DBVT (não em shadow buffer).
- `OBJECT_OT_bake_lod_impostor`: grade do atlas agora usa colunas que dividem o número de ângulos (8 ângulos = 4x2,
  antes 3x3 com célula vazia).
- Teste no RangeRuntime (Occlusion Culling desligado): near/billboard/near/invisible/back com nível, `culled` e rotação
  corretos em cada etapa.

## 2026-09-25 - Game Settings (aba Scene): labels, Navigation Mesh separada e Python Console

- `properties_game.py`, `SCENE_PT_game_physics`: "Physics Engine" e "Solver" no lugar de "Engine"; boxes
  "Steps & Timing" (Game Rate / Per Frame, sempre visível), "Deactivation (Sleeping Objects)" e "Culling"
  (Render / Object Activity). Corrigido o ramo com física "None", que usava a propriedade inexistente `logic_step_max`.
- Obstacle Simulation com dica "Used by the Steering actuator to avoid obstacles" e labels "Simulation",
  "Level Height", "Show Debug Visualization" (é o RVO do atuador Steering, independente da navmesh).
- Navigation Mesh virou o painel próprio `SCENE_PT_game_navmesh` (fechado por padrão); removido
  `Scene.show_expanded_game_navmesh`.
- "Level of Detail - LOD" virou "Level of Detail", com dica de que os níveis ficam na aba Object.
- Python Console: checkbox "Enable Python Console" movido para dentro do box, junto das teclas e de uma dica
  (segurar as teclas durante o jogo abre o console do sistema; o jogo pausa enquanto ele está aberto).
- Traduções pt_BR/es/ru dos novos textos em `translations_labels.py` (`RENDER_PANELS`).

## 2026-09-25 - Aba Render: painéis reorganizados, FXAA configurável e addons padrão

- Seletor de engine (`RENDER_PT_render`) movido para `properties_render_engine.py`, registrado antes de
  `properties_game` para ficar no topo da aba Render.
- Player: Embedded e Standalone lado a lado num painel "Player". System e Game Exit Key lado a lado; cursor
  customizado recolhível. Dynamic Resolution foi para dentro do painel Display, ao lado das opções de tela.
- Attachments: slots vazios aparecem como "Empty", mostra o índice `bgl_DataTextures[n]` real, avisa quando há slots
  vazios antes (os índices dos materiais deixam de bater) e quando o SSR usa o Slot 0. `active_attachment_index`
  usa `GAME_ATTACHMENT_COUNT`.
- Animations: frame rate da animação e taxa de lógica lado a lado, com dica do "Restrict Animation Updates".
- Bake: dicas de que precisa de UV e imagem, e de que usa o shading do Blender Render. Easter egg "Make GTA 6" mantido.
- FXAA: `SCENEFXSettings` ganhou `fxaa_edge_threshold`, `fxaa_edge_threshold_min`, `fxaa_subpix` e
  `fxaa_search_steps` (padrões = valores antigos fixos no shader; versioning em `versioning_range.c`). Os shaders do
  viewport (`gpu_shader_fx_fxaa_frag.glsl`) e do jogo (`RAS_Fxaa2DFilter.glsl`, uniform `ge_FxaaParams`) leem esses
  valores; filtros criados por Python/atuador usam os padrões. Painel FXAA expansível em Post-Processing.
- Userpref padrão liga os addons Icon Viewer e Game Engine Scene Statistics (vale para userpref novo; um
  `userpref.blend` salvo mantém a escolha do usuário).

## 2026-09-25 - Build: correções para Android NDK e Cycles no player

- `source/CMakeLists.txt`: sem GLU no Android mesmo com perfil compat. `mallocn_intern.h`: sem `malloc_stats()` no
  bionic. `util_profiling.cpp`: `#include <chrono>`. `blenderplayer/CMakeLists.txt`: liga `bf_intern_cycles` quando
  `WITH_CYCLES` (o `bf_python` registra o módulo `_cycles`).
- `docs/build-dirs.md`: nomes oficiais dos diretórios `build*` (o Android oficial é o APK WebView; `build-android/`
  é o experimento NDK congelado). Referenciado em `AGENTS.md`, `build-notes.md` e `mobile-export-plan.md`.
