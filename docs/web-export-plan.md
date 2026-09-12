# Plano — Export para Web (WebGL/WebAssembly)

## Objetivo

Levantar o estado atual da engine em relação a portabilidade Web via Emscripten
e comparar o esforço com o já mapeado para mobile em
[`mobile-export-plan.md`](mobile-export-plan.md). Este documento é um
**levantamento + plano preliminar**, não uma decisão de implementação. Nenhum
código foi alterado para produzi-lo.

## Por que comparar com Android/iOS em vez de tratar como caso isolado

A pergunta que motivou este documento foi "é melhor exportar para Web?",
comparando com o levantamento mobile já feito. A resposta depende de quanto
trabalho de terceiros dá para reaproveitar versus quanto teria que ser escrito
do zero — o mesmo eixo usado no levantamento mobile (lá, a saída foi "GHOST
via SDL2 evita escrever um backend nativo do zero"). Para Web, o Emscripten
já entrega pronto justamente a peça que mais pesa no port mobile: a ponte
janela/input/áudio via SDL2.

## Levantamento do estado atual

### 1. GHOST (camada de janela/plataforma)

Backends existentes em `source/intern/ghost/intern/`: Win32, X11, **SDL2**
(`GHOST_SystemSDL.cpp/.h`, `GHOST_WindowSDL.cpp/.h`,
`GHOST_DisplayManagerSDL.cpp/.h`, atrás de `WITH_GHOST_SDL`), Cocoa (macOS),
NULL (headless).

**Não existe backend Web/Emscripten.** Mas, diferente do Android (que exigiria
escrever `GHOST_SystemAndroid`/`GHOST_WindowAndroid` do zero), o backend SDL2
**já existe e já compila** neste repositório. O Emscripten tem porta oficial
de SDL2 embutida no próprio toolchain (`-sUSE_SDL=2`), que traduz chamadas
SDL2 de janela/eventos/áudio para `<canvas>`/Web Audio automaticamente. Ou
seja: o caminho mais provável para Web é reutilizar `GHOST_SystemSDL` como
está, compilado sob Emscripten, em vez de escrever qualquer backend novo de
janela — trabalho estrutural bem menor que o backend GHOST que Android exige.

Gap real, não de janela mas de **loop de execução**: o código desktop assume
um loop bloqueante (`while (window open) { poll events; render; }`). O
Emscripten não permite loop bloqueante no thread principal (trava a aba) —
exige `emscripten_set_main_loop()`, que registra um callback por frame e
devolve o controle ao navegador. Isso é uma mudança estrutural no ponto de
entrada do runtime (`RangeRuntime`/embedplayer), não em GHOST em si.

### 2. Build system (CMake)

`source/CMakeLists.txt` reconhece `UNIX AND NOT APPLE`, `APPLE`, `WIN32` e,
desde a exploração Android, `ANDROID` (ver `platform_android.cmake`, stub).
**Não existe ramo `EMSCRIPTEN`** nem toolchain file para ele hoje.

O Emscripten se apresenta ao CMake como uma toolchain própria
(`emcmake cmake ...`, usando `<emsdk>/upstream/emscripten/cmake/Modules/Platform/Emscripten.cmake`)
e a variável de plataforma que o CMake expõe é `EMSCRIPTEN` (não `UNIX`, ainda
que o Emscripten simule POSIX/Bionic-like em vários pontos). Precisaria de um
`platform_web.cmake` novo, roteado de forma equivalente ao que já foi feito
para `ANDROID` — o mesmo padrão de dispatch em `CMakeLists.txt`, já provado
navegável na exploração de 2026-09-09.

Já existe infraestrutura relevante, reaproveitável do trabalho mobile:
- `WITH_GLEW_ES`, `WITH_GL_EGL`, `WITH_GL_PROFILE_ES20` (linhas ~515-527) —
  WebGL 1 mapeia para GLES 2.0 e WebGL 2 para GLES 3.0, então essas opções
  servem tanto para Android quanto para Web.
- `WITH_GL_PROFILE_CORE_RANGERUNTIME` — a migração Core Profile do
  `RangeRuntime` (concluída, ver changelog) já removeu fixed-function/
  immediate-mode e versionou os shaders — pré-requisito comum a ES *e*
  WebGL, não seria refeito.
- CMakePresets já usado para `linux-runtime` e `android-runtime` (exploratório)
  — um preset `web-runtime` seguiria o mesmo padrão, com
  `CMAKE_TOOLCHAIN_FILE` apontando para `Emscripten.cmake` do emsdk.

### 3. Input

Mesma lacuna do mobile: **não existe conceito de touch/toque na engine**
(`SCA_IInputDevice` só cobre teclado/mouse/joystick desktop). Diferente do
Android, porém, um build Web em desktop (mouse/teclado, jogado no navegador)
não teria essa lacuna — só passa a existir se o alvo for celular via
navegador. SDL2 já traduz mouse/teclado do navegador para os eventos GHOST
existentes sem trabalho extra, incluindo sob Emscripten (a porta SDL2 do
Emscripten mapeia eventos DOM de mouse/teclado para a API SDL2 normal).

### 4. Rasterizer / OpenGL → WebGL

Mesma base do levantamento mobile: a migração Core Profile do
`RangeRuntime` (35 call sites em 4 arquivos, documentada em várias entradas
do `changelog.md`) removeu matrix stack fixo, fixed-function de
material/luz e desenho imediato (`glBegin`), migrando shaders para
`#version 330 core`. Esse é o mesmo trabalho estrutural que WebGL exige
(GLSL ES/WebGL não tem fixed-function nem immediate-mode).

Gaps específicos de WebGL, além dos já conhecidos do Core Profile
(`glClipPlane`, motion blur via `glAccum`, fallback de `gl_LightSource[]`):
- **Sintaxe GLSL ES** (`precision mediump float;` etc.) — mesmo gap já
  registrado para Android, GLSL desktop não é 100% compatível.
- **WebGL 1 = GLES 2.0, WebGL 2 = GLES 3.0** — se o CSM (cascade shadow
  maps) ou outro recurso usar funcionalidade só de GLES 3/desktop 4.x, o
  piso mínimo aceitável (WebGL 1 vs. exigir WebGL 2, suportado por ~97% dos
  navegadores modernos) precisa ser decidido cedo.
- Emscripten com `-sUSE_SDL=2 -sFULL_ES3=1` ou `-sUSE_WEBGL2=1` cria o
  contexto WebGL automaticamente via a mesma chamada SDL2 (`SDL_GL_CreateContext`)
  já usada no desktop — não precisa de EGL manual como Android exigiria.

### 5. Áudio

`source/intern/audaspace/` com backend OpenAL (`WITH_OPENAL`, padrão ON,
mas **depende de `WITH_AUDASPACE`** — se audaspace estiver desligado,
`WITH_OPENAL` é forçado a `OFF` com warning, `CMakeLists.txt:695-697`).

Emscripten tem porta própria de OpenAL Soft (`-sUSE_OPENAL=1`), que traduz
para Web Audio API automaticamente — mesma lógica da porta SDL2, evita
cross-compilar OpenAL Soft manualmente como Android/iOS exigiriam. Restrição
conhecida do navegador (não específica desta engine): a maioria exige um
gesto do usuário (clique) antes de liberar áudio — precisa de tratamento no
ponto de entrada do jogo, não é um bloqueio de engine.

### 6. Python embarcado

Diferente de Android/iOS (que exigiriam cross-compilar CPython do zero via
`python-for-android` ou `Python-Apple-support`), o **CPython tem alvo oficial
`wasm32-emscripten`**, mantido junto do projeto Pyodide desde a série 3.11 —
mais maduro e testado do que as alternativas mobile. Ainda assim é um build
separado, com suas próprias limitações: sem threads reais por padrão, sem
`subprocess`/sockets nativos, `sys.platform == "emscripten"` muda caminhos de
detecção de plataforma que o projeto já trata por CMake
(`platform_win32.cmake` etc.) — precisaria de um `platform_web.cmake`
equivalente.

### 7. Física

Bullet 2.84 (`source/extern/bullet2`) é C++ portável, compila sob Emscripten
sem alteração conhecida — mesma conclusão do levantamento mobile (menor
risco).

### 8. Threads e memória (gaps que Android/iOS não têm da mesma forma)

- **Memória**: WASM32 usa espaço de endereçamento de 32 bits — mesmo com
  `ALLOW_MEMORY_GROWTH`, o teto prático fica bem abaixo do que um binário
  nativo 64-bit assume. Cenas com muita textura/geometria carregada de uma
  vez podem esbarrar nisso antes de qualquer gargalo de GPU.
- **Threads reais** (`pthreads` em Wasm) exigem `SharedArrayBuffer`, que por
  sua vez exige os cabeçalhos HTTP `Cross-Origin-Opener-Policy` e
  `Cross-Origin-Embedder-Policy` no servidor que hospeda o build — se algum
  subsistema da engine depender de threads (não confirmado/não investigado
  neste levantamento), isso é fricção de **deploy**, não só de build, e
  precisa ser documentado para quem for hospedar o jogo.
- **Sistema de arquivos**: Emscripten expõe um FS virtual em memória por
  padrão; persistência real (save game) exige `IDBFS` (IndexedDB) montado
  explicitamente e sincronizado (`FS.syncfs`) — comportamento assíncrono,
  diferente de escrever um arquivo direto como no desktop/Linux atual.

### 9. Docs existentes / alinhamento com Linux e mobile

- **`docs/linux-build.md`** — o trabalho de separar `RangeRuntime` do editor
  e isolar dependências Win32-only é a mesma base reaproveitada aqui, como já
  é para mobile.
- **`docs/mobile-export-plan.md`** — mesmo eixo de análise (GHOST/CMake/
  input/rasterizer/áudio/Python/física), usado como referência direta deste
  documento; a exploração prática de Android lá (2026-09-09) confirma que o
  dispatch de plataforma no CMake aceita uma plataforma nova com pouca
  cirurgia, o que também vale para `EMSCRIPTEN`.
- **`docs/distribution-0.1.md`** — convenção de empacotamento (ZIP portátil
  + `SHA256SUMS.txt`); Web não empacota da mesma forma (não há "instalar", é
  hospedar arquivos estáticos gerados pelo Emscripten: `.html`/`.js`/`.wasm`/
  `.data`), então esse documento precisaria de uma seção nova, não uma
  adaptação do fluxo atual.
- **`docs/roadmap.md`** — nenhum item Web hoje.

## Conclusão do levantamento

Comparado ao mobile, Web tem um gap estrutural visivelmente menor porque
Emscripten já entrega pronto, como parte do toolchain, exatamente as três
peças que mais pesam no port mobile:

1. **Janela/input/áudio**: reaproveita `GHOST_SystemSDL` (já existe e
   compila neste repo) via a porta SDL2 do Emscripten, em vez de escrever um
   backend de plataforma do zero.
2. **Runtime Python para Wasm**: CPython tem alvo oficial `wasm32-emscripten`
   (Pyodide), mais maduro que as rotas de cross-compile mobile.
3. **Contexto gráfico**: `SDL_GL_CreateContext` sob Emscripten já cria WebGL
   automaticamente, sem a ponte manual `ANativeWindow`→EGL que Android exige.

O trabalho real que sobra é: (a) `platform_web.cmake` + preset
`web-runtime`, seguindo o padrão já validado para `ANDROID`; (b) adaptar o
ponto de entrada do runtime para `emscripten_set_main_loop` em vez do loop
bloqueante atual; (c) resolver gaps de GLSL ES/WebGL específicos, se algum
shader usar recurso fora do piso escolhido (WebGL 1 vs. 2); (d) decidir e
implementar persistência de save via IDBFS; (e) confirmar se algum
subsistema depende de threads reais antes de prometer suporte sem os
cabeçalhos COOP/COEP no deploy.

Isso não elimina o esforço — ainda é um port real, com pontos que só se
confirmam tentando compilar (a exploração mobile de 2026-09-09 mostrou que a
teoria e a prática divergem: dois bugs de código genuínos só apareceram ao
tentar compilar de verdade). Mas, pelos fatos levantados aqui, **Web é o
candidato de menor esforço entre Web, Android e iOS** para esta engine
especificamente, por reaproveitar mais trabalho de terceiros já maduro.

## Dependências externas a buscar

- **Emscripten SDK (emsdk)** — https://github.com/emscripten-core/emsdk
  (MIT), instala o toolchain completo (clang/LLVM alvo Wasm, portas
  SDL2/OpenAL/zlib/etc. embutidas, não precisa buscar essas libs em
  separado como no mobile).
- **Nenhuma lib nova vendorizada é necessária a priori** — SDL2, OpenAL e
  Python já têm porta oficial dentro do próprio emsdk (`-sUSE_SDL=2
  -sUSE_OPENAL=1`, mais o build `wasm32-emscripten` do CPython/Pyodide como
  peça separada a integrar).

## Ambiente de teste

Diferente de Android (que precisa de emulador/dispositivo físico) e iOS
(que precisa de Mac), Web testa localmente em qualquer navegador moderno
depois de `emcc`/`emcmake` gerar o `.html`/`.js`/`.wasm`, servido por um
HTTP server simples (`python3 -m http.server`, já disponível no ambiente do
projeto). É o alvo mais barato de iterar entre os três levantados.

## Tentativa real de build exploratório (2026-09-12)

Repetindo a metodologia usada em `mobile-export-plan.md` (exploração Android
de 2026-09-09): em vez de só levantar teoria, foi feita uma tentativa real de
configurar e buildar `RangeRuntime` sob Emscripten, para confirmar ou corrigir
as conclusões acima. Resultado: **build trava num bug genuíno do
`CMakeLists.txt`, não específico do preset** — a exploração não conclui um
`.js`/`.wasm` funcional, mas confirma a maior parte do levantamento teórico e
descobre um problema novo, aplicável também a Android.

Passos e achados, em ordem:

1. **`platform_web.cmake`** (stub, `source/build_files/cmake/platform/`) e
   dispatch `elseif(EMSCRIPTEN) include(platform_web)` em `CMakeLists.txt`,
   inserido entre `ANDROID` e `UNIX AND NOT APPLE` — confirma a previsão do
   levantamento teórico (mesmo padrão usado para `ANDROID`).
   `WITH_X11`, que antes só excluía `APPLE OR HAIKU OR ANDROID`, precisou
   excluir `EMSCRIPTEN` também (o toolchain do Emscripten define `UNIX` como
   `TRUE` por compatibilidade, o que roteava X11 incorretamente — mesma
   categoria de bug que `ANDROID` já exigiu corrigir).
2. **SDL2 confirmado reaproveitável**: `GHOST_SystemSDL`/`GHOST_WindowSDL`
   compilam sob Emscripten sem alteração, mas só depois de passar
   `-sUSE_SDL=2` como flag de **compilador** (não só linker) — o Emscripten
   intercepta `#include <SDL.h>` com um stub (`fakesdl/SDL.h`) que erra sem
   essa flag. Confirma a peça central do levantamento teórico.
3. **Bug de cascata `WITH_GLU`/`WITH_GL_PROFILE_COMPAT`**: setar
   `WITH_GLU=OFF` direto no preset não tem efeito, porque `CMakeLists.txt`
   sobrescreve `WITH_GLU` via `set()` baseado em `WITH_GL_PROFILE_COMPAT`
   (que é `ON` por padrão). Com `WITH_GLU` efetivamente `ON`, o GLEW-ES
   vendorizado (`extern/glew-es/include/GL/glew.h`) puxa typedefs de OpenGL
   ES 1.1 fixed-point (`GLfixed`, `PFNGL*XPROC`) que não existem nos headers
   GLES3/WebGL do Emscripten. Fix: setar `WITH_GL_PROFILE_COMPAT=OFF` no
   preset (não `WITH_GLU` diretamente) — isso cascata corretamente. Achado
   novo, não estava no levantamento teórico; vale nota equivalente em
   `mobile-export-plan.md`, já que o mesmo cluster de opções é usado lá.
4. **Bug genuíno, ainda sem fix, bloqueador atual**: com
   `WITH_GL_PROFILE_ES20=ON` e `WITH_SYSTEM_GLES=OFF`, `CMakeLists.txt` exige
   incondicionalmente um valor não vazio de `OPENGLES_LIBRARY`
   (`CACHE FILEPATH`) — `FATAL_ERROR` se vazio, independente do valor de
   `WITH_GL_EGL`. Esse valor é usado depois via `list(APPEND
   BLENDER_GL_LIBRARIES "${OPENGLES_LIBRARY}")`, e o gerador Ninja trata o
   resultado como **caminho de arquivo literal a ser encontrado no disco**,
   não como nome/flag de biblioteca resolvida normalmente (`"GL"` →
   `ninja: error: '.../source/GL' ... missing`; `"-lGL"` →
   `ninja: error: '.../source/-lGL' ... missing`, mesmo padrão). Sob
   Emscripten **não existe** um `libGL` real de sistema para apontar — as
   chamadas GL/GLES já vêm embutidas na própria toolchain via `-sUSE_SDL=2`/
   `-sFULL_ES3=1` etc. Ou seja: essa exigência de arquivo é incompatível com
   o alvo Web por construção, não por falta de valor certo a colocar no
   preset. **Corrigir de verdade exige mudar a lógica em `CMakeLists.txt`**
   (por exemplo, pular a exigência de `OPENGLES_LIBRARY` quando
   `EMSCRIPTEN` for verdadeiro) — mudança de código da engine, não só de
   preset, então não foi aplicada nesta exploração (que é só levantamento).

**Conclusão desta tentativa**: a maior parte do levantamento teórico se
confirmou na prática (dispatch de plataforma, reaproveitamento de SDL2,
ausência de bloqueio de Python/configure). O build não chegou a linkar
`RangeRuntime.js` por um bug genuíno e documentado na lógica de
`OPENGLES_LIBRARY` do `CMakeLists.txt`, que precisa de decisão/mudança de
código (fora do escopo de um levantamento) para ser destravado. Como
efeito colateral, essa exploração encontrou um problema que também é
relevante para a rota Android (`android-runtime` usa
`OPENGLES_EGL_LIBRARY`/`OPENGLES_gl_LIBRARY` com caminhos reais do NDK, então
não bate nesse bug ali — mas o padrão de `CACHE FILEPATH` tratado como
arquivo literal é o mesmo mecanismo).

## Perguntas em aberto (para responder depois)

- Piso gráfico: aceitar WebGL 1 (GLES 2.0, compatibilidade quase universal)
  ou exigir WebGL 2 (GLES 3.0, ~97% dos navegadores, mas fecha a porta para
  navegadores/dispositivos mais antigos)?
- O jogo/cena atual depende de threads reais em algum subsistema (física,
  streaming de asset, áudio)? Isso muda se o deploy exige ou não os
  cabeçalhos COOP/COEP.
- Save game: aceitável adotar IndexedDB (`IDBFS`) como mecanismo de
  persistência Web, com a semântica assíncrona que isso implica?
- Orçamento de memória: qual o teto de textura/geometria esperado para a
  cena real, e isso cabe confortavelmente num heap Wasm32 com
  `ALLOW_MEMORY_GROWTH`?
- Prioridade relativa a Android/iOS: Web substitui a necessidade de mobile
  no curto prazo (jogável em navegador de celular, sem precisar de APK/IPA),
  ou os dois são objetivos independentes?
- FFmpeg está desabilitado no Linux (API removida na v7); em Web,
  vídeo/cutscenes normalmente usam o elemento `<video>` do navegador em vez
  de decodificar via FFmpeg — isso é aceitável como substituição, ou o
  formato `.range` de cutscene nativo (ver `cutscene-native-integration-plan.md`)
  já resolve isso independentemente de FFmpeg?

## Segunda tentativa: build real de `RangeRuntime` (2026-09)

Depois do levantamento acima, o bug do `OPENGLES_LIBRARY` foi corrigido de
verdade em `CMakeLists.txt` (pular a exigência quando `EMSCRIPTEN` é
verdadeiro) e o build avançou bem além do ponto anterior, expondo uma série
de bugs genuínos e distintos, corrigidos um a um:

1. `CMAKE_CROSSCOMPILING_EMULATOR` ausente para rodar geradores de dados
   (datatoc/makesdna/makesrna) cross-compilados — precisa apontar para `node`.
2. `NODERAWFS` necessário para esses geradores lerem/escreverem arquivos reais
   durante o build (não só memória virtual do wasm).
3. `WITH_MOD_FLUID`/`WITH_MOD_SMOKE`/`WITH_FFTW3`/`WITH_MOD_OCEANSIM`
   desabilitados — dependem de libs nativas sem porta Emscripten viável no
   momento.
4. `extern/glew-es/src/glew.c`: guardas de GLX ausentes para Emscripten em 6
   pontos — adicionado `#if !defined(__EMSCRIPTEN__)` ao redor de código GLX.
5. `LEGACY_GL_EMULATION=1` habilitado via flag do Emscripten (`-s`) para
   suprir chamadas `glBegin`/`GL_QUADS` de OpenGL fixo usadas pelo engine.
6. Portas oficiais do Emscripten ativadas: `-sUSE_ZLIB=1 -sUSE_FREETYPE=1`.
7. `source/blender/blenlib/intern/storage.c`: `statvfs` só existe em alguns
   unixes — adicionado `__EMSCRIPTEN__` ao guard `USE_STATFS_STATVFS`.
8. `-Wno-sign-conversion` adicionado às flags do Emscripten para tolerar
   conversões de sinal que o toolchain do sistema não reclamava.
9. `WITH_GL_PROFILE_COMPAT=ON` reativado (necessário para declarações de GL
   legado/`glBegin` que `GLEW_ES_ONLY` removia).
10. Bug de interação genuíno entre os itens 5 e 9: com
    `WITH_GL_PROFILE_ES20` **e** `WITH_GL_PROFILE_COMPAT` juntos (combinação
    nunca exercida antes nesta fork), a lógica de "eliminar símbolos ES1"
    do `CMakeLists.txt` (linha ~1353, `-DGL_ES_VERSION_1_0=0 ...`) suprime
    typedefs (`GLfixed`, `PFNGL*XPROC`) que outras seções do mesmo
    `glew.h` ainda referenciam sem depender desse define. Fix: essas defines
    só são aplicadas quando `NOT (WITH_GL_PROFILE_CORE OR
    WITH_GL_PROFILE_COMPAT)`, replicando o padrão já usado para
    `GLEW_ES_ONLY` no mesmo bloco.
11. `source/blender/blenlib/BLI_strict_flags.h`: os `#pragma GCC diagnostic
    error "-Wsign-conversion"` (e afins) são incondicionais para qualquer
    compilador que reporte `__GNUC__` — o clang do Emscripten reporta, então
    esses pragmas sobrescreviam o `-Wno-sign-conversion` da linha de comando
    e quebravam `string_utf8.c`/`MOD_solidify.c`. Fix: todo o bloco agora é
    pulado também quando `__EMSCRIPTEN__` está definido.
12. `source/blender/gpu/intern/gpu_shader.c`: usa `GLEW_VERSION_4_3/4_4/4_5`
    sem guarda, mas esse fork do glew-es só declara até `GLEW_VERSION_4_2`
    (não existe `GL_VERSION_4_3+` nos headers vendorizados) — identificador
    não declarado. Fix: envolvidas em `#ifdef GL_VERSION_4_x` antes de cada
    checagem.

### Bloqueio atual (real, arquitetural — não um bug pontual)

Com os fixes acima, o build avança até compilar módulos do
`gameengine` (`ge_ketsji`, `ge_expressions`, `ge_converter`, etc.) e falha em
massa porque:

- O game engine usa a API do Python (`PyObject`, `PyImport_ImportModule`,
  etc.) **incondicionalmente** em dezenas de arquivos (`KX_AnimationEvent.cpp`,
  `EXP_PythonCallBack.h`, `KX_ChangeColorActuator.h`, `KX_PythonJoystick.h`,
  entre outros) — não há guardas `#ifdef WITH_PYTHON`. O preset Web atual usa
  `WITH_PYTHON=OFF` (assim como Android/iOS), o que quebra a compilação do
  BGE inteiro, não só de features isoladas.
- Também apareceram, no mesmo lote: `boost/format.hpp` e `tbb/tbb.h` não
  encontrados (Boost/TBB não portados para este alvo Emscripten), e faltam
  `jpeglib.h`/`png.h`/`openjpeg.h`/`tiffio.h` (codecs de imagem que `imbuf`
  usa sem gate de `WITH_IMAGE_*` em `jpeg.c`/`png.c`/`jp2.c`/`tiff.c`) — ainda
  não investigados a fundo porque o bloqueio do Python é anterior na ordem
  de build e é estruturalmente maior.

**Decisão tomada com o usuário**: como o `docs/web-export-plan.md` já previa
(seção "Python embarcado" acima), a rota correta é **não** tentar arrancar o
Python do game engine (reescrever dezenas de arquivos, alto risco de quebrar
lógica de jogo via script), e sim **cross-compilar CPython 3.11 para o alvo
`wasm32-emscripten`** e ligar com `WITH_PYTHON=ON`. Isso é um sub-projeto à
parte (não existe build pré-compilado disponível no `emsdk` nem no
repositório — confirmado por busca em `extern/` e `emsdk/`), com escopo de
dias, não um fix pontual dentro do ciclo atual. **Pausado aqui por decisão
explícita do usuário** — não iniciado. Próximo passo, quando retomado: seguir
o suporte oficial `Tools/wasm/emscripten` do próprio CPython 3.11+ para gerar
`libpython3.11.a` + headers, depois apontar `PYTHON_LIBRARY`/
`PYTHON_INCLUDE_DIR` no preset `web-runtime` e retomar o ciclo de build.

### Retomada: ambiente de build para CPython wasm (2026-09-12)

Decisão do usuário: retomar o cross-compile de CPython 3.11 para
`wasm32-emscripten`, usando a automação oficial `Tools/wasm/wasm_build.py`
do próprio CPython. Essa ferramenta assume um ambiente POSIX
(`./configure && make`) e não roda nativamente em PowerShell/Git Bash no
Windows.

- **Ambiente escolhido**: WSL2 com Ubuntu, já presente na máquina (não
  precisou de instalação nova — uma tentativa de `wsl --install -d Ubuntu`
  retornou `ERROR_ALREADY_EXISTS`, revelando que a distro já existia).
- **Realocação para o drive D:** por pedido explícito do usuário (mais
  espaço livre), a distro foi movida de C: para `D:\WSL\Ubuntu` via
  `wsl --shutdown` seguido de `wsl --manage Ubuntu --move D:\WSL\Ubuntu`
  (comando de gerência do WSL 2.6.1.0, evita export/import manual).
  Verificado após a mudança: `wsl --list --verbose` mostra a distro em
  versão 2, e `df -h` dentro dela confirma o filesystem montado a partir de
  D:.
- **Dependências de build** (build-essential, git, python3.11 +
  dev/venv, pkg-config, zlib1g-dev, libffi-dev, cmake) instaladas via
  `apt-get` dentro da distro.
- **Pendente**: configurar um emsdk nativo Linux dentro do WSL (o
  `D:\emsdk` existente é uma instalação Windows, cujos binários ativados não
  rodam a partir do ambiente Linux do WSL), clonar CPython 3.11 e rodar
  `Tools/wasm/wasm_build.py` para gerar `libpython3.11.a` + headers para
  `wasm32-emscripten`.
