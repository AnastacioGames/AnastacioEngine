# Plano: água realista (estudo do water 0.99 do martinsh)

Referência estudada: `D:\ANASUTASHIO_GAMES\Arquivos Blends and Range\Arquivos Prontos Auxiliares\Shader\Water\water_0.99_optimized.blend`
(Martins Upitis, 2013, BGE). Estudo feito em 2026-10-30.

## Licença: não copiar o código

- O arquivo não tem licença. O readme diz que foi compartilhado "só para prévia" e que o autor
  "não recomenda usar em projetos". Sem licença explícita, o padrão é todos os direitos reservados.
- Também tem trechos de terceiros: céu baseado em Simon Wallner (simonwallner.at) e `MouseLook.py`
  de Mike Pan.
- Regra deste plano: **reimplementar as técnicas** (todas são públicas e conhecidas) com código
  nosso. Não colar shader, script nem textura do arquivo (`watercaustics.png`, `normalcaustics.png`,
  `depth.png` são dele). Usar o arquivo só para comparar o resultado visual.
- Se um dia quiser usar algo literal, a saída é pedir permissão por escrito ao autor.

## O que o arquivo faz (pente fino)

| Peça | Arquivo no .blend | Técnica | A engine já tem? |
|---|---|---|---|
| Superfície da água | `watersurface.py` | 6 camadas de normal map rolando com o vento, cada uma deformada pela anterior (choppy); Fresnel dielétrico exato; reflexo planar e refração distorcidos pela normal; aberração cromática na refração; brilho do sol (spec com potência alta pesado pela luminância do reflexo); espalhamento de luz nas cristas (cor turquesa, laranja no pôr do sol); costa por mapa de profundidade (ondas menores e mais lentas perto da praia) | Reflexo planar sim (Planar Reflection). Fresnel exato, espalhamento nas cristas, normal encadeada e aberração não |
| Câmera debaixo d'água | `watersurface.py` (lado de baixo), `ground_water.py`, `blur.py` | IOR invertido (água→ar), névoa por distância com cor que depende do sol, escurece com a profundidade; chão com cáusticas projetadas pela normal da água; desfoque | Não |
| Câmera saindo da água | `distort.glsl` (Filter 2D) | Debaixo: ondas senoidais com separação RGB. Ao sair: uma "lâmina" de água (ruído 3D esticado na vertical, escorrendo) que se desfaz em ~4 s e gotas (ruído 3D cortado por limiar, formas orgânicas) que somem em ~100 s subindo o limiar. Normal da gota por `dFdx/dFdy`, refração com R/G/B deslocados diferente. Borda da tela atenuada para não amostrar fora | Não (o LensWaterFX do Rolimã é a fase 1) |
| Céu | `sky.py` | Modelo de Preetham (Rayleigh + Mie, turbidez), tonemap Uncharted 2 | Sim: céu Atmospheric da engine |
| Sol arrastável | Lamp + bricks de Mouse/Parent | O sol vira filho do mouse com o botão esquerdo | Só demo; dá para fazer em Python |
| Flare do sol | `sunflare.py`, `flare1` | Halo por `dot(reflect)`; raycast até o céu para esconder atrás de objetos | Sim: lens flare da engine (com saída antecipada) |
| Brilho/anamórfico | `glow.py`, `texrender.py` | Bloom com limiar + faixa anamórfica | Bloom/Glare sim; anamórfico conferir |
| Exposição automática | `lum.py` | Mede a luminância numa render pequena e adapta com `1 - exp(-t*adapt)` | Conferir (não achei "auto exposure" no changelog) |
| Reflexo/refração | `watertexture.py` | Câmera espelhada + ImageRender 512² com plano de recorte | Planar Reflection nativo (C++) é melhor |

## O que vale aproveitar (por ordem de ganho visual / custo)

1. **Gotas na lente + lâmina ao sair da água** (Filter 2D, barato). Fase 1, já serve ao Rolimã.
2. **Shader de superfície da água nativo**: normal encadeada em 4 camadas (6 é caro), Fresnel exato,
   espalhamento nas cristas, brilho do sol, refração com aberração, cor/névoa ligadas ao sol do World.
   Usar o Planar Reflection existente e a profundidade da cena para a refração (sem segunda câmera).
3. **Debaixo d'água**: névoa e cor pela profundidade + ondulação da tela + cáusticas procedurais no
   chão (sem a textura dele). Ligado sozinho quando a câmera cruza o plano da água.
4. **Exposição automática** (se a engine ainda não tem).
5. Sol arrastável: só para demo/editor.

## Otimização para a engine

- Ruído: trocar o Perlin 3D por hash (8 chamadas `rnm` por canto, muito caro) por value noise 3D
  barato ou uma textura de ruído 3D pequena; 2 oitavas bastam para a lente.
- Água: 4 amostras de normal no lugar de 6; LOD por distância (longe usa 2); refração pela cor da
  cena já renderizada (sem render extra); reflexo pelo Planar Reflection em meia resolução.
- Filtros só ligados quando precisam (`filter.enabled`), como as auras do Rolimã.
- Seguir as regras do repo: ramo `__EMSCRIPTEN__`/WebGL2 quando mexer em C++, medir na iGPU
  (`RANGE_WEAK_GPU`) antes de aceitar.

## Fases

1. LensWaterFX do Rolimã com a técnica da lente (limiar de ruído, lâmina, normal por derivada, RGB),
   mantendo os raios para fora com velocidade. (em andamento 2026-10-30)
2. Levar o filtro de lente para a engine como efeito pronto (componente/preset de câmera).
3. Material "Water Surface" nativo (nó ou preset) com Planar Reflection.
4. Modo debaixo d'água automático + cáusticas.
5. Demo `tools/debug/cenas/` com praia, sol arrastável e pôr do sol para comparar com o arquivo.
