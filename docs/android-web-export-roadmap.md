# Roadmap — Export para Web e Android

> **Revisão de 2026-09-20:** a sequência Android vigente está em
> [android-export-plan.md](android-export-plan.md): provar um APK WebView mínimo no aparelho real antes do
> exportador/editor. As fases Android nativas abaixo são referência histórica da trilha NDK congelada;
> a validação Web desktop não comprova suporte Android.

## Contexto de sequência

Neste momento, `RangeRuntime` já roda em:
- **Windows x86_64** (nativo, validado)
- **Linux x86_64** (nativo, validado em 2026-09-15 em notebook com GPU NVIDIA real)

A validação Linux ajuda diretamente os exports Web/Android por três motivos:

1. **Portabilidade real do runtime**: a engine já saiu do eixo Windows/MSVC e roda em um toolchain Unix real
   com GCC/ld, RPATH, bibliotecas de sistema e GPU dedicada. Isso reduz o risco de bugs escondidos por
   pressupostos Windows antes de chegar no Emscripten/NDK.
2. **Dependências isoladas por plataforma**: o Python 3.11 isolado em `/opt/anastacio-python311`, o fix de
   RPATH e a seleção de bibliotecas de sistema validam o mesmo modelo que Web e Android precisam: um
   runtime empacotado com ABI controlada, sem depender do Python do sistema do usuário.
3. **Pipeline de distribuição Unix**: `build-linux/bin/` e `tools/linux/package-runtime.sh` são um protótipo
   prático para empacotar runtimes não-Windows. Web troca isso por HTML/JS/WASM; Android troca por APK/AAB,
   mas o princípio de "runtime instalado + assets do jogo + manifesto" é o mesmo.

Web e Android compartilham a migração do Core Profile do rasterizer (concluída), o preset CMake
(`CMakePresets.json`) e a maioria da lógica de link. As diferenças são de contexto de execução
(Emscripten vs. NDK), janela/input, ciclo de vida da aplicação e especificidades de toolchain.

## Web: estado atual (2026-09-14)

O runtime **já inicializa, carrega a cena e executa frames**. Console limpo de erros WebGL e Python funcionando.

### Progresso consolidado

#### 1. Build completo fecha limpo
- `platform_web.cmake` criado e roteado
- Dual-toolchain (ferramentas nativas + wasm) resolvido
- CPython 3.11 cross-compilado para `wasm32-emscripten`
- Todas as dependências linkadas (Boost, TBB, GLEW, GL emulation shims)
- Build exit 0 com `RangeRuntime.js`/`RangeRuntime.wasm` gerados

#### 2. Pipeline de renderização navegável
- GPU queries adaptadas
- Shader `gpu_shader_material.glsl` compila sem erros GLSL ES (130+ conversões de tipo int/float)
- Framebuffers/textures com formato WebGL2/GLES3 válido
- Materiais reconhecidos desativam/restauram draw buffers corretamente
- Filtros 2D nativo (FXAA, Rain, Clouds, LensFlare, Tonemap, SSAO, Bloom, SSR, etc.) ligados
- Divisores de atributo/quad de tela salvos/restaurados para Web
- 6.192 draws confirmados sem erro GL em teste automatizado

#### 3. Input funcionando em navegador real
- Teclado e mouse: mapeamento de eventos SDL → GHOST → Python validado
- Joystick/gamepad: eixos analógicos (D-pad/stick) sem travamento
- Confirmado visualmente pelo usuário: cubo controlável por setas no navegador (`test-smoke.html`, 2026-09-14)
- Python `keyboard.events`/`mouse.events` prioritizam `JUSTACTIVATED` para não perder toques instantâneos

#### 4. Persistência de save
- IndexedDB via IDBFS: `bge.logic.saveGlobalDict()`/`loadGlobalDict()` implementados
- Sincronização automática no boot e após escrita
- Smoke test funcional pendente (salvar → reload → confirmação visual)

#### 5. Filtros 2D — validação de 15 efeitos
- Teclado binding (1-0/Q para 11 filtros simples, W/E/R/T para built-in): todos ativados sem erro de shader
- Bugs de GLSL ES corrigidos: `RAS_SSAO2DFilter.glsl`, `RAS_OutLine2DFilter.glsl`, `RAS_Bloom2DFilter_bufH/V.glsl`, `RAS_LightScattering_Buffer2DFilter.glsl`, `RAS_SSR2DFilter.glsl`, `RAS_SSR_Blur2DFilter.glsl`
- Aceite visual do usuário pendente (testes automatizados confirmam execução, não aparência)

