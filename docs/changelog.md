# Changelog — AnastacioEngine

Registro histórico do que foi feito, alterado ou adicionado no fork. Entradas antigas preservam o contexto
da época e podem conter hipóteses corrigidas em entradas posteriores. Para o estado vigente, consulte
`docs/roadmap.md` e `relatorio-melhorias-anastacioengine.md`.

**Como está organizado.** Este arquivo guarda as entradas mais recentes (novas entradas vão no topo, logo abaixo desta tabela). O histórico mais antigo está em `docs/changelog/`, dividido em arquivos de até ~70 KB para caber na leitura de uma IA. Quando este arquivo passar de ~60 KB, mova as entradas mais antigas para um novo arquivo em `docs/changelog/` e acrescente uma linha na tabela abaixo.

## 2026-10-20 - Gravação de tela (screencast) refeita

- O screencast da 2.79 (Ctrl+Alt+F3) não existia mais nesta base; só o screenshot. Volta como
  `SCREEN_OT_screencast` (liga/desliga), menu Window ▸ Record Screen e Ctrl+Alt+F3. Opções: `fps` (30),
  `quality` (Low/Medium/High/Very High = CRF 28/23/18/14), `full` (janela inteira ou só a 3D View), `show_cursor`,
  `filepath` (vazio: `<blend>_screencast_<data-hora>.mp4` ao lado do .blend, ou na pasta padrão).
- Núcleo em `windowmanager/intern/wm_screencast.c`: captura logo antes de cada swap
  (`wm_window_swap_buffers`), então grava o editor e o jogo rodando embutido; lê o back buffer (o front buffer
  é indefinido com compositor) por um anel de 3 PBOs com fence, sem travar a GPU; encoder H.264/MP4 numa
  thread própria com fila e pool de 8 quadros (se não der conta, descarta e avisa em vez de travar a UI);
  cada quadro leva o tempo de captura como pts, então janela parada não gera trabalho e o vídeo sai em tempo
  real; cursor desenhado no quadro (anel, preenchido com botão apertado). Segue a janela pelo `ghostwin`
  (sobrevive a abrir outro arquivo); para sozinho ao fechar a janela e ao sair.
- Header Info: botão vermelho "Recording mm:ss" (atualiza a cada 1 s) que para e informa o arquivo salvo.
- `writeffmpeg.c`: encoder usa várias threads (o padrão do libavcodec era 1; na gravação ao vivo, metade dos
  núcleos), buffer RGB intermediário alocado uma vez por stream (era por quadro), cópia por linha com
  `memcpy`; modo realtime (`BKE_ffmpeg_context_realtime_set`) pula as opções x264 legadas (subq 6, 3
  B-frames, CAVLC) que anulavam o preset rápido. Também vale para render de animação em vídeo (threads e
  buffer).
- Screenshot: indentação enganosa do crop corrigida e `glFinish` redundante removido.
- Compilado (RangeEngine + RangeRuntime). Gravação testada pelo usuário com janela: OK.
- Header Info, lado esquerdo (depois dos menus; no canto direito o popover saía da janela): botão `Rec` + popover `INFO_PT_screen_recorder` (Start/Stop, Full Window, Show
  Cursor, Frame Rate, Quality, pasta de destino, `Open Folder`, `Play Last`). Clique direito no header Info:
  checkbox `Screen Recorder` (`WindowManager.info_show_screen_recorder`) mostra/esconde. As opções ficam em
  `WindowManager.screencast_*` (Python) e o operador C as lê quando não recebe a propriedade, então o
  Ctrl+Alt+F3 usa as mesmas. RNA novo: `WindowManager.is_screencast_running` e `screencast_filepath`
  (vídeo atual ou último da sessão). Operadores em `bl_operators/anastacio_screencast.py`.
- `Full Window` desligado grava a 3D View: a ativa, senão a maior da tela (antes era a área ativa, que
  pelo popover seria o próprio header Info); sem 3D View, grava a janela. Jogo em Standalone (processo
  separado, `AnastacioRuntime`) agora também é gravado, veja abaixo.
- Gravação do Standalone automática: o núcleo (PBOs, fila, encoder, cursor) saiu de `wm_screencast.c` para
  `blenkernel/intern/screencast.c` (`BKE_screencast.h`), usado pelo editor e pelo runtime. Com o editor
  gravando e `Record Standalone Player` ligado (padrão), `wm.blenderplayer_start` passa
  `RANGE_SCREENCAST_FILE/_FPS/_CRF/_CURSOR` ao runtime, que grava a própria janela desde o 1º quadro até sair
  (`GPG_Canvas::SwapBuffers`, encerra em `GPG_ScreencastEnd` antes de fechar a janela; sobrevive a restart e
  troca de arquivo do jogo). Arquivo `<blend>_standalone_<data-hora>.mp4` na mesma pasta. Enquanto o
  Standalone roda, a gravação do editor fica pausada (`WindowManager.screencast_paused`, tempo fora do
  vídeo). `Play Last` abre a mais recente das duas. Testado em background (janela escondida do Cook): vídeo
  1280x720 com a imagem do jogo; falta teste com janela.

## 2026-10-20 - Idiomas do jogo (Range.locale) e atlas de texto

- `Range.locale` (puro Python, `scripts/modules/range_locale.py`, ligado pelo `initGamePython`): tabela
  `//locale/translations.csv` (key + uma coluna por idioma BCP 47; colunas `context`/`note`/`_x` ignoradas) e
  `//locale/locale.json` (base, nomes, `font`/`atlas` por idioma; `atlas: "-"` = sem atlas). Reserva
  `pt-BR → pt → base → chave`; `tr(key, **fmt)`; idioma do sistema na 1ª abertura; escolha em
  `globalDict["locale.language"]`; `onChange`.
- Curve: `locale_key[64]` (Translation Key) e flag `CU_LOCALE_FONT` (Language Font). `KX_FontObject` aplica o
  idioma na hora (`Range.logic._setLocale` percorre as cenas), no `ProcessReplica` e no desenho; atlas vem de
  `m_atlasCurve` (próprio ou de outro Curve). Python novo: `font`, `atlas`, `translationKey`, `useLanguageFont`.
- Editor: painel Text ▸ Translation e Scene ▸ Localization (`bl_operators/anastacio_locale.py`): criar/abrir
  a tabela, chaves a partir dos textos, `Generate Language Atlases` (Curve `LocaleAtlas_<código>` com fake user,
  só as letras da coluna + dígitos/pontuação).
- Bitmap Atlas: "Generate from Font" não gera .json (dados ficam no .range); botões Show JSON (Text Editor),
  Open Folder e Copy Atlas to Selected; Load aceita `X.json` + `X.png`.
- Testado com `--server` (cena gerada): troca de texto/atlas, reserva, `addObject` já traduzido, normalização.
  Sem teste com janela ainda.
- RolimaRacer migrado: `Tools/migrar_idiomas.py` gerou a tabela (129 chaves), `_language.py` virou ponte
  (mesmos textos conferidos chave a chave), `Language Font` em 169 textos, russo com Roboto-Regular.
- Fluxo simplificado (painel Scene ▸ Game Languages em passos): `Enable Languages` (idioma dos textos +
  primeira tradução, já prepara a cena), lista de idiomas com "N to translate"/"done", `Add/Remove
  Language`, `Translate All Texts` (chave sem acento a partir do texto; textos iguais dividem a chave),
  `Preview Language` na viewport (guarda o original em `_locale_base_body`; `save_pre` restaura, o .range
  nunca salva a prévia), `Guide`. Componente `range_language.LanguageButton` (clique/tecla → próximo,
  anterior ou um idioma; mostra o nome nativo) e `Range.locale.next/previous/step/native_name` (também
  como controlador Python em modo Module). Guia em `docs/idiomas.md`. Testado em background (editor + `--server`).

## 2026-10-19 - Fresnel, Z Offset e Shadow Casting Alpha no modo Game

- Fresnel da transparência (`raytrace_transparency.fresnel`/`fresnel_factor`): mesma fórmula do Blender Internal
  (`shade_alpha_fresnel`); precisa de Transparency e blend Alpha/Alpha Sort. Painel Transparency do Game.
- Z Offset: o jogo já aplicava só o termo de inclinação (nada em decal visto de frente); agora soma
  `-zoffs * 8` unidades de profundidade (`RAS_MaterialBucket::BindNode`). Viewport GLSL faz igual (`gpu_draw.c`).
  Muda o resultado de materiais antigos com Z Offset diferente de zero.
- Shadow Casting Alpha (`shadow_cast_alpha`): no jogo o caster vai para o bucket de sombra alfa e descarta
  em pontilhado (`shadow_cast_alpha_discard`, uniform `GPU_DYNAMIC_SHADOW_DEPTH_PASS`); o filtro suave vira
  sombra parcial. Não vale com Variance. Viewport: prévia por stipple 25/50/100% (`draw_mesh_object`).
- Cena `tools/debug/cenas/criar_cena_material_bi_game.py` (uma opção por layer); aceita no jogo.

## 2026-10-19 - Material Shadows Only no modo Game (shadow catcher)

- `use_only_shadow` agora funciona no GLSL do jogo (antes só no Blender Internal): o material mostra só a
  sombra recebida, na cor difusa, com alpha = alpha do material × sombra (maior valor entre as lamps com sombra).
  Precisa de Alpha Blend; o painel Shadow do Game mostra a opção e avisa se o blend for Opaque/Clip.
- `gpu_material.c` (`shade_one_light`/`GPU_shaderesult_set`), GLSL `shade_only_shadow_amount`/`_result`,
  campo `onlyshadow` no `GPUShadeResult`. Só materiais clássicos (não nós).
- Cena de teste `tools/debug/cenas/criar_cena_shadow_catcher.py`: layers 1-3 com jeitos manuais
  (Multiply, cor do horizonte, Multiply com borda esmaecida) e layer 4 com a opção nativa; aceita no jogo.

## 2026-10-19 - Range Trace, fase 3 (frames lentos e trilho de câmera)

- Módulo `frames`: uma linha por frame com o tempo das categorias do profiler (`KX_KetsjiEngine`, ao lado do
  `KX_EngineProfiler::EndFrame`). O relatório lista os frames lentos com as categorias e o que carregou junto.
- Módulo `sector`: `RANGE_TRACE_RAIL=cena;curva;objeto;segundos[;reverse]` põe uma câmera na curva com
  velocidade constante em tempo real, olhando 8 m à frente, VSync desligado, e fecha o jogo no fim
  (`KX_Scene::StartTraceRail`/`UpdateTraceRail`, reaproveitando `BL_SampleCutscenePath` e
  `EvaluateCutscenePath` da Cutscene). Relatório: 40 trechos, faixa e mapa de calor visto de cima.
- Launcher: módulos `frames` e `sector`, cartão do trilho (cena, curva, câmera, segundos, inverter sentido)
  lembrado por jogo; RolimaRacer já vem com `Pista_1`, `Pista1.009`, `Camera_debug_track`.
- Ajustes depois do teste no RolimaRacer: viewports das outras câmeras desligadas no trilho (tela dividida);
  olhar suavizado (média de 4 a 16 m à frente e constante de 0,15 s; o maior tranco de giro caiu de 27°
  para menos de 4° por frame); início do trilho no CheckPoint com `Finish Line` (`auto`), num objeto pelo
  nome ou no primeiro ponto; campo Início no launcher. No RolimaRacer o `auto` acha a `LinhadeChegada`.
- Testado com um `.range` gerado (círculo de 50 m, `--server`): a câmera percorre a curva nos dois sentidos,
  olhando ~4° para dentro da curva (o esperado para 8 m à frente), e o jogo fecha no fim.

## 2026-10-19 - Range Trace, fase 2 (launcher com janela)

- `tools/debug/range_trace_launcher.py` (tkinter) e `abrir_trace_launcher.bat`: escolhe jogo, executável,
  saída e módulos, lembra as escolhas em `%APPDATA%\AnastacioEngine`, roda o jogo e abre o relatório ao fechar.
- Editor: Game > Range Trace... (`bl_operators/anastacio_trace.py`) abre o launcher com o arquivo atual.
- `usage` validado com janela no RolimaRacer (313 `visible`, 182 `image`).
- Evento `object` ganha `visible`, `navmesh` e `static_batch`; o relatório separa os invisíveis por design
  (navmesh, colisores) da lista de nunca desenhados e marca os objetos com Static Batch.

## 2026-10-19 - Range Trace, fase 1 (o que carrega e o que é desenhado)

- Novo `CM_Trace` (`gameengine/Common`): `RANGE_TRACE=<pasta>` grava `trace.jsonl`, módulos por
  `RANGE_TRACE_MODULES`. Módulo `load` em `BL_Converter.cpp` (catálogo de objetos, malhas, materiais com
  imagens e deixados de fora por cena; tempos de conversão/texturas/shaders; On Demand convertido no jogo).
  Módulo `usage` em `KX_Scene::CalculateVisibleMeshes` (primeira vez visível na câmera ou sombra) e gancho
  `GPU_profile_image_hook` (`gpu_shader.c`/`gpu_draw.c`) para cada imagem enviada à GPU.
- `tools/debug/relatorio_trace.py` (HTML + `resumo.md`) e `tools/debug/abrir_trace.bat`. Guia: `docs/range-trace.md`.
- Teste `--server` no RolimaRacer: 5 cenas, 533 objetos, 187 malhas, 60 materiais, 35 imagens registrados;
  sem janela nada é desenhado, então o módulo `usage` falta conferir no jogo com janela.

## 2026-10-18 - Release 0.5.3 (Windows)

- Versão 0.5.3 com as correções do módulo Effects (sons da chuva) e das partículas/chuva no WebGL2.
  Zips Windows e RangeArmor montados e conferidos; Linux (engine e RangeArmor Linux) fica para depois.
  Detalhes em `docs/release-0.5.3.md`.
- Linux 0.5.3: pacote da engine e primeira RangeArmor para Linux (`tools/linux/stage_rangearmor_linux.sh`);
  `test_weather_sounds_auto.py` ajustado ao módulo Effects completo de `79556dad`.

## 2026-10-18 - .cooked de outro compilador quebrava a colisão

- O BVH de malha estática no `.cooked` é o `btOptimizedBvh` gravado com `serializeInPlace` (layout de memória
  do compilador). Cache do MSVC lido no GCC (ou o contrário) era aceito e os objetos atravessavam o chão
  (tutorial Logic Bricks 2.0 no Linux com o `.cooked` commitado do Windows). `CcdPhysicsController.cpp`:
  versão do BVH = compilador + `sizeof(btOptimizedBvh)`, BVH estranho é recusado e refeito;
  `CcdCookedData::AddBvh` substitui a entrada recusada para o `.cooked` ser regravado.
- Teste: cache do Windows no runtime Linux, 1ª execução `bvh 1 loaded, 1 used, 1 new` e Player em z=0,5;
  2ª execução reaproveita (`0 new`). `docs/logic-bricks-2-tutorial.cooked`/`.blend1` fora do git, `*.cooked` no `.gitignore`.

## 2026-10-18 - 0.5.2 no Linux: sons de efeito fora do pacote

- `creator/CMakeLists.txt` não instalava `release/datafiles/sounds/`: chuva, trovão, explosão e destruição
  ficavam fora do pacote (Linux e, sem cópia manual no `build/bin`, também o zip Windows). Regra de
  `install` adicionada; `container-build-22.04.sh` confere `sounds/effects/trovao1.wav` no tar.
- Pacote Linux 0.5.2: `ctest` 10/10 e testes Python do pacote extraído; detalhes e avisos para o Windows
  em `docs/release-0.5.2.md`.

## 2026-10-18 - Sons automáticos com projeto na mesma unidade da engine

- Projeto na mesma unidade da engine: o save deixava o caminho do som da engine relativo e
  `ensure_weather_sounds` só copiava caminhos absolutos, então chuva/trovão ficavam apontando para dentro da
  engine (sumiriam no jogo exportado). Agora resolve o caminho antes de copiar para `sounds/`.
- `bpath.c`: slots vazios do World Sound não são mais remapeados (viravam `//..\..\` e pareciam
  preenchidos); `_slot_path` limpa esse caminho em arquivos já salvos.
- Pacote Windows sem o `AnastacioEngine_BakeTest.exe`. Teste: `tools/test_weather_sounds_auto.py` em C: e D:.

## 2026-10-18 - Preparação da 0.5.2

- Versão 0.5.2 em `ANASTACIO_VERSION_STRING`, About (`wm.py`), `stage_release_windows.py` e
  `container-build-22.04.sh`. Novidades, testes feitos e checklist do Linux em `docs/release-0.5.2.md`.
- `script_load_modules` (ctest) falhava ao importar `anastacio_video` (só existe no jogo, importa `Range`):
  entrou na BLACKLIST de `bl_load_py_modules.py`. ctest 15/15.

## 2026-10-18 - Liga/desliga o som de cada efeito e variação dos one-shots

- Checkbox de som em todo efeito que toca som da engine, ligado por padrão (arquivos antigos seguem com som):
  World Rain e Lightning (ícone de alto-falante no cabeçalho, `use_rain_sound`/`use_rain_lightning_sound`,
  bits em `World.weather_sound_mute`, ex-`rain_aura_pad`), Empty Lightning (`lightning.use_sound`,
  `LIGHTNING_NO_SOUND`) e Explosive/Destruction (`use_sound` no `RangeExplosiveSettings`, `EXPLOSIVE_NO_SOUND`).
  O preenchimento automático respeita esses checks e agora só preenche os slots do evento que falta.
- `KX_AudioManager::PlayEvent`: cada one-shot (trovão, explosão, destruição) sai com pitch ±12% e até 15% mais baixo.
- Teste: `tools/test_weather_sounds_auto.py`.

## 2026-10-18 - Som de chuva e trovão automático

- Chuva ou raio ligados (World Weather ou Empty Lightning) sem som no Effects ficavam mudos: o som só
  entrava pelo Add Sound Module > Effects ou Use Engine Sounds. Agora `save_pre`, `save_post` e
  `game_pre` chamam `ensure_weather_sounds()` (`properties_world_sound.py`): cria o módulo Effects ou os
  slots que faltam, põe `chuva.wav`/`trovao1-3.wav` da engine e copia para `<projeto>/sounds`; num
  arquivo novo o caminho relativo é gravado a partir do segundo salvamento. Slots já preenchidos não mudam.
- Teste: `tools/test_weather_sounds_auto.py`. Teste das categorias da aba Object
  (`tools/test_object_render_categories.py`) confere Network e Activity Culling na aba Game.

## 2026-10-18 - Highlight Active: realce ao vivo dos logic bricks

- Com o jogo embutido rodando, o Logic Editor acende os bricks que disparam (moldura laranja) e os fios
  entre bricks acesos, com um pulso correndo do sensor ao atuador; apaga em 0,4 s. Funciona com o
  cadeado aberto ou fechado (travado, só o Logic Editor redesenha e não é escurecido; até 30 Hz).
- Regras: sensor aceso enquanto positivo; controlador quando disparado por sensor positivo ou enquanto
  um sensor seu segue positivo e um atuador dele roda; atuador enquanto roda sem evento negativo.
- `SCA_ILogicBrick::m_blenderBrick` liga o brick do jogo ao do Blender (conversores); o
  `SCA_LogicManager` junta os pulsos e `LA_BlenderLauncher::LogicDebugCollect()` entrega a
  `WM_logic_debug_pulses()`. Só coleta com um Logic Editor aberto e o toggle ligado.
- Toggle `Highlight Active` no header (`SpaceLogic.show_highlight_active`, bit negado
  `SLOGIC_HIGHLIGHT_ACTIVE_OFF`, ligado por padrão). Cena: `tools/debug/cenas/criar_cena_logic_realce.py`.

## 2026-10-17 - Qualidade do SSGI nativo

- Traçado: amostragem intercalada Bayer 4x4 (Keller & Heidrich) no lugar do ruído estático, jitter de passo
  por raio, fade suave no raio máximo, clamp de fireflies e bias proporcional à profundidade.
- Composição: joint bilateral upsampling (Kopf 2007) com posição sub-texel; filtro guiado por normal e plano.
- Nova opção `ae_ssgi_denoise` (Off 3x3 / Normal 5x5 / High 7x7) em `ge_SSGIParams[1].w`; presets Low/Medium
  usam High, High/Ultra usam Normal. Teste: `criar_cena_ssgi.py -- out.range modo denoise`; prints com `SSGI_SHOT`.

## 2026-10-17 - SSGI nativo mais fácil de usar (branch local `feat/ssgi-facilidade`)

- Painel: as 8 regras genéricas viraram só problemas que bloqueiam o efeito, cada um com correção (botão
  para PBR Shading Nodes, slots a liberar), mais `Check Scene` com contagem total/aproximado/excluído e
  motivo por material. `Limits` ficou com espaço de tela e desktop.
- `gpu_material.c`: `gpu_ssgi_closure()` desce por Mix/Add Shader (`ssgi_mix_closure`/`ssgi_add_closure`
  em GLSL; o fac reaproveita link, uniform dinâmico do Fast Shader Loading ou constante). Transparent/
  Holdout contam zero. Nova opção `ae_ssgi_approximate` (padrão ligada): closures sem saída de SSGI
  recebem GI pela cor (`ssgi_approximate_closure`), especulares só bloqueiam raios. Alpha Clip aceito
  (nós e material simples). O slot de cor linear passou a ser sempre a saída Surface.
- `LA_Launcher.cpp`: `GPU_material_ssgi_disabled_reason()` registra por que o SSGI ligado não roda.
- Validação: `criar_cena_ssgi.py` ganhou modos `graphs`/`graphs_strict`. RX 6800M, 640x480: `standard`
  1488 pixels válidos/1435 elegíveis; `graphs` (Mix, Mix+Transparent, Add, Toon com Alpha Clip, Glossy)
  1488/1344, GI nas paredes Mix (deltas vermelho/branco > 0), sem erro GL; `graphs_strict` 1348/1297
  (Toon/Glossy excluídos). `Check Scene` bate com o runtime. Aviso conferido com PBR desligado.
  Falta aceite visual.

## 2026-10-17 - CSM Auto Bias também para Variance (VSM)

- `gpu_lamp_csm_auto_bias()` deixou de excluir VSM: a mesma análise de "um texel de profundidade por
  cascata" agora alimenta o parâmetro que o shader VSM já usava (`test_shadow_vsm()` lê `bias` como
  10x o piso de variância). Para Simple o cálculo continua igual (bias de profundidade + slope bias
  em espaço de mundo); para Variance, o piso de variância vira `10 * texelDepth²`, onde `texelDepth`
  é o mesmo erro de profundidade de 1 texel usado no slope bias do Simple. Slope bias continua sem
  efeito no VSM (shader não recebe esse parâmetro).
- UI (`properties_game.py`): `Auto` no painel Bias agora aparece com CSM ligado em qualquer tipo de
  buffer (antes só Simple); com Auto ativo em VSM, `Bleed Bias` continua editável ao lado de
  `Strength`. A tabela de cascatas também passou a mostrar o Bias manual por cascata quando Auto está
  desligado, mesmo em VSM (antes a coluna ficava sempre oculta para VSM, mas o shader já lia esse
  valor por cascata).
- Fatores ainda sem validação visual (igual ao Auto Bias do Simple, 2026-10-16).

## 2026-10-17 - Splash: apoio à Anastacio Engine e à Range Engine

- A barra inferior da splash agora exibe dois botões Patreon identificados separadamente: `Patreon Anastacio`
  aponta para `https://www.patreon.com/cw/AnastacioEngine` e `Patreon Range` aponta para
  `https://www.patreon.com/rangeengine`, preservando o apoio ao projeto original do qual o fork deriva.

## 2026-10-16 - Use Shadow: seções e painel próprio do CSM

- `Buffer & Quality` deixou de ser botão laranja e virou seção em box dentro do painel, com seta sem relevo.
- `Cascaded Shadow Mapping` virou painel próprio (`DATA_PT_shadow_csm_game`, só Sun), com seta nativa e o
  liga/desliga no cabeçalho como o `Use Shadow`, e o conteúdo dentro de um box.
- Subpainéis `bl_parent_id` foram testados e descartados: no editor Properties saem sem seta, com cabeçalho
  quebrado e fora do box.

## 2026-10-16 - Painel Use Shadow reorganizado

- Ordem nova: geral (com rótulo `Color:`), alcance (Clip Start/End e Frustum Size), Buffer & Quality e
  Cascaded Shadow Mapping, com o liga/desliga do CSM no próprio cabeçalho.
- Tamanho (e Bias, sem Auto Bias) de cada cascata numa tabela Near/Medium/Low; os sliders de proporção mudam
  de nome conforme Camera/Light e um aviso diz qual cascata vai até o Clip End/Frustum Size.
- Removidos da UI os controles sem efeito: `CSM Shadow Soft Medium/Low` (`csm_soft` não é lido pela engine) e
  Samples/Soft com CSM ligado (o shader das cascatas lê uma amostra; filtros PCF mostram aviso).

## 2026-10-16 - CSM: performance no modo Camera, 2 ou 3 cascatas e Auto Bias

- Queda de FPS no modo Camera com Static Shadow: as cascatas seguem a câmera, então o cache estático era
  re-renderizado todo frame em movimento (passada estática + blit + dinâmica, mais caro que sem cache). Agora,
  enquanto a cascata se move, desenha-se uma passada simples; o cache só é refeito com a matriz parada.
- O ajuste de Z às caixas dos casters (modo Camera) passou de 3 varreduras por frame (uma por cascata) para
  uma por luz; o modo Light não faz essa varredura.
- Cache de matrizes CSM: a chave agora inclui a projeção da câmera (lente/zoom/aspecto) e usa
  `GetCameraToWorld()` como o cálculo (VR).
- Nova propriedade `csm_cascade_count` (2 ou 3, bit `LA_CSM_TWO_CASCADES` em `csm_flag`): com 2 a Medium
  vai até o Clip End/Frustum Size, só 2 passadas, e a Low fica com buffer de 16 px espelhando a Medium.
- Novo `use_csm_auto_bias` (bit `LA_CSM_AUTO_BIAS`, Simple apenas): Bias = 0,5 texel de profundidade e
  Slope Bias = 1 texel por cascata, calculados no bind das matrizes; o campo Bias vira `Strength`. Os bias
  das cascatas no shader CSM passaram a uniform dinâmico. Fatores ainda sem validação visual.
- `RAS_DebugDraw::DrawCameraFrustum(persmat, color)`, já usado pelo debug colorido do CSM, entra no repositório.

## 2026-10-16 - Weather Rain: seções expansíveis

- Droplets, Ripples, Splash, Puddles, Aura e Lightning agora têm cabeçalhos horizontais expansíveis, cada qual
  com uma seta e seu próprio controle de ativação no lado direito. Ripples e Splash deixaram de dividir uma
  mesma seção e de usar colunas, para manter esse padrão visual.
- As seções vêm abertas em Worlds novos e são abertas uma vez ao carregar arquivos existentes, preservando a
  apresentação anterior até o usuário escolher quais recolher.

## 2026-10-16 - Weather Rain: Ripples e Splash lado a lado

- O painel de chuva agora organiza todos os controles de Ripples em uma coluna e todos os controles de Splash
  na coluna ao lado. Em cada cabeçalho, o checkbox do efeito e seu próprio `Only in Puddles` ficam na mesma
  linha; os avisos das game properties foram quebrados em duas linhas para caberem na nova largura.

## 2026-10-16 - CSM com referência pela câmera ou pela luz Sun

- A Lamp Sun com CSM ganhou a opção `Reference`: `Camera` mantém as três faixas de profundidade anteriores;
  `Light` cria três áreas quadradas concêntricas orientadas pela luz, com vermelho no centro, verde ao redor e
  azul como área externa definida por `Frustum Size`. Nesse modo, os limites usados para escolher a cascata no
  shader também são quadrados no espaço local da Sun, em vez de distância ao longo da câmera.
- O desenho de debug do editor e o debug do runtime acompanham a referência escolhida. Em `Light`, as caixas
  são desenhadas da maior para a menor para preservar a leitura das cores transparentes; em `Camera`, o desenho
  em fatias do frustum permanece inalterado. O painel contextualiza os controles como `Inner Size` e
  `Middle Expansion` no modo da luz.
- `RangeEngine` e `RangeRuntime` foram recompilados com sucesso após reinicialização liberar o executável do
  editor. As cenas controladas `csm-camera.range` e `csm-light.range` foram reabertas e inspecionadas com o
  editor atualizado; referência, CSM, debug, clipping e tamanho externo persistiram. A confirmação visual das
  caixas concêntricas e da propagação da sombra no jogo real permanece pendente.
- No primeiro teste visual, somente a área vermelha projetava sombra; verde e azul selecionavam a cascata,
  mas amostravam matrizes antigas ou ainda zeradas. As sub-lamps Medium/Low recebiam `viewmat`, `winmat` e
  `persmat` novos durante o passe, porém o cache de uniforms dinâmicos não incluía essas matrizes em sua chave.
  `GPU_lamp_shadow_buffer_bind_matrices()` agora invalida esse cache ao instalar cada matriz CSM. Editor e
  runtime foram recompilados, mas o teste visual mostrou que essa primeira correção não bastava.
- Instrumentação temporária na cena real `projects-teste/sombras_cascaded.range` confirmou dois casters nas
  três cascatas e profundidade escrita nos três mapas (905.216/139.490/5.253 pixels); os depth maps brutos
  mostraram a silhueta do cubo também em verde e azul. Bias efetivo (`0,005/0,0005/0,0005`), slope zero e as
  três matrizes GPU distintas também foram conferidos. O degradê observado era o blend de 10% misturando a
  sombra vermelha com uma amostra externa branca, não o parâmetro `Soft`.
- No modo `Light`, o shader agora calcula o XY de amostragem diretamente no espaço local da Sun com o half-size
  de cada quadrado (`split0`, `split1`, `Frustum Size`) e usa a matriz Near compartilhada somente para Z, já que
  as caixas concêntricas têm a mesma orientação e clipping de profundidade. Isso evita depender da matriz das
  sub-lamps para localizar a amostra; `Camera` mantém o caminho anterior. Referência, splits e tamanho externo
  passaram a ser uniforms vivos. A instrumentação foi retirada, shaders/editor/runtime recompilados, e a
  confirmação visual desta correção permanece pendente.

## 2026-10-15 - Material: filtros de painéis e conversão PBR para Classic

- As abas Object e Render do Game também receberam filtros no topo. Object usa
  `Object | Game | Transform`: relações/organização/exibição; recursos específicos do jogo; e transformações;
  do jogo. Render usa `System | Graphics`: System reúne cook/player/animações e runtime/display/VR;
  Graphics reúne shading/iluminação/pós-processamento e o Bake de Textura legado. As faixas foram incorporadas aos primeiros painéis das
  abas, evitando que a ordenação do Blender 2.79 as leve para o rodapé. Load Object with Scene, Network,
  Activity Culling e Animation Events foram reunidos na própria aba Object com Culling e LOD. O seletor do
  objeto usa somente o `Fake User` nativo (`F`), sem uma segunda caixa redundante. No Game ele é um painel
  normal `Object`; no Blender Render o seletor histórico continua sem cabeçalho. Como o Blender 2.79 exibe
  painéis reativados conforme o `sortorder` persistido na tela, a UI ganhou a opção genérica de painel
  `PIN_TO_TOP`; o painel superior de Object a utiliza para permanecer acima de todos os grupos mesmo depois
  de alternar os filtros.
- Na aba Texture do Game, o preview deixou de ser um painel vertical separado e passou para dentro da caixa
  `Texture`, ao lado da lista de slots. Um botão de visibilidade na coluna de ações mostra ou oculta o
  preview; ele inicia oculto e a lista recupera a largura disponível. Os controles nativos
  Texture/Material/Both, forma do material e alpha continuam disponíveis no preview integrado.
- No Game, `Material Slot` e `Material Preview` compartilham uma única caixa no topo: lista de slots à
  esquerda e preview sem título à direita. Os seletores do preview ficam em uma linha sob a imagem; os
  botões de adicionar, remover, menu e ordenar slots formam uma coluna à direita do preview. Abaixo dessa
  faixa, o seletor do material, o vínculo, os tipos de superfície e o nó ativo usam toda a largura da caixa.
  Um botão de visibilidade abaixo do menu mostra ou oculta o preview; ele inicia oculto e a lista de slots
  ocupa toda a largura disponível, preservando a coluna de ações à direita.
  O painel vertical de preview é ocultado nesse modo para não duplicar o conteúdo; no Blender Render ele
  permanece na organização histórica.
- Uma faixa no rodapé de `Material Slot`, antes de todos os subpainéis, filtra a aba em três grupos, na ordem
  `Surface`, `Game` e `Setup`: Surface reúne pipeline, Diffuse, Specular, Shading, Node Shader e Subsurface;
  Game reúne Game Settings, Foliage, Options, Shadow e Transparency; Setup reúne PBR, Quick Material,
  conversão, atlas e preview. No Blender Render a organização histórica
  não muda. A faixa inicialmente registrada como painel sem cabeçalho foi movida para o próprio Material Slot
  porque o Blender 2.79 ordena painéis sem cabeçalho no final da coluna.
- O painel agora se chama `Convert Material` e mostra `PBR` e `Classic` lado a lado. O novo operador
  `material.to_classic_nodes` converte Principled, Emission e Glass reconhecíveis para uma árvore Classic com
  `Extended Material`; leva valores de cor/metallic/roughness/specular/alpha/emit e cria texture slots para
  Base Color, Specular, Roughness (invertida para Hardness), Normal/Bump, Alpha e Emit, preservando o UV Map.
- Texts anexados em Vertex/Geometry/Fragment permanecem no material. Múltiplos Principled/imagens e recursos
  sem equivalente (Subsurface, Anisotropic, Sheen, Clearcoat, Transmission e Vertex Offset por nós) geram
  aviso explícito de aproximação; a operação confirma antes, participa do Undo e alinha a cena para Classic.
- `tools/test_material_classic_and_categories.py` validou cinco mapas, valores, alpha, emissão, os três Texts,
  os três filtros e os dois botões. A cena salva abriu no `AnastacioRuntime`, executou cinco frames com os
  shaders anexados e gravou `material_classic_runtime.ok`.

## 2026-10-15 - Quick Material separado da conversão PBR

- `Quick Material` voltou a ter título próprio e foi dividido nas caixas `Create Material` (texture set e
  material pronto) e `Layered Materials` (mistura por máscara e superfícies molhadas/reflexivas). Todos os
  cabeçalhos internos agora usam ícone; os ícones repetidos foram retirados dos botões PBR/Classic.
- `Convert Material to PBR` virou um painel expansível independente, fechado por padrão, com somente o botão
  de conversão dentro da caixa.

## 2026-10-15 - PBR Shading Nodes também na aba Material

- A aba Material do Game Engine ganhou, imediatamente abaixo de `Material Slot`, um painel expansível
  `PBR Shading Nodes`, fechado por padrão. Dentro da caixa há somente o botão homônimo, ligado à mesma
  propriedade global usada pela aba Render; os dois controles permanecem sincronizados.

## 2026-10-15 - Conversão PBR explicita o UV Map padrão

- Ao converter um material legado, slots com coordenadas `UV` agora sempre recebem um nó `UV Map`, em vez
  de `Texture Coordinate`. O mapa indicado no slot continua tendo prioridade; quando o campo `Map` está
  vazio, o conversor grava explicitamente a primeira camada UV do mesh ativo. Se o mesh não possui UV, o nó
  ainda é criado, mas seu nome fica vazio.
- `tools/test_material_to_pbr_uv.py` cobre mapa implícito, mapa explícito e mesh sem UV. Os três casos
  passaram no `AnastacioEngine.exe` instalado em `build/bin/`.

## 2026-10-15 - Baked Lighting: interface em português

- O painel agora usa `Iluminação Pré-calculada`, com os três modos, avisos, contagem de receptores,
  cobertura do atlas, botões e dicas em português. Mensagens de progresso e de erro do bake também foram
  traduzidas.
- O antigo `Texture Bake (Legacy)` foi renomeado para `Bake de Textura (Legado)` e seu aviso direciona
  para o painel moderno em português. Os scripts de fonte e da instalação `build/bin/` foram sincronizados.

## 2026-10-15 - OpenCL bake: aviso indevido de `kernel_lamp_emission`

- Reproduzido em `projects-teste/baked_gpu.range`: o plano tem material de nós sem texture slot,
  mas isso não causava o aviso. O cubo está como Rigid Body; só o plano Static participa do bake.
- `OpenCLSplitPrograms::load_kernels` não compila os kernels split quando `use_baking` está ativo,
  mas `OpenCLDevice::wait_for_availability` tentava carregá-los assim mesmo. O erro vinha dessa
  checagem indevida; o kernel OpenCL de bake separado continuava funcionando, por isso a operação
  podia terminar com imagem válida apesar do aviso. Agora o caminho de bake ignora os kernels split.
- O executável de teste atualizado, linkado separadamente porque o editor do usuário estava aberto,
  fez AO, Static e Indirect na RX 6800M sem o aviso, todos com atlas de 256x256 e 99,98% de cobertura.
  AO na CPU teve a mesma cobertura e faixa de valores do AO na GPU. Após fechar o editor, o link normal
  ainda falhou com `LNK1104` para `bin/AnastacioEngine.exe` e removeu o executável antigo. Uma cópia
  byte a byte do executável de teste corrigido foi instalada sob o nome principal; SHA-256 idêntico.
  AO, Static e Indirect foram repetidos no executável principal, todos sem o aviso e com a mesma
  cobertura. A causa do `LNK1104` no link normal e a validação visual no jogo seguem pendentes.

## 2026-10-15 - Bake CPU/GPU: seleção explícita e erro de kernel não vira sucesso

- `GPU` desligado agora força Cycles na CPU durante o bake, mesmo se a cena estiver configurada para GPU;
  o dispositivo original e as preferências de GPU são restaurados ao final. O console informa o dispositivo usado.
- No OpenCL, selecionamos apenas uma entrada da GPU dedicada. Nesta máquina a RX 6800M aparecia duas vezes
  na lista de dispositivos e o bake anterior habilitava ambas.
- `RE_bake_engine` agora devolve falha quando o motor registra erro; o operador de lightmap verifica o retorno
  de cada passe e não salva uma imagem nova após falha. Um erro de kernel exige novo bake, preferencialmente
  com `GPU` desligado se persistir.
- Build `RangeEngine`/`AnastacioRuntime` passou (6/6). Smokes CPU Static e AO passaram; smoke OpenCL
  `Indirect + Dynamic Shadows` passou em 512x512 com light volume 20x20x5, sem aviso de kernel. A falha
  exata da cena do usuário ainda não foi reproduzida; validação visual nessa cena permanece pendente.

## 2026-10-15 - Baked Lighting moderno: interface contextual, AO e iluminação estática

- Acabamento do fluxo: `Bake Scene` mostra contagem de receptores e motivos de exclusão, deixa o controle
  `Receive Baked Lighting` visível para o objeto ativo, informa cobertura real dos pixels baked no atlas e explica
  que mover luzes ou objetos após o modo estático exige novo bake. O antigo painel virou `Texture Bake (Legacy)`
  e o X virou `Clear Baked Lighting`. O novo controle preserva o atributo legado `ae_lightmap_exclude`.
- O smoke estático foi repetido com o plano ativo e confirmou que a seleção não limita o bake da cena; também
  confirmou inclusão/exclusão por objeto e cobertura do atlas. Scripts da UI sincronizados em `build/bin`.
- `Render > Baked Lighting` agora escolhe entre `Indirect + Dynamic Shadows` (comportamento anterior e
  padrão compatível) e `Ambient Occlusion`. O painel mostra separadamente o modo do resultado atual e o
  modo do próximo bake, oculta controles sem efeito e agrupa Lightmap, Moving Objects e Advanced.
- O AO usa o atlas/UV automático existente, com `Distance` e `Strength`, restaura as configurações temporárias
  do World e não cria Light Volume. No Game PBR ele multiplica somente a parcela ambiente; luz direta,
  especular, sombras e elegibilidade para SSGI permanecem dinâmicas.
- O novo modo `Static Lighting + Shadows` grava no atlas a irradiância difusa direta e indireta com sombras.
  A marca interna do atlas distingue-o do Light Volume: somente os receptores estáticos deixam de somar
  difuso direto em tempo real; especular permanece dinâmico, e objetos móveis conservam luz direta completa.
  O Light Volume continua contendo apenas indireta/World.
- Correção posterior: o primeiro encaixe de AO/estático ampliava a assinatura GLSL do Principled e causava
  `node_bsdf_principled: no matching overloaded function` ao converter um material para PBR. A interface
  legada foi preservada; o tipo do bake passou a ser uma marca interna na amostra da lightmap. Build
  `ge_rasterizer_shaders` + `RangeEngine` passou novamente e o smoke estático passou sem erro GLSL.
- `Use in Game`, conclusão e limpeza do bake invalidam os materiais explicitamente. Arquivos antigos sem
  `ae_lightmap_mode` continuam sendo interpretados como iluminação indireta.
- Build `ge_rasterizer_shaders` + `RangeEngine` passou (105/105). `tools/test_baked_ao_smoke.py` validou bake
  256x256, RGBM grayscale, faixa 0..1, restauração do World, persistência do modo e reabertura da cena; o
  usuário confirmou o AO em Play e Standalone. `tools/test_baked_static_smoke.py` validou dois receptores
  estáticos, exclusão de objeto dinâmico do atlas, RGBM com contraste, Light Volume 1x1x1 e persistência do
  modo; `AnastacioRuntime` encerrou com código 0 e sem erros GLSL. O usuário validou uma cena simples com
  cubo e plano Static; uma cena maior com materiais variados ainda não foi testada visualmente.

## 2026-10-15 - Quick Material: conversão PBR visível no título

- O título do painel agora é `Quick Material / Convert Material to PBR`; a conversão continua no mesmo
  painel, evitando criar outro menu para um fluxo já relacionado.
- Removido o controle duplicado `Specular Color` do Quick Material; o ajuste fica somente no painel
  `Specular`.

## 2026-10-15 - World: painéis recolhíveis Sky, Sun e Night

- `Sky`, `Sun` e `Night` são painéis irmãos, cada qual com sua própria seta de expansão. `Sun` e `Night`
  preservam seus campos dentro de uma caixa; propriedades e comportamento do runtime permanecem inalterados.

## 2026-10-15 - Pacote Windows: incluir addon Anastacio Ragdoll

- A instalação 0.5.1 usada nos testes estava sem `anastacio_ragdoll.py` e
  `anastacio_ragdoll_runtime.py`, embora os arquivos existissem em `build/bin/`.
  Os dois arquivos foram restaurados no pacote local e o empacotador agora valida
  sua presença antes de gerar um novo ZIP.

## 2026-10-15 - Links de apoio: Patreon da Anastacio Engine

- Os links de suporte da splash e da tela About agora direcionam para
  `https://www.patreon.com/cw/AnastacioEngine`, substituindo o Patreon da Range Engine.

## 2026-10-14 - Web/Android: alternar controles para acessar menus

- Diagnóstico no jogo externo do itch.io: pacote usa `fps`/stick dinâmico; zonas invisíveis dos sticks
  capturam toques sobre Start. Usuário confirmou que `?touch=0` permite iniciar. O link direto também
  mudou o contexto de exibição em relação ao iframe; dimensionamento e movimento lateral da nave
  não foram diagnosticados nem alterados nesta entrega.
- `tools/web/package-web.py`: botão persistente **Controles: ligados/desligados**, canto superior
  direito com safe area e estado acessível (`aria-pressed`). Começa ligado; esconder remove controles
  e captura, solta eixos/botões/teclas virtuais e cancela o loop de olhar/zera giro acumulado.
  Religamento preserva o layout atual, incluindo escolha feita pelo botão de troca. Layout `none`,
  `?touch=0` e desktop sem toque forçado não exibem o botão. Sem alteração de C++ ou dimensionamento.
- Pacote gerado com `build-web-release/bin` e cena existente `projects-teste/pad`; execução no
  Edge headless/CDP: `verify-touch.cjs` **39/39**, incluindo toque no canvas recebido como mouse
  pelo runtime, liberação durante movimento/tiro/olhar e rotação com controles desligados.
  O painel de logs do teste cobria o ponto de toque: desabilitada sua captura apenas durante essa
  verificação. Sintaxe JS conferida; `test_range_web.py` **40/40**, `test_android.py` **21/21**.
- Documentação atualizada. `python tools/check_docs.py`: 31 erros e 73 avisos em links/mapas
  anteriores e alheios a esta mudança (incluindo `demos/revisados/README.md` ausente).
- Pendente: teste em celular real, Web no iframe do itch.io e APK. Pacotes já publicados precisam
  de nova exportação; não houve publicação ou alteração no jogo do amigo.

## 2026-10-14 - Ragdoll: componente comum, NPCs e presets passivos

- Addon 0.3 prepara rigid bodies, juntas cone-twist e anexa automaticamente
  `anastacio_ragdoll_runtime.AnastacioRagdoll`, módulo compartilhado da instalação. Geração
  inicial de autoria continua separada. Atualização não duplica componente/objetos;
  remoção e Undo/Redo incluem física, componente e pasta, preservando o controlador.
- FREE para controlador Rigid Body/Dynamic BOX e ANCHOR para assento/empty, recuperação
  automática opcional/tempo de simulação; NPC sem retorno automático permanece caído.
  Confirmação explícita de transições, flags preservadas em falha, callbacks do jogo,
  herança linear e angular, sem setters de damping/velocidade por quadro.
- Presets Duro/Equilibrado/Leve ajustam amplitudes e damping, sem músculos/motores.
  Massa total independente distribuída por volume/peso relativo; campos por osso.
- Diagnóstico: nomes de constraints ganham sufixo durante staging; runtime usa nome
  real exportado no pivô. Esta API não expõe blenderObject; bounds consultados por
  cullingBox. Cache mundial é diferido: composição de localTransform na transição.
  Escala não uniforme do controlador distorcia ciclos até NaN; agora recusada, com
  validação finita antes de escrever poses. Raycast com máscara precisa xray=1 para
  atravessar os corpos excluídos e alcançar o chão.
- Testes no player: cinco rigs simultâneos, 100 ciclos por modo, Active inicial,
  automático/permanente, herança angular/linear, obstáculo/veto e alvo inválido;
  demo de cinco humanoides/50 corpos passou 370 frames. UI validou Undo/Redo completo.
  Evidências em `debug-logs/ragdoll-runtime-final-20261014/`; guia em
  [ragdoll-runtime.md](ragdoll-runtime.md). Não houve C++ ou migração do jogo.
- FREE usa AABB com limites documentados; cápsulas/Character, compounds/terreno
  complexo, colisões configuráveis, blend, instâncias dinâmicas e Web ainda pendentes.
  A avaliação visual dos presets pelo usuário permanece aberta.

## 2026-10-14 - Ragdoll: retirada do addon antigo e escopo de NPCs

- Removido `easy_ragdoll_RangeEngine.py` do fonte distribuído e da instalação atual,
  incluindo bytecode instalado, por autorização explícita do usuário. Backup fora dos
  scripts em `debug-logs/ragdoll-legacy-removed-20261014/`; referência original de tools
  e scripts externos do RolimaRacer preservados. Novo addon Anastacio Ragdoll mantido.
- Usuário confirmou autoria em rig próprio e decidiu manter addon/componentes Python
  enquanto a API atender, sem C++ novo. Acrescentado ao plano: NPCs usando o mesmo
  núcleo, recuperação automática opcional e atraso configurável; não implementado ainda.

## 2026-10-14 - Ragdoll: collections no Outliner e acesso ao painel

- Addon Anastacio Ragdoll 0.2: collection por armature, dentro da pasta do rig, contendo
  caixas e pivôs sem mudar parenting. UID por cena e referência do rig preservam a pasta
  após renomear; atualização não duplica; remoção limpa somente pasta vazia. Conteúdo
  alheio e subpastas são preservados. Falha ao organizar descarta a pasta recém-criada.
- Painel disponível pela armature em Object Mode sem seleção de osso, e por corpo/empty
  gerado. Incluída escolha Pose/Rest Position. Usuário validou prévia em rig próprio.
- Novo exemplo desativa a constraint externa usada no teste de preservação, responsável
  pelo deslocamento do Root em Pose Mode na primeira cena. Nenhum arquivo aberto pelo
  usuário foi sobrescrito, incluindo seu novo esqueleto.
- Regressão bpy/editor em `debug-logs/ragdoll-collections-20261014`: geração, reabertura,
  Undo/Redo de atualização e remoção, callback de prévia. Mantém autoria NO_COLLISION;
  runtime comum e dois modos de recuperação continuam na próxima etapa.

## 2026-10-14 - Ragdoll: autoria por osso e validação no jogo

- Usuário confirmou bom funcionamento dos scripts corrigidos. Rodada `194141`:
  três ativações por input, duas por impacto, cinco retornos; sem erros e sem SPIKE
  nas janelas das quedas/retornos. Dados em `debug-logs/perfil-rolima-20261014-194141/`.
- Novo addon `anastacio_ragdoll.py`, fonte e cópia instalada, separado do legado:
  prévia sem criar objetos, ajustes de caixas por osso, geração em staging com rollback,
  substituição/remoção somente dos dados próprios, Undo/Redo e persistência. Primeira
  entrega de autoria, com NO_COLLISION e influência zero; runtime/juntas ainda pendentes.
- `validar_autoria_ragdoll.py` passou em geração, geometria, rollback, referências
  externas, independência de rigs, salvar/reabrir, Undo/Redo de atualização/remoção
  e execução real do callback POST_VIEW sem exceções. Aparência ainda não avaliada.
  No primeiro teste UI, `open_mainfile` dentro do script de startup invalidou contexto
  da janela; corrigido passando o arquivo na linha de comando antes de `--python`.
  Teste desativa confirmação de saída só na sessão, sem salvar preferências globais.
  C++ e `.range` original do jogo não alterados.

## 2026-10-14 - Ragdoll: auditoria e planejamento

- Implementada primeira correção nos dois scripts externos do RolimaRacer:
  inicialização completa, transições síncronas/idempotentes com sucesso confirmado,
  constraints próprias, cache por ligação real, fonte física/assento explícitos,
  remoção de damping manual por quadro e refresh sem deriva. Recuperação com falha
  mantém flags e erro explícito; fumaça não invalida retorno. Sem alteração de C++,
  do addon instalado ou do `.range` original. Validação visual ainda pendente.
- Regressão no player: 100 ciclos alternando input/impacto com trace ligado/desligado,
  Active inicial, menu, constraints extras, colisores auxiliares e referência alterada
  sem falso retorno. Quatro rigs reais: 100 ciclos por rig, simultaneamente,
  20/20/22/23 corpos, 800 transições e nenhum erro. Geradores reutilizáveis em
  `tools/debug/cenas/validar_correcao_ragdoll.py` e `validar_rigs_rolima.py`.
  No gerador isolado, arquivo de biblioteca sem bloco de startup não serviu ao player;
  corrigido exportando cena + texto do driver e regravando como mainfile completo.
- Rodada instrumentada em jogo real `perfil-rolima-20261014-192125`: confirmados os
  módulos externos por caminho/hash, três ativações por V e três por impacto, seis
  retornos e nenhum erro registrado. Componente com 20 corpos: ativação 0,436–0,538 ms,
  desativação 0,233–0,295 ms; retorno completo do controlador até 1,076 ms. Nenhum
  SPIKE nas janelas das quedas/retornos (+2 s); pausas de 1606,3 e 693,9 ms entre
  quedas, dominadas por swap. Sem prova da causa de GPU/driver ou da lâmpada de
  faísca relatada pelo usuário. Resumo e dados brutos preservados na pasta da rodada.
- Continuação: inspeção bpy confirmou quatro armatures com o componente externo
  `scripts.VehicleSystem.ragdoll_system.ragdoll.Ragdoll`, sem texto embutido de ragdoll.
  Duas rodadas em jogo real registraram picos dominados por `endframe.swap`, sem eventos
  para vincular cada pico a uma queda. Preparado diagnóstico opt-in no RolimaRacer:
  motivos/etapas, origem dos módulos, câmeras e filtros observados, ativado pelo iniciador
  com `ROLIMA_RAGDOLL_TRACE`; resumo em `tools/debug/analisar_ragdoll.py`.
- Validação: cena isolada de um osso/corpo percorreu impacto, input e retorno no player,
  com diagnóstico ligado e desligado; duas quedas, quatro transições e nenhum erro de
  observação. Exceção intencional preservada pelo decorator; AST sem instrumentação igual
  ao código anterior. Cena gerada foi reaberta e inspecionada. Próxima rodada no jogo
  completo ainda pendente. Sem mudanças em C++ ou no `.range` do jogo.
- `tools/check_docs.py` continua com 31 erros e 73 avisos preexistentes (links de demos
  e mapas desatualizados); os links novos e diffs foram conferidos separadamente.

- Localizados o fonte do addon em `source/release/scripts/addons/`, a cópia instalada
  (hash idêntico), a referência original em `tools/` e os dois scripts do RolimaRacer.
- Registrados os riscos de inicialização, seleção de constraints, retorno, damping que
  acorda corpos e contornos de culling/compound no [plano](ragdoll-modernization-plan.md).
- Proposta: prévia no editor por Python, núcleo comum e modos livre/vinculado; C++ somente
  para lacunas verificadas. Nenhum código ou `.range` alterado, nenhum build ou teste físico.

## 2026-10-14 - Correção do pacote Windows 0.5.1: operadores e splash

O ZIP publicado excluía `bl_operators/logic_to_python.py`: o filtro genérico de logs no
empacotador removia qualquer arquivo cujo nome começasse por `log`. Como o
`bl_operators/__init__.py` ainda importa esse módulo, a inicialização Python abortava com
`KeyError: 'logic_to_python'`, deixando a tela inicial incompleta e emitindo erros RNA.

- `tools/stage_release_windows.py` agora exclui somente os nomes de logs, preserva
  `logic_to_python.py`, não leva `__pycache__` e valida todos os módulos declarados pelo
  `bl_operators/__init__.py` antes de compactar.
- O `AnastacioEngine-0.5.1-windows-x64.zip` foi remontado de `build/bin/`, extraído e
  aberto a partir da cópia extraída; a validação dos módulos de startup passou.

## 2026-10-13 - Link da comunidade Discord da Anastacio Engine

Os links Discord da tela inicial e do menu About do editor agora apontam para
`https://discord.gg/AsbjKgh4E`.

## 2026-10-14 - Linux: ícone do cubo dourado no menu e dock

- O pacote e o instalador de atalho Linux agora usam o mesmo cubo dourado do
  recurso do executável Windows e do ícone de janela X11. O antigo ícone
  vermelho `range-engine.png` deixou de ser incluído no pacote.
- `AnastacioEngine.desktop` declara `Icon=AnastacioEngine`; ao executar
  `install-desktop.sh`, o PNG é registrado em
  `~/.local/share/icons/hicolor/256x256/apps/AnastacioEngine.png` (ou no
  equivalente de `XDG_DATA_HOME`). O instalador aceita tanto o nome-fonte
  legado `RangeEngine.desktop` quanto o arquivo já renomeado no pacote.

## 2026-10-14 - Linux: executáveis AnastacioEngine e AnastacioRuntime

- O desktop Linux agora segue o Windows: os alvos CMake internos `RangeEngine` e
  `RangeRuntime` produzem `AnastacioEngine` e `AnastacioRuntime`. Web/Android/macOS,
  APIs e formatos continuam com os nomes de compatibilidade anteriores.
- Atualizados pacote portátil, atalho do desktop, quickstarts, teste de rede e RangeArmor.
  O RangeArmor prefere o nome novo no Linux e continua aceitando `RangeRuntime` em
  projetos antigos, sem alterar caminhos personalizados.
- Os dois presets Linux foram reconfigurados, recompilados e instalados. `AnastacioEngine
  --background --version` passou; o player novo respondeu com a ajuda esperada sem arquivo.
  A suíte Python do RangeArmor passou (13 testes). O teste Rust do launcher não rodou nesta
  máquina porque `cargo` não está instalado.
- Pacote de validação local, sem `web/`: `build-linux/dist/AnastacioEngine-0.5.1-rename-test-linux-x86_64.tar.xz`.
  SHA-256 conferido após extração; contém os dois binários e `AnastacioEngine.desktop`, sem
  `RangeEngine`/`RangeRuntime`. O editor e player extraídos abriram pelos nomes novos.
- Durante a validação, o empacotador passou a executar `ldd` com `lib/` do staging no
  `LD_LIBRARY_PATH`; sem isso a própria `libpython` copiada podia gerar falso “not found”.

## 2026-10-13 - Web: PNG no wasm32 e runtime release carregam a cena

`ImBuf` contém `double ppm[2]`, mas `IMB_allocImBuf` o criava por `MEM_mallocN`; no caminho lock-free do wasm32 a alocação pode ter só 4 bytes de alinhamento, e a primeira escrita de `ppm` em `IMB_initImBuf` abortava como `alignment fault` no decoder PNG. A struct agora usa `MEM_mallocN_aligned(..., 8)` (liberação normal por `MEM_freeN`). Reconfigurado o preset Linux release, o `RangeRuntime` recompilou e o pacote da `WEB_TESTE_2D.range` passou no Chrome headless: Python inicializou, a cena converteu 34 objetos, carregou texturas em 90 ms e compilou oito materiais sem aborto. Falta teste jogável/visual antes de incluir `web/` num novo pacote Linux.

## 2026-10-13 - Release 0.5.1 Linux: pacote sem web/, testes e pacote

Testes do pacote de release 0.5.1: `ctest` completo (10/10, ver entrada do bevel abaixo) e a suite
`tools/tests/web_profile` (133/133, 4 skip esperados por falta de JDK/Android SDK/Node). Dois bugs achados e
corrigidos no caminho: `script_load_modules` usava `bpy.utils.register_module` (não existe neste `bpy.utils`;
trocado por `register_class`) e um teste do `web_profile` apontava para
`projects-teste/teste-editor-web/criar_m1c_nos.py`, removido do versionamento desde `794225d0`; o gerador de
cena foi recuperado do histórico para `tools/debug/cenas/criar_cena_m1c_nos.py` (local correto para geradores
versionados) e o teste atualizado. `tools/linux/package-runtime.sh` gerou
`AnastacioEngine-0.5.1-linux-x86_64.tar.xz` com `SKIP_WEB=1` (ver item aberto em
[roadmap.md](roadmap.md#web-webglwebassembly): preset `web-runtime-release` só compila no Windows/WSL,
faltando aqui o Python wasm32 cross-compilado); o pacote Linux saiu sem `web/`, então Export Web/Build APK
ficam indisponíveis nessa cópia especificamente.

## 2026-10-13 - Bevel: resultado não-determinístico em vértice com muitas arestas

`ctest bmesh_bevel` falhava de forma intermitente (~1 em 6 execuções) no caso `Bentstar_test` (10 arestas
convergindo num vértice), por "Vertex Coordinate Mismatch". `adjust_offsets` (`bmesh_bevel.c`) percorria
`bp->vert_hash` (GHash indexado por ponteiro `BMVert *`) para decidir por qual vértice começar a caminhada
de cada cadeia/ciclo de offsets; a ordem de iteração de um GHash por ponteiro depende do endereço de alocação
e não é reprodutível entre execuções, e o ponto de partida do ciclo muda o arredondamento final do float
(dentro da tolerância apertada do teste, `FLT_EPSILON * 60`). A própria `BM_mesh_bevel` já evita esse problema
em outro trecho (comentário no código: usa `BM_ITER_MESH`, ordem determinística por índice do vértice, em vez
de `GHASH_ITER`); `adjust_offsets` passou a fazer o mesmo na primeira passada (a sensível à ordem), recebendo
`bm` como parâmetro. Testado: `ctest -R bmesh_bevel` 10/10 em execuções separadas, suite completa 100%.

## 2026-10-13 - Release 0.5.1: ORM Occlusion por canal e versão

`ANASTACIO_VERSION_STRING` e o splash (`wm.py`) foram para `0.5.1`. A Occlusion (canal R) do "RGB to ORM"
sobrescrevia Diffuse Ref, Specular Intensity e Ambient ao mesmo tempo, sem opção de restringir a um
subconjunto, mesmo quando a textura tinha `mapto` ligado nas três por outro motivo. `MTex.orm_occlusion_to`
(novo campo, reaproveita o byte de padding existente em `MTex`) deixa escolher quais das três influências
recebem a Occlusion; default e migração de arquivos antigos preservam o comportamento anterior (as três
ligadas). UI em `properties_texture.py` (checkboxes "Diffuse"/"Specular"/"Ambient" sob "ORM").

## 2026-10-13 - Sombra colorida no Sun com cascatas

No Sun com CSM (`vitral_csm.range`) só apareciam fios coloridos na base dos vidros, sem a mancha no chão.
Visto da luz, o vidro é uma faixa de poucos texels no alvo de cor (meia resolução, e cada texel da cascata
cobre muito chão); o filtro linear misturava a profundidade dele (alpha) com o 1.0 limpo em volta, e o vidro
"ficava atrás" do chão. `shadow_color_tint` agora lê a profundidade dos 4 texels com `texelFetch`, ignora os
limpos e usa o caster mais distante (o mais próximo pintava o próprio vidro inclinado). Conferido por
screenshot: CSM com mancha no chão; Sun sem CSM, Spot e cena legada iguais a antes. Resta um serrilhado
pequeno na borda do vidro no CSM.

## 2026-10-13 - SSGI não corta mais vidro transparente

Com SSGI ligado, vidros em Alpha Blend sumiam pela metade, com borda em degraus (`vitral_sun.range`). A
composição (`RAS_SSGIImage2DFilter.glsl`) trocava o pixel pela cor linear do opaco + GI, e essa cor não tem
o que foi desenhado por cima; a troca era decidida por bloco de meia resolução. Agora soma só a diferença
que o GI causa (`scene + display(linear+gi) - display(linear)`). Conferido por screenshot: vidros inteiros
com SSGI, sem os quadradinhos soltos.

## 2026-10-13 - Release: template Android e pasta web/ no pacote

Usuário da 0.5.0 não conseguia gerar APK: `range_web/android.py` só achava o template em
`tools/android/webview-template` (árvore de desenvolvimento) e o zip não o trazia. O tar Linux da 0.5.0 não
tinha `web/` nenhuma (Export Web também quebrado no Linux).

- `android.template_dir()` procura também `web/android-template/` ao lado do executável.
- `tools/stage_release_web.py` monta `web/runtime`, `web/tools` e `web/android-template` (só arquivos do git;
  ~55 MB, quase tudo o runtime). `tools/linux/package-runtime.sh` passa a chamá-lo; no Windows é passo do
  procedimento em `docs/distribution-0.1.md`.
- Testes (2026-10-13): `test_android.py` (21, inclui layout da release); zip 0.5.0 extraído com o `android.py`
  novo e `web/` montada pelo script gerou o APK por `engine_android_export.py` (12/12). Build Linux com o
  script ainda não rodado.

## 2026-10-13 - Export: jogo publicado sem overlays de depuração

Um usuário publicou o jogo Web com o painel de framerate/profile ligado (flag salva na cena, não do export).

- **Web**: `package-web.py` passa `-g show_framerate/show_profile/show_properties/show_render_queries = 0` ao
  player no `index.html`; `--debug-overlays` mantém o que está no `.range`. Painel Web ganhou "Keep debug
  overlays" (desligado por padrão). O `.range` não é alterado.
- **Desktop** (RangeArmor e Save As Runtime): `export_debug_overlays_off` (`bl_operators/wm.py`) desliga
  Framerate/Profile e Debug Properties só durante o salvamento da cópia (`.rasec`/runtime) e os religa depois;
  mesma opção "Keep debug overlays" nos dois. Physics Visualization fica de fora (o player não lê `-g show_physics`).
- Testes (2026-10-13): cópias salvas em background saem com as flags desligadas (ligadas com a opção) e a cena
  volta ao estado anterior; no Chrome headless o mesmo `.range` (overlay ligado) roda sem o painel no pacote
  padrão e com o painel usando `--debug-overlays`.

## 2026-10-13 - Linux: OpenColorIO 2.x, FFmpeg 5+, Ctrl+C no player e imgui.ini

Trazido do branch `claude/project-thread-q8gfb3` (trabalho de 2026-10-04 que nunca tinha entrado no `main`).

- **OpenColorIO 2.x** (`intern/opencolorio`, caminho 2.x atras de `OCIO_VERSION_HEX`, 1.x intocado; Cycles usa
  o CPU processor da 2.x). A 2.x escondia Filmic, Film e False Color (fora de `active_views`): o wrapper lista
  todas, como a 1.x. `config.ocio`: papel `XYZ` virou `cie_xyz_d65_interchange` (a 2.x recusava o arquivo) e
  `DCIP3`, display inexistente, saiu de `active_displays`.
- **FFmpeg 5+/6.x**: shims em `ffmpeg_compat.h` so para libavcodec >= 59; `VideoFFmpeg`, `anim_movie`, `util`,
  `indexer` e `writeffmpeg` (export de video e audio) funcionam com 4.x e 6.x. Presets Linux seguem com
  `WITH_CODEC_FFMPEG=OFF` (decisao de empacotamento); ligar com `-DWITH_CODEC_FFMPEG=ON`.
- **Player: SIGINT e segundo sinal.** Mantido o mecanismo do `main` (`LA_SigTermRequested`, 570c1108); Ctrl+C
  (SIGINT) usa o mesmo caminho e um segundo SIGTERM/SIGINT mata o processo (jogo travado antes do proximo frame).
- **`imgui.ini`**: no Linux nascia um arquivo chamado `\imgui.ini`; agora `program_dir + "imgui.ini"`.
- Testes (2026-10-13): build no Ubuntu 24.04 (OCIO 2.1.3, FFmpeg 6.1, `-DWITH_CODEC_FFMPEG=ON`):
  `tools/linux/av_ports_test.py` 14/14 (views do OCIO, export MP4/MKV/OGG/AVI com audio e cores, filme como
  imagem e strip, proxy); `tools/linux/video_texture_test.py` H.264, MPEG-4, VP9 e MJPEG em ordem e em loop;
  SIGTERM e SIGINT fecham em ~0,05 s com codigo 0, jogo preso em loop Python sai no segundo SIGTERM. Container
  22.04 (OCIO 1.1.1, pacote oficial) compila e empacota sem regressao. Windows/MSVC nao compilado.

## 2026-10-12 - Preparacao da release 0.5.0 (Windows, Linux e Web)

- Versao: `ANASTACIO_VERSION_STRING` e About (`wm.py`) ja em 0.5.0 (6eec04e2); `container-build-22.04.sh` com `VERSION` padrao 0.5.0.
- README: downloads apontam para `v0.5.0`, "Como usar" com `AnastacioEngine.exe`/`AnastacioRuntime.exe`, secao "Novidades da 0.5.0". Galeria `release-images/v0.4.7/` renomeada para `v0.5.0/` (o nome 0.4.7 era provisorio).
- Linux: `package-runtime.sh` remove `Range_Components_Label.rar` (antes so o procedimento manual da doc removia). `container-build-22.04.sh` confere no tar `libae_uvatlas.so`, `libae_denoise.so`, `icons_upbge/`, `icons_blender5/`, `anastacio_network/` e a ausencia do `.rar`.
- Docs: `distribution-0.1.md` ganhou o procedimento atual do Linux (container, `.tar.xz`); `linux-build.md` e `roadmap.md` sem referencias velhas de versao.
- Nao feito: OIDN nao esta no apt do container, entao o bake de lightmap no Linux usa o box blur. Nenhum pacote foi gerado nem testado nesta entrada.
- Correcoes achadas nos testes do pacote: (1) **crash com SSGI** no nó Diffuse: o GLSL `node_bsdf_diffuse_ambient_ssgi` ganhou `emit` (emissivos no SSGI) e o nó nao passava o argumento (access violation no `GPU_stack_link`); novo wrapper `node_bsdf_diffuse_ambient_ssgi_node` com emit 0, reconhecido em `GPU_material_ssgi_outputs`. (2) Build Web: historico das nuvens em `gpu_compositing.c` so com `GL_VERSION_4_3` (`glCopyImageSubData`). (3) wasm-ld: stubs de `uiTemplateHeader3D_controls`, `uiItemS_type` e `ED_view3d_layers_shown` no blenderplayer. (4) Exportar Web acha o runtime e o empacotador em `web/runtime` e `web/tools` ao lado do exe (zip da release) e usa o Python embutido.
- Web: Volumetric Fog nao compilava no navegador (`sampler2DShadow` sem precisao no GLSL ES); o cabecalho `#version 300 es` agora declara `precision highp sampler2DShadow` e `sampler3D`. Teste no Chrome headless: nevoa liga sem erro a 60 FPS, mas o feixe do Spot nao aparece (no desktop aparece) — pendente.
- `startup.blend` de fabrica trocado pelo salvo pelo usuario em 2026-10-12 (mesmos addons, sem pie menus); anterior em `startup.blend1`.

## 2026-10-12 - Sombra colorida (vitral), feixe colorido na névoa, poeira no feixe e emissivos no SSGI

- **Sombra colorida:** opção **Material > Shadow > Colored** (`MA_COLORED_SHADOW`, só com Alpha Blend e Cast). Depois da passada de profundidade, cada Sun/Spot desenha esses materiais numa textura RGBA16F da lâmpada (`colortex`, criada só se algum material usa a opção): rgb = luz que passa (Base Color do Principled ou cor do material antigo, mais branca quanto mais transparente), alpha = profundidade do vidro mais próximo (blend MIN). O receptor atrás dele multiplica a luz por essa cor. Caminhos: material antigo (`shade_shadow_tint`, `shade_shadow_tint_csm` para Sun com cascatas) e loop de luzes do Principled (`scene_light_shadow_tint`). Bucket novo `COLOR_SHADOW` em `RAS_BucketManager`; passada em `KX_ShadowRenderer`, também com o cache estático.
- **Feixe colorido na névoa:** os shafts do Sun e das Spots leem a mesma textura (`vfog_shadowcolor0-2`, unidades 23-25 do filtro) e o feixe sai com a cor do vidro.
- **Poeira no feixe:** World > Volumetric Fog > **Dust** (`vfog_dust`, 0 = desligado, arquivos antigos iguais). Pontinhos claros só onde a luz chega (sol e lâmpadas, respeitando sombra e vidro), derivando com o vento; desligado em Low. `vfog_data` ganhou o índice 56.
- **Emissivos no SSGI** (Codex): Emission ligado direto no Material Output e Emit do material antigo viram fonte de luz do SSGI.
- Não feito: Point lamp, sombra Variance e nó Lamp Data seguem com sombra preta; Sun com cascatas no Principled não tem sombra nenhuma hoje, então também não tem cor.
- Teste: `tools/debug/cenas/criar_cena_vitral.py` (modos sun, spot, csm, legacy, nodes_off). Aceite visual do usuário no runtime: sombra colorida OK em sun/spot/csm, nodes_off preta como antes, névoa e feixes visíveis. Valores da poeira ajustados no olho.
- Depois: **Glow** no material (`shadow_color_emit`, no lugar do antigo `pad8`; 0 = como antes, até 3 = luz 4x mais forte), aceito no runtime. Margem de 0.002 na comparação de profundidade tira a acne (pontos coloridos no próprio vidro, visíveis com Glow). Tentativa de borrar a mancha (9 amostras) desfeita: pesada e feia. Com SSGI ligado o vidro transparente sai cortado em degraus (limitação antiga do SSGI com Alpha Blend, não desta entrada). Medição de FPS (`VITRAL_BENCH`) não liberou o limite de 60; no profile a cena fica 94% ociosa.
- Otimização: a passada de cor desenha só os objetos com material Colored (`KX_CollectColorShadowCasters`) e é pulada quando nenhum está na área da luz/cascata e o alvo já está branco (`GPU_lamp_shadow_color_dirty`). Alvo de cor com metade do tamanho do mapa de sombra e framebuffer próprio, sem depth test (a profundidade fica no alpha): 1/4 da memória e da limpeza. Névoa: poeira só nos passos que o sol alcança; nas lâmpadas a sombra é lida antes e passo sombreado pula densidade e poeira. Margem anti-acne baixada para 0.0008 (0.002 vira ~1 m numa cascata).
- Pendente: no Sun com cascatas (`vitral_csm`, material antigo) a mancha colorida no chão sumiu, só aparecem fios na ponta da projeção; funcionava antes de mover a luz da cena. Suspeitos: bias das cascatas empurrando o receptor para a frente do vidro, ou o framebuffer sem depth test. Comparar com `vitral_legacy` (sem cascatas) para separar.

## 2026-10-12 - Culling de atividade: desligar uma flag tirava o objeto da lista da outra

- Causa: `KX_GameObject::SetActivityCulling(..., false)` removia o objeto de `m_cullinglist` ao desligar só a fisica (ou só a logica), mesmo com a outra flag ligada. Sem estar na lista, `UpdateActivity` nunca rodava nele e a logica não era mais suspensa por distância. Mesmo caso para o contrário.
- Outros dois problemas no mesmo ramo: se o objeto estava culled ao perder a última flag, ficava fora da render list para sempre (`m_bRender` nunca voltava a true); e desligar a logica de um objeto culled não retomava o `m_actionManager`.
- Correção em `KX_GameObject.cpp` (`SetActivityCulling`): a lista só é limpa quando não sobra nenhuma flag de fisica/logica; ao sair da lista, o objeto é restaurado se estava culled; a logica retoma também o action manager.
- Hipótese de Kitsuy (Discord, 2026-10-11) de `m_cullinglist.clear()` no construtor de `KX_Scene`: não se aplica, a lista é um `std::vector` membro e já nasce vazia.
- Segunda lista de Kitsuy (2026-10-12: `m_animatedlist`, `m_euthanasyobjects`, `m_tempObjectList`, listas de partículas/reverb/sombra, `m_rainAura`): mesmo caso, todos `std::vector` membros (nascem vazios); `m_rainAura` é `unique_ptr` nulo, criado sob demanda. Teste `tools/debug/cenas/criar_cena_restart_estado.py`: 6 rodadas com `scene.restart()`, 8 rigid bodies perto e 8 longe (culling de física): alturas idênticas nas 6, cubos longe parados em todas, frame mediano 16,66 ms em todas. Nenhum estado sobra entre reinícios.
- Sugestão de Kitsuy de remover `PIL_sleep_ms(1)` em `wm_window.c` (`wm_window_process_events`, linha 1570): esse trecho só roda no `WM_main` do editor, com a UI ociosa. O jogo (Play no editor via `LA_BlenderLauncher` e player standalone via `GPG_Ghost`/`LA_PlayerLauncher`) roda no loop próprio `LA_Launcher::EngineMainLoop` (`while ... EngineNextFrame()`), que lê eventos direto do GHOST e não passa por esse sleep. Remover não ganha nada no jogo e faria o editor ocioso girar a CPU a 100%. Não alterado.
- Teste: `tools/debug/cenas/criar_cena_activity_culling_logic.py` (headless). A (fisica desligada no frame 5) e B (controle) saem do raio no frame 60. Antes: A contava 59 / 99 / 179 nos frames 60 / 100 / 180; depois: 59 / 60 / 60, igual ao controle.
- Não testado: o caso de objeto culled que perde a última flag (restauração de `m_bRender`/render list) e o retorno do action manager. Não há leitura de `m_bRender` no Python; dependem de visual ou de um probe em C++.

## 2026-10-12 - World Sound: filtro Music / Ambient no painel

- Painel **Sound Modules** ganhou dois botões em linha (Music e Ambient); a lista mostra só os módulos do tipo escolhido.
- O filtro é `WindowManager.world_sound_filter` (estado da tela, não entra no `.range`). Padrão: Music.
- Testado em background: propriedade existe, padrão MUSIC, troca para AMBIENT e volta. Desenho do painel na janela: pendente de conferência do usuário.

## 2026-10-12 - World Sound, etapa 2: `KX_AudioManager` e `Range.audio`

- Escopo fechado pelo usuário: só Music e Ambient (sem módulos de Efeitos/Voz), com opção de eco das Reverb Areas nos dois.
- `Ketsji/KX_AudioManager.{h,cpp}`: criado no launcher ao lado do `KX_NetworkMessageManager` (`LA_Launcher.cpp`) e entregue ao engine (`Set/GetAudioManager`). O engine registra, antes da lógica de cada quadro, o World de cada cena ativa (uma vez por World; módulo de nome já registrado só recebe os sons que faltam) e chama `Update()` uma vez por quadro, com relógio real próprio.
- Music: uma faixa por vez, crossfade com o Fade do módulo, avanço automático ao fim da faixa (Shuffle/Loop), faixa única em Loop sem intervalo. Ambient: todas as camadas em loop, com fade. Volume final = módulo x som x fade; Mute zera.
- Diferença do plano: não usa `AUD_PlaybackManager`. O fade já exige ajustar o volume de cada handle a cada quadro, então o volume do módulo entra na mesma conta e pause/stop percorrem os handles do módulo.
- Eco: flag nova `WO_SOUND_USE_REVERB` (bit no `flag` existente) / `use_reverb_areas`. `KX_Scene::UpdateReverbAreas` passa a área vencedora ao gerenciador; com várias cenas no quadro vale a mais forte, e sem relato por 0,5 s o eco sai (a cena das áreas acabou).
- Python `Range.audio` (alias `bge.audio`): `play(module, sound="", fade=-1)`, `stop(...)`, `pause`, `resume`, `next`, `previous`, `setVolume`, `getVolume`, `isPlaying`, `playing`, `sounds`, `modules`. Nome inexistente devolve `False`/`None`, sem exceção.
- Headless (`--server`): os módulos existem e a API responde, nada toca.
- Testado sem janela (`AnastacioRuntime.exe --server`, cena de `tools/debug/cenas/criar_cena_world_sound.py`): módulos e sons visíveis já no primeiro quadro, API responde, troca da cena A para a B (World sem módulos) mantém os módulos registrados, encerra sem erro.
- **Não testado**: som de verdade (crossfade, avanço da playlist, pausa, eco num som 2D), porque o modo sem janela não tem dispositivo de áudio; depende do usuário abrir a cena. O `AnastacioEngine.exe` não foi relinkado nesta rodada porque o editor estava aberto (os objetos compilaram; o player foi linkado).

## 2026-10-12 - World Sound, etapa 1: dados no World e aba no editor

- Motivo: todo jogo refaz música, volumes e troca de faixa (no RolimaRacer é um componente Python numa cena sempre viva). Plano em três etapas; esta é só a parte do editor, ainda **sem som no jogo**.
- DNA (`DNA_world_types.h`): `WorldSoundModule` (nome, tipo Music/Ambient, volume, fade, flags Play on Start/Shuffle/Loop/Mute) e `WorldSoundEntry` (nome, caminho, volume, pitch); `World.sound_modules`. Lista vazia é o padrão, então arquivos antigos e da Range original abrem sem versioning.
- Cópia/liberação em `world.c`, gravação/leitura em `writefile.c`/`readfile.c`, caminhos dos áudios no `bpath.c` (Make Relative/Absolute e Save As cuidam deles).
- RNA (`rna_world.c`): `world.sound_modules` e `module.sounds` com `new/remove/move`; nomes únicos, porque o jogo vai achar módulo e som por nome.
- Aba **World Sound** ao lado de World (`BCONTEXT_WORLD_SOUND = 19`; `rna_space.c`, `buttons_context.c`, `space_buttons.c`) e painel em `bl_ui/properties_world_sound.py`: adicionar módulo, escolher vários arquivos de uma vez, ordenar, remover.
- Testado em background: criar, renomear, mover, remover, copiar o World, salvar e reabrir (valores e caminhos conferem); arquivo antigo (`tools/ProjetoCutscene/Cutscene_test.range`) abre com a lista vazia; a aba aparece no enum de contextos. Não conferido: a aba desenhada na janela do editor (aceite do usuário).
- Gotcha: `"//"` dentro de comentário de um `DNA_*.h` quebra o makesdna (erros de alinhamento num struct vizinho).
- Posição da aba: a fileira de cima do editor é controlada pela lista `top_context` em `bl_ui/space_properties.py` (cabeçalho e navigation bar). Sem `WORLD_SOUND` nela, a aba caía na coluna lateral com as abas de objeto. Corrigido e instalado em `build/bin`; conferência visual pendente.
- `docs/code-map-gameengine.md` e `docs/code-map-kx-gameobject.md`: números de linha atualizados com `check_docs.py --fix` (54 erros de linhas defasadas).

## 2026-10-12 - Decimate (Collapse): opção High Quality

- Queixa: objeto simples com muita subdivisão saía "torto" e com a UV deformada. Medição (`tools/debug/cenas/medir_decimate.py`, cinco formas com superfície e UV analíticas) mostrou que a forma em si quase não desviava; o defeito era triangulação (num cubo arredondado em Ratio 0,1, 144 de 480 triângulos com ângulo abaixo de 5°) e UV (erro de até 16% da textura).
- Opção nova **High Quality** no modificador (`use_collapse_quality`, bit `MOD_DECIM_FLAG_QUALITY` no `flag` existente, sem campo novo no DNA). Modificadores novos nascem com ela ligada; arquivos salvos antes ficam com ela desligada e o resultado deles continua idêntico (conferido contra o build anterior nas cinco formas). O Decimate do modo de edição usa sempre o método novo.
- O que muda em `bmesh_decimate_collapse.c` com a opção ligada:
  - quádricos pesados pela área da face, normalizados pela área média (independente da escala da malha);
  - posição do vértice por decomposição em autovalores: só as direções bem definidas do quádrico movem o vértice a partir do centro da aresta; quinas e vincos ficam exatos e áreas planas ou cilíndricas não jogam o vértice longe;
  - plano de preservação de volume (Lindstrom-Turk) somado ao sistema;
  - custo de forma (`comprimento² / qualidade do pior triângulo`), que ordena as áreas planas e evita triângulos finos; substitui o fallback de topologia;
  - UV lida no triângulo em que o vértice cai (da mesma ilha), em vez de interpolada só ao longo da aresta; os dois lados da aresta recebem o mesmo valor quando não há costura;
  - costuras de UV: vértice de dentro da ilha só colapsa para cima do vértice da costura, vértice de costura só desliza pela costura, encontro/fim de costura e polo de UV ficam no lugar. Colapso que move costura é permitido com custo alto, para o Ratio pedido continuar alcançável;
  - no modo Symmetry a aresta espelhada passa a ser conferida contra face virada (o método antigo não confere).
- Resultado nas cinco formas, Ratio 0,5 a 0,02, novo contra antigo: erro de UV médio 0,34x e máximo 0,22x; triângulos abaixo de 5° de 358 para 113; erro de volume menor (esfera a 2%: -10,9% para -7,8%); desvio de forma médio 1,06x (o método antigo já era bom nisso). Custa mais: cerca de 3x o tempo (esfera de 199 mil triângulos para 10%: 1,9 s para 5,4 s).
- Robustez conferida: quads mantidos (Triangulate desligado), malha sem UV, 2 UVs + cor de vértice, grupo de vértices, Symmetry (0 faces viradas contra 5 do antigo), malha em escala 0,001 e 1000, `validate()` sem correções em todos.
- Play: o conversor avisa no console quando um objeto entra no jogo com Decimate ligado (é recalculado na carga; todo quadro em malha animada) e o painel do modificador mostra "Apply before playing". Textos novos em pt-BR, es e ru.
- Não medido: custo do aviso/recalculo em jogo real; aceite visual do usuário pendente.

## 2026-10-12 - Componente Python de Rigid Body Joint

- `Shift+A > Constraints > Rigid Body Joint Component` cria `scripts/rigid_body_joint_component.py` e o anexa
  ao objeto ativo. O arquivo é deliberadamente editável: em `start()` procura o alvo e chama
  `Range.constraints.createConstraint()` para Hinge, Limited Hinge/Slider 6DOF, Ball Socket ou Cone Twist.
- O mesmo botão também fica na aba **Object Constraints** quando a cena usa `BLENDER_GAME`, abaixo de
  **Add Object Constraint**.
- O painel Game Components separa Joint, Pivot and Axis e Limits, com alvo em lista de objetos da cena,
  colisão entre corpos ligados, quebra e limites lineares/angulares. O botão de recarregar do componente
  refaz a lista de alvos sem apagar a escolha que ainda exista.
- Validação: geração do arquivo compilada por Python; no editor instalado, operador criou o arquivo e registrou
  `RigidBodyJointComponent` no objeto (`RIGID_BODY_JOINT_COMPONENT_EDITOR_SMOKE: PASS`). Teste visual/físico
  no jogo real permanece necessário.

## 2026-10-12 - Object Constraints: menu compatível com Game Engine

- Com `BLENDER_GAME`, o painel **Object Constraints** mantém o menu completo herdado, mas só deixa clicável
  **Rigid Body Joint**. Esta é a única constraint de objeto que `BL_BlenderDataConversion` converte para o
  runtime Bullet; as demais aparecem esmaecidas em vez de serem editáveis e depois ignoradas ao rodar o jogo.
- Arquivos existentes permanecem intactos: se o objeto contiver uma constraint incompatível, o painel mostra
  um aviso. O menu e o comportamento dos outros motores não mudam; constraints de osso continuam separadas.
- Textos novos traduzidos para pt-BR, espanhol e russo.

## 2026-10-12 - Logic Bricks → Python: teste integrado (mini-jogo) e o que ele achou

- Cena nova `tools/create_logic_convert_scene_game.py`: mini-jogo sem entrada do jogador com os sistemas interagindo (Player em dois estados que atira e perde vida, dois pontos que criam Enemies a partir de um modelo em camada inativa com os próprios bricks, Steering, colisões, placar por mensagem, level up que toca uma ação, Track To, Near, Ray, Visibility, Camera). 40 amostras de 20 valores, lidas no fim do quadro.
- Quatro diferenças reais entre bricks e convertido apareceram e foram corrigidas no conversor (o código entrou no commit `afef97e5`):
  - **Delay ao voltar para um estado:** a engine reinicia o sensor quando ele volta a ser usado (`SCA_ISensor::RegisterToManager` chama `Init`); o convertido continuava a contagem antiga e a máquina de estados ficava trocando de estado todo quadro. Delay e Random agora zeram fora do estado.
  - **Collision com objeto de física Sensor:** o sensor da engine ignora quem é do tipo Sensor e enxerga todo o resto, com ou sem Actor (`isActor()` em `KX_ClientObjectInfo` quer dizer "não é sensor"). O convertido enxergava todo mundo.
  - **Near:** a engine usa uma esfera física que dispara ao tocar a forma do outro objeto; o convertido media até o centro. Agora soma o raio da esfera de colisão do outro (objetos dinâmicos sem Collision Bounds, ou Bounds Sphere); as outras formas continuam pelo centro.
  - **Add Object de objeto em camada ativa:** o actuator copia; `scene.addObject` recusa e o erro parava o componente inteiro. Esse controller agora fica como brick, com o motivo no TODO.
- Resultado: bricks duas vezes idênticos; bricks × Component 800 de 800; bricks × Module 800 de 800; `LEFT_AS_BRICK 0`. Regressão: F6 a F12 e Steering iguais como antes, base e F5 só com o `-0.00` de sempre; testes de geração F5/F6/F7 passam.
- Levantamento só de leitura no RolimaRacer (42 arquivos, nada salvo): 324 controllers, 272 convertem, 12 são Python, 24 estão desativados e 22 ficam como brick (12 som empacotado, 6 Filter 2D custom sem shader, 3 Sound sem som, 1 Action sem ação); nenhum erro e todo o código gerado compila. Não foi rodado em jogo.

## 2026-10-12 - Logic Bricks → Python: lacunas da auditoria fechadas e rótulos do brick Property

- Conversor, sensores: **Collision com Pulse** gera evento quando muda a quantidade de objetos colidindo (é o que `KX_CollisionSensor` de fato compara; Near e Radar não têm a opção); **Mouse Over Any com Pulse** gera evento quando o cursor passa para outro objeto; **Keyboard `log`/`target`** convertido (`logic.keyboard.text`, backspace e enter como a engine; alvo que não é texto vira texto), e o sensor de registro sem controller continua como brick ativo, porque a engine o registra à força; **Random com Delta Time** usa `tick_skip_dt` e deixou de sortear no 1º quadro.
- Conversor, **Track To**: alvo vindo de propriedade do objeto ou do World (o nome é relido a cada atualização; sem alvo a orientação fica onde estava e o objeto fixo não volta). Todo Track To passa a usar a conta exata da engine: sem pai usava `alignAxisToVect`, que com Time > 0 errava bastante (-0,04 contra -0,19 dos bricks). A orientação local inicial do pai agora é gravada na conversão, não lida no `start()`.
- Conversor, **ordem dos actuators**: dentro de um objeto eles rodam na ordem da pilha de actuators, como a engine, e não na dos controllers (dois controllers no mesmo quadro com Assign 5 e Add 1 davam 5; os bricks dão 6).
- Conversor: Assign de texto em **World Property** segue a mesma regra de expressão do Assign de objeto.
- `use_priority` dos controllers: conferido no C++ e em jogo, não muda nada dentro de um objeto para os controllers que o conversor converte (só importa para controller Python e para a ordem entre objetos). Nada a fazer.
- Brick Property: os 16 rótulos fixos do modo Runtime API / Weather Effects / World Property em `logic_window.c` passam por `IFACE_()`; o item "Edge" da neblina volumétrica virou "Edge Softness" (caía na tradução de aresta de malha). Traduções novas em pt-BR, es e ru.
- Doc da API: assinatura de `KX_Camera.getScreenRay` corrigida no `.rst` (`dist` é obrigatório e `property` tem padrão `""`).
- Validado em jogo, bricks × convertido, `LEFT_AS_BRICK 0`: `create_logic_convert_scene_f11.py` (sensores) e `create_logic_convert_scene_f12.py` (Track To, 13 rastreadores) idênticos, também no modo Module; F10 ampliada (ordem dos actuators, World de texto) 361 de 361; F7, F8, F9, F6 e Steering iguais como antes. Na F11 as colunas de Mouse Over só valem quando a janela do runtime recebe o cursor (`cursor=centro` no arquivo); com outra janela na frente saem zeradas nos dois lados.
- Registro de teclas conferido depois com teclas simuladas pelo Windows (`tools/create_logic_convert_scene_keylog.py`; a, b, c, Backspace, d, Enter, e, z, z, cada tecla segurada 100 ms): texto registrado idêntico em bricks e convertido (`xabd
ezz`) e 9 disparos do sensor All Keys nos dois, nos mesmos intervalos de quadros. Teclas enviadas enquanto o jogo ainda carrega entram no texto mas não disparam o sensor, nos dois lados; por isso o teste espera 4,5 s antes de digitar.
- Mouse Over da F11 e Mouse Look da F5 repetidos com o cursor dentro da janela: iguais (F11 345 de 345).
- Editor religado depois; o item "Edge Softness" e os rótulos traduzidos foram conferidos em background pela consulta de tradução, não na tela do Logic Editor.
- Diferenças que são da arquitetura e ficam: ordem entre objetos (bricks reordenam a lista de actuators ativos; componentes rodam na ordem dos objetos), navmesh refeito em jogo no Steering, alvo procurado por nome.

## 2026-10-12 - Logic Bricks → Python: disparo dos controllers como na engine, casos que faltavam e traduções

- **Quando o controller dispara.** O código convertido agora segue `SCA_ISensor::Activate`: cada sensor gera um evento quando muda de valor ou por pulso repetido, e o controller só reavalia e reenvia o resultado aos actuators em quadro com evento de algum sensor dele. Antes o controller disparava só na própria subida ou no pulso True Level. Consequências:
  - controller que continua positivo dispara de novo quando outro sensor dele muda (ex.: Or de duas teclas com Property Add);
  - sensor que já começa positivo sem gerar evento (Delay ou Always com Invert, controller Nand/Nor parado) não dispara no 1º quadro;
  - **Tap** vale para todos os sensores (antes só Keyboard e Mouse), inclusive combinado com pulso True Level;
  - **pulso False Level** é lido; o **Skip** conta a partir da última mudança do sensor (antes saía em 1, 2, 5, 8 em vez de 1, 4, 7) e é do sensor, não de cada controller ligado nele;
  - **Delta Time** do pulso (`use_dt` / `tick_skip_dt`) é lido; **Level** dispara o controller que acabou de entrar no estado; Joystick com All Events dispara todo quadro enquanto positivo.
- **Bricks desativados** (sensor, controller ou actuator) não entram mais no código convertido, como a engine, que nem cria esses bricks. Para converter de novo, o operador guarda na propriedade `logic_to_python_off` do objeto quais bricks ele mesmo desativou e reativa só esses antes de converter. Objeto convertido antes deste registro (todos os controllers desativados) é reativado inteiro.
- **Casos que ficavam como brick e agora convertem:** Action com **Child** (os filhos tocam a própria ação; o mapa objeto → ação é gravado no `start()`), Motion Character com **VR Gaze** (`cam.gazeDirection`) e Add Object com o objeto vindo de **propriedade** (do objeto ou do World; tenta `scene.convertObject` no Load Mode On Demand).
- Correções achadas pelas cenas novas:
  - Add Object: Linear Velocity vira `applyForce`, como `InstantAddObject` (antes `setLinearVelocity`; num corpo dinâmico dava vx 2,98 contra 0,05 dos bricks);
  - Property Assign em propriedade de **texto**: o valor é expressão, então `"abc"` grava abc, inteiro grava o texto dele e nome de propriedade copia o valor; texto sem aspas que não é propriedade fica como brick;
  - Steering: retomada depois do Self Terminate, orientação inicial do pai usada pelo Facing e corpo com dinâmica suspensa. `acceleration` e `turn_speed` só são usados pela engine com simulação de obstáculos, que o conversor já recusa;
  - Action: repete as recusas de `BL_Action::Play` (camada ocupada por prioridade maior ou pela mesma ação); sensor Armature com Invert e constraint inexistente; Game Save/Load Config com campos vazios usa o padrão da engine.
- Traduções (pt-BR, es, ru) dos rótulos e dicas do brick Weather Effects: 73 do Fog/Clouds - Volumetric e 53 mais antigos (chuva, respingos, aura, raio, terremoto). Cinco rótulos fixos de `logic_window.c` estão no dicionário mas seguem em inglês até ganharem `IFACE_()` no C; o rótulo "Edge" da neblina cai na tradução de aresta de malha.
- Testes de geração: `test_logic_convert_f5_codegen.py` e `_f6_` estavam quebrados desde a F7 (faltava `render` no módulo falso e `delay_time` no sensor); corrigidos, e os bricks falsos ganharam os padrões das flags comuns.
- Validado em jogo, bricks × convertido (Component), `LEFT_AS_BRICK 0` em todas:
  - `create_logic_convert_scene_f8.py` (Child, VR Gaze, Add Object de propriedade): 281 de 281; um valor de ação de filho oscila de uma rodada para outra até entre duas rodadas de bricks;
  - `create_logic_convert_scene_f9.py` (Action com Blendin, camadas e conflito de prioridade; sensor Armature nos 5 testes com IK; Save/Load Config; Screenshot; Filter 2D): 1155 de 1155. Do Screenshot e do Motion Blur só se confere que rodam e que o arquivo é criado;
  - `create_logic_convert_scene_f10.py` (regra de disparo acima, bricks desativados, Assign de texto): 301 de 301, também no modo Module e convertendo duas vezes seguidas (`twice`);
  - `create_logic_convert_scene_steering.py` (22 objetos): 1101 de 1101;
  - regressão: F7 241 de 241, F6 igual, base e F5 iguais a menos de um `-0.00` contra `0.00` que já existia. O Mouse Look da F5 depende do mouse real e não é comparável com o mouse em uso.
- Lacunas conhecidas (auditoria das propriedades de todos os bricks): `use_pulse` do Collision e do Mouse Over (re-disparo ao trocar de objeto), Track To com alvo vindo de propriedade, `log`/`target` do sensor Keyboard, `use_priority` dos controllers, Random com Delta Time, navmesh refeito em jogo no Steering.

## 2026-10-12 - Logic Bricks → Python: bricks que faltavam e Weather Effects volumétrico

- Conversor (`bl_operators/logic_to_python.py`) passa a converter: atuador **Action** (Play, Ping Pong, Flipper, Loop Stop, Loop End, Property; mesmo fluxo de `BL_ActionActuator::Update` por cima de `playAction`), sensor e atuador **Armature**, **Filter 2D**, **Vibration**, Motion **Servo Control**, **Character Motion** e **Set Position**, Edit Object **Change Color**, Game **Save/Load Config** e **Screenshot**, Property **Level** e **Runtime API** (sensor e atuador), e **Mouse Over** com material, x-ray e máscara.
- Correções no conversor: Delay em segundos usava o campo de frames (`delay` em vez de `delay_time`); Mouse Over nunca convertia (`use_material` do sensor Mouse é enum, sempre verdadeiro); Motion Loc/Rot agora escalam por `60 * deltaTime` como a engine; Linear/Angular Velocity com Damping fazem a rampa da engine.
- Continuam como brick: Action com Child (a ação de cada filho não é exposta em Python), Motion Character com VR Gaze, Add Object com objeto vindo de propriedade.
- Brick Property > Weather Effects: categorias novas **Fog - Volumetric** (`vfog_effect`) e **Clouds - Volumetric** (`vcloud_effect`), e Sky Layers e cor das nuvens em Clouds. Valores novos de `ACT_RUNTIME_PROP_WEATHER_*` (50 a 91), sem renumerar os antigos.
- Correção: efeito Float de Weather Effects com valor exatamente 0 ou 1 gravava 0 (o texto era lido como bool).
- Correção: o campo Target do sensor Property (Runtime API) não aceitava objeto (faltava `PROP_EDITABLE`).
- API Python nova para o conversor: `KX_Camera.getScreenRay(x, y, dist, property="", xray=False, mask=0xFFFF)`, `filterManager.addFilter(index, type, fragmentProgram="", owner=None, mipmap=False)` (aceita `RAS_2DFILTER_OUTLINE`; `owner` liga as game properties aos uniforms) e `filterManager.setBuiltinFilterEnabled(type, enabled=True)`.
- Validado em background: 57 controllers com todos os bricks novos (inclusive ligados de outro objeto) convertem e o código gerado compila (`tools/test_logic_convert_f7_codegen.py`).
- O componente gerado chama `self.update()` no fim do `start()`: a engine roda o `start()` no 1º quadro e o `update()` só a partir do 2º, e os bricks já agem no 1º. Sem isso o convertido ficava um quadro atrasado.
- Validado em jogo com `tools/create_logic_convert_scene_f7.py` (10 amostras de 24 valores, bricks × convertido, `LEFT_AS_BRICK 0`): no modo Component os 240 valores batem no mesmo quadro, com a ação em loop de 1-40 e de 1-38,5. Nos modos Module/Script também batem os 240 quando a amostra é tirada no fim do quadro (argumento `post`, que lê no `post_draw`); os 204 de 240 medidos antes eram artefato da medição, porque o Checker é um controller Python e lia o quadro pela metade. A diferença real desses modos é só de ordem dentro do quadro: outro controller Python que leia o objeto no mesmo quadro vê a mudança um quadro antes do que veria com bricks. As cenas antigas (`create_logic_convert_scene.py`, `_f5`, `_f6`) continuam com CHECK idêntico. Não cobertos em jogo: Vibration (sem joystick), Screenshot, Load Config, Motion Blur e sensor Armature por erro de IK.

## 2026-10-12 - Bindings Python: partículas GPU, Explosive e clima

- `KX_ParticleSystem`: `blendMode`, `billboardMode`, `emissionMode` (strings), `useBackfaceCulling`, `useDebugUi`, `useVortex`, `vortexHeight`, `vortexRadiusTop`, `vortexRotationSpeed`.
- `KX_GameObject` (painel Explosive): `explosionRadius`, `explosionForce`, `upBias`, `useOcclusion`, `explosionEffect`, `effectLife`, `useParticleExplosion`, `particleSize`, `particleStyle`, `fireColor`, `smokeColor`, `sparkColor`, `fireAmount`, `smokeAmount`, `sparkAmount`, `smokeDuration`, `blastSpeed`, `useGroundMark`, `useMarkNearby`, `groundMark`, `markSize`, `markLife`. Documentados no RST.
- `KX_WorldInfo.setWeather/getWeather`: Sky Layers, Volumetric Clouds (`vcloud_*`), `cloud_detail`, `cloud_color_r/g/b` e o restante do Fog - Volumetric (`vfog_use_*`, `vfog_quality`, `vfog_max_lights`, `vfog_anisotropy`, `vfog_edge`, `vfog_noise_scale`, `vfog_shaft_intensity`, `vfog_morning_boost`, `vfog_wind_direction`).
- Sem binding de propósito: curvas de tamanho/cor, `emit_from`, `particle_look`, `collision_ground_object`, `use_burst_on_start`, `use_fragment_shader` (resolvidos na conversão da cena; `fragmentShaderPath` já liga/desliga o shader) e `vfog_resolution` (buffers criados no load).
- Teste: `tools/debug/cenas/criar_cena_teste_bindings_fx.py` (71 verificações, `BINDINGS_LOG`).

## 2026-10-12 - Explosive: estilos, Ground Mark e fumaça mais longa

- Particle Explosion ganha o tamanho Tiny, os estilos Fire/Electric/Concrete/Water e cores, quantidades, Smoke Duration e Blast Speed editáveis.
- **Ground Mark**: projeta o material do objeto Mark no chão estático sob a explosão. Usa a mesma projeção do Impact Decal (`KX_DestructionManager::ProjectDecal`). O botão **New** cria a marca do estilo na camada 20: queimado, queimadura elétrica, poeira ou mancha molhada. Size e Life são editáveis.
- **Mark Nearby Objects** (opção do Ground Mark): marca menor (metade) no lado virado para a explosão dos objetos com malha no alcance da marca, até 12, os mais perto primeiro; segue o objeto (parented) e as amassadas se ele tiver Deformation.
- A fumaça final dura mais: Fire 9 s, Electric 6 s, Concrete 10 s (antes 4,5/2,5/6). A névoa da água continua curta.
- Cena: `tools/debug/cenas/criar_cena_explosao_tamanhos.py --marca`.

## 2026-10-12 - Explosão de partículas: modo Burst, Drag, partículas suaves e Explosive > Particle Explosion

- GPU particles ganharam `emission_mode` (Continuous/Burst). No Burst o lote inteiro nasce de uma vez
  e fica morto até a próxima rajada: `use_burst_on_start`, `burst_interval` (0 = só no início ou por
  Python) e `particles.burst()`. Na rajada, a velocidade de cada partícula varia de 30 a 100% para encher
  a esfera. Novo `drag` (perda de velocidade por segundo, `exp(-drag*dt)`). Python: `burstMode`,
  `burstInterval`, `drag` e `obj.particlesMix` (segundo emissor).
- Correção: objetos adicionados em jogo (Add Object / Effect do Explosive) não recriavam o emissor Mix.
- Partículas suaves: o `main` de cada look (built-in ou custom) é embrulhado e o alpha some perto da
  geometria, usando a mesma cópia de profundidade da Depth Transparency (blit uma vez por câmera
  quando há emissores). Tira o corte reto onde os sprites cruzam o chão.
- Look Smoke: a máscara zera antes da borda do quad (sprites grandes mostravam canto reto).
- Physics > Explosive > **Particle Explosion** com **Explosion Size** (Small/Medium/Large/Huge, escala
  0.5/1/2/3.5): bola de fogo + fumaça + estilhaços nativos no ponto da detonação, sem objeto Effect
  (`KX_Scene::SpawnParticleExplosion`). Arquivos antigos: flag desligada.
- Cenas: `tools/debug/cenas/criar_cena_explosao_particulas.py` (rajada repetida ou `--explosivo` com
  Effect) e `criar_cena_explosao_tamanhos.py` (os 4 tamanhos). Conferido por capturas no Runtime.

## 2026-10-11 - Presets nativos de constraints e leitura do tutorial Blender 2.69

- `Shift+A > Constraints` agora oferece Hinge, Limited Hinge (6DOF), Slider (6DOF), Ball Socket e Cone
  Twist (6DOF). Cada preset anexa da biblioteca distribuída `demos/Physics/constraintsTutorial.range`
  o conjunto original do tutorial, centraliza-o no cursor 3D e preserva o `RIGID_BODY_JOINT`, alvo,
  limites e forma visual. Cada conjunto inclui os dois corpos físicos e os dois filhos `NO_COLLISION` que
  formam o acabamento central. A cena muda automaticamente para `BLENDER_GAME`.
- Todo preset recebe dois materiais explícitos: `Constraint Anchor - Magenta` na âncora e
  `Constraint Body - Cyan` no corpo móvel.
- O arquivo externo `constraintsTutorial.blend` (Blender 2.69) foi aberto sem gravação: 1 cena, 28 objetos
  e cinco joints de objeto lidos — Hinge, Ball e três Generic 6DOF. O conversor atual já suporta todos
  esses tipos. O script histórico `snap` só usa `Rasterizer` e não participa da física.
- Validação pela instalação real em `build/bin`: os cinco operadores terminaram com `FINISHED`, anexaram
  20 objetos (10 corpos + 10 peças de acabamento), cinco joints com alvos válidos, aplicaram os dois
  materiais e salvaram a cena já em `BLENDER_GAME` (`INSTALLED_FINISH_TEST: PASS`). A cena gerada rodou
  no `AnastacioRuntime` por 20 frames e encontrou os cinco donos de constraint. Não há alteração C++ que
  exija relink.

## 2026-10-11 - Qualidade de Clouds e Sky Layers (Low/Medium/High) e rótulos "Clouds - tipo"

- Painel World > Weather: os três tipos de nuvem passam a se chamar "Clouds - Procedural", "Clouds -
  Volumetric" e "Clouds - Sky Layers" (traduzidos em pt/es/ru em `translations_labels.py`).
- Novos campos no DNA do World (depois de `vcloud_pad`): `cloud_detail` e `sky_layer_detail` (oitavas do
  ruído, 1-8) e `sky_layer_relief` (0 desliga o relevo e pula uma passada de ruído). `cloud_detail == 0` /
  `sky_layer_detail == 0` é a sentinela de arquivo antigo em `direct_link_world` → Medium (5 oitavas,
  relevo 1), que é exatamente o visual de antes. As FBMs com Detail são normalizadas para a faixa de 5
  oitavas, então a cobertura não muda com o Detail.
- Botões Low/Medium/High (`world.cloud_quality_preset`, em `custom_pt_world.py`) só preenchem esses
  valores, que continuam editáveis; o botão que bate com os valores atuais fica pressionado. Clouds:
  Detail 3/5/7. Sky Layers: Detail 3/5/7, Relief 0/1/1.
- Chegam ao shader pelo uniform `clouds_quality` (3D View, `gpu_compositing.c`) e `ge_CloudsQuality`
  (jogo, `RAS_2DFilter` / `KX_Scene` / `KX_RenderPipeline`). A FBM da Volumetric continua com 5 oitavas.

## 2026-10-11 - Volumetric Clouds acendia o Céu em Camadas junto

- Os três tipos de nuvem (Clouds, Sky Layers, Volumetric Clouds) são opções separadas e compartilham uma
  máscara de bits (1, 2, 4). O teste das Sky Layers era `mask > 1.5`, escrito quando só existiam os bits
  1 e 2; com a Volumetric (4) ligada sozinha, as Sky Layers também eram desenhadas (se a cobertura
  delas fosse > 0). Agora testa só o bit 2, `mod(floor(mask / 2.0), 2.0) > 0.5`, no jogo
  (`RAS_Clouds2DFilter.glsl`) e na 3D View (`gpu_shader_fx_clouds_frag.glsl`).
- `tools/debug/cenas/criar_cena_valida_ceu.py`: modo `layers` (Clouds + Sky Layers em cores distintas,
  tecla 2 alterna Clouds) e modo `vclouds` (só Volumetric, com as outras desligadas mas com cobertura,
  para pegar a regressão). A tecla 2 passa `bool` para `setWeather("clouds", ...)`: flags de clima
  recusam `0.0`/`1.0`.

## 2026-10-11 - Chuva Volumetric sumia na 3D View (precisão do tempo)

- Os riscos do estilo Volumetric rolavam `time * speed * 500` no shader. Na 3D View `time` é o relógio
  do Windows (tempo desde que o PC ligou, `fmod` 10000 s): com algumas horas de uptime e Fall Speed
  alto o produto passava de 2^24, o `fract()` do risco ficava sempre 0 e a chuva não aparecia (o
  Classic já fazia wrap com `mod 4096` e seguia funcionando). No jogo o mesmo acontecia após alguns
  minutos de Play.
- A fase de queda agora é calculada na CPU em double com wrap em 20480 e entra como uniform próprio:
  `rain_fall_phase` (`gpu_compositing.c` → `gpu_shader_fx_rain_frag.glsl`) e `ge_RainFallPhase`
  (`KX_RenderPipeline.cpp` → `RAS_2DFilter` → `RAS_Rain2DFilter.glsl`). Aparência inalterada; uma
  troca de padrão a cada ~41 s / Fall Speed no wrap, imperceptível com a queda rápida.

## 2026-10-11 - Aba Texture: ícone do mundo só com o mundo selecionado e slots num painel recolhível

- `ED_texture_context_check_world` (`buttons_texture.c`) passou a exigir que não haja objeto ativo.
  Clicar no World no Outliner limpa o objeto ativo, então o ícone do mundo só aparece nesse caso e o
  contexto de textura não fica preso em World depois de visitar a aba World com um objeto ativo.
- `properties_texture.py`: o painel sem cabeçalho `TEXTURE_PT_context_texture` ficou só com os botões
  de contexto (agora com rótulo: Material, World, Lamp, Particles, Line Style, Other, definidos em
  `rna_space.c`); lista de slots, nome e tipo foram para o novo painel recolhível
  `TEXTURE_PT_texture_slots` ("Texture"), com o conteúdo numa caixa. O painel de botões mantém o
  idname antigo de propósito: o arquivo salva a ordem dos painéis por idname e um idname novo sem
  painel desenhado antes dele vai para o fim da região (`UI_panel_begin`). O addon Cycles exclui os
  dois da lista de painéis compartilhados.

## 2026-10-11 - Avisos do `--debug`: feedback loop no 1º quadro e memória não liberada ao sair

Investigação do que o editor imprimia com `--debug --debug-gpu` depois de três Plays na cena de
startup: 3 avisos `Feedback loop warning` e 25 blocos não liberados (66 KB). Cinco causas, todas
corrigidas; depois delas o editor (com 3 Plays e sem Play) e o runtime saem com zero blocos e sem o
aviso.

- **Feedback loop (1 por Play).** `RAS_2DFilterManager::RenderFilters` escolhe o off screen de
  destino sem deixar o filtro desenhar no dono da profundidade que ele lê, mas `UsesDepthTexture()`
  só responde certo depois do primeiro `Initialize()` do filtro, que acontecia dentro do `Render`.
  No primeiro quadro o filtro de nuvens (`FILTERPASS_CLOUDS`) era tratado como se não lesse
  profundidade e, com multisample, desenhava em `FILTER0` lendo a profundidade de `FILTER0`. Agora o
  gerenciador chama `Initialize()` antes de decidir. No desktop era um quadro inofensivo; no WebGL
  esse desenho é rejeitado.
- **`GPUNodeLink` (2 por material por Play).** Em `gpu_material.c` o link da cor do horizonte era
  criado antes de saber se o céu é atmosférico; `env_sky_atmospheric` não o consome e link sem nó
  nunca é liberado. `hor`/`zen`/`nad` passaram a ser criados só no ramo `env_sky`, nos dois lugares
  (material clássico e ambiente dos shader nodes).
- **Programa preso no cache de shaders.** Em `GPU_generate_pass`, um acerto do cache durante o
  prefetch (`9f440a1c`) caía no ramo de compilar: a referência recém-adquirida era perdida, o
  programa nunca mais chegava a zero usuários e ainda era mandado compilar de novo. Acontecia a
  partir do 2º Play no editor. Agora a referência é devolvida e nada é enviado.
- **`vsm_store_instancing`** faltava em `GPU_shader_free_builtin_shaders` (shader e interface).
- **Shaders próprios da viewport** (grade do chão em `view3d_draw.c` e raio da chuva em
  `view3d_rain.c`) nunca eram liberados: novo `ED_view3d_shaders_free()`, chamado no `WM_exit`
  antes do `GPU_exit()`.

**`-d memory` do runtime consertado.** A troca para o alocador com checagem acontecia no meio da
leitura dos argumentos, depois de `init_nodesystem()`; na saída o `free_nodesystem()` abortava com
`Memoryblock free: pointer not in memlist` e o relatório de blocos nunca aparecia. A troca agora é
feita no começo do `main`.

**Ferramentas:** `tools/debug/cenas/criar_cena_startup_autosair.py` (cena de startup que encerra o
jogo sozinha após ~3 s) e `tools/debug/editor_auto_play.py` (aperta Play N vezes dentro do editor e
fecha), para repetir esta checagem sem ninguém apertar P.

**Validação:** editor com 3 Plays e sem Play, runtime com `-d memory` na cena de startup, e runtime
com `-d gpu` nas cenas `valida_materiais` e `vclouds_luz`, sem erro de shader nem crash. Não
investigados: `Internal error, builtin font not loaded` nas placas de texto 3D do runtime e uma
linha `AVG` do profiler com tempo negativo entre um Play e outro no editor.

## 2026-10-11 - Volumetric Clouds: luz com borda prateada mais fina e lado iluminado branco

Ajuste do modelo de luz em `RAS_Clouds2DFilter.glsl` (jogo) e no espelho da viewport
`gpu_shader_fx_clouds_frag.glsl`. O lobo de silver lining em `cloudPhase` ficou mais estreito e
mais forte (Henyey-Greenstein `g` 0.99 → 0.996, ganho 2 → 4), para dar a borda fina e brilhante em
volta do sol em vez de um brilho largo. No acúmulo do raymarch a cor deixou de ser só a cor base
escalada: a parte na sombra usa um ambiente frio (`cloudColor * vec3(0.72, 0.8, 0.95)`) e a parte
iluminada mistura a cor base com branco conforme `lit`. Cenas de teste em `tools/debug/cenas/`:
`criar_cena_vclouds_luz.py` (4 variantes no mesmo `.range`, alternadas por Scene Actuator),
`inspecionar_vclouds_luz.py`, `criar_cena_vclouds_debug1.py`, `criar_cena_valida_ceu.py` e
`criar_cena_valida_materiais.py`.

**Validação:** o filtro compila sem erro e a cena `vclouds_luz` roda a 60 fps no
`AnastacioRuntime.exe` trocando entre as 4 variantes. Aceite visual do usuário pendente. O log do
runtime mostra `Internal error, builtin font not loaded` a cada cena (placas de texto 3D), não
investigado.

**Incidente de build do mesmo dia:** o editor fechava ao apertar P e o runtime caía na abertura
com `0xc0000409` (estouro de pilha no construtor de `RAS_2DFilterManager`). Não era bug de código:
depois de um build completo de `main` feito sem `VSLANG=1033` (2713 objetos com `#deps 0` em
`ninja -t deps`), um checkout para outra branch trocou 17 headers (`RAS_2DFilterData.h`,
`DNA_material_types.h` etc.) e o build incremental recompilou só 108 arquivos. Resolvido com
`ninja -t clean` + build completo em `main` com `VSLANG=1033`.

## 2026-10-11 - Volumetric Clouds (3º modo em World > Weather): raymarch real + 2 bugs legados corrigidos

Novo modo "Volumetric Clouds" em World > Weather, aditivo aos dois já existentes (Clouds e Sky
Layers, intocados). Raymarch volumétrico real num `RAS_2DFilter` (`RAS_Clouds2DFilter.glsl`,
mesma cadeia de post-process dos outros dois modos, agora um `cloud_mask` de 3 bits): duas fases
(coarse empty-space skip + detail com acumulação de luz Beer-Lambert), self-shadow via
mini-raymarch em direção ao sol (`cloudLightMarch`), phase function Henyey-Greenstein dual-lobe
para silver lining, sombra aproximada no terreno (`cloudTerrainShadow`, reusa o mesmo campo de
densidade do ponto de vista do sol, sem exigir cascade shadow map), disco/glow de sol desenhado
no próprio filtro (`sunAngle`/falloff gaussiano, tolerante a desalinhamento de câmera). Presets de
qualidade Low/Medium/High (24/12, 48/24, 64/48 passos). DNA/RNA novos em `DNA_world_types.h` e
`rna_world.c` (`vcloud_*`, flag `WO_VCLOUDS_ENABLE`), painel em `custom_pt_world.py` espelhando
Sky Layers. Gerador de cena de teste reutilizável em `tools/debug/cenas/criar_cena_vclouds.py`.

**Bug crítico corrigido:** o pass `RAS_2DFilter`/`FILTERPASS_CLOUDS` para todo o sistema de nuvens
(Clouds + Sky Layers + Volumetric) só é criado quando `filters.useClouds` é verdadeiro
(`KX_Scene.cpp`), e esse booleano ignorava a flag `WO_VCLOUDS_ENABLE` — com Volumetric Clouds
ligado sozinho (sem Clouds nem Sky Layers), o filtro inteiro nunca era instanciado e nada
aparecia. Corrigido somando `world->vcloud_flag & WO_VCLOUDS_ENABLE` à condição de criação e
populando os campos `filters.vcloud_*` nesse mesmo bloco.

**Bug legado separado corrigido (céu de fundo preto):** achado ao testar a cena de exemplo. Em
`gpu_material_old_world()` (`gpu_material.c`), quando a cena não tem `Sun` lamp vinculado, a cor
do sol de fallback usada pelo céu atmosférico (`do_sky_atmospheric`, que multiplica o céu inteiro
por essa cor) estava fixada em preto — trocada para branco. Achado colateral de tipo também
corrigido: a mistura horizonte↔zênite usava `node_mix_shader` (espera `vec4` com alpha) em cores
`vec3` puras (`set_rgb`), lendo alpha de lixo; nova função `mix_rgb3` (vec3→vec3) em
`gpu_shader_material.glsl` substitui as duas ocorrências. Também documentado: setar
`world.use_sky_blend` direto por script (sem passar pelo enum real `world.sky_type`) deixa bits
antigos Real/Atmospheric ligados e cai nesse caminho por engano — `criar_cena_vclouds.py` agora
usa `world.sky_type = 'GRADIENT'`.

**Validação:** bug crítico e bug do céu confirmados corrigidos via captura automática
(`bge.render.makeScreenshot()` + leitura do PNG, sem depender de print manual) e visualmente pelo
usuário. Composição com os 3 modos de nuvem simultâneos (`--all-modes` no gerador de cena) sem
regressão. FPS por preset Low/Medium/High não mostrou diferença mensurável na máquina de
desenvolvimento (GPU não é o gargalo nessa cena de teste — 93% do frame em espera de vsync mesmo
no preset High); validar o critério original (Low não cai >15-20% numa iGPU fraca) exige rodar em
hardware de referência real, não feito nesta sessão.

## 2026-10-11 - Planar Reflection: crash no runtime e espelho preto corrigidos

- **Crash no runtime (commit `9630e952`)**: a entrada abaixo dizia que o `AnastacioRuntime.exe` "não terminou
  por falta de display/GPU". Estava errado: o ambiente tem GPU e o runtime caía com SIGSEGV em
  `gpu_node_input_link` ← `GPU_stack_link` ← `node_shader_gpu_planar_reflection` (backtrace no
  `%TEMP%\<cena>.crash.txt` que o próprio engine grava). Causa: `node_exec_socket_use_stack()`
  (`nodes/intern/node_exec.c`) só dava slot de pilha a FLOAT/VECTOR/RGBA/SHADER. Os sockets `Enable`
  (BOOLEAN) e `Resolution` (INT) ficavam sem `bNodeStack`, viravam `GPU_NONE` e encerravam cedo a contagem de
  entradas do `GPU_stack_link`, que então lia os parâmetros restantes de um `va_list` sem argumentos. Agora
  BOOLEAN e INT ganham slot e são lidos como escalar (`node_socket_get_boolean_as_float`/`_int_as_float` em
  `node_util.c`; `nodestack_get_vec`/`node_gpu_stack_from_data` em `node_shader_util.c` os tratam como FLOAT).
  Foi o primeiro nó a levar um socket BOOLEAN/INT ao codegen de GPU (os `Enable` de Bloom/SSR de World são
  lidos direto em `KX_Scene.cpp`).
- **Espelho preto**: a captura e a projeção da UV estavam certas. Eram duas coisas:
  1. A cena de teste ligava `Color` no Base Color de um Principled, que ilumina o reflexo de novo com as luzes
     da cena. Espelho puro é `Color` → shader **Emission** → Surface (o Emission existe e funciona no jogo).
  2. A captura é desenhada com os materiais dos próprios objetos refletidos, que já terminam no Color
     Management da cena (`gpu_material_link_display_transform`); o material do espelho aplicava de novo.
     `node_planar_reflection` agora desfaz essa codificação (`game_view_untransform`, inversa de
     `game_view_transform`, com exposure/gamma/contraste enviados em `unfplanarview` por
     `GPU_material_bind_planar`) e devolve cor linear com alpha 1. Com Color Management desligado nada é
     desfeito. A tabela de contraste do Filmic saiu para `gpu_view_transform_contrast()`, usada pelos dois
     lados; o shading dos materiais existentes não muda.
- Conferido por pixel em `criar_cena_planar_reflection.py` (1280x720): fundo direto e fundo no espelho
  `63,63,80` nos dois; frente do cubo `184,93,68` direta e `184,94,70` refletida. Cena combinada
  `criar_cena_tudo_junto.py` (Billboard, Strands, Fur com e sem direção, Explode, espelho): 65 frames, exit 0.
- **Não conferido**: Filmic e exposure/gamma diferentes do padrão (só Standard foi testado); o Billboard, que
  nos screenshots fica atrás do painel de profile. O Strands gera poucos fios num plano de 2 triângulos
  (a densidade é por triângulo): para parecer grama a malha precisa ser subdividida.
- Merge do `main` (Céu em Camadas + SSGI nativo) nesta branch: dois conflitos aditivos
  (`node_shader_output_material.c`, includes de `KX_Scene.cpp`). O build incremental depois do merge crashava
  em qualquer cena (`GPU_material_free` ← `ED_render_id_flush_update`): o Céu em Camadas acrescenta campos a
  `World` antes de `gpumaterial` e o Ninja deste build não rastreia headers, então `render_update.c.obj`
  ficou com o layout antigo. Rebuild limpo resolveu; não era bug do SSGI. Regra de
  [build-notes.md](build-notes.md): depois de mudar `DNA_*.h`, inclusive por merge, `ninja -t clean`.

## 2026-10-11 - Reflexo planar dedicado: implementado (compilador de material aberto, com supervisão)

- Sessão seguinte à investigação abaixo ("Reflexo planar dedicado: investigado, não implementado"), mesmo
  dia: o usuário autorizou explicitamente abrir o compilador de material para fazer o nó de verdade. Nó
  novo `ShaderNodePlanarReflection` (`SH_NODE_PLANAR_REFLECTION`, categoria **Fragment** no Add menu do
  Shader Editor): `Enable` (bool, padrão False) + `Resolution` (int 16–2048, padrão 512) + `Clip End`
  (float, padrão 100) → saída `Color` (RGBA).
- Associação objeto→espelho: o nó reflete pelo plano local do próprio objeto (XY local, normal +Z, mesma
  convenção de `KX_TextureRenderer`/`KX_PlanarMap`) — não por um socket de objeto separado. Em
  `BL_BlenderDataConversion.cpp`, depois do scan de probes de cubemap, cada objeto tem seus materiais
  varridos (nível superior da árvore de nós, sem recursão em grupos); se o nó existe com `Enable` ligado,
  cria/reaproveita um `KX_PlanarReflector` via `KX_TextureRendererManager::AddPlanarReflector()`.
- Nova classe `KX_PlanarReflector` (`source/source/gameengine/Ketsji/KX_PlanarReflector.h`/`.cpp`),
  subclasse de `KX_PlanarMap` — mesma relação que `KX_LightProbe` tem com `KX_CubeMap`: sintetiza um
  `EnvMap` estático pra reusar o construtor de `KX_PlanarMap` sem slot de textura legado, e é dono de um
  `GPUTexture*` 2D próprio (`GPU_texture_create_2D`), criado sob demanda em `SetupCamera()`.
- Hook novo em `KX_TextureRenderer`/`KX_TextureRendererManager`: `SetFrameViewProjection(view, projection)`
  — virtual no-op por padrão (zero custo/risco para cubemap/probe existentes), chamado por
  `RenderRenderer()` logo depois de montar `view`/`projection` de cada face; `KX_PlanarReflector` o
  sobrescreve pra cachear `projection * view` da câmera espelhada daquele frame, usada depois pelo GLSL
  pra projetar a UV de tela.
- GPU codegen (`gpu_material.c`/`GPU_material.h`): `GPU_material_planar_reflection(mat)` marca a flag
  `use_planar_reflection` quando o nó existe no material (chamada em `node_shader_gpu_planar_reflection`,
  `node_shader_stage_nodes.c`); `GPU_material_bind_planar(mat, tex, viewproj)` faz o bind por objeto, mesmo
  padrão de `GPU_material_bind_probe` (unidade de textura própria, `unfplanarenabled` zerado quando não há
  `KX_PlanarReflector` pra aquele objeto). GLSL novo `node_planar_reflection` em `gpu_shader_material.glsl`:
  projeta a posição do fragmento (view→mundo via `GPU_INVERSE_VIEW_MATRIX`, mesmo builtin do `node_billboard`)
  pela `unfplanarviewproj` cacheada, divide por `w`, remapeia pra `[0,1]` e amostra `unfplanartex`.
- Binding em `BL_BlenderShader.cpp::Update()`, no mesmo bloco dos probes: se o material usa o nó, resolve
  o `KX_GameObject` do `RAS_MeshUser` (mesmo padrão de `BL_Shader::Update()`), busca o
  `KX_PlanarReflector` desse objeto via `FindPlanarReflector()` e chama `GPU_material_bind_planar()`. Nada
  disso roda pra materiais sem o nó (flag checada primeiro) nem toca o binding de probes/SSR existente.
- Build: `ninja RangeEngine` (via `vcvars64.bat`, skill `build-anastacio`) no worktree
  `D:\AnastacioEngine-shadernodes`. 1ª tentativa falhou no link (`LNK2019`, `KX_PlanarReflector.cpp`/`.h`
  esquecidos no `CMakeLists.txt` de `source/gameengine/Ketsji`); corrigido e `cmake . && ninja RangeEngine`
  gerou `AnastacioEngine.exe`/`AnastacioRuntime.exe` limpos (sem warning novo).
- Testado: `tools/debug/cenas/criar_cena_planar_reflection.py` via `AnastacioEngine.exe -b
  --factory-startup --python ... --` confirma `ShaderNodePlanarReflection` em `bpy.types` com os três
  sockets de entrada e a saída `Color`, e salva um `.range` com o nó ligado ao Base Color de um Principled.
  **Não confirmado**: `AnastacioRuntime.exe -w <W> <H> <scene.range>` não terminou dentro do tempo de
  espera neste ambiente (mesma limitação de display/GPU já documentada pro teste de Bloom/SSR) — nem a
  sobrevivência no runtime nem o reflexo aparecendo corretamente na tela foram confirmados visualmente.
  Depende do usuário testar com GPU/display real.
- Detalhe completo em
  [shader-nodes.md#reflexo-planar-planar-reflection](shader-nodes.md#reflexo-planar-planar-reflection).

## 2026-10-11 - Reflexo planar dedicado: investigado, não implementado

- Próximo item da fila de shader-nodes: um nó de material `ShaderNodePlanarReflection` para o `KX_PlanarMap`
  já existente (espelho/água real). Esta entrada é só a investigação e a decisão de escopo — nenhum código
  de engine foi alterado.
- Confirmado: `KX_PlanarMap` (`source/source/gameengine/Ketsji/KX_PlanarMap.h`/`.cpp`) já é uma câmera
  espelhada completa e funcional — reflete posição/orientação da câmera da cena pelo plano do objeto
  espelho, recorta com near-plane oblíquo (sem `glClipPlane` fixo), inverte front-face na reflexão e
  cacheia a projeção por câmera. Hoje é ligada só pelo sistema legado de Environment Map de slot de
  textura (`EnvMap`/`MTex`, `ENVMAP_REFLECTION`, `stype == ENV_REALT`), lido em
  `BL_BlenderDataConversion.cpp` (~linha 3715-3745) — fora do Shader Editor novo (`bNodeTree` de material).
- Comparado com o padrão usado em Bloom/SSR (nós de World sem GPU codegen, só lidos na conversão de cena em
  `KX_Scene.cpp`, ver entrada de 2026-10-11 "Bloom e SSR pelo World node graph"): esse padrão funciona pra
  Bloom/SSR porque os dois já são filtros de tela cheia automáticos; o nó só liga um interruptor que já
  existe. Reflexo planar não tem interruptor automático equivalente — produz uma textura por objeto que
  precisa ser amostrada por um material para aparecer.
- Também comparado com o reflexo de probes de cubemap que já funciona em qualquer material PBR com nós
  (fase 4, `KX_LightProbe` + `KX_TextureRendererManager::FindProbe` + `GPU_material_bind_probe`/
  `GPU_material_bind_probe2` em `BL_BlenderShader.cpp`): esse caminho é automático por posição do
  fragmento, sem nó nenhum no material, mas é cubemap (direção 3D). Reflexo planar precisaria de um
  binding por objeto/material equivalente (`sampler2D` + matriz view-projection da câmera espelhada,
  projetando a UV no fragment shader) — não existe hoje, e criar isso é trabalho novo em
  `gpu_material.c`/`GPU_material.h`/`BL_BlenderShader.cpp` (o compilador de nós e o binding de uniforms do
  material), não uma leitura de socket na conversão de cena.
- Alternativa "config only" (nó sem saída `Color`, só Enable/Clip Start/Clip End/Resolution, que criasse o
  `EnvMap`/`MTex` legado por baixo dos panos na conversão) foi descartada: não há confirmação de que
  material novo baseado em nós (Shader Editor, Principled) amostre esse slot legado hoje, então o nó
  arriscava não aparecer em tela pra quem usa o Shader Editor — escondendo a mesma incerteza em vez de
  resolvê-la.
- Decisão: parar e documentar em vez de implementar um nó que arrisca ser enfeite, ou abrir o compilador de
  material sem supervisão. Ver
  [shader-nodes.md#reflexo-planar-por-que-não-virou-nó-ainda](shader-nodes.md#reflexo-planar-por-que-não-virou-nó-ainda)
  e a entrada correspondente em `docs/roadmap.md`. Pendente: decisão do usuário sobre abrir esse codegen
  novo (com supervisão) ou manter reflexo planar fora do Shader Editor por ora.

## 2026-10-11 - Fur Shells: direção do pelo configurável

- Pendência do backlog de shader-nodes (ver [shader-nodes.md](shader-nodes.md)): o nó Fur Shells só inflava a
  malha ao longo da normal, sem jeito de controlar a direção do "pelo" (vento, direção custom).
- Dois sockets novos no nó Fur Shells, **depois** dos existentes (Length/Layers/Density/Vector) pra não quebrar
  link salvo em `.range` antigo: **Direction** (vetor, padrão `(0,0,0)`) e **Direction Strength** (fator 0-1,
  padrão 0). Com Direction Strength 0 (padrão) o resultado é idêntico ao de antes — só a normal, 100%
  retrocompatível. Conforme sobe até 1, cada shell desloca ao longo de
  `normalize(mix(normal, Direction, Direction Strength))` em vez de só `normal`.
- `GPU_material_shells` (`gpu_material.c`/`GPU_material.h`) ganhou os parâmetros `direction`/`direction_strength`;
  guarda o vetor já normalizado e o maior `direction_strength` pedido (igual ao padrão existente de
  `max_ff`/`max_ii` pra `shell_length`/`shell_layers`, caso mais de um Fur Shells no mesmo material).
- `GPUPassStages` (`gpu_codegen.h`) ganhou `shell_dir[3]`/`shell_dir_strength`, propagados em
  `gpu_material.c` pra dentro da struct de estágios junto com `shell_length`.
- `code_generate_geometry_stage` (`gpu_codegen.c`) emite `#define SHELL_DIR vec3(...)` e
  `#define SHELL_DIR_STRENGTH ...` junto com `SHELL_LENGTH`/`OUTLINE_WIDTH`, e o laço de shells agora calcula
  `vec3 shell_dir = normalize(mix(vs_varnormal[i], SHELL_DIR, SHELL_DIR_STRENGTH));` antes de deslocar o vértice
  (`SHELL_DIR_STRENGTH` 0 cancela o `mix`, mantendo o resultado idêntico ao `vs_varnormal[i]` de antes). O
  Outline (casco invertido) continua usando só a normal, sem mudança.
- `node_fur_shells` em `gpu_shader_material.glsl` ganhou os parâmetros `direction`/`direction_strength` na
  assinatura (não usados no corpo da função, que só calcula a máscara de fios) — necessário porque
  `GPU_stack_link` passa todo o array `in[]` do nó posicionalmente pros parâmetros `in` da função GLSL, então a
  ordem dos sockets novos (`in[4]`/`in[5]`) precisa bater com a ordem dos parâmetros novos na função.
- Compilado limpo (`RangeEngine`/`RangeRuntime` via `build-anastacio`, sem warning novo). Validado sem display
  com `tools/debug/cenas/criar_cena_fur_shells_direction.py`: sockets certos em `bpy.types`
  (`['Length', 'Layers', 'Density', 'Vector', 'Direction', 'Direction Strength']`), `.range` salvo; e, com GL
  disponível nesta sessão, `AnastacioRuntime.exe` rodou a cena 65 quadros sem crash e tirou um `shot.png` — o
  geometry shader do Fur Shells com os novos defines compilou e executou de fato. **Falta**: inspeção visual
  do `shot.png` (ninguém olhou se o pelo realmente "penteia" na direção configurada).

## 2026-10-11 - Shader nodes: Billboard, Strands, Explode (pendentes da fase 3)

- **Billboard** (`SH_NODE_BILLBOARD`, estágio vertex): entradas `Lock Axis`, `Scale`; saída `Offset` pro
  Vertex Offset do Material Output. `node_billboard` (`gpu_shader_material.glsl`) gira a malha (autorada no
  plano local XZ) pras direções direita/cima da câmera, lidas de `GPU_INVERSE_VIEW_MATRIX`/
  `GPU_INVERSE_OBJECT_MATRIX`; cilíndrico (eixo Z fixo) ou esférico conforme `Lock Axis`.
- **Strands** (`SH_NODE_STRANDS`, estágio geometry): entradas `Density`, `Length`, `Curvature`; saída
  `Tip Factor`. Novo modo `use_strands` em `code_generate_geometry_stage` (`gpu_codegen.c`): um triângulo
  fino por strand, origem pseudo-aleatória no triângulo de entrada, LOD por distância da câmera. Reaproveita
  o canal `varshelllayer`/`node_shell_layer` do Fur Shells/Outline em vez de criar varying nova (por isso não
  tem saída separada de índice da strand). `GPU_material_strands` novo em `gpu_material.c`/`GPU_material.h`.
- **Explode** (`SH_NODE_EXPLODE`, estágio geometry): entrada `Factor`; saída `Amount` (passthrough). Novo
  modo `use_explode`: cada triângulo sai inteiro deslocado por normal + direção aleatória por face (hash de
  `gl_PrimitiveIDIn`), `max_vertices = 3`. `GPU_material_explode` novo.
- Strands/Explode e Shells/Outline são mutuamente exclusivos no mesmo material (prioridade decidida em
  `GPU_generate_pass`: Shells/Outline > Strands > Explode > `geomcode` do usuário).
- Registro: `BKE_node.h` (1015-1017), `node.c`, `NOD_static_types.h`, `NOD_shader.h`, `nodeitems_builtins.py`
  (Billboard em Vertex; Strands/Explode em Geometry).
- Compilado limpo (`RangeEngine`/`RangeRuntime`, `ninja` via `build-anastacio`). Validado sem display com
  `tools/debug/cenas/criar_cena_billboard_strands_explode.py`: tipos certos em `bpy.types`, `.range` salva; e,
  com GL disponível nesta sessão, `AnastacioRuntime.exe` rodou a cena 65 quadros sem crash e tirou um
  `shot.png` — os geometry shaders novos compilaram e executaram de fato. **Falta**: inspeção visual do
  `shot.png`, cor do cabeçalho do nó por estágio, presets dedicados, custo no painel. Ver
  [shader-nodes.md](shader-nodes.md#billboard-strands-explode-fase-3).

## 2026-10-11 - GLSL Script: funções auxiliares sem conflito, uniforms `u_` e TIME

- Antes: funções auxiliares já compilavam, mas iam para o shader com o nome original; dois nós GLSL Script com um helper, constante ou `#define` de mesmo nome (ou o mesmo Text em dois nós) davam redefinição.
- Nomes por nó (`codegen_script_names` em `gpu_codegen.c`): funções, variáveis/constantes globais e structs do nível de cima do Text ganham `#define nome glsl_scriptN_nome` antes do `#line 1` e `#undef` no fim, junto com os macros do próprio script. As linhas do Text não mudam, então o erro de compilação continua na linha certa (conferido: erro posto na linha 9 saiu como `0:9`). Globais `in`/`out`/`varying` ficam como estão.
- Uniforms `u_` (`node_shader_glsl_script.c`): `uniform float|int|vec2|vec3|vec4 u_nome;` vira entrada do nó depois dos parâmetros do `main`, com `// @min @max @default` opcionais (`@min`+`@max` em float usa socket de fator, com slider). O valor fica no socket (salvo no `.range`, ligável) e aparece também em Material > Node Shader > Script Uniforms. No shader a palavra `uniform` é apagada da cópia do código e o wrapper preenche o global a partir do socket.
- Sem recompilar: entrada `u_` sem ligação entra como uniform dinâmico apontando para um valor guardado no `GPUMaterial` (`GPUScriptUniform`; a árvore de nós é uma cópia local durante a geração, então não dá para apontar para o socket). `GPU_material_script_uniform_set/get/reset` percorrem as três listas de variantes do material.
- Python do jogo: `KX_BlenderMaterial.setScriptUniform(nome, valor)` e `getScriptUniform(nome)`. O material guarda os valores e os reaplica quando o shader é gerado de novo; ao sair do jogo voltam ao valor do nó.
- `TIME` no script: quando o código usa a palavra, o nó recebe o tempo do material como entrada escondida e o wrapper preenche um global próprio do script.
- Teste: `tools/debug/cenas/criar_cena_glsl_script_uniforms.py`. No runtime (AMD RX 6800M), print conferido: cubo com xadrez + anéis de dois scripts com `pattern()`, `SCALE` e `TINT` iguais; esfera com os `@default` (verde, 4 listras) e esfera com o mesmo Text alterada pelo jogo (magenta, 10 listras); grade ondulando pelo script no Vertex Offset com `TIME` e `u_height` trocado pelo jogo. Sem erro de shader no log.
- Não testado: painel Script Uniforms e sliders no editor (só geração em background), embedded player, build Web.

## 2026-10-11 - Shader nodes: presets explicados em frames, código gerado, geometry livre e erro visível

- Presets (`bl_operators/node.py`): cada grupo já nasce separado em frames coloridos com rótulo (Inputs, Vertex, Geometry, Colour, Output), uma coluna por parte (`_preset_frames`; `part=` em `_preset_node` escolhe o frame quando o tipo do nó não diz). Presets novos: **Wind Leaves** (Wind + manchas de cor, Offset ligado sozinho), **Triplanar** (uma textura por eixo misturada pela normal, sem UV) e **Hologram** (linhas que correm + borda de Fresnel, Alpha Clip). Nomes dos presets no dicionário de tradução. Teste: os 9 presets criados em `-b` (frames sem nó solto nem coluna sobreposta) e os 3 novos conferidos em captura do runtime.
- **Show Generated Code** (`material.show_generated_code`; botão em Material > Node Shader e no cabeçalho do Node Editor): grava o GLSL final em `<material>_generated.vert/.geom/.frag` e mostra nos Text Editors abertos. Reusa `gpu.export_shader`, que passou a devolver também `geometry` (`GPUShaderExport.geometry`). Precisa de janela (sem contexto GL em `-b`) e do shader compilado. Teste no editor com janela: Toon Outline gerou os três Texts (geometry com `OUTLINE_WIDTH`), o Text Editor passou a mostrar o `.frag`; sem estágio geometry o `.geom` vira um aviso de uma linha.
- Campo Geometry em modo livre (`code_generate_geometry_stage`): Text com `void main()` em vez de `void geometry()` é usado como escrito. As linhas `layout(...) in;`/`layout(...) out;` do usuário sobem para o topo do shader (o layout de entrada dá o tamanho dos arrays `vs_*` que os helpers indexam) e ficam comentadas no lugar, mantendo a numeração de linhas do Text; sem elas valem `triangles` e `triangle_strip, max_vertices = 3`. Entradas `vs_*`, saídas e helpers `geom_*` continuam sendo declarados pela engine. Teste: `tools/debug/cenas/criar_cena_geometry_livre.py`; captura do runtime (RX 6800M) conferida com os três casos (faces afastadas, pirâmide por face com 12 vértices, triângulos encolhidos sem layout), sem erro de shader no log.

## 2026-10-10 - Nós de material com estágios de vertex e geometry (fases 1-4 do plano shader-nodes)

- Codegen (`gpu_codegen.c`): cada nó guarda os estágios em que roda. Os nós ligados à nova entrada **Vertex Offset** do Material Output (e do Output antigo) viram `vertex_nodes()` no vertex shader (`USE_VERTEX_NODES` em `gpu_shader_vertex.glsl`, depois do `vertex()` do usuário e antes da projeção); as funções da biblioteca que eles chamam são copiadas para o vertex (`glsl_lib_strip_vertex`). Atributos são lidos direto (`att`), posição/normal de view calculadas no próprio vertex. Nós só do vertex não entram no fragment.
- Estágio geometry gerado: toda varying do vertex vira `vs_<nome>` por `#define` e o GS gerado copia tudo (incluindo varyings declaradas no código do usuário e `gl_ClipDistance[6]` do `CLIP_WORKAROUND`). Sem suporte a GS (web/GLES) o material desenha como se não tivesse o estágio, com aviso único no console. Flag `GPU_SHADER_FLAGS_USER_GEOMETRY` no hash do cache; programas com GS continuam fora do binário cozido.
- `Material.geomcode` (linha "Geometry:" em Shader Sources, `script_geom` no RNA): o usuário escreve `void geometry()` com `geom_copy/geom_emit/geom_emit_offset/geom_set_position/geom_position/geom_normal` e `TIME`; `layout(... max_vertices = N) out;` opcional (padrão 3). DNA, readfile, library_query, material.c, atlas e recompilação ao editar o Text.
- Sombras: materiais que movem vértices (código do usuário, Vertex Offset ligado, Fur Shells, Outline) passam a sombrear com o próprio shader (`GPU_material_moves_vertices` em `KX_BlenderMaterial`).
- Nós novos (antigo e novo sistema): Vertex Offset, Wind, Wave (Vertex), Fur Shells, Outline, Shell Layer (Geometry), Camera Distance (Input) e **GLSL Script** (Script): o Text tem uma função `main`, seus parâmetros viram os sockets (float/int, vec2/vec3, vec4; `out` = saída), um wrapper converte os tipos; roda no fragment ou no vertex conforme o uso; editar o Text atualiza sockets e recompila.
- Fur Shells: camadas pela normal com uma invocação de GS por camada (`invocations`, GL 4.0; laço no 3.x), máscara de fios por célula de UV (saídas Layer/Alpha). Outline: casco invertido com winding trocado (precisa de backface culling).
- Menu Add no estilo do Blender 5: categorias Vertex, Geometry, Script e Presets nos dois sistemas de shading.
- Presets como grupos editáveis (`node.shader_preset_add`): Fur, Grass, Toon + Rim, Toon Outline, Dissolve, Water Waves (Offset ligado sozinho ao Vertex Offset; presets com Alpha põem o material em Alpha Clip).
- Materiais existentes geram o mesmo código (os acréscimos ao template ficam sob `#ifdef`); só o texto do template mudou, então o cache de shaders do usuário/`.cooked` recompila uma vez.
- Fase 5 (parcial): `#line 1` antes do código do GLSL Script e do geomcode, então o erro de compilação aponta a linha do Text.
- Teste: `tools/debug/cenas/criar_cena_shader_nodes.py` (água com Water Waves, esfera Fur, macaco Toon Outline, cubo GLSL Script, cubo de referência, cubo com geomcode). Runtime: 6 materiais compilados e linkados sem erro (AMD RX 6800M, GL 4.6 compat), 60 FPS. Avaliação visual pendente no jogo real.
## 2026-10-11 - CV3 corrigido: armature fora da tela não força mais pose+skinning todo frame

- **SP12 não era pendência:** `KX_AddObjectActuator::ResolveOriginalObject` já usa
  `KX_Scene::FindInactiveObjectAcrossScenes`, apoiado no índice O(1)
  `m_inactiveNameIndex` desde 2026-10-05. O índice cobre inserção, remoção, merge
  de LibLoad e o raro nome duplicado preservando “primeiro da lista vence”.
- **SP13:** `RAS_BatchGroup::SplitMeshUser` chama `OnMeshUserSplit`, que já remove o
  objeto do `KX_BatchGroup` e atualiza a referência. `KX_BatchGroup::SplitObjects`
  repetia a mesma remoção depois do retorno. A segunda busca linear foi removida;
  o `Split` e o upload do VBO continuam necessários e inalterados.
- **SP4/SP5, medição A/B:** uma cena temporária com uma icosfera subdividida 5 (hull) e um grid 128×128 (BVH),
  18 spawns alternados de cada tipo e `time.perf_counter()` ao redor de `addObject()` descartou o primeiro de
  cada sequência. Ao reconstruir reversivelmente o runtime base e depois restaurar a mudança: SP4 caiu de
  **6,645 para 0,182 ms** na média de 17 spawns steady (−97,3%; ~36,5×). SP5 foi de **0,845 para 0,708 ms**;
  confirma a rota sem regressão, mas não demonstra ganho de parede isolável, pois o setup restante do Bullet
  domina. O runtime final foi reconstruído e repetiu 0,182/0,708 ms com `PASS`; uma
  rodada adicional no binário final deu 0,154/0,600 ms e também passou.
- **SP4:** o `CcdShapeConstructionInfo` já é compartilhado pelas réplicas da mesma
  malha. Os pontos do hull agora são retidos nele após o primeiro `CreateBulletShape`;
  os spawns seguintes não fazem hash, cópia do cache `.cooked` ou
  `btConvexHullComputer`. `UpdateMesh` e `ProcessReplica` invalidam os pontos antes
  de trocar a geometria, inclusive para um deformer/`ReplaceMesh`.
- **SP5:** a chave da BVH também fica no
  `CcdShapeConstructionInfo`, portanto cópias normais não re-hasham os vértices e
  índices. A invalidação é junto da geometria em `UpdateMesh`/`ProcessReplica`; o
  lote de conversão mantém o hash paralelo existente. SP6/SP7 foram avaliados e continuam adiados: `RemoveValue`
  remove todas as ocorrências e a fila de eutanásia é FIFO para preservar a ordem e evitar dupla remoção de filho.
  SP9/SP10/SP11/SP14/SP15 também foram confirmados como adiados pelos contratos de Bullet, hot-reload,
  conversão/merge e ownership de meshes; a evidência por item está na tabela da auditoria.
- Configurado build Release próprio do worktree e compilado com êxito
  `KX_BatchGroup.cpp.obj`; após a alteração do header, recompilado e relinkado
  com êxito `ge_physics_bullet` e `KX_SoftBodyDeformer.cpp.obj`.
- **Regressão runtime SP4/SP5:** `RangeRuntime` foi relinkado e executou uma
  cena temporária controlada. Ela instanciou alternadamente 48 réplicas
  `RIGID_BODY`/`CONVEX_HULL` e 48 `STATIC`/`TRIANGLE_MESH` da mesma malha de
  cada tipo; o resultado persistido foi `PASS`, com 96 criações, zero retornos
  nulos e todos os objetos presentes ao fim. A cena foi reaberta em background:
  confirmou câmera, os dois tipos de bounds e o controlador Python. Isso valida
  o caminho funcional e o ciclo de vida do cache; não mede seu ganho. Uma
  comparação de desempenho deve usar a mesma cena no baseline e nesta alteração,
  com contadores temporários do cálculo de hull/hash BVH ou outra métrica
  diretamente sensível ao trabalho removido.

Continuação do mesmo worktree (`claude/auditoria-gpu-cache`). CV3 estava marcado como "decisão de
design" na auditoria: `anim_needs_update` (`KX_Scene.cpp:2192`) forçava pose + skinning completos
todo frame para um armature mesmo com todos os meshes deformados fora da tela (culled), porque o
código original (herdado do Blender 2.4x) sempre atualizou armaturas por segurança — o AABB usado
no teste de culling segue a última pose aplicada, então uma pose congelada pode manter um
personagem culled para sempre se uma ação movesse um membro para dentro da tela sem a raiz do
objeto se mover.

Usuário escolheu pular a pose/skinning quando culled, com uma rede de segurança em vez de manter o
comportamento atual. Implementado:
- `anim_needs_update` não força mais `needs_update = true` só por existir um filho deformado culled;
  o ramo que já forçava update ao primeiro filho não-culled continua idêntico (nunca foi o problema).
- `BL_ArmatureObject::TickCullSkip()` (novo campo `m_cullSkipFrames`, `BL_ArmatureObject.h`/`.cpp`)
  conta quantos frames consecutivos a pose foi pulada e força um update completo a cada 15 frames
  (`CULL_SKIP_FORCE_INTERVAL`), limitando a pose congelada a no máximo 15 frames mesmo no pior caso.
  `ResetCullSkip()` zera o contador sempre que um update real acontece por qualquer motivo.

`bf_ketsji`/`bf_converter` compilam limpos; build completo (`RangeEngine`/`RangeRuntime`) e smoke no
player sem crash. Validado com `tools/debug/cenas/criar_cena_cv3_correcao.py`: armature fora do
enquadramento da câmera com uma ação cíclica tocando (osso girando 0→1,2 rad em 20 frames, modo
LOOPEND). Lendo `channels['Bone'].pose_matrix` via Python frame a frame (só muda quando
`BL_Action::Update` aplica a pose de fato) em 180 frames: a pose ficou congelada em blocos de
exatamente 15 frames consecutivos e deu um salto visível no frame seguinte a cada marca de
15/30/45/.../180 — nunca mais que 15 frames sem atualizar, nunca atualizando fora da marca. Uma
tentativa de mover o armature para dentro do enquadramento da câmera no frame 101 não ficou
"visível" para o culling nessa cena específica (framing não cobriu a nova posição), então essa
transição não foi exercitada por este teste — mas o ramo de código responsável por ela já existia
antes e não foi alterado. Avaliação visual no jogo real (personagem culled não trava nem "pula"
de forma perceptível ao reaparecer) pendente do usuário.

## 2026-10-11 - KX10 (cache de shadow cull) validado com Spot/armature/layers, fecha como corrigido

Continuação do mesmo worktree (`claude/auditoria-gpu-cache`). O item KX10 (`AutoShadowStillValid`/
`BuildShadowCullCache`) já tinha passado no benchmark estático (sombras 0,613 → 0,194 ms, FPS +28,3%)
mas faltava a validação com Spot/deformadores/layers pedida em `docs/auditoria-suspeitos.md`.

Nova cena `tools/debug/cenas/criar_cena_kx10_correcao.py` (não é benchmark, é teste de corretude):
Spot com Auto Shadow, um personagem com modifier ARMATURE sempre dentro do alcance (parado, mas
com deformador), um cubo rígido que entra/sai do alcance via Python em 3 fases (perto/longe/perto2,
40 frames cada) e um objeto numa layer fora do `shadow_layer` do Spot. Roda com `--sem-armature`
para isolar o teste do objeto que entra/sai sem a interferência do deformador.

- **Com armature**: `lightsShadowUpdated` = 1 em todos os 150 frames das 3 fases — confirma que a
  checagem `entry.m_object->GetDeformer()` nunca deixa o cache congelar com deformador em alcance,
  mesmo com a pose parada.
- **Sem armature**: 0 em repouso (39 frames seguidos por fase) e exatamente 1 no frame seguinte a
  cada transição real de alcance do cubo (f=42 e f=82) — sem update perdido nem espúrio.
- O objeto fora da layer do Spot nunca apareceu na contagem (filtro de layer correto).

KX10 passa de "parcial" para **corrigido** em `docs/auditoria-suspeitos.md`. Checagem visual da
sombra renderizada no jogo real (com/sem o cache) continua pendente do usuário, como os demais itens
desta auditoria que dependem de avaliação visual.

## 2026-10-11 - Cluster GPU cache: GP6 e RA2 corrigidos; GP3/GP4/GP5/GP7 analisados sem alteração

Continuação do cluster "gpu / depsgraph" de `docs/auditoria-suspeitos.md` (GP1/GP2/RA1 corrigidos em
2026-10-09 com o mesmo padrão). Worktree `D:\AnastacioEngine-auditoria-claude`, branch
`claude/auditoria-gpu-cache`.

- **GP6 corrigido** (`gpu_material.c` `GPU_material_update_lamps`): cache por `GPULamp` (campos
  `dynupdate_*`) comparando viewmat/viewinv/vec/co/obmat por `memcmp` e um bitmask
  `dynupdate_computed`, já que materiais diferentes podem pedir subconjuntos diferentes de
  `DYN_LAMP_*` da mesma lamp. Hit evita `mul_m4_m4m4`/`mul_mat3_m4_v3` quando a mesma lamp é
  atualizada de novo com a mesma view (caso comum: todos os materiais do frame compartilham a
  câmera).
- **RA2 corrigido** (`gpu_material.c` `GPU_material_bind_uniforms`): cache de inversas em
  `GPUMaterial` (`invcache_*`, resetado por bind como `objectlay_valid`): quando o mesmo
  `obmat`+`viewmat` repete dentro da mesma ativação do material (multi-passe do mesmo objeto —
  z-prepass, sombra, principal, halo), `localtoviewmat`, `normalmat` e `invlocaltoviewmat` são
  reaproveitados em vez de recalculados via `invert_m3_m3`/`invert_m4_m4`.
- **GP3 analisado, não alterado**: o único chamador de `GPU_verify_image` com `compare=0`
  (`GPU_texture_from_blender`) depende do `bindcode` real retornado pela função; o atalho
  `compare=1` já existente devolve só um booleano, então trocar o flag corromperia o texture id.
  Corrigir direito exige reescrever o atalho para devolver o bindcode já conhecido
  (`ima->gputexture[gputt]->bindcode`), mudança mais profunda nos outros 4 chamadores da função —
  fora do escopo seguro desta sessão.
- **GP4 confirmado sem alteração**: mantém a conclusão de 2026-10-09 (cache de uniform já testado,
  sem ganho mensurável no RolimaRacer porque os inputs dinâmicos desse caminho mudam de fato todo
  frame nessa cena).
- **GP5 analisado, não alterado**: `GPU_lamp_visible` depende de `material->ma`, então um cache
  por lamp (como GP6) daria resultado incorreto entre materiais com visibilidade de camada
  diferente para a mesma lamp; custo baixo/prioridade baixa já no relatório não justifica o cache
  por par (lamp, material).
- **GP7 analisado, não alterado**: cache de `FindProbe` por posição do objeto não cobre o caso da
  sonda em si se mover com o objeto parado (regressão visual silenciosa); correção completa exige
  contador de geração em `KX_TextureRendererManager` para as posições dos `viewpoint` das sondas,
  desenho documentado para retomada.

Build: `bf_gpu` (alvo específico contendo `gpu_material.c`) e `RangeRuntime`/`RangeEngine`
completos compilados do zero neste worktree (sem build dir prévio) via CMake+Ninja com
Cycles/CUDA desligados só para acelerar esta verificação (configuração de teste, não committada).
Medição com `tools/debug/cenas/criar_cena_luzes_sombra.py` (40 cubos + chão, 2 materiais, 3 spots
com sombra) via `tools/debug/auditar_trabalho_repetido.py`, rodadas de 10 s: contadores de GL
(`lightUniforms` ~334, `drawCalls` 164, `physicsMs` ~0,05-0,06 ms) idênticos antes/depois do GP6 e
do RA2 dentro do ruído de medição, confirmando ausência de regressão — a cena não tem materiais ×
lamps nem passes por objeto suficientes para destacar o ganho de CPU acima do ruído dos
instrumentos existentes (não há contador dedicado a "lamp matrix recompute" nem a
`GPU_RENDER_INVERSE` nesta cena). Ambas as correções são estritamente redundantes com a mesma
saída (zero risco identificado) e escalam com N_materiais × N_lamps (GP6) ou N_passes por objeto
(RA2); cenas maiores devem mostrar o ganho que esta não evidenciou numericamente.

## 2026-10-11 - Auditoria Spawn/remoção/LibLoad: SP4/SP5 medidos, SP12 confirmado, SP13 corrigido

- **SP12 não era pendência:** `KX_AddObjectActuator::ResolveOriginalObject` já usa
  `KX_Scene::FindInactiveObjectAcrossScenes`, apoiado no índice O(1)
  `m_inactiveNameIndex` desde 2026-10-05. O índice cobre inserção, remoção, merge
  de LibLoad e o raro nome duplicado preservando “primeiro da lista vence”.
- **SP13:** `RAS_BatchGroup::SplitMeshUser` chama `OnMeshUserSplit`, que já remove o
  objeto do `KX_BatchGroup` e atualiza a referência. `KX_BatchGroup::SplitObjects`
  repetia a mesma remoção depois do retorno. A segunda busca linear foi removida;
  o `Split` e o upload do VBO continuam necessários e inalterados.
- **SP4/SP5, medição A/B:** uma cena temporária com uma icosfera subdividida 5 (hull) e um grid 128×128 (BVH),
  18 spawns alternados de cada tipo e `time.perf_counter()` ao redor de `addObject()` descartou o primeiro de
  cada sequência. Ao reconstruir reversivelmente o runtime base e depois restaurar a mudança: SP4 caiu de
  **6,645 para 0,182 ms** na média de 17 spawns steady (−97,3%; ~36,5×). SP5 foi de **0,845 para 0,708 ms**;
  confirma a rota sem regressão, mas não demonstra ganho de parede isolável, pois o setup restante do Bullet
  domina. O runtime final foi reconstruído e repetiu 0,182/0,708 ms com `PASS`; uma
  rodada adicional no binário final deu 0,154/0,600 ms e também passou.
- **SP4:** o `CcdShapeConstructionInfo` já é compartilhado pelas réplicas da mesma
  malha. Os pontos do hull agora são retidos nele após o primeiro `CreateBulletShape`;
  os spawns seguintes não fazem hash, cópia do cache `.cooked` ou
  `btConvexHullComputer`. `UpdateMesh` e `ProcessReplica` invalidam os pontos antes
  de trocar a geometria, inclusive para um deformer/`ReplaceMesh`.
- **SP5:** a chave da BVH também fica no
  `CcdShapeConstructionInfo`, portanto cópias normais não re-hasham os vértices e
  índices. A invalidação é junto da geometria em `UpdateMesh`/`ProcessReplica`; o
  lote de conversão mantém o hash paralelo existente. SP6/SP7 foram avaliados e continuam adiados: `RemoveValue`
  remove todas as ocorrências e a fila de eutanásia é FIFO para preservar a ordem e evitar dupla remoção de filho.
  SP9/SP10/SP11/SP14/SP15 também foram confirmados como adiados pelos contratos de Bullet, hot-reload,
  conversão/merge e ownership de meshes; a evidência por item está na tabela da auditoria.
- Configurado build Release próprio do worktree e compilado com êxito
  `KX_BatchGroup.cpp.obj`; após a alteração do header, recompilado e relinkado
  com êxito `ge_physics_bullet` e `KX_SoftBodyDeformer.cpp.obj`.
- **Regressão runtime SP4/SP5:** `RangeRuntime` foi relinkado e executou uma
  cena temporária controlada. Ela instanciou alternadamente 48 réplicas
  `RIGID_BODY`/`CONVEX_HULL` e 48 `STATIC`/`TRIANGLE_MESH` da mesma malha de
  cada tipo; o resultado persistido foi `PASS`, com 96 criações, zero retornos
  nulos e todos os objetos presentes ao fim. A cena foi reaberta em background:
  confirmou câmera, os dois tipos de bounds e o controlador Python. Isso valida
  o caminho funcional e o ciclo de vida do cache; não mede seu ganho. Uma
  comparação de desempenho deve usar a mesma cena no baseline e nesta alteração,
  com contadores temporários do cálculo de hull/hash BVH ou outra métrica
  diretamente sensível ao trabalho removido.

## 2026-10-11 - SP4/SP5 (cache de hull/BVH no spawn): cache implementado, validação ainda pendente

Worktree `codex/auditoria-spawn-liblod`. O Codex implementou o cache por `KX_Mesh` para SP4
(`btConvexHullComputer` por cópia) e SP5 (`shared_bvh_key`), mas reportou que o build completo do
RangeRuntime com as mudanças foi interrompido antes de terminar — não conta como validação.

Plano proposto para validar de fato: recompilar/linkar o RangeRuntime completo; criar uma cena
temporária controlada (um template inativo com colisão convexa e outro com mesh/BVH, um script
gera muitas réplicas da mesma malha, registra sucesso e fecha sozinho); rodar a cena no runtime e
confirmar pelo log que todas as réplicas nascem, simulam física e são removidas sem crash; e, para
medir o ganho, comparar baseline × alteração com um contador temporário de cálculo de hull/hash
BVH (o medidor geral de frame tende a não ser sensível, já que o cache elimina trabalho interno de
construção, não trabalho por frame) — instrumentação a ser removida antes de entregar.

Status em `docs/auditoria-suspeitos.md`: SP4/SP5 passam de "adiado" para "implementado, validação
pendente".

## 2026-10-10 - Troca de layer no editor: cache de shaders, aquecimento dos layers escondidos e medição

- Cache de shaders do editor (`gpu_shader_editor_cache.c`): binários dos materiais da viewport ficam em `%LOCALAPPDATA%\AnastacioEngine\ShaderCache\editor.shaders` (chave da GPU/driver, limite 256 MB), lidos após `GPU_init` e gravados no `WM_exit` e ao fim do aquecimento. São os ganchos padrão de `GPU_shader_binary_cache_set`: o Play põe os do `.cooked` e, ao limpar, os do editor voltam. `RANGE_NO_EDITOR_SHADER_CACHE=1` desliga.
- Buffers de malha (`gpu_buffer_setup`): preenchidos na CPU e enviados com `glBufferData`; o `glMapBuffer` esperava a GPU/driver (até 8,6 s para 137 KB no RolimaRacer).
- Aquecimento dos layers escondidos (`view3d_warmup_step`): 3 s após abrir o arquivo ou trocar de cena, os objetos dos layers que a vista não mostra são desenhados com cor e profundidade desligadas, ~30 ms por quadro, com a barra "Preparing Layers" no Info (job, cancelável). O driver da AMD compila de fato no primeiro desenho real (mesmo com binário do cache), 1–3 s por objeto; assim isso acontece antes de ligar o layer. `RANGE_NO_SHADER_WARMUP=1` desliga.
- Pré-compilação paralela na troca de layer foi tentada e desligada: programas enviados e não usados eram apagados enquanto o driver AMD compilava, congelando o editor ~30 s.
- Troca pelos botões do cabeçalho (RNA `layers`) passa pelo mesmo caminho da tecla (`ED_view3d_layers_shown`).
- Medição: com `RANGE_SHADER_LOG`, linhas `layer_switch` (total, dag, update, desenho, shaders, imagens, buffers), `draw_object` (objetos acima de 10 ms: buffers, shader, begin/bind de material, imagens), `buffer` e `warmup`; shader do cache sai como `cached`. `tools/debug/abrir_engine_log_layer.bat` abre o editor com o log em `debug-logs\layer_log.txt`.
- RolimaRacer (RX 6800M): ligar todos os layers foi de 9–46 s para ~50 ms com caches quentes. Pendente: confirmar com caches frios que, esperando a barra terminar, a primeira troca fica curta.

## 2026-10-10 - Ferramentas do 2D Filter custom: erros na linha do texto, recarga, uniforms e modelos

- Erro de compilação de filtro custom: o console cita o nome do Text (ou `addFilter(n)`) e as linhas do texto (`#line 1` só para fontes do usuário; antes `#line 0` deslocava uma linha). `GPU_shader_last_error_log()` guarda o log da última falha e ele fica em `filter.compileLog`. Embutidos continuam com `#line 0`, sem invalidar o cache de binários.
- Texto externo (`.glsl` em disco) do atuador é conferido 2x/s durante o jogo (`KX_2DFilterManager::ReloadChangedSources`, `BLI_stat`) e recompilado ao salvar; falhou, o programa anterior continua. `filter.recompile(fonte=None)`, `sourceName`, `sourcePath`. Recompilar refaz as propriedades de jogo ligadas (antes a lista era filtrada na 1ª compilação).
- Entradas estáveis: `bgl_ViewMatrix`, `bgl_ProjectionMatrix`, `bgl_InverseViewMatrix`, `bgl_InverseProjectionMatrix`, `bgl_PreviousViewProjectionMatrix`, `bgl_Resolution`, `bgl_Time`, `bgl_Frame` e `bgl_PreviousTexture` (imagem final do quadro anterior, RGBA16F na unidade 17; só alocada/copiada enquanto um filtro ativo a usa; desligada no Web). Normal: reconstruir da profundidade (exemplos na doc), sem buffer novo.
- `filter.activeUniforms` (nome, tipo, tamanho via `glGetActiveUniform`) e `filter.setUniform(nome, valor)` com o tipo do shader, reaplicado após recompilar.
- Modelos em Text Editor > Templates > 2D Filters (GLSL): SSAO, SSGI simples com reprojeção temporal, bloom em um passe e contorno. Referência em `docs/2d-filters.md`.
- Teste: `tools/debug/cenas/criar_cena_filtro2d.py` (erro citado na linha 3; recompile OK; KeyError/ValueError do `setUniform`; arquivo externo com erro mantém o filtro e mostra o log, corrigido recompila; os 4 modelos compilam; 60 FPS com vsync, 10 s). Avaliação visual dos modelos pendente com o usuário.

## 2026-10-10 - Qualidade de textura por mipmap, filtros sem recarga e tamanho de sombra em tempo real

- `Range.render.setTextureQuality(0/1/2)`/`getTextureQuality()`: só a textura em alta fica no projeto; no envio para a GPU caem os maiores níveis de mipmap (metade/um quarto), nunca abaixo de 256 px no lado maior e só em texturas com mipmap. DDS pula os níveis gravados no arquivo. Trocar recarrega as texturas do jogo e dos arquivos do LibLoad; no editor o valor volta ao sair do jogo.
- `setAnisotropicFiltering` e `setMipmapping` (linear/nearest, desligar) só atualizam os filtros das texturas carregadas (`GPU_update_image_filters`), sem `GPU_free_images`; antes recarregavam todas as texturas e ignoravam as do LibLoad. Linear <-> nearest antes não chegava às texturas já carregadas.
- Geração de mipmap na GPU aceitava só `GL_EXT_framebuffer_object`; agora também GL 3.0/ARB, como a função que gera.
- Mipmap desligado: o min filter das texturas sem mipmap era `GL_LINEAR` e o mag `GL_NEAREST`; agora ambos nearest (exibição sem filtro). DDS com um nível só não fica com filtro de mipmap; cabeçalho com 0 níveis cai para descompactado.
- Anisotrópico padrão do jogo exportado 2 -> 8.
- `light.shadowMapSize` (leitura/escrita): redimensiona o mapa de sombra de Sun/Spot sem recompilar (`GPU_texture_resize_2D` mantém os objetos de textura que os materiais referenciam); cascatas mantêm a proporção; o valor é reaplicado se a lâmpada da GPU for recriada (`setGLSLMaterialSetting`).
- Teste: `tools/debug/cenas/criar_cena_textura_qualidade.py` (textura 1024: 1024/512/256/1024; aniso 16 no mesmo frame; nearest 0x2701, none 0x2600; sombra 2048 -> 512, mantida após recriar a lâmpada, -> 1024). Avaliação visual da sombra pendente no RolimaRacer.

## 2026-10-10 - Deform da armature: correções em RanGE Optimized e GPU Skinning

- RanGE Optimized: vértice com peso só em grupo sem osso de deformação virava NaN (divisão por zero) e herdava a normal do vértice anterior; agora fica na pose de repouso, como no Blender. A normal ignorava a rotação entre armature e malha; agora usa a mesma paleta de matrizes da GPU (pre/post embutidos), com a rotação misturada pelos pesos.
- GPU Skinning: aviso de fallback saía a cada frame (agora uma vez); a paleta só vai para o shader quando a GPU está ativa (antes um fallback com material GPU Skinning seria deformado duas vezes); shape keys agora chegam ao VBO; caixa de culling/LOD calculada pelos ossos (caixa de repouso de cada grupo transformada pelo osso) em vez de ficar na pose de repouso; grupos sem osso de deformação saem dos pesos da GPU, como na CPU.
- Caixa com auto update desligado não fica mais invertida.
- Crash na reinicialização do aquecimento de shaders (GPUTexture negative refcount): `GPU_pass_load_images` (8b50d426) deixava a textura da imagem no input do pass, que a liberava ao ser destruído sem nunca ter sido desenhado.
- Descrições das opções de Deform e Culling no painel.
- RolimaRacer (cópia de teste, 10 pilotos, 30 s): Blender ~1,4 ms de Skinning, RanGE Optimized ~1,6 ms, GPU ~0,3-0,8 ms; nenhum crash.
- Pendente: Culling "Full" continua igual a "None" para armatures com malha deformada (91f7d8c0); torná-lo útil exige atualizar o skin só quando a malha volta a ser vista.

## 2026-10-10 - LOD de malha deformada mede do corpo, não da origem

- `KX_GameObject::UpdateLod` media a distância da origem do objeto. No ragdoll do RolimaRacer o corpo do piloto (filho da armature, presa ao carro) voa com os ossos e a origem fica no carro: com o carro longe, o piloto trocava para LOD baixo mesmo com a câmera do ragdoll colada nele. Objetos com deformer e bounds automáticos (skinning na CPU, shape/modifier) agora medem do centro da caixa deformada; estáticos seguem na origem. Skinning na GPU não atualiza a caixa (continua na pose de repouso).
- RolimaRacer (jogo `d70b243`): a câmera do ragdoll segue o `foco_camera_ragdoll` do próprio piloto (grupo do personagem ou o mais perto do carro no início), não o primeiro dos 10 da cena; grava `ref_camera_ragdoll`, lido pelo DoF.
- Verificação: `RangeEngine`/`RangeRuntime` compilados; cópia de teste com 10 pilotos e 4 ragdolls (tecla V): câmera no corpo do jogador em todos e corpo em LOD 0 com a origem a 10,3 m da câmera (LOD 1 começa em 10 m); usuário conferiu no jogo.

## 2026-10-10 - Travadas do RolimaRacer: imagens de nós no load e resolução dinâmica

- **Pico de ~39 ms em `cam.buckets`** (aberto desde 2026-10-09, visto em todas as rodadas recentes): era o primeiro desenho das nuvens. `clouds.png` (1024x512, 38 ms entre leitura e mipmaps) está no material `sprite.001`, usado só como nó Material dentro de `NuvemNodes`. O load sobe as imagens dos slots do material, não as de dentro da árvore de nós; essas subiam no `GPU_pass_bind` do primeiro desenho. Agora `BL_BlenderShader::ReloadMaterial` chama `GPU_material_load_images` (→ `GPU_pass_load_images`, que sobe as imagens de todas as entradas do pass e restaura a textura ligada na unidade ativa).
- **Resolução dinâmica só descia:** o timer de GPU (`GL_TIME_ELAPSED`) era encerrado depois do `UpdateSleepTime()`, e o sono do limite de FPS (~11 ms a 60 FPS) contava como GPU. A medida ficava em ~16 ms: nunca abaixo de 85% do alvo para subir, e qualquer oscilação acima de 105% baixava 5%. No RolimaRacer (escala AUTO aplicada desde o jogo `920cb28`) cada degrau recriava os buffers da tela: 120-170 texturas por rodada de 40 s, de 2560x1440 até 1152x648. O timer agora termina antes do sono.
- **`Speed_FX` reconvertida a cada nitro/velocidade:** os atuadores `FX_Line_speed` (Add Overlay) e `Remove FX` da câmera do carro (`Empty.camera.MASTER`, `.001`, `Empty.camera.CARRO`) destruíam e convertiam a cena de novo: 2 filtros de câmera + 2 do `SpeedLinesFX` + offscreen de meia tela a cada 1-6 s. Com **Preload** no add e **Keep** no remove (recurso de `cd76be52`) ela é convertida uma vez. Ajuste do `.range` do jogo, feito só na cópia de teste.
- `RANGE_SHADER_LOG` grava também as imagens enviadas (`image WxH [mipmap] nome`, com o tempo desde a leitura do arquivo) — `GPU_profile_log_image` em `GPU_verify_image`. `tools/debug/abrir_rolima_profile.bat` abre o RolimaRacer no player com os dois logs.
- Verificação: `RangeRuntime` compilado; cópia `RolimaRacer.perf-autopilot.range` (pede a Pista_1 direto, 1 piloto, tecla I = piloto automático), rodadas de 40 s: antes 1 pico de 44,8 ms no quadro em que as nuvens aparecem; depois nenhum quadro acima de 25 ms, nenhuma textura criada na corrida e `Speed_FX` convertida 1 vez. Falta: editor (`RangeEngine`) não recompilado (estava aberto); rodada com 10 pilotos pelo menu; ragdoll (~800 ms no swap) segue aberto.

## 2026-10-09 - Debug Mode: profile revisado, gráficos de barras/pizza e fonte maior

- Categoria nova `tc_components` ("Components"): os componentes Python rodavam dentro de `KX_Scene::LogicUpdateFrame` e o tempo deles aparecia como "Actuators" (no RolimaRacer era a maior linha do profile). `getProfileInfo()` ganha a chave `"Components"`; "Actuators" passa a ser só atuadores + áudio 3D.
- Porcentagens do painel Profile e de `getProfileInfo()`: o tempo (média de 25 quadros) era dividido pelo tempo do último quadro sozinho, então pulavam e não somavam 100. Agora dividem pela soma das médias.
- Atribuições corrigidas em `KX_SimulationPipeline`: cutscene contava em Skinning/ActivityCulling (agora Logic), earthquake em UpdateParents/Logic (agora Physics) e o `EndTick` da rede em ParticleUpdate (agora Overhead).
- Painel Profile: cor de "Sleeping" e "GPU Latency" estava trocada (a regra invertida "pouco é ruim" vale para Sleeping); cor de FPS < 24 era amarela e 24-30 vermelha (invertido); RenderRate/AnimationRate ficavam congelados com Show Profile ligado e Show Framerate desligado.
- Graph Profiler: lia só as 8 primeiras categorias de uma lista antiga. Agora soma todas em 10 grupos (Physics, Logic+Actuators, Components, Animations+Skinning, Scenegraph, Culling, Render, Shadows, Overhead, GPU Latency) e tem seletor **Chart**: Timeline, Bars (ordenado, com ms e %) e Pie. Em Bars/Pie a caixa **Sleeping** conta o tempo ocioso como fatia, e aí as porcentagens são as mesmas do painel Profile.
- Fonte: painel Profile, barra de cima e painéis do Debug Mode usam a fonte da engine gerada em 14 px (`KX_Imgui::RequestDefaultFont`), em vez da de 12 px reduzida a 80%.
- Painéis Scene/Options: ID único para objetos de mesmo nome, seleção limpa quando o jogo remove o objeto (ponteiro solto), destaque segue a câmera ativa, Show Framerate/Profile/Debug Properties viram caixas de seleção.
- Verificação: build RangeEngine/RangeRuntime ok; `tools/debug/cenas/criar_cena_profile_categorias.py` 4/4 no runtime (componente de 2 ms cai em Components, Actuators 0,00 ms, porcentagens somam 100). Falta: conferir no jogo os gráficos novos e a fonte da barra de cima.

## 2026-10-10 - gameOb.hiddenFromCamera: objeto escondido de uma câmera só

- `KX_GameObject.hiddenFromCamera` (Python, lê/escreve uma `KX_Camera` ou `None`): o objeto continua visível para as outras câmeras e some só da indicada. Uso: tela dividida, em que a câmera de primeira pessoa de um jogador esconde o próprio tronco e a do outro jogador ainda o vê. Filtro em `KX_RenderPipeline::RenderCamera` sobre uma cópia da lista de visíveis (o cache de culling é compartilhado entre câmeras com o mesmo cullingcam), só quando algum objeto usa o recurso (`s_hiddenFromCameraCount`). Réplicas nascem sem câmera; remover a câmera da cena limpa as referências (`KX_Scene::NewRemoveObject`). Não vale para sombras nem para a cópia de câmera do modo estéreo.
- Antes não dava para fazer em Python: `pre_draw_setup` roda para todas as câmeras antes de qualquer culling e `pre_draw` depois do culling da câmera.
- RolimaRacer: `fp_body_visibility.py` passa a usar `hiddenFromCamera` com a câmera de primeira pessoa do carro (`camera_change.py` grava `camera_foot` no colisor); sem o atributo, mantém o `visible = False` antigo. Também no Rolima: o cubo branco do multiplayer era `Empty.camera.MASTER.001` do `group_Cameras_Multiplayer` sem `hide_render` (corrigido no `.range`).
- Verificação: build RangeEngine/RangeRuntime ok; cena mínima com duas câmeras em tela dividida no runtime: atribuir/ler, `TypeError` para objeto que não é câmera, referência limpa ao remover a câmera, e no print o cubo aparece na metade da câmera 1 e não na da câmera 2. No RolimaRacer, multiplayer com um jogador em primeira pessoa: o outro vê o piloto inteiro (testado pelo usuário).

## 2026-10-09 - Controle na tela: layout de corrida (stick, setas ou inclinar)

- `tools/web/package-web.py`: layout `race` (gamepad 0): stick esquerdo na direção, gatilhos nos pedais (eixo 5 acelera, 4 freia), A/B/X/Y, Start e RB pequenos no topo. Tipos novos de controle, que valem para qualquer layout: botão com alvo `axis` (com `value`; duas setas opostas se anulam), `tilt` (a gravidade de `Module.rangeMotion` vira um eixo; `full` = seno da inclinação de curso todo) e `switch` (troca o layout inteiro pelo próximo da lista e guarda a escolha em `localStorage`). No `race`, o `switch` alterna stick → setas → inclinar; o jogo lê sempre o mesmo gamepad. Botões aceitam `left`, `top` e `size` (`small`/`wide`).
- `range_web/touch.py`: `race` em `LAYOUTS`/`_REACH` (com gatilhos, Start e RB); painel Web/Android: opção "Racing (steer + pedals)" com pt/es/ru.
- Sem mudança de C++: a ponte `Module.rangePad` já levava os seis eixos.
- RolimaRacer (fora deste repositório): controles do carro e das câmeras passaram a ler o Range Input System (`KeyMapping/Rolima*.json`, gerados de `scripts/input/InputConfig.py`), com leitor por jogador (tela dividida) e botões do controle na numeração da engine (Pause no Start; antes caía no clique do analógico).
- Verificação: `test_range_web.py` 40/40; JS da página com `node --check`; no Edge headless com toques simulados: gatilhos, botões, Start/RB, setas (esquerda+direita = 0), inclinar (30° = curso todo, zona morta) e a troca dos três modos. Falta: celular de verdade, e o pacote Web/APK do RolimaRacer (ainda não gerado com este layout).
- Achados não corrigidos no Input System: `process_scale` (`KX_InputTable.cpp`) tem erro de precedência no fator; `INDEX` de joystick em texto é lido como 0 (`valueint`); dois gatilhos na mesma ação não se subtraem; `inputMaps` monta um dict novo a cada leitura.

## 2026-10-09 - Cenas: Preload/Keep no atuador Scene e scene.end(keep=True)

- Atuador Scene: caixa **Preload** em Set/Add Overlay/Add Background (`use_preload`, flag `ACT_SCENE_PRELOAD` no antigo `pad1` de `bSceneActuator`, sem mudar o layout). Quando a cena dona do atuador é convertida, a cena alvo é pré-carregada; o add depois só insere a cena pronta.
- Atuador Remove Scene: caixa **Keep** (`use_keep`, `ACT_SCENE_KEEP`) e `scene.end(keep=True)`: a cena sai da lista e fica pausada (sem lógica, física ou desenho), sem ser destruída; o próximo add/replace do mesmo nome a devolve como estava, retomada. Liberada no stop da engine.
- `preloadScene` só enfileira (thread safe: o actuator pode ser convertido no LibLoad assíncrono); a checagem e a conversão rodam no fim do quadro.
- Conversor Logic Bricks → Python: Preload vira `awake(self, args)` com `logic.preloadScene(args.get(...))` (roda 1 quadro antes do `start`); Keep vira `sc.end(keep=True)`.
- RolimaRacer: `BrainCore.py` pré-carrega `_vignette` e `_pause` no estado 3 do loading.
- Profiler: com `RANGE_SHADER_LOG`, o SPIKE lista `firstbind:` (programas usados pela 1ª vez no quadro e no anterior). Achado: travadas de ~800 ms no swap ao voltar do ragdoll, sem shader novo; investigação aberta.
- Componente Python: `awake()` e `start()` agora rodam juntos no 1º quadro, e `update()` a partir do 2º. Antes o `awake()` ocupava o 1º quadro sozinho e `start()` + `update()` vinham no 2º. Ordem de um quadro: sensores/controllers → componentes → actuators; o `start()` agora cai no mesmo quadro dos primeiros bricks. `RANGE_COMPONENT_LEGACY_START=1` volta o horário antigo para comparar. Achado no RolimaRacer: o `PlayerController` procurava o piloto (`init_all`) antes de o `add_all_players` prendê-lo e o boneco ficava em pose T; o jogo dependia do quadro de atraso. Corrigido no jogo (`init_all` espera `can_start_logic`).
- Verificação: build RangeEngine/RangeRuntime ok; `tools/debug/cenas/criar_cena_preload_keep.py` 15/15 e `tools/debug/cenas/criar_cena_component_timing.py` 6/6 checagens ok no runtime; conversor testado headless (código compila, sem pendências); RolimaRacer autopilot 22 s sem traceback, 60 FPS, nenhum quadro >16 ms.

## 2026-10-09 - Travadas do RolimaRacer: preloadScene e instrumentos de pico

- Medição (`debug-logs/travadas-20261009a`..`k`, rodadas de ~22 s, cache de shader quente): o pico de 62 ms em t≈7,5 s era o `addScene` síncrono de `HUD` (13 ms) + `Pista_MiniMap` (44 ms: convert 12, texturas 22, shaders 7). Não era shader compilado no jogo. Também `Contagem_3_2_1` (28 ms, às vezes). O pico de ~40 ms em `render.cameras` é intermitente (4 de 11 rodadas, instante aleatório), cai em `cam.buckets(Pista_1)` sem draw lento ou em `Skinning`, sem shader novo: parece espera de driver/GL, ainda aberto.
- `Range.logic.preloadScene(name)`: converte a cena no fim do quadro (shaders e texturas) sem adicioná-la; `addScene`/`replaceScene`/`addScene(asynchronous=True)` do mesmo nome só inserem a cena pronta (`KX_SceneScheduler::PreloadScene`/`TakeOrConvertScene`). Cenas não usadas são liberadas no stop da engine.
- RolimaRacer: `scripts/AddOverlayScene.py` pré-carrega suas overlays no `start()` (tela de loading ainda aberta). Resultado (`debug-logs/travadas-preload-20261009o`..`q`): nenhum quadro acima de 16 ms em 3 rodadas; antes 62 ms em todas.
- Instrumentos (só com variável ligada): `RANGE_SHADER_LOG=<arquivo>` grava cada shader criado (tempo, flags, nome); o `SPIKE` do `RANGE_PROFILE` anota draws ≥3 ms, fases `cam.*` da câmera e `texreload:<imagem>`.

## 2026-10-09 - Python: céu, destruição, FXAA/grão e quantização de rede

Prioridade 1 de `D:\AnastacioDocs\inventario\faltando_python.md`.

- `KX_WorldInfo`: `skyType`, `useSkyStars`, `starStyle`, `useSkyMoon`, `moonSize`, `moonBrightness`, `useSkyAurora`, `auroraColors`, `atmosphere*` (enums pelos nomes do RNA). A lua é uniform ao vivo; o resto recompila só o shader do world no quadro seguinte. Os valores originais voltam ao fim do jogo. Materiais de objetos mantêm o tipo de céu com que foram compilados.
- `KX_GameObject`: `fragments`, `burstSpeed`, `debrisLifetime`, `useBreakOnCollision`, `useInheritVelocity`, `impactImpulse`, `useExplodeOnImpact`, `useChainReaction`, `dentImpulse`, `useDentOnCollision`, `bendAxis`, `bendAngle`, `bendMaxAngle`, `decal`, `decalSize`, `decalLife`, `maxDecals`, `isDeformable`. Valem por instância: o `KX_DestructionManager` guarda cópias das configurações e liga ou desliga os callbacks de colisão quando os flags mudam.
- `scene.filterManager`: `fxaaEnabled`, `fxaaEdgeThreshold`, `fxaaEdgeThresholdMin`, `fxaaSubpix`, `fxaaSearchSteps`, `grainEnabled`, `grainStrength`.
- `Range.network.replicate(..., quantize={nome: (min, max, bits)})`.
- Já existiam: `light.autoShadowUpdate` e os sync/priority/net_id de rede (`replicate()`, `net_id()`). `use_interpolate` não é lido pelo runtime, então ficou sem binding.
- Verificação: build RangeEngine/RangeRuntime ok; `tools/debug/cenas/criar_cena_api_prioridade1.py` teve 73/73 checagens ok no runtime.

## 2026-10-09 - Lote 4 de auditoria: itens restantes LP/SP

- LP3 (parcial): `KX_RenderPipeline::GetRenderData` usa arrays fixos em vez de `std::vector` por quadro (mono sem alocação). Estéreo adiado.
- LP13: `KX_SoundActuator::Update` só repete `AUD_Handle_getStatus` logo após `play()`.
- Revisados e adiados: LP9, LP10, SP9, SP10, SP12, SP13, SP14, SP15 (motivos em `docs/auditoria-suspeitos.md`).
- Verificação: build RangeEngine/RangeRuntime ok; `demos/escudo.range` 10 s sem erro.

## 2026-10-09 - Lote 3 de auditoria: PY, LP, SP

- LP1: `RAS_2DFilterManager::RenderFilters` sai cedo quando nenhum filtro está `Ok()` (passes de Camera FX desligados não copiam mais a tela inteira por frame).
- LP2: dicionário de profile Python montado só em `GetPyProfileDict()`.
- LP11: `BindTextures` faz um único `MipmapTextures`.
- PY4: `RAS_Shader::SetUniformfv/iv` com valor igual não marca o shader como sujo.
- PY5: `KX_Camera` lens/fov comparam antes de `InvalidateProjectionMatrix`.
- SP2: `ReplaceMesh` sai cedo com a mesma malha única sem física.
- SP8: `FreeBlendFileData` só chama `ReloadMaterials` se uma luz da biblioteca saiu.
- Já corrigidos: PY2 (bug), PY3, SP1, SP3. Adiados/decisão: PY1, PY6, PY7, LP4-LP8, LP12, LP14, SP4-SP7, SP11. Não revisados: LP3, LP9, LP10, LP13, SP9, SP10, SP12-SP15.
- Build ok; demos/escudo.range roda 10 s sem erro. Sem A/B de tempo; LP1 pede medição no RolimaRacer após o nitro.

## 2026-10-09 - Lote 2 de auditoria: CV1/KX2, GL2, GL3, GL4, PH9

- CV1/KX2: `BL_Action` guarda `m_hasObjectIpo` no `Play()` (lista de controladores nao vazia apos `BL_CreateIPO`); `Update()` so liga `m_requestIpo` com canais de transform do objeto. Acao so de bones nao chama mais `UpdateWorldDataThread` na subarvore. Shape/material/cor seguem atualizando.
- GL2: `NET_Replicator::capture` compara o estado bruto (transform, velocidades, props) bit a bit com o anterior; igual pula serializacao e hash (mesmo resultado do protocolo).
- GL3: grade de relevancia so e reconstruida com `m_gridDirty` (objeto adicionado/removido, `hasTransform` mudou ou troca de celula).
- GL4: `ImageBase::m_imageVersion` (sobe em `calcImage`/`refresh` e em `ImageBuff` load/clear/plot); `Texture::refresh` nao reenvia quando imagem, versao, tamanho e mipmap sao os mesmos e nao ha buffer exportado.
- PH9: contador de pares do `CallbackTriggers` virou vetor ordenado reutilizado (sem no de `std::map` por par). `new CcdCollData` por par/frame continua: quem deleta e o `KX_CollisionEventManager`.
- PH6 = GL8 (ja feito).
- Cena `tools/debug/cenas/criar_cena_lote2_auditoria.py` (30 armatures com 20 filhos, cubo com acao de location, 150 caixas com sensor Collision, ImageBuff com plot): comportamento igual antes/depois (mesmos contatos, cubo anda, textura atualiza). A/B de tempo inconclusivo: variacao entre rodadas do mesmo build (Animations 0,4-1,1 ms) maior que a diferenca. GL2/GL3 so compilados, sem teste em rede.

## 2026-10-09 - Lote de auditoria: CV4, PH5, GL7, GL8

- CV4: `BL_SkinDeformer` guarda snapshot de `obmat`/`chan_mat`/`pose_mat`; tempo novo com pose identica nao refaz skinning nem reenvia VBO. Forcado, shape aplicada ou qualquer diferenca ainda refazem.
- PH5: `CcdCharacter::updateAction` so publica a transform no motion state se o ghost mudou.
- GL7: cone do Ray Gaze testa distancia e cosseno (contra `cos(limite)`) antes de `IsSelf`/propriedade/material; sem `acos` por objeto.
- GL8: Near/Radar guardam a ultima transform gravada e so chamam `WriteMotionStateToDynamics` quando muda; cache zerado em replica e reparent.
- Cena `tools/debug/cenas/criar_cena_lote_auditoria.py`: personagem cai/anda/para; Near liga com alvo perto, desliga com dono afastado e volta; Ray com cone acompanha; armature girando e parada sem erro; exit 0. Visual de skinning e FPS pendentes.
- Analisados sem mudanca (motivo na tabela): RA6, RA7, PH1, PH4, PH7, GP3-GP7. CV5/CV6 ja estavam corrigidos. CV1/KX2, GL2-GL4, PH6/PH9 ficam para tarefa propria.

## 2026-10-09 - KX4, RA8; PH8 conferido

- KX4: billboard LOD (`KX_GameObject::UpdateLod`) so chama `NodeSetGlobalOrientation`/`NodeUpdate` quando a orientacao mundial difere da desejada (>1e-5 por elemento); comparar a matriz mundial cobre pai girando. Cena `tools/debug/cenas/criar_cena_kx4_ra8.py`: orientacao fixa com camera parada, gira no frame seguinte ao mover a camera.
- RA8: `RunBatchingNode` reusa `m_batchCounts`/`m_batchIndices` do `RAS_DisplayArrayBucket` em vez de alocar dois vetores por passada. Mesma cena: `KX_BatchGroup` de 40 cubos, 41 -> 2 draws, estavel apos mover um cubo.
- PH8: `ProcessFhSprings` ja testava `body` nulo; tabela da auditoria atualizada. Sem medicao de FPS.

## 2026-10-09 - RA4: cache do stream VBO de instancing

- `RAS_InstancingBuffer` so chama `GPU_buffer_lock_stream` se a lista/ordem de slots, o pass index do material ou alguma revisao de `RAS_MeshUser` mudou; `Realloc` invalida. Apenas `RAS_NORMAL` sem sort; billboard, halo e transparencia ordenada enviam como antes.
- Revisao de `RAS_MeshUser` agora e `uint64_t` vinda de um contador atomico global (na criacao e a cada mudanca de matriz/cor/layer/pass index). Evita ABA: objeto novo reaproveitando a memoria de um removido (addObject/endObject no mesmo tick, replaceMesh, LibFree) nunca repete a revisao cacheada.
- Novo contador `instancingUploads` em `getRenderStats()`. Cena `tools/debug/cenas/criar_cena_ra4_instancing.py` (agora grava todos os frames): 1 draw o tempo todo; uploads 1 inicial, 0 em repouso, 1 ao mover (f60), mudar cor (f100), ocultar (f140) e mostrar (f180). Sem medicao de FPS.
- Observado a parte: o player nao encerra apos `bge.logic.endGame()` nessa cena; nao investigado.

## 2026-10-09 - RA5 aceito; RA4 entregue para continuidade

- Usuario declarou RA5 concluido. Roadmap, relatorio e auditoria agora registram o aceite; nao se atribui ganho de ms/FPS sem medicao.
- RA4 foi iniciado e repassado ao Claude em `docs/auditoria-handoff-claude.md`. Editor e player compilaram; o diff local ainda exige a cena/runtime antes de qualquer conclusao: revisoes por `RAS_MeshUser`, snapshot de slots/revisoes no `RAS_InstancingBuffer`, contador `instancingUploads` em `getRenderStats()` e cache somente para instancing normal sem sort. Billboards, halos e transparencia ordenada continuam enviando o VBO a cada passe. Gerador novo: `tools/debug/cenas/criar_cena_ra4_instancing.py`.

## 2026-10-09 - RA5: preparar apenas materiais com geometria ativa no passe

- Confirmado: `PrepareBuckets` chamava `Prepare` (validacao de texturas e atualizacao de luzes) e incrementava `materialBinds` mesmo sem slots ativos. Agora consulta os display-array buckets e prepara somente materiais com geometria ativa no passe atual. Preparacao continua antes de `GenerateTree`; override permanece com retorno antecipado. Sem cache entre frames ou mudanca de layout de dados.
- Gerador reutilizavel `tools/debug/cenas/criar_cena_ra5.py`: 24 cubos com materiais Principled distintos, ocultacao/retorno, saida/entrada do frustum e ocultacao total. Cena reaberta e inspecionada; player anterior/corrigido encerraram com exit code 0 e sete amostras com draws identicos (24/1/24/1/24/0/24). `materialBinds` antes: 25 em todas; depois: 24/1/24/1/24/0/24. O contador mede preparacoes neste caminho, nao binds GL efetivos. Nenhum ganho de FPS atribuido.
- Editor/player compilados com vcvars64/VSLANG=1033, incluindo dependencias do header. Primeira linkagem falhou LNK1104 porque o player da referencia ainda estava aberto; apos encerramento confirmado, segunda tentativa passou. Ollama recusou conexao; leitura direta dos efeitos de Prepare/UpdateTextures usada como fallback. Evidencias em `%TEMP%/anastacio-ra5/`. Visual, texturas dinamicas e multiplos passes de sombra/probe no jogo real permanecem para validacao. Alteracoes preexistentes nos dois repositorios preservadas; sem commit.
- Variante `ALPHA_SORT` tambem encerrou com exit code 0 e as mesmas sete amostras de draws/preparacoes da versao opaca corrigida, sem erros Python/shader nos logs. Inspecao inicial corrigida para usar nome no membership da colecao bpy; gerador da variante corrigido para `mat.alpha`, pois o Principled legado nao tem socket Alpha. Falhas restritas aos scripts temporarios. Documentacao e diff verificados.
- Estado informado pelo usuario nesta retomada: RA3 validado no jogo e integrado em `12741810`; lote GL integrado a partir de `4fc43c91` (commit local `1d2462da`). Efeitos de roda do RolimaRacer validados, commits `81d53c1`/`ee41118`; nenhuma mudanca no jogo nesta sessao.

## 2026-10-09 - GL5/GL6/GL9/GL10: auditoria GameLogic integrada

- Integrado o lote validado em worktree isolada: cache seguro de literais no Property Actuator (GL5), uma só leitura de texto no Property Sensor Changed (GL6), retorno cedo do TimeEventManager sem Timer (GL9) e menos lookups/varreduras invariantes nos sensores de teclado/mouse (GL10).
- Cena de 300 objetos, 1.800 atuadores e 300 sensores de cada tipo: seis rodadas alternadas mantiveram valores finais idênticos e reduziram a média de 1,82 para 1,26 ms/frame (-31%). GL6 e GL9 foram falsos positivos em grande parte; o relatório preserva limites e ramos não alterados em [auditoria-claude-resultados.md](auditoria-claude-resultados.md).

## 2026-10-09 - RA3: benchmark A/B isolado

- Reconstruidos dois players isolados com os mesmos objetos/headers atuais, variando apenas a chamada zsort em RAS_MeshSlot (map/sort/unmap antigo versus cache). Ambiente VSLANG/vcvars; builds e dependencias fora de build/bin. Isso isola ativacao do cache, sem alegar baseline historico completo. Fontes C++ e trabalho do Claude preservados.
- Copia da cena aprovada com `tools/debug/cenas/preparar_benchmark_ra3.py`: post_draw conta frames, movimento por tempo real, 1280x720, vsync OFF, limites logica/render 10000 Hz, 3 s warmup + 10 s medidos. Tres rodadas por versao/modo, alternadas; 12 runtimes exit 0/END e sem erros Python/shader. Pilotos limitados descartados; diferencial anterior reexecutado com PASS.
- Medianas sem/com cache: repouso 0,6498/0,6497 ms; movimento 0,6225/0,6336 ms. Faixas sobrepostas e variacao alta: ganho/regressao inconclusivos. Profiling separado em repouso passou, mas draw.mesh_slot inclui mais que zsort e nao isola seu custo. Resultados completos, limites e evidencias no [plano RA3](ra3-transparencia-plan.md) e `%TEMP%/anastacio-ra3-benchmark/`.
- Usuario autorizou RolimaRacer/Pista_1; preparada e aberta copia temporaria com caminhos absolutos, sem salvar sobre o original. Visual do jogo real e casos adicionais continuam pendentes. Sem commit.

## 2026-10-09 - RA3: execucao no RolimaRacer/Pista_1

- O jogo original encerrava apos cerca de 20 s porque continha acidentalmente `audit_work.py`: 27 controladores `audit_py` e sensores `audit_always` chamavam `Range.logic.endGame()`. Copia de seguranca criada ao lado do jogo; a instrumentacao foi removida e a cena inicial restaurada para `0_SCN_System` (a limpeza inicial tinha salvo `Speed_FX` como ativa, produzindo tela cinza).
- O player atual carregou o fluxo `0_SCN_System` -> Loading -> `Pista_1`, com `Contagem_3_2_1`, HUD e minimapa. Uma copia de teste no diretorio do projeto solicitou Pista_1 ao BrainCore, preservando caminhos relativos dos componentes; o usuario confirmou que ficou rodando. A tecla I foi enviada apos a carga para testar o piloto automatico, sem inferir visual por log.
- Isto confirma abertura estavel da pista no jogo real e remove o fechamento artificial; nao mede FPS nem substitui inspeção visual detalhada de fumaça/transparencia e dos casos adicionais do plano.
- Revisao final simplificou `UpdateSize`: o VBO ja invalida os centros de poligono, e esta invalidacao propaga a ordem do IBO. Editor/player foram recompilados depois disso; o diferencial MSVC passou novamente (9.600 ordenacoes, 2.005+ comparacoes e retry map/unmap) e a cena automatica concluiu 240 frames, exit 0, sem erros Python/shader.

## 2026-10-09 - RA3: aceite visual da cena controlada

- Usuario confirmou a cena corrigida como correta apos esclarecer T: alterna o objeto esquerdo entre 9 e 5 camadas e restaura a topologia original. Aceite visual registrado no plano, roadmap e relatorio vigente.
- Diferencial/build/runtime ja passaram. Validacao no jogo real e benchmark continuam pendentes; casos adicionais ausentes da cena nao foram considerados aprovados. Nenhum commit nesta etapa.

## 2026-10-09 - RA3: primeira peca do cache de zsort

- Usuario confirmou a cena de referencia adequada para comparacao. Gerador `tools/debug/cenas/criar_cena_ra3_transparencia.py`: ALPHA_SORT, objetos compartilhando malha, duas cameras, movimento/escala negativa, deformacao e substituicao de topologia; controles Opaque/Alpha/Clip/Add. Inspecao bpy e runtime com marcador END passaram.
- Cache no RAS_DisplayArrayStorage representa a ultima direcao efetivamente escrita no IBO compartilhado. Comparacao exata; sorter/comparador preservados. Posicoes, topologia, recriacao/redimensionamento e mapeamento invalidam. FlushIndexMap retorna sucesso do unmap; falhas nao validam o cache.
- Teste isolado MSVC extrai sorter/cache reais com adaptadores minimos e map/unmap simulados: 9600 ordenacoes de referencia e mais de 2000 comparacoes passaram; 1000 chamadas repetidas nao acrescentaram maps apos a primeira. Nao comprova OpenGL real, mathfu, visual ou FPS.
- Editor/player compilados com VSLANG/vcvars. Primeira ligacao do editor falhou LNK1104; ausencia de processo conferida e repeticao passou. Player corrigido terminou 240 frames, exit 0, sem erros Python/shader. Referencia/detalhes em [plano RA3](ra3-transparencia-plan.md).
- Comparacao visual da versao corrigida, jogo real e benchmark pendentes. Sem commit. A copia tentada do player anterior ocorreu depois da ligacao: nao e baseline binario valido.

## 2026-10-09 - RA3: planejamento com checagem visual obrigatoria

- Pedido do usuario incorporado no [plano RA3](ra3-transparencia-plan.md): referencia visual antes de mudar C++, cache em peca pequena, diferencial/build/runtime, comparacao visual antes/depois no player real e medicao separada. Sem avaliacao visual, item permanece pendente.
- Roteiro cobre faces sobrepostas, IBO compartilhado entre objetos com rotacoes diferentes, movimento/escala negativa, troca de camera, geometria/topologia e empates. Materiais de controle e passes adicionais exigem conferir flags/caminho efetivo; ALPHA_SORT e configuracao explicita do caso principal. Map/unmap e recriacao do storage fazem parte dos testes de validade.
- Planejamento e documentacao apenas; nenhuma cena gerada, mudanca C++ ou benchmark nesta etapa. Proxima acao: preparar e executar a cena de referencia para avaliacao do usuario.

## 2026-10-09 - RA3: diagnostico da ordenacao e do IBO compartilhado

- Retomada apos RA2/GP8. `RAS_MeshSlot::RunNode` mapeia o IBO antes de `SortPolygons`; este conserva centros de poligonos, mas cria vector de PolygonSort e executa std::sort por chamada. `FlushIndexMap` desmapeia apos escrever todos os indices. Nao existe teste de repouso nesse caminho.
- O storage pertence ao display array, compartilhado entre slots; cache por objeto permitiria usar a ordem deixada por outro objeto. A chave deve representar a ultima ordem efetivamente escrita no buffer compartilhado. O algoritmo usa apenas a direcao Z da transformacao view x object para comparar profundidades: translacao nao altera a ordem. Posicoes/topologia e recriacao do IBO exigem invalidacao independente; falha de map nao pode validar o cache.
- Refinada a alegacao sobre sombras: RunNode ignora zsort com shader override; BucketManager desliga override para sombras alpha nao-variance, permitindo esse caminho. Nao ocorre em todas as sombras.
- Plano registrado no roadmap para uma primeira peca autocontida, preservando algoritmo e empates, com diferencial para slots/cameras alternados, geometria, recriacao e falha de map, seguido de build/runtime. Apenas leitura e documentacao nesta etapa; sem mudanca C++, benchmark ou ganho alegado. Skill do Claude modificada anteriormente e artefatos nao relacionados preservados.

## 2026-10-09 - Consolidacao KX14 e RA2/GP8 em commit

- Consolidado o cache de Text-Res/estado espacial dos speakers, reutilizacao do produto view x object, Damage seletivo/cache do contador e nome AnastacioRuntime nos textos do dialogo/log Windows. Builds editor/player e testes registrados nas entradas abaixo; player final apos ajuste de nome encerrou com exit code 0 e mesmas seis amostras dent/reset. Inicio do log atualizado confirmado.
- Validacao documental e diff sem erros. Benchmark de FPS, visual e audio no jogo real permanecem pendentes; matrizes inversas continuam por draw. Artefatos e mudancas nao relacionados permanecem fora do commit.

## 2026-10-09 - RA2/GP8: Damage seletivo e contador por programa

- `GPU_material_use_damage` consulta pass e localizacao do uniform no shader linkado; `BL_BlenderShader::UpdateObjectMatrix` so faz dynamic_cast do deformer se o contador Damage esta ativo. Nao conserva ponteiro de deformer nem depende de tipo de material no editor; reload consulta o novo GPUMaterial.
- `GPU_material_bind_damage` usa o helper existente `GPU_shader_uniform_int_cached` para count. Unico escritor desse uniform confirmado por busca; cache pertence ao GPUShader e preserva materiais que compartilham programa, transicoes hit -> zero e programa recriado. Arrays de hits/strength continuam enviados por chamada com count positivo, inclusive quando hits mudam mantendo a contagem.
- Teste C++ extraiu o binder antes/depois e o helper cached real, com estado/GL simulados. 6000 draws diferenciais com dois materiais compartilhando programa: count/arrays finais iguais, arrays com mesma quantidade de envios; contador 6000 -> 3001, sendo 3000 draws em repouso -> 1. Programa novo, sem uniform e sem shader passaram. Sem medida de FPS.
- Editor/player compilados com vcvars64/VSLANG=1033; header GPU recompilou dependencias. Primeira linkagem do player falhou LNK1104; destino ausente/gravavel e processo ausente conferidos, segunda linkagem passou. Sem crash de layout de header.
- Skill `anastacio-cena-de-teste` aplicada: gerador existente `tools/create_damage_marks_test.py` adaptado em `%TEMP%/anastacio-ra2-damage/make.py`, com objeto sem deformer compartilhando material Damage e controlador de dent/reset. Cena gerada e reaberta/inspecionada: material compartilhado, no Damage, Dent, camera e pulso/modulo confirmados. Runtime final exit code 0; tres dent e tres reset aceitos. Logs sem erro de shader; avaliacao visual no jogo real pendente.
- Erro inicial do teste: script temporario chamado `inspect.py` ocultou modulo padrao importado pelo NumPy; falha `No module named bpy` seguida de crash em AUD_initPython. Renomeado para `verify_scene.py`, runtime passou. Nenhum clean rebuild necessario: causa identificada no log como colisao de modulo do teste, nao layout C++.
- Usuario apontou nome RangeRuntime no dialogo. Textos fixos em `GamePlayer/GPG_ghost.cpp` (titulo/mensagem de crash e inicio do log Windows) atualizados para AnastacioRuntime; arquivo de log e variavel RANGE_NO_CRASH_DIALOG preservados. Executavel ja era AnastacioRuntime.exe; este era um texto legado.
- Evidencias em `%TEMP%/anastacio-ra2-damage/`: `before.c`, `after.c`, `damage_test.cpp`/`.exe`, `make.py`, `verify_scene.py`, `test.range`, `inspection.json`, `result.json`, `runtime-valid.txt`. Alteracoes KX14 e primeira peca RA2 preservadas, sem commit. Matrizes inversas continuam por draw; cache adicional depende de justificativa por medicao.

## 2026-10-09 - RA2: produto view x object compartilhado dentro do draw

- Retomada apos KX14; alteracoes locais de texto/speaker preservadas e sem commit. `BL_BlenderShader::UpdateObjectMatrix` delega as matrizes a `GPU_material_bind_uniforms`. Confirmadas ate tres multiplicacoes identicas de view x object quando os builtins local-to-view, normal e inversa coexistem.
- Produto calculado uma vez por chamada, somente com viewmat e algum desses builtins. Inversas, transposta e uploads permanecem no caminho original; sem estado novo, header alterado ou cache entre draws. Objeto, camera, passes de sombra/reflexao e matriz explicita de halo/billboard continuam entradas atuais de cada chamada.
- Teste C temporario extraiu as funcoes anterior/corrigida, com estruturas/API GPU simuladas e helpers matematicos controlados (nao os helpers Blender). 6400 casos diferenciais: todas as 16 combinacoes de builtins de matriz, view nula, info de particulas nula, translacao, shear, escala negativa e matriz zero. Uniforms capturados identicos byte a byte; inversas com contagens iguais; produtos 8400 -> 4900. Primeira compilacao do harness falhou por faltar `true` no stub; definicao adicionada e compilacao/execucao passaram.
- Editor/player compilados com vcvars64/VSLANG=1033. Cena existente e previamente inspecionada do KX11 executada pelo player atualizado com exit code 0: 22 amostras iguais a `after-final.json`, incluindo movimento de camera/luz e escala. Teste funcional sem comparacao visual; nao mede FPS nem a reducao das multiplicacoes dentro desse runtime.
- Damage (RA2/GP8): `GPU_material_bind_damage` retorna antes do upload se damagecountloc == -1; portanto nao ha envio de count=0 para materiais sem o uniform. O dynamic_cast em BL_BlenderShader ocorre antes desse retorno e continua por objeto; materiais com Damage ainda enviam count por draw. Cache de RA1 usa helpers cached explicitos, nao cobre genericamente esses uploads. Esta parte fica para a proxima peca, assim como eventual cache de inversas que exigiria validar todas as entradas e o estado de programas compartilhados.
- Evidencias em `%TEMP%/anastacio-ra2/`: `before.c`, `after.c`, `matrix_test.c`/`.exe`, `runtime-result.json` e logs de runtime. Ganho de tempo/FPS e visual no jogo real pendentes. RA2 parcial, sem commit.

## 2026-10-09 - KX14: cache de Text-Res e estado espacial dos speakers

- KX11 e registros KX12 commitados em `c3a1daf6` (`perf: cache seletivo de transformacao e cone das luzes KX11`). KX13 conferido: travessia direta dos filhos ja corrigida; nenhum novo trabalho nesse item.
- `KX_FontObject::UpdateTextFromProperty` guardava `m_resolution` (float) em `m_res` (string), invocando a atribuicao de um caractere e frustrando o cache. Agora le `Text-Res` uma vez e guarda o texto, inclusive entradas invalidas. So tenta `std::stof` quando o texto muda; falhas preservam a resolucao. Uma propriedade constante deixa de reaplicar a resolucao a cada frame, conforme o cache textual previsto; alteracoes de `Text` continuam pelo caminho existente.
- Teste C++ extraiu os metodos anterior/corrigido com propriedades simuladas e a conversao real `std::stof`. Em 6000 updates diferenciais (numericos, invalido, overflow, mudanca de texto e remocao da propriedade), resolucao/texto coincidiram. Conversoes 6000 -> 6; excecoes 2000 -> 2. Cena reaberta/inspecionada e player com exit code 0: 16 amostras confirmaram repouso, mudancas, preservacao da resolucao em entradas invalidas e remocao/recriacao da propriedade.
- `KX_Speaker` conserva os 10 floats de posicao/velocidade/orientacao relativos a camera, com validade independente. O helper compara bytes e chama apenas setters cujos valores mudaram; so conserva dados aceitos pela API, permitindo nova tentativa apos falha. `play()` e `ProcessReplica()` invalidam os caches, inclusive se o endereco de um handle for reutilizado. Culling/3D math, consulta de status, efeitos e outros parametros de audio continuam no caminho existente.
- Confirmado no backend OpenAL que cada setter espacial trava o device e chama `alSourcefv`; backend Software apenas atribui dados. Teste do helper extraido, com setters simulados: 3000 chamadas em repouso -> 3, mais transicoes, falha/retry e invalidacao de handle passaram. Cena com WAV mono de 4 s empacotado, speakers 3D/2D e template inativo: movimento de speaker/camera, rotacao, pausa/retomada, stop/play e replica. Reaberta/inspecionada; runtime exit code 0, 12 amostras com tempos de reproducao esperados, replica ativa e log sem erros. Tentativas iniciais do gerador usavam objeto ativo para `addObject`; corrigido para template em camada inativa, conforme a API. Estes dados nao substituem avaliacao auditiva do posicionamento/Doppler.
- Particulas: `RAS_ParticleBuffer::SetModelMatrix` apenas copia 16 floats na CPU; o upload do model ocorre depois no draw. Nenhuma mudanca nessa parte de KX14. Editor/player compilados com vcvars64/VSLANG=1033 apos mudanca do header do speaker; dependencias afetadas recompiladas e runtime sem crash.
- Evidencias em `%TEMP%/anastacio-kx14/`: `font_cache_test.cpp`/`.exe`, `make.py`, `test.range`, `verify_scene.py`, `inspection.json`, `result.json`; `audio_cache_test.cpp`/`.exe`, `make_audio.py`, `audio.range`, `verify_audio.py`, `audio-inspection.json`, `audio-result-valid.json` e `audio-runtime-valid.txt`. Reducao de trabalho comprovada nos testes isolados; ganho de FPS/tempo e visual/audio no jogo real nao medidos. KX14 sem commit; usuario pediu encerrar esta conversa apos o item atual. Proxima retomada: RA2, pois RA1 ja consta corrigido.

## 2026-10-09 - KX11: cache seletivo de transformacao e cone implementado

- `GPULamp`, struct privada em `gpu_material.c`, guarda a matriz de entrada, escala e validade. `GPU_lamp_update` normaliza/copia/inverte somente quando a entrada muda (comparacao exata dos 16 floats); `GPU_lamp_update_spot` conserva o cosseno enquanto o angulo permanece igual. Blend continua calculado a cada chamada. Inicializacao pelo Blender invalida ambos os caches; nao houve mudanca em header ou DNA.
- Layer/hide continuam atribuídos por chamada, assim como escalas Hemi/Spot e dimensoes Area (inclusive alteracoes de `Lamp` sem movimento). `gpu_lamp_calc_winmat` continua chamado quando ha shadow buffer, preservando o comportamento das matrizes compartilhadas com Point/CSM. Cores/atenuacao e Static Split nao foram alterados.
- Teste C temporario extraiu as duas funcoes do HEAD anterior e da fonte corrigida. Em 5000 atualizacoes diferenciais (5 tipos), comparou transformacoes normalizadas/inversas, posicao/direcao, escalas, Area, layer/hide, cone e projecao apos sobrescrita simulada. Incluiu translacao, rotacao, escala, angulo/blend, dimensoes/shape Area, invalidacao e matriz zero. Todas passaram; normalizacoes/inversas 5000 -> 30 e cossenos do cone 5000 -> 15. Helpers matematicos e projecao sao substitutos controlados neste teste, nao validacao da GPU ou medida de FPS.
- Cena controlada com material Principled, 2 meshes e 5 luzes (Point Auto Shadow/culling, Spot com sombra, Sun com CSM, Area e Hemi), criada e reaberta/inspecionada pelo editor. Executou por 120 ticks alterando posicao/escala, cone/blend, visibilidade, camera e cor/energia/distancia. Player anterior foi recompilado a partir do C original mantendo as outras correcoes; ambas as execucoes terminaram com exit code 0 e 22 amostras identicas de estado/contadores de sombras. Fonte corrigida restaurada byte a byte e produtos finais recompilados.
- Evidencias em `%TEMP%/anastacio-kx11/`: `make.py`, `test.range`, `verify_scene.py`, `inspection.json`, `cache_test.c`/`.exe`, `before.json`, `after.json` e logs de runtime. Editor/player compilados com vcvars64/VSLANG=1033; primeira linkagem do editor falhou com LNK1104, destino verificado ausente/gravavel e segunda tentativa passou. Visual real e benchmark de FPS permanecem pendentes; nenhum ganho percentual de FPS alegado. Sem commit.

## 2026-10-09 - KX12: UpdateBuckets verificado sem nova correcao

- `KX_Scene::RenderBuckets` chama `KX_GameObject::UpdateBuckets` para os objetos do passe. Matriz e front face so sao atualizados com `DIRTY_RENDER`; `KX_Mesh::UpdateBitmapText` retorna cedo quando o texto permanece igual. Os setters de camada, pass index e cor apenas atribuem dados CPU.
- `RAS_MeshUser::ActivateMeshSlots` preenche a lista de slots ativos para renderizar. `RAS_BucketManager` esvazia essa lista depois do passe por `RemoveActiveMeshSlots`; pular a ativacao para objetos estaticos retiraria esses objetos de passes posteriores. Nao foi identificado trabalho caro redundante que justifique novo cache neste item.
- KX12 classificado como verificado por leitura, sem alteracao C++, build ou benchmark novo. Nenhum ganho de performance atribuido a esta auditoria; KX11/RA9 permanece pendente. Documentacao validada com `tools/check_docs.py`.

## 2026-10-09 - KX11/RA9: atualizacao de luz e limites do cache

- `KX_ShadowRenderer` chama `UpdateDistanceCulling` e `KX_LightObject::Update` para cada luz antes das sombras. `RAS_OpenGLLight::Update` chama os quatro setters GPU; `GPU_lamp_update` normaliza a matriz, inverte e recalcula a projecao quando ha shadow buffer; `GPU_lamp_update_spot` recalcula o cosseno. Cores e atenuacao apenas escrevem dados CPU neste caminho; nao sao chamadas GL/uniforms por objeto.
- Um retorno antecipado baseado apenas em transformacao/parametros da luz nao basta: `GPU_lamp_shadow_point_face_bind` escreve `winmat` para as faces Point; `GPU_lamp_shadow_buffer_bind_matrices` escreve view/win para CSM. Area tambem consulta dimensoes em `Lamp`, e hide depende do culling da camera. Uma futura correcao deve separar o cache dos dados da luz da restauracao das matrizes usadas pelas sombras e preservar essas dependencias.
- A parte de RA9 sobre `dynamicCasterSet` e restrita a Static Split: o set e declarado por luz, mas so recebe casters quando `useStaticSplit` esta ativo. Nao e a reconstrucao do mapa Auto Shadow corrigida no KX10.
- Diagnostico por leitura de codigo, sem alteracao C++ ou alegacao de ganho. Medicao isolada e implementacao de cache seletivo continuam pendentes no roadmap. Documentacao conferida com `tools/check_docs.py`.

## 2026-10-09 - KX10: benchmark antes/depois com ganho medido

- Cena sintetica estatica: 1600 meshes com material, sem colisao, 16 Point com Auto Shadow e alcance 50, camera mirando a cena, Sun, 640x360, vsync OFF e logica a 1000 Hz (limite que ainda introduz espera). Gerador reutilizavel `tools/debug/cenas/criar_cena_benchmark_kx10.py`, derivado dos testes existentes. Cena reaberta e inspecionada: contagens, materiais, sombras/Auto, camera, modulo/funcao e pulso confirmados.
- Comparacao isolou o KX10: compilado temporariamente o CPP anterior, mantendo KX6/KX7; restaurado o CPP corrigido e recompilado `RangeRuntime` com vcvars64/VSLANG=1033. Tres rodadas por versao, cada uma com 3 s de aquecimento e 10 s medidos, profiler desligado: antes 704,3 / 701,9 / 717,9 FPS; depois 899,3 / 903,5 / 908,6 FPS. Medianas 704,3 -> 903,5 FPS (+28,3%); periodo medio correspondente 1,420 -> 1,107 ms. Todas as rodadas encerraram com exit code 0 e mantiveram shadowPasses/lightsShadowUpdated em zero no intervalo medido.
- Rodada separada por versao com profiler existente: media de `render.shadows` apos aquecimento 0,613 -> 0,194 ms (-68,3%, aproximadamente 0,419 ms poupados). 58/75 janelas de 120 frames. FPS acima vem das rodadas sem profiler. Rodadas agrupadas por versao, sem alternancia; resultado limitado a esta carga estatica sintetica, nao e previsao para o jogo real ou sombras continuamente invalidadas.
- Evidencias em `%TEMP%/anastacio-kx10-bench/`: `bench.range`, `inspection.json`, `before-1..3.json`, `after-1..3.json`, logs `before-profile.txt`/`after-profile.txt` e `summary.json`. Fonte corrigida conferida byte a byte com backup; player final compilado com KX10. Spot, deformadores, layers/parametros e visual real continuam pendentes. Sem commit.

## 2026-10-09 - KX10: mapa de casters somente na invalidacao de Auto Shadow

- `AutoShadowStillValid` consulta o mapa persistente da luz e conta casters no snapshot atual; so cria/substitui um `unordered_map` quando a sombra invalida. Preservados filtros de layer/alcance, tolerancia de transformacao, parametros da luz e invalidacao por deformadores. O snapshot de `BuildShadowCullCache` ja e compartilhado entre luzes/passadas no escopo de sombra do frame; varredura por frame e por luz permanece para detectar mudancas. Sem cache entre frames novo.
- `RangeRuntime` compilou com vcvars64/VSLANG=1033. Cena `%TEMP%/anastacio-kx10/test.range` com Point Auto Update, gerador `make.py` e inspecao `verify_scene.py`; `inspection.json` confirmou camera, luz, Auto Update, modulo/funcao e material. Player encerrou com exit code 0 antes e depois do patch. `before.json` e `after.json` tem 18 amostras identicas: 0 passadas em repouso e 6/1 luz apos movimento, saida/entrada do alcance, ocultar/mostrar, escala, movimento da luz e remocao do caster; volta a 0 apos cada evento.
- Removida a construcao/destruicao do mapa no caminho valido por inspecao de codigo; ganho de tempo/FPS nao medido. Spot, deformadores, layers, parametros e visual no jogo real ainda pendentes. KX10 parcial: custo da varredura permanece. KX6/KX7 e demais alteracoes locais preservadas, sem commit.

## 2026-10-09 - KX9: revisao da correcao existente e teste de frustum

- `KX_Camera::UpdateView` ja corrigido no commit `6d8c640d`: compara os 16 elementos de modelview, marca mudanca ao recalcular projecao e so entao liga `frustumDirty`. `ExtractFrustum` reconstrui sob demanda e limpa a flag. Atualizada a linha desatualizada da auditoria; nenhuma alteracao C++ nesta rodada. Culling de objetos continua por frame.
- Cena `%TEMP%/anastacio-kx9/test.range`, gerador `make.py`, inspecao `verify_scene.py` e resultados `inspection.json`/`result.json`. Camera, modulo, funcao e pulso conferidos; player encerrou automaticamente com exit code 0. Consultas `pointInsideFrustum` estaveis em repouso: origem e ponto lateral dentro; mover camera +1000 em X colocou ambos fora, retornar colocou ambos dentro. Lente 16 para 120 colocou ponto lateral fora, mantendo origem dentro; restaurar 16 recuperou classificacao original.
- Teste confirma resposta funcional de modelview/projecao; nao mede numero de reconstrucoes nem ganho em ms/FPS. Stereo, Camera FX e visual no jogo real pendentes. KX6/KX7 e demais alteracoes locais preservadas, sem commit.

## 2026-10-09 - KX8: Auto World Sun sem invalidacao continua reproduzida

- Auditoria de `UpdateAutoWorldSun`: `SG_Node::SetLocalPosition` e `SetLocalOrientation` ja ignoram valores iguais; a recaptura do World compara assinatura (incluindo direcao do sol) antes de `ForceUpdate`. Nenhuma mudanca C++ neste item.
- Cena temporaria `%TEMP%/anastacio-kx8/test.range`, gerador `make.py` e inspecao `verify_scene.py`: Auto World Sun ligado, camera e controlador MODULE conferidos em `inspection.json`. Player encerrou com exit code 0 e escreveu `result.json`. Frames 160/175 e 330/345: `sceneNodeUpdates`, `transformSyncs` e `meshMatrixChanges` zerados. Ao mover camera x=4 para x=8, sol acompanhou +4 em X, mantendo orientacao.
- A primeira execucao falhou porque o script temporario `inspect.py` ocultou o modulo padrao usado por numpy; renomeado para `verify_scene.py`, execucao passou. Nao foi erro de build/engine.
- Evidencia limitada a transformacoes em cena controlada; sombras com cascatas, sol com parent, alteracao de hora/direcao e visual no jogo real pendentes. Sem alegacao de ganho em ms/FPS. KX6/KX7 preservados, sem commit.

## 2026-10-09 - KX7: slow parent dorme no ponto fixo

- `KX_SlowParentRelation` compara exatamente posicao, escala e orientacao antes/depois da interpolacao. Resultado igual deixa de reagendar e de propagar `parentUpdated`. Primeira chamada preserva o reagendamento inicial; mudancas no pai/filho reativam pelo scene graph. Formula mantida, sem epsilon.
- `RangeRuntime` compilou. Cena temporaria `%TEMP%/anastacio-kx7/test.range` inspecionada via bpy e executada ate encerramento automatico: filho convergiu para x=4, retomou ao mover pai e convergiu para x=8. Frames 160/175 e 330/345: `sceneNodeUpdates`, `transformSyncs` e `meshMatrixChanges` em 0; frame 182: x=7.9375 com atualizacoes ativas. Evidencias `inspection.json` e `result.json` na mesma pasta.
- Translacao/repouso/retomada validados; rotacao/escala, visual no jogo real e ganho em ms/FPS pendentes. KX6 preservado, sem commit.

## 2026-10-09 - KX6: anexos de osso dormem com a armature parada

- `BL_ArmatureObject::UpdateTimestep()` agora agenda os filhos com relacao de osso quando uma acao, constraint actuator ou `armature.update()` avanca a pose. A relacao deixou de se reagendar incondicionalmente; armas e acessorios de uma armature ociosa nao percorrem mais sua subarvore a cada frame.
- A relacao ainda marca os descendentes quando executa, preservando anexos ligados ao objeto preso ao osso. `RangeRuntime` recompilou; falta apenas a conferencia visual no jogo real de um objeto preso a osso durante uma animacao.

## 2026-10-09 - KX13: animacao percorre filhos sem alocar vetor temporario

- Os passes de pose e de deformer de `KX_Scene` agora visitam diretamente os filhos de `SG_Node`, preservando a travessia por links sem objeto e encerrando assim que encontra um filho que exige pose. Armatures com muitos filhos deixam de alocar e preencher dois vetores por atualizacao.
- A investigacao tambem descartou a parte de strings do suspeito: `KX_AnimationEventManager::EventCall` armazena `const char*`; a conversao para a string Python so ocorre quando ha evento e callback a chamar.
- `RangeRuntime` recompilou com os warnings preexistentes de ordem de inicializacao e variavel nao usada em `KX_Scene.cpp`.

## 2026-10-09 - KX5: probe nao atualiza animacao seis vezes durante a captura

- A simulacao ja atualiza poses e deformers antes do pipeline de render. `KX_TextureRendererManager` deixou de chamar `UpdateAnimations()` dentro do loop de faces da probe; assim `setHalfAnimations()` continua alternando uma vez por passo, e uma probe cubica nao reavalia a mesma animacao ate seis vezes.
- A selecao de LOD por face foi mantida. A distancia correta para uma reflexao e a distancia da probe, portanto substituir a malha quando ela difere da camera principal e necessario para a imagem capturada.
- `RangeRuntime` recompilou. A confirmacao visual de uma probe atualizada com um objeto em `setHalfAnimations()` permanece para teste no jogo real.

## 2026-10-09 - CV5/CV6: shape keys paradas nao deformam a malha outra vez

- `BL_Action` pede nova deformacao apenas quando a avaliacao e os blends alteram algum `KeyBlock::curval`. `BL_ShapeDeformer` conserva os coeficientes usados anteriormente; curvas em hold deixam de chamar `BKE_key_evaluate_relative`, reskin e upload da malha a cada frame.
- `LoadShapeDrivers()` so habilita `BKE_animsys_evaluate_animdata` e `ForceUpdate()` se a key copiada tiver curvas de driver. Uma armature pai sem driver nao aciona esse caminho.
- `RangeRuntime` recompilou. A cena temporaria criada para medir no player confirmou a estrutura (acao, controlador, camera 16 mm, Sun e materiais contrastantes), mas o player desta sessao encerrou antes de executar o primeiro controlador e nao gerou marcador; a medicao em runtime permanece pendente.

## 2026-10-09 - CV7/CV8: objetos sem acao ativa deixam a atualizacao por frame

- `GetActionManager()` nao registra mais o objeto apenas porque um getter Python consultou nome, frame ou estado da acao. `PlayAction()` so adiciona a lista depois que iniciou uma layer com sucesso.
- Ao fim de `KX_Scene::UpdateAnimations`, depois de disparar eventos, objetos comuns sem nenhuma layer ativa saem de `m_animatedlist`; por isso deixam de gerar task e de entrar em `m_animNeedsUpdateCache` nos frames seguintes. Armatures permanecem na lista, pois constraints e deformers podem precisar de pose mesmo sem uma acao KX.
- Regressao controlada no `AnastacioRuntime.exe`: uma acao one-shot chegou a `x=4.000`, terminou, foi iniciada de novo e chegou a `x=3.556` antes de terminar (`PASS=True`). A mudanca elimina o trabalho ocioso, mas esta rodada nao mediu tempo de CPU numa cena grande.

## 2026-10-09 - PH3: deformer de soft body só invalida a malha quando ela mudou

- `KX_SoftBodyDeformer::Apply`: compara exatamente cada posição e normal de saída antes de escrever o array; `NotifyUpdate` recebe somente os atributos que mudaram. AABB deixa de ser percorrido, reinicializado e invalidado quando nenhuma posição mudou. Não há limiar nem estado artificial de sono: uma deformação real continua atualizando e subindo ao VBO.
- Medição temporária com grade triangular de 6 561 nós, câmera 16 mm, materiais contrastantes e Sun: com gravidade zerada o solver ainda altera nós e, corretamente, manteve `updateNotifies=1` e `boundsPushes=1` por frame (física ~7,5 ms). Após `suspendDynamics()`, os frames estáveis tiveram ambos os contadores em 0; a física ficou ~5,1 ms, mostrando que o custo do solver é independente do envio da malha.
- Correção complementar do defeito visual: pose matching não é criado para mesh planar, pois Bullet inverte uma matriz singular e a malha cresce sem limite. `soft_body_test.py` passou 16/16 no runtime recompilado.

## 2026-10-09 - Cache de uniforms de luz e sombra no GPUShader (GP1/GP2/RA1 corrigidos)

- `GPU_shader_uniform_vector_cached` / `GPU_shader_uniform_int_cached` (`gpu_shader.c`): guardam o último
  valor enviado por location dentro do `GPUShader` (os programas são compartilhados entre materiais pelo
  shader_cache) e pulam o `glUniform` quando o valor não mudou.
- `GPU_material_bind_shadow_lamps` e `GPU_material_bind_scene_lights` usam essas funções para persmat, bias,
  point, enabled, sampler das sombras e as 11 uniforms das luzes de cena. Os binds de textura de sombra
  continuam a cada draw, porque outros draws reusam as unidades.
- Medido na cena `tools/debug/cenas/criar_cena_luzes_sombra.py` (3 spots com sombra, 164 draws por frame com os cubos visíveis):
  `lightUniforms` de ~902 para ~334 por frame. RolimaRacer não muda (já era 0). O script da cena criava o plano no
  cursor 3D (acima dos cubos, que ficavam escondidos); agora o plano vai para a origem e os cubos são vermelhos.

## 2026-10-09 - Contador de uniforms de luz (GP1/GP2/RA1 medidos)

- Novo contador `lightUniforms` em `bge.logic.getRenderStats()` (`CM_WORK_LIGHT_UNIFORMS`): chamadas GL de
  `GPU_material_bind_shadow_lamps` e `GPU_material_bind_scene_lights` por frame. Também entra no detector
  `tools/debug/auditar_trabalho_repetido.py`.
- O detector aceita `-` no lugar da cópia: põe o medidor só na memória do editor aberto (sem `-b`) e não salva.
  Assim os imports `scripts.*` dos componentes continuam resolvendo, o que não acontecia na cópia salva fora da
  pasta do jogo.
- Medição: 0 no RolimaRacer em corrida (~400 draws), que não tem lâmpada com sombra em buffer; no COMPAT as luzes vão
  por `gl_LightSource`. Na cena nova `tools/debug/cenas/criar_cena_luzes_sombra.py` (41 malhas com Principled, 3 spots
  com sombra): ~880 GL por frame, ~22 por draw, repetidas com a cena parada.
- O detector também registra `lightBinds`. Foi ele que mostrou que a primeira versão da cena não tinha shader: sem
  `use_shading_nodes` o Principled cai nos nós antigos, o material fica sem programa e nada é desenhado.

## 2026-10-08 - Varredura de trabalho repetido e os 8 bugs de correção encontrados

- [auditoria-suspeitos.md](auditoria-suspeitos.md): varredura por leitura de código de Converter, Ketsji/SceneGraph,
  Rasterizer, Physics, GameLogic/Network/VideoTexture, Python, laço principal/filtros/ImGui/áudio, gpu e
  spawn/LibLoad. Suspeitos classificados por gravidade (0 = bugs de correção, 1-4 = custo); nada medido ainda.
- `KX_GameObject::RemoveRessources`: quando um material da malha vinha da biblioteca liberada, o `break` só
  saía do laço interno e o externo seguia iterando `m_meshes` já limpo por `RemoveMeshes()` (UB no `LibFree`).
  Agora retorna nos dois ramos. `RangeEngine` compilou; sem teste de `LibFree` em jogo.
- `CcdPhysicsEnvironment::ProcessFhSprings`: desreferenciava `body` antes do teste de nulo; com algum objeto
  Fh na cena, sensores e personagens (sem rigid body) derrubavam a engine. Agora pula `body` nulo.
- `KX_GameObject::ReplaceMesh` com física: as cópias compartilham o `CcdShapeConstructionInfo`, e
  `ReinstancePhysicsShape` sem `dupli` refazia o shape de todas elas. Agora passa `dupli=true`, como o
  `reinstancePhysicsMesh(dupli=True)` do Python. Compilou; falta conferir em jogo.
- `KX_Scene::AddNodeReplicaObject`: reconstruía a navmesh do original a cada cópia e a cópia ficava sem
  navmesh (`ProcessReplica` zera `m_navMesh`). Agora constrói a da cópia.
- `worldOrientation[i] = ...` (mathutils, `MATHUTILS_MAT_CB_ORI_GLOBAL`) gravava a orientação local.
- Texto bitmap 2.4x: cada cópia registrava uma malha duplicada no conversor que só saía no fim da cena.
  O objeto guarda essas malhas (`m_bitmapTextMeshes`) e `NewRemoveObject` as desregistra.
- `KX_GameObject::UpdateComponents`: os dois ramos eram iguais e o activity culling sempre parava os
  componentes. Agora só para com a opção Components ligada; outras suspensões continuam parando.
- `RAS_2DFilter`: offsets de amostragem (`ge_TextureCoordinateOffset`) eram calculados só no 1º frame;
  agora são recalculados quando o canvas muda de tamanho.
- Todos compilados no `RangeEngine`; nenhum conferido em jogo ainda.

## 2026-10-08 - Static Batch, culling sem AABB repetida e detector de trabalho repetido

- `377a0026`: checkbox **Static Batch** (`ob.use_static_batch`) no painel Physics; o conversor junta
  os objetos marcados num `KX_BatchGroup`. Cena de 1.600 objetos: ~707 → ~2.513 FPS sem culling.
- `98f54d7f`: `RAS_MeshBoundingBox::Update()` marcava `m_modified = true` sempre; com DBVT cada objeto
  reenviava a AABB ao Bullet todo frame (~320 µs com 1.600). Agora só marca quando a malha muda.
  Com culling e Static Batch: ~1.170 → ~1.700 FPS, empatando com a referência; sem Static Batch
  ~512 → ~640. Validado no jogo do usuário (nada sumiu ou piscou).
- `61d35afc`: contadores por frame em `getRenderStats()` (`sceneNodeUpdates`, `transformSyncs`,
  `boundsPushes`, `meshMatrixChanges`, `updateNotifies`) e `tools/debug/auditar_trabalho_repetido.py`.
  Com o bug recolocado, `boundsPushes` = 1.600/frame; corrigido, 0.
- Documentos: [batching-estatico-e-culling.md](batching-estatico-e-culling.md),
  [auditoria-trabalho-repetido.md](auditoria-trabalho-repetido.md).

## 2026-10-08 - `SetMatrix()` separa membro do batch quando a matriz muda

`RAS_MeshUser::SetMatrix()` compara a matriz antes de separar; matriz igual mantém o
batch. `RAS_BatchGroup::SplitMeshUser()` notifica um hook virtual, e `KX_BatchGroup`
atualiza a lista e a referência sem acoplar RAS ao KX. `RAS_MeshUser` agora separa os
slots antes de destruí-los. `RangeRuntime` compilou. Teste estático: 64 membros/1 draw
até frame 119; mover referência: 63 membros, `batchGroup=None`, referência seguinte e
draws 1→2; `destruct()` restaurou 64. Remoção da referência e de membro comum também
passou. Validação visual do objeto movido, reload e falha parcial seguem pendentes. A
leitura do checkout da referência não confirmou rebuild integral por quadro; não portar `Reset()`
sem entender o split/restauração. Evidências em `<investigacao-local>/benchmark/diagnostico/anastacio_batch_manual/RESULTADO.md`.

## 2026-10-08 - Ciclo de remoção de membro do KX_BatchGroup corrigido

`KX_GameObject::RemoveMeshes()` agora notifica `KX_BatchGroup` antes de destruir o
mesh user. O grupo remove o ponteiro da lista não proprietária e, se o membro removido
era a referência, troca para um membro restante ou limpa a referência RAS. `RangeRuntime`
compilou; no standalone, remoção do primeiro membro e de um membro comum passou, contagem
ficou em 63, referência correta, `destruct()` completou e exit code foi 0. A próxima peça
separada é invalidação por `SetMatrix`; reload, grupo vazio e falha parcial seguem pendentes.
Evidências em `<investigacao-local>/benchmark/diagnostico/anastacio_batch_manual/RESULTADO.md`.

## 2026-10-08 - Ciclo de remoção de membro do KX_BatchGroup corrigido

`KX_GameObject::RemoveMeshes()` agora notifica `KX_BatchGroup` antes de destruir o
mesh user. O grupo remove o ponteiro da lista não proprietária e, se o membro removido
era a referência, troca para um membro restante ou limpa a referência RAS. `RangeRuntime`
compilou; no standalone, remover o primeiro membro e um membro comum passou, contagem
ficou em 63, referência correta, `destruct()` completou e exit code foi 0. A próxima peça
separada é invalidação por `SetMatrix`; reload, grupo vazio e falha parcial seguem pendentes.
Evidências em `<investigacao-local>/benchmark/diagnostico/anastacio_batch_manual/RESULTADO.md`.

## 2026-10-08 - Split manual antes de mover membro do batch

Na cena sintética de 64 objetos, `KX_BatchGroup.split([obj])` antes da alteração
de `worldPosition` removeu o membro do grupo. Após um frame, `drawCalls` subiu de
1 para 2, mantendo os outros 63 objetos agregados; `destruct()` restaurou 64. O
standalone terminou com exit code 0. Isso valida um fallback manual quando o jogo
antecipa a transformação. Não resolve invalidação automática, referências na lista
Python após `endObject()` nem reload/troca de cena. Reproduções e log em
`<investigacao-local>/benchmark/diagnostico/anastacio_batch_manual/`.

## 2026-10-08 - Auditoria do batching existente para auto-batching

Continuação da investigação da referência. A Anastacio já possui batching estático via
`KX_BatchGroup`/`RAS_BatchGroup`/`RAS_BatchDisplayArray`, mas o uso é explícito por
Python. A principal lacuna para automação é que `RAS_MeshUser::SetMatrix()` não
separa/reconstrói o membro do batch quando sua transformação muda. Também foram
registrados os limites do mesh user de referência, `frontFace=true`, transparência,
deformers/atributos por objeto, falha parcial de merge e validação das passadas de
sombra. Próxima etapa recomendada: testar o batch manual, especialmente transformação,
remoção e reload, antes de automatizar a elegibilidade. Nenhum código C++ foi alterado
nesta etapa; mudanças de profiler que já estavam no workspace foram preservadas.
Detalhes em `docs/batching-estatico-e-culling.md`.

## 2026-10-08 - Teste do KX_BatchGroup manual no standalone

Cena sintética local de 64 objetos/16 meshes compartilhados executada no
`AnastacioRuntime.exe`: batch manual resultou em 1 draw call e `destruct()` restaurou
64. Mover membro manteve `batchGroup` ativo, consistente com a matriz copiada para os
vértices agregados; confirmação visual pendente. Remover um membro com `endObject()` e
destruir o grupo completou sem crash, mas `group.objects` ainda mostrava 64 no intervalo
observado; após destruição, 63 draws. Reload de cena no mesmo processo não testado.
Nenhum C++ foi alterado. Dados e limites em
`<investigacao-local>/benchmark/diagnostico/anastacio_batch_manual/RESULTADO.md`.

Para achar uma entrada por assunto: `grep -rn "^## .*termo" docs/changelog.md docs/changelog/`.
Entradas antigas não estão em ordem cronológica estrita; a data no título é a referência.

| Arquivo | Datas | Entradas | Tamanho |
|---|---|---|---|
| [este arquivo](changelog.md) (entradas recentes) | 2026-10-08 | 35 | 45 KB |
| [14_2026-10-06_a_2026-10-05.md](changelog/14_2026-10-06_a_2026-10-05.md) | 2026-10-06 a 2026-10-05 | 42 | 54 KB |
| [15_2026-10-04_a_2026-10-03.md](changelog/15_2026-10-04_a_2026-10-03.md) | 2026-10-04 a 2026-10-03 | 60 | 63 KB |
| [16_2026-10-02_a_2026-10-01.md](changelog/16_2026-10-02_a_2026-10-01.md) | 2026-10-02 a 2026-10-01 | 76 | 68 KB |
| [17_2026-09-30_a_2026-09-27.md](changelog/17_2026-09-30_a_2026-09-27.md) | 2026-09-30 a 2026-09-27 | 48 | 63 KB |
| [18_2026-09-26_a_2026-09-25.md](changelog/18_2026-09-26_a_2026-09-25.md) | 2026-09-26 a 2026-09-25 | 54 | 62 KB |
| [13_2026-09-24_a_2026-09-24.md](changelog/13_2026-09-24_a_2026-09-24.md) | 2026-09-24 a 2026-09-24 | 22 | 30 KB |
| [12_2026-09-23_a_2026-09-23.md](changelog/12_2026-09-23_a_2026-09-23.md) | 2026-09-23 a 2026-09-23 | 9 | 13 KB |
| [11_2026-09-22_a_2026-09-20.md](changelog/11_2026-09-22_a_2026-09-20.md) | 2026-09-22 a 2026-09-20 | 25 | 39 KB |
| [10_2026-09-20_a_2026-09-20.md](changelog/10_2026-09-20_a_2026-09-20.md) | 2026-09-20 a 2026-09-20 | 12 | 19 KB |
| [01_2026-09-20_a_2026-09-14.md](changelog/01_2026-09-20_a_2026-09-14.md) | 2026-09-20 a 2026-09-14 | 45 | 69 KB |
| [09_2026-09-17_a_2026-09-06.md](changelog/09_2026-09-17_a_2026-09-06.md) | 2026-09-17 a 2026-09-06 | 51 | 71 KB |
| [02_2026-09-14_a_2026-09-11.md](changelog/02_2026-09-14_a_2026-09-11.md) | 2026-09-14 a 2026-09-11 | 24 | 71 KB |
| [03_2026-09-12_a_2026-08-23.md](changelog/03_2026-09-12_a_2026-08-23.md) | 2026-09-12 a 2026-08-23 | 49 | 90 KB |
| [08_2026-09-06_a_2026-09-02.md](changelog/08_2026-09-06_a_2026-09-02.md) | 2026-09-06 a 2026-09-02 | 26 | 68 KB |
| [07_2026-09-02_a_2026-08-31.md](changelog/07_2026-09-02_a_2026-08-31.md) | 2026-09-02 a 2026-08-31 | 23 | 69 KB |
| [06_2026-08-31_a_2026-08-26.md](changelog/06_2026-08-31_a_2026-08-26.md) | 2026-08-31 a 2026-08-26 | 7 | 71 KB |
| [05_2026-08-25_a_2026-08-24.md](changelog/05_2026-08-25_a_2026-08-24.md) | 2026-08-25 a 2026-08-24 | 2 | 68 KB |
| [04_2026-08-24_a_2026-08-24.md](changelog/04_2026-08-24_a_2026-08-24.md) | 2026-08-24 a 2026-08-24 | 4 | 81 KB |

## 2026-10-08 - Auto-batching RAS confirmado na engine de referência

Comparacao direta do checkout da referência com a Anastacio identificou `TryAutoBatch` no
RAS da referência. A cena estatica do benchmark tem 1.600 objetos em 16 meshes
compartilhados, um material; o player de junho marca `isMDEI=false`. Logo, MDEI nao
explica o resultado.

Foi feito A/B no mesmo executavel da referência de junho (SHA-256 no manifesto) e na mesma
cena, mudando apenas `bge_allow_auto_batch` nos 16 datablocks de mesh. Resolucao
1280x720, viewport 1281x721, MSAA/AF 2, VSync 0, culling desligado, ticrate 10000,
2 s de aquecimento e 4 s de amostra. Duas repeticoes alternadas: False 661,8/667,2
FPS (media 664,5); True 2610,0/2595,0 (media 2602,5), ganho de 3,92x. Todas as
rodadas produziram 128600 primitivas. A cena original sem a propriedade explicita
mediu 2636 FPS, alinhada ao valor True.

No fonte da referência, a conversao le a propriedade (default true) e configura
`RAS_Mesh::SetAllowAutoBatching`; o renderer so a consulta para decidir se tenta
`TryAutoBatch`. O A/B com o player real confirma que o auto-batching explica a maior
parte da diferenca na cena estatica. Nao houve alteracao de fonte/build da engine.
Nao foi capturado o numero exato de draws GL; a medicao de primitivas confirma que a
geometria permaneceu presente. Dados, cenas, scripts e hashes em
`<investigacao-local>/benchmark/diagnostico/autobatch_ab/RESULTADO-AUTOBATCH-AB.md`.

Proximo passo: avaliar um prototipo opt-in na Anastacio para objetos estaticos ou
raramente alterados, preservando fallback e invalidacao de transformacoes. Nao
inferir beneficio para carros dinamicos.

## 2026-10-08 — Cache da camada do objeto e validação do standalone

Usuário confirmou ausência de lag percebido na rodada sem instrumentação do
standalone e física funcionando bem, com limite de 60 FPS. Área da janela
confirmada em 2560×1440 usando configurações salvas (sem -w 1280 720). Agente
entrou pelo menu na Pista_1 e enviou I depois da contagem; teste anterior em janela
menor confirmou progresso automático pelos checkpoints. Isso valida funcionamento
da primeira otimização; não estabelece ganho de FPS no jogo.

Nova peça em gpu_material.c: GPU_OBJECT_LAY só é reenviado quando muda, com
invalidação em GPU_material_bind para programas compartilhados e novas passadas.
Nenhuma outra atualização de objeto é pulada. Editor e player recompilados.
Seis execuções de controle passaram: legado 1600 → 1 inteiros/quadro; camada
alternada 1600 → 16 (ordem de desenho por malha); ObjectInfo preserva 1600 matrizes
e vetores; PBR conserva 8 comandos de probes. Teste C do bloco real passou
troca/retorno de camada, zero, bits altos/múltiplos, reativação de programa
compartilhado e localização ausente.

Oito rodadas sem profiler, OFF/ON/ON/OFF, 5 s de aquecimento + 15 s de amostra:
MSAA 2/AF 2: 704,3 → 710,6 FPS (+0,89%, pequeno/inconclusivo). MSAA 4/AF 4:
controle variou de 561,5 a 672,8 e cache de 685,9 a 715,5; não atribuir a
diferença média ao cache sem repetição mais estável. Não há ganho consistente
demonstrado dessa peça, nem explicação da diferença grande com a referência legada.
Física/lógica intactas; validação visual no jogo dessa segunda peça pendente.
Checker mantém 30 referências antigas de física e 3 avisos preexistentes.
Evidências: `<investigacao-local>/benchmark/diagnostico/CACHE-CAMADAS.md`.

## 2026-10-08 — Segunda rodada do RolimaRacer e hipótese de desfoque

Usuário confirmou Pista_1, 10 carros e muitos efeitos; orientou continuar testes
e apenas registrar lags, investigando se forem frequentes. Suspeita de desfoque
da câmera em movimento rápido registrada como hipótese. Player de controle sem
cache executou o jogo: 37 médias e 26 picos, incluindo espera de 6,45 s em swap.
Nas duas sessões, recortes após 25 s com física tiveram mediana de 60 FPS e zero
uploads de probes. Sem ganho demonstrado do cache na pista; não comparar taxas
de picos porque trajetos/durações diferiram. Próxima rodada sem profiler/log de
animação, com efeitos preservados. Fonte/editor/player otimizado permanecem iguais.
Evidências: `<investigacao-local>/benchmark/diagnostico/rolima-real/COMPARACAO-PISTA1.md`.

## 2026-10-08 — Primeira execução do cache no RolimaRacer

Player principal abriu `D:/ProjetoRolimaRacer/RolimaRacer.range` pelo menu normal,
com profiler e log de animação, sem modificar jogo ou frequência de lógica/física
(tic rate inicial 60). Usuário relatou que chegou à corrida com alguns lags.
50 médias/19 picos: muitos trechos em 60 FPS; maiores pausas em `endframe.swap`,
incluindo 6,64 s, sem compilação/criação de textura naquele quadro. Causa ainda
não identificada; foco da janela e comparação sem cache pendentes. Houve também
picos de preparação de cenas. Probes tiveram zero uploads em todas as médias:
ganho do controle PBR não demonstrado no jogo. Pista não confirmada. Evidências:
`<investigacao-local>/benchmark/diagnostico/rolima-real/PRIMEIRA-VALIDACAO.md`.

## 2026-10-08 — Comparação de FPS do cache de probes ausentes

Dois players de teste compilados com o mesmo código de diagnóstico: o controle
desliga somente os retornos antecipados do cache. Fonte restaurada e editor/player
principais recompilados com a otimização. Série longa sem RANGE_PROFILE, ordem
OFF/ON/ON/OFF, 5 s de aquecimento e 15 s de amostra, 1600 objetos com Principled:
MSAA 2/AF 2: 240,2 → 288,9 FPS (+20,3%); MSAA 4/AF 4: 242,7 → 292,8 (+20,6%).
Janela 1280×720, viewport de desenho 1281×721, VSync 0 e 128602 primitivas iguais;
hardware AMD RX 6800M. O tic rate elevado só pertence à cena estática de benchmark.

Série curta exploratória teve variação grande no controle legado e não fundamenta
ganho nesse material; primeira rodada curta coincidiu com o término do rebuild.
Série longa ocorreu após os builds e é a evidência de FPS do PBR. Resultado não
mede jogo real nem compara com a referência. Cores seguem adiadas. Validação do carro
e probes visuais no jogo depende do arquivo do usuário. Dados/hashes em
`<investigacao-local>/benchmark/diagnostico/cache_long_summary.json`.

## 2026-10-08 — Cache de probes ausentes por ativação do material

`gpu_material.c` evita repetir os uniforms das duas probes ausentes durante uma
ativação do material. Reinicia em `GPU_material_bind`; probe ativa invalida o estado
ausente e continua vinculando textura por objeto. Mudança de maxlod força envio.
Não muda lógica, física, matrizes ou seleção de probes.

Editor e player compilados via MSVC. Quatro cenas executadas com MSAA 2 e AF 2:
PBR passou de 12.800 comandos de probe/quadro para 8; legado manteve 1.600 inteiros
de objeto, ObjectInfo manteve 1.600 matrizes e instancing permaneceu fora desse caminho.
Teste C com as funções reais extraídas e wrappers simulados passou repetição,
alteração de maxlod, probe ativa repetida, ativa para ausente, reinício e peso zero.
Ganho de FPS sem profiler e validação visual com probes no jogo real ficam pendentes.
Evidências: `<investigacao-local>/benchmark/diagnostico/CACHE-PROBES.md`.
Checker de docs: 30 referências antigas da física e 3 avisos preexistentes.

## 2026-10-08 — Contagem de uploads na atualização do objeto

- Novo GPU_render_profile.h e contadores no ponto de envio ao OpenGL, classificados
  por objeto, sombras, luzes/IES, probes, dano e skinning. Contagem de comandos após
  retornos por localização ausente/ponteiro nulo, não bytes nem uploads de imagem.
  Profiler grava médias por quadro e zeros; fases locais à thread.
- Na cena legada de 1600 objetos: 1600 uniforms inteiros de camada e zero uploads
  nas fases de sombra/luzes/probes/dano. No controle Principled: 30400 comandos por
  quadro, incluindo estado padrão de recursos ausentes. Controle Object Info:
  1600 matrizes 4×4 e 1600 vetores por quadro, validando os contadores positivos.
- Cenas de nós sem opt-in PBR não exercitaram o shader esperado e foram excluídas;
  os controles positivos usam game_settings.use_shading_nodes=True.
- RangeRuntime e RangeEngine compilados com VSLANG=1033/vcvars64. Execuções instrumentadas
  e controles sem profiler passaram. Nenhum corte de atualização implementado;
  frequência/passos de lógica/física e comportamento de veículos não foram alterados.
- Evidências locais: `<investigacao-local>/benchmark/diagnostico/CONTAGEM-UPLOADS.md`.
  Próxima peça: cache específico de um estado padrão, com invalidação e teste no jogo.

## 2026-10-08 — Decomposição do desenho por objeto

- RunNode dividido em medições de estado, ativação de material, push/apply/pop de
  matriz e submissão. Duas rodadas das quatro cenas, com ordem inversa na segunda,
  e quatro controles com profiler desligado encerraram com sucesso.
- Ativação do material foi a maior fase individual nas duas rodadas; matrizes e
  submissão também contribuem. Estados de alpha, front face e seleção de luzes já
  têm caches. Medições curtas continuam limitadas pelo piso do cronômetro.
- RangeRuntime compilado com ambiente MSVC correto. Controles sem profiler:
  681/1894/2186/3119 FPS (1600/400 objetos separados, instancing e mesh unido).
- Evidências locais: `<investigacao-local>/benchmark/diagnostico/FASES-DO-DESENHO.md`.
  Próxima peça: contar uploads e trabalho realmente executado na atualização do
  objeto. Nenhum corte de recursos ou otimização de comportamento aplicado.

## 2026-10-08 — Diagnóstico de render por objeto versus a engine de referência

- Adicionadas medições por amostragem ao profiler existente: mesh slot, atualização do
  objeto/uniforms, seleção/envio de luzes e submissão. Helper novo sem alterar layouts de structs.
- Quatro cenas executadas; o caminho `RAS_MeshSlot::RunNode` concentrou a maior parte do
  tempo de CPU de render na cena de 1600 objetos sem instancing. `ProcessLighting` já tem
  cache por camada/cena; contagem de entradas não indica reconstrução de luzes.
- Medição completa descartada por overhead; amostragem 1/61 inclui bloco vazio e fases
  separadas. Estimativas pequenas permanecem limitadas pelo custo do cronômetro.
- `RangeRuntime` compilado com ambiente MSVC correto e cenas instrumentadas encerraram
  com sucesso. Sem otimização gráfica aplicada; cores adiadas por decisão do usuário.
- Quatro controles com profiler desligado encerraram com sucesso: 683/2026/2179/3062 FPS
  (1600/400 objetos, instancing e mesh unido). Editor e runtime recompilados com sucesso.
- Checker de docs: 30 referências antigas no mapa de física e três avisos de tamanho,
  fora dos arquivos instrumentados.
- Evidências locais: `<investigacao-local>/benchmark/diagnostico/LOCALIZACAO-GARGALO.md`.
  Próxima investigação: decompor estado/matrizes/submissão de RunNode; culling é frente separada.

## 2026-10-08 — Conversão: normais e tangentes das malhas em paralelo

- `BL_PrepareMeshes` (`BL_BlenderDataConversion.cpp`), chamado no início de `BL_ConvertBlenderObjects`:
  junta as malhas dos objetos que vão converter (cena e grupos de dupli, na ordem da conversão) e calcula em
  threads (`std::thread`, uma por núcleo) o `CDDM_from_mesh`, o hash de loops, as normais de loop e as
  tangentes MikkTSpace. Cada thread só lê dados Blender de malhas distintas e escreve no próprio
  DerivedMesh; materiais, display arrays, `KX_Mesh`, cache de loops e `.cooked` continuam na thread principal.
  `BL_ConvertMesh` usa o DerivedMesh pronto (com o hash tirado antes das normais) e o resto do caminho é o mesmo.
- Malhas que vão sair do `.cooked` (chave prevista a partir dos materiais Blender) e cópias idênticas
  (mesmo hash; copiam do cache de loops) não calculam nada no lote. Previsão errada só devolve o trabalho
  ao caminho sequencial; o resultado não muda.
- `RANGE_NO_MESH_BATCH=1` volta ao cálculo malha a malha, para comparar. `[Load] convert` mostra
  `mesh batch N Xms` (tempo de parede do lote).
- Medido (10 núcleos), convert sequencial → lote: `level_1_home` (YoFrankie) sem `.cooked` 324–504 → 149–167 ms,
  com `.cooked` 101–134 → 74–79 ms; `make_cooked_small_test.py` 16 segmentos sem cozido 128–134 → 63 ms,
  com cozido 25–27 → 28–30 ms (todas cozidas: o lote só custa ~4 ms de threads e DerivedMesh).
- Checksum exato (posição, normal, tangente, UV, cor e polígonos em float32) idêntico entre build anterior,
  lote e `RANGE_NO_MESH_BATCH=1`, com e sem `.cooked`, em `level_1_home`, `make_cooked_small_test.py` e
  `make_cooked_mesh_test.py`.

## 2026-10-08 — Compilação paralela dos shaders de material

- Com `GL_ARB_parallel_shader_compile`, os programas de todos os materiais são enviados ao driver antes de
  montar cada material (`GPU_shader_prefetch_*` em `gpu_shader.c`, `GPU_material_prefetch`,
  `KX_BlenderMaterial::PrefetchMaterial`); o driver compila vários ao mesmo tempo e cada montagem só pega o
  programa pronto (mesma chave do binário do `.cooked`). Sem a extensão, nada muda.
- `addScene` assíncrono, LibLoad assíncrono e recarga por luzes novas enviam os materiais aos poucos, dentro do
  orçamento do frame, e só depois montam (`step_shaders` em `BL_Converter.cpp`): a tela de loading segue
  desenhando. No AMD a consulta `GL_COMPLETION_STATUS_ARB` espera a compilação acabar, por isso não é usada.
- `RANGE_NO_PARALLEL_SHADERS=1` volta à compilação um por um; `RANGE_SHADER_SALT=<texto>` põe um comentário em
  todo shader para o cache do driver errar e medir a primeira abertura.
- AMD RX 6800M, compilação a frio: `make_parallel_shader_test.py` (48 materiais) 16,5 → 4,2 s, imagens
  idênticas; RolimaRacer até a corrida 61,7 → 22,6 s (shaders da pista 49,1 → 11,2 s até ficar pronta).
  Sem testar ainda em NVIDIA.

## 2026-10-08 — `.cooked`: carregamento das malhas em bloco

- Vértices cozidos escritos em bloco (`RAS_DisplayArray::AppendVertices`/`AddVertexInfo`/`AddIndices`):
  normais e tangentes por `memcpy`, UV e cor camada por camada, em vez de um `AddVertex` por vértice.
- `hash_bytes` com 4 trilhas de 64 bits e campos juntados em bloco antes do hash (`hash_strided`); chave
  versão 4 (registros antigos de malha são regravados).
- `make_cooked_small_test.py`, 8 064 loops com cozido: 259 → 206 ms (parte cozida 141 → 96 ms, hash
  35 → 27 ms). O que sobra é limitado por memória (alocar e preencher os vértices).
  Checksum de `make_cooked_mesh_test.py` idêntico.

## 2026-10-08 — `.cooked`: normais e BVH de física

- O registro de malha (chave versão 3) guarda também a normal de cada vértice gerado: com o cozido o
  `calcLoopNormals` é pulado (200 malhas de 8 064 loops: 56 → 0 ms).
- Registro novo (tipo 4): a BVH das formas Triangle Mesh serializada pelo Bullet
  (`btOptimizedBvh::serializeInPlace`), com chave do hash dos arrays de física que o `CcdEndBvhBatch` já
  calculava. Carregar é uma cópia mais `deSerializeInPlace`. O cabeçalho repete a chave inteira e é conferido
  antes do uso. `[Load] convert` mostra `physics Xms (bvh Xms; ...)` e o `[Cooked]` conta as BVHs.
- `make_cooked_mesh_test.py` faz 400 raycasts na malha de física e põe ponto, normal e polígono no checksum:
  idêntico entre rodada normal e cozida; física do teste 15 → 1 ms.
- `make_cooked_small_test.py`, convert com cozido antes → depois: 8 064 loops 396 → 259 ms (BVH 100 → 14 ms),
  1 984 loops 98 → 78 ms. O `.cooked` desse teste foi de 42 para 87 MB.

## 2026-10-08 — `.cooked`: todas as malhas

- Removido o mínimo de 10 mil loops: o registro cozido ganha em qualquer tamanho. Novo
  `tests/convert_flag/make_cooked_small_test.py` (200 malhas únicas com UV), convert sem → com cozido:
  112 loops 45 → 21 ms (0,8 MB), 480 loops 120 → 35 ms (2,7 MB), 1 984 loops 436 → 98 ms (10 MB),
  8 064 loops 1 820 → 396 ms (42 MB). No RolimaRacer (537 malhas, só 15 com 10 mil+ loops) o mínimo
  antigo deixava quase tudo de fora.

## 2026-10-08 — `.cooked`: tangentes

- O registro de malha (versão 2 da chave) guarda também a tangente de cada vértice gerado (4 floats) quando a
  malha usa tangentes; com o registro cozido o `DM_calc_loop_tangents` (mikktspace) é pulado.
- `make_cooked_mesh_test.py` agora inclui as tangentes no checksum: idêntico entre rodada normal e cozida.
  Malha do teste (24 mil vértices): meshes 32 → 4 ms, tangentes 24 → 0 ms; `.cooked` de 849 KB.

## 2026-10-08 — `.cooked`: buffers de malha

- O `.cooked` ganhou um registro novo (tipo 3) com a montagem dos display arrays de cada malha: para cada
  vértice gerado, de qual loop ele veio (o bit alto marca face plana), mais os índices de primitiva e de
  triângulo (os de triângulo só quando diferem). Ao carregar, os vértices são remontados direto dos loops,
  sem a busca de vértices compartilhados, que era a parte lenta (`BL_CookedArrays` em
  `BL_BlenderDataConversion.cpp`).
- Chave: o hash de normais/tangentes que já existia mais slots de material, `mat_nr` das faces, todas as
  camadas de UV e de cor e uma versão. Ficam de fora malhas com menos de 10 mil loops, com dados de osso
  (GPU skinning) e com texto bitmap. Dados que não batem com a malha são rejeitados antes de tocar nos arrays.
- Primeira versão guardava os vértices prontos: 104 MB no teste de 12 objetos. Guardando só os loops ficou
  22,6 MB, com a malha um pouco mais lenta (esfera de 130 mil triângulos: 57 → 14 ms com vértices prontos,
  57 → 26 ms com loops).
- `[Load] convert` mostra `N cooked Xms` e o resumo `[Cooked]` conta as malhas.
- Validação (`tests/convert_flag/make_vs_libload.py`, Runtime, rodadas repetidas): convertObject
  834 → 332 ms e LibLoad 850 → 295 ms (convert 496 → 244 ms). Novo
  `tests/convert_flag/make_cooked_mesh_test.py` (2 materiais com um wire, faces lisas e planas, 2 UVs e cor):
  checksum de vértices, normais, UVs, cores e polígonos idêntico entre a rodada normal e a cozida.

## 2026-10-08 — Aquecimento de shaders: idiomas, reinício no editor e cache único

- Tela de aquecimento (`LA_Launcher.cpp`) em inglês, português, espanhol e russo, pelo idioma da engine (`BLT_lang_get`).
- Editor: o reinício pedido pelo aquecimento vinha sem arquivo e lia um caminho inválido (`Error: loading C:\ failed`). `BL_KetsjiEmbedStart.cpp` agora reinicia com os dados da memória quando não há arquivo, mantendo alterações não salvas.
- Cache do usuário (`CcdCookedData.cpp`): o hash do caminho trata `/` como `\` no Windows. O editor passava `D:/...` e o player `D:\...`, criando dois caches do mesmo jogo.
- Validado com RolimaRacer no editor: aquecimento de 321 shaders, reinício sem erro, e na abertura seguinte o editor reusou o cache do player (menu: 33 shaders em 55 ms). Tela traduzida não foi verificada visualmente.

## 2026-10-08 — Player Windows AnastacioRuntime.exe e integração com RangeArmor

- Usuário autorizou a segunda etapa. Alvo `RangeRuntime` mantém seu nome interno e
  produz `AnastacioRuntime.exe` no Windows; recurso e registro de `.range` atualizados.
  Linux e artefatos Web/Android mantidos. Standalone, Cook e export nativo adaptados.
- RangeArmor cria caminhos novos, aceita configuração legada e mantém prioridade de
  caminhos existentes/personalizados. Somente config da entrega é ajustado ao runtime
  copiado. Templates antigos conhecidos por hash usam launcher atual no Run/Export;
  descoberta da instalação portátil não exige variáveis de ambiente.
- Build editor/player passou (14 etapas). Launcher: três testes/build; painel: 26 testes
  release/build. Link dos testes debug falhou com LNK1104 no artefato antigo; perfil release
  passou. Doze testes Python e 132 Web/Android passaram. Quatro avisos herdados do painel.
- Player novo, Cook pelo editor, standalone e export nativo executaram a cena controlada;
  hull preparado usado. Corrigido fixture do editor que tentava abrir `.rasec` como `.range`.
  Artefatos antigos do player retirados da raiz de `build/bin/` para backup reversível.
- ZIPs atuais em `build/dist/validation-20261008-113829/`, CRC/caminhos/extração conferidos.
  Primeiro ensaio sem override usou pacote anterior enquanto o novo staging terminava;
  repetido sequencialmente com o pacote atualizado. Projeto/config/launcher legados,
  Cook, export e jogo extraído passaram. Evidências e limites na seção 14 do
  [plano](executable-rename-plan.md#14-player-windows-renomeado--2026-10-08).
  Nenhuma publicação ou alteração das associações no Registro.

## 2026-10-08 — Pacotes Windows atuais preparados e executados após extração

- Staging isolado da instalação atual gerou engine (188.011.888 bytes) e RangeArmor
  (10.435.006 bytes), com SHA256, caminhos `/` e CRC conferidos. Símbolos, logs,
  caches Python, testes e backup Godot excluídos; CRT e licenças preservados.
- Editor/painel extraídos iniciaram. Scripts e Python extraídos copiaram runtime,
  prepararam `.cooked` e exportaram fixture; launcher executou e confirmou uso do hull.
  Preferências restauradas. Corrigido campo DataSource ausente no primeiro fixture.
- Sem publicação nem rebuild nativo. Pacotes em `build/dist/validation-20261008-111756/`;
  evidências, instrução de instalação da ferramenta e limites no
  [plano de migração](executable-rename-plan.md#13-pacotes-windows-atualizados--2026-10-08).

## 2026-10-08 — Mapas atualizados e export comprimido pela GUI validado

- `check_docs.py --fix` atualizou 91 referências/contagens do mapa. Checagem posterior:
  zero erros e zero avisos. Alteração documental, sem necessidade de rebuild nativo.
- 132 testes Web/Android e nove testes de segurança/cópia da RangeArmor passaram.
- Export Windows64 pela GUI com compressão gerou ZIP, preservando entrega anterior.
  Integridade e caminhos `/` conferidos; pacote extraído em pasta com espaços executou
  launcher com exit 0 e confirmou uso do hull preparado. CRT e `.cooked` presentes.
- Preferências restauradas; nenhuma publicação. Evidências e limites no
  [plano da ferramenta](rangearmor-update-plan.md). Runtime de desenvolvimento torna
  ZIP grande; staging público deve excluir símbolos e arquivos internos.

## 2026-10-08 — Jogo confirmado pelo usuário e sobras do editor retiradas

- Usuário confirmou execução do jogo; plataforma/pacote e desempenho não especificados.
- Cinco artefatos antigos do editor movidos de `build/bin/` para backup reversível,
  incluindo executável de teste de setembro e símbolos antigos. Editor atual executou
  com startup de fábrica e retornou 0. Nenhum rebuild limpo necessário.
- Runtime e RangeArmor mantêm os nomes da primeira etapa. Inventário e backup no
  [plano de migração](executable-rename-plan.md).

## 2026-10-08 — Exportação pela GUI da RangeArmor testada e logotipo ampliado

- Projeto temporário aberto pelo botão Open Project/seletor de pasta; botão Export
  Windows64 gerou cache/entrega e mostrou sucesso. Launcher exportado executou a lógica
  da cena e utilizou hull preparado. MainFile inexistente mostrou falha na GUI e manteve
  entrega anterior. Controles reais acionados por automação de acessibilidade do Windows.
- Logotipo do cabeçalho ganhou área fixa de 280 × 84 pontos, com proporção preservada.
  Build release passou; painel instalado aberto para conferir aparência. Backup em
  `build/safety-backups/rangearmor-logo-20261008-105253/` e imagem em
  `build/rangearmor-logo-validation.png`.
- Lista de recentes/config do painel restaurada byte a byte. Sem alteração de projeto
  real ou publicação. Limites e evidências no [plano](rangearmor-update-plan.md).

## 2026-10-08 — Painel RangeArmor recompilado com tratamento de exit code

- Runner Rust considera exit code além de mensagens `X ` e aguarda leitura dos dois
  streams antes de marcar conclusão. Novo teste cobre saída 7 sem prefixo de erro.
- 26 testes passaram e build release concluiu com MSVC/vcvars64/VSLANG. Rust 1.92
  não satisfazia dependências egui/eframe; instalado toolchain 1.95.0 separado e usado
  explicitamente, sem mudar o compilador padrão. Avisos de campos não lidos em `project.rs`.
- Executável novo criou janela e fechou com exit 0 antes/depois da instalação; hashes
  SHA256 conferem. Backup em `build/safety-backups/rangearmor-panel-20261008-104444/`.
  Nenhuma publicação. Exportação pela GUI/jogo real continua pendente; [plano](rangearmor-update-plan.md).

## 2026-10-08 — Inicialização do painel RangeArmor verificada

- Painel instalado Rust/eframe criou sua janela e fechou normalmente, exit 0.
  Teste identificou janela por PID/título e enviou fechamento; `WaitForInputIdle`
  não era adequado ao executável. Evidência em `build/rangearmor-panel-startup.json`.
- GUI Godot permanece como backup. Interação com projetos/botões ainda pendente.
  Fonte Rust do runner ignora exit code e depende de prefixo `X `; correção para
  falhas silenciosas ficou registrada no [plano](rangearmor-update-plan.md).

## 2026-10-08 — Erros na cópia de runtimes da RangeArmor propagados ao chamador

- Script de cópia retornava sucesso após diagnóstico de falha. Agora encerra com código 1
  para projeto inválido, runtime ausente, plataforma não suportada ou exceção na cópia.
- Nove testes passaram, incluindo CLI real e restauração do runtime anterior após falha
  na substituição pelo staging. Script instalado atualizado com backup; execução sem
  config retornou 1. GUI permanece pendente; [plano](rangearmor-update-plan.md).

## 2026-10-08 — Runtime copiado pela RangeArmor executado fora do build

- Script instalado copiou instalação real para projeto temporário em caminho com espaço
  e acento. CRT/Python/player presentes, editores excluídos. Preparador instalado gerou
  `ANACOOK2` usando player copiado; execução de `.rasec` confirmou uso do cache e marcador
  da lógica da cena. Evidência em `build/rangearmor-real-copy-validation.txt`.
- Teste direto anterior revelou limitação de codificação do destino de `ANASTACIO_COOK`
  com acento; preparador atual passou com arquivo temporário e cópia Python. Limitação
  nativa registrada no [plano](rangearmor-update-plan.md), sem alteração de C++.
- GUI, jogo real, outra GPU/Linux e APK em aparelho continuam pendentes.

## 2026-10-08 — Cópia dos runtimes da RangeArmor atualizada

- Script instalado legado foi preservado em backup e substituído pelo fonte recuperado.
  Removida dependência de corte fixo do caminho Python e de lista fixa de DLLs que omitia CRT.
- Cópia exclui editores RangeEngine/AnastacioEngine, preserva player e dependências,
  usa staging e mantém runtime anterior em pasta `.previous-*`. Destinos sobrepostos
  à origem ou fora do projeto são recusados.
- Oito testes Python passaram; cópia executada sobre instalação simulada, com falha
  injetada e preservação do destino anterior. GUI, instalação completa e jogo real
  continuam pendentes. Ver [plano](rangearmor-update-plan.md).

## 2026-10-08 — Exportadores Web/Android verificados com o editor renomeado

- Usuário confirmou funcionamento do editor novo. 131 testes puros Web/Android passaram.
- Integração `engine_web_export.py` passou no `AnastacioEngine.exe`: pacote/manifesto,
  controles e preservação da exportação anterior verificados. Preflight inicial reportou
  `WEB-GFX-002`: falso positivo causado por log de tempo com "shaders" e "compiled".
  Heurística em `tools/web/package-web.py` agora exige indicação de falha. Teste JavaScript
  de regressão passou para logs de sucesso, falha real e diagnóstico estruturado; novo
  export/preflight real passou sem problemas. Diagnóstico inicial preservado em
  `build/editor-rename-web-preflight.json`. Jogo real continua exigindo validação visual.
- Integração `engine_android_export.py` passou, incluindo Gradle `assembleDebug`, relatório
  e conteúdo do APK. APK de teste gerado no diretório temporário registrado no plano;
  não instalado em aparelho nem publicado. Android NDK permanece congelado.
- Nomes `RangeRuntime.exe` e artefatos `RangeRuntime` Web preservados. Nenhuma alteração
  de C++ ou do formato de cooking nesta continuação. Ver [plano](executable-rename-plan.md).

## 2026-10-08 — Editor Windows renomeado para AnastacioEngine.exe

- `OUTPUT_NAME` no ramo executável Windows do alvo `RangeEngine`; módulo `bpy`, alvo interno,
  player, APIs, preferências, ProgIDs e nomes Linux/Web preservados. Recurso Windows compartilhado
  distingue `OriginalFilename` do editor e do player. Detecção do processo pai aceita nomes
  novo/legado com comparação exata sem distinção de caixa; ícones externos não dependem do nome novo.
- Build inicial teve LNK1104 no player e falha no install do editor por arquivo ausente.
  A instalação global do pós-build podia concorrer com o link do player. Dependência Windows
  `RangeEngine` → `RangeRuntime` agora ordena essas etapas; segundo build completo passou.
  CMake informou ausência do compilador CUDA neste ambiente; recompilação de cubins não foi validada.
- 32 arquivos de ferramentas/templates tiveram comandos Windows atualizados, além das instruções
  vigentes. README distingue fonte atual de releases anteriores, cujos executáveis não mudaram.
- Backup em `build/safety-backups/editor-rename-20261008-095726/`; editor antigo movido de
  `build/bin/` para esse backup. Não foi encontrado Registro apontando ao antigo executável desta
  instalação, portanto não foi criada nem removida associação de arquivos.
- Validação: `ninja RangeEngine RangeRuntime` passou com vcvars64/VSLANG; editor iniciou e expôs
  novo caminho; metadados dos dois executáveis corretos; Cook real, abertura de `.range`, save
  de cópia e resolução do painel pelo editor novo passaram. Caminho do painel foi capturado em
  teste, sem iniciar a GUI. Sete testes Python do backend RangeArmor continuam passando.
- ZIP local `build/dist/AnastacioEngine-rename-validation-20261008-100156.zip` extraído em pasta
  com espaços: editor iniciou; player gerou `.cooked` e executou `.rasec`. `blender.crt/` presente,
  executável antigo ausente do ZIP. Pacote de validação não publicado.
- Pendente: jogo real/GUI/console, Steam/LAN, registro e remoção HKCU/HKLM em ambiente de teste,
  Windows sem Visual Studio. Ver [plano de migração](executable-rename-plan.md).
  Verificador de docs mantém os 30 erros/61 avisos anteriores dos mapas de código.

## 2026-10-08 — RangeArmor: preparo do cooking e exportação com staging

- Backup em `build/safety-backups/rangearmor-20261008-093834/`: módulos de fonte antes da edição,
  scripts instalados originais da RangeArmor, launcher original e comparação com o snapshot.
  Fonte histórico `69df19d9` recuperado em `tools/rangearmor/`, fora da pasta ignorada.
- Cook manual prepara saída temporária, substitui o cache após sucesso e preserva o anterior em
  falha/timeout. Uma preparação vazia bem-sucedida remove o resultado antigo.
- Backend RangeArmor prepara o `.cooked` do `MainFile` protegido antes de empacotar. Export de um
  clique fornece o runtime do host; save protegido e JSON precisam terminar com sucesso.
  Painel usa caminho derivado do diretório do editor, sem corte fixo pelo nome do executável.
- Opção `Cook before export`, ligada por padrão no export de um clique. Desligada usa `--no-cook`:
  entrega sem `.cooked`, preservando os caches de autoria. Painel independente mantém preparo padrão.
- Release em staging, com entrega anterior preservada em `.previous-*`, falhas com exit code 1,
  nomes de saída confinados ao projeto e ZIP com `/`; formato escolhido pelo alvo Windows/Linux.
- Teste inicial do pacote extraído encontrou launcher obsoleto com panic `Option::unwrap()`.
  Launcher Windows recompilado do fonte recuperado, template instalado atualizado e hash do
  template antigo registrado para substituição apenas na entrega. Launchers personalizados e
  binários originais dos projetos existentes permanecem preservados.
- Validação: build `RangeEngine RangeRuntime` com vcvars64/VSLANG passou após um LNK1104 transitório
  no primeiro link; Cook, preset e opção de export executados no editor; sete testes Python de segurança e dois
  testes Rust passaram. Exportador instalado gerou ZIP, extraído em outra pasta, cujo launcher
  retornou 0 e cujo jogo gravou marcador de execução. Incluiu `blender.crt/` e `.cooked`.
- Pendente: jogo real, interação visual da GUI, Linux, outra GPU e
  migração dos runtimes de projetos antigos. GUI preservada; executáveis da engine não renomeados.
  `check_docs.py` continua apontando 30 erros/61 avisos anteriores nos mapas de código.

## 2026-10-08 — YoFrankie: fases cozidas e ReplaceMesh sem malha

- Medição no porte do YoFrankie (`D:\yofrankie`): o carregamento lento das fases era compilação de shaders
  (ex. `level_1_home`: 9,6 s com cache do driver frio, 1,1 s com ele quente, 0,2 s com o `.cooked`).
  Cook de todas as fases: minilevels 6–8 s → ~0,1 s, `level_underworld` 5,7 s → 0,19 s, seletor 2,1 s → 0,08 s.
  Sobra por fase ~0,3 s de conversão (tangentes ~0,2 s) e ~0,25 s de texturas.
- ReplaceMesh (`BL_ConvertActuators.cpp`): malha que nenhum objeto da cena usa agora é convertida na hora,
  como no Blender 2.4x. Actuator sem malha não avisa mais: os scripts do HUD a definem por nome
  (`actuator.mesh = ...`); o aviso aparecia 14 vezes em toda fase.

## 2026-10-07 — Arquivo cozido: pontos do Convex Hull em `.cooked`

- Medição por etapa (teste `tests/convert_flag/make_vs_libload.py`, que agora grava o `getLoadLog()` em
  `vs_results.txt`): LibLoad de 12 objetos 2336 ms = física 1604 ms (cada esfera Convex Hull de 130k
  triângulos ~210 ms no `btConvexHullComputer`), malhas 406 ms, 1º shader 317 ms; terreno Triangle Mesh
  ~13 ms. Tangentes e texturas 0.
- Novo `CcdCookedData` (Physics/Bullet): guarda os pontos do casco por hash dos vértices em
  `<arquivo principal>.cooked`, aberto/fechado pelo `BL_Converter`. Grava só quando o principal é `.blend`
  (jogar no editor); jogo exportado só lê. O hash ignora a ordem dos vértices: a mesma malha chegava em ordem
  diferente a cada objeto (8 esferas iguais davam 8 hashes).
- Export Game copia `<blend>.cooked` para `<jogo>.cooked` (ou apaga um antigo).
- Resultado (1 entrada de 464 KB): física 1661 → 41 ms; LibLoad 2388 → 763 ms; `convertObject` 2490 → 878
  ms; assíncrono 2770 → 967 ms. Mesmo sem arquivo, a 1ª rodada cai para ~1,2 s (as esferas iguais
  reaproveitam o casco). Jogo exportado conferido: física 40 ms no LibLoad.
- Botão **Cook** (`game.cook`, `bl_operators/anastacio_cook.py`) e **Clear Cooked** (`game.cook_clear`): painel
  "Cook" logo abaixo do Engine (Render) e os dois botões antes do Play no cabeçalho e na barra flutuante da 3D
  View. O Cook salva uma cópia temporária e abre o RangeRuntime com `ANASTACIO_COOK=<blend>.cooked`: converte
  todas as cenas e objetos (inclusive On Demand; só Editor Only fica fora) e sai antes do 1º frame, sem lógica.
  Testado com o `vs_convert.blend` (tudo On Demand): gerou a entrada do casco; runtime 5,4 s.
- Ícone novo `COOK` (panela) no espaço BLANK 42: `.dat` 16/32 do atlas embutido e PNGs de `icons_blender5` e
  `icons_upbge`.
- Shaders de material cozidos: `GPU_SHADER_FLAGS_BINARY_CACHE` (só no codegen; `RAS_Shader` religa o programa e
  fica fora) faz `gpu_shader.c` procurar o binário GL (`glProgramBinary`) pelos ganchos
  `GPU_shader_binary_cache_set`, ligados pelo `BL_Converter` ao `CcdCookedData` (registro tipo 2). Chave = hash
  de todos os trechos do código + flags + vendor/renderer/versão do driver; binário recusado pelo driver volta a
  compilar e é trocado. Shader do LibLoad 310 → 3 ms; com o Cook, LibLoad 2388 → 473 ms e `convertObject`
  2490 → 536 ms. Imagem conferida igual com e sem cache.
- Bug antigo achado pela chave instável: em `gpu_material.c`, sem sol no mundo (céu atmosférico e névoa), a
  direção/energia/tamanho do sol eram ponteiros para variáveis de bloco já encerrado quando o `GPU_link` lia —
  o shader recebia lixo (ex. `cons35 = vec3(2.2e38, ...)`), diferente a cada execução. Agora `static`.
- Cook não roda mais um passo de lógica: a cena inicial fica suspensa e o launcher desenha um frame (compila os
  shaders do desenho) e sai. Conferido com script que marca arquivo: não rodou. Cena sem Convex Hull agora gera
  `.cooked` (shaders), então o botão de limpar acende.
- `hash_bytes` do cache de normais/tangentes (`BL_BlenderDataConversion.cpp`) passa a ler 4 bytes por passo:
  hash 79 → 35 ms nos 12 objetos; LibLoad do teste 473 → 427 ms. Sobra a montagem dos buffers (~370 ms).
- Shaders no PC do jogador: o binário GL só vale na mesma GPU/driver, então o jogo exportado guarda os seus num
  cache do usuário (`%LOCALAPPDATA%\AnastacioEngine\ShaderCache\<jogo>-<hash do caminho>.shaders`; Linux
  `$XDG_CACHE_HOME` ou `~/.cache`), com cabeçalho `ANASHAD1` + chave da GPU/driver
  (`GPU_shader_binary_device_key`). O `.cooked` ao lado do jogo segue só leitura. Shaders novos durante o jogo
  entram no cache ao fechar.
- Aquecimento na primeira abertura (ou GPU/driver trocado): sem cache válido, `BL_SetShaderWarmUp` liga o mesmo
  modo do Cook (todas as cenas convertidas, cena inicial suspensa, um frame) e o launcher pede `RESTART_GAME`; o
  jogo volta já lendo o cache. Uma vez por arquivo e processo, e o cache é gravado mesmo vazio, para não reiniciar
  em loop. Teste exportado sem `.cooked`: 1ª abertura compilou (314 ms) e reiniciou; 2ª abertura 3 ms.
- Tela do aquecimento: `LA_Launcher` desenha fundo escuro e "Preparing shaders for this graphics card (first
  start only)..." (BLF, perfil compat) antes de converter. Conferido lendo os pixels (a captura do Windows não
  enxerga a janela GL). Launcher passa a incluir blenfont/glew com `GL_DEFINITIONS_RASTERIZER`.
- Testes do cache do usuário: chave de driver trocada no arquivo → aquece de novo; pasta impossível de gravar →
  aquece uma vez, avisa "could not write" e segue sem loop; shader de LibLoad no meio do jogo 310 ms → 3 ms na
  abertura seguinte. Aviso "compiling every shader" saiu do `CcdCookedData` para o `BL_Converter` (só quando
  aquece de fato).

## 2026-10-07 — Teste auditivo Web de Reverb Area com alternância de dois segundos

- Revisão a pedido do usuário: versão 0.1.1 troca pulsos por som contínuo em loop sem
  descontinuidade; gain 1, decay 10 s, reflections 3 e late gain 10. Mantém a limitação EFX.

- Novo gerador `tools/create_web_reverb_ab_scene.py`: Speaker 3D com WAV empacotado,
  pulsos idênticos e pausas, listener fixo e área CAVERN movida para dentro/fora a cada 2 s.
- `tools/web/reverb-ab-status.js` mostra o estado emitido pelo jogo;
  `tools/web/verify-reverb-ab.cjs` verifica logs, intervalo e saída AudioWorklet sem screenshots.
- Editor executou o gerador com exit 0; pacote usa o runtime release existente de 2026-10-04,
  sem recompilação. Edge passou seis estados (0–10 s), alternância ~2 s, effect 0/1 e gain 0,9
  na caverna; AudioWorklet running, 518144 frames, peak 0,12725. Não comprova reverb audível.
- Limitação confirmada no cache (`WITH_OPENAL=OFF`) e no header de compatibilidade:
  o backend SDL não oferece EFX. Estado Python ativo não significa aplicação de reverb no mixer.
  Usuário confirmou nenhuma diferença audível na versão contínua com reverb forte;
  pacote local em `build-web/dist/reverb-ab/`. Segunda execução: peak 0,12844, 518144 frames,
  seis estados PASS. Parser do verificador corrigido para aceitar tempo inicial -0.000.
- Suíte pura Web executada nesta sessão: 131 testes, todos OK (17,329 s).

## 2026-10-07 — Add Object carrega o objeto On Demand só quando dispara

- O atuador Add Object com alvo em Load Mode "On Demand" não converte nada na carga: guarda o nome e
  chama `BL_Converter::ConvertSceneObject` na primeira vez que adiciona (com os filhos). As vezes
  seguintes só replicam. Alvo "Editor Only" gera um aviso no console. Não é mais preciso deixar o
  atuador com o objeto vazio para evitar a carga antecipada.
- Nome vindo de propriedade: depois das camadas inativas e do External Files, procura um objeto
  On Demand da cena.
- O atuador mostra os botões With Scene / On Demand / Editor Only do objeto alvo (`logic_window.c`).
- Teste `tests/convert_flag/make_vs_libload.py`: mesmos 12 objetos por `convertObject` e por LibLoad.
  Tempo igual (~2,3 s), `convertObject` usa ~55 MB a menos; o LibLoad assíncrono não trava o frame.

## 2026-10-07 — Load Mode do objeto: com a cena, sob demanda ou só no editor

- Nova propriedade `Object.game_load_mode` (`SCENE` / `ON_DEMAND` / `EDITOR_ONLY`) sobre os bits
  `OB_TASK_CONVERT` e o novo `OB_TASK_EDITOR_ONLY` (bit 27 de `gameflag`, sem mudança de struct).
  `convert_object` continua valendo; ligá-lo tira o modo Editor Only.
- Editor Only nunca é convertido: `scene.convertObject()` e `setObjectConvert()` recusam o objeto, e filhos
  Editor Only ficam de fora quando o pai é convertido com `children=True`.
- `scene.unconvertedObjects`: nomes que `convertObject()` ainda pode criar (sem Editor Only nem malha liberada).
- `getLoadLog()`: o detalhe de "convert" traz "N left out (M editor only)".
- Outliner (motor de jogo): checkbox de Load with Scene à esquerda do olho; Editor Only aparece como fantasma.
- Painel "Loading" com os 3 modos e botões para os selecionados e filhos; textos traduzidos (pt_BR, es, ru).

## 2026-10-07 — Flag Convert vira "Load with Scene", com avisos no painel

- O rótulo da flag (`Object.convert_object`, bit `OB_TASK_CONVERT`) passa a ser "Load with Scene";
  o nome no Python e no arquivo não mudam. O tooltip cita `scene.convertObject()`.
- O painel "Game Object Tasks" virou "Loading" e vem aberto. Ele avisa os casos que antes falhavam
  em silêncio: objeto ligado sob um ancestral desligado (sai da carga do mesmo jeito), membro desligado
  de um grupo usado por um dupli group ligado, e malha compartilhada com objetos ligados
  (`freeUnconvertedData` não a libera). Com a flag desligada, mostra a chamada `scene.convertObject("nome")`
  e quantos filhos ficam de fora junto.
- Operador `object.game_load_with_scene` (botões "Load All" / "Leave Out All"): liga ou desliga a
  flag nos objetos selecionados e nos filhos deles, com undo.
- `BL_Converter::FindSceneObject` e `BL_Converter::IsChildOf` substituem as cópias que existiam em
  `BL_Converter.cpp` e `KX_PythonInit.cpp`. O teste de runtime de `tests/convert_flag/` sai igual.

## 2026-10-07 - Tesla Rhythm via Python Component

- Planejado e implementado `AnastacioTeslaRhythm`, anexado à câmera da nova
  `build/bin/demos/TeslaPiano/TeslaPiano_Rhythm.range`; fonte cinematic preservada.
- Cinco pistas A/S/D/F/G, 116 notas com acordes, música original sintetizada a 112 BPM,
  pontuação/combo/precisão, pausa, reinício, resultado e calibração de offset.
- WAV e mapa compartilham timestamps; áudio Audaspace é o relógio da descida e câmera.
  Sonda revelou oscilações pequenas na posição do backend; relógio tornado monotônico.
- Overlay post_draw preserva estado GL; câmera alterna lados frontais olhando ao Terminal,
  com fundo parentado à câmera. Controlador de piano anterior fica em estado inativo na variante.
- Núcleo passou fronteiras de julgamento, prevenção de duplicatas, perdas e mapa inteiro.
  RangeRuntime passou sonda com desenho real do HUD, relógio, julgamento, direção da câmera,
  pausa, resultado, reinício e limpeza. Evidência: `rhythm_probe_result.txt` na pasta da demo.
- `python tools/check_docs.py`: zero erros; 36 avisos de mapas existentes desatualizados.
  Aparência e latência percebida aguardam avaliação do usuário no jogo real.
- Contrato e fontes em [tesla-rhythm.md](tesla-rhythm.md).

## 2026-10-07 - Revalidacao das melhorias do Material Atlas

- Nova execucao em build/bin, sem alterar codigo: quatro casos modais passaram com exit 0
  (cancelamento inicial, cancelamento apos dois mapas, falha intermediaria e sucesso com Undo/Redo).
- Suite principal de pixels e persistencia, restauracao com save/reload e objeto compartilhado,
  integracao GI/atlas nas duas ordens e GPU AMD Radeon RX 6800M passaram com exit 0.
- Logs em debug-logs/material-atlas-{core,restore,integration}-retest.log e
  debug-logs/material-atlas-modal-*.log. Aparencia no jogo e Escape fisico seguem pendentes.

## 2026-10-07 - Cancelamento seguro do Material Atlas

- Interface passa a coordenar cinco jobs nativos do baker; Escape e a API
  material.anastacio_atlas_cancel solicitam parada. Main/mesh/nodes, validacao, packing e
  commit ficam na UI thread; a interface e operadores concorrentes de atlas ficam bloqueados.
- object_bake_api.c compartilha o inicio de job sem criar operador modal filho. Completion sink
  recebe FINISHED/CANCELLED na liberacao do job. Callback verifica G.is_break e stop do job;
  imagem parcial nao vira sucesso. ReportList privado evita leitura concorrente pela UI; report
  e callback do Render deixam de apontar para o job depois de liberar sua memoria.
- Rollback aguarda job finalizar/join antes de liberar IDs. Remove timer, restaura configuracao,
  selecao, malha e interface; commit so depois dos cinco mapas validados. Scripts/background
  permanecem sincronos; use_async=True habilita modo modal no editor com janela. Preparacao UV
  e validacao/packing continuam sincronos; nao prometer cancelamento instantaneo.
- Build RangeRuntime e depois RangeEngine, vcvars64 e VSLANG=1033: exit 0. Erro inicial C2664
  em RNA_def_property_flag corrigido com cast explicito de PropertyFlag, sem repetir cegamente.
- tools/run_material_atlas_modal_tests.py: quatro processos isolados com janela, todos exit 0.
  Cancelamento no inicio e apos dois mapas, erro Metallic fora de 0-1 e sucesso com pixels/packed
  maps/Undo/Redo automatico. Fonte/usuarios/UVs/selecao/settings preservados, sem IDs temporarios.
  A tecla fisica Escape nao foi validada: GHOST usa Raw Input e ignora PostMessage de teclado.
  Harness chama a mesma rotina nativa via API. Corrigidos Event.timer inexistente e quit dialog
  que mantinha o processo aberto; runner Python registra exit codes reais (PowerShell retornou null).
- Suites de pixels/rollback, GI nas duas ordens/GPU OpenCL e restore/save/reload passaram.
  Alguns encerramentos do harness modal avisaram 458 bytes nao liberados, origem nao determinada;
  caso final de sucesso encerrou com aviso de 64 bytes tambem visto antes desta mudanca.
  IDs de dados foram conferidos. Player final: exit 0 e ANASTACIO_ATLAS_RUNTIME_PASS.
  check_docs.py: 63 documentos, 0 erros e 36 avisos em mapas existentes; diff --check passou.

## 2026-10-07 - Restauracao explicita do Material Atlas

- Operador C++ material.anastacio_atlas_restore no painel Material Atlas. O commit do bake
  registra fonte e slot ativo com IDProperties da malha. Referencia ID sobrevive a renomeacao,
  duplicacao e salvar/reabrir; sem mudancas de DNA/headers.
- Restaura a malha fonte inteira e slots data-linked, preserva atlas com fake user e nao remove
  materiais/imagens compartilhados. Recusa modifiers, shape keys e slots object-linked.
  Atlas antigos nao recebem busca heuristica. Edicoes posteriores nao sao transferidas;
  GUI/report explicam rebake de GI quando a iluminacao foi feita depois do atlas.
- RangeRuntime compilou/linkou; RangeEngine terminou com exit 0 via vcvars64/VSLANG=1033.
  Teste --restore passou com fonte renomeada, reload, atlas compartilhado, recusa de modifier,
  slot ativo, UV fonte, packed maps e novo save/reload. Suite original de pixels/rollback passou.
  Player executou native_atlas_test.range, exit 0 e ANASTACIO_ATLAS_RUNTIME_PASS.
- Cancelamento permanece separado: object_bake_api.c bake_exec nao processa Escape em execucao
  sincrona. Exige jobs/controle de interrupcao; proxima peca aguardando revisao pelo workflow.
  Logs material-atlas-restore-{build,player-build,test,runtime}.log em debug-logs.

## 2026-10-07 — Física de malha de triângulos na conversão: metade do tempo

- A caixa local da forma (`btTriangleMeshShape::recalcLocalAabb`) varria todos os triângulos 6 vezes.
  `CreateBulletShape` agora calcula o mesmo mínimo/máximo numa passada pelos vértices dos triângulos e
  entrega pronto (`setPremadeAabb`), antes de cada forma, então vale também para `reinstancePhysicsMesh`.
- Durante a etapa de física do conversor (`CcdBeginBvhBatch`/`CcdEndBvhBatch`), o hash e a BVH de cada
  malha diferente ficam para o fim da etapa e rodam em todos os núcleos; cópias idênticas seguem
  dividindo uma BVH. Fila por thread, então o LibLoad assíncrono monta a sua. O hash agora lê 8 bytes
  por vez. `RANGE_NO_BVH_BATCH=1` volta à construção uma a uma, para comparar.
- 8 pilotos de ~327k triângulos: física 295 → 147 ms, load da cena 779 → 627 ms.
- Conferido com `tests/convert_flag/make_bvh_test.py` (malhas únicas, Shift+D, Alt+D com escala,
  LibLoad assíncrono e `reinstancePhysicsMesh`): 900 raios por grupo e 6 bolas caindo por 120 frames
  saem byte a byte iguais ao caminho original.

## 2026-10-07 — `scene.convertObject` e `bge.logic.freeUnconvertedData`

- `scene.convertObject(nome, children=True)` (`BL_Converter::ConvertSceneObject`): converte em runtime
  um objeto da própria cena deixado de fora pelo Convert, mais os filhos não convertidos. Usa a
  cena temporária de `FindOrConvertMainObject` com os layers da cena de origem: vai para `objects`
  se estiver num layer ativo, senão para `objectsInactive`. Objeto já convertido é devolvido como
  está. Pai já vivo na cena: o filho é convertido como raiz, religado com `SetParent` e posto sob
  um nó de `parentinv` com a relação da carga normal (normal, vértice, pai lento ou osso). Pai não convertido
  ou em layer ativo/inativo diferente: `ValueError`, como o load que descarta esse filho.
- Conferido no Play do editor (`make_editor_test.py` + `run_editor_test.py`, roda o player
  embutido e confere depois): os flags mudados por `setObjectConvert` voltam ao valor original e
  `freeUnconvertedData` dá `RuntimeError` sem tocar na malha.
- `bge.logic.freeUnconvertedData(scene)`: só no player standalone (`initPlayerPython` marca o Main
  como do jogo; no player embutido o Main é o do editor e a chamada dá `RuntimeError`). Libera a
  geometria (CustomData) das malhas cujos únicos usuários são objetos da cena com Convert
  desligado e não convertidos; `Mesh`, materiais e shape keys ficam. Depois disso
  `convertObject`, `setObjectConvert(..., True)` e `ConvertMeshSpecial` recusam esses dados.
  Teste de 8 pilotos, 2 convertidos: 37,5 MB liberados em 5 ms (a diferença para o `LibLoad`
  era ~45 MB). Testes: `tests/convert_flag/make_runtime_test.py` e `FREE_UNCONVERTED=1` em
  `make_test.py`.

## 2026-10-07 — Membros de dupli group respeitam o Convert

- `BL_ConvertBlenderObjects`: objetos de grupo com `convert_object` desligado não são mais
  convertidos ao instanciar o grupo (antes o flag só valia para objetos da cena). `DupliGroupRecurse`
  já ignora membros não convertidos. Teste: `tests/convert_flag/make_group_test.py`.

## 2026-10-07 — Conversão de malhas ~33% mais rápida, `getLoadLog` e armature sem pose

- `BL_ConvertDerivedMeshToArray`: a lista de vértices compartilhados (um `std::vector` por vértice
  da malha, uma alocação cada) virou cadeias num pool único (`BL_SharedVertexMap`), mesma ordem de
  busca; `RAS_DisplayArray::Reserve` pré-aloca vértices/índices por material. Vale para qualquer
  cena e para malhas de modifiers em runtime (`BL_ModifierDeformer`). Teste de 8 pilotos (~327k
  tris cada): etapa de malhas 595 → ~399 ms, load da Pista_1 ~976 → ~793 ms. Verificação
  temporária comparando busca nova x antiga: 0 diferenças em 2,46 M vértices (com e sem UV).
- `[Load] convert` detalha objetos, logic, mesh users, culling, bounds e malha (dm, normals, end).
  Nova `bge.logic.getLoadLog(clear=False)`: lista de dicts (scene, stage, ms, detail, total).
- `BL_ArmatureObject`: armature nunca avaliada (sem `pose`, ex. criada por script numa cena
  inativa) travava o player; a pose é construída com `BKE_pose_rebuild` antes da cópia.
- Medições (`tests/convert_flag/make_test.py`, opções `mat` e `arm`): material de nó com textura +
  Normal Map soma ~135 ms de tangentes (calculadas uma vez e copiadas para malhas iguais), shader
  1 compilado e 7 reutilizados; 20 armatures de 60 ossos com Action em layer inativo: ≤5 ms.
  Ainda dominam malha (~400 ms) e física triangle mesh (~345 ms). Build `RangeEngine RangeRuntime`.

## 2026-10-07 - Validacao adicional do Material Atlas

- `tools/test_material_atlas_integration.py`: GI -> atlas -> GI e atlas -> GI passaram com bake
  real de World, 256px/8 samples, sem denoise/light volume. Pixels finitos e iluminacao nao preta;
  atlas preserva pixels/UV de GI e rebake de GI preserva as cinco imagens/UV do atlas.
- GPU OpenCL AMD Radeon RX 6800M selecionada, CPU desabilitada nas preferencias: cinco passes
  e cores esperadas passaram; configuracao GPU preservada depois da operacao.
- Editor com janela: Undo/Redo restaurou dois materiais/UV fonte e depois material unico/cinco
  imagens packed. Script insere undo_push explicitamente; clique habitual permanece pendente.
  Primeira tentativa do harness perdeu contexto apos factory reset; corrigido preservando a janela.
  Ao encerrar, editor avisou um bloco nao liberado de 64 bytes; origem nao determinada.
- Pacote Web exportado por validate-web.py; preflight sem incompatibilidades. Edge 154.0.4258.62
  headless/WebGL 2 carregou cena, compilou shaders e emitiu ANASTACIO_ATLAS_RUNTIME_PASS.
  `tools/test_material_atlas_web.cjs` usa playwright-core e navegador instalado; nao captura telas.
- Logs em debug-logs/material-atlas-{integration,undo,web,web-runtime}.log. Nenhuma mudanca de
  producao nesta validacao; executaveis existentes usados. Linux sem binario atual disponivel;
  visual real, GI com denoise/volume e clique habitual de Undo seguem abertos.
- check_docs.py: 0 erros, 36 avisos de mapas existentes antes da atualizacao documental.

## 2026-10-07 — `bge.logic.setObjectConvert`: escolher objetos convertidos antes do load

- Novas funções `bge.logic.setObjectConvert(scene, object, convert, children=True)` e
  `getObjectConvert(scene, object)` em `KX_PythonInit.cpp`. Ligam/desligam o flag Convert
  (`OB_TASK_CONVERT`, painel Game Object Tasks) de um objeto e, por padrão, dos descendentes, numa
  cena ainda não carregada (busca inclui set scenes). Uso: no menu, desligar pilotos não escolhidos
  antes de `replace("Pista_1")`. `ValueError` se cena/objeto não existir; retorna quantos mudaram.
- Flags originais são guardados e restaurados em `exitGamePython()`, só para objetos ainda no
  `G.main`: no Play embutido as mudanças não vazam para o editor nem para o `.blend` salvo.
- Limites: só vale antes da conversão da cena; membros de dupli group ignoram o flag; logic bricks
  apontando para objeto desligado perdem o alvo; objeto ligado a várias cenas é afetado em todas;
  dados brutos do mesh continuam na RAM (economiza conversão: GPU, física, logic).
- Teste `tests/convert_flag/make_test.py` (8 pilotos pesados, 3 rodadas): load da Pista_1 com todos
  ~972 ms / 680 MB; com 2 via setObjectConvert ~356 ms / 466 MB; com 2 via LibLoad de arquivos
  separados ~377 ms / 421 MB. Custo dos flags ~0,05 ms. Build `RangeEngine RangeRuntime` passou.

## 2026-10-07 — Material Atlas nativo em C++ e correções de bake

- Nova ferramenta em Properties > Material > Anastacio Material Atlas. Operador C++
  `material.anastacio_atlas_bake`; painel padrão apenas invoca o operador, sem depender do addon.
  Um mesh ativo, materiais PBR opacos com Principled: Base Color, Roughness, Metallic, Specular e
  Normal, packed PNG 16 bits, UV AnastacioAtlas e material único. Malha fonte fica como backup;
  materiais fonte e demais objetos compartilhando a malha não são alterados.
- Reutiliza `ae_uvatlas` diretamente; triangulação real e detecção de UV conflitante por loop.
  Bake de cor/scalars por emissão evita iluminação duplicada e Base Color preto em materiais
  metálicos. Normal usa tangent space do atlas, preservando a UV fonte do Normal Map.
  Não aplica denoise de GI em mapas físicos; Lightmap e configuração de iluminação permanecem.
- `bake_api.c`: busca de UV nomeada corrigida de CD_MTFACE para CD_MLOOPUV; inicialização de
  primitivas inválidas acontece antes de retornar por UV ausente; stride da normal por polígono
  corrigido para poly * 3. A UV nomeada incorreta provocou crash reproduzido durante o teste.
- Execução prepara cópias, verifica os cinco passes/pixels, cria o material e só então aplica.
  Restaura render, samples/device e seleção; falha no pack libera temporários. Node tree final é
  embedded ID do material. Stubs de progresso adicionados ao player para permitir link do editor
  compartilhado, sem UI de bake no standalone.
- `ninja RangeEngine RangeRuntime` com vcvars64 e VSLANG=1033 passou; instalação em build/bin.
  No rebuild final, player e editor foram construídos em chamadas separadas, nessa ordem:
  a chamada conjunta apresentou LNK1104 no player e a instalação do editor tentou ler o EXE ausente.
  `ninja RangeRuntime` e depois `ninja RangeEngine` passaram sem alterar flags de compilação.
  `tools/test_material_atlas.py` passou: seis materiais, metal total, gradiente na UV fonte, normal
  inclinada reconstruída na UV de atlas, source/Lightmap preservadas, mesh compartilhado,
  rejeição de transmissão, rollback de pack degenerado, proteção contra rebake e save/reload.
  Também valida UV fonte ausente e rollback após passes executados com valores fora de 0–1;
  o formato PNG não pode cortar silenciosamente mapas HDR/dados inválidos.
  RangeRuntime carregou a cena, compilou shaders e confirmou material único, encerrando com código 0.
- Limites e pendências no [plano](material-atlas-plan.md): materiais legados, vários objetos,
  transparência, modifiers/shape keys e grafos mais amplos não entram nesta primeira peça.
  Visual no jogo real, Undo na interface, GPU e Web/Linux ainda pendentes.
- Check documental padrão encontrou arquivos rastreados removidos por outra tarefa (ex.
  `docs/parallel-work-plan.md`); execução do mesmo verificador filtrando arquivos ausentes passou
  com 0 erros e 35 avisos de mapas existentes. Nenhum arquivo removido foi restaurado.

## 2026-10-07 — pesquisa e preparação do atlas de materiais

- Complemento: auditoria do Baked Lighting atual, matriz de reutilização de UV/xatlas, bake Cycles, GPU, padding e progresso; contrato de coexistência Lightmap + AnastacioAtlas. Na etapa de preparação somente documentação foi alterada.

- Auditoria estática do `automate_atlas_bake.py` 1.3: gera mapas, mas não cria material final; falhas de passe podem terminar em FINISHED; UVs, materiais e imagens requerem proteção.
- Pesquisa de Material Combiner, Bake Groups, BakeToSingleMaterial e Auto-Bake, com versões/API e licenças observadas. Recomendação: evolução própria e reutilização das capacidades locais de UV/bake.
- [Plano](material-atlas-plan.md) registra contrato, etapas, limites, matriz de validação e fontes. A implementação foi autorizada posteriormente e registrada em entrada separada.

## Texture Paint: traços Line e Curve voltam a pintar (2026-10-07)

- `paint_image.c`: a checagem "mouse sobre face do objeto ativo" (`fff04797`) lê o backbuf de seleção a cada
  pincelada. Line e Curve geram as pinceladas de uma vez, sem redesenho; depois da primeira o backbuf devolve
  as cores da viewport (índices como 466210 numa malha de 6 faces) e o traço inteiro era descartado. Esses
  traços agora pulam a checagem (`texture_paint_brush_is_batched`); o traço livre continua com ela.
- Dicas do rodapé: modo Curve mostra os atalhos da curva (Ctrl LMB ponto, Enter pinta); Line diz
  `Drag + release`.
- Validado: curva por script altera os pixels; usuário confirmou pintura com Line e Curve.
- Em aberto: crash por corrupção de heap (`0xc0000374`) visto em 06/10 e 07/10 pintando, sem reprodução.

## Editor: dicas de atalho nos modos de pintura e sculpt (2026-10-07)

- `view3d_draw.c`: faixa no rodapé da 3D View, alinhada à esquerda e acima da barra flutuante Play/Standalone,
  com tecla + ação para Texture Paint, Sculpt, Vertex Paint e Weight Paint (tirado dos keymaps de
  `paint_ops.c`). Contextual: traço Line mostra `Drag Draw line · Alt Snap angle`; Fill com degradê mostra
  `Drag Gradient direction`. Quebra em linhas quando a viewport é estreita. O BLF desliga `GL_BLEND` a cada
  texto, por isso o blend é religado antes de cada moldura.
- Textos em inglês via `IFACE_`/`N_`, traduzíveis por Preferences > International Fonts.
- Liga/desliga: `UserDef.uiflag2` `USER_HIDE_PAINT_HINTS` (negativa, prefs antigas mostram as dicas), RNA
  `show_paint_hints`, em Preferences > Interface e no menu de botão direito do cabeçalho da 3D View
  (`screen_ops.c`). Nada novo no .blend da cena.
- `properties_paint_common.py`: topo do painel do pincel com `Free | Line | Curve` (`stroke_method`) e
  `Solid | Gradient` (`use_gradient`); o checkbox de degradê do fim do painel saiu.
- Build `RangeEngine` OK; screenshot validado em Texture Paint e Sculpt. Botões do painel ainda sem teste manual.

## Viewport: overlays restantes no estilo Blender 5 (2026-10-07)

Linhas com `GL_LINE_SMOOTH` + blend (desligado no picking, estado de blend do chamador restaurado),
larguras e pontos escalados por `U.pixelsize`, pontos redondos (`GL_POINT_SMOOTH`).
- `view3d_draw.c`: cursor 3D com anel de 8 traços vermelho/branco, halo escuro e cruz com vão; eixo Z do
  grid fino e suave; nome da vista e info do canto com sombra (novo `BLF_shadow_default` em `blf.c`).
- `drawobject.c`: origem do objeto quase opaca com borda escura; wire de curva/texto/superfície/metaball;
  edição de curvas (alças, splines, pontos); lattice; normais e marcas seam/sharp/crease/bevel do Edit Mode;
  bounds, colisão, rigid body e texture space; moldura do empty de imagem; particle edit.
- Transform: linhas de restrição, círculo proporcional, snap e helplines suaves; snap ativo vira anel com
  halo e ponto central. Knife suave e com pontos redondos. Motion paths suaves com pontos redondos.
- Anel do pincel: 96 segmentos, 1,5 px, halo escuro; no Sculpt alpha 0,8.
- Sem mudança: ruler e gestos de seleção (já seguiam o padrão), desenho de partículas fora do particle edit.
- Build `RangeEngine` OK; validação visual pendente.

## Viewport: bones e cursor de pintura no estilo Blender 5 (2026-10-07)

- Referência: fonte do Blender 5.0 em `D:\blender5-ref` (sparse: `sculpt_paint`, `uvedit`, `blenkernel`,
  `geometry`, `draw/engines/overlay`). Só overlays; shading dos meshes e formato do .blend inalterados.
- Bones (`drawarmature.c`): sólidos sem luz GL, com a mistura de 2 tons do
  `overlay_armature_shape_solid_vert.glsl` (luz `(0.1, 0.1, 0.8)` em view space, tom escuro = 35% da cor) em
  Octahedral, B-Bone (caixas) e Envelope (esfera/cilindro próprios no lugar do GLU). No Object Mode, arestas
  finas suaves na cor de wire do objeto (laranja quando selecionado); a primeira tentativa, um contorno escuro
  grosso por silhueta, foi rejeitada pelo usuário. Wire e Stick com linha suave, 2 px no bone selecionado.
  Seleção por clique (`G_PICKSEL`) continua com o desenho antigo.
- Axes dos bones (`drawaxes_colored` em `drawobject.c`): X/Y/Z em vermelho/verde/azul misturados com a cor do
  texto (0.1 selecionado, 0.65 não selecionado), letras mais claras, linhas suaves. Empties sem mudança.
- Cursor do pincel (`paint_cursor.c`): fora do Sculpt, cinza 0.75 com alpha 0.9 como os brushes essentials do
  5.2; só substitui o vermelho padrão, então uma cor de cursor customizada salva no arquivo é mantida.
- Texture Paint em plano grande perto da câmera: o Blender 5.0 tem o mesmo descarte do triângulo inteiro
  quando um vértice fica antes do near clip (`project_paint_flt_max_cull`, com `TODO`); não há correção para
  portar, e o teste de bucket da engine já é mais completo (aresta `v3-v1`).

## Multiplayer: correções da revisão Steam, retorno à sala e adaptadores (2026-10-07)

- ImGui Python: `push_style_var`/`pop_style_var` com constantes `STYLE_*` e
  `load_default_font(size)`, fonte da engine com ícones ForkAwesome em outro tamanho. O atlas
  fica travado durante o frame, então o tamanho é montado no `NextFrame` seguinte (retorna
  `None` até lá). Menu `AnastacioNetworkComponent` redesenhado (16 px, tema, ícones); capturas
  de configuração, sala e espera conferidas no player.
- Testes de plataforma da rede (local, 2026-10-07): Linux (WSL Ubuntu, GCC 15) build isolado com
  121/121 gtests, incluindo o plugin ABI via `.so`; wasm (emsdk local) 60/60 no filtro do CI, golden
  incluídos (rodar no node Linux: com `NODERAWFS` no Windows o gtest aborta sem cwd, e o caminho
  `D:/…` do golden precisa de um link `D:` → `/mnt/d` na pasta atual). Interoperabilidade:
  `net_echo` cliente Linux→servidor Windows (ENet) e Windows/wasm→servidor Linux (ENet e
  WebSocket), 3/3 ecos. Navegador: `RangeRuntime --server` no Windows + `net_web_watch` no Chrome
  headless (`--enable-logging=stderr`, sem playwright): `NETWEB PASS spawns=1 snapshots=40`,
  servidor `NETTEST server PASS`. Falta o RangeRuntime completo no Linux e o player web da engine.
- ImGui Python: `push_item_width`/`pop_item_width`/`set_next_item_width`; campos, slider e chat
  do menu de rede agora ocupam a largura do conteúdo. `load_font` não mexe mais no atlas no meio
  do frame: valida o arquivo, enfileira e devolve o id definitivo (fila única com
  `load_default_font`, montada em ordem no `NextFrame`); `push_font` com id ainda na fila usa a
  fonte atual, mantendo push/pop balanceados.
- Revisão final: sair da sala preserva convites não lidos; "Iniciar partida" some durante a
  partida; o controlador guarda a cena da sessão ao hospedar (`lobby_scene`). No RolimaRacer,
  o botão de resultado online faz o host chamar `return_to_lobby` (cliente aguarda) e `on_lobby`
  limpa HUD/resultado e reabre `_network_menu`. Só checagem de sintaxe; falta teste no jogo real.
- Complemento Windows lê `+connect_lobby` dos argumentos reais do processo, com tokens
  completos, validação de ID e suporte a caminhos com espaços. Mantido fallback da API Steam.
  Player externo aceita argumento de convite após o arquivo, sem tratá-lo como filename.
- Cancelamento e timeout retiram CCallResults, zeram pending e permitem nova operação.
  Handles tardios de create/join são recolhidos separadamente para deixar salas abandonadas;
  acompanhamento limitado a 64 operações. Teste SDK passou cancelar e recriar sem espera.
- Eventos de desconexão não são descartados; novas conexões são limitadas quando a fila
  acumula. Snapshot/Input descartam mensagens antigas por número da lane. ReplicaClient
  já descartava snapshots antigos por tick e InputQueue já descartava inputs consumidos.
  Membro cuja lista local ainda não atualizou aguarda até 3 segundos, com limite de conexões.
- `Range.network.return_to_lobby()`/`on_lobby` resetam partida/prontidão e notificam clientes.
  Controlador reabre Steam; retorno com nome de cena espera seu carregamento no host.
  Componente tem show/hide/return_to_lobby e reaparece ao voltar; show explícito funciona
  durante a partida. Convite em sessão pede confirmação, chat usa nomes, LAN mostra IPv4
  locais/porta, nome só é escrito ao editar e capacidade usa slider 2..64.
- Agente solicitado pelo usuário corrigiu adaptadores RolimaRacer: início delegado uma vez
  ao NetworkManager, responsável persistente pelo tick no SteamComponent e fallback no menu,
  enable_steam=False evita init e seleção de pista/carro fica com host. Pacote instalado
  foi adicionado ao ignore do jogo. Assets/veículos não alterados nem mudanças commitadas.
- Builds MSVC do complemento/editor/player e CTests passaram. Teste determinístico do
  complemento cobre argv, cancelamento/timeout, fila e sequenciamento; teste dos adaptadores
  simula on_start atrasado e confirma início único, tick, convite e chat. Dois players ENet
  passaram duas partidas, retorno/reset e reentrada; regressão spawner passou.
- SDK socket pair passou canais/handshake/replicação; menu Steam passou retorno, busca
  pública após propagação de metadados e segunda partida. Primeiro teste de busca consultou
  antes da publicação; aguardada propagação e PASS. Cena mínima de adaptadores passou
  pista → menu: corrigido o teste para resolver o componente vivo após a troca, em vez de
  conservar proxy destruído. Exportado Steam passou convite argv entregue ao componente
  e menu real; exportado LAN passou sem DLL Steam. Teste de lobby de baixo nível não pode
  competir com o componente pela mesma fila; prova de convite exportado usa o controlador.
- Exportador foi conferido contra distribution-0.1.md: RangeRuntime como player, Python
  completo e blender.crt são requisitos do pacote testado, já registrados na entrada anterior.
  Nenhum release publicado. Convites reais entre contas, relay externo, condição de ordem
  dos membros e corrida/carros reais continuam pendentes; argv com ID fictício não os prova.

## Multiplayer: transporte Steam, salas, componente e exportação nativa (2026-10-07)

- ABI C v2 do complemento, adaptador ITransport em Network e seleção `transport='steam'`
  em host/join. Control/Rpc confiáveis em lanes separadas; Snapshot/Input não confiáveis;
  envelope versionado preserva payload/protocolo nativo. Unload bloqueado com transportes vivos.
- Complemento SDK: P2P, poll groups, limites de payload/orçamento, identificação de peers,
  consulta de rota e desativação de ICE direto para prova de relay; callbacks compartilhados.
  Salas públicas/amigos, filtros jogo/build/protocolo, convites, cancelamento/tardios,
  host saindo e acesso por membros quando há lobby. Sem migração automática de host.
- Componente e estado reutilizáveis em `release/scripts/modules/anastacio_network/`, com menu
  ImGui LAN/Steam, pronto/chat/iniciar/sair. Player adiciona scripts/modules; editor purga
  helpers com Range temporário, inclusive quando importados por adaptadores de jogo.
- RolimaRacer: net_menu virou adaptador da engine, configuração em network_settings;
  SteamComponent compartilha init/callbacks e idioma/conquistas; NetworkManager coordena
  sala/saída e pista. RPC de pista não chama change_scene no cliente (SceneChange é do host).
  Assets `.range` e veículos originais preservados. Scripts anteriores do menu/Steam guardados
  localmente em build-steam/game-script-backup antes da alteração.
- Exportador legado: módulo reutilizável incluído mesmo sem Copy Scripts, seleção opcional de
  pasta Steam, Python completo e blender.crt, player RangeRuntime e perf_counter. Instalador
  explícito para outros exports nativos. AppID dev só entra com opção explícita; nada publicado.
- MSVC: complemento, RangeEngine/RangeRuntime, CTest rede PASS. SDK socket pair passou quatro
  canais nos limites 1200/65536, handshake, chat, transform/propriedade, spawn/despawn/ownership.
  Primeiro probe de spawn não inseria objeto no IWorld do teste; corrigido o fixture e PASS.
- Steam online numa conta: criar/listar sala pública com filtros, metadados, cancelamento,
  host nativo e unload guard PASS. Componente com ImGui no player PASS. Cópias dos adaptadores
  RolimaRacer em cena mínima passaram init compartilhado e transição para Pista_1.
- Regressão LAN spawner em dois players PASS (movimento, propriedade, spawn, pronto/chat/início
  e descoberta). Exports Steam/LAN executados e players passaram; LAN sem DLL Steam.
  ZIP local extraído para build-steam/export-extracted: Game.exe passou com sala real e componente.
- Pendentes: relay real entre duas redes/contas, convites aberto/fechado, corrida/carros reais,
  AppID comercial/conquistas, review da distribuição pública e Linux. Testes locais não são
  evidência desses itens. [Procedimentos](steam-complement-development.md).

## Multiplayer: inicialização Steam online validada, B2 (2026-10-07)

- Steam iniciada localmente; smoke test no RangeRuntime headless com AppID 480 e conta
  conectada confirmou inicialização SDK, identidade, callbacks e shutdown/reinit.
- `STEAMTEST real SDK online PASS` e `STEAMTEST PASS`; contexto de prova final permaneceu
  ativo até StopEngine, que o encerrou corretamente. Log local em build-steam/online-runtime-test.log.
- B2 encerrado para Windows/AppID de desenvolvimento. Transporte, salas, migração de
  conquistas/idioma e validação com AppID comercial continuam pendentes; jogo não foi alterado.

## Multiplayer: inicialização opcional Steam, B2 offline (2026-10-07)

- Novo projeto separado `source/complements/anastacio_steam/`: SDK local, DLL opcional,
  validação do AppID de lançamento, cliente/conta e dono existente; sem relançar editor.
- Serviço por processo em Network, API Python initialize/status/shutdown e bombeamento no
  NextFrame; StopEngine libera após destruir componentes. Nenhum script do RolimaRacer alterado.
- Builds Windows/MSVC de complemento, RangeEngine e RangeRuntime passaram. CTest da rede PASS.
  Smoke test no player headless: API, uint64, callbacks, duplicação e limpeza PASS; DLL real
  carregou e reportou `Steam client is not running`. Init online não validado, Steam fechada.
- Diagnóstico do erro Windows 126: dependência CRT inicial removida com CRT estático;
  a falha persistiu até normalizar separadores de caminho para busca DLL_LOAD_DIR. Provas
  isoladas WinDLL com caminho nativo carregaram; reteste no player passou depois do fix.
- [Guia local](steam-complement-development.md) e script `tools/net_engine_test/steam_runtime_test.py`.
  SDK mantém warnings C4996 nos próprios headers. Sem export/release, transporte ou salas.

## Multiplayer: carregador opcional do complemento, B1 (2026-10-07)

- ABI C v1 e carregador RAII em Network, sem SDK Steam: caminho absoluto, busca Windows
  restrita ao diretório da DLL/System32, validação de tabela e limpeza de contexto/biblioteca.
- Quatro DLLs de prova testam ciclo de vida, identidade uint64, falha/retry de init,
  recarga, versões/tamanhos incompatíveis e ponteiro ausente. Não são complemento Steam real.
- Builds MSVC `build-net/net_tests` e `build/ge_network` passaram. CTest da rede passou.
  Sem API Python ou ligação do serviço ao runtime; próximos passos na etapa B2.

## Multiplayer: inventário inicial do complemento Steam (2026-10-07)

- Consulta bpy no RolimaRacer.range pelo editor de build/bin, sem salvar: SteamComponent,
  NetworkManager, NetworkMenu e quatro NetworkVehicleSync confirmados; processo saiu com c?digo 0.
- SDK 1.55 local encontrado, incluindo lanes; AppID de desenvolvimento ? 480, comercial pendente.
- [Decis?o proposta](steam-multiplayer-inventory.md): pacote reutiliz?vel da engine, complemento
  opcional por ABI C, ?nico dono do runtime e canais compat?veis com a sess?o atual.
- Pr?xima pe?a isolada: carregador e DLL de prova antes da integra??o SDK. N?o houve mudan?a C++
  nem gameplay; exportador efetivo e distribui??o do complemento ainda precisam ser fechados.

## Multiplayer: plano do complemento Steam (2026-10-07)

- Criado [plano do complemento Steam](steam-multiplayer-plan.md), com salas/convites Steamworks e
  adaptador opcional para o transporte da rede nativa. Componente e menu reutilizáveis devem ser
  distribuídos pela engine; RolimaRacer mantém configuração e regras da corrida.
- Etapas incluem inicialização única, contrato de canais/identidade, prova de relay em duas redes,
  integração de sessão, corrida real e distribuição. Não implementado; nenhum C++ ou jogo alterado.
- Fontes oficiais Steamworks consultadas; SDK/AppID e forma de distribuição precisam ser conferidos
  no inventário inicial. Engine padrão continua independente da biblioteca Steam.

## Sombra: atualização automática para Spot/Point (2026-10-07)

- Nova opção por lâmpada **Auto Update** (Spot/Point, painel de sombra; `LA_AUTO_SHADOW`, RNA
  `use_auto_shadow_update`, Python `light.autoShadowUpdate`), desligada por padrão. Com ela, a sombra só é
  redesenhada quando a lâmpada (transform, distância, cone, clip, bias, layer) ou algum objeto dentro da distância
  dela mudou, entrou ou saiu; objetos com deformador (armature/shape keys) contam sempre como movidos.
  Comparação no snapshot de bounds das passadas de sombra (`KX_Scene::GetShadowCullSnapshot`) em
  `KX_ShadowRenderer.cpp` (`AutoShadowStillValid`); `updateShadow()` e mudança na lista de casters forçam
  o redesenho. Limitação: movimento só por shader de vértice (vento/grama) não é detectado; deixe Auto desligado
  nessas lâmpadas. Etapa 1 do plano de otimização de luzes (etapas 2-3 sem GLSL; 4-5 dependem dos shaders).
- Teste `tools/create_auto_shadow_test.py` (`projects-teste/auto_shadow/`): 8 Points com sombra, 441 cubos,
  um cubo girando perto de 2 lâmpadas. Auto desligado: 48 passadas/8 lâmpadas por frame; ligado: 12/2.
  FPS travado em 60 nos dois (RX 6800M), então o ganho de tempo ainda não foi medido; falta a checagem visual
  do usuário (sombra acompanhando o cubo, sem sombra congelada).

## Demos de nós: cópias revisadas com frames e controles robustos (2026-10-07)

- Revisadas as 11 receitas da lista do usuário, com cópias `_revisado.range` em
  [`demos/revisados/`](../demos/revisados/README.md). Originais `.range` e geradores preservados.
  `tools/review_recipe_nodes.py` abre os assets existentes e organiza materiais, World, lâmpadas e
  grupos em frames por etapa, com notas separadas e colunas por dependência. Parentes são atribuídos
  antes das posições, evitando deslocamentos relativos da API 2.79; nós altos têm espaço reservado.
- Dissolve: extremos exatos (q <= 0 inteiro, q >= 1 invisível), brasa limitada à parte visível e
  largura única ligada à faixa e ao gradiente. Neve/musgo: extremos exatos de Amount, independentemente
  de ruído/suavidade; ruído em Object acompanha o objeto, normal do mundo mantém orientação da cobertura.
- Água: espuma acompanha Bump das ondas; materiais da costa usam Geometry Position para a altura do
  mundo. Triplanar: Bump discreto pela luminância (aproximação desligável por Strength = 0).
  Interior Mapping: dimensões limitadas a 0.001 nos divisores; limites nas entradas do grupo.
  Escudo, lava e shaders de vértice de vento/grama/pelos mantêm a lógica original; frames indicam
  o texto GLSL correspondente. Nenhuma mudança em C++ ou no build.
- Toon: a primeira rodada do player avisou que o material de contorno não tinha vértices/primitivas.
  O casco Solidify ainda estava no modificador, mas o conversor usa a malha base (`CDDM_from_mesh`).
  Aplicado somente o modificador Contorno na cópia, preservando espessura, normais invertidas e slot
  de material; o gerador verifica que as faces do contorno existem. As faixas de iluminação não mudam.
- `python tools/validate_recipe_nodes.py`: **11/11 PASS** no player atual de `build/bin/` (RX 6800M),
  cada cópia temporária executando 120 ticks de lógica e encerrando, sem erros de shader/Python detectados.
  Testes percorrem conexões Math reais para os extremos, verificam limites dos frames e comprovam por
  SHA-256 a preservação dos originais. Os assets entregues não encerram automaticamente; logs e cópias
  de teste ficam em TEMP. A primeira execução do gerador expôs uma falha no avaliador de testes
  (override de quantidade no nó Math de Time); corrigido antes da validação completa.
- Validação visual da qualidade dos efeitos e do layout permanece para o usuário no editor/jogo real;
  não foi usada captura automatizada. `check_docs.py` antes da atualização: 54 erros/4 avisos já existentes
  nos mapas/referências, relacionados a linhas de código fora desta revisão.

## Tesla Piano: acentos de partículas GPU (2026-10-07)

- `tools/add_tesla_gpu_effects.py` adiciona 11 emissores nativos, com pool total de 348 partículas:
  oito Sparkle azulados nos toros (32 cada), carga sutil na bola central (20) e dois Smoke baixos
  nas laterais (36 cada). Sem texturas externas, shaders novos ou alterações em C++.
- Controlador musical aciona o emissor correspondente por 0.45 s; espaço aciona todos por 0.75 s.
  A opacidade cai nos últimos 0.2 s antes de desligar. Névoa e carga central são ambientes contínuos.
- Atualizada `TeslaPiano_Cinematic.range`, preservando backup `TeslaPiano_Cinematic_before_gpu_effects.range`.
  Sonda no runtime passou: acionamentos reais de nota/espaço, emissores ativos, redução temporizada
  e desligamento (`debug-logs/tesla-gpu-result.txt`). `check_docs.py`: mesmos 35 erros/23 avisos anteriores.
  Aparência e desempenho precisam ser avaliados pelo usuário no jogo real.

## Tesla Piano: UV do fundo e tremor reduzido (2026-10-07)

- Fundo preto diagnosticado na cena salva: plano `Anastacio_Fundo_Industrial` sem qualquer UV.
  A cena já usava Game PBR, no qual Image Texture/Emission são suportados. Corrigido com UV
  completo 0..1 e nó UV Map ligado explicitamente à imagem; textura convencional adicional
  disponível para fallback legado. A autoria usa `uv_textures.new` da API 2.79.
- Amplitude do tremor 0.045 → 0.012, frequência 18 → 14 Hz, decay 0.65 → 0.85/s, roll desligado;
  impulso por nota 0.24 → 0.18 e espaço 1 → 0.85. Fator do blur associado 0.75 → 0.35.
- `tools/fix_tesla_background_shake.py` atualiza a cena com backup separado; corrigida também a
  criação de UV em `tools/upgrade_tesla_atmosphere.py`. Gravação e verificações de UV/nós/amplitude
  bem-sucedidas no editor. Validação visual do fundo deve ser feita pelo usuário no jogo real.

## Tesla Piano: foco central e Camera FX (2026-10-07)

- `tools/configure_tesla_camera_fx.py` configura a câmera de `TeslaPiano_Cinematic.range`
  com foco Object no `Terminal` (bola central), faixa nítida de 8 m, suavização de 0.2 s,
  DOF Medium com blur de 3.5 px e diafragma de seis lâminas.
- Speed Blur e Directional Blur ligados com forças moderadas e Protect Focus; Cat Eye Bokeh
  suave e vinheta de 0.12. O Speed Blur acompanha trauma² via `speedOverride`, pois o tremor
  por lens shift não translada a câmera. Sem trauma, o override volta a zero.
- Cena atualizada com backup `TeslaPiano_Cinematic_before_camera_fx.range`. Sonda separada
  no runtime confirmou foco válido no Terminal, efeitos ligados, blur seguindo o impacto
  e voltando a zero, além da inicialização musical (`debug-logs/tesla-focus-result.txt`: PASS).
  Avaliação visual permanece no jogo real pelo usuário.

## Tesla Piano: tremor musical e fundo industrial (2026-10-07)

- `tools/upgrade_tesla_atmosphere.py` aplica o tremor existente de `KX_Camera` ao controlador
  musical: cada nota chama `shake(0.24)` e espaço chama `shake(1.0)`. O trauma nativo acumula,
  limita em 1 e decai a 0.65/s; amplitude 0.045, frequência 18 Hz e roll ligado no Camera Game FX.
- Gerada paisagem industrial noturna com imagegen integrado, salva em
  `build/bin/demos/TeslaPiano/textures/tesla_background.png` e empacotada na cena. Plano de fundo
  emissivo, alinhado à câmera, sem colisão e com margem para tremor.
- Entrega em `build/bin/demos/TeslaPiano/TeslaPiano_Cinematic.range`, preservando as versões
  original e PBR. Execução no editor e teste no runtime bem-sucedidos; sonda separada confirmou
  inicialização do piano, impulso isolado, acumulação rápida, redução até zero e impacto forte.
  Resultado em `debug-logs/tesla-shake-result.txt`. Aparência/enquadramento e sensação do tremor
  aguardam avaliação do usuário no jogo real; nenhuma captura automática usada como prova visual.

## Tesla Piano: materiais procedurais PBR (2026-10-07)

- `tools/upgrade_tesla_materials.py` transforma uma cena existente sem recriar sua lógica e grava
  uma cópia irmã `TeslaPiano_PBR.range`. Aplicado a 35 objetos da demo em `build/bin/demos/TeslaPiano/`.
- Nós editáveis: cobre com espiras horizontais, aço com microtextura, bases grafite, concreto com
  variação de cor/relevo e máscara procedural de rugosidade molhada, terminal e teclas emissivos.
  Game Shading Nodes ligado; luz Hemi convertida em Sun, compatível com Game PBR.
- Build `RangeEngine` bem-sucedido com `vcvars64.bat` e `VSLANG=1033`; execução do script e gravação
  bem-sucedidas. Runtime manteve-se aberto no teste de inicialização; validação visual e musical
  no jogo real pendente. A geometria/cenário da referência artística não foi recriada.
- `check_docs.py` encontra 35 erros e 23 avisos preexistentes, sobretudo linhas dos mapas de código
  alteradas por trabalho paralelo; nenhum mapa foi reescrito nesta tarefa.

## Chuva: poças d'água (2026-10-07)

- Weather > Rain > Puddles (`WO_WEATHER_RAIN_PUDDLES`, bit 11). Campos novos no DNA: `rain_puddle_amount`,
  `_size`, `_darkness`, `_reflection`, `_distance`, `_min_up` (versioning dá os padrões 0.5/4/0.4/0.8/40/0.9).
- No filtro de chuva (jogo e viewport): ruído em XY do mundo nas superfícies viradas para cima; borda
  molhada escura, água refletindo a cor horizonte/zênite do World com fresnel, e a normal dos Ripples
  distorce o reflexo. Profundidade/normal agora calculadas uma vez para poças e ripples.
- Game property `puddles_effect` com a mesma regra dos outros efeitos (bit 4 de `KX_RainSurfaceMask`).
- Com Intensity 0 o filtro continua desenhando as poças (secam pelo Amount). `setWeather`: `puddles`,
  `puddle_amount`, `puddle_size`, `puddle_darkness`, `puddle_reflection`, `puddle_distance`, `puddle_min_up`.
- Ripples + Puddles: o fresnel usa a água plana e a refração dos ripples dentro da poça foi reduzida,
  para os anéis não ficarem azuis demais.
- Screen Space Reflection opcional (`WO_WEATHER_RAIN_PUDDLE_SSR`, bit 12; `setWeather('puddle_ssr')`): 32 passos
  em world space contra o depth, refino por bisseção, cai no céu onde o raio sai da tela ou passa atrás de objeto.
- Only in Puddles em Ripples (bit 13) e Splash (bit 14), `ripple_puddle_only`/`splash_puddle_only`: o efeito só
  aparece na água da poça e liga o Puddles junto. As duas podem ficar ligadas: vão em `Puddle1.x = 1 + 1 + 2`.
- Revisão: `fwidth` da borda das poças saiu de dentro do branch por pixel (derivada indefinida em fluxo
  não uniforme) e `setWeather('puddle_ssr')` ganhou o setter que faltava.

## Chuva: Ripples/Splash/Aura por propriedade, ajustes iguais e raios laterais (2026-10-07)

- UI do Weather > Rain: checkbox Droplets no topo; Ripples e Splash com a mesma lista e ordem
  (Intensity, Size, Rate, Normal, Distance, Upward Surface). Campos novos no DNA: `rain_ripple_size`,
  `rain_ripple_rate`, `rain_splash_normal`, `rain_splash_min_up` (antes fixos no shader: 1, 0.8, 1, 0.7);
  viewport e engine usam os mesmos valores.
- Game properties `ripples_effect`/`splash_effect`: se algum objeto tiver, só ele recebe o efeito; sem
  nenhum, continua em toda superfície. `KX_RainSurfaceMask` desenha os objetos marcados numa textura RG32F
  (bits + profundidade de vista) e o filtro de chuva compara com a profundidade da cena. Não segue
  armature/shape key. Só no jogo (a viewport mostra em tudo).
- Aura: propriedade padrão `aura_chuva` → `aura_rain_effect` (versioning renomeia no World e nos objetos);
  sem objeto marcado, todo objeto com malha dentro de Distance recebe a aura.
- Lightning > Sideways Bolts (`WO_WEATHER_RAIN_LIGHTNING_SIDE`): metade dos raios corre na horizontal
  entre nuvens. `setWeather`: `ripple_size`, `ripple_rate`, `splash_normal`, `splash_min_up`, `lightning_side`.
- Otimizações: a máscara pula objetos fora da câmera ou além da Distance (pela esfera do AABB) e não
  redesenha quando câmera/objetos não mudaram; Aura mede a Distance pelo AABB (não pela origem) e, sem
  objeto marcado, usa só os 32 mais próximos; splash rejeita pela máscara antes de reconstruir
  profundidade/normal. Corrigido teste de bit da máscara (objeto com as duas propriedades perdia o splash).

## Sombra com materiais Clip / código de vértice corrigida + demo de pelos (2026-10-07)

- Materiais que fazem a sombra com o próprio shader (Clip, alpha-to-coverage e, desde 2026-10-06, opacos
  com código de vértice) deixavam a cena inteira "na sombra" e travavam a GPU (~60 ms). Na passada de
  sombra o material ligava como sampler a textura de profundidade da lâmpada que era o próprio alvo
  (feedback) e recalculava luzes/matrizes compartilhadas da lâmpada com a vista dela. Agora, com
  `GetShadowMode() != RAS_SHADOW_NONE` (`GetDrawingMode()` não marca a passada de sombra): sem
  `ProcessLighting`/`UpdateLights` e sem lâmpadas ligadas (unidades de textura de sombra esvaziadas).
  Objetos com esses materiais passam também a receber sombra corretamente (a grama da demo de vento
  ficou mais escura por isso).
- Código de vértice do usuário: `UV`, `ORCO`, `TANGENT` e `COLOR` eram globais inicializadas com
  atributo (inválido no GLSL atual: o shader não compilava e o material ficava branco); viram `#define`.
- `tools/create_fur_test.py` → `demos/pelos.range`: pelo em 40 cascas no vertex shader
  (`pelos_vertex.glsl`, `#define` ajustáveis), fios afinando, gravidade e vento, xadrez e malhado; ~42 FPS
  com duas Suzannes e sombra na RX 6800M.

## Efeitos de câmera não recompilam mais ao ligar/desligar (2026-10-07)

- `KX_2DFilterManager::UpdateCameraFX` removia os passes `FILTERPASS_CAMERA_DOF`/`FILTERPASS_CAMERA_LENS`
  quando o efeito desligava e recriava (compilando o shader) quando voltava. No RolimaRacer isso
  acontecia a cada nitro e a cada troca de câmera, com travada visível.
- Agora o passe é criado uma vez e só alterna `SetEnabled`; desligado, o `RAS_2DFilter::Render` já
  devolve a entrada sem desenhar.

## Coleção "fora do jogo" deixava a layer 20 ligada (2026-10-07)

- Marcar uma coleção do outliner como "fora do jogo" liga a layer 20 da cena (para os objetos movidos
  continuarem visíveis), mas religá-la não desligava. Sem nenhuma coleção excluída, o conversor deixa de
  ignorar a layer 20, e tudo que mora nela (no RolimaRacer, o molde `group_Cameras` da Pista_1) entrava
  ativo no jogo: um segundo rig de câmera parado longe do carro. `outliner_collection_game_exclude_set()`
  agora desliga a layer 20 quando a última coleção excluída volta ao jogo. Arquivos já salvos com a layer
  presa precisam desligar a layer 20 da cena uma vez (ou excluir e religar uma coleção).
