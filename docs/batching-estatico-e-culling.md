# Batching estático e culling: investigação de desempenho (2026-10-08)

Comparação com uma engine de referência derivada do mesmo código (UPBGE 0.2) numa cena
sintética de 1.600 objetos parados (16 malhas compartilhadas, 1 material, 128.600
triângulos). A Anastacio fazia ~510 FPS com culling e ~707 sem; a referência, ~1.860 e
~2.628. Dois gargalos independentes explicavam a diferença.

## 1. Custo de desenho por objeto → opção Static Batch

Na referência, desligar o agrupamento automático de objetos estáticos derrubava o FPS
para o nível da Anastacio (A/B no mesmo executável: 2.602 → 664 FPS). A Anastacio já
tinha a peça (`KX_BatchGroup` → `RAS_BatchGroup` → `RAS_BatchDisplayArray`), só exigia
script Python e tinha falhas de ciclo de vida.

- `ae1370bc`: `RAS_MeshUser::SetMatrix` separa o membro do grupo quando a matriz muda
  (memcmp); hook `RAS_BatchGroup::OnMeshUserSplit` atualiza lista e referência do
  `KX_BatchGroup`; `KX_GameObject::RemoveMeshes` tira o objeto do grupo antes de apagar
  o mesh user; `~RAS_MeshUser` separa antes de limpar os slots.
  Validado: movimento visual (só o objeto movido sai, 64 → 63 membros, 1 → 2 draws),
  `endObject` da referência e de membro comum, `scene.restart()` 3x sem crash.
- `377a0026`: checkbox **Static Batch** (`ob.use_static_batch`, `gameflag2 & OB_STATIC_BATCH`)
  no painel Physics para tipos Static/No Collision. O conversor junta os objetos ativos
  marcados num `KX_BatchGroup`; ficam fora deformers, destrutíveis/explosivos/deformáveis
  e física que não seja Static/No Collision. Objetos de grupos instanciados (dupli) ainda
  não entram.
- O culling continua por membro: `RAS_DisplayArrayBucket::RunBatchingNode` emite só os
  intervalos dos slots visíveis (multi-draw), então dividir em regiões não traz ganho.

| Culling | Sem Static Batch | Com Static Batch | Referência |
|---|---:|---:|---:|
| desligado | ~707 | ~2.513 | ~2.628 |
| ligado (antes da correção 2) | ~512 | ~1.170 | ~1.860 |

Riscos conhecidos: falha parcial em `SplitMeshSlot` deixa `m_batchGroup` setado; os
`static_cast` para `KX_BatchGroup`/`KX_ClientObjectInfo` assumem que não existem grupos
só RAS; shaders que usam coordenadas locais/Object Info passam a ver o objeto de referência.

## 2. Culling DBVT refazendo trabalho todo frame → `98f54d7f`

Com Occlusion Culling (DBVT) ligado, o culling da câmera custava ~0,3–0,5 ms com 1.600
objetos parados. Cronômetros temporários em `KX_Scene::CalculateVisibleMeshes` mostraram
~320 µs no laço `SetCulled(true)`/`UpdateBounds(false)` e as 1.600 caixas "modificadas"
em todo frame. Causa: `RAS_MeshBoundingBox::Update()` terminava com `m_modified = true`
incondicional; cada objeto com auto-update de bounds recalculava a AABB e reenviava ao
Bullet (`CcdGraphicController::SetLocalAabb`). Correção: marcar só quando um array mudou,
sem apagar uma marca posta por `SetAabb`. Deformers usam `RAS_BoundingBox` simples e não
são afetados; `replaceMesh`/`addObject` forçam `UpdateBounds(true)`.

Descartados por medição: grão 256 no `parallel_reduce` do `KX_CullingHandler` (a câmera
usa o caminho DBVT) e cache de visibilidade entre frames (com a câmera girando 1e-4 rad
por frame, a referência manteve o FPS). Sem occlusion a Anastacio já ficava à frente.

Câmera girando, culling ligado, mesma rodada: Static Batch ~1.170 → ~1.700 FPS
(referência ~1.680); sem Static Batch ~512 → ~640 FPS. Validado no jogo do usuário.

## Ferramenta derivada

O padrão do bug 2 (trabalho por frame sobre dados que não mudaram) virou o detector
descrito em [auditoria-trabalho-repetido.md](auditoria-trabalho-repetido.md).
