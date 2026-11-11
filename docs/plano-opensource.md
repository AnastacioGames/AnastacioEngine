# Plano: aproveitar código open source nas pendências

Criado em 2026-11-11. Ordem por ganho/esforço. Regras: só licenças compatíveis (MIT, BSD, zlib, Apache-2.0);
código de terceiros vai em `source/extern/<nome>/` sem modificação, com `README.txt` (licença, URL, commit),
como já é o `source/extern/xatlas`. Toda etapa C++ com ramo `__EMSCRIPTEN__` quando tocar API de SO/GL,
medição em cena controlada (`tools/debug/cenas/`) e iGPU (`RANGE_WEAK_GPU`) antes do aceite com janela.

## 1. xatlas: já integrado (só fechar a pendência)

Situação: `source/extern/xatlas` (MIT, commit f700c779) + `source/intern/ae_uvatlas` + `xatlas_pack()` em
`bl_operators/anastacio_lightmap.py`, desde a4e15a09; Lightmap Pack é o fallback. O roadmap ainda lista
"UV da lightmap por xatlas" como falta.

Os dois empacotadores rodam e vence o que cobre mais área (`make_lightmap_uvs`); `ae_uvatlas` só compila com
`WITH_CYCLES` e, se a biblioteca faltar, `xatlas_pack` devolve False sem log.

1. Registrar no log o **vencedor** (xatlas, Lightmap Pack, ou biblioteca ausente) e a área de cada um.
2. Cena controlada: malhas curvas, sala retangular, n-gons côncavos e faces degeneradas. Conferir além da
   área: sobreposição, margem entre ilhas e costuras visíveis no bake.
3. Atualizar o roadmap (tirar o item) e anotar no changelog.
4. Opcional: expor no painel a escolha Auto/xatlas/Lightmap Pack se a medição mostrar casos piores.

Esforço: 1 sessão curta.

## 2. meshoptimizer (MIT, zeux/meshoptimizer)

Biblioteca C++ pequena, sem dependências. Dois usos:

### 2a. Ordem de desenho dos triângulos (runtime) — feito 2026-11-11 (ver changelog)

O .cooked não guarda buffers de GPU prontos: `BL_CookedArrays::Save` (`BL_BlenderDataConversion.cpp`) grava
loops de origem, normais, tangentes e listas de índices; a leitura reconstrói o resto. A chave da malha tem
`version = 4` (`BL_CookedMeshKeyFlags`).

Riscos conferidos (revisão do Codex): `KX_Mesh::getVertex` expõe o índice do vértice e `RAS_Mesh::GetPolygon`
lê a lista de triângulos direto, então reordenar muda a API Python; a física (`CcdPhysicsController.cpp`, por
`origIndex` e `GetPolygon`) e os deformers (`BL_SkinDeformer`, `BL_MeshDeformer`, `KX_DentDeformer`,
`KX_SoftBodyDeformer`) dependem da ordem original. Otimizar só no caminho .cooked faria o jogo se comportar
diferente com e sem cache.

1. Vendorizar em `source/extern/meshoptimizer` (alvo CMake estático, README com licença/commit).
2. **Primeira versão: buffer de índices só para o desenho.** As listas públicas e de colisão e a ordem dos
   vértices ficam intactas; o array de desenho recebe `meshopt_optimizeVertexCache` (e overdraw só em opaco)
   no **mesmo ponto** dos dois caminhos (com e sem cache), antes de montar Static Batch e instancing, sem
   cruzar limites de parte/material. Só triângulos (linhas e materiais invisíveis ficam como estão).
3. Se gravar no .cooked: subir `version` da chave da malha (cache antigo vira miss e reconverte).
4. Remapear vértices (`optimizeVertexFetch`) só se a medição justificar, com remapeamento idêntico em todos os
   atributos, metadados, deformers e física.
5. Medição: cena controlada com 200 malhas de 20 k tris; ACMR (`meshopt_analyzeVertexCache`) antes/depois e
   tempo de GPU por etapa, inclusive em iGPU física e Web (ganho não é garantido). Regressões: `getVertex`,
   `getPolygon`, raycast com UV/face, skinning, shape keys, Dent, Static Batch, Geometry Instancing.

### 2b. Proxies do HLOD — Method "Sloppy" feito 2026-11-11

Feito: `source/intern/ae_meshopt` + Method Decimate/Sloppy no Build HLOD (padrão Decimate). Material, UV e cor
por vértice saem do triângulo original mais próximo. Medição (`tools/debug/cenas/medir_hlod_sloppy.py`, 16
objetos, ratio 0,1): Decimate 0,83 s, distância média/máx. original→proxy 0,058/0,485; Sloppy 0,38 s,
0,044/0,299. Falta: proxies no .cooked (item 3 abaixo) e aceite visual com janela.

1. `anastacio_hlod.py` hoje junta e usa Decimate Collapse. Adicionar modo "Sloppy" via `ae_meshopt`
   (biblioteca nativa no mesmo esquema do `ae_uvatlas`, chamada por ctypes): `meshopt_simplifySloppy`
   ignora topologia e funde objetos separados de uma célula (bom para proxy de longe).
2. Manter Decimate como padrão até medição: erro visual (diferença de pixels a 200 m) e tempo de build.
3. Proxies no .cooked (pendência do HLOD) entram junto, pelo mesmo caminho do 2a.

Esforço: 2a médio (formato e casos de exclusão); 2b pequeno.

## 3. Upscaling temporal (etapa 3 do plano-taa) com FSR 2 só como referência

