# Revisão independente: estudo DirectX (clusters/PTLAS) do Codex

Revisão estática em 2026-11-04 de [analise-directx-clusters-ptlas.md](analise-directx-clusters-ptlas.md).
Sem alteração no renderizador, build ou medição. As referências `arquivo:linha` valem para o `main` em 706dbf1b.
Fontes externas: as cópias em `artifacts/directx-study/` (revisões registradas em `upstream-commit.txt`
e `spec-commit.txt`), não reobtidas.

Legenda: **[GL]** lógica aproveitável em OpenGL/WebGL2 · **[JÁ]** a engine já faz · **[DXR]** depende de DXR/driver ·
**[HIP]** hipótese sem evidência suficiente.

## Resumo

| Item do Codex | Veredito |
|---|---|
| 1. Instancing parcial | **Confirmado o diagnóstico, corrigida a prioridade.** O custo maior provável é outro: um buffer por tipo de passe, compartilhado por todas as luzes/câmeras (ver A1). |
| 2. Queries sem espera | **Confirmado.** Bloqueio no mesmo quadro é real; afeta só o painel. |
| 3. Metadados do Static Batch | **Rejeitado como cache.** O preenchimento custa o mesmo que a comparação. Trocado por junção de faixas contíguas (A2, [HIP]). |
| Itens "não se transfere" | **Confirmados**, com uma ressalva sobre WebGL2 em A2. |

## 1. Instancing parcial — confirmado, com correções

Conferido no código:

