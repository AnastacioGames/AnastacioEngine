# Plano — Export para celular (Android/iOS)

## Objetivo

Levantar o estado atual da engine em relação a portabilidade mobile e traçar o
caminho depois que o export Linux (`RangeRuntime`, ver `docs/linux-build.md`)
estiver fechado e validado em hardware nativo. Este documento é um
**levantamento + plano preliminar**, não uma decisão de implementação. Nenhum
código foi alterado para produzi-lo.

## Por que depois do Linux

Android usa toolchain baseada em Linux (NDK/clang) e o mesmo modelo POSIX de
sistema de arquivos, threads e sockets. O trabalho de portabilidade que o
export Linux já força — remover dependências Win32-only, separar
`RangeRuntime` (player) de `RangeEngine` (editor), lib set próprio, Python
isolado — é diretamente reaproveitável como base para Android. iOS herda menos
disso (toolchain Xcode/Clang própria, EAGL/Metal em vez de EGL/GLX), mas o
princípio de "player sem editor, gráfica portátil" continua valendo.

## Levantamento do estado atual

### 1. GHOST (camada de janela/plataforma)

Backends existentes em `source/intern/ghost/intern/`: Win32, X11, SDL2
(genérico, via `WITH_GHOST_SDL`), Cocoa (macOS), NULL (headless).

**Não existe backend Android nem iOS.** Sem `GHOST_SystemAndroid`, sem
`GHOST_WindowAndroid`, sem equivalente iOS. As únicas ocorrências de
`ANDROID`/`IOS` no grep são de libs vendorizadas de terceiros (SDL2, glew,
gtest, glog, Eigen), não código próprio.

Ponto positivo: `GHOST_ContextEGL.cpp/.h` já existe e já sabe pedir contexto
**OpenGL ES** (`EGL_OPENGL_ES_BIT`/`ES2_BIT`/`ES3_BIT_KHR`, linhas ~408-422).
Isso adianta a parte de negociação de contexto ES, mas falta toda a ponte
`ANativeWindow` → superfície EGL (não existe hoje). iOS não usa EGL — usa
EAGL/Metal — então esse ganho não vale para iOS.

### 2. Build system (CMake)

`source/CMakeLists.txt` só reconhece três ramos de plataforma: `UNIX AND NOT
APPLE`, `APPLE`, e o resto implícito como `WIN32`. Nenhuma variável `ANDROID`
ou `IOS` existe no projeto.

`source/build_files/cmake/platform/` só tem arquivos para apple, unix, win32
— **não há `platform_android.cmake`, `platform_ios.cmake`, nem qualquer
toolchain file de NDK**. Essa parte seria construída do zero.

Já existe infraestrutura relevante, ainda que não pensada para mobile:
- `WITH_GLEW_ES`, `WITH_GL_EGL`, `WITH_GL_PROFILE_ES20` — opções já presentes
  em `source/CMakeLists.txt` (linhas ~515-527), marcadas como experimentais.
- `source/extern/glew-es/` — GLEW variante ES/EGL já vendorizada
  (`eglew.h`, `glesew.h`).
- `WITH_GL_PROFILE_CORE_RANGERUNTIME` — opção nova, criada para a migração
  Core Profile do player (ver item 4), que já isola o rasterizer/gpu do resto
  do build. É o mesmo padrão de escopo que um build ES para mobile precisaria.
- O export Linux já usa CMakePresets (`linux-runtime`), então adicionar
  `android-runtime`/`ios-runtime` como presets futuros é natural.

### 3. Input

Abstração em `source/source/gameengine/Device/` (`DEV_InputDevice`,
`DEV_Joystick*`) e `GameLogic/` (`SCA_IInputDevice`, `SCA_MouseSensor`,
`SCA_KeyboardSensor`, `SCA_JoystickSensor`).

**Não existe conceito de touch.** As únicas ocorrências de "touch" no código
são o sensor de colisão física (`KX_CollisionSensor`, `ST_TOUCH`) — objetos se
tocando, não touchscreen. Não há `SCA_TouchSensor`, não há mapeamento
touch→mouse, e o `GHOST_EventTrackpad` existente é gesto de trackpad desktop,
não touchscreen mobile. Um path de input novo teria que ser criado sob
`SCA_IInputDevice`.