### Próximas etapas — Web

**Curto prazo (bloqueadores finais de validação visual)**

1. **Aceite visual do cubo renderizado** — cubo real no canvas, iluminação correta, movimento via Python/input
   - Chrome headless com CDP mostrava console limpo mas sem objetos — precisa validação em navegador real
   - Status: 6.222 draws confirmados sem erro GL, mas ainda sem confirmação visual do usuário na cena

2. **Aceite visual de filtros 2D** — cada um dos 15 efeitos visualmente correto
   - Smoke test automatizado confirma 0 erros de shader após keyboard binding
   - Aceite visual pendente

3. **Smoke test de persistência** (save/load)
   - IDBFS implementado, nenhuma cena local testa ainda
   - Criar cena mínima que salva → reload página → confirma persistência

4. **Documentação de deploy**
   - Headers COOP/COEP se SharedArrayBuffer for necessário (pthreads)
   - Decisão de WebGL 1 vs. WebGL 2 como piso mínimo
   - Padrão de distribuição (tar.xz com HTML harness + `RangeRuntime.js`/`.wasm`)

**Médio prazo (recursos opcionais, baixa prioridade)**

- CSM (Cascade Shadow Maps) — decidir se é GLES 3 only (WebGL 2 obrigatório) ou reaproveitar fallback de GLES 2
- Suporte a pthreads/threads reais (hoje desativado na PoC, pode ser necessário para engine_sync.cpp)
- Touch input (se mobile no navegador for alvo futuro)

### Limitações conhecidas de Web

- Gamepad: patch SDL2 do emsdk versionado em `tools/web/patch-sdl2-gamepad.py` (aplicação manual, ver roadmap)
- GLSL ES precision: alguns shaders usam `precision mediump` hardcoded, pode gerar truncamento em GPUs fracas
- Memory: `FS.syncfs()` é síncrono, em cenas grandes pode congelar o navegador

---

## Android: estado atual (2026-09-09)

Levantamento exploratório concluído. **Nenhum código alterado para Android até o momento** — o preset existe, mas falha antes de atingir qualquer backend GHOST (missing `malloc_stats` na Bionic, `GL/glu.h` no NDK).

### Levantamento do estado

Detalhado em [`mobile-export-plan.md`](mobile-export-plan.md); resumo:

#### Infraestrutura reaproveitável
1. **OpenGL ES caminho**: Core Profile já feito (`RangeRuntime`, 35 call sites)
2. **CMake preset**: `android-runtime` já existe em `CMakePresets.json` (linhas 109-154)
3. **EGL context**: `GHOST_ContextEGL.cpp` já sabe pedir contexto ES
4. **Input/janela base**: SDL2 tem suporte nativo Android (pode reaproveitar `GHOST_SystemSDL`)
5. **Física**: Bullet 2.84 portável, upstream Android-ready
6. **Áudio**: OpenAL com backends Android/iOS, falta seleção/cross-compile

#### Gaps genuínos a resolver
1. **Backend GHOST Android** — novo, não existe hoje
   - Windows/X11/Cocoa/SDL2 existem; Android não
   - Padrão atual: `GHOST_System*` + `GHOST_Window*` + display manager
   - Android exige `ANativeWindow` → EGL surface — já parcialmente coberto por `GHOST_ContextEGL`

2. **Input touch** — não existe conceito de touchscreen (`SCA_TouchSensor` não existe)
   - Teclado/mouse/joystick já mapeados
   - Touch seria um tipo novo de `SCA_IInputDevice` ou mapeamento touch→mouse

3. **CPython 3.11 cross-compilado** — precisa ser construído por NDK
   - O fluxo Linux validou o padrão de Python isolado fora do sistema; Android deve repetir a ideia com
     prefixo próprio gerado pelo NDK, não com Python do host
   - Android segue o mesmo padrão, com uma etapa de `configure --host=aarch64-linux-android`

