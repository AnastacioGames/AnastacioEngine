# Roadmap

## Estado concluído — filtros 2D no Web (2026-09-14)

**Etapa encerrada para prosseguir com a implementação:** os filtros nativos originais da engine foram confirmados funcionando no navegador. A cobertura dos filtros adicionados na evolução da Range Engine foi implementada, compilada e exercitada sem erros de shader ou falhas de draw; o refinamento visual e a validação de custo ficam deliberadamente para uma etapa posterior. Para o uso na Internet, esses efeitos devem ser tratados como opcionais, devido ao custo de múltiplos passes e à variação de suporte entre GPUs/navegadores.

## RangeArmor

O fluxo de runtime Windows/Linux x86_64 foi concluído e está documentado em
[`rangearmor-modernization-plan.md`](rangearmor-modernization-plan.md). A interface 32-bit foi retirada;
o runtime já foi validado em Linux nativo fora do WSL (ver item "Linux x86_64" em Prioridade atual abaixo
para o que ainda falta).

Somente itens abertos, pendentes de validação ou explicitamente adiados ficam neste arquivo. Recursos
concluídos estão resumidos em [`../relatorio-melhorias-anastacioengine.md`](../relatorio-melhorias-anastacioengine.md)
e detalhados no [`changelog.md`](changelog.md).

## Prioridade atual

- **Perfil Range Engine Web e validador**: levantamento e regras em
  [web-profile-validation-plan.md](web-profile-validation-plan.md). Manter autoria na Range Engine e
  implementar verificação Web, propriedades persistidas, análise de dependências e relatório; teste/export dependem do
  runtime Web integrado. Marco A feito (2026-09-18: `Scene.range_web` e painel "Web (Range)", sem validador; Exportar Web indisponível com motivo). Marco B feito (núcleo puro `range_web`: manifesto do runtime, resultados e regras de arquivos/Python, 33 testes; ainda sem UI). Marco C feito (coleta `bpy` + resolução transitiva de controllers/components/imports/assets, 47 testes + integração no motor). Operador Validar Web e resultados com Localizar no painel (2026-09-18; desenho no editor ainda não verificado). Marco D parcial (2026-09-18): `tools/web/make-runtime-manifest.py` gera `RangeRuntime.manifest.json` do build e o Validar Web o consome (módulos Python, hashes, WEB-PKG-001); falta o teste automatizado no navegador (cubo + controller + A/D). Próximo: fechar D e marco E (pré-voo, logs, shader).

- **Cutscene nativo**: Fases 0–2 e 4–5 implementadas, incluindo dados persistidos,
  aba Properties depois de World com ícone `SEQUENCE`, operadores nativos,
  runtime C++, API Python, import/export JSON e exemplo `.blend`. Permanecem
  abertos a Fase 3 (ícones PNG próprios para identificação e ações específicas,
  sem substituir os ícones padrão `ZOOMIN`/`ZOOMOUT` de adicionar/apagar) e a
  validação manual de Play → Stop → Play e standalone. Ver o
  [plano de integração](cutscene-native-integration-plan.md) e o
  [roteiro do exemplo](cutscene-native-example.md).
- **Linux x86_64 (RangeRuntime e RangeEngine)**: ambos compilam, linkam, instalam e rodam em Linux nativo
  (Ubuntu 24.04, GPU NVIDIA real) desde 2026-09-15 — ver `docs/linux-build.md` e `docs/changelog.md`
  (entradas de 2026-09-15) para os bugs corrigidos em cada validação. O pacote portátil 0.3.0 também foi
  validado em máquina limpa. Pendente: (1) validar a janela real do `RangeEngine` com sessão gráfica
  (GHOST/X11, ícones, i18n, addons Python — só foi testado em modo `--background` até agora); (2) portar
  `WITH_OPENCOLORIO` e `WITH_CODEC_FFMPEG` do editor para as APIs atuais de OpenColorIO 2.x/FFmpeg 5+
  (desligados por incompatibilidade de API, não por ausência de lib — ver changelog 2026-09-15).
- **Release 0.3.0 — concluída**: pacotes Linux e Windows x86_64 publicados na mesma release `v0.3.0` do
  GitHub (`AnastacioGames/AnastacioEngine`), com `SHA256SUMS.txt` cobrindo os três arquivos. A RangeArmor
  passou a ser distribuída como asset separado (`RangeArmor-0.3.0-windows-x64.zip`) na mesma página, em vez
  de embutida no zip da engine — ver `docs/distribution-0.1.md` e changelog de 2026-09-15.
- **Export Web/Android após Linux nativo**: a validação Linux confirma que o runtime já é portável fora do
  Windows/MSVC e fornece um modelo concreto para Python isolado, RPATH/empacotamento e seleção de bibliotecas
  por plataforma. Isso ajuda Web e Android, mas não elimina seus backends específicos: Web ainda precisa
  fechamento visual/deploy, e Android ainda precisa resolver NDK, ciclo de vida, janela/input e APK. O plano
  consolidado está em [`android-web-export-roadmap.md`](android-web-export-roadmap.md).
- **Associação de arquivos**: permitir abrir `.blend` e `.range` diretamente com os executáveis adequados,
  definindo instalação/registro no Windows e comportamento de duplo clique.
