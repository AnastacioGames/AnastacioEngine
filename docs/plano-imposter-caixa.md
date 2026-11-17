# Plano: Impostor de Caixa (Box Impostor)

Data: 2026-11-17. Inspiração: palestra "Imposter Syndrome" (Thomas R Murphy, BCON26) e o add-on
pago "Imposter Cards" dele. Nada do add-on é copiado; a técnica (card voltado para a câmera +
vistas assadas + parallax) é conhecida e é refeita aqui do zero.

## O que já existe

- Nó **Billboard** (Vertex, `node_billboard` em `gpu_shader_material.glsl`): gira a malha para a
  câmera no vertex shader, cilíndrico ou esférico. É o mesmo truque dos nós mostrados na palestra
  (`posição virada − posição real` no Displacement). Malha no plano local XZ.
- LOD com **Billboard** + **Bake Impostor Texture** (`OBJECT_OT_bake_lod_impostor`): fotografa a
  cor por Blender Internal em 1 ou N ângulos em volta de Z; `KX_ImpostorAtlasDeformer` troca a
  célula pelo ângulo. Só cor (luz assada na imagem), só ângulos horizontais.
- Formato de nó GLSL por arquivo com `@surface` (`node_shader_glsl_script.c`): dá posição e normal
  do pixel no espaço do objeto (em metros) e até 4 imagens.

## O que falta (o ganho do impostor de caixa)

1. Ver o objeto de **cima/baixo** também, não só em volta de Z.
2. **Volume**: parallax pela profundidade assada, então o card não parece plano quando a câmera
   anda.
3. **Luz da cena**: normal assada, o impostor é iluminado em tempo real em vez de ter a luz pintada.

## Técnica

Bake: 6 vistas ortográficas da caixa do objeto (+X, −X, +Y, −Y, +Z, −Z), cada uma enquadrando a
face correspondente da bounding box. Atlas 3x2:

- `<obj>_imp_color.png` — RGBA (alpha = recorte).
- `<obj>_imp_data.png` — RGB = normal em espaço do objeto (0..1), A = profundidade a partir da face
  da caixa, normalizada pela espessura da caixa naquele eixo (0 = na face, 1 = face oposta). Lido
  como dado (sem sRGB).

Runtime (fragment, nó GLSL `@surface`):

1. Raio do olho: origem = posição do pixel no card, direção = da câmera para o pixel, tudo no
   espaço do objeto. Precisa da posição da câmera no espaço do objeto (ver Etapa 1).
2. Interseção do raio com a caixa → `t_entra`, `t_sai`.
3. Para cada um dos 3 eixos, só a vista cujo lado encara a câmera (sinal da direção): marcha de
   `t_entra` a `t_sai` em N passos (steep parallax); em cada ponto, a UV vem de trocar os eixos
   (swizzle: tira o eixo da vista) e a profundidade do ponto é comparada à assada. Primeiro passo
   dentro = acerto daquela vista.
4. Fica o acerto com menor `t` das 3 vistas (o "Greater/Less Than por comprimento" da palestra).
   Sem acerto: alpha 0 (descarte pelo Alpha Clip do material).
5. Saída por `@shading` não combina com `@surface`; o nó devolve cor+alpha, e uma segunda saída de
   normal fica para a Etapa 3.

Qualidade: `steps` 1 (uma amostra por vista no plano do meio, o "low" da palestra) até 32.

Card: um quad no plano XZ com o tamanho da diagonal da caixa, com o nó Billboard esférico ligado
no Vertex Offset, para cobrir a caixa de qualquer ângulo.

## Etapas (uma por vez, com aceite)

