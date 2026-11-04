# Análise do DirectX: clusters e atualizações parciais

Análise estática em 2026-11-04. Não houve alteração no renderizador, compilação dos exemplos,
execução em GPU ou medição de ganho. Os candidatos abaixo precisam de implementação e benchmark.

## Fontes e escopo

Foram lidos os exemplos públicos e a especificação, não a implementação interna do runtime ou dos drivers:

- [DirectX-Graphics-Samples, revisão analisada](https://github.com/microsoft/DirectX-Graphics-Samples/tree/68a2b1e97f71642924e74c7757ca21756ad221b5/Samples/Desktop/D3D12Raytracing/src).
  No exemplo `D3D12RaytracingPartitionedTLAS`: `animation.hlsl`, `PtlasWrite.hlsli` e o guia.
  No `D3D12RaytracingClusteredGeometry`: geração de argumentos em `FillInstantiateArgs.hlsl`,
  preparação de templates e leitura de timestamps em `D3D12RaytracingClusteredGeometry.cpp`.
- [DirectX-Specs: Raytracing2.md, revisão analisada](https://github.com/microsoft/DirectX-Specs/blob/2808d2103364aa2d0140f77c16cb705a6a597edf/d3d/Raytracing2.md).
- [Anúncio e resultados da Microsoft](https://devblogs.microsoft.com/directx/clas-ptlas-preview/).

Cópias de consulta estão em `artifacts/directx-study/`, com as revisões nos arquivos
`upstream-commit.txt` e `spec-commit.txt`. Ollama recusou conexão; a conferência foi direta.

A Anastacio usa OpenGL no desktop e WebGL2 no Web/Android. CLAS, PTLAS e
`ExecuteIndirectRTASOperations` não são chamadas que possamos inserir nesse backend.
O aproveitamento possível é dos padrões de atualização e organização dos dados.

## 1. Instancing: atualizar somente os registros alterados

**Candidato principal para reduzir trabalho durante o jogo.**

No exemplo PTLAS, `Animate` só chama `AppendPtlasWrite` quando a transformação mudou,
a partição mudou ou uma sincronização completa foi solicitada. O append reserva uma posição
com `InterlockedAdd`, mas preserva o `InstanceIndex` estável do objeto no registro copiado.
Posição na lista de mudanças e identidade do objeto são coisas distintas.

Isso não elimina toda a varredura: o shader ainda recebe uma thread por instância. A economia
está nas escritas emitidas e na atualização da estrutura, não em tornar todo o algoritmo O(mudanças).

Na Anastacio:

- [HasCachedData](../source/source/gameengine/Rasterizer/RAS_InstancingBuffer.cpp#L106) já compara
  a sequência de slots e as revisões dos objetos. Se nada mudou, não envia o buffer.
- [Update](../source/source/gameengine/Rasterizer/RAS_InstancingBuffer.cpp#L132) refaz os dados de
  **todas** as instâncias quando uma revisão muda. A comparação retorna na primeira diferença.
- [RunInstancingNode](../source/source/gameengine/Rasterizer/RAS_DisplayArrayBucket.cpp#L269)
  limita o cache ao modo normal sem ordenação. Billboards, halos e transparência têm outros contratos.

**Adaptação proposta:** inicialmente manter a lista/ordem atual e, quando ela permanecer igual,
identificar os registros com revisão diferente e atualizar intervalos correspondentes. Alteração
da lista, realocação, material ou modo incompatível conserva o envio completo. Não começar com
uma nova arquitetura global de IDs ou culling por compute.

Há um obstáculo real: [GPU_buffer_lock_stream](../source/source/blender/gpu/intern/gpu_buffers.c#L872)
faz `glBufferData(..., NULL, GL_STREAM_DRAW)`, descartando os dados anteriores para evitar espera.
Escrever apenas os objetos alterados depois dessa chamada deixaria os demais sem conteúdo válido.
O caminho parcial precisa preservar armazenamento e controlar sincronização; `glBufferSubData`
pode esperar a GPU e sair mais caro que o envio completo. Deve existir fallback para muitas mudanças.
Também é preciso atualizar cada bloco usado pelo layout: matriz, posição, cor, layer e Object Info.

**Validação proposta:** reutilizar `tools/debug/cenas/criar_cena_ra4_instancing.py` e comparar
0%, 1%, 10% e 100% de objetos móveis. Medir bytes enviados, intervalos, CPU e GPU em ms,
além do contador de uploads. Uma chamada parcial e uma completa contam igualmente como um upload.
Cobrir ocultação/retorno, múltiplas câmeras e passes, crescimento do buffer, cor, layer, pass index,
replaceMesh, remoção/recriação no mesmo endereço, sombras e probes. Preservar a revisão anti-ABA existente.

## 2. Métricas da GPU: consumir resultados de quadros anteriores

**Candidato menor e isolado, útil para medir sem introduzir espera no painel.**

O exemplo de clusters mantém timestamps em um anel. `DoRender` lê o slot antigo antes de
reutilizá-lo e só começa a publicar depois do preenchimento inicial. Esse padrão depende das
garantias de conclusão da GPU oferecidas pelo gerenciamento de frames do exemplo.

Na Anastacio, o painel chama `GetRenderQueryValue`, que chega a
[Result](../source/source/gameengine/Rasterizer/RAS_OpenGLRasterizer/RAS_OpenGLQuery.cpp#L109):
`glGetQueryObjectiv(..., GL_QUERY_RESULT, ...)`. As queries são encerradas no mesmo `EndFrame`
em que o painel pede seus resultados. Essa leitura pode bloquear até a GPU concluir o trabalho.

**Adaptação proposta:** anel de conjuntos de queries, leitura somente após `Available()` e
retenção do último resultado válido, com indicação de amostra pendente no início. Se o anel
estiver cheio, pular uma amostra em vez de esperar ou sobrescrever uma query pendente.
Não presumir que três quadros transcorridos provam conclusão da GPU.

Isso beneficia o modo `SHOW_RENDER_QUERIES`; não é promessa de acelerar o jogo com o painel
desligado. [A resolução dinâmica](../source/source/gameengine/Ketsji/KX_KetsjiEngine.cpp#L610)
já consulta disponibilidade e usa leitura sem espera, portanto não precisa receber a mesma correção.
Preservar também a proibição de sobrepor queries `GL_TIME_ELAPSED` e desabilitar métricas sem suporte Web.

**Validação proposta:** painel ligado/desligado sob carga de GPU, medindo CPU do painel,
cadência e validade das amostras; alternar o painel e a resolução dinâmica, reiniciar o jogo e
conferir ausência de erros GL. Ganho de renderização com o painel desligado não é critério desse candidato.

## 3. Comandos de Static Batch: reutilizar metadados quando válidos

**Candidato secundário de CPU, com ganho incerto.**

A ideia de preservar registros que não mudaram também sugere revisar
[RunBatchingNode](../source/source/gameengine/Rasterizer/RAS_DisplayArrayBucket.cpp#L357).
Os vetores de contagens e offsets já retêm capacidade, mas seus valores são preenchidos novamente
em cada chamada, mesmo com a mesma sequência visível e a mesma geometria.

Um cache teria de considerar a sequência dos membros, o passe e uma revisão estrutural do batch.
`RAS_BatchDisplayArray::Split` desloca índices e offsets dos membros seguintes: comparar apenas
ponteiros ou quantidade seria incorreto. Transparência ordenada deve continuar no caminho atual.
A própria comparação tem custo O(N), por isso pode não compensar o pequeno preenchimento atual.
Só avançar se o perfil apontar essa função como custo relevante.

## O que já existe ou não se transfere

- Static Batch já envia somente os intervalos dos membros visíveis. Dividi-lo espacialmente
  para recuperar culling por membro seria redundante. A sugestão inicial na conversa foi corrigida
  após conferir [a investigação existente](batching-estatico-e-culling.md) e o código.
- Instancing, LOD, DBVT, cache de bounds, caches de sombras e separação estático/dinâmico já existem.
  A política do exemplo de mover instâncias frequentes para uma partição global não demonstra,
  por si só, uma otimização ausente nesses sistemas.
- Templates de clusters reaproveitam trabalho de construção de estruturas de ray tracing.
  Não substituem a deformação dos vértices nem oferecem automaticamente um GPU skinning melhor.
- O formato `COMPRESSED1` é um contrato de posições para essas operações DXR. Portá-lo para
  atributos de vértice OpenGL exigiria outro layout, decodificação e avaliação de precisão; não é
  o primeiro candidato. Não promete reduzir texturas, que costumam ocupar outra parte da VRAM.
- Gerar argumentos DXR em compute evita retornos à CPU nesse pipeline, mas não fornece um
  caminho portátil pronto para WebGL2. Não se justifica introduzir compute/indirect em toda a engine
  sem uma medição que aponte esse limite.

## Ordem sugerida

Para buscar ganho no jogo: medir e prototipar primeiro o envio parcial de instancing, em peça
autocontida. Para melhorar a confiabilidade do profiling: tratar o anel de queries separadamente.
O cache de comandos do batch fica condicionado a evidência no perfil. Nenhum ganho percentual
dos testes DXR foi extrapolado para a Anastacio, e nenhum desses candidatos foi implementado.