- **Export para Web (WebGL/WebAssembly)**:
  **Empacotamento (2026-09-18):** `tools/web/package-web.py` + `tools/web/verify-package.cjs` implementados e
  verificados com `web-smoke.range` (ver [web-deploy.md](web-deploy.md)). Preset `web-runtime-release` e remoção do preload
  TEMP feitos. Smoke test de persistência IDBFS feito
  (`tools/web/verify-persistence.cjs`). Próxima peça: marco A do perfil/validador na UI (`Scene.range_web`).
  **Export com validação testado no navegador (2026-09-18):** `bom_cubo.blend` (cubo com textura difusa, normal map,
  Sun e Point, teclado e Motion) validado e exportado pelo comando de linha e rodando em `localhost`. Corrigidos no
  runtime: `null function` em `GPU_texture_from_blender` (sem `glGetTexLevelParameteriv` no GLES), blit de profundidade
  entre formatos diferentes (texturas de profundidade Web agora 24 bits) e cubo preto sob luz GLSL (NaN no
  Cook-Torrance com Roughness 0). Abertos: normal map `.dds` aparece um pouco diferente do desktop; aviso
  `glBlitFramebuffer` depth/stencil que já aparece uma vez no console; regenerar o manifesto do runtime
  (`tools/web/make-runtime-manifest.py`) automaticamente a cada build Web, pois manifesto velho bloqueia o export com
  WEB-PKG-001; página de pré-voo do marco E; marco G. Detalhes no [changelog](changelog.md).
  **Teste real após a retomada:** usuário reportou tela preta com piscadas.
  Corrigido divisor de instância residual no quad de tela: UVs ficavam constantes
  e os filtros amostravam o canto da textura. Build passou; 6.192 draws sem erro
  GL e amostras numéricas confirmam cor atravessando FXAA e chegando à tela.
  Aguardando novo aceite visual. A `untitled.range` do harness está vazia
  (sem objetos/câmera); uma nova `web-smoke.range`, gerada por
  `tools/create_web_smoke_scene.py`, havia exposto `alignment fault` em
  `test_pointer_array` ao carregar objetos. **Retestado em 2026-09-14 após o
  fix de teclado**: o `alignment fault` não reproduziu mais — `test-smoke.html`
  agora carrega `web-smoke.range`, inicia o controlador Python e desenha sem
  falhas (`build-web/smoke-diagnostic.log`). **Aceite visual confirmado pelo
  usuário em 2026-09-14**: cubo controlável pelas setas no navegador,
  em `test-smoke.html`.

  **Retomada 2026-09-14:** confirmado `offscreen attachments=2`. O bind dos
  materiais gerados agora desativa temporariamente saídas ausentes no shader
  e restaura os draw buffers ao terminar. Build e execução Web passaram para
  materiais e filtros FXAA, chuva, nuvens, lens flare e tonemap: os filtros
  reconhecidos pelo código-fonte usam somente o primeiro anexo durante o draw.
  Última execução: 6.222 draws em 1.037 frames, sem erro GL nesta cena.
  **Aceite manual do usuário em 2026-09-18** (pacote `web-smoke-release`): movimento, filtros simples (1–9, 0, Q),
  filtros embutidos (W/E/R/T) e gamepad OK. Antes pendente: filtros nativos ampliados (cena
  dedicada de MRT/filtros já criada e validada por CDP, ver abaixo; aceite
  visual e Python/teclado do caminho original já confirmados em cena
  separada, ver "Input de teclado/mouse no Web" abaixo). Detalhes no
  changelog de 2026-09-14. O histórico abaixo descreve os bloqueios
  anteriores e não substitui esta atualização.

  **Cobertura dos filtros nativos restantes (2026-09-14):** o fix de draw
  buffers acima (`m_webSingleColorOutput`, `RAS_2DFilter.cpp`) cobria só
  FXAA, Rain, Clouds, LensFlare e Tonemaps. Estendido para os demais filtros
  nativos de saída única confirmados por leitura de fonte: SSAO, Blur,
  Sharpen, Dilation, Erosion, Laplacian, Sobel, Prewitt, GrayScale, Sepia,
  Invert, OutLine, e os passes finais de composição de Bloom/SSR/Light
  Scattering que não têm off screen próprio (os passes intermediários desses
  três, que já bindam off screen dedicado de um anexo só, ficaram de fora de
  propósito). Build Web limpo (exit 0, `RangeRuntime`) e smoke test via CDP
  sem regressão (2.055 draws, zero falhas, 685 com MRT ativo).

  **Cena dedicada — tentativa inicial invalidada, refeita com binding de
  teclado (2026-09-14, mesmo dia):** a primeira versão desta cena empilhava
  os 15 filtros como `SCA_2DFilterActuator` "sempre ativos" via
  `controller.link(actuator=act)`, e o smoke test reportou 2.046 draws sem
  falha — **mas essa validação estava incorreta**: `link()` só declara a
  ligação lógica, um `SCA_PythonController` só dispara o actuator quando o
  script chama `cont.activate()` explicitamente, e a cena nunca fazia essa
  chamada — nenhum dos 15 filtros chegou a ser criado. O usuário confirmou
  visualmente ("apareceu mas sem efeitos"). Refeita a pedido do usuário
  ("colocar os efeitos em teclas do teclado"): cada filtro agora é
  ativado por uma tecla dedicada (`1`-`9`/`0`/`Q` para os 11 filtros simples,
  `W`/`E`/`R`/`T` para os 4 built-in SSAO/Bloom/LightScatter/SSR), via
  `cont.activate()` por nome de actuator. Achado um segundo bug que teria
  mascarado o teste mesmo com `activate()`: os 11 filtros simples
  compartilhavam `filter_pass=0`, corrigido dando um `filter_pass` único
  0-10 a cada um. Gotcha de teste automatizado: eventos de teclado
  sintéticos via CDP não chegam ao SDL/Emscripten sem um clique do mouse no
  canvas primeiro (foco) — sem isso, todo teste de tecla falha em silêncio,
  inclusive testes que antes funcionavam (falso-negativo de regressão).
  Com o binding de teclado ativando os filtros pela primeira vez de verdade,
  **apareceram 5 bugs reais de shader** (WebGL2/GLSL ES 3.00 rejeita tipagem
  mista int/float que compiladores desktop aceitam): `RAS_SSAO2DFilter.glsl`,
  `RAS_OutLine2DFilter.glsl`, `RAS_Bloom2DFilter_bufH/V.glsl`,
  `RAS_LightScaterring_Buffer2DFilter.glsl`, `RAS_SSR2DFilter.glsl` e
  `RAS_SSR_Blur2DFilter.glsl` — todos corrigidos. Rebuild `RangeRuntime` exit
  0; sweep completo via CDP das 15 teclas: **zero erros de compilação de
  shader e zero falhas de draw em todas as 15**. **Ainda falta**: aceite
  visual do usuário no navegador real (o teste automatizado agora confirma
  que os 15 filtros executam sem erro de GL/shader, não a aparência visual
  correta de cada efeito — não há objetos refletivos para SSR nem luz
  configurada para Light Scattering/SSAO nesta cena mínima). Detalhes no
  changelog de 2026-09-14.

  **Input de teclado/mouse no Web (2026-09-14):** duas causas raiz encontradas e
  corrigidas. (1) A porta SDL2 do Emscripten usava por padrão o alvo `"#window"`
  para o listener de teclado, que falha silenciosamente
  (`EMSCRIPTEN_RESULT_NOT_SUPPORTED`) neste ambiente;
  `SDL_SetHint(SDL_HINT_EMSCRIPTEN_KEYBOARD_ELEMENT, "#canvas")` em
  `GHOST_SystemSDL.cpp` corrige o registro. (2) Mesmo com o evento entrando na
  fila do SDL, `GHOST_SystemSDL::processEvents` nunca via nada: um segundo
  consumidor não filtrado da mesma fila global do SDL (`DEV_Joystick::HandleEvents`
  em `DEV_JoystickEvents.cpp`, `while (SDL_PollEvent(...))` sem checar o tipo)
  drenava e descartava todo evento não-joystick antes de GHOST processá-lo —
  só colide no Web porque lá o `sdlew` usado pelo código de joystick resolve os
  mesmos símbolos estáticos do binário (fila compartilhada), diferente do
  Windows nativo, onde `sdlew` carrega um `SDL2.dll` próprio e isolado. Corrigido
  trocando por `SDL_PeepEvents` restrito às faixas de tipo joystick/controller.
  Validado de ponta a ponta via Chrome headless/CDP com dispatch real de tecla
  (`code` preenchido): a cadeia completa SDL → `GHOST_SystemSDL::processEvents`
  → `DEV_EventConsumer::HandleKeyEvent` recebe `SDL_KEYDOWN`/`SDL_KEYUP`
  corretamente. **Aceite visual confirmado pelo usuário em 2026-09-14**: cubo
  controlável pelas setas no navegador real (`test-smoke.html`). Mouse e
  joystick também confirmados de ponta a ponta (log ground-truth do script
  Python: `keyboard moved cube`, `mouse click flipped spin direction`,
  `joystick moved cube`, `joystick button flipped spin direction`), mas essa
  segunda rodada foi validada via evento sintético/CDP, não observação visual
  direta do usuário.

  **Terceira causa raiz (2026-09-14):** usuário testou manualmente e reportou
  "funciona mas preciso apertar várias vezes". Captura SDL/GHOST confirmada
  100% confiável (6/6 toques mesmo sem intervalo); o problema estava um nível
  acima, nos getters de conveniência Python `keyboard.events`/`mouse.events`
  (`KX_PythonKeyboard.cpp`/`KX_PythonMouse.cpp`), que liam só o último
  elemento da fila de transições do tick — se um toque completo (down+up)
  cabe no mesmo tick de lógica (mais provável no Web, tick mais lento que o
  nativo), o valor final vira `JUSTRELEASED` e o toque some silenciosamente.
  Padrão antigo do BGE, raro de ver a 60fps nativo. Corrigido priorizando
  `JUSTACTIVATED` quando presente em qualquer ponto da fila do tick; não
  mexe na lógica de sensores (`SCA_KeyboardSensor::Evaluate`), que já lida
  com a fila corretamente. Build Web e nativo recompilados sem erro.
  **Confirmado em 2026-09-14**: toque único instantâneo (down+up sem
  intervalo, o pior caso) em ArrowRight e ArrowLeft, dois testes isolados
  com reload limpo — cubo respondeu nos dois, sem precisar de múltiplas
  tentativas. Teclado e mouse considerados resolvidos. Detalhes no
  changelog de 2026-09-14.

  **Gamepad físico — D-pad/analógico travando (2026-09-14, resolvido):** com
  controle físico real, botão funcionava perfeitamente mas o D-pad/analógico
  ficava travado/engasgado. Log de diagnóstico (duas camadas de printf,
  `EMSCRIPTEN_JoystickUpdate` vs. `DEV_Joystick::OnAxisEvent`) provou a causa
  raiz real neste repositório: `GHOST_SystemSDL::processEvents` (via
  `SDL_PollEvent` irrestrito) e `DEV_Joystick::HandleEvents` (via
  `SDL_PeepEvents` filtrado) fazem cada um seu próprio `SDL_PumpEvents` por
  frame na MESMA fila global do SDL — no Web os dois resolvem os mesmos
  símbolos estáticos (ver causa raiz de teclado/mouse acima). O `PollEvent`
  de GHOST silenciosamente drenava/descartava eventos
  `SDL_CONTROLLERAXISMOTION` antes do `PeepEvents` filtrado do joystick
  conseguir lê-los: no log, 13 mudanças reais de `axis[0]` no browser geraram
  zero chamadas a `OnAxisEvent` na mesma janela de tempo. Botões não sofriam
  porque `SDL_GameControllerGetButton()` lê o estado interno do SDL
  diretamente (atualizado antes até do evento entrar na fila), sem depender
  da fila. Corrigido: `DEV_Joystick::GetAxisPosition()` (e os dois
  chamadores internos `pGetAxis`/`pAxisTest`, mais `aAxisIsPositive`) agora
  leem `SDL_GameControllerGetAxis()` ao vivo, no mesmo padrão já usado (e já
  confiável) para botões — elimina a corrida de fila por completo em vez de
  reordenar `HandleEvents`/`processEvents` ou mexer no GHOST. **Confirmado
  pelo usuário em 2026-09-14** com hardware físico real: D-pad/analógico
  respondendo de forma suave e consistente após o fix, sem travar.
  Separadamente, o timestamp do `Gamepad.timestamp` do browser continua
  documentado como pouco confiável (ver ponto anterior) — o gate de
  timestamp removido na porta SDL2 do emsdk foi mantido como reforço
  independente, mas **esse patch (e os printfs de diagnóstico) continuam
  fora do controle de versão deste repositório** (cache de toolchain do
  emsdk, não versionado) — não sobrevive a reinstalação limpa nem se
  propaga para outra máquina. Formalizar isso (patch aplicado no build, port
  SDL2 customizado versionado, etc.) segue como item aberto. Detalhes no
  changelog de 2026-09-14.

  **Persistência de save via IndexedDB (2026-09-14):** implementado IDBFS para
  `bge.logic.saveGlobalDict()`/`loadGlobalDict()`, o único mecanismo de save do
  engine — `pathGamePythonConfig()` redireciona para `/saves/` sob
  `__EMSCRIPTEN__`, `web_idbfs_prerun.js` (novo `--pre-js`) monta IDBFS e
  sincroniza do IndexedDB antes do `main()` iniciar, e `saveGamePythonConfig()`
  dispara `FS.syncfs(false, ...)` após cada escrita para persistir de volta.
  Build `RangeRuntime` limpo (exit 0), IDBFS confirmado embutido no
  `RangeRuntime.js` gerado. Ponta a ponta verificado por
  `tools/web/verify-save.cjs` (cena `tools/create_web_save_scene.py`: `saveGlobalDict` numa sessão, `loadGlobalDict` após
  recarregar). **Aceite manual do usuário em 2026-09-18**: `SAVED` na 1ª sessão e `LOADED` após F5 no navegador. Detalhes no changelog
  de 2026-09-14.

  Levantamento original em
  [`web-export-plan.md`](web-export-plan.md), comparando com o levantamento mobile já existente.
  Conclusão: Web é o candidato de menor esforço entre Web/Android/iOS para esta engine, porque o
  Emscripten já entrega pronto as três peças que mais pesam num port de plataforma — porta SDL2
  (reaproveitaria o `GHOST_SystemSDL` já existente, sem escrever backend novo), alvo oficial
  `wasm32-emscripten` do CPython (mais maduro que cross-compile mobile) e criação automática de
  contexto WebGL via `SDL_GL_CreateContext`. Ainda é um port real: falta adaptar o loop principal
  para `emscripten_set_main_loop`, resolver gaps de GLSL ES/WebGL, decidir persistência de save
  (IDBFS) e confirmar dependência de threads reais (afeta requisitos de deploy).
  Tentativa real de build (2026-09-12, mesma metodologia da exploração Android de 2026-09-09):
  `platform_web.cmake` + preset `web-runtime` criados, dispatch `EMSCRIPTEN` e `WITH_X11`
  corrigidos no `CMakeLists.txt`, SDL2 confirmado reaproveitável (com `-sUSE_SDL=2` como flag de
  compilador), bug de cascata `WITH_GLU`/`WITH_GL_PROFILE_COMPAT` encontrado e contornado via
  preset. Build travou num bug genuíno e ainda não corrigido do `CMakeLists.txt`: a exigência de
  `OPENGLES_LIBRARY` (perfil ES20 sem EGL) é tratada como caminho de arquivo literal pelo Ninja,
  incompatível com Emscripten (que não tem `libGL` de sistema) — corrigir exige mudar a lógica em
  `CMakeLists.txt`, não só o preset. Detalhes completos em `web-export-plan.md`.
  Progresso desde então (sessões seguintes, ver
  [`web-python-poc-plan.md`](web-python-poc-plan.md) para o detalhe completo):
  bug do `OPENGLES_LIBRARY` corrigido, dual-toolchain (ferramentas geradoras
  `makesdna`/`datatoc`/`makesrna` nativas vs. runtime wasm) resolvido,
  `WITH_PYTHON=ON` religado com CPython compilado para `wasm32-emscripten`, e
  série de gaps de link fechados um a um (Boost, TBB, GL query, GLEW,
  OpenMP/mpdec/expat, stub de áudio, flags de porta bz2/sqlite3, shims de
  emulação GL/GLU usados pelo módulo Python `bgl`: `glLightf`, `glMaterialf`,
  `glLogicOp`, `gluPickMatrix`). **Build web hoje fecha limpo**
  (`BUILD_EXIT=0`, `RangeRuntime.js`/`RangeRuntime.wasm` gerados). Testes reais
  no navegador (harness local + Chrome headless via `--headless=new` com
  `--user-data-dir` absoluto — `--headless` antigo e caminho relativo abrem
  uma janela real do Chrome em vez de rodar sem interface) foram avançando a
  runtime além do arranque do Python, revelando e corrigindo, um de cada vez,
  bugs de pipeline fixo desktop-only sob Emscripten: `GPU_state_init`
  (corrigido, commit `c9871b0`), `RAS_OpenGLRasterizer::SetLines`/
  `glPolygonMode` (sem equivalente em WebGL/GLES2, guard `#ifdef __EMSCRIPTEN__`
  que pula a chamada) e o shader do ImGui inicializado com `#version 120`
  (GLSL desktop, rejeitado pelo WebGL2; corrigido para `#version 300 es` sob
  Emscripten em `KX_Imgui.cpp`). Com esses três corrigidos, o teste chegou a
  compilar o shader do ImGui, mas revelou um problema bem maior e sistêmico em
  `gpu_shader_material.glsl` (5411 linhas): dezenas de erros de tipo GLSL ES
  espalhados pelo arquivo inteiro — operações int/float sem conversão
  implícita (GLSL desktop permite, GLSL ES não), `sampler2DShadow` sem
  precisão declarada e `mod()` sem overload para inteiro. Cinco ocorrências
  do padrão int/float já corrigidas (linhas ~615, ~1145, ~1972, ~2329, ~2348),
  mas a varredura de 2026-09-13 mostrou erros adicionais entre as linhas
  ~2702 e ~4639 do arquivo. **Varredura concluída em 2026-09-13**: corrigidos
  também `test_shadow_pcf_penumbra` (`samples` int em divisão/exponente),
  `floorfrac`, `calc_gradient` (radial), o bloco spline Catmull-Rom,
  `test_shadow_simple` (`type == 1/2`), `node_tex_checker` (`mod()` em int
  trocado por `&`), Principled BSDF (`Cdlum > 0`), `node_tex_magic` (10
  comparações `depth > N`), `mtex_parallax` (`textureLod` com lod inteiro e
  loop `i < numsteps`), `node_tex_wave` (`fac = 1`), `lamp_visible`
  (`col`/`energy` * `mask` inteiro) e `dither()` (`bayer[i]` inteiro dividido
  por `64.0`). Também corrigido, em `gpu_codegen.c`: (a) `GLEW_VERSION_3_0`
  sempre falso sob Emscripten fazia o codegen emitir `varying`/`attribute`
  legado mesmo alvejando `#version 300 es` — introduzida a macro
  `GPU_CODEGEN_USE_MODERN_QUALIFIERS` que força `in`/`out`/`attribute`
  modernos sob `__EMSCRIPTEN__`; (b) `gl_FragData[i]` (built-in legado,
  inexistente em GLSL ES 3.00) — `code_generate_fragment` agora declara
  `out vec4 fragDataN;` explícito por índice de saída usado e
  `codegen_call_functions` escreve nessas variáveis em vez de `gl_FragData[i]`
  quando `GPU_CODEGEN_USE_MODERN_QUALIFIERS`. Resultado: `gpu_shader_material.glsl`
  agora compila **sem nenhum erro** no teste Chrome headless (antes: dezenas de
  erros de tipo). Método usado para localizar bugs cujo número de linha do erro
  do driver não bate com o arquivo fonte (porque `GPU_shader_create_ex` concatena
  várias strings GLSL antes de compilar): calibrar um deslocamento fixo a partir
  de um erro já confirmado (`lamp_visible`, deslocamento ~75 linhas) e localizar
  os demais por conteúdo/padrão do operador, não pelo número absoluto.
  Build limpo do shader não é mais o bloqueio: o teste avançou para dentro do
  loop de renderização e revelou um problema de camada diferente — bind de
  buffers WebGL (`vertexAttribPointer`/`drawElements` reportando
  `INVALID_OPERATION`/`no buffer is bound`), provavelmente no rasterizer
  (`RAS_OpenGLRasterizer`/VAO-VBO) sob emulação GL do Emscripten, corrigido em
  sessão posterior (ver changelog). Progresso 2026-09-13 (teste real em
  navegador com prints de tela do usuário, não Chrome headless): corrigido
  `gpu_texture.c` — textura de profundidade usava `GL_DEPTH_COMPONENT16`
  como internalformat mas manteve `type = GL_UNSIGNED_BYTE`, combinação
  inválida em WebGL2/GLES3 (`GL_DEPTH_COMPONENT16` exige
  `GL_UNSIGNED_SHORT`); confirmado pelo usuário que os erros
  `glTexImage2DRobustANGLE: Invalid combination...` e `Attachment has zero
  size` desapareceram após o fix. Restou um segundo bug, ainda **não
  resolvido**: `GL_INVALID_OPERATION: glDrawElements: Active draw buffers
  with missing fragment shader outputs` (256 ocorrências, teto de log do
  Chrome atingido). Tentativa de fix em `gpu_codegen.c` (declarar
  `layout(location = i)` explícito em cada `out vec4 fragDataN` gerado)
  **não resolveu** — erro idêntico após rebuild, descartando a hipótese de
  que a ausência de location explícita fosse a causa para este cenário
  (material padrão só popula `outputs[0]`; ver `gpu_material.c`,
  `GPU_material_output_link` sempre chamado com `index=0` exceto em
  `node_shader_output_attachment.c`). Hipótese em aberto no fim da sessão:
  `RAS_OffScreen::m_numColorSlots` (contagem de anexos passada a
  `glDrawBuffers` via `GPU_framebuffer_bind_all_attachments`, ver
  `LA_Launcher.cpp`/`RAS_OffScreen.cpp`/`gpu_framebuffer.c`) pode ser maior
  que 1 para esta cena de teste, enquanto o material do cubo só escreve em
  location 0 — foi adicionado um `fprintf` diagnóstico em `LA_Launcher.cpp`
  (`offscreen attachments=N`) para confirmar; ainda sem retest do usuário no
  momento em que a sessão foi encerrada (fim de expediente). Se `N=1`, a
  hipótese cai e resta investigar o shader legado de pipeline fixo
  (`gpu_shader_basic_frag.glsl`, usa `gl_FragColor`/`varying`, incompatível
  com GLES3) ou algum outro FBO (sombra, filtro 2D) como fonte real do erro.
  **Importante, reforçado pelo usuário nesta sessão**: console sem um erro
  específico (ou até "engine started" no log) não é validação visual nem
  funcional — o critério de aceite (cubo real renderizando corretamente e
  controlável por Python/teclado, confirmado visualmente pelo usuário no
  navegador, sem captura automatizada) continua pendente e é o próximo
  passo assim que o console estiver realmente limpo.
