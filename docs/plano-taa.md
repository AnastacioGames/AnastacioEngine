# Plano: TAA (anti-aliasing temporal) e, depois, upscaling

Estado: etapa 1 implementada (2026-11-01); etapa 2 implementada para objetos rígidos (2026-11-11, ver
changelog e "Como ficou a etapa 2"); etapa 3 aberta.
Uso: Render > TAA no editor, ou `scene.filterManager.taaEnabled = True` / `taaSharpen` no Python.
Teste: `tools/debug/teste_taa.py` (instruções no topo do arquivo).

Antes: Hoje a Engine só tem FXAA na imagem final
(`KX_2DFilterManager::EnsureFxaaPass`). O changelog antigo já registrava TAA como lacuna: sem jitter
de projeção, sem motion vectors e sem histórico da cor final.

## O que já existe e será reaproveitado

- **Resolve temporal dos efeitos:** `RAS_Temporal2DFilter.glsl` faz reprojeção pela profundidade,
  rejeição por oclusão e clamp 3x3. Ligado por `KX_2DFilterManager::AttachTemporalResolve` em névoa,
  SSGI, SSR e SSAO (`TEMPORAL_VFOG/SSGI/SSR/SSAO`). Roda em baixa resolução, nunca na cor final.
- **VP do quadro anterior:** `bgl_PreviousViewProjectionMatrix` nos filtros 2D
  (`RAS_2DFilter.cpp:171`) e `m_prevViewProj`/`m_prevFXCamera` em `KX_2DFilterManager::UpdateCameraFX`
  (motion blur de câmera), que já detecta troca de câmera.
- **GPU skinning:** `BL_SkinDeformer` já envia `m_boneMatrices` ao vertex shader; para vetores de
  movimento de personagens basta guardar também as matrizes do quadro anterior.
- **Matriz de projeção:** `RAS_Rasterizer::GetFrustumMatrix` é o ponto único para aplicar jitter.

## Etapa 1: TAA só com movimento da câmera (feita)

1. **Jitter:** sequência Halton(2,3) de 8 amostras, deslocamento de ±0,5 pixel somado ao
   `left/right/bottom/top` do frustum (ou às colunas de translação da projeção). Só na câmera principal;
   planar maps, `ImageRender`, sombras e cubemaps ficam sem jitter.
   Guardar a projeção sem jitter para culling, picking e `getScreenPosition` do Python.
2. **Passe `FILTERPASS_TAA`:** novo shader `RAS_TAA2DFilter.glsl`, rodando em resolução cheia depois do
   tonemap e antes de FXAA, lente e UI. O FXAA continua independente (o painel avisa que os dois juntos amaciam mais).
   - reprojeção pela profundidade com a VP anterior (mesma conta do `RAS_Temporal2DFilter.glsl`);
   - tirar o jitter atual da UV antes de ler a cor;
   - clamp da vizinhança em YCoCg (variância, γ ≈ 1,0) contra ghosting;
   - histórico lido com Catmull-Rom (5 leituras) para não borrar;
   - alpha ≈ 0,1, subindo quando a reprojeção cai fora da tela ou na desoclusão;
   - sharpen leve opcional (estilo CAS) no fim.
3. **Histórico:** ping-pong RGBA16F (RGBA8 se não houver float) do tamanho da tela. Invalidar quando
   trocar de câmera, redimensionar a janela, mudar de cena ou numa câmera com corte brusco.
4. **Interface:** painel Render > TAA (liga/desliga e Sharpen), ao lado do FXAA.
   Python: `scene.filterManager.taaEnabled` e `taaSharpen`.
5. **Web:** sem cópia de profundidade nem float em alguns dispositivos; desligar e voltar para o FXAA.

Limite da etapa 1: objetos que se movem em relação à câmera deixam rastro ou borram. Serve para
cenários parados, carro ou personagem visto de câmera fixa lenta, e para testes.

## Etapa 2: vetores de movimento (velocity buffer)

1. Novo alvo RG16F no framebuffer da cena (MRT) com a diferença de posição na tela entre os dois
   quadros, já sem o jitter.
2. Vertex shader dos materiais: passar `prevModelViewProj` por objeto
   (guardar a matriz do objeto do quadro anterior em `KX_GameObject`/`RAS_MeshUser`).
3. GPU skinning: guardar também `m_prevBoneMatrices`. Skinning na CPU: guardar a posição anterior ou
   aceitar só o movimento do objeto.
