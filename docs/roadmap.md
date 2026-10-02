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
- **Reverb Area (2026-09-29)**: validar ouvindo no jogo real (entrar/sair de uma área com um speaker 3D
  tocando) e no Web, onde o OpenAL de compatibilidade (`web-no-openal/efx.h`) pode não ter EFX. Sem desenho
  da zona de efeito total no viewport (só a borda externa, pelo Empty).
- **Áudio 3D/efeitos OpenAL**: só se algum jogo precisar; `Sound.data()`/`buffer()` do `aud` indisponíveis por
  falta de numpy.
- **Filtros 2D**: refinamento visual e custo de múltiplos passes ficam para etapa posterior; tratar como
  opcionais na Internet.
- **`USE_RNA_RANGE_CHECK` no Emscripten (resolvido no M2)**: checagem reativada. Os cinco campos DNA
  (`fie_ima`, `seed1`/`seed2`, `skgen_subdivision_number`, `handle_vertex_size`) viraram `unsigned char`, com SDNA
  idêntico. Evidência em `docs/changelog.md` (2026-09-20). O MSVC nativo não executa essa checagem.

### VR no celular (Web, estilo Cardboard)

Plano e estado em [mobile-vr-plan.md](mobile-vr-plan.md): pose da cabeça pelo `deviceorientation`, head tracking
na câmera, distorção de lente no Side-by-Side e botão "Entrar em VR". OpenXR (headset) adiado até haver hardware.

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
- Linux: `linux-editor` recompilado com `WITH_INTERNATIONAL=ON` e `engine_i18n.py` com 36 ok (2026-09-26); os
  `blender.mo` (pt_BR, pt, es, ru) saem em `bin/2.79/datafiles/locale/` e o `package-runtime.sh` copia o `bin`
  inteiro. Seletor de idioma conferido na janela pelo usuario (2026-09-26).
- Roteiros manuais citam os botões pelo nome em português; em inglês são Validate Web, Export Web, Open in browser.

### Linux x86_64

`RangeRuntime` e `RangeEngine` compilam e rodam em Linux nativo; pacote 0.4.0 publicado. Ver
[linux-build.md](linux-build.md). Pendente:

- **Bugs do Kitsuy (2026-09-28)**: corrigidos e validados no Windows e no Linux (Intel integrada,
  NVIDIA via offload e llvmpipe sem GPU; ver changelog). Falta mandar o build ao Kitsuy.