A engine não usa compute shaders e precisa rodar em WebGL2; o FSR 2 oficial (FidelityFX, MIT) é todo em compute.
Portanto é um **TAAU próprio em passes de fragment shader**, que reaproveita ideias do FSR 2 sem prometer a mesma
qualidade.

Correções da revisão: `RAS_CANVAS_DIVISOR` é dos offscreens dos filtros 2D (`RAS_2DFilterOffScreen::Update`), não
reduz a cena. Quem reduz a cena é `RAS_ICanvas::SetRenderScale` (usado por `KX_KetsjiEngine::UpdateDynamicResolution`).
O vetor da etapa 2 é deslocamento **em espaço de mundo** (alpha = válido), não vetor de tela.

1. **Prova de conceito com escala fixa** (ex.: 67%): cor, profundidade e movimento na resolução interna; resolve
   e histórico na resolução de saída. Ajustar `KX_RenderPipeline::PostRenderScene` e
   `RAS_2DFilterManager::PrepareTaaHistory` para separar as duas resoluções, além de viewport, jitter (Halton com
   fase pela razão de escala) e coordenadas. Invalidar o histórico em resize, corte de câmera, troca de cena e
   mudança de escala.
2. Definir onde ficam os filtros seguintes e a UI/texto (resolução cheia exige tratar o caminho de desenho deles).
3. Reconstrução com ideias do FSR 2: filtro Lanczos aproximado, dilatação de profundidade/vetor, lock de detalhe
   fino, RCAS no fim (já existe do FSR 1). Crédito MIT no topo dos shaders portados.
4. Máscara reativa: decidir como produzi-la (transparentes e partículas não escrevem no MRT de velocidade).
   Objetos sem vetor hoje (instancing e geometry stage em `gpu_codegen.c`, Static Batch, `BL_Shader`, skinning na
   CPU): fechar instancing e Static Batch antes do aceite.
5. Depois: integrar com a resolução dinâmica, `filterManager.upscaleMode` (Off/Quality/Balanced/Performance),
   padrão Off.
6. Web: conferir formatos renderizáveis/filtráveis, limites de MRT e de unidades de textura, cópia de
   profundidade e precisão; o velocity hoje é desligado no Web/Android.
7. Medição: `criar_cena_taa_movimento.py` + grade de cercas finas; tempo de GPU na RX 6800M e em iGPU física
   (`RANGE_WEAK_GPU` não substitui); comparar com escala simples + FSR 1.

Esforço: grande (o maior da lista). Risco: ghosting em desoclusão e em objetos sem vetor; exposição/tonemap antes
ou depois do upscale.

## 4. Água: ondas FFT (fora por decisão do usuário em 2026-11-11; fica como referência) do Ocean Modifier (código já no repo, GPL)

`source/source/blender/blenkernel/intern/ocean.c` (Tessendorf, FFTW3) está ligado no build local
(`WITH_MOD_OCEANSIM`, `WITH_FFTW3`, `WITH_IMAGE_OPENEXR` = ON). O bake atual grava EXR `disp_`/`normal_`/`foam_`
por quadro (`object_modifier.c`, job). Evita o problema do water 0.99 (sem licença); conferir as obrigações de
licença da FFTW (GPL) na distribuição.

0. **Teste primeiro:** bake curto no editor instalado, conferir arquivos e valores (eixos, sinais, escala,
   espaço de cor, float), carregar e animar a sequência no runtime desktop e Web.
1. Editor: botão que converte o bake em textura do jogo (displacement + normal + foam). Cuidados: repetir no
   espaço não garante loop no tempo (fazer loop por período escolhido ou cross-fade); a espuma acumula
   estado entre quadros; memória/banda das sequências (preferir poucas camadas em atlas 2D e baixa resolução).
2. Material "Water Surface" (fase 3 do `plano-agua-realista.md`): amostra 2 escalas da textura de ondas,
   vertex displacement opcional, Fresnel, Planar Reflection, refração pela cor da cena, espuma pelo mapa.
3. Runtime não roda FFT por quadro (CPU cara, FFTW no Web): só textura assada. Opcional depois:
   FFT em fragment shader (ping-pong) se o loop assado ficar repetitivo.
4. Física: `Range.water.height(x, y)` lendo a mesma textura na CPU para boias/barcos, com a mesma transformação
   mundo→UV, interpolação no espaço e no tempo, as duas escalas e o deslocamento horizontal do shader.
5. Medição iGPU + Web; demo da fase 5.

Esforço: médio.

## Revisão do Codex (2026-11-11)

Aceitos: vencedor do xatlas no log; meshoptimizer só nos índices de desenho e igual com/sem cache;
`SetRenderScale` em vez de `RAS_CANVAS_DIVISOR`; vetor em espaço de mundo; Ocean testado antes de planejar o
material; loop temporal, espuma e FFTW. Conferidos no código (anastacio_lightmap.py, KX_2DFilterManager.cpp,
KX_KetsjiEngine.cpp, BL_BlenderDataConversion.cpp). Parcial: a afirmação de que deformers quebram com
remapeamento coerente não está provada, por isso o remapeamento ficou para depois da medição.

## Ordem e entregas

| # | Item | Entrega | Revisão |
|---|------|---------|---------|
| 1 | xatlas | roadmap/changelog + medição | Codex no diff |
| 2a | meshoptimizer .cooked | commit + medição ACMR/GPU | Codex no diff |
| 2b | HLOD Sloppy | commit + comparação visual | aceite com janela |
| 3 | Upscaling | etapas: jitter/divisor → reconstrução → máscara → UI | Codex + aceite com janela |
| ~~4~~ | ~~Água FFT~~ (fora) | bake → material → altura em Python | Codex + aceite com janela |