4. Partículas na GPU: escrever a velocidade da própria partícula.
5. Objetos sem vetor (shaders customizados, filtros antigos): cair na reprojeção pela câmera.
6. O TAA passa a usar o vetor; a rejeição por profundidade continua como segurança.
   O motion blur de câmera também pode passar a usar o buffer (motion blur por objeto).

Custo estimado: é a parte mais invasiva, porque mexe no gerador GLSL dos materiais (`gpu_codegen`) e no
render da cena. Exige teste com materiais legados, nós de shader e instancing.

### Como ficou a etapa 2 (2026-11-11)

O desenho mudou do item 1 acima: em vez de velocidade em pixels, cada material de objeto opaco escreve
**onde o ponto estava no mundo no quadro anterior, menos onde está agora** (RGBA16F, alpha 1 = válido).
O TAA já reconstrói a posição no mundo pela profundidade; ele soma esse deslocamento antes de projetar
com a câmera do histórico. Assim o tratamento de jitter da etapa 1 não mudou.

- Slot: `GPU_material_velocity_slot`, depois dos attachments do usuário e dos 4 do SSGI; o launcher cria o
  alvo a partir da cena inicial e todas as cenas usam esse layout (`GPU_material_velocity_layout_set`).
  Desligado no Web/Android.
- Matriz anterior: `RAS_MeshUser::GetPreviousMatrix`, com um contador por quadro de render
  (`NextRenderFrame`, antes das sondas). Objeto que não foi desenhado no quadro anterior fica sem movimento.
- Sem vetor (o TAA usa só a câmera nesses pixels): céu, transparentes, Static Batch, halo/billboard,
  instancing, estágio de geometria (Fur Shells, Outline...), shaders Python próprios (`BL_Shader`). Skinning na CPU
  e Vertex Offset entram só com o movimento do objeto.
- GPU Skinning (armature em "RanGE GPU Skinning"): o shader recebe também a paleta de ossos do quadro
  anterior (`prevBoneMatrices`, `RAS_MeshUser::GetPreviousBones`) e soma a mudança de pose ao movimento.
  Teste: `tools/debug/cenas/criar_cena_taa_skin.py` + `medir_taa_movimento.py <cena> --cinza` (câmera parada,
  osso indo e voltando, pixels cinza a mais andando): só câmera +2,6 pontos, com vetor +1,0; o mesmo
  vai-e-volta com o objeto inteiro dá +1,75 x +0,70, então o skinning ficou no nível do objeto rígido (a sobra
  é borda que revela fundo).
- O alvo é zerado no começo de cada cena, depois do céu.
- A/B: `RANGE_TAA_VELOCITY_OFF=1` volta para a etapa 1.
- Teste: `tools/debug/cenas/criar_cena_taa_movimento.py` + `tools/debug/medir_taa_movimento.py` (runtime no
  desktop invisível). Pixels do carro que mudam entre parado e andando: sem TAA 0,4%, só câmera 5,7-7,1%,
  com vetor 0,4%.
- Limite: `filterManager.taaEnabled = True` numa cena que começou sem TAA não cria o alvo (fica na etapa 1).

## Etapa 3: upscaling

Renderizar a cena com `RAS_CANVAS_DIVISOR` (ex.: 67% ou 50%) e usar o TAA para reconstruir a resolução
cheia (jitter cobrindo os pixels de saída), com sharpen no fim. A UI e o texto continuam em resolução
cheia. Alvo: ganho de FPS em iGPU sem perder nitidez como o upscale simples.

## Testes

- Cena controlada (skill `cena-de-teste`): grade de cercas finas e fios, câmera girando devagar.
  Comparar FXAA x TAA com print e com o profiler (`frames`, `shaders`).
- Caso de corrida: RolimaRacer com câmera atrás do carro (exige etapa 2 para o carro não borrar).
- Troca de câmera, resize e pause: sem fantasma do quadro antigo.
- Custo alvo: ≤ 1 ms em 1080p numa GPU dedicada média; medir também na iGPU.

## Riscos

- Rastro e ghosting em partículas transparentes e em objetos sem vetor.
- Borrão geral: precisa do Catmull-Rom e do sharpen.
- Transparências e efeitos já temporais (SSR/SSGI) somam dois históricos; manter os efeitos antes do TAA.
- Jitter vazando para scripts que leem a projeção da câmera.