### 4. Rasterizer / OpenGL

Estado hoje: o rasterizer do jogo (`RAS_OpenGLRasterizer`) roda em **OpenGL
2.1 compatibility profile por padrão** (`WITH_GL_PROFILE_COMPAT=ON`,
`WITH_GL_PROFILE_CORE=OFF`), mesmo em GPU que suporta 4.6 — confirmado em log
de teste real (RTX 5060 relatando suporte a 4.6 mas engine usando 2.1).

**Achado mais relevante do levantamento:** existe uma migração recente e
concluída para **OpenGL Core Profile**, documentada em várias entradas do
`docs/changelog.md` ("Migração para OpenGL Core Profile — Fase N"), escopo
limitado a `RangeRuntime` (35 call sites em 4 arquivos: `RAS_OpenGLRasterizer.cpp`,
`RAS_OpenGLLight.cpp`, `RAS_OpenGLDebugDraw.cpp`, `RAS_StorageVao.cpp`). O
editor (`source/blender/editors/`, ~3589 call sites fixed-function em 73
arquivos) ficou de fora, deliberadamente.

Trabalho já feito nessa migração que **também é o caminho para ES 3.0**
(ambos removem fixed-function/immediate-mode e exigem GLSL versionado com
atributos explícitos):
- Matrix stack (`glPushMatrix` etc.) convertido para uniforms rastreados na CPU.
- Estado de material/luz fixed-function (`glMaterialfv`, `glFog*`,
  `glShadeModel`) confirmado morto sob GLSL e neutralizado sob CORE.
- Desenho imediato (`glBegin(GL_QUADS)`) em `gpu_framebuffer.c` reescrito para
  VBO+VAO.
- Shaders migrados para `#version 330 core`.

Gaps conhecidos e não resolvidos (documentados no próprio changelog):
- `glClipPlane` (clip planes) sem equivalente em core profile — precisaria de
  `gl_ClipDistance[]` escrito no vertex shader.
- Motion blur via `glAccum` (accumulation buffer) — removido do core profile,
  sem substituto direto; precisaria de passe de velocity buffer.
- Fallback de `gl_LightSource[]` em `gpu_shader_material.glsl`
  (`node_bsdf_diffuse`/`glossy`/`principled`) desabilitado sob CORE, deixado
  como fallback só-ambiente — gap conhecido, não corrigido.

Gap adicional específico de ES (fora do que a migração Core já cobriu):
sintaxe/precision qualifiers de GLSL ES vs. GLSL desktop, e criação de
contexto/surface EGL no SO alvo (item 1).

### 5. Áudio

`source/intern/audaspace/` com backend OpenAL (`WITH_OPENAL`, padrão ON).
Testado e confirmado funcional no Linux (WSLg) — OpenAL Soft inicializa,
cria contexto, sem erro (só a rota de áudio do WSLg para o Windows host era
suspeita, não a engine). OpenAL Soft tem suporte comunitário para Android
(OpenSL ES/AAudio) e iOS (CoreAudio/AVAudioEngine), mas **nenhum desses
backends está selecionado ou cross-compilado no CMake deste repositório
hoje** — precisaria ser construído por plataforma.

### 6. Python embarcado

Versão fixada por plataforma nos arquivos de CMake, não é uma constante
única do projeto:
- Windows: 3.11 (`platform_win32.cmake`)
- macOS: 3.10.2 (`platform_apple.cmake`)
- Linux (export atual): 3.11, isolado em `/opt/anastacio-python311`,
  "compilado separadamente para manter a ABI esperada pela engine"
  (`docs/distribution-0.1.md`/`docs/linux-build.md`)

Android e iOS vão precisar, cada um, de um CPython cross-compilado próprio
(3.10/3.11) com ABI compatível. Isso é conhecido do usuário, só registrado
aqui como confirmação factual.

### 7. Física

Bullet 2.84 (`source/extern/bullet2`), integrado em
`source/source/gameengine/Physics/Bullet/`. Bullet 2.x é portável e tem
suporte upstream de longa data para Android/iOS — não é esperado ser um
bloqueio.

### 8. Docs existentes / alinhamento com o export Linux

