# Relatório de melhorias — AnastacioEngine

Resumo curto do que já foi feito e das decisões técnicas em vigor. O que falta fazer está em
[`docs/roadmap.md`](docs/roadmap.md). O detalhe de cada mudança (diagnóstico, medições, testes) está no
[`docs/changelog.md`](docs/changelog.md) e no histórico antigo [`docs/changelog-arquivo.md`](docs/changelog-arquivo.md);
procure por assunto com `grep -n "^## .*termo" docs/changelog*.md`.

## O que é

- Fork da Range Engine 1.6 Rev1, derivada da UPBGE 0.2.5b e do Blender 2.79. Frentes principais: performance,
  iluminação/renderização e ferramentas de jogo.
- Executáveis: editor `AnastacioEngine` e player `AnastacioRuntime` (Windows desde 2026-10-08, Linux desde
  2026-10-14). Os alvos de build continuam `RangeEngine` e `RangeRuntime`. O player aceita o nome antigo nos
  projetos; formatos, APIs e preferências seguem compatíveis.
- Plataformas: Windows, Linux x86_64, Web (WebGL2/WebAssembly) e Android (APK com WebView). iOS fora do escopo.
- Um item só entra no roadmap da engine quando exige mudança em `source/` e recompilação. Configuração de cena,
  assets e scripts soltos ficam no changelog ou na documentação da ferramenta.

## Histórico resumido

### Agosto 2026

- **Performance:** GPU Skinning, Z-prepass para alpha-cutout (GPU 28,3 → 21,5 ms no benchmark), buffer de
  instancing sem realocar, impostor (billboard) de árvore com atlas multiângulo.
- **Render:** migração do player para OpenGL core profile; filtros 2D piloto.
- **Partículas GPU** por transform feedback (fases A–N): presets, blend aditivo, debug ao vivo, toggle `enabled`.
- **Editor:** seletor de estilo de ícones, componentes ImGui organizados.

### Setembro 2026

- **Ketsji (núcleo do jogo), planos 1–11:** contadores e categorias de profiling, testes de regressão, guardas de
  escopo, extração de `KX_ShadowRenderer` e `KX_RenderPipeline`, cache de cascata do CSM, passo fixo opcional
  (Fixed Timestep), limpeza de código morto. Ver [plano](docs/ketsji-engine-modernization-plan.md).
- **Web:** runtime no navegador (render, luzes e sombras PBR, filtros 2D, teclado, mouse, gamepad, save IDBFS,
  áudio MP3/OGG, Python), validador e pré-voo no editor, empacotador, "Abrir no navegador".
- **Android:** APK/AAB com WebView, export pelo editor, release assinado, controles na tela, sensores de movimento.
- **Linux nativo:** editor e player compilando e rodando, pacote portátil feito em container Ubuntu 22.04, Cycles
  com CUDA/OpenCL/Embree, i18n.
- **Cycles:** CUDA na RTX 50, OpenCL na AMD, correções de leitura/escrita e parser IES.
- **Cutscene nativo** (fases 0–2 e 4–5), import/export JSON.
- **LibLoad e External Files:** Groups, Texts, Add Object com bibliotecas.
- **Navmesh:** API moderna do Detour e navmesh dinâmica com obstáculos em runtime.
- **Editor:** barra flutuante na 3D View, Outliner com coleções, Asset Browser, abas Camera/Input/Export Game,
  painéis de material do modo jogo, idiomas (English, Português, Español, Русский), associação de `.blend`/`.range`.
- **Jogo:** Reverb Area, Animation Events, World Status, destruição e explosões, câmera com foco/rastreio/Camera FX,
  chuva/nuvens/lens flare no World, soft body, compatibilidade com scripts BGE/UPBGE, Logic Bricks → Python (fase 1).
- **Releases** 0.3.0 a 0.4.6 (Windows e Linux).

### Outubro 2026

- **Materiais e render:** nós do Cycles no Game PBR (Glass, Hair, volume, IES, Sky, refração), reflection probes,
  sombra Point, nós de shader com estágios vertex/geometry e GLSL Script, reflexo planar, Material Atlas,
  Quick Material, conversão PBR ↔ Classic, Fresnel/Shadows Only, sombra colorida, CSM por câmera ou luz,
  Volumetric Clouds e Sky Layers, fog volumetric, SSGI experimental, Baked Lighting moderno (AO e luz estática).
