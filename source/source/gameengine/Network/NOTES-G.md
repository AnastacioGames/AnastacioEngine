# Frente G: RPC

Criado em 2026-10-04. Branch `net/rpc`. Arquivos: `NET_RPC.h/.cpp`, `tests/NET_RPC_test.cpp`.

## Interpretações

- **Tabela:** `RpcTable::add` em qualquer ordem, depois `finalize()` ordena por nome (comparação de bytes,
  igual em todas as plataformas) e o `rpcId` é o índice. Nome vazio ou repetido é recusado; até 65 535 RPCs.
- **Quem pode chamar o quê:**
  - cliente → `Server`, `All`, `Others`;
  - `Owner` só sai do servidor para o dono do objeto. Cliente que manda `Owner` conta violação.
  - `All` roda no servidor e em todos os clientes, inclusive quem chamou; `Others` roda no servidor e em todos
    menos quem chamou. Chamado pelo servidor, `Others` vai para todos os clientes e não roda no servidor.
  - `Owner` chamado pelo servidor num objeto do próprio servidor roda localmente.
- **Violação** (conta na sessão pelo novo `ServerSession::reportViolation`): corpo inválido, `rpcId`
  desconhecido, alvo proibido, argumentos fora da assinatura (quando `checkArgs`), `requireOwner` com
  `netId` 0 ou de outro dono.
- **Objeto despawnado:** RPC com `netId` que não existe mais é descartado em silêncio dos dois lados
  (`droppedNoObject`), sem violação: é corrida normal com o `Despawn`.
- **Confiável ou não:** confiável vai no canal 1 (`Rpc`). Não confiável vai no canal 3 (`Input`) de cliente
  para servidor e no canal 2 (`Snapshot`) de servidor para cliente. A sessão aplica o limite de 120 RPC/s a
  qualquer mensagem `Rpc`, em qualquer canal; o RPC não conta de novo.
- **Assinatura:** opcional (`checkArgs` + `argTypes`). Sem ela, qualquer lista de argumentos válida passa.
- **Limite de 1024 bytes:** conta do byte `count` até o fim do último argumento (como em `NET_Messages`).

## Mudança fora dos arquivos novos

- `ServerSession::reportViolation(ClientId, nowMs, events)` (aditivo): soma uma violação vinda da camada de
  cima; devolve false se fechou a conexão.

## Dúvidas para o contrato

1. **Quem chamou:** o `Rpc` não tem campo de origem; no cliente, um RPC repassado (`All`/`Others`) chega com
   `caller = 0`. Proposta: mensagem provisória `200 RpcFrom` = `u16 fromClient` + corpo do `Rpc`, só de
   servidor para cliente. Não implementada: a sessão descarta tipos acima de 18 sem repassar, então exigiria
   mudar a sessão nas duas pontas.
2. Clientes que ainda não carregaram a cena também recebem o repasse; o RPC num objeto que eles não conhecem é
   descartado. Se for preciso, dá para filtrar por `ready`.