Nenhum doc em `docs/` menciona Android ou iOS hoje. Docs relevantes para
alinhar o plano mobile:

- **`docs/linux-build.md`** (2026-09-08) — runbook em andamento. Estado
  atual: `RangeRuntime` (só player) linka e roda no Debian 13 via WSL/WSLg,
  abre janela X11/WSLg real, cria contexto OpenGL 4.5 (Mesa/llvmpipe software
  render), carrega e roda um `.range` real (`RolimaRacer.range`) de forma
  estável por minutos. Ainda não validado: GPU nativa Linux (só testado via
  software render), áudio audível (init OK, saída não confirmada), um bug
  visual de alpha reportado e não investigado. Escopo do build Linux: só
  player, com OpenGL/X11/Python/SDL/OpenAL; FFmpeg desabilitado (usa API
  removida do FFmpeg 7, precisa de migração própria); editor, Cycles e
  compositor desabilitados. Usa preset CMake `linux-runtime` e lib set
  próprio (não `lib/win64_vc15`). Status oficial declarado no doc: "Linux
  x86_64: experimental, sem build oficial."
- **`docs/distribution-0.1.md`** — convenção de empacotamento Windows (ZIP
  portátil, redistribuível VC++, `SHA256SUMS.txt`) que o Linux já espelha
  (`package-runtime.sh` → `.tar.xz` + `.sha256`) e que um empacotamento mobile
  futuro (APK/IPA) deveria seguir na mesma lógica de processo, mesmo que o
  formato final seja diferente.
- **`docs/roadmap.md`** — fluxo Windows/Linux x86_64 dado como concluído e
  documentado; falta validar Linux em hardware nativo (fora WSL). Nenhum item
  mobile ainda.
- **`docs/changelog.md`** — contém o histórico completo da migração Core
  Profile (item 4 acima), a peça de engenharia mais relevante para mobile já
  concluída no repo, mesmo sem ter sido feita pensando em mobile.

## Conclusão do levantamento

O gap gráfico é menor do que pareceria à primeira vista: a migração Core
Profile do `RangeRuntime` já fez o trabalho estrutural mais pesado (remover
fixed-function, versionar shaders, isolar o build do rasterizer via
`WITH_GL_PROFILE_CORE_RANGERUNTIME`) e o GHOST já sabe negociar contexto ES
via EGL. O que falta para mobile é, na prática, trabalho novo e não incremental
em três frentes que hoje não existem em nenhum grau:

1. **Plataforma/janela**: backend GHOST Android (ANativeWindow→EGL) e backend
   iOS (EAGL/Metal) do zero.
2. **Toolchain de build**: CMake para NDK (Android) e Xcode/`ios.toolchain`
   (iOS) do zero, incluindo cross-compile de Python, OpenAL Soft, Bullet
   (esse último provavelmente já compila sem problema) para cada plataforma.
3. **Input touch**: abstração nova sob `SCA_IInputDevice`, mais adaptação da
   lógica de jogo/menus para tocar em vez de clicar (os menus que o Codex está
   implementando agora deveriam já considerar isso, ver perguntas abaixo).

Áudio e física são as frentes de menor risco (bibliotecas já portáveis, só
falta a integração de build).

## Dependências externas a buscar

A maior parte de `source/extern` (Bullet, Eigen, cjson, imgui, audaspace,
recastnavigation) é fonte C/C++ portável e compila para ARM sem troca. Só
estas peças dependem de binário/toolchain específico de plataforma e
precisam ser buscadas/compiladas à parte:

- **Python cross-compilado (Android/iOS)**: não é um download solto, é um
  passo de build. Usar `python-for-android` (kivy, MIT) para Android ou
  `BeeWare/Python-Apple-support` (BSD, já entrega builds prontos) para iOS,
  na mesma versão usada no Linux (CPython 3.11) para manter ABI.
- **SDL2 completo**: o que existe hoje em `source/extern/sdlew` é só um stub
  loader, não a lib inteira. Baixar a fonte completa de
  https://github.com/libsdl-org/SDL (zlib license) — já tem backend Android
  (`SDL_androidvideo`) e iOS (`SDL_uikitvideo`) prontos upstream. Candidato
  natural para servir de base a um futuro `GHOST_SystemSDL` mobile em vez de
  escrever `GHOST_SystemAndroid`/iOS do zero.
