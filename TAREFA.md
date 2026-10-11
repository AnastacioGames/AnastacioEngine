# Tarefa deste worktree (Codex) — cluster Spawn / remoção / LibLoad

Fonte: [docs/auditoria-suspeitos.md](docs/auditoria-suspeitos.md), seção
"Spawn, remoção, LibLoad, lote e conversão sob demanda" (perto do final do
arquivo). Leia a seção inteira antes de começar — a tabela tem a coluna
"Onde" com arquivo:linha de cada item.

Branch: `codex/auditoria-spawn-liblod`. Worktree separado do projeto principal
e do worktree do Claude (`D:\AnastacioEngine-auditoria-claude`, cluster GPU) —
arquivos não se cruzam, pode trabalhar em paralelo sem medo de conflito.

## Resultado (concluído em 2026-10-11)

- **SP4/SP5:** corrigidos, validados no runtime e medidos A/B. O cache do hull
  reduziu `addObject()` de 6,645 para 0,182 ms no cenário controlado; a chave
  BVH não mostrou ganho isolável de parede, mas eliminou o hash repetido sem
  regressão.
- **SP6/SP7, SP9–SP11, SP14/SP15:** avaliados no código e confirmados como
  adiados; os contratos de ordem, ciclo de vida, hot-reload e ownership tornam
  a troca mais arriscada que o ganho sem uma carga real específica.
- **SP12:** já estava corrigido desde 2026-10-05 por `m_inactiveNameIndex`.
- **SP13:** removida a segunda remoção redundante do `KX_BatchGroup`; o upload
  de VBO inerente ao `Split` foi preservado.

Evidência detalhada e estado vigente: `docs/auditoria-suspeitos.md`; histórico
e resultados de teste: `docs/changelog.md`. Os artefatos temporários permanecem
em `_tmp_sp45_validation/` fora do commit.

## Itens investigados/corrigidos

Ordem sugerida, da maior confiança/payoff pra menor:

1. **SP4 + SP5** — mesmo bloqueio: falta um cache por `KX_Mesh` para hull
   (`CcdPhysicsController.cpp:2947`, `btConvexHullComputer`) e BVH compartilhada
   (`CcdPhysicsController.cpp:117-235` `shared_bvh_key`). Hoje recalcula hash de
   todos os vértices/índices a cada spawn mesmo quando a malha é a mesma.
   Prioridade alta — confiança "alta/média" no relatório.
2. **SP6 + SP7** — remoção de objeto é O(N)×20 (`KX_Scene.cpp:1448`
   `NewRemoveObject`, `BaseListValue.cpp:82` `RemoveValue` não para ao achar) e
   O(K²) em `DelayedRemoveObject`/`RemoveEuthanasyObjects` (`KX_Scene.cpp:1421`).
   Risco citado: "consumir pelo fim muda a ordem de destruição" — confirme que
   qualquer índice novo não muda a ordem observável antes de aplicar.
3. **SP12** — `KX_AddObjectActuator.cpp:278`/`KX_Scene.cpp:4140`: modo
   propriedade faz busca linear no Main a cada disparo. Risco citado:
   "cache nome→objeto exige invalidação ampla" — se for implementar, pense
   em quando invalidar (novo objeto, remoção, troca de propriedade).
4. **Avalie e documente** (não precisa corrigir se o risco for maior que o
   ganho — já estão marcados "adiado" com motivo no relatório; sua tarefa é
   confirmar ou refutar esse motivo com código/medição antes de decidir):
   SP9 (par pendurado no Bullet), SP10 (cache quebraria hot-reload de
   partículas GPU), SP11 (mudança estrutural na conversão sob demanda),
   SP13 (reenvio de VBO do lote no Split), SP14 (índice reverso malha→objeto),
   SP15 (ReplaceMesh duplicado no SpawnDecal).

## Como medir

Use a skill `cena-de-teste` deste repo (bpy legado) para cenas de spawn
repetido — o padrão já usado nos itens corrigidos (ex.: SP1, SP2, SP3, SP8)
foi cena de teste controlada + contador antes/depois. Siga o padrão de
measurement (rodadas curtas, ~10s, já é o que o usuário prefere).

## Build

Use a skill `build-anastacio` (vcvars64 + ninja). O worktree já tem `lib`
configurada (junction para a lib real do projeto principal) — **nunca** rode
`git worktree remove` neste worktree sem antes `cmd /c rmdir lib` (há um hook
em `.claude/settings.json` que bloqueia isso automaticamente, mas não confie
só nele).

## Ao terminar cada item

Atualize a tabela/status em `docs/auditoria-suspeitos.md` (mesmo padrão dos
itens já "corrigido"/"concluído"/"adiado" existentes) e registre no
`docs/changelog.md` se mexeu em código. Não toque nas seções de GPU
(GP3-GP7, RA2) — são do outro worktree.
