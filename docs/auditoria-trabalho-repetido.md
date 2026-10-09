# Auditoria de trabalho repetido por frame

## O conceito

O bug do culling corrigido em `98f54d7f` (ver [batching-estatico-e-culling.md](batching-estatico-e-culling.md))
pertence a uma família: **uma marca de "mudou" (dirty flag) que fica sempre ligada**, ou um
laço por frame que refaz trabalho sobre dados parados. Nada quebra visualmente, o
resultado é sempre o certo, só que recalculado à toa. Por isso o bug não aparece em
teste visual nem em revisão de código: só aparece como custo que cresce com o número de
objetos.

Sinais no código:

- marca setada fora do `if` que detecta a mudança (`m_modified = true;` no fim da função);
- `Notify*`/`SetModified`/`SetTransform` chamados por frame sem comparar com o valor anterior;
- laço por frame sobre todos os objetos onde a maioria cai num caminho "nada a fazer",
  mas o laço ainda percorre e toca a memória de cada um.

Regra de ouro: **numa cena parada, o trabalho de atualização por frame deve ser ~0**.

## Os contadores

`source/source/gameengine/Common/CM_WorkCounters.h` conta, por frame, e publica em
`bge.logic.getRenderStats()`:

| Chave | Onde conta | Esperado com tudo parado |
|---|---|---|
| `sceneNodeUpdates` | nós recalculados em `KX_Scene::UpdateParents` | ~0 |
| `transformSyncs` | `KX_GameObject::UpdateTransform` (física + árvore de culling) | ~0 |
| `boundsPushes` | `KX_GameObject::SetBoundsAabb` (AABB para o culling) | 0 |
| `meshMatrixChanges` | `RAS_MeshUser::SetMatrix` com matriz diferente | ~0 |
| `updateNotifies` | `CM_UpdateServer::NotifyUpdate` (malha/material marcados) | ~0 |

Os contadores são atômicos (o culling roda em tarefas TBB) e trocados no início de cada
frame em `KX_KetsjiEngine::BeginFrame`. O custo é um incremento por evento.

## Como rodar o detector

```
build\bin\AnastacioEngine.exe -b jogo.blend --python tools\debug\auditar_trabalho_repetido.py -- copia.blend log.txt
set AUDIT_SECONDS=20
build\bin\AnastacioRuntime.exe copia.blend
```

O script salva uma cópia com um medidor na câmera ativa de cada cena; o original não muda.
O log traz, a cada segundo, o número de objetos e a média por frame de cada contador.
`AUDIT_SECONDS=0` não fecha sozinho (para jogar e observar).

Como ler: fique parado no jogo. Um contador perto do número de objetos, ou que não cai
quando nada se move, é suspeito. Mova a câmera e veja quais contadores sobem: só os que
dependem da câmera deveriam subir.

## Validação

Cena de 1.600 objetos parados: com a correção, todos os contadores ficam em 0 depois do
primeiro segundo (carregamento). Recolocando temporariamente o bug de `98f54d7f`,
`boundsPushes` vai a 1.600 por frame — o detector teria achado o problema sem cronômetros.

## Varredura estática feita junto

- `RAS_MeshBoundingBox::Update`: o caso corrigido.
- `KX_ImpostorAtlasDeformer::SetAtlasCell`: reescreve UVs, mas só quando a célula muda
  (`KX_GameObject::UpdateLod` compara `m_currentAtlasCell`). OK.
- `BL_MeshDeformer::Apply`: protegido por `m_lastDeformUpdate != m_lastFrame`. OK.
- `BL_Shader::setAttrib`: ignora valor repetido. OK.
- Demais `NotifyUpdate` estão em caminhos de edição explícita (Python, deformers, destruição).

Próximo passo: rodar o detector nos jogos reais (parado e em movimento) e investigar
o contador que não zerar.
