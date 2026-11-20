# Plano: prévia visual completa na 3D View

Objetivo: a 3D View mostrar o resultado visual de todos os recursos da engine sem o usuário apertar P ou Standalone. Só visual; física e lógica ficam fora.

Estado: levantamento de 2026-11-18 por leitura de código, revisado pelo Codex no mesmo dia (também leitura estática). Nada implementado e nada comparado em imagem. "Há caminho de código" não prova paridade visual com o jogo.

## Premissa: dois pipelines separados

A viewport usa o compositor `GPUFX` do módulo `gpu` (`gpu_compositing.c`: `GPU_fx_compositor_initialize_passes` na linha 490, `GPU_fx_do_composite_pass` na 1253). O jogo usa `RAS_2DFilterManager`/`KX_2DFilterManager` no `gameengine`. São códigos distintos, e o `gpu` não pode depender do `gameengine`. Por isso a Fase 0 é uma **prova de integração**, não um registro genérico.

## Fase 0: prova com um passe estático

1. Escolher um efeito de tela de passe único e estático: aberração cromática.
2. Pôr a fonte do shader e o contrato de entradas num local comum aos dois builds, com integração `datatoc`.
3. Escrever dois adaptadores finos: um para o `GPUFX` e outro para o jogo, cada um respeitando a ordem e o espaço de cor do seu pipeline.
4. Comparar as duas saídas em cena controlada (liga/desliga, redimensionar a janela, câmera ativa x visão livre).
5. Só então extrair o registro mínimo que a experiência justificar: nome, flag de toggle, classe de custo, dependências. O registro descreve; a implementação, a aquisição de dados e a execução continuam por conta de cada recurso. Não vale a promessa "uma linha por recurso".

UI: menu/popover "Live Preview" na 3D View, com um toggle por grupo e preset Off / Leve / Completo; generaliza `editor_render_flag` e `weather_editor_hide`. Migrar as flags atuais sem mudar o que o usuário vê hoje.

## Temporal

- Partir do histórico de nuvens que já existe no `GPUFX` (`gpu_compositing.c` linhas 310 e 1715). Não existe histórico universal: cada efeito precisa de cor, profundidade, resolução, jitter e validade próprios.
- Definir invalidação: corte de câmera, resize, mudança de projeção, mudança de parâmetro, reabertura da região, perda de contexto, várias viewports e estéreo.
- Redesenho: sem redesenho contínuo quando nada evolui; efeitos convergentes (TAA, SSGI) param quando estabilizam. Base: `ED_view3d_realtime_viewport_update` (`space_view3d.c` ~1433).

## Estado atual da viewport (conferido)

Já mostra, sujeito a flags, shading Solid ou superior e limites: Bloom, Tonemap, Light Scatter, SSR, SSAO, FXAA, Lens Flare (do World), Chuva, Nuvens, Sky Layers, Fog Volumétrico, Film Grain, CSM/PCSS, shaders por nós, DOF antigo em visão de câmera, **lightmaps** (Principled/GLSL via `node_shader_gpu_lightmap`, `node_shader_bsdf_principled.c:94`, `node_shader_util.c:376`) e a mesh de LOD (`drawobject.c:4538`).

## Lista de recursos faltantes, por fase

### Fase 1: passes de tela estáticos
| Recurso | Observação |
|---|---|
| Aberração cromática, vinheta, Fisheye (`FILTERPASS_CAMERA_LENS`) | Começam pela prova da Fase 0. |
| Compositor de nós (`FILTERPASS_COMPOSITOR`) | Só o subconjunto de nós que o jogo suporta; extrair/expor o compilador de estágios de `KX_2DFilterManager.cpp:589`; invalidar quando a árvore muda. |
| Custom 2D Filters e Smart 2D Filter | Só filtros declarados na cena. Uniforms e Python dinâmicos ficam fora. |

### Fase 2: DOF do jogo
Bokeh do jogo (`FILTERPASS_CAMERA_DOF`, `_REDUCE`), com Cat Eye (parâmetro do DOF, não do Lens). Definir foco Object/Property/Auto sem `KX_Camera` e o comportamento fora da visão de câmera. Manter o DOF legado (`BKE_camera_to_gpu_dof`) como opção até haver comparação.