- **Export mobile (Android/iOS)**: levantamento em [`mobile-export-plan.md`](mobile-export-plan.md),
  incluindo uma tentativa real de build Android (2026-09-09) que provou o CMake navegável (preset
  `android-runtime` chega a "Configure done") mas travou em dois bugs de código genuínos
  (`malloc_stats` ausente na Bionic, `GL/glu.h` inexistente no NDK) antes mesmo de faltar o backend
  GHOST Android completo. Mais caro que Web pelo mesmo eixo de comparação (sem atalho equivalente
  ao Emscripten/SDL2/Pyodide). Nenhuma decisão de implementação tomada.
- **Export presets (in-Blender)**: implementado o painel `Scene > Export (RangeArmor)` com
  `RangeArmorExportSettings` (RNA Python, sem DNA/C) e a gravação de `product_name`/`product_version`
  em `GameName`/`Version` de `launcher/config.json` antes de abrir o RangeArmor Panel, preservando as
  demais chaves. Achado importante: `_validate_data` no RangeArmor Panel usa whitelist estrita de
  chaves — por isso os campos `company_name`, `icon_path` e toggle de plataforma ainda aparecem no
  painel mas não são gravados (não há chave correspondente aceita hoje); habilitá-los exige estender
  `DEFAULT_FIELDS`/`_validate_data` no lado Godot, decidido explicitamente como fora desta fase. Falta
  o teste manual (projeto novo e projeto antigo) descrito no [plano](export-presets-plan.md).