- `HasCachedData` compara passe, tamanho, ponteiro do slot e revisão de cada `RAS_MeshUser`
  ([RAS_InstancingBuffer.cpp:106](../source/source/gameengine/Rasterizer/RAS_InstancingBuffer.cpp#L106)).
  Qualquer diferença leva a `Update`, que refaz **todas** as instâncias
  ([RAS_InstancingBuffer.cpp:132](../source/source/gameengine/Rasterizer/RAS_InstancingBuffer.cpp#L132)). Correto.
- `GPU_buffer_lock_stream` faz `glBufferData(..., 0, GL_STREAM_DRAW)` + `glMapBuffer`
  ([gpu_buffers.c:872](../source/source/blender/gpu/intern/gpu_buffers.c#L872)). Escrever só intervalos depois disso
  deixaria o resto indefinido. Correto.
- A revisão é global e monotônica (`s_instancingVersion`, atômica), trocada em matriz, cor, layer e pass index
  ([RAS_MeshUser.cpp:41](../source/source/gameengine/Rasterizer/RAS_MeshUser.cpp#L41)). Isso já é a proteção anti-ABA:
  um objeto novo no mesmo endereço nunca repete revisão. Correto.
- O cache só vale para `RAS_NORMAL` sem ordenação
  ([RAS_DisplayArrayBucket.cpp:303](../source/source/gameengine/Rasterizer/RAS_DisplayArrayBucket.cpp#L303)).
  Necessário: `GetTransform` depende de `drawingmode` (billboard/halo dependem da câmera).

Paralelo com o exemplo PTLAS: `Animate` → `AppendPtlasWrite` só grava registros alterados, mas o destino
é uma estrutura persistente da GPU cuja sincronização o próprio aplicativo controla por fence. Aqui o buffer é
órfão a cada envio. A analogia vale para a **lógica de seleção** (marcar alterados por revisão), não para o envio.

### Correção: o que a atualização parcial realmente economiza

São ~80 bytes por instância com todos os atributos (36 matriz + 12 posição + 16 cor + 4 layer + 12 info).
10 mil instâncias são ~800 KB por envio. O custo dominante tende a ser a **CPU de empacotamento**
(`GetTransform` + escrita por instância) e a sincronização, não a banda. Isso também é hipótese: só a medição em ms diz o que domina.

Três variantes, da mais segura para a mais arriscada:

| Variante | Como | Economiza | Risco |
|---|---|---|---|
| P1 | Cópia CPU persistente; reempacotar só os índices com revisão diferente; enviar o buffer inteiro com órfão (`glBufferData(data)`) | CPU de empacotamento | Baixo: mesma semântica de sincronização de hoje. +80 B/instância de RAM |
| P2 | `glBufferSubData` só nos intervalos, sem órfão | CPU e banda | Alto: se a GPU ainda lê o quadro anterior, o driver espera ou copia escondido. Pode sair mais caro que o envio completo |
| P3 | Anel de N buffers, cada um com suas revisões; atualiza o buffer k com o que mudou desde **a última escrita dele** | CPU e banda, sem espera | Alto: N cópias das revisões por buffer, fence ou N≥3 quadros, invalidação por realocação |

No WebGL2 não existe `glMapBuffer`; a camada de compatibilidade do Emscripten já guarda uma cópia CPU e envia a faixa
mapeada. Isso favorece P1 também lá. Recomendo P1 se o perfil justificar; P2/P3 só com medição.
Regras de fallback para P1: lista de slots diferente (visibilidade/ordem), `Realloc`, troca de passe,
modo não normal ou ordenado → empacotamento completo, como hoje.

### Nova observação A1 (mais importante): troca de passes invalida o cache

`m_instancingBuffer` tem **um buffer por `DrawType`**
([RAS_DisplayArrayBucket.cpp:199](../source/source/gameengine/Rasterizer/RAS_DisplayArrayBucket.cpp#L199);
tipos em [RAS_Rasterizer.h:75](../source/source/gameengine/Rasterizer/RAS_Rasterizer.h#L75)).
Todas as luzes de sombra, as 2 ou 3 cascatas do CSM e as 6 faces de luz pontual
([KX_ShadowRenderer.cpp:623](../source/source/gameengine/Ketsji/KX_ShadowRenderer.cpp#L623)) usam o mesmo buffer `RAS_SHADOW`; câmeras extras, split screen,
sondas e espelhos usam o mesmo `RAS_RENDERER`. Cada passe tem um conjunto visível diferente, então
`HasCachedData` falha a cada troca e a cena **totalmente parada** pode reenviar o grupo várias vezes por quadro.
Isso anula o cache em repouso justamente nos casos com mais passes, e nenhum envio parcial resolve:
a lista muda, não as revisões.

Correção possível **[GL]**: pequeno conjunto de buffers por `DrawType` (ex.: 2–4), escolhido pela lista de slots
(tamanho + hash dos ponteiros, confirmado pela comparação completa já existente), com descarte do menos usado.
Cada buffer guarda seu próprio `m_cachedMeshSlots`/`m_cachedVersions`, então a regra anti-ABA continua igual.
Ainda é **hipótese de desempenho**: depende de quantas vezes por quadro o mesmo bucket é desenhado em `RAS_SHADOW`
(o cache de invalidação das cascatas, [KX_ShadowRenderer.cpp:385](../source/source/gameengine/Ketsji/KX_ShadowRenderer.cpp#L385), pode pular passes)
e do custo em ms; contar uploads não prova gargalo. 2–4 buffers também não são solução garantida: se alternarem
mais conjuntos visíveis do que buffers, o cache continua sendo substituído. O tamanho do cache sai da medição
(quantos conjuntos distintos por quadro), com limite de memória.

## 2. Queries do painel — confirmado

- O painel chama `GetRenderQueryValue` → `m_renderQueries[value].Result()`
  ([KX_KetsjiEngine.h:617](../source/source/gameengine/Ketsji/KX_KetsjiEngine.h#L617)) →
  `glGetQueryObjectiv(GL_QUERY_RESULT)` ([RAS_OpenGLQuery.cpp:109](../source/source/gameengine/Rasterizer/RAS_OpenGLRasterizer/RAS_OpenGLQuery.cpp#L109)).
- As queries são encerradas em `EndFrame` imediatamente antes de `RenderDebugProperties`
  ([KX_KetsjiEngine.cpp:556](../source/source/gameengine/Ketsji/KX_KetsjiEngine.cpp#L556)), sem nenhum
  comando entre o `End` e a leitura. `GL_QUERY_RESULT` nesse ponto espera o resultado das queries, ou seja,
  o trabalho da GPU até o `End`. Não é exatamente um `glFinish` (não espera trabalho posterior), mas reduz o
  paralelismo CPU/GPU com o painel aberto e pode distorcer os números exibidos.
- A resolução dinâmica já usa `Available()` + `ResultNoWait()`
  ([KX_KetsjiEngine.cpp:638](../source/source/gameengine/Ketsji/KX_KetsjiEngine.cpp#L638)) e tem guarda contra
  sobrepor `GL_TIME_ELAPSED` com o painel. Não precisa de mudança. Codex está correto.

O anel de timestamps do exemplo de clusters lê o slot antigo antes de reutilizá-lo porque o gerenciamento de
frames garante conclusão. Em GL não há essa garantia: a adaptação correta é anel de 2–3 conjuntos de queries,
ler só quando `Available()`, manter o último valor e **pular** a amostra se o próximo slot ainda estiver pendente.
O Codex já propôs isso. Cuidado extra: a guarda que pausa a resolução dinâmica quando o painel está ligado
tem que continuar valendo para todos os slots do anel. Benefício limitado ao modo de diagnóstico; é barato e isolado.

## 3. Metadados do Static Batch — rejeitado como cache

O laço atual de `RunBatchingNode` faz, por membro visível, duas leituras inline de `m_parts`
([RAS_DisplayArrayBucket.cpp:385](../source/source/gameengine/Rasterizer/RAS_DisplayArrayBucket.cpp#L385)).
Comparar a lista com a anterior custa as mesmas N leituras de ponteiro, mais a invalidação por `Split`
([RAS_BatchDisplayArray.cpp:107](../source/source/gameengine/Rasterizer/RAS_BatchDisplayArray.cpp#L107)), que desloca
offsets de todos os membros seguintes. Não há trabalho a economizar. O culling por membro já existe
(só os intervalos visíveis entram no `glMultiDrawElements`); não propor divisão espacial para isso.

### Nova observação A2: juntar faixas contíguas **[HIP]**

Quando membros visíveis vizinhos ocupam faixas de índice adjacentes (`offset[i] + 4*count[i] == offset[i+1]`),
podem virar uma única faixa antes do `glMultiDrawElements`
([RAS_StorageVbo.cpp:161](../source/source/gameengine/Rasterizer/RAS_OpenGLRasterizer/RAS_StorageVbo.cpp#L161)).
Com tudo visível e em ordem, o batch inteiro vira uma faixa. O custo é uma comparação a mais por membro no laço
que já existe, sem estado nem invalidação. Não se aplica ao caminho ordenado por distância.

Ganho incerto: no desktop o driver costuma processar o multidraw de forma barata. No WebGL2,
`glMultiDrawElements` depende da extensão `WEBGL_multi_draw`; sem ela, a emulação vira um laço de `drawElements`,
cada um validado pelo navegador. **Conferir antes** como o build Web resolve essa chamada e medir a quantidade
média de faixas por batch. Só vale se houver muitas faixas pequenas e contíguas.

## Outras ideias dos exemplos e da especificação

| Ideia | Classe | Avaliação |
|---|---|---|
| Separar instâncias que mudam muito numa partição global (PTLAS) | [JÁ] | Static Batch já divide (`SplitMeshUser`) o membro que se move; instancing separa por bucket. Sem ganho novo demonstrado. |
| Manter índice estável da instância separado da posição na lista de escritas | [GL] | É a base de P1/P3: o slot no buffer segue a ordem da lista visível; a revisão identifica a instância. Já implícito no desenho atual. |
| Templates de clusters / instanciação de CLAS | [DXR] | Reuso de construção de BVH de ray tracing. Não temos BVH na GPU. |
| `COMPRESSED1` para posições | [DXR]/[HIP] | Contrato de entrada do build de aceleração. Quantização de vértices em GL exige outro layout e decodificação no shader; sem evidência de gargalo de banda de vértices. |
| Argumentos gerados em compute + `ExecuteIndirect` | [DXR]/[HIP] | WebGL2 não tem compute nem indirect. Inviável como caminho comum. |
| Timestamps em anel | [GL] | É o item 2. |
| Números de desempenho do anúncio | — | Medem construção de BVH em DXR. Nenhum percentual se transfere para esta engine. |

## Prioridade

| # | Candidato | Benefício provável | Complexidade | Risco |
|---|---|---|---|---|
| 1 | A1: medir alternância e ms; se relevante, cache limitado de buffers | Médio–alto em cenas com sombra/CSM/split screen e instancing | Baixa–média | Baixo (cada buffer reusa a validação atual) |
| 2 | Anel de queries do painel | Painel confiável; nenhum ganho com painel fechado | Baixa | Baixo |
| 3 | P1: empacotar só instâncias alteradas, envio completo | Baixo–médio em grupos grandes com poucos móveis | Média | Baixo–médio |
| 4 | A2: juntar faixas contíguas no batch | Incerto; talvez relevante na Web | Baixa | Baixo |
| — | P2/P3, cache de metadados do batch, compute/indirect | Não recomendado agora | — | — |

## Menor experimento para o melhor candidato (A1)

Sem alterar código:

1. Variante de `tools/debug/cenas/criar_cena_ra4_instancing.py` **sem as ações de quadro** (a original move,
   recolore, oculta e mostra um objeto nos quadros 60–180) e com os objetos espalhados em profundidade, para que
   cada cascata enxergue um conjunto diferente. Sol com CSM em 3 cascatas; rodadas extras com 2 cascatas e com
   uma luz pontual (6 faces).
2. Rodar ~10 s no runtime em background e registrar por quadro: `CM_WORK_INSTANCING_UPLOADS`, número de
   conjuntos visíveis distintos por bucket, e ms de CPU em `RunInstancingNode`/`Update` (Game Trace ou
   `RANGE_PROFILE`). Medir só com instrumentação existente; se faltar a contagem de conjuntos, ela é o único acréscimo.
3. Leitura: uploads/quadro ≈ número de passes, mesmo parado, confirma o mecanismo; a decisão de corrigir depende
   dos ms. Sem sombras, deve dar ≈ 0. Se der ≈ 0 com sombras, A1 cai.

Se confirmado, o protótipo é uma peça só: `RAS_DisplayArrayBucket` com até 4 buffers por `DrawType`.

## Métricas e regressões

Métricas: uploads/quadro, bytes enviados, ms de CPU em `RunInstancingNode`, ms de GPU (timer, sem limite de FPS),
FPS médio e 1% mínimo; para o anel de queries, CPU do painel e idade da amostra exibida.
Rodadas curtas (~10 s) com 0%, 1%, 10% e 100% de objetos móveis.

Regressões a cobrir: ocultar/mostrar objetos, `replaceMesh`, remover e recriar no mesmo endereço,
mudar cor, layer e pass index, crescimento do buffer (`Realloc`), troca de material/recarga de shader
(que hoje zera os buffers, [RAS_DisplayArrayBucket.cpp:438](../source/source/gameengine/Rasterizer/RAS_DisplayArrayBucket.cpp#L438)),
transparência ordenada, billboards/halos, sombras CSM e luzes múltiplas, sondas, split screen,
override shader, Web (sem `glMapBuffer` e sem timer de GPU), iGPU.

## check_docs

Estado atual (`python tools/check_docs.py`): 116 documentos, **168 erros e 58 avisos, todos em
`docs/code-map-gameengine.md` e `docs/code-map-gpu.md`** (linhas e tamanhos defasados). São os mesmos 168
registrados pelo Codex, portanto anteriores a esta revisão. A conferência depois de criar este arquivo está
anotada na entrega. O `check_docs` só confere arquivos rastreados (`git ls-files`); enquanto este documento
não for adicionado ao Git, ele fica fora da conferência. Com ele marcado no índice (`git add -N`), o total
continuou 168 erros: nenhum novo.

## Réplica do Codex (2026-11-04)

Aceitos e incorporados acima: A1 passa a ser prioridade, mas como hipótese a medir em ms; tamanho do cache
sai da medição; a RA4 precisa de variante parada; CSM tem 2 ou 3 cascatas; leitura da query não equivale a
`glFinish`; `check_docs` usa arquivos rastreados. Sequência acordada: medir a alternância entre passes →
cache limitado de buffers se o custo for relevante → empacotamento parcial na CPU (P1). Cache de metadados do
Static Batch fora da prioridade.

## Medição A1 (2026-11-04)

Cena parada nova: [criar_cena_ra4_passes.py](../tools/debug/cenas/criar_cena_ra4_passes.py)
(nada se move, recolore ou some); orquestrador [medir_ra4_passes.py](../tools/debug/cenas/medir_ra4_passes.py).
Runtime ~10 s por caso, `getRenderStats` + `RANGE_PROFILE`, 120 quadros de aquecimento descartados.
Máquina de desenvolvimento do usuário; `main` a partir de 7212f1e4. Saída em `artifacts/ra4_passes/`.

| Caso | uploads/quadro | passes de sombra | `render.shadows` (ms) 400 inst. | 2000 inst. | 5000 inst. |
|---|---|---|---|---|---|
| sem sombra | 0 | 0 | — | — | — |
| sol, 2 cascatas, espalhado | 2 | 2 | 0,20 | 0,40 | 1,00 |
| sol, 3 cascatas, espalhado | 3 | 3 | 0,20 | 0,58 | 1,28 |
| sol, 3 cascatas, juntos | 3 | 3 | 0,30 | 0,93 | 2,38 |
| luz pontual | 4 | 6 | 0,20 | 0,40 | 0,90 |

Tempos refeitos em 2026-11-04 depois da correção do desenho N² (seção abaixo); a primeira rodada
estava inflada pelo bug. Contagens de upload iguais nas duas rodadas. Todos os casos ficaram presos a 60 FPS.

O que mostra:

- **Mecanismo confirmado.** Com a cena parada, cada passe de sombra com lista diferente reenvia o grupo inteiro
  (0 uploads sem sombra, 2/3 com CSM). Na luz pontual, 4 uploads em 6 passes: faces vizinhas com a mesma lista
  aproveitam o cache. Mesmo com os objetos juntos, as 3 cascatas deram 3 uploads (as listas diferem).
- **Custo pequeno.** Passar de 2 para 3 cascatas com 5000 instâncias somou ~0,28 ms, incluindo culling
  e desenho do passe extra. O upload de 5000 instâncias custa, portanto, no máximo ~0,3 ms por passe aqui.
  A 400 instâncias fica no limite da resolução do profiler (0,1 ms).
- **Sem gargalo de GPU.** Com a correção, 5000 instâncias com sol em 3 cascatas cabem folgado em 60 FPS.
  O caso "juntos" é mais caro pela sobreposição de geometria, não pelos uploads.
- Não medido: custo de GPU/driver de orfanar o buffer várias vezes por quadro.

**Decisão sugerida:** não implementar o cache de buffers por lista agora. O ganho máximo esperado é ~0,3 ms
por passe em grupos de milhares de instâncias. Reabrir se um jogo real mostrar `render.shadows` alto com
`instancingUploads` alto por quadro. Pelo mesmo motivo, P1 (empacotar só o que mudou) também fica sem prioridade.

## Achado na investigação da GPU: instancing desenhava N² (corrigido localmente)

A medição A1 mostrou ~166 ms de GPU com 5000 cubos numa RX 6800M. Isolando sem sombra: 2000 cubos com
instancing 19,8 ms × 0,43 ms sem instancing, mesmos objetos visíveis e desenhos; cubos minúsculos não mudavam
(não era pixel); `GL_STATIC_DRAW`/`glBufferSubData` não mudavam (não era memória do buffer); iGPU também ~30×.
Um diagnóstico do estado dos atributos no desenho mostrou `indices=14400` para 400 instâncias de um cubo de 36:
o Static Batch automático tinha mesclado os objetos, e o nó de instancing, que tem prioridade
([RAS_DisplayArrayBucket.cpp:218](../source/source/gameengine/Rasterizer/RAS_DisplayArrayBucket.cpp#L218)),
desenhava o lote inteiro por instância.

Correção em `BL_StaticBatchObjects`: material de instancing fica fora do batch. Depois: 2000 instâncias 0,38 ms;
5000 com CSM 1,37 ms. Com isso, a medição A1 (custo de reenvio por passe) continua válida, mas os tempos de
GPU da primeira tabela estavam inflados pelo bug.