Estado: Etapa 1 feita (91d183384). Etapa 2 feita: `object.bake_box_impostor`
(`startup/bl_operators/anastacio_box_impostor.py`); caixa cúbica em metros, eixos U/V por vista no topo
do arquivo; ainda sem botão na interface (F3). Etapa 3 (cor) feita, aguardando aceite: nó
`presets/glsl_nodes/box_impostor.glsl` + material do card criado pelo bake (nó → Color, Billboard
esférico → Vertex Offset). Decisões do teste: marcha só com as 3 vistas voltadas para a câmera (com as 6,
partes finas como a orelha viram lâminas e os passos pulam); profundidade lida no texel mais próximo e
dilatada 1 texel no bake, cor espalhada para os texels transparentes; leituras com `img_<nome>_lod`
(mipmap em laço com break dava linhas); 32 passos padrão. Card fora do Auto Static Batch (Billboard).
Etapa 3b (modo Box) feita, aguardando aceite: param `box_mode` + `box_x/y/z` (meias-medidas da
bbox); o raio acerta a bbox real e lê 1 vez a cor da face de entrada (objetos que preenchem a caixa:
caixotes, prédios). O bake liga sozinho quando >= 95% de cada face da bbox tem a profundidade da face
(`_box_fill`, guardado em `card["box_impostor_fill"]`); furos de 1 texel somem na dilatação.
Profundidade do acerto feita (`surface_depth` + `gl_FragDepth`, aguardando aceite): objetos que
atravessam o impostor cortam a forma real (desliga o early-Z só desse material).
Falta: normal para a luz, botão na UI.

1. **C (pequeno):** `@surface` ganha `surface(uv).view` = direção câmera → pixel no espaço do
   objeto (em metros, mesma convenção de `position`), calculada no wrapper a partir de `scr_slv`
   (sem builtin novo). Perspectiva: `eye = -vec3(dot(slv[0].xyz,t), dot(slv[1].xyz,t),
   dot(slv[2].xyz,t)) / ssc` com `t = slv[3].xyz`, `view = normalize(position - eye)`.
   Ortográfica (`gl_ProjectionMatrix[3][3] != 0`, como em `gpu_shader_material.glsl:311`):
   `view = normalize(-vec3(slv[0].z, slv[1].z, slv[2].z) / ssc)`. Vale com o Vertex Offset do
   Billboard, que é somado antes de `varposition` (`gpu_shader_vertex.glsl:331`). Supõe eixos sem
   cisalhamento. Teste: nó de depuração que pinta a direção.
2. **Bake (Python):** operador `object.bake_box_impostor` — 6 renders ortográficas por Blender
   Internal com passes de cor, normal e Z por nó File Output; monta os dois atlas e cria
   `<obj>_box_impostor` (quad + material com o nó, Alpha Clip, Billboard). Cena de teste em
   `tools/debug/cenas/`.
3. **Nó GLSL** `presets/glsl_nodes/box_impostor.glsl` (Library > Impostor): cor + alpha; depois
   normal para a luz.
4. **LOD:** opção no nível LOD para usar o impostor de caixa (sem o giro na CPU, o shader faz).
5. Medir na cena controlada: N árvores reais × impostor (FPS, draw calls).

## Revisão do Codex (2026-11-17), aceita após conferir no código

- A marcha usa a interseção da **reta** com a caixa e começa em `t_entra` mesmo negativo: o card
  fica no meio da caixa, e a metade entre o card e a câmera não pode se perder.
- Cada mapa de profundidade guarda só a primeira superfície vista daquela face: exigir alpha válido,
  detectar o cruzamento (antes fora, agora dentro) e refinar entre os dois passos; tratar componente
  de direção quase zero, UV fora da face e vazamento entre células do atlas (margem/clamp na célula).
- Bake: a cor precisa ser **albedo sem luz** (passe Color do BI), senão a luz conta duas vezes.
  Normal e Z em EXR float intermediário; o passe Normal do BI é em espaço de câmera e vira espaço
  do objeto por vista.
- `LOC_TO_VIEW` é uniform por objeto (`gpu_material.c:1097`): GPU instancing e Static Batch ficam
  desligados para o impostor na primeira versão. Sombra pelo mesmo offset ainda não confirmada.

## Riscos

- Static Batch junta objetos e perde a origem de cada um → billboard e `eye` errados. Impostor de
  caixa fica fora do batch na primeira versão (ou guarda o centro por vértice depois).
- Custo: 3 vistas × N passos de leitura de textura por pixel. Card pequeno na tela (uso a distância)
  mantém barato; `steps` baixo para iGPU/celular.
- GLSL ES (Web/celular): sem `transpose`/`inverse`, laço com limite constante.