4. **Binário final** — APK ou SO dentro de APK
   - `RangeRuntime.so` compilado, mas precisa de scaffolding Java/Kotlin
   - Padrão atual: C-only, sem interface Android nativa

### Diferenças entre Web e Android

| Aspecto | Web (Emscripten) | Android (NDK) |
|---------|---|---|
| **Plataforma** | JavaScript/WASM | ARM64 ELF SO |
| **Janela** | SDL2 → Canvas | SDL2 → ANativeWindow (novo backend) |
| **Loop principal** | `emscripten_set_main_loop()` | Loop bloqueante normal, pausável por lifecyle Android |
| **Python** | Emscripten toolchain nativo | Cross-compile com sysroot NDK |
| **Áudio** | OpenAL Soft (Emscripten stub) | OpenAL Soft com backend OpenSL ES ou AAudio |
| **Persistência** | IndexedDB | `/data/data/<app>/files/` via VFS |
| **Networking** | CORS + WebSocket | TCP/UDP nativo |
| **GPU** | WebGL 2 (GLES 3) | GLES 3.0+ (hardware real) |
| **Toolchain** | emsdk | NDK r30+ |
| **Pré-requisito** | Emscripten 6.0.9+ | Android SDK/NDK, gradle |

---

## Compartilhado entre Web e Android

### Build system
- Ambos usam CMakePresets (`web-runtime` e `android-runtime` já existem)
- Dispatch `EMSCRIPTEN` e `ANDROID` em `CMakeLists.txt`
- `platform_web.cmake` e `platform_android.cmake` necessários (web já feito, android em stub)
- A validação Linux mostrou que os presets por plataforma precisam controlar RPATH, libs de sistema e
  recursos desligados por incompatibilidade de API, em vez de assumir o conjunto Windows.

### Gráficos
- GLSL ES/WebGL 2 = GLES 3.0 — mesma migração Core Profile
- Shaders já compilam limpo para WebGL 2 (GLSL ES 3.00, 130+ fixes)
- Mesmos framebuffers/textures com formato compatível
- Mesmos filtros 2D para ambas as plataformas

### Input
- Teclado/mouse mapeados (Web já validado; Android reutiliza)
- Joystick/gamepad via SDL2 (Web validado; Android herdaria)
- Touch futuro seria separado, mas teclado+mouse já funcionam

### Python embarcado
- Mesma versão (3.11 isolada)
- Diferentes toolchains: Emscripten vs. NDK cross-compile
- Mesmos imports e API do game engine
- Lição do Linux: tratar o Python como parte do runtime empacotado, com ABI e caminho previsíveis.

### Áudio
- OpenAL Soft base para ambos
- Diferentes backends: Web tem stub/Emscripten, Android tem OpenSL ES (não implementado)

---

## Roadmap combinado — próximos passos

### Fase 1: Finalizar e liberar Web (2-3 semanas)
**Pré-requisito para Android: validação visual de Web prova que o pipeline de shaders é robusto.**

1. ✅ Build fecha limpo
2. ⚠️ Aceite visual do usuário (cubo renderizado, input funcionando no navegador)
   - Bloqueador para avançar: nenhum, teste automatizado já passa
   - Necessário antes de declarar sucesso: validação visual pelo usuário
3. ✅ Persistência IDBFS (implementado, smoke test pendente)
4. ⚠️ Documentação de deploy
5. ✅ Filtros 2D (15 compilam limpo, visual pendente)

**Saída esperada**: release alpha de Web com documentação clara de deploy, funcionando em navegador real.

### Fase 2: Backend Android + skeleton de APK (3-4 semanas)

A validação Linux torna esta fase menos especulativa: já existe prova de que o player compila e roda fora do
Windows com dependências Unix reais. O trabalho Android deve começar pelos erros concretos já vistos no NDK
(`malloc_stats`, `GL/glu.h`) e só depois entrar no backend de janela/ciclo de vida.

1. **Criar `GHOST_SystemAndroid` e `GHOST_WindowAndroid`**
   - Baseado em `GHOST_SystemSDL` existente, mas mapeando lifecyle Android
   - Integração de `ANativeWindow` com contexto EGL (`GHOST_ContextEGL`)
   - Callback de pause/resume

