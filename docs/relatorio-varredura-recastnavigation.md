# Relatório de varredura de bugs silenciosos — RecastNavigation 1.6.0 (vendoring)

## Preparação

- Data: 2026-09-07
- Fonte: `D:\AnastacioEngine\tools\recastnavigation-main` (checkout local da tag/branch 1.6.0, 2023-05-21)
- Escopo coberto (conforme solicitado):
  - `Recast/Include/*.h`, `Recast/Source/*.cpp`
  - `Detour/Include/*.h`, `Detour/Source/*.cpp`
- Fora do escopo (não revisado): DetourCrowd, DetourTileCache, RecastDemo, Tests, Docs.
- Base de comparação: `CHANGELOG.md` do próprio repo (seção 1.6.0), para não repetir achados já corrigidos upstream (rasterização em borda de tile #476, off-mesh links duplicados #202, heap corruption em region layers #214, DT_OUT_OF_NODES #222, array overrun em removeVertex do DetourTileCacheBuilder #601, erro de arredondamento em connectExtLinks #428, etc.).
- Nenhuma alteração de código foi feita — fase de levantamento apenas.

## Frentes inspecionadas

- Ownership manual (rcAlloc/dtAlloc, rcFree/dtFree, retorno antecipado sem free, checagem de NULL pós-alocação) — auditoria sistemática de todas as chamadas de alocação em `Recast/Source/*.cpp` e `Detour/Source/*.cpp`.
- Limites/overflow em `unsigned short` (índices de vértice/voxel) e `unsigned char` (layerId, contadores de camada).
- TODO/FIXME remanescentes (nenhum novo relevante além dos já rotulados como cosméticos/rename pelo próprio changelog).
- Stubs/retornos constantes suspeitos (nenhum stub vazio encontrado nos arquivos do escopo).
- Consistência entre "log de erro" e valor de retorno (contratos de sucesso/falha).

## Registro de cada achado

### RN-01 — `dtNavMesh` fica com `m_tiles` não inicializado (lixo de heap) se a segunda alocação de `init()` falhar

- **Arquivo:linha:** `Detour/Source/DetourNavMesh.cpp:237-244` (alocação) e `Detour/Source/DetourNavMesh.cpp:209-222` (destrutor)
- **Sintoma/risco:** `dtNavMesh::init()` aloca `m_tiles` (linha 237) e, **antes de zerá-lo** (`memset` só ocorre na linha 243-244), tenta alocar `m_posLookup` (linha 240). Se essa segunda alocação falhar (`DT_OUT_OF_MEMORY`, retorno antecipado na linha 241-242), `m_tiles` permanece um bloco de memória não inicializado (conteúdo indeterminado). Quando o objeto `dtNavMesh` for destruído, o destrutor (linha 211-219) itera `m_tiles[i].flags` e, se o bit `DT_TILE_FREE_DATA` "aparecer" ligado por acaso no lixo de memória, chama `dtFree(m_tiles[i].data)` sobre um ponteiro de lixo — corrupção de heap / crash não determinístico.
- **Condição mínima de reprodução:** forçar falha de alocação entre as linhas 237 e 240 (ex.: allocator customizado via `dtAllocSetCustom` que falha na segunda chamada, ou pressão de memória real com `maxTiles` grande o suficiente para que `m_tiles` aloque mas `m_posLookup` não), depois destruir o `dtNavMesh`.
- **Causa provável:** ordem de operações — o `memset` de zeragem foi colocado depois das duas alocações, em vez de logo após cada alocação bem-sucedida (ou de usar `dtCalloc`).
- **Prioridade:** alta (corrupção de heap silenciosa, sem log, dependente de OOM — baixa frequência mas alto impacto quando ocorre).

### RN-02 — `dtNavMesh::~dtNavMesh()` não protege contra `m_maxTiles` "órfão" quando a própria alocação de `m_tiles` falha

- **Arquivo:linha:** `Detour/Source/DetourNavMesh.cpp:232-239` (ordem de atribuição) e `:211` (loop do destrutor)
- **Sintoma/risco:** `m_maxTiles` é atribuído (linha 232) **antes** da alocação de `m_tiles` (linha 237). Se essa alocação falhar, `init()` retorna `DT_FAILURE|DT_OUT_OF_MEMORY` com `m_maxTiles != 0` mas `m_tiles == NULL` (valor herdado do construtor, linha 196). Se o chamador, apesar da falha, ainda destruir o objeto (padrão comum: `dtNavMesh* mesh = dtAllocNavMesh(); mesh->init(...); ... delete/dtFreeNavMesh(mesh)` sem checar o status antes), o destrutor executa `for (i < m_maxTiles) m_tiles[i]...` com `m_tiles` nulo → null pointer dereference.
- **Condição mínima de reprodução:** `dtNavMesh::init()` com `maxTiles` grande o bastante para falhar a alocação de `m_tiles`, seguido de destruição do objeto (comum em código que ignora o `dtStatus` de `init()`, o que a própria doc do Detour desencoraja mas não impede).
- **Causa provável:** falta de guarda `if (m_tiles)` no destrutor, e/ou não resetar `m_maxTiles` para 0 nos caminhos de erro de `init()`.
- **Prioridade:** média (depende de o chamador ignorar o `dtStatus` de retorno, o que é um uso incorreto da API, mas o destrutor não é defensivo contra isso e o crash resultante é difícil de diagnosticar).

### RN-03 — `createBVTree()` não checa falha de `dtAlloc` para o array `items`

- **Arquivo:linha:** `Detour/Source/DetourNavMeshBuilder.cpp:175`
- **Sintoma/risco:** `BVItem* items = (BVItem*)dtAlloc(sizeof(BVItem)*params->polyCount, DT_ALLOC_TEMP);` não é seguida de checagem `if (!items)`. O laço imediatamente seguinte (linhas 176-233) escreve em `items[i]` sem qualquer teste de nulidade, e `subdivide()` (linha 236) também desreferencia o ponteiro. Todas as demais alocações desta mesma função/arquivo (linhas 301 e 441) têm checagem de NULL — este é o único ponto inconsistente. É chamada internamente por `dtCreateNavMeshData()` (linha 627) sempre que `params->buildBvTree == true`, ou seja, no caminho comum de bake de navmesh.
- **Condição mínima de reprodução:** falha de alocação (OOM real, ou allocator customizado que falhe) durante `dtCreateNavMeshData()` com `buildBvTree = true` e `polyCount` grande.
- **Causa provável:** omissão pontual da checagem de NULL, provavelmente por ser uma função `static` interna que "sempre funcionou" em testes com memória disponível.
- **Prioridade:** média (fácil de corrigir, mas exige condição de OOM para se manifestar).

### RN-04 — `rcBuildContours()`: crescimento do array de contornos (`newConts`) sem checar falha de alocação

- **Arquivo:linha:** `Recast/Source/RecastContour.cpp:937-946`
- **Sintoma/risco:** Quando o número de contornos excede `maxContours` (comentário do próprio código: "This happens when a region has holes" — **não é um caminho raro/artificial**, ocorre organicamente em geometria real com regiões furadas), o código dobra a capacidade e aloca `newConts` via `rcAlloc`, mas **não testa se `newConts` é `NULL`** antes do laço `newConts[j] = cset.conts[j]` (linha 938-944) que já escreve nele. Em caso de falha de alocação, é um crash imediato por desreferência de ponteiro nulo, sem log (diferente do padrão do resto do arquivo, que sempre loga `RC_LOG_ERROR` e retorna `false` em alocações que podem falhar — ver linhas 599-601, 845-847, 954-958 do mesmo arquivo).
- **Condição mínima de reprodução:** gerar uma malha com uma região que tenha buracos suficientes para que o número de contornos ultrapasse a estimativa inicial de `maxContours` (calculada a partir do número de regiões), sob pressão de memória (ou allocator de teste que falhe na N-ésima chamada).
- **Causa provável:** o autor tratou esse realloc como "praticamente nunca falha" e esqueceu a checagem simétrica que aplicou em todo o resto do arquivo.
- **Prioridade:** alta (caminho de execução real e não exótico — "região com buracos" é comum em navmeshes de jogos com pilares/obstáculos internos —, combinado com ausência total de log de erro, o que dificulta diagnosticar em produção).

### RN-05 — `rcBuildPolyMesh()` e `rcMergePolyMeshes()` retornam `true` mesmo após detectar corrupção de dados por overflow de `unsigned short`

- **Arquivo:linha:** `Recast/Source/RecastMesh.cpp:1287-1294` (`rcBuildPolyMesh`) e `Recast/Source/RecastMesh.cpp:1466-1473` (`rcMergePolyMeshes`)
- **Sintoma/risco:** Ambas as funções fazem, ao final:
  ```cpp
  if (mesh.nverts > 0xffff)
      ctx->log(RC_LOG_ERROR, "...The resulting mesh has too many vertices %d (max %d). Data can be corrupted.", mesh.nverts, 0xffff);
  if (mesh.npolys > 0xffff)
      ctx->log(RC_LOG_ERROR, "...The resulting mesh has too many polygons %d (max %d). Data can be corrupted.", mesh.npolys, 0xffff);
  return true;
  ```
  Ou seja: o próprio código reconhece e loga que os dados estão corrompidos (porque `mesh.verts`/`mesh.polys`/`mesh.regs` são arrays de `unsigned short`, e índices como `p[j] = (unsigned short)indices[...]` já truncaram silenciosamente valores acima de 65535 antes desse ponto), mas ainda assim devolve `true` (sucesso) ao chamador. Qualquer código que apenas verifique o booleano de retorno (o padrão usado em 100% dos outros pontos de erro do próprio arquivo, que retornam `false`) vai prosseguir usando um `rcPolyMesh` com índices truncados/colididos, alimentando isso para `dtCreateNavMeshData()` e gerando um navmesh final logicamente incorreto sem qualquer falha "dura" perceptível — só um log de warning que é fácil de não notar em produção.
  Nota: `rcBuildPolyMesh` já rejeita `maxVertices >= 0xfffe` **antes** de alocar (linha 1006-1010, retorna `false` corretamente) — mas isso protege apenas o total teórico de vértices de entrada, não o resultado após o merge/triangulação de `rcMergePolyMeshes` (que combina múltiplos tiles e não tem checagem equivalente antes de processar), nem cobre `npolys`.
- **Condição mínima de reprodução:** para `rcMergePolyMeshes`: mesclar tiles cuja soma de vértices ou polígonos ultrapasse 65535 (`maxVerts`/`maxPolys` calculados nas linhas 1315-1325 sem cap prévio) — plausível em cenas grandes com muitos tiles pequenos sendo mesclados em um único `rcPolyMesh` "solo".
- **Causa provável:** a checagem foi adicionada como aviso de diagnóstico tardio (provavelmente para depuração do próprio Recast) mas nunca foi promovida a condição de falha (`return false`), inconsistente com o padrão de contrato do resto do arquivo.
- **Prioridade:** alta (é exatamente o tipo de "bug silencioso" citado pelo usuário: sucesso reportado com dado sabidamente corrompido; especialmente relevante para `rcMergePolyMeshes`, usado ao combinar tiles de navegação — cenário comum no AnastacioEngine ao gerar navmesh para mapas grandes).

## Achados descartados / não reportados (falsos positivos verificados)

- `unsigned char remap[256]` em `Recast/Source/RecastLayers.cpp:472` — parece um limite mágico, mas é consistente: `layerId` e `rj.layerId` são sempre `unsigned char` (máx. 255 valores possíveis), então a tabela de 256 posições cobre todo o domínio. Não é overflow.
- Pilhas fixas `stack[MAX_STACK]` em `Detour/Source/DetourNavMeshQuery.cpp:2067-2099` e `:3119-3157` — todas as inserções (`stack[nstack++] = ...`) são precedidas por `if (nstack < MAX_STACK)`. Sem overflow.
- Demais ~30 chamadas de `rcAlloc`/`dtAlloc` no escopo (Recast.cpp, RecastArea.cpp, RecastMeshDetail.cpp, RecastRasterization.cpp, RecastRegion.cpp, DetourNode.cpp, parte de DetourNavMeshBuilder.cpp) têm checagem de `NULL` consistente com log de erro e `return false`/status apropriado.

## Resumo de prioridades

| ID | Prioridade | Arquivo |
| --- | --- | --- |
| RN-05 | Alta | Recast/Source/RecastMesh.cpp |
| RN-04 | Alta | Recast/Source/RecastContour.cpp |
| RN-01 | Alta | Detour/Source/DetourNavMesh.cpp |
| RN-03 | Média | Detour/Source/DetourNavMeshBuilder.cpp |
| RN-02 | Média | Detour/Source/DetourNavMesh.cpp |

## Encerramento desta execução

- Nenhuma correção foi aplicada (fase de levantamento, conforme solicitado).
- Nenhum build foi executado (não há alteração de código para validar).
- Recomendação de próximo passo: revisão humana dos 5 achados, priorizando RN-05 (contrato de sucesso/falha) e RN-04 (crash em caminho comum de geometria com buracos) antes de vendorizar a lib para dentro do AnastacioEngine; RN-01/RN-02/RN-03 são de baixa frequência (dependem de OOM) mas baratos de corrigir com uma checagem de `NULL` adicional.
