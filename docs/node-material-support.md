# Suporte dos nós de material por motor

Resumo do que cada nó de shader faz no Game (GLSL), no Cycles e no Blender Render (BI).
O editor de nós mostra o mesmo resultado como selo no cabeçalho do nó
(`node_engine_badge` em `source/blender/editors/space_node/node_draw.c`).

- **Game PBR:** Game com `Scene > Game > Shading Nodes` (`use_shading_nodes`) ligado. Usa os nós do Cycles.
- **Game legado:** Game sem essa opção. Usa os nós do BI.
- Para a cor do World mudar durante o jogo, o material precisa de `use_constant_world = False`.

## Selos

| Selo | Significado |
|---|---|
| sem selo | funciona igual nos caminhos em que aparece |
| `Game` | nó só do jogo; ignorado no Cycles e no BI |
| `BI` | só Blender Render e Game legado |
| `Cycles` | só Cycles e Game PBR |
| `~Game` | aparece só no Game PBR: o nó roda, mas é aproximado |
| ícone de alerta + cabeçalho avermelhado | o motor ativo não suporta o nó |

## Nós aproximados no Game PBR (`~Game`)

| Nó | O que o Game faz |
|---|---|
| Glossy BSDF | brilho GGX das luzes da cena; reflete a textura do World (desfocada pela Roughness) ou, sem ela, a cor do World |
| Toon BSDF | faixas de luz do Toon do Cycles, Component Diffuse e Glossy; cor do World como ambiente |
| Glass BSDF | fresnel entre o reflexo do World e o World desfocado como luz transmitida, com brilho das luzes; não refrata a cena |
| Refraction BSDF | World desfocado como luz transmitida; não refrata a cena |
| Anisotropic BSDF | brilho GGX anisotrópico das luzes (Anisotropy, Rotation e Tangent como no Cycles; sem Tangent ligado, radial no Z do objeto); reflexo do World isotrópico, como o Glossy |
| Translucent, Velvet, Subsurface Scattering | viram Diffuse BSDF |
| Hair BSDF | cor chapada, sem luz |
| Ambient Occlusion | concavidade local da superfície (derivadas de tela), escurece cantos dentro de Distance; não oclui por outros objetos |
| Bevel | devolve a normal sem mudança |
| Light Path | valores fixos de raio de câmera |
| Light Falloff | todas as saídas devolvem Strength |
| Sky Texture (Hosek / Wilkie) | usa o modelo Preetham |

## Nós sem suporte no Game PBR (alerta)

Sem código GLSL; a saída é ignorada ou zero:
Wireframe (precisa de baricêntricas, que o fragment shader não tem), Hair Info, Holdout, IES Texture,
Point Density, Script, Principled Hair BSDF, Volume Absorption, Volume Scatter, Principled Volume.
Nós do BI num material do Game PBR (e do Cycles no Game legado) também entram aqui.
Ao carregar a cena, o jogo escreve um warning por material com esses nós
(`material "X": nodes not supported in the game ...`), visível no console do jogo e no log.
Teste de regressão: `tools/create_node_sweep_test.py` (um material por tipo de nó).

## Nós completos no Game PBR

Principled, Diffuse, Glossy e Toon usam as mesmas luzes: Sun, Point e Spot com atenuação e cone,
até 8 luzes, sombra nas 3 primeiras (Point com sombra de cubo; segue o `Cast Shadow` da lâmpada).

Principled BSDF, Diffuse BSDF, Transparent BSDF, Emission, Background, Mix/Add Shader,
texturas procedurais (Noise, Voronoi, Musgrave, Wave, Magic, Gradient, Checker, Brick),
Image e Environment Texture, Texture Coordinate, UV Map, Attribute, Geometry, Object Info,
Normal Map, Tangent (Radial e UV Map), Bump, Fresnel, Layer Weight, Blackbody, Wavelength, Sky Texture (Preetham),
nós de cor, conversão e vetor.

## Reflection probe

Dentro do raio de um objeto com a propriedade de jogo `probe`, Principled, Glossy e Glass refletem o
cubemap capturado pelo probe em vez do World. Detalhes no changelog de 2026-10-01.

## Nós exclusivos do jogo (`Game`)

Sprites Animation, Object, Time e Parallax funcionam nos dois caminhos do Game.
Output Attachment só no Game legado.

## Cor final (Color Management)

Com Shading Nodes, a saída de materiais e World aplica Scene > Color Management: exposure, gamma e view
transform Filmic (curva aproximada; looks de contraste mudam a inclinação). Outros view transforms (Raw, Log,
False Color) são tratados como Standard. Lido ao compilar o shader; não se combina bem com o filtro 2D de
tonemap (dupla curva).

## Pendências

Fases 3 a 5 validadas pelo usuário em 2026-10-02 (`tools/create_node_phases_test.py`). O caminho BI fica como está (decisão da Fase 6).