### Fase 3: temporal
Directional Blur (matriz anterior + profundidade) valida a infraestrutura; depois Speed Blur (precisa da velocidade da câmera), TAA/TAAU (define resolução interna e escala) e SSGI (`KX_2DFilterManager.cpp:410`). Cada um tem entradas e alvos próprios.

### Fase 4: iluminação e geometria
| Recurso | Observação |
|---|---|
| Light Probe Volume | Provavelmente ausente (pendente de teste visual). Distinguir a grade de sondas do jogo (`KX_ProbeVolume.cpp`) do baked light volume, que já tem caminho no material. |
| Sombra colorida | Provavelmente ausente (pendente de teste visual): a chamada está em `RAS_OpenGLLight.cpp:404`, sem equivalente em `view3d_draw_shadows.c`. Exige renderizar e vincular o mapa colorido. |
| Baked Lighting | Já tem caminho; testar paridade e limites (UV Lightmap, atlas, modos). |
| Impostor e HLOD | A mesh LOD já aparece; faltam orientação do impostor, célula do atlas (`KX_GameObject.cpp:1597`) e HLOD. Testar por variante. |

### Fase 5: partículas do jogo
`RangeGPUParticleSettings`, flipbook, fumaça/fogo/light_flicker. Estado e buffers nascem em `KX_GameObject.cpp:888` e são desenhados em `KX_RenderPipeline.cpp:1149`. A prévia precisa de simulação, relógio, emissão, profundidade, transparência e descarte; instanciar só o `RAS_ParticleBuffer` não basta.

### Fase 6: UI e mídia
UI Tree (HUD), Text Boxes com o atlas do jogo, Video Player, Minimap.

### Dependem de decisão de produto
- **Light Flash:** é o pulso da destruição (`KX_DestructionManager.cpp:1333`); precisa de um gatilho de prévia e de simulação temporal, o que toca o limite "sem lógica".
- Lens Flare como objeto: sem evidência de ser um recurso separado do Lens Flare do World, que já aparece. Conferir antes de listar.

### Fora do escopo
Chuva com velocidade (depende do movimento), animações/NLA do jogo, Cutscene, ragdoll, World Sound, multiplayer.

## Ordem

Inventário e matriz de suporte → Fase 0 → Fase 1 → Fase 2 → Fase 3 → Fase 4 → Fase 5 → Fase 6.

## Riscos e regras

- **Conflito de regra:** "não mudar o shading dos meshes na viewport" (`project_viewport_fidelidade`) não cobre sondas e sombra colorida, que alteram a iluminação dos materiais. Decidir antes da Fase 4 se há extensão controlada ou se ficam fora.
- **Equivalência de câmera:** visão livre, câmera ativa, ortográfica, camadas, resolução e aspect ratio dão resultados diferentes. Cada recurso declara suas entradas e o que é aproximado.
- **Ferramentas do editor:** testar overlays, seleção, profundidade, transparência, X-ray, pintura, offscreen e várias regiões. A cadeia atual trata X-ray e pula trabalho durante pintura.
- **Ordem e cor:** comparar ordem de passes, HDR/LDR, tonemap, alpha e profundidade entre `GPUFX` e jogo antes de dizer que é o mesmo efeito.
- **Desempenho e compatibilidade:** limite de memória por região, recompilação de shaders, capacidades GL e fallback Web/GLES (ramo `__EMSCRIPTEN__` para API de SO ou threads). Tudo desligado por padrão.
- **Medição:** rodadas de ~10 s, em cenas geradas por script.
- **Aceite:** testes automáticos cobrem ativação, desativação, resize e estabilidade; a paridade visual só é aceita com o usuário vendo o jogo e a viewport lado a lado.

## Para incluir outros recursos depois

Acrescentar na fase certa: nome, fonte no jogo, o que a viewport não mostra, custo, se é temporal e que dados de runtime precisa.

## Notas de execução

