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

### Fase 4: iluminação e geometria (CONCLUÍDA 2026-11-20: Probe GI, sombra colorida, Baked, impostor, HLOD; paridade visual aguarda aceite)
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