- **World Status**: as oito World Properties automáticas foram implementadas e compiladas, mas não
  apareceram em um `World` novo no teste real. Diagnosticar criação, versionamento e atualização da UI.
- **Contorno pendente `USE_RNA_RANGE_CHECK` (Emscripten)**: o Emscripten é o
  primeiro toolchain deste projeto a definir `__STDC_VERSION__ >= 201112L`
  (MSVC nativo nunca define), o que ativa checagens de range em tempo de
  compilação (`rna_internal.h`) que expõem incompatibilidades reais e
  pré-existentes entre o tipo do campo DNA e o hardmax definido na RNA —
  encontrados até agora: `ImageUser.fie_ima` e `Material.seed1`/`seed2`.
  A checagem foi **desativada só para Emscripten** (`#if ... &&
  !defined(__EMSCRIPTEN__)` em `rna_internal.h`) como **contorno
  temporário**, não correção — permanece pendente resolver cada caso
  individualmente (tipo do campo DNA vs. definição de range da RNA), sem
  presumir de antemão "alargar o tipo do campo DNA", e considerando
  explicitamente compatibilidade retroativa com `.blend` legado em cada
  caso.
- **Auditoria de `source/source/blender`**: confirmar ou descartar os candidatos registrados em
  [`relatorio-varredura-bugs-silenciosos.md`](relatorio-varredura-bugs-silenciosos.md), com reprodução,
  correção isolada e teste aplicável.
