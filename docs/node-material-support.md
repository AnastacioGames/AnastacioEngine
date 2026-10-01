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
| Glossy BSDF | Diffuse com brilho suave; sem reflexo |
| Glass, Refraction, Toon, Translucent, Velvet, Anisotropic, Subsurface Scattering | viram Diffuse BSDF |
| Hair BSDF | cor chapada, sem luz |
| Ambient Occlusion | AO sempre 1; a cor passa direto |
| Bevel | devolve a normal sem mudança |
| Light Path | valores fixos de raio de câmera |
| Light Falloff | todas as saídas devolvem Strength |
| Sky Texture | branco |

## Nós sem suporte no Game PBR (alerta)

Sem código GLSL; a saída é ignorada ou zero:
Blackbody, Wavelength, Tangent, Wireframe, Hair Info, Holdout, IES Texture,
Point Density, Script, Principled Hair BSDF, Volume Absorption, Volume Scatter, Principled Volume.

## Nós completos no Game PBR

Principled BSDF, Diffuse BSDF, Transparent BSDF, Emission, Background, Mix/Add Shader,
texturas procedurais (Noise, Voronoi, Musgrave, Wave, Magic, Gradient, Checker, Brick),
Image e Environment Texture, Texture Coordinate, UV Map, Attribute, Geometry, Object Info,
Normal Map, Bump, Fresnel, Layer Weight, nós de cor, conversão e vetor.

## Nós exclusivos do jogo (`Game`)

Sprites Animation, Object, Time e Parallax funcionam nos dois caminhos do Game.
Output Attachment só no Game legado.

## Pendências

Ver o plano em `docs/roadmap.md` (nós de material): iluminação unificada (Fase 3)
e aproximações melhores para Glass, Toon, AO, Blackbody e Sky (Fase 4).