- **OpenAL Soft com backend mobile**: https://github.com/kcat/openal-soft
  (LGPL — atenção à forma de linkagem, dinâmica é mais segura para manter a
  separação de licença), compilado com backend OpenSL ES/AAudio (Android) ou
  CoreAudio (iOS).
- **Android NDK** (Google) e **Xcode + iOS SDK** (Apple, exige Mac) — não são
  libs, são as toolchains necessárias para compilar tudo acima para ARM.

## Ambiente de teste no PC

Enquanto a base mobile não existe, dá para continuar testando no Windows/VS
com as mesmas libs, via **vcpkg** (Microsoft, MIT) — mais fácil que caçar
binário solto:

```powershell
git clone https://github.com/microsoft/vcpkg
.\vcpkg\bootstrap-vcpkg.bat
.\vcpkg\vcpkg install sdl2:x64-windows openal-soft:x64-windows
```

Integra com CMake via
`-DCMAKE_TOOLCHAIN_FILE=<vcpkg>/scripts/buildsystems/vcpkg.cmake` num preset
novo. **Não instalar `bullet3` pelo vcpkg** — o projeto já vendoriza Bullet
2.84 em `source/extern/bullet2`; misturar as duas versões causaria conflito.

Isso testa a lib em si (compila/linka/roda no PC), mas **não** testa
comportamento mobile de verdade (touch, EGL, tela pequena). Para isso, depois
que o backend Android existir:

- **Android Studio + emulador** — roda o APK final num Android virtual no
  PC, sem precisar de celular físico. É o teste mais fiel disponível sem
  hardware.
- iOS não tem emulador equivalente fora do Mac (só Simulator, que roda
  dentro do Xcode) — reforça a pergunta em aberto sobre precisar de um Mac.

## Levantamento prático: primeira tentativa real de build Android (2026-09-09)

Sessão de teste exploratório, só para ver até onde o build vai — não é
implementação de suporte Android, é levantamento de informação. Preset
`android-runtime` em `source/CMakePresets.json` (NDK r30, arm64-v8a,
`android-24`), toolchain `android.toolchain.cmake` do NDK.

### Configure (CMake) — chegou a 100%, todos os bloqueios contornados

Cinco bloqueios encontrados e contornados, um a um, só com flags de preset e
dois ajustes pequenos de detecção de plataforma em `source/CMakeLists.txt`:

1. **X11 forçado em qualquer `UNIX`** — `set(WITH_X11 ON)` disparava mesmo
   para Android (a toolchain do NDK também define `UNIX=TRUE`). Corrigido
   excluindo `ANDROID` da condição (`if(UNIX AND NOT (APPLE OR HAIKU OR
   ANDROID))`, linha ~211-213).
2. **`platform_unix.cmake` inclusa para Android** — esse arquivo assume Linux
   desktop com JPEG/PNG/ZLIB/Freetype/TBB instalados no sistema, nenhum dos
   quais existe/faz sentido para cross-compile Android. Corrigido criando
   `source/build_files/cmake/platform/platform_android.cmake` — **stub vazio
   e deliberadamente não-funcional**, só para rotear `ANDROID` para um
   arquivo próprio em vez de reusar o do Linux (dispatch em
   `CMakeLists.txt` ~983-989, `if(ANDROID) include(platform_android)
   elseif(...)`). Esse stub fica no repo como ponto de partida real para um
   futuro `platform_android.cmake` funcional.
3. **`find_package_wrapper` undefined** — macro só existe dentro de
   `platform_unix.cmake`, quebrou quando `WITH_SYSTEM_GLES` tentou chamá-la.
   Contornado com `WITH_SYSTEM_GLES=OFF` no preset.
4. **EGL/GLES/OpenGL include dir não encontrados** — contornado apontando
   `OPENGLES_EGL_LIBRARY`/`OPENGLES_gl_LIBRARY` para as libs-stub que o
   próprio NDK já vendoriza (`libEGL.so`/`libGLESv2.so` em
   `<ndk>/toolchains/llvm/prebuilt/windows-x86_64/sysroot/usr/lib/aarch64-linux-android/24/`,
   presentes de API 21 a 30) e `OPENGL_INCLUDE_DIR` para o sysroot do NDK.