- **Fix `WITH_INPUT_IME` no `RangeRuntime` nativo**: `bad_level_call_stubs/CMakeLists.txt`
  não propagava `-DWITH_INPUT_IME` como faz para as demais opções
  (`WITH_INPUT_NDOF`, `WITH_GAMEENGINE`, etc.), então os stubs de IME em
  `stubs.c` ficavam sempre compilados fora, mesmo com `WITH_INPUT_IME=ON`
  (padrão no Windows) usado por `interface_handlers.c`/`wm_window.c` —
  causava `LNK2019` (`WM_event_is_ime_switch`, `wm_window_IME_begin`,
  `wm_window_IME_end`) só no link do player, não do Blender completo.
  Corrigido adicionando o bloco `if(WITH_INPUT_IME)` espelhando o padrão
  existente. Build nativo `v142-ninja` (com `WITH_AUDASPACE=ON`, padrão do
  `CMakeLists.txt`) validado limpo após o fix; execução manual do
  `RangeRuntime.exe` confirmada (inicializa GPU real, roda establemente,
  sem crash) — validação de áudio ficou limitada a "sem erro visível no
  caminho `AUD_init`/`OpenAL32.dll` presente", não uma verificação audível
  fim a fim, por falta de um asset de teste com fonte de som à mão.