2. **CPython 3.11 cross-compilado para Android**
   - Mesma abordagem de Web PoC (`wasm_build.py`) e Linux (`install-python311.sh`), mas com NDK
   - Sysroot: `$ANDROID_NDK_HOME/toolchains/llvm/prebuilt/...`

3. **CMake adjust**
   - `platform_android.cmake` (hoje em stub) com lógica real
   - Libs de sistema via NDK sysroot (libz, liblog, etc.)
   - OpenAL backend seleção (OpenSL ES inicialmente)
   - Aplicar desde o começo a disciplina validada no Linux: features incompatíveis ficam explicitamente
     desligadas no preset até serem portadas, com motivo documentado.

4. **APK scaffolding mínimo**
   - Java/Kotlin nativo (Activity, Surface, window management)
   - Carregar `RangeRuntime.so` do C++ lado
   - Padrão: não é app "nativa" no design, é wrapper SDL2 + engine C/Python

### Fase 3: Input + Persistência Android (1-2 semanas)

1. ✅ Teclado/mouse (herdado de SDL2)
2. 🆕 Touch sensor (novo `SCA_IInputDevice`)
3. 🆕 Persistência `/data/data/<app>/files/`
4. 🆕 Permissões Android (storage, camera se usado, etc.)

### Fase 4: Validação e documentação (1-2 semanas)

1. Smoke test em dispositivo real ou emulador
2. Debug de efeitos visuais (shaders GLSL ES 3.0)
3. Benchmark e otimização (se necessário)
4. Documentação: Como buildar APK, como exportar do Blender, etc.

---

## Bloqueadores e decisões pendentes

### Web
- **Contexto desktop vs. mobile no navegador**: hoje o código assume mouse/teclado. Versão mobile (tela pequena, touch) é futura.
- **SharedArrayBuffer / pthreads**: patch do emsdk é temporário, não versionado. Se engine precisar de threads reais, formalizar (portabilidade/segurança de build).
- **Cookies / tracking**: que informações IDBFS pode guardar? Política de privacidade.

### Android
- **32-bit**: NDK ainda suporta ARMv7 (32-bit), mas o repo descartou suporte 32-bit em 2026. Validar x86_64 e arm64-v8a? 
  - Recomendação: arm64-v8a só para MVP, x86_64 em seguida se houver necessidade de teste no emulador
- **Versão mínima de API**: Android 9 (API 28)? API 21 é muito velho?
  - OpenGL ES 3.0 requer API 18+, então API 21-28 é razoável
- **Gráficos**: GLES 3.0 obrigatório como em Web?
  - Android 5.0+ tem GLES 3.0, a maioria dos dispositivos desde 2015 tem
  - Recomendação: GLES 3.0 obrigatório, fallback para 2.0 (mais simples) é escopo futuro

---

## Próximas etapas imediatas

1. **Web — aceite visual do usuário** (esta semana)
   - Testar no navegador real (Chrome/Firefox, desktop)
   - Confirmar: cubo renderizado, input funcionando
   - Saída: aprovado/bloqueadores claros

2. **Documentação Web** (mesma semana)
   - Como buildar (`emcmake cmake --preset web-runtime`, etc.)
   - Como fazer deploy (servidor HTTP, headers COOP/COEP?)
   - Como exportar do Blender (futura integração com RangeArmor?)

3. **Plano detalhado de Android** (semana seguinte)
   - Especializar este documento com:
     - Diagrama de como NDK + Gradle + Java glue se conectam
     - Checklist de features (touch, storage, etc.)
     - Estimativas reais de esforço por etapa
     - Reuso das lições Linux: Python isolado, RPATH/equivalente de empacotamento, seleção de libs,
       validação em hardware real
   - Criar `android-build.md` espelhando `linux-build.md` e `web-export-plan.md`

---

## Leitura complementar

- [`web-export-plan.md`](web-export-plan.md) — levantamento original de Web
- [`web-python-poc-plan.md`](web-python-poc-plan.md) — prova de conceito de Python no navegador
- [`mobile-export-plan.md`](mobile-export-plan.md) — levantamento original de mobile
- [`docs/roadmap.md`](roadmap.md) — work-in-progress de engine, seção "Export para Web"
- [`docs/changelog.md`](changelog.md) — histórico datado, 2026-09-14 para Web, 2026-09-09 para Android