5. **Python headers ausentes** — esperado, não existe CPython cross-compilado
   para Android no repo (ver item 6 acima). Contornado com `WITH_PYTHON=OFF`.

Resultado: `cmake --preset android-runtime` termina com "Configure done —
Generate done" completo. Isso confirma que a arquitetura de CMake do projeto
consegue reconhecer Android como plataforma com pouca cirurgia — o grosso do
trabalho real não está no CMake.

### Build real (compilação) — bloqueado em incompatibilidades genuínas de código-fonte

Ao rodar `cmake --build --target RangeRuntime`, a compilação chega a
processar boa parte dos ~1742 alvos (vários `.c`/`.cpp` de `blenlib`,
`makesdna`, GHOST compilam limpo sob o Clang do NDK) antes de falhar em dois
pontos que já são **código-fonte real**, não configuração:

- `intern/guardedalloc/intern/mallocn_lockfree_impl.c:458` e
  `mallocn_guarded_impl.c` — chamam `malloc_stats()`, função de glibc que
  **não existe na Bionic** (libc do Android). Falha sob
  `-Werror=implicit-function-declaration`.
- `intern/ghost/intern/GHOST_Context.cpp` / `GHOST_ContextNone.cpp` — `fatal
  error: 'GL/glu.h' file not found`. Cadeia: `GHOST_Context.h` →
  `intern/glew-mx/glew-mx.h:50` → `extern/glew-es/include/GL/glew.h:1193`
  (`#include <GL/glu.h>`), puxado porque `WITH_GLU` está ON por herança do
  desktop. GLU não tem equivalente Android nem está vendorizado no repo.

Esses dois já não são mais "faltou configurar", são linhas de `.c`/`.cpp`
que precisariam de `#ifdef ANDROID`/patch real — e a partir daqui a lista só
tende a crescer (GHOST ainda não tem backend de janela Android nenhum, então
mesmo resolvendo esses dois, o próximo bloqueio previsível é exatamente a
ausência de `GHOST_SystemAndroid`/`GHOST_WindowAndroid` descrita no item 1).

### Conclusão desta rodada

Confirma o que a análise estática já apontava: o gap real de Android não é
CMake (isso agora está provado navegável em poucas horas), é trabalho de
portabilidade em código C/C++ do engine — guardedalloc, GHOST, e
provavelmente mais adiante. Ficam registrados no repo, como artefato
reaproveitável desse levantamento:

- `source/CMakePresets.json` → preset `android-runtime` funcional até o
  ponto do configure.
- `source/build_files/cmake/platform/platform_android.cmake` → stub vazio,
  ponto de partida.
- Dois ajustes de detecção de plataforma em `source/CMakeLists.txt` (item 1
  acima) — mudança de infraestrutura de build, não toca em gameplay/menu.

## Perguntas em aberto (para responder depois)

- Prioridade entre Android e iOS primeiro, ou os dois em paralelo? (iOS exige
  Mac + Xcode para compilar/assinar — isso muda o plano de infraestrutura.)
- O escopo mobile deve replicar o escopo Linux (só `RangeRuntime`, sem
  editor), ou há necessidade de rodar o editor em tablet em algum cenário?
- Motion blur e clip planes (gaps já conhecidos do Core Profile) são
  features usadas no jogo atual? Se não, não bloqueiam o port; se sim, entram
  no escopo mobile também.
- Os menus que o Codex está implementando agora já preveem estados de
  foco/hover pensados para touch (sem depender de hover de mouse), ou vão
  precisar de revisão quando o input touch existir?
- Existe orçamento/plano para dispositivo de teste físico Android e Mac com
  Xcode, ou o teste inicial seria só em emulador/simulador?
- Distribuição: Google Play / App Store formal, ou instalação direta
  (APK sideload / TestFlight) por enquanto?
- Nível mínimo de hardware alvo (isso define se OpenGL ES 3.0 é aceitável
  como piso ou se precisa suportar ES 2.0 também, o que reabriria parte do
  trabalho de shader).
- FFmpeg está desabilitado no Linux por usar API removida na v7 — isso afeta
  vídeo/cutscenes no mobile também, ou esse caminho já é dispensável lá?
