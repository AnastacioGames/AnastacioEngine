# Revisão da frente 6 — Lógica, componentes e API Python

Levantamento: [levantamento-modulos-criticos.md](levantamento-modulos-criticos.md), seção 6.

## Corrigido

- **LOG-01 — broadcast duplicado ao ler sem destinatário.** `KX_NetworkMessageManager::GetMessages("", ...)`
  lia a lista sem receptor duas vezes (receptor vazio é o próprio broadcast). Afetava os comandos de áudio
  do World Sound (`GetMessages("", "audio")`, cada comando executado 2x) e `Range.logic.getMessages("")`.
  A leitura passou a usar `find` em vez de `operator[]`, sem criar entradas vazias por consulta.
  Regressão: [criar_cena_revisao_mensagens.py](../tools/debug/cenas/criar_cena_revisao_mensagens.py)
  (`--server`; esperado 1/2/2/3/0).

## Conferido sem mudança

- `RegisterObject`: os dois pontos de chamada recebem objetos distintos (objetos ativos na conversão e
  réplicas novas em `AddReplicaObject`); `Merge` do LibLoad move a lista. Não há registro duplo.
- `UpdateComponents`: a cópia do vetor custa só ponteiros por tick. Remoções (`endObject`, LibFree) são
  adiadas para `RemoveEuthanasyObjects`/`ProcessScheduledLibraries`, então nenhum ponteiro da cópia fica
  inválido durante o tick. Suspensão e culling de componentes respeitados em `KX_GameObject::UpdateComponents`.
- Sensor de mensagem passa o nome do objeto (nunca vazio); a cutscene só testa se há mensagem.
