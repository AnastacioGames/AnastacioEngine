# Análise: como a ThunderPlayer chega aos números do benchmark (2026-10-09)

Código consultado: `D:\ThunderPlayer-investigacao\source` (main 39bba1e3, ago/2026).
Binário medido: player de junho (o de agosto quebra com corrupção de heap).
As duas engines vêm do mesmo UPBGE 0.2.x, então os arquivos foram comparados lado a lado.
Medições: `D:\ThunderPlayer-investigacao\benchmark\diagnostico\` (relatórios do Codex) e
`...\diagnostico\static_batch_1009\` (A/B de hoje).

## Resumo

A diferença de 3 a 4 vezes sem instancing vem quase toda de **um recurso**: a Thunder agrupa
sozinha os objetos parados que usam a mesma malha e o mesmo material num buffer só (auto-batching).
A Anastacio já tem o mesmo mecanismo, a caixa **Static Batch** (`377a0026`), mas ela vem
**desligada** e precisa ser marcada objeto por objeto. As cenas do benchmark não a usavam.

Com Static Batch marcado, na mesma sessão (média de 2 rodadas, 1280×720, MSAA 2×):

| Cena | Culling | AE sem Static Batch | AE com Static Batch | Thunder |
|---|---|---:|---:|---:|
| 1.600 objetos | ligado | 592 | **1579** | 1353 |
| 1.600 objetos | desligado | 679 | **2331** | 2330 |
| 400 objetos | ligado | — | **3190** | 2293 |
| 400 objetos | desligado | — | **3471** | 2998 |

O A/B do Codex confirma a mesma coisa pelo outro lado: na própria Thunder, desligar o
auto-batching (`bge_allow_auto_batch = False`) derruba de 2602 para 664 FPS, o nível da Anastacio.

## Como a Thunder funciona (o que conta para o resultado)

### 1. Auto-batching de estáticos: o fator principal
- `RAS_DisplayArrayBucket::ActivateMesh`: quando um bucket tem mais de 1 slot ativo e o objeto não
  está em grupo, um contador sobe; depois de 10 ativações (`s_autoBatchThreshold = 10`), chama
  `TryAutoBatch()`.
- `TryAutoBatch` junta os mesh users num `RAS_BatchGroup` do bucket (`GetOrCreateFrameBatchGroup`,
  chave malha + display array + material). A geometria já transformada é copiada para um
  `RAS_BatchDisplayArray`.
- Fica fora do batch: material com z-sort, deformer, bucket com instancing e malha com
  `bge_allow_auto_batch = False`. **O padrão é ligado.**
- O desenho vai por `RunBatchingNode`. Ele junta os intervalos de índices contíguos dos slots
  visíveis e manda tudo num multi-draw (`IndexPrimitivesBatching`), com o material ativado uma vez
  só pelo objeto de referência. Os resultados ficam em cache por `m_sequenceVersion`.
- Movimento: `RAS_MeshUser::SetMatrix` compara a matriz com `memcmp` e, se mudou, tira o objeto do
  grupo (`SplitMeshUser`). Objeto que se mexe volta a ser desenhado sozinho e reentra no grupo
  depois de cerca de 10 frames parado.

### 2. Cache de estado por objeto (efeito pequeno)
- `RAS_Rasterizer::NeedsMeshUserUpdate` só deixa pular `ActivateMeshUser` e `GetTransform` quando
  material, matriz, cor, camada e pass index são **iguais aos do objeto desenhado antes**. Objetos
  em posições diferentes quase nunca batem, então o ganho fora do batch é pequeno.
- Para materiais de nós, a Thunder não chama `ProcessLighting` nem `BindShadowLamps` por objeto.
  A Anastacio chama os dois; o profiler do Codex mediu cerca de 0,12–0,15 ms cada com 1.600
  objetos, valor próximo do custo do próprio cronômetro. Esses dois passos atendem às sombras e
  às luzes no perfil core/Web da Anastacio, então não dá para tirá-los sem o mesmo cuidado.

### 3. Culling
- `KX_Scene::CalculateVisibleMeshes` tem um cache de visibilidade entre frames. Ele é usado quando
  nenhuma bounding box mudou, não há objetos dinâmicos e a matriz do frustum é idêntica bit a bit.
  Câmera parada = culling quase grátis. **A Anastacio testou isso e descartou:** com a câmera
  girando 1e-4 rad por frame a Thunder não ganha nada.
- A Thunder só faz `SetCulled(true)` e `UpdateBounds` em objetos com auto-update de bounds.
  A Anastacio corrigiu a causa real em `98f54d7f`: a AABB era marcada "modificada" em todo frame.
- Atalho duvidoso: depois de 60 frames no mesmo segundo, a Thunder testa só 4 planos no DBVT
  (sem near/far). É mais rápido, mas pode desenhar coisa que está atrás da câmera ou além do far.
  **Não copiar.**
- `KX_CullingHandler`: grão 256 no `parallel_reduce` e `UpdateBounds` só nos objetos dinâmicos.
  O grão foi testado na Anastacio e descartado (a câmera usa o caminho DBVT).

### 4. Instancing (onde a Thunder perde)
O código de agosto tem um caminho com SSBO persistente e indirect draw (`RAS_PersistentInstanceManager`)
e um caminho legado com caches de versão. No binário de junho o instancing ficou em 720–900 FPS,
contra 1779–2581 da Anastacio. Não há nada a copiar aqui.

## Comparação com a Anastacio

| Ponto | Thunder | Anastacio |
|---|---|---|
| Agrupar estáticos | automático, padrão ligado | `Static Batch` por objeto, padrão desligado |
| Objeto agrupado que se move | sai do grupo e volta depois de 10 frames parado | sai do grupo (`ae1370bc`), não volta sozinho |
| Ativação do material por objeto | pula se igual ao anterior | sempre ativa; caches de camada e probes em `gpu_material.c` |
| Luzes por objeto (nós) | não processa | `ProcessLighting` (com early-out) + `BindShadowLamps` |
| Culling com câmera parada | cache entre frames | recalcula; corrigido o trabalho repetido de AABB |
| DBVT relaxado (4 planos) | sim | não, e não deve ter |
| Instancing | mais lento | 2,4 a 3,6 vezes mais rápido |

## Plano

1. **Static Batch automático ou mais fácil de ligar** (fecha o item 1 do roadmap). Opções, da mais
   segura para a mais agressiva:
   a. botão "marcar todos os estáticos elegíveis" na cena/editor;
   b. opção da cena "Auto Static Batch", que trata todo objeto Static/No Collision sem deformer
      como se a caixa estivesse marcada;
   c. auto-batch em runtime como o da Thunder, com reentrada no grupo depois de N frames parado.
   Cuidado nas três: shaders que usam Object Info ou coordenadas locais passam a ver o objeto de
   referência (risco já anotado em `batching-estatico-e-culling.md`). Por isso é preciso uma saída
   por malha, como o `bge_allow_auto_batch` da Thunder.
2. **Reentrada no grupo:** hoje um objeto que se moveu uma vez fica fora do grupo para sempre.
   Copiar o contador de frames parado da Thunder.
3. **Culling com Static Batch ligado** (1579 contra 2331 FPS): o culling ainda custa cerca de 0,2 ms
   com 1.600 objetos. Só vale mexer se aparecer em jogo real. O cache da Thunder já foi descartado.
4. **Não fazer:** DBVT com 4 planos, pular luzes por objeto sem cobrir sombras e core/Web, e importar
   o MDEI (sem dados que justifiquem).
5. Antes de qualquer mudança: medir no RolimaRacer quantos objetos seriam elegíveis. A cena do
   benchmark é o melhor caso (1.600 cópias paradas da mesma malha).