- **Carregamento:** cache e biblioteca GLSL enxuta, LibLoad assíncrono com progresso, arquivo `.cooked`
  (hull, shaders, malhas, tangentes, BVH), Load Mode por objeto, texturas DDS, preparar áudio, aquecimento de shaders.
- **Performance:** Static Batch (empate com a ThunderPlayer), auditoria de trabalho repetido por frame (~100 itens),
  caches de luz/probe/camada, resolução dinâmica, Range Trace e Performance Report, Scene Doctor.
- **Lógica:** Logic Bricks → Python completo (F1–F12), Logic Bricks 2.0, Highlight Active, Logic Tree (F1–F6),
  Smart Components e Smart Wizard, Smart 2D Filter, UI Tree (menus 2D).
- **Estabilidade de objetos:** autoatribuição segura de LOD, retomada da lógica ao desligar culling,
  proteção de escala singular e correções de referências/conversões nos bindings;
  [validação](docs/revisao-kx-gameobject-python.md).
- **Argumentos Python:** helper comum sem cache compartilhado entre métodos; keywords de parenting
  e troca de mesh independem da ordem de chamada. Editor/player compilados e validados.
  [Revisão e limites](docs/revisao-parser-python.md).
- **Jogo:** multiplayer nativo (ENet + WebSocket, servidor headless, predição, RPC) e complemento Steam no
  Windows, World Sound (Music/Ambient, chuva e trovão), VR no celular, deformação por impacto, ragdoll,
  veículos (controle arcade, Smart Component), idiomas do jogo (`Range.locale`), screencast, Start Asleep.
- **Ferramentas:** Decimate High Quality, RangeArmor com cooking, pacote Universal, relatório de crash sem PDB.
- **Releases** 0.5.0 a 0.5.4.

## Capacidades herdadas que não devem ser reimplementadas

- GPU instancing (`RAS_InstancingBuffer`, `RAS_DisplayArrayBucket::RunInstancingNode`).
- Batching estático (`RAS_BatchDisplayArray`, `RAS_BatchGroup`); a opção Static Batch por objeto usa essa base.
- LOD por distância (`KX_LodManager`, `KX_LodLevel`).
- Frustum culling (`SG_CullingNode`, `KX_CullingHandler`, `SG_Frustum`) e occlusion culling por DBVT do Bullet
  (`use_occlusion_culling` e objetos `Occluder`: é configuração de conteúdo, não falta de C++).
- Principled BSDF/PBR. Não criar outro modelo PBR antes de verificar o que já existe.
- MSAA de ponta a ponta.

## Decisões técnicas vigentes

### Render e materiais

- O player usa OpenGL core profile; o editor fica em compatibility. No core, motion blur legado e texto de debug
  por `BLF_draw` são no-ops. Core profile é decisão de arquitetura, não ganho automático de performance.
- Filtros 2D do jogo e efeitos multipass nativos são pipelines diferentes e se validam separadamente.
- Shaders do usuário seguem pelo editor de nós, com a interface e os conceitos do Blender 5, sem portar código
  dele ([shader-nodes.md](docs/shader-nodes.md)). Sem geometry shader (Web/GLES) o estágio é ignorado.
- Fast Shader Loading (`GAME_FAST_SHADER_LOAD`) fica desligado por padrão: compila muito mais rápido, mas perde
  o constant folding (cena pesada ~60 → 31 fps). Opção por jogo, só no jogo, nunca no viewport.
- GI baked: lightmap RGBM 8 bits num atlas compartilhado + light volume para objetos móveis. A qualidade vem da
  densidade de texels (`ae_lightmap_scale`) e da margem das ilhas, não de uma textura por objeto. Web/Android usam
  no máximo a lightmap. Falha do Cycles interrompe o bake sem publicar atlas novo. Detalhes no
  [plano](docs/baked-lighting-plan.md). O SSGI é complemento em tela, não substitui o bake.
- Uma referência de otimização por cena (`KX_Scene::GetOptimizationReferencePosition()`, hoje a câmera ativa)
  alimenta Activity Culling e o vento da folhagem; fora da `Wind Distance` o vertex shader pula o vento.
- Novas lâmpadas nascem com o preset de sombra para Sun (PCF, 1024 px na cascata Near); dados antigos não mudam.
- Realtime Planar precisa de uma imagem associada, senão não renderiza.