### Item 1: Baked Lighting (Fase 4)
**O que se achou (leitura de código, sem build):** o material é o mesmo nos dois lados. `node_shader_gpu_lightmap` (`node_shader_util.c:376`) e `lightmap_sample` (`gpu_shader_material.glsl:5501`) servem viewport e jogo; as props `ae_lightmap`/`ae_lightmap_use`/`ae_lightmap_mode` e o `update_tag` dos materiais (`anastacio_lightmap.py`) recompilam os dois. A divergência real estava na UV: o jogo pula o atributo "Lightmap" quando o mesh não tem a camada (`BL_BlenderShader.cpp:140`, o shader lê 0,0 = texel vazio e o objeto fica com a luz ambiente), enquanto a viewport (`cdDM_drawMappedFacesGLSL`) deixava o atributo sem array e com o valor genérico que o desenho anterior deixou, isto é, indefinido.
**Feito:** o atributo sem camada recebe `glVertexAttrib2f(idx, 0, 0)` antes de desenhar (`cdderivedmesh.c`, laço final de `cdDM_drawMappedFacesGLSL`). Teste novo `casos/editor_previa_baked_lighting.py` (atlas RGBM por script, plano com e sem UV Lightmap, liga/desliga `ae_lightmap_use`).
**Diferenças conhecidas e não mexidas:** (1) mipmap/anisotropia do atlas: o jogo aplica o da cena (`RAS_Rasterizer::SetMipmapping`), a viewport o das preferências (estado global de `gpu_draw.c`); (2) em Edit Mode o mesh não manda a UV (`is_editmesh`), sem lightmap; (3) objeto sem material (`totcol == 0`) usa `defmaterial` na viewport.
**Conferir no build/teste:** compilar `blenkernel`; rodar `rodar.py editor_previa_baked_lighting`; ver no editor um objeto sem UV Lightmap ao lado de um com; checar se o `glVertexAttrib2f` no índice 0 não gera vértice (fora de glBegin só define o valor corrente).
**Dúvidas:** o teste assume que `uv_textures.new('Lightmap')` produz UV 0..1 por face no plano; se a cor sair invertida, é o atlas, não o código.

### Item 2: Impostor e HLOD (Fase 4)
**O que se achou (leitura de código):** a mesh do nível já aparecia, mas a seleção do nível divergia do jogo (`KX_LodManager::GetLevel`, `KX_GameObject::UpdateLod`): a viewport (`lod_level_select`) media sempre do `obmat` do objeto, sem o fator de LOD (câmera × objeto), sem a origem do HLOD (o `source` de um nível invisível, que o `anastacio_hlod.py` usa para o original medir a distância a partir do proxy), sem histerese e sem descartar os níveis que o jogo descarta (sem malha-fonte e não invisíveis). Billboard e célula do atlas não existiam na viewport.
**Feito:**
- `object.c`: `lod_level_select` reescrito igual ao jogo (níveis inválidos pulados, origem HLOD, fator câmera × objeto, histerese da cena/do nível); novas `BKE_object_lod_update_ex` (com cena e fator da câmera; `BKE_object_lod_update` virou atalho) e `BKE_object_lod_impostor` (matriz de giro em Z como o jogo: +Y local para a câmera, escala preservada; célula do atlas por `heading/2π` arredondando para o vizinho mais próximo).
- `view3d_draw.c`: `view3d_lod_camera_factor` (câmera da vista de câmera, senão a da cena, `Camera.lod_factor`) nos dois pontos que atualizam LOD (cena e dupli).
- `drawobject.c`: `draw_object` agora envolve `draw_object_profiled` (o antigo corpo): com nível Billboard troca `ob->obmat` pela matriz girada só durante o desenho e, com atlas, liga a transformação de UV.
- `DerivedMesh.c`/`cdderivedmesh.c`: `DM_draw_uv_transform_set/clear/get`; o laço que enche o VBO de UVs de `cdDM_drawMappedFacesGLSL` aplica `uv * escala + offset` (equivale ao `KX_ImpostorAtlasDeformer::SetAtlasCell`).
- Teste `casos/editor_previa_impostor_hlod.py`: atlas 2x1 vista de +Y e de -Y, billboard de +X, HLOD com original perto da câmera.
**Fora do que foi feito:** o HLOD em si (troca proxy/original) já funciona só pela regra de distância; não há mais nada específico dele na viewport. Sombra e passes de profundidade do impostor continuam com a matriz normal (só o desenho principal gira). O caso do esqueleto/ragdoll (centro dos bounds deformados em `UpdateLod`) e `lodLevelMax`/`ShowLodLevel` (Python) não se aplicam à prévia.
**Conferir no build/teste:** mexi em `BKE_object.h` e `BKE_DerivedMesh.h` (headers, não DNA): se aparecer crash estranho, `ninja -t clean` conforme o AGENTS.md. Rodar `rodar.py editor_previa_impostor_hlod`. Ver à mão: orbitar a câmera em volta de uma árvore com impostor com atlas (a célula deve trocar como no jogo); LOD sem Billboard continua igual.
**Dúvidas:** a UV do atlas é aplicada a todas as camadas UV do mesh do impostor (o jogo mexe na UV de índice 0); para o quad do gerador de impostor dá o mesmo resultado. O teste assume que o jogo escolhe a célula 0 em +Y e a 1 em -Y (conta feita à mão em `UpdateLod`); se o jogo ler o contrário, o teste acusa no próprio jogo.

