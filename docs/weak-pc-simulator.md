# Simulador de PC fraco

Deixa a GPU desta máquina umas N vezes mais lenta, para sentir e medir o jogo como num notebook com vídeo
integrado (ex.: Intel HD 4400) sem ter um.

- Uso no editor: **Performance > Simulate Weak PC** (Off, 2x, 4x, 8x, 16x) e depois **Measure**. O botão
  mostra o fator ("Measure (GPU 8x slower)"), e o relatório traz o aviso no topo.
- Uso direto: `RANGE_WEAK_GPU=8 AnastacioRuntime.exe jogo.range`. Vale também para o jogo dentro do editor
  se a variável estiver no ambiente ao abrir o editor.
- Código: `source/source/gameengine/Ketsji/KX_WeakGpu.{h,cpp}`, chamado em `KX_KetsjiEngine::BeginFrame`
  (`FrameStart`) e `EndFrame` (`Burn`, antes do timer da resolução dinâmica). Em `gpu_extensions.c`, a
  variável faz a GPU ser tratada como integrada (Auto = Low, mesmos padrões de um notebook).

## Como funciona

1. Timestamps de GPU marcam o início do frame e o fim do render; o resultado é lido 2 frames depois, sem travar.
2. Depois do render, uma passada de tela cheia com um laço de custo fixo por pixel gasta (N - 1) × o tempo
   de GPU medido. O blend `ZERO, ONE` mantém a imagem; o número de voltas se ajusta sozinho a cada frame.
3. Com isso o FPS, o "GPU Latency" do Profile e a resolução dinâmica reagem como numa placa N vezes mais lenta.

## Limites

- Escala o total, não as proporções: numa iGPU de verdade, efeitos com muita leitura de textura (blur,
  SSAO, SSR) pesam relativamente mais que aqui. Use o fator como ordem de grandeza.
- Se o jogo é limitado pela CPU, a GPU fica ociosa dentro do frame e o tempo medido inclui essa espera; o
  simulador então pesa um pouco mais do que deveria.
- Clock da GPU: sem carga (jogo travado no vsync) a placa baixa o clock e cada etapa parece mais lenta; com o simulador ela sobe o clock. Por isso a coluna estimada do relatório com o simulador desligado tende a exagerar. Medido em `teste_efeitos.range`: etapas ~3,5x mais rápidas com 8x ligado.
- CPU, memória de vídeo e driver não são simulados. Sem timer de GPU (Web) a variável é ignorada.
- Nada substitui medir no aparelho real; serve para achar o problema antes.

## Tempo de GPU por etapa (relatório)

O Measure liga também `RANGE_PROFILE` (`profile.txt` na pasta do relatório). A seção **GPU time by step**
mostra a média de GPU de cada etapa (início, sombras, cena, filtros 2D com cada passada, cópia final) e uma
coluna estimada para uma GPU 8x mais lenta (ou o fator do simulador, se ligado). Vermelho: a etapa sozinha
passaria de metade do orçamento de 60 FPS lá.