### Carregamento e performance

- Numa cena parada, o trabalho de atualização por frame deve ser ~0; conferir com `getRenderStats()`. Ver
  [batching estático e culling](docs/batching-estatico-e-culling.md) e
  [trabalho repetido](docs/auditoria-trabalho-repetido.md).
- Variáveis para comparar com o comportamento antigo: `RANGE_NO_GLSL_STRIP=1` (biblioteca GLSL inteira),
  `RANGE_NO_LOOPDATA_CACHE=1` (cache de tangentes), `RANGE_NO_IMAGE_PREFETCH=1` (decodificação paralela),
  `RANGE_SHADER_UNIFORM_VALUES=1` (força Fast Shader Loading).
- Tela de loading: LibLoad assíncrono com `status.progress` real e merge de ~8 ms por frame; pré-carregar com os
  objetos em camada inativa e instanciar com `addObject`.
- Dados por objeto não devem ser guardados ingenuamente em malhas compartilhadas durante a conversão Blender → Ketsji.
- Cache de shader em disco (`glProgramBinary`) testado e descartado: o cache do driver já é mais rápido.

### Tempo e lógica

- Por padrão, 1 `Update()` por frame com o catch-up por sleep herdado; com v-sync, `FrameOver()` zera o atraso.
  Fixed Timestep (opcional e sempre ligado no multiplayer) usa o acumulador do Plano 8, sem interpolação no render.
- `import bge` e submódulos são aliases de `Range`; scripts novos usam `Range`. A inicialização restaura em
  `collections` as ABCs antigas e expõe `aud.Factory` como alias de `aud.Sound`.
- `object.particles.enabled` segue a Game Property `GPU_Particles_Enabled`; scripts que precisam persistir o
  estado mudam essa property.
- World Sound fica só com Music e Ambient; efeitos e fala continuam nos objetos (Speaker / Sound actuator).
- Ragdoll é addon + componentes Python; C++ novo só por limitação demonstrada.

### Web e Android

- O port Web usa WebGL2/GLES3 direto; ponteiros de extensão do GLEW não existem no Emscripten.
- No perfil CORE (Web), as luzes do Principled/Diffuse/Glossy chegam por `unflightsource[]` (`GPUSceneLight`), não
  por `gl_LightSource`: mudança no formato de luz atualiza os dois caminhos. `GPU_max_textures()` fica em 28 no Emscripten.
- Reverb Area não tem efeito no Web: o backend SDL não aplica EFX.
- `USE_RNA_RANGE_CHECK` está ativo no Emscripten. Cinco campos DNA viraram `unsigned char` sem mudar o SDNA; não
  alargar o tipo nem reduzir o hardmax para agradar o compilador.
- Android é APK com WebView embutindo o pacote Web; rota nativa (NDK) abandonada em 2026-10-17. A lógica fica em
  `range_web/android.py`. JDK e Android SDK não vêm com a engine. A chave de release fica fora do git e nunca é
  sobrescrita; perder a chave obriga a publicar como outro app. `applicationId` é a identidade do app (mudar perde o save).
- Controles na tela entram como gamepad 0, teclas ou mouse virtual pelo `Module.rangePad`; não criar sistema de
  ações paralelo. O layout é configuração do export Web e o APK herda.

### Build e pacotes

- Mudança em DNA exige clean rebuild ([build-notes.md](docs/build-notes.md)).
- Pacote Linux: FFmpeg desligado (`WITH_CODEC_FFMPEG=OFF`); o `aud` lê áudio pela libsndfile 1.2.2 compilada no
  container (a do apt não lê MP3). `WITH_OPENCOLORIO` ligado com a OCIO 1.1.1 do Ubuntu 22.04.
- RangeArmor gera runtimes Windows/Linux x86_64 (`.zip`/`.tar.xz`), sem alvos 32-bit; campos 32-bit antigos só são lidos.
- O complemento Steam é opcional e separado: a engine comum não depende de Steamworks, e o Web exclui o carregador.

## Fontes relacionadas

- [Roadmap](docs/roadmap.md)
- [Changelog](docs/changelog.md) e [histórico antigo](docs/changelog-arquivo.md)
- [Arquitetura](docs/architecture.md)
- [Guia de manutenção](docs/maintenance-guide.md)