### Item 3a: Partículas do jogo (Fase 5)
**Decisão de desenho:** em vez de reescrever a simulação em C (como a chuva em `view3d_rain.c`), a prévia usa o próprio `RAS_ParticleBuffer` do jogo (transform feedback, looks de fumaça/fogo, flipbook, curvas, colisão, vórtice, burst, prewarm), então a fidelidade vem do mesmo código. O editor já liga `gameengine` (`KX_CompositorBuildPreviewStages` é chamada de `view3d_draw.c`).
**Feito:**
- `gameengine/BlenderRoutines/BL_PreviewParticles.{h,cpp}` (novos, no CMake de `ge_blender_routines`): interface C `BL_preview_particles_draw(scene, layers, viewmat, winmat)` e `BL_preview_particles_free()`. Um mapa `Object* -> buffers` (principal e Mix); recria o buffer quando os bytes de `gpu_particles`/`gpu_particles_mix` ou as flags mudam; passo da simulação = tempo real desde a última chamada (limitado a 0,1 s; segunda viewport no mesmo frame não passa o passo duas vezes); descarta buffers de emissores removidos. A montagem espelha `KX_GameObject::SetupGPUParticlesBuffer/ApplyGPUParticleParams/UpdateParticles` (manter em sincronia).
- `view3d_draw.c`: `view3d_draw_game_particles` (depois do transparente, junto da chuva, antes do X-ray); só em shading Solid+ e com o **Realtime** da viewport ligado (o Realtime já é o dono do timer de redesenho; sem ele nada anima, e fica tudo desligado por padrão); `BL_preview_particles_free` em `ED_view3d_shaders_free`.
- `space_view3d.c`: o timer do Realtime passa de 0,1 s para 1/30 s quando a cena tem emissor GPU (recria o timer se o passo muda).
- Teste `casos/editor_previa_particulas.py` (fração de pixels amarelos no jogo × prévia com/sem Realtime).
**Não coberto:** partículas "soft" (fade contra a geometria: precisa da profundidade da cena, passo 0 hoje); colisão por profundidade da tela (`use_gpu_particle_collider`); propriedade de jogo `GPU_Particles_Enabled` e o `burst()` por Python (lógica, fora do escopo); emissor culled pela câmera (a viewport simula todos); editar a curva de tamanho/cor não recria o buffer (só mudar outro campo ou reabrir). Explosão por partículas (`KX_ParticleBlast`) e Light Flash dependem de gatilho e ficam fora.
**Conferir no build/teste:** compilar `ge_blender_routines` (novo .cpp: includes de `RAS_ParticleBuffer.h`, `KX_Globals.h`, `PIL_time.h`) e o link do editor com `BL_preview_particles_*`; `RangeEngine` completo. Em runtime: GL do editor aceita transform feedback e VAO (é o mesmo contexto do jogo embutido, mas não foi visto); o `glUseProgram(0)` no fim de `Draw` não deve quebrar o desenho seguinte (X-ray, overlays); `KX_SetMainPath` é chamado todo frame com `G.main->name` (mesmo valor que o launcher usa). Rodar `rodar.py editor_previa_particulas`.
**Dúvidas:** o `PreviewEmitter` fica em `std::map<Object*,...>` — um objeto apagado cujo ponteiro é reaproveitado por outro dentro do mesmo frame seria tratado como o mesmo emissor (a comparação por bytes das settings recria o buffer na prática). Gravar de verdade o tempo do jogo (relógio com pausa) não foi feito: pausar o Realtime pausa só o redesenho.