- **Retorno do Discord (2026-09-29), testar tudo na maquina Linux:**
  - **Dependencias do pacote (Fumangy):** "instalei, mas pede dependencias". O pacote usa as `.so` do sistema
    e o `apt install` da release/`linux-build.md` so vale no Ubuntu 24.04 (nomes com versao: `boost-locale1.83.0`,
    `openexr-3-1-30`, `openimageio2.4t64`, sufixo `t64`). Todas sao exigidas mesmo sem usar o Cycles (so
    `libembree4` e exclusiva dele). Pedir distro/versao e `ldd ./RangeEngine | grep "not found"`. Solucao
    proposta: empacotar as `.so` em `lib/` (RUNPATH `$ORIGIN/lib`, ja usado pelo Python), deixando so
    GL/X11/driver no sistema; validar em Ubuntu 22.04, Debian 12 e Fedora limpos.
    **Diagnostico 2026-09-29 (pacote 0.4.4 extraido, sem apt):** na maquina de build `ldd | grep "not found"`
    sai vazio (ja tem tudo). Dependencias diretas fora de `lib/`: Runtime = GL/GLU/GLEW, X11 (Xi, Xinerama,
    Xxf86vm, Xfixes, Xrender), SDL2, OpenAL, sndfile, freetype, png, jpeg-turbo8, tiff6, fftw3, gomp, z,
    stdc++; o editor soma OpenImageIO 2.4, OpenEXR 3.1, boost_locale 1.83 e embree4. A OIIO puxa ~250 `.so`
    transitivas (GDAL, OpenCV, FFmpeg). **Bloqueio maior:** os binarios exigem `GLIBC_2.38` (`__isoc23_strtol`,
    `__isoc23_sscanf`, `fmod`) e `GLIBCXX_3.4.32`; a glibc nao pode ir em `lib/`, entao Ubuntu 22.04 (2.35) e
    Debian 12 (2.36) nao rodam nem com as `.so` empacotadas. Para cobrir essas distros, compilar o pacote numa
    base antiga (container Ubuntu 22.04/Debian 12) e empacotar as `.so` que nao sao GL/X11/glibc; para o
    editor, avaliar tirar a OIIO do pacote Linux.
    **Feito 2026-09-29:** `package-runtime.sh` empacota as `.so` e o pacote passou a ser compilado num container
    Ubuntu 22.04 (`tools/linux/container-build-22.04.sh`, glibc 2.35). Publicado na v0.4.5; falta o Fumangy
    confirmar no Ubuntu 26.04 (o pacote antigo falhava com `libOpenImageIO.so.2.4`).
  - **Som no player Linux (Kitsuy):** jogo com tela preta no 0.4.5 Linux; causa: `aud` nao lia `.mp3` (libsndfile
    1.0.31 do 22.04 sem MPEG, FFmpeg desligado no Linux). **Feito 2026-09-30:** container compila e empacota a
    libsndfile 1.2.2 com MP3; pacote 0.4.6 toca `.mp3`/`.ogg`. Falta publicar a 0.4.6 e o Kitsuy confirmar.
  - **`colormanagement` no pacote Linux (Kitsuy, 2026-09-30):** falta `2.79/datafiles/colormanagement`; so e
    instalada com `WITH_OPENCOLORIO`, que estava desligado no Linux; player rodava em "fallback mode". **Feito
    2026-09-30:** o apt do 22.04 tem a OCIO 1.1.1 (API 1.x do codigo); presets Linux ligam `WITH_OPENCOLORIO`,
    pacote 0.4.6 leva `libOpenColorIO.so.1` e a pasta, sem "fallback mode". Falta o Kitsuy confirmar.
  - **`RangeRuntime` ignora `SIGTERM`** (handler instalado, processo segue rodando): conferir o handler.
  - ~~Menu do player Linux (Kitsuy)~~: cancelado pelo usuario em 2026-09-29.
  - **Build do zero:** Kitsuy so conseguiu compilar trocando a pasta `source` pela do RGE 1.6.13 dele (pedia
    `CMakePresets.json`) e voltando depois. Conferir que clone limpo + presets compila sem cache antigo.
    **2026-09-29:** clone limpo da `main` + `cmake --preset linux-editor -S source` configurou e compilou
    RangeEngine e RangeRuntime (2858/2858, sem erro) em Ubuntu 24.04; player abriu demo. Causa provavel: a doc
    mandava usar a branch `linux-sync` (106 commits atras); doc corrigida e branch apagada. Falta o Kitsuy
    confirmar com clone novo.
  - **`setHalfAnimations(1)`:** Kitsuy confirmou sem crash no Linux e no Windows; reconferir no build proprio.
  - **Zip Windows 0.4.4 com `\` nos caminhos** (extraido no Linux sai sem pastas): refeito em 2026-09-29 com `/`
    (Python `zipfile`), extraido e identico ao staging. Falta abrir os `.exe` da copia extraida e subir o asset
    (`gh release upload --clobber`). Nao usar `Compress-Archive` do PowerShell 5.1.
- **API float/int/bool do Kitsuy** (`KX_GameObject` com `m_float1..9`, `m_int1..9`, `m_bool1..9`, enviada em
  2026-09-29): nao integrada. Nomes genericos e limite fixo; perguntar o caso de uso e, se valer, propor
  propriedades tipadas com nome ou um vetor `own.data`.
- **Nao sao bugs (Kitsuy):** carro precisa do modo de frame rate fixo (duas atualizacoes de fisica a mais para
  as rodas); iluminacao estranha era o ajuste de environment lighting do jogo dele.

- **Pacote 0.4.0 quebrado no Linux** (`libpython3.11.so.1.0` nao encontrado; tooltip crasha o editor) —
  **ambos corrigidos e validados em Linux nativo 2026-09-21** (RUNPATH `$ORIGIN/lib`, e use-after-free de
  `ARegion` em `wm_tooltip.c` corrigido + testado em sessao grafica real; "Python Tooltips" agora vem marcado
  por padrao para exercitar o caminho de codigo, ver `linux-build.md`/`changelog.md`). A `linux-sync` foi
  testada no Linux pelo usuario em 2026-09-21 ("tudo ok"). **Pacote 0.4.1 publicado e corrigido em
  2026-09-22**: release anterior só continha `RangeEngine` (bug em `tools/linux/package-runtime.sh`, faltava
  `RangeRuntime`); script corrigido, os dois presets recompilados/reempacotados juntos e o asset do GitHub
  Release `v0.4.1` atualizado via `gh release upload --clobber`. Testado localmente com sessão gráfica real:
  `RangeEngine` abre sem erros e `RangeRuntime` carrega um `.range` de exemplo, detecta GPU/OpenGL (Mesa Intel
  RPL-P, OpenGL 4.6) e renderiza sem erros. Teste feito na própria máquina de build. **Máquina limpa testada em
  2026-09-26** (container Ubuntu 24.04 mínimo): o 0.4.1 não acha a stdlib do Python fora da máquina de build;
  `package-runtime.sh` corrigido e o editor renderiza com Cycles no container. Release `v0.4.2` corrigido
  publicado em 2026-09-26 (editor + runtime); `v0.4.3` Linux publicado em 2026-09-27. Janela testada num Ubuntu 24.04 limpo em 2026-09-28 (container, Intel Mesa; ver `linux-build.md`). Lista de pacotes de runtime em `linux-build.md`.
- **Cycles no editor Linux**: ligado no preset `linux-editor` com Embree 4, CUDA e OpenCL; CPU testada pela
  interface (com e sem Embree) e CUDA (RTX 5060, sm_120, CUDA 13.0) testada pela interface (2026-09-26).
  CUDA no Windows (CUDA 13.4, sm_120) testado pela interface, render e bake (2026-09-26).
  OpenCL no Windows (RX 6800M) testado pela interface e em `-b`, render e bake (2026-09-26).
  Pendente, sem maquina Linux com GPU AMD disponivel: testar OpenCL no Linux. O WSL nao serve (nao expoe
  o OpenCL da AMD); precisa de Linux instalado (dual boot ou pendrive). Se um usuario Linux com AMD
  aparecer, pedir o teste. Roteiro: Preferences > System > Cycles
  Compute Device = OpenCL, marcar a GPU AMD; Render Device = GPU Compute; renderizar a cena padrao e fazer
  bake de AO (chao sob cubo) comparando com a CPU. O primeiro uso compila o kernel OpenCL e pode demorar
  varios minutos. Cubins CUDA para sm_75/sm_86/sm_89/sm_120 (RTX 20/30/40/50) no release desde 2026-09-26;
  so sm_120 testado em hardware real. OSL fica desligado (sem pacote no Ubuntu
  24.04; exige OSL 1.9 com LLVM antigo).
- Portar `WITH_OPENCOLORIO` (API 1 → 2.x, dezenas de call sites em `intern/opencolorio`) e `WITH_CODEC_FFMPEG`
  do editor para OpenColorIO 2.x/FFmpeg 5+. Só necessário fora do container 22.04 (Ubuntu 24.04+ só tem OCIO
  2.x): o container usa a OCIO 1.1.1 do apt desde 2026-09-30. FFmpeg segue desligado; só o wrapper `audaspace`
  do FFmpeg foi ajustado.

### Cutscene nativo

Fases 0–2 e 4–5 implementadas; validação manual (Play → Stop → Play e standalone) aceita em 2026-09-20.
Aberto: Fase 3 (ícones PNG próprios, sem substituir os `ZOOMIN`/`ZOOMOUT`). Ver
[plano](cutscene-native-integration-plan.md) e [roteiro](cutscene-native-example.md).
Evento Camera Path (2026-09-30): falta relinkar `RangeEngine` e o usuário testar no jogo. Wait Trigger ainda não
é liberado por nada no código, e o export/import só cobre Spawn Object.

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

### Destruição e explosões

[Plano](destruction-plan.md) aprovado em 2026-09-29; F0 (DNA, RNA e painéis), F1 (Generate Fragments), F2 (quebra por colisão e `shatter()` no runtime), F3 (`scene.explode()`, pavio, impacto, cadeia, Effect e `detonate()`), F4 (Max Debris, `onBreak`/`onExplode`, impulso por massa nos pedaços) e F5 (demo em `source/release/demos/Destruction/`, API no `.rst`) prontas; falta o usuário jogar a demo e ajustar a sensação: objetos
pré-fraturados (Cell Fracture) e explosivos, com os painéis Destruction e Explosive na aba Physics e
`scene.explode()`, em fases F0–F5. Protótipo Python validado por teste automático no runtime
0.4.5 (fora do git, em `tools/ADD na engine anastacioEngine/`).

### Câmera: foco, rastreio e Camera FX

Implementado em 2026-09-29 (fases 1 a 5 do [plano](camera-fx-plan.md)); referência em [camera-fx.md](camera-fx.md).
Validado no `RangeRuntime` com `tools/create_camera_fx_scene.py` (foco por propriedade, Drone, shake, fallback
após remover o alvo, efeitos desligados em jogo). Pendente: conferência visual dos filtros e custo medido
(`tc_filters2d`) no Rolima Racer; troca dos scripts do jogo fica para quando o usuário decidir.

### Logic Bricks → Python Component

Fase 1 pronta em 2026-09-30: botão **To Python** no header do Logic Editor (`logic.convert_to_component`,
`bl_operators/logic_to_python.py`) gera `<objeto>_logic.py` com um `KX_PythonComponent`, registra no objeto e
desativa só os bricks convertidos. Suporta Always, Keyboard, Mouse (botões, roda, movimento), Property sensor;
And/Or/Nand/Nor/Xor/Xnor; Motion simples, Property (Assign/Add/Toggle/Copy), State, Message; estados e pulsos.
Validado com `tools/create_logic_convert_scene.py` (mesmo resultado com bricks e com componente). Próximas fases:
- F2 (parcial, 2026-09-30): feitos Collision (propriedade), Near, Radar, Ray (propriedade), Delay (frames),
  Mouse Over, controller Expression, actuators Edit Object (Add/End/Replace Mesh/Dynamics), Scene, Game,
  Visibility; depois Random (mesma cadência, sequência do `random` do Python), Track To (alvo fixo, sem pai) e
  Sound (Play/Loop Stop/End, via `aud`; ping-pong fica como brick) e Camera actuator. Controller
  Python fica como brick (já é código). Collision/Ray por material convertidos (Ray por material com x-ray fica como brick). Links entre objetos convertidos (sensor/actuator de outro objeto via `scene.objects.get`; Collision/Near/Radar e actuators com helper do próprio objeto ficam como brick). Message sensor convertido
  via `logic.getMessages` (nova API).
- F3 (2026-09-30): campo Mode no operador: Python Component (padrão), Always + Python (Module) e
  Always + Python (Script). Os dois últimos criam `LC_always` (pulso contínuo) e um controller `LC_state_<n>`
  por estado usado; o código é o mesmo, com `main(cont)` no fim. Mesmo CHECK nos três modos.
- Pendente: usuário testar no editor com um objeto real lotado de bricks.

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
- **Loop de tempo (perguntas ao Kitsuy, 2026-09-26)**: (1) em `KX_KetsjiEngine::FrameOver()`, o ramo de
  `m_overframetime < 0` usa `m_deltaTime` (passo lógico) onde o resto usa `m_deltatime` (tempo real): erro de
  digitação herdado ou intencional? Não mudar sem a resposta. (2) `m_timeUnderRate` é `long`: com Max Logic
  Frames = 5 a 60 Hz a conta dá ~0,02 e vira `sleep_for(0ms)`, o loop gira sem dormir. É intencional?
- **Release**: antes da próxima distribuição, declarar se o fork sai como GPLv2-or-later ou GPLv3 e incluir o
  arquivo de licença correspondente na raiz/pacote.

## Performance

- Culling de sombra com occlusion: em `benchmark.range` (1920x1080, 2026-09-28) `ShadowCulling` custa
  14.3ms (60% do frame; ~13 passadas: 10 Spots + Sun em cascata, occlusion res 128). Com occlusion desligado
  na cena: 0.3ms e FPS 41→59.5 (A/B repetido 2x). `MainRender` é só ~0.5ms (o antigo "MainRender alto"
  era GPU/fill-rate). Proposta: não usar occlusion nas passadas de sombra (`is_shadowbuf`) em
  `KX_Scene::CalculateVisibleMeshes`; câmera principal mantém. Aplicada em 2026-09-28: sombras não usam DBVT (usar DBVT sem occlusion
  sumia com os personagens com skinning); 60 FPS, `ShadowCulling` 0.4ms, `Skinning` normal. Teste visual do usuário OK em 2026-09-28 (sombras dos personagens, sem sumir nem piscar).
- Avaliar folhagem e LOD na cena real; impostor e bake de atlas já existem, o resto pode ser trabalho de asset.
- Navmesh dinâmica: hoje o navmesh é gerado uma vez (`mesh.navmesh_make`). Plano (2026-09-28), passos
  pequenos, cada um compilável e confirmado antes do próximo:
  1. Vendorizar `DetourTileCache/` de `tools/recastnavigation-upstream` + compressor passthrough (CMake,
     `readme-blender.txt`).
  2. Membros novos em `KX_NavMeshObject` (tile cache, alocador, compressor, `m_dynamic`), sem mudar
     comportamento.
  3. `BuildNavMeshTiled()` opt-in (property `dynamic_navmesh`), reconstruindo a partir dos polígonos do próprio
     navmesh com parâmetros de `gm.recastData`; caminho estático intacto, sem DNA nova. Avisos ao usuário:
     no painel (Python, `layout.label(icon='ERROR')`) quando `dynamic_navmesh` existe mas não é booleana,
     quando o modo dinâmico está ligado sem navmesh gerada, e quando há obstáculo sem navmesh dinâmica na cena;
     no console, ao iniciar o jogo, se o build dinâmico falhar e cair para o estático. Tooltip avisa que os
     caminhos podem diferir levemente do estático.
  Passos 1-3 feitos em 2026-09-28 (aviso de "obstáculo sem navmesh dinâmica" fica para o passo 4). Cena de
  teste (plano + caixa): caminhos dinâmicos contornam a caixa e diferem do estático em até ~0.6 de comprimento.
  4. Obstáculos: objetos com `OB_HASOBSTACLE` (raio `obstacleRad`, altura da bbox); remover+adicionar ao mover;
     limpar ao destruir.
  5. `dtTileCache::update` por frame em `KX_Scene::LogicEndFrame`.
  Passos 4-5 feitos em 2026-09-28: `KX_Scene` guarda os objetos com "Create Obstacle" (mesmo sem Obstacle
  Simulation) e as navmeshes dinâmicas; `LogicEndFrame` chama `KX_NavMeshObject::UpdateObstacles` (cilindro
  com raio `obstacleRad` e altura da bbox; remove+adiciona ao mover mais de 0.1; remove ao destruir). Painel
  Create Obstacle avisa quando não há navmesh dinâmica na cena. Teste: cilindro no caminho aumenta a rota
  (17.89 → 18.75) e ela volta ao original quando o obstáculo sai. Segmentos de borda da Obstacle Simulation
  continuam os do build inicial.
  6. `KX_SteeringActuator` refaz `findPath` quando o navmesh mudar (contador de versão).
  Passo 6 feito em 2026-09-28: `KX_NavMeshObject::GetVersion()` sobe quando a navmesh é reconstruída ou
  quando os tiles terminam de mudar; o Steering refaz o caminho se a versão mudou, mesmo com update period -1.
  7. Python (`dynamic`, `rebuild()`, `addObstacle`/`removeObstacle`) + docs. DetourCrowd fica para depois.
  Passo 7 feito em 2026-09-28: `KX_NavMeshObject.dynamic` e `.version` (só leitura),
  `addObstacle(object, radius=0.0)` e `removeObstacle(object)`; raio automático usa o "Create Obstacle" ou
  metade da bbox. Teste visual do usuário OK em 2026-09-28: painel, console, cilindros amarelos do `draw()` e
  agente com Steering contornando obstáculo em movimento. Aviso de Create Obstacle sem navmesh dinâmica não foi
  visto na tela.
  Riscos: perda de precisão nas bordas, atraso de alguns frames, ponteiros de objetos destruídos.

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
  nodes em uma cena maior. Diffuse/Glossy/Toon usam o mesmo loop desde a Fase 3 (abaixo).
- **Nós de material Game × Cycles × BI** (matriz em [node-material-support.md](node-material-support.md)):
  Fases 1 (correções GLSL, World como ambiente), 2 (selos `~Game`/alerta no editor) e 3 (Diffuse/Glossy/Toon no
  loop de luzes do Principled) feitas em 2026-10-01; Fase 4 (Glass/Refraction com fresnel + World,
  reflexo no Glossy, Toon Glossy, AO por concavidade local, Blackbody, Wavelength, Sky Preetham). Fase 5
  (Filmic/exposure/gamma de Color Management aplicados na saída do material nodes, aproximado) feita em 2026-10-01. Fases 3 a 5
  validadas pelo usuário em 2026-10-02 (`tools/create_node_phases_test.py`). Tangent e Anisotropic BSDF de verdade em
  2026-10-02; Wireframe segue sem suporte (sem baricêntricas no fragment shader). Fase 6 decidida em 2026-10-01: o BI fica como está (Game legado segue com os nós do BI, sem migração).
- **Principled/PBR no Web**: luzes de cena e sombra portadas para o perfil CORE (`unflightsource[]`, changelog de
  2026-09-23); aceite visual do usuário no navegador com GPU real em 2026-09-23 (brilhos das luzes e sombras
  das esferas corretos). Falta só reconferir o desktop.
- Sombras (`gpu_lamp_wants_shadow` em `gpu_material.c`): com Shading Nodes, Sun, Spot e Point seguem o
  `Cast Shadow` do Cycles (Point por atlas de cubo 3x2, 2026-10-01, validado pelo usuário); sem Shading Nodes,
  Sun exige `RAY_SHADOW`, Spot `BUFFER_SHADOW` e Point não tem sombra. A Point não aparece no viewport do editor
  nem nos materiais BI.
- **Light probes**: reflection probe local feito em 2026-10-01 (propriedade `probe` num objeto, ver changelog);
  validado pelo usuário em `probe_reflection_test.range`. Em aberto: luz difusa local (irradiance, harmônicos
  esféricos do mesmo cubemap), mistura entre probes vizinhos e correção de paralaxe por caixa.
- **Resolução dinâmica**: opt-in em `Game Render Properties > Dynamic Resolution`; validada em cena GPU-bound
  (aceite de 2026-09-20).
- **CSM**: blend entre cascatas e debug tint já implementados; falta medir o custo de GPU dessas duas features.
- Avaliar antialiasing temporal somente com caso de uso e critérios de qualidade definidos.
- Aceitos como no-op no core profile (reabrir só com demanda concreta): motion blur legado e texto de
  debug via `BLF_draw` (o clipping de espelho/água foi resolvido com projeção oblíqua em 2026-09-28).

## Validações manuais pendentes

Aceitas pelo usuário em 2026-09-20 e removidas daqui: sombras no jogo real (Planos 1A e 5, múltiplas luzes),
migração de `maxphystep`, Sol/Lens Flare, splash e About, Outliner, barra da 3D View, aba Particles, gamepad no
menu ImGui e Runtime Property Sensors/Actuators. O stress de captura de vídeo e OpenAL foi cancelado por decisão do usuário. Ainda abertos:

- **Sombras**: registrar a origem dos avisos de textura sem nível-base vistos em `-d gpu` (desconhecida).
- **Game Settings, FXAA e LOD (2026-09-25)**: conferir no jogo real os painéis novos das abas Render e Scene,
  os ajustes de FXAA e o LOD com Billboard/Invisible.
- **Foliage no Web (2026-09-25)**: conferir num build Web que um material com Foliage Shader compila
  (troca `grass == 1` → `grass > 0.5` no vertex shader) e que o vento anima. No desktop foi aceito pelo usuário.
- **Shader Sources do material (2026-09-25)**: conferir no jogo real um material com Vertex/Fragment GLSL
  próprio (a posse dos buffers do código do usuário mudou para `gpu_material.c`) e o layout novo do painel
  Shading. Em aberto: editar o Text não recompila o material.
- **Painel Transparency do modo jogo (2026-09-25)**: conferir no editor o layout novo e os dois avisos
  (Mask/Raytrace + Opaque; Depth Transparency sem efeito). Em aberto, sem decisão: a pré-passada de
  profundidade de Clip/Alpha to Coverage em `RAS_BucketManager` nunca roda (o bucket fica sempre vazio).
- **Painel Options do modo jogo (2026-09-25)**: conferir no editor o painel sem Invert Z/Exclusive, Light Group
  ativo fora de Halo, Z Offset sempre ativo e o aviso de Instancing + GPU Skinning.
- **Painel Subsurface Scattering do modo jogo (2026-09-25)**: conferir no editor que os presets somem, o RGB
  Radius aparece sem "m" e que o efeito some ao desligar Diffuse na lâmpada.
- **Asset Browser (2026-09-25)**: conferir na janela real o gesto de arrastar um asset (objeto, grupo, material)
  do modo Assets para a Vista 3D, o duplo clique, o toggle Append/Link, a janela Window > Asset Browser e as
  miniaturas depois de "Generate Previews". Troca de modo, bibliotecas, drop, janela e previews passaram em
  execução automatizada, mas nenhum gesto com o mouse foi testado.
- **Loop de tempo (2026-09-26)**: o teste automático (cena simples, monitor 165 Hz) já passou; ver changelog de
  2026-09-27. Falta conferir no jogo real, num monitor de 60 Hz se houver, com v-sync ligado e desligado, que o FPS
  não trava em 30, não perde tecla e o veículo não muda. Com v-sync e picos de carga o jogo não recupera mais o
  tempo perdido (57,7 fps médios no teste); ver se isso incomoda no jogo real.
- **Profiler (Plano 2)**: opcionalmente conferir as categorias `CollisionDepth`/`TextureRenderers` como linhas
  separadas num relatório de benchmark.

## Fora do escopo atual

- Paralelização ampla do loop principal e remoção do GIL de Python.
- Atualização completa do Bullet apenas para obter solver multithread.
- Edição de cena durante o jogo com persistência automática.
- Reimplementação de recursos herdados listados no relatório de melhorias.
