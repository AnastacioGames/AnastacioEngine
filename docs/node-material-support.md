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
| Glass BSDF | fresnel entre o reflexo do World e a luz transmitida, com brilho das luzes; com Blend Mode Alpha Blend refrata a cena atrás (cópia da tela, desfoque pela Roughness); em blend sólido usa o World desfocado |
| Refraction BSDF | com Alpha Blend refrata a cena atrás (cópia da tela); em blend sólido usa o World desfocado |
| Anisotropic BSDF | brilho GGX anisotrópico das luzes (Anisotropy, Rotation e Tangent como no Cycles; sem Tangent ligado, radial no Z do objeto); reflexo do World isotrópico, como o Glossy |
| Translucent BSDF | luz das lâmpadas por trás da superfície (Lambert em -N); não atravessa o objeto |
| Velvet BSDF | brilho de borda em ângulo rasante (mais estreito com Sigma baixo) |
| Subsurface Scattering | wrap lighting por canal (Radius × Scale): a luz passa do terminador; sem espalhamento real |
| Hair BSDF | brilho das luzes ao longo do fio (Tangent; sem Tangent ligado, radial no Z do objeto, como o Anisotropic): Reflection com Offset e RoughnessU, Transmission como contraluz na silhueta; World como ambiente suave |
| Ambient Occlusion | concavidade local da superfície (derivadas de tela), escurece cantos dentro de Distance; não oclui por outros objetos |
| Wireframe | arestas dos triângulos (quads mostram a diagonal), Size em unidades do mundo ou pixels; só no jogo, não na viewport. A malha com esse material perde o compartilhamento de vértices (3 por triângulo) |
| Bevel | devolve a normal sem mudança |
| Light Path | valores fixos de raio de câmera; Ray Length é a distância até a câmera |

## Nós sem suporte no Game PBR (alerta)

Sem código GLSL; a saída é ignorada ou zero:
Hair Info, IES Texture,
Point Density, Script, Principled Hair BSDF, Volume Absorption, Volume Scatter, Principled Volume.
Nós do BI num material do Game PBR (e do Cycles no Game legado) também entram aqui.
Ao carregar a cena, o jogo escreve um warning por material com esses nós
(`material "X": nodes not supported in the game ...`), visível no console do jogo e no log.
Teste de regressão: `tools/create_node_sweep_test.py` (um material por tipo de nó).

## Nós completos no Game PBR

Principled, Diffuse, Glossy e Toon usam as mesmas luzes: Sun, Point e Spot com atenuação e cone,
até 8 luzes, sombra nas 3 primeiras (Point com sombra de cubo; segue o `Cast Shadow` da lâmpada).
A Transmission do Principled refrata a cena atrás com Blend Mode Alpha Blend (mesma cópia da tela do Glass); em blend sólido é ignorada.

Principled BSDF, Diffuse BSDF, Transparent BSDF, Holdout (preto, alpha 0), Emission, Background, Mix/Add Shader,
texturas procedurais (Noise, Voronoi, Musgrave, Wave, Magic, Gradient, Checker, Brick),
Image e Environment Texture, Texture Coordinate, UV Map, Attribute, Geometry, Object Info,
Normal Map, Tangent (Radial e UV Map), Bump, Light Falloff (distância até a câmera, como raio de câmera no Cycles), Fresnel, Layer Weight, Blackbody, Wavelength, Sky Texture (Preetham e Hosek / Wilkie; com World Sun segue a lâmpada no jogo),
nós de cor, conversão e vetor.

## Reflection probe

Dentro do raio de um objeto com a propriedade de jogo `probe`, Principled, Glossy e Glass refletem o
cubemap capturado pelo probe em vez do World, no reflexo e na luz difusa; o reflexo tem correção de paralaxe por uma esfera do tamanho do raio do probe (some aos poucos com Roughness alta); com o Empty do probe desenhado como Cube, a correção usa a caixa do Empty (Display Size × escala, eixos do mundo), melhor para salas. Funciona também em cena sem World. Entre dois probes que se sobrepõem o reflexo mistura os dois, e no quarto externo do raio mistura com o World capturado, sem troca brusca. Com World em nós, o jogo captura o
World num cubemap no primeiro quadro e o usa fora dos probes. Detalhes no changelog de 2026-10-01 e 2026-10-02.

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