### Item 3b: UI e mídia (Fase 6)
**UI Tree (HUD) e Minimap: feito.** O desenho dos widgets já é um módulo comum ao editor e ao jogo (`range_ui_draw`), então a prévia na 3D View só precisou de colocação e de um gatilho, em Python (sem C++).
- `startup/range_ui_tree.py`: `_draw_hud_preview` (handler `POST_PIXEL` da `SpaceView3D`), `_camera_frame_rect` (quadro da câmera projetado em pixels da região com `location_3d_to_region_2d` sobre `Camera.view_frame`, vale para perspectiva e ortográfica), `_hud_preview_nodes` (mesma ordem de desenho do runtime: Panel/Image/Minimap ao fundo, depois widgets, depois botões). Cada nó é posicionado com o mesmo retângulo normalizado do bake e `range_ui_draw.place` (Stretch/Keep Aspect e âncora iguais ao jogo), recortado pelo quadro da câmera. Só desenha em cena Game, em vista de câmera, para as Screens HUD sem `ui_camera` ou com a câmera da vista. O desenho de um nó foi extraído de `_draw_previews` para `_draw_node_preview`, agora usado também pelo Node Editor (mesmo comportamento).
- Toggle novo `Scene.range_ui_hud_preview` ("Game HUD (UI Tree)"), no popover Overlay logo abaixo de Realtime (`bl_ui/space_view3d.py`), **desligado por padrão**. É propriedade da Cena, não da viewport, porque `SpaceView3D` não aceita propriedades Python nesta engine (sem idprops).
- Valores: os de exemplo do Node Editor (barra a 70%, propriedades 0, marcadores de exemplo no Minimap). O jogo lê propriedades do objeto ao vivo, o que é lógica e fica fora. Texto usa o formato cru, sem tradução por chave (como já era no Node Editor).
- Teste `casos/editor_previa_hud.py` (dois Panels, geometria relativa jogo × prévia, toggle desligado).
**Text Boxes e Video Player: não feitos.** Pedem decisão e teste com GPU, e não valem código às cegas:
- *Text Boxes (atlas do jogo):* a viewport desenha o objeto Text como curva do Blender; o jogo desenha com `KX_FontObject` (blf ou atlas de bitmap) com quebra por palavra, páginas e alinhamento próprios (changelog 2026-10-25). Reproduzir isso na viewport é reimplementar o layout e o desenho do `KX_FontObject` (1,1 mil linhas) ou expor o layout dele ao editor, como o `RAS_ParticleBuffer` acima. Proposta: bridge C em `BlenderRoutines` que roda só a parte de layout (linhas/páginas) e desenha com o mesmo atlas; decidir se a prévia substitui o texto 3D (que o usuário edita) ou se desenha por cima.
- *Video Player:* é um componente Python (`anastacio_video.py`) que alimenta a textura do material pelo VideoTexture do jogo, com som próprio. Na viewport o mínimo viável é um quadro de pôster (primeiro frame) pelo `Image` de filme do Blender, ligando-o ao material só durante o desenho; reprodução contínua e som são lógica. Precisa de decisão de produto (pôster x reprodução) antes de código.
**Conferir no build/teste:** sincronizar `source/release/scripts/startup/range_ui_tree.py` e `bl_ui/space_view3d.py` em `build/bin/2.79/scripts/` (regra do AGENTS.md); não há C++ nesta parte. Rodar `rodar.py editor_previa_hud`. Ver à mão: ligar "Game HUD" com uma UI Tree HUD de exemplo (template HUD do Node Editor) em vista de câmera, com zoom e com a câmera fora do centro; confirmar que o quadro recorta o HUD. Textos novos ("Game HUD (UI Tree)") ainda sem tradução nos catálogos.
**Dúvidas:** `Camera.view_frame(scene=...)` e `location_3d_to_region_2d` em callback `POST_PIXEL` não foram executados aqui (2.79 em Python 3.5); se `view_frame` devolver o quadro em outro plano o retângulo sai errado, e o teste acusa pela geometria. HUD de split screen (`ui_camera` de outra câmera) não é desenhado na prévia.