- **Vehicle System / Vehicle Lab**: executar por marcos o
  [plano 2](vehicle-system-plan-2.md) — Fase B (Steering & Brakes, incl. volante visual),
  Fase C (Powertrain: drive type, torque/RPM, marchas), Fase A (Chassis: Center of Mass
  offset). Fase D (Wheel & Suspension) está fechada, sem trabalho novo.

## Performance

- Investigar o custo residual de `MainRender` na cena de benchmark. O teste A/B já descartou GPU Skinning
  como causa; qualquer nova hipótese deve começar por medição.
- Avaliar o conteúdo de folhagem e os níveis de LOD na cena real. A infraestrutura de impostor e o bake de
  atlas já existem; o restante pode ser trabalho de asset, não de engine.
- Vendorizar `Recast/`/`Detour/` a partir de `tools/recastnavigation-main` (a API de integração
  já foi portada para `dtNavMesh`/`dtNavMeshQuery`, ver
  [changelog](changelog.md#2026-09-08--recastnavigation-port-para-api-moderna-dtnavmeshdtnavmeshquery);
  falta trazer a lib em si, com a varredura de bugs silenciosos prevista no plano original).
- Navmesh dinâmica: hoje o navmesh é gerado uma única vez (`mesh.navmesh_make`) e não reage a
  objetos que se movem depois do bake. Suporte a isso exigiria trazer `DetourTileCache`
  (não vendorizado hoje) e um sistema de obstáculos temporários — escopo novo, não iniciado.

## Iluminação e gráficos

- **Resolução dinâmica (runtime)**: implementada como opt-in em `Game Render Properties > Dynamic Resolution`, com alvo de FPS, limites e passo. O controlador mede GPU, aplica média/histerese e reduz somente os offscreens do 3D; a janela, input e UI continuam na resolução nativa. Funciona no Play do Game Engine e no standalone, não na 3D View de edição. Build e smoke test passaram; falta validar visualmente numa cena GPU-bound, comparando ligado/desligado e observando se não há oscilação perceptível de escala ou artefatos nos efeitos.
- CSM: blend suave entre cascatas (`shadow_simple_csm`/`shadow_vsm_csm`, cross-fade via
  `smoothstep` numa banda de 10% do split) e visualização de debug (`csm_debug_tint`, DNA/RNA/UI)
  já estão implementados em `gpu_shader_material.glsl` — item desatualizado, mantido aqui só até
  medir o custo real de GPU dessas duas features, que segue pendente.
- Avaliar antialiasing temporal somente com um caso de uso e critérios de qualidade definidos.
- Permanecem aceitos como no-op no core profile: motion blur legado, clipping de espelho/água e texto de
  debug via `BLF_draw`. Reabrir apenas com demanda concreta.

## Validações pendentes

- **Export para Web — atualização 2026-09-13**: o runtime wasm já inicializa Python, lê `untitled.range` até `ENDB`, cria o canvas WebGL2, compila os shaders básicos em GLSL ES 300 e cria os framebuffers e suas texturas. O caminho Web usa as entradas GLES3 diretas para shader, VAO, framebuffer e renderbuffer, pois os ponteiros de extensão desktop do GLEW ficam nulos no Emscripten; a chamada singular `glDrawBuffer` é traduzida para `glDrawBuffers`. O bloqueio atual está isolado em `RAS_Query::RAS_Query`, ainda ligado às funções de GPU query do GLEW desktop. Depois dessa adaptação ainda falta alcançar e validar visualmente a primeira cena.
- **Export para Web — atualização 2026-09-13 (2)**: com o alocador corrigido (handoff Codex), `LA_Launcher::InitEngine` avançou até um novo `null function` dentro de `RAS_Rasterizer::Init()`/`GPU_state_init()`. Diagnosticado e corrigido: (1) `GPU_basic_shader_light_set`/`GPU_basic_shader_light_set_viewer` (`gpu_basic_shader.c`) chamavam `glLightfv`/`glMaterialfv`/`glLightModeli` (pipeline fixo, inexistente em WebGL/GLES2) incondicionalmente dentro de `GPU_default_lights()`; agora esses caminhos são pulados sob `__EMSCRIPTEN__`, mantendo só a contabilidade de estado (`lights_enabled`/`lights_directional`) usada para escolher a variante do shader GLSL. (2) `GPU_state_init()` (`gpu_draw.c`) chamava `glDepthRange` (double), que não existe em GLES2/WebGL (só `glDepthRangef`); agora usa `glDepthRangef` sob `__EMSCRIPTEN__`. Com isso `LA_Launcher::InitEngine` completa e o loop chega a `LA_Launcher::RenderEngine()`. **Novo bloqueio, já localizado**: `RAS_OpenGLRasterizer::SetLines(bool)` chama `glPolygonMode(GL_FRONT_AND_BACK, GL_LINE/GL_FILL)`, também desktop-only (sem equivalente em GLES2/WebGL) — próximo `null function` a corrigir, mesmo padrão dos fixes acima.
- **Export para Web — atualização 2026-09-13 (3)**: com o shader `gpu_shader_material.glsl` compilando sem erros, o teste avançou para dentro do loop de render e passou por três classes de erro de console no Chrome headless, todas corrigidas e confirmadas ausentes por log real do navegador: (1) ordem de unbind VAO/VBO em `RAS_StorageVao.cpp`/`RAS_OpenGLRasterizer.cpp` fazia o WebGL2 derrubar a referência do VBO no VAO emulado; (2) IBO do DebugDraw (`RAS_OpenGLDebugDraw.cpp`) usava o target errado; (3) `texImage2D: invalid internalformat` — textura de sombra criada com `GL_DEPTH_COMPONENT` (não dimensionado, inválido em WebGL2/GLES3), corrigido para `GL_DEPTH_COMPONENT16` sob `__EMSCRIPTEN__` (`gpu_texture.c`); (4) `texParameter: invalid parameter name` — `GL_DEPTH_TEXTURE_MODE` não existe em GLES3/WebGL2 core, chamada pulada sob Emscripten; (5) `getParameter: invalid parameter name` — Chrome deduplica mensagens de erro idênticas no console, o que escondeu que a causa real era `RAS_OpenGLRasterizer::GetNumLights()` consultando `GL_MAX_LIGHTS` (pipeline fixo, sem equivalente em GLES3/WebGL2); corrigido retornando 8 fixo sob `__EMSCRIPTEN__` (mesmo teto que o código desktop já aplicava). Localizado por instrumentação temporária (monkeypatch de `getParameter` no harness de teste, com `console.log` capturado via `--enable-logging=stderr`, já que `--dump-dom` trava no loop de render em tempo real desta página). Endurecimentos adicionais de correção em `gpu_extensions.c` (colordepth via `GL_RED/GREEN/BLUE_BITS`, anisotropia via `GLEW_EXT_texture_filter_anisotropic`, `GL_MAX_COLOR_TEXTURE_SAMPLES`) também aplicados sob guards `__EMSCRIPTEN__`; nenhum dos três isoladamente eliminou o erro observado, mas permanecem como correções de espec válidas. **Importante — distinção entre validado e pendente**: console limpo (sem nenhuma linha `WebGL:`) e `"[web-launcher] engine started"` foram confirmados via log real do Chrome headless; isso NÃO é validação visual nem funcional. Ainda faltam: (a) confirmar visualmente que o cubo aparece corretamente renderizado e iluminado no canvas; (b) confirmar que o controle via Python/teclado do cubo funciona em tempo real no navegador. Um achado à parte, não investigado: a mesma instrumentação temporária revelou `getParameter(GL_ELEMENT_ARRAY_BUFFER_BINDING)` retornando erro `INVALID_FRAMEBUFFER_OPERATION` (0x8895/1286, 6x) — não visível no log final sem instrumentação; impacto real desconhecido, requer investigação futura antes de ser descartado.

- Cutscene nativo: executar no editor o roteiro de
  [`cutscene-native-example.md`](cutscene-native-example.md), cobrindo
  salvar/reabrir, Play → Stop → Play e execução standalone; confirmar que o
  `Spawn Object` dispara uma vez, limpa a réplica no Stop/Restart e mantém o
  mesmo resultado nos dois modos. A validação automatizada de geração,
  reabertura, importação/exportação e estrutura do exemplo já passou.

- Ketsji / Plano 1A: contador de estabilização CSM corrigido, rebuild limpo e
  smoke test de reinício aprovados. Validar sombras no jogo real em
  Play → Stop → Play e standalone, incluindo múltiplas luzes/cenas e a transição
  do nono para o décimo frame elegível. Ver
  [plano mestre](ketsji-engine-modernization-plan.md). Registrar separadamente
  os avisos de textura sem nível-base vistos em `-d gpu`; origem ainda não
  determinada. O runtime local testado reporta perfil Compatibility.
- Ketsji / Plano 1A: `shadowCulling` separado de `maxphystep` (DNA/RNA/
  versionamento/engine/launcher/Python docs), rebuild limpo (2.935/2.935) e
  smoke test aprovados. Falta testar a migração de arquivo antigo com
  `maxphystep` gravado em 0/1/5/10 real (hoje só revisada por leitura) e
  validar visualmente que arquivos antigos preservam o comportamento de
  sombra. Ver [plano mestre](ketsji-engine-modernization-plan.md).
- Ketsji / Plano 1A: `SetTicRate`/`SetRenderRate`/`SetAnimationRate` agora
  rejeitam zero, negativo, NaN e infinito (Python e C++), preservando a
  última taxa válida; rebuild e smoke test dedicado aprovados.
- Ketsji / Plano 1A: cálculo da posição do Sol em `PostRenderScene` agora
  ignora `screenPos.w` nulo/próximo de zero/negativo (Sol atrás da câmera ou
  paralelo ao plano de visão) em vez de dividir por ele; rebuild e smoke test
  dedicado (cena `ketsji_sun_projection_smoke.range` nova) aprovados. Falta
  confirmar visualmente no jogo real que o Light Scattering/Lens Flare não
  pisca ou salta ao cruzar esses ângulos, já que os uniforms não são
  inspecionáveis via Python. Ver [plano mestre](ketsji-engine-modernization-plan.md).
- Ketsji / Plano 1A: item 5 (último) — `FreeCustomMouseCursor` corrige a
  remoção do cursor personalizado com `nullptr` (o setter desreferenciava o
  ponteiro novo antes de checar se existia) e o vazamento da struct
  `CustomMouseCursor` na troca e no encerramento da engine; rebuild e smoke
  test dedicado aprovados. **Plano 1A concluído (itens 1–5).** Nenhum ponto de
  entrada Python passa `nullptr` ao setter hoje, então esse ramo específico
  não tem cobertura automatizada, só revisão de código. Ver
  [plano mestre](ketsji-engine-modernization-plan.md).
- Ketsji / Plano 2: categorias `tc_collisiondepth` (`CollisionDepth`) e
  `tc_texturerenderers` (`TextureRenderers`) separadas do profiler (antes
  somadas em `Shadows`/`MainRender`), completando o item "Texture renderers e
  collision-depth pass" em duas unidades; clean rebuild aprovado nas duas.
  Falta confirmar visualmente as duas categorias como linhas separadas num
  relatório de benchmark — validação opcional, não bloqueante. Ver [plano
  mestre](ketsji-engine-modernization-plan.md).
- Ketsji / Plano 2: categoria `tc_particles` (`ParticleUpdate`) separada de
  `Scenegraph`, isolando `KX_Scene::UpdateGpuParticleEmitters()` (metade
  "atualização" do item "atualização e desenho de partículas"); clean
  rebuild e teste no jogo real aprovados. Ver [plano
  mestre](ketsji-engine-modernization-plan.md).
- Ketsji / Plano 2: categoria `tc_actuators` (`Actuators`) separada de
  `Logic`, isolando `SCA_LogicManager::UpdateFrame` (parte "actuators" do
  item "sensores, controllers/Python e actuators separadamente"; sensores e
  controllers seguem fundidos, fora do escopo); clean rebuild e teste no
  jogo real aprovados. Ver [plano
  mestre](ketsji-engine-modernization-plan.md).
- Ketsji / Plano 2: categoria `tc_input` (`Input`) separada de `Overhead`,
  isolando o bloco de input/ImGui no início de `NextFrame()` (item "Input e
  ImGui"); clean rebuild e teste no jogo real aprovados. Ver [plano
  mestre](ketsji-engine-modernization-plan.md).
- Ketsji / Plano 2: categoria `tc_scenegraph` (`UpdateParents`) separada em
  três — `tc_scenegraph_logic`, `tc_scenegraph_actuators` e
  `tc_scenegraph_physics` —, uma para cada passagem de `UpdateParents()` em
  `NextFrame()` (item "Cada passagem de `UpdateParents`"); clean rebuild e
  teste no jogo real aprovados. Ver [plano
  mestre](ketsji-engine-modernization-plan.md).
- Ketsji / Plano 2: categoria `tc_lightupdate` (`LightUpdate`) separada de
  `Shadows`, isolando o loop de atualização de luzes
  (`UpdateDistanceCulling`/`Update`/glow) em `RenderShadowBuffers()` (7ª
  unidade, parte "atualização de luzes" do item "Atualização de luzes,
  ajuste de matrizes CSM, shadow culling e shadow draw"; shadow
  culling/shadow draw já estavam separados, ajuste de matrizes CSM ficou
  fora por não ter ponto de retomada isolado); clean rebuild e teste no
  jogo real aprovados. Ver [plano
  mestre](ketsji-engine-modernization-plan.md).
- Ketsji / Plano 5: 3ª e 4ª unidades de otimização de sombras concluídas e com
  build limpo — reutilização das câmeras temporárias de sombra e cache por
  luz que pula o recálculo das matrizes de cascata quando câmera/luz não se
  moveram e não há shadow casters dinâmicos. Falta validar em jogo real (CSM,
  split estático/dinâmico, debug do frustum) antes de dar o Plano 5 por
  encerrado. Ver [plano mestre](ketsji-engine-modernization-plan.md).
- Ketsji / Plano 5: 5ª unidade — nova propriedade de câmera
  `csm_cache_max_stale_frames` ("Shadow Cascade Cache Tolerance", painel
  Culling, slider 0/1/2) para o usuário controlar o cache de cascata da 4ª
  unidade, motivada por um relato de tremor de sombra ao mover a câmera.
  Rebuild limpo e teste em jogo real aprovados: valor 2 (Tolerant) não
  mostrou diferença perceptível de tremor nem pop de sombra. O cap de 1
  frame de tolerância (`kCSMCacheToleranceEpsilon`) foi mantido como está —
  aumentar esse limite ficaria como trabalho futuro isolado, não decidido
  agora. **Plano 5 concluído (unidades 1–5).** Ver
  [plano mestre](ketsji-engine-modernization-plan.md).
- Confirmar visualmente o splash e About no `RangeEngine`: todo o popup deve subir discretamente em 1,2 s; o
  painel inferior precisa manter o estilo limpo (sem caixas cinzas), `Create Project`, recentes e os links de
  rede devem permanecer interativos.
- Antes da próxima distribuição, declarar explicitamente se o fork será publicado como GPLv2-or-later ou
  sob GPLv3 e incluir o arquivo de licença correspondente na raiz/pacote.
- Confirmar no editor a aba Particles em objetos Empty e as ordens ajustadas nos painéis Render Layers e
  Physics.
- Testar os bindings do menu ImGui com um gamepad físico e ajustar as áreas clicáveis, se necessário.
- Executar a cena de regressão física dos Runtime Property Sensors/Actuators, incluindo massa, velocidades,
  gravidade e referências a objetos removidos.
- Sob stress real, exercitar start/stop de captura de vídeo e múltiplos efeitos OpenAL. Os fixes estáticos de
  concorrência já compilam; este teste é complementar.

## Fora do escopo atual

- Paralelização ampla do loop principal e remoção do GIL de Python.
- Atualização completa do Bullet apenas para obter solver multithread.
- Edição de cena durante o jogo com persistência automática.
- Reimplementação de recursos herdados listados no relatório de melhorias.

## Validação visual do Outliner

- Confirmar visualmente `View > Show Alternating Rows` ligado/desligado: alterar a cor de fundo no tema, rolar a lista e verificar seleção e colunas de restrição. Build, inicialização e persistência dos dois estados ao salvar/reabrir passaram em 2026-09-13.

## Validação visual da 3D View

- Confirmar a barra flutuante da 3D View no canto inferior esquerdo: testar Play, Standalone e Debug/Console, todos os modos de sombreamento e sua seta de opções, o ícone de câmera para atualização contínua, Only Render, o painel de overlay, o bloqueio de câmera/camadas, o seletor de camadas e a entrada/saída de Edit Mode (controles Auto Merge, Occlude Geometry e Mesh Display). Com o ícone ligado, confirmar a atualização contínua de materiais animados e de decals/projetores; desligado, confirmar que ela para. Redimensionar a área e verificar conflitos com textos informativos. Build e inicialização passaram em 2026-09-13.
