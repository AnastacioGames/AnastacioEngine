# Frente E: replicação (`net/replication`)

Arquivos: `NET_IWorld.h`, `NET_Replicator.h/.cpp` (servidor), `NET_ReplicaClient.h/.cpp` (cliente),
`tests/NET_Replication_test.cpp`, `tools/net_bench.cpp`. Nenhuma mensagem nova; `NET_Messages`,
`NET_Snapshot` e `NET_Session` não mudaram.

## Interpretações (conservadoras)

- **Spawn/Despawn só para objetos criados em jogo** (`NetId >= 0x80000000`). Objeto de cena já existe
  no cliente: sair da relevância vira `removed = 1` no snapshot, e o objeto fica parado no mundo do
  cliente (não é destruído). Entrar de novo manda o estado completo no próximo snapshot.
- **Relevância** de objeto criado em jogo liga/desliga `Spawn`/`Despawn` para aquele cliente.
  Histerese: só sai depois de `raio × 1,1` (configurável). Objeto do próprio cliente (dono) e
  "sempre relevante" ignoram distância. Sem `setClientView` (ou raio ≤ 0) tudo é relevante.
- **Ordem:** o `Spawn` (canal 0) é enviado antes do primeiro snapshot que cita o objeto. Em ENet os
  canais não têm ordem entre si; se o snapshot chegar antes do `Spawn` e o objeto tiver propriedades,
  o decode falha (sem esquema), o snapshot não recebe ack e o servidor reenvia o objeto depois. Sem
  propriedades, o estado fica no buffer e só é aplicado quando o objeto existir.
- **Snapshot vazio é enviado** mesmo sem mudanças (cabeçalho de 11 bytes: tipo, tamanho, dois ticks e
  contagem 0), para o cliente continuar recebendo ticks e confirmando. "Objeto parado = 0 bytes" vale
  por objeto.
- **Orçamento de banda:** balde de tokens por cliente (`bytesPerSecond`, padrão 64 KB/s, capacidade
  máx(2 × 1200, taxa/4)). Spawn/Despawn/Ownership gastam do mesmo balde (podem deixá-lo negativo,
  porque são confiáveis); com menos de 32 bytes o snapshot do tick é pulado.
- **Prioridade:** cada objeto mudado soma `priority` ao acumulador do cliente a cada snapshot em que
  espera; entra primeiro o maior acumulador, que zera ao ser enviado. O tamanho é estimado pelo
  encode completo do objeto (limite superior do delta) e o pacote é cortado até caber em
  `min(1200, tokens)`.
- **Remoções:** até 256 por snapshot; as outras ficam como no baseline e saem nos seguintes.
- **Mudança detectada por hash** (FNV-1a 64) dos campos quantizados de cada objeto, calculado uma vez
  por tick. Colisão de hash (2^-64) faria um objeto não ser enviado até a próxima mudança.
- **Objeto dormindo** (`IWorld::isSleeping`): o servidor não relê o estado; o último capturado vale.
- **Reconexão:** `ClientJoined` (inclusive com `reconnected`) reinicia a replicação do cliente: todos os
  `Spawn` de novo e snapshot completo. No cliente, `Spawn` de objeto que já existe só atualiza estado
  e dono.
- **Fim da janela de reconexão** (`ClientExpired`): objetos do cliente criados em jogo sofrem despawn
  (`despawnOnExpire`, padrão) e os de cena voltam para o servidor.
- **Cliente:** descarta snapshot com tick não mais novo que o último aceito (também no WebSocket);
  baseline ausente → `FullStateRequest` (no máximo 1 por segundo); ack (`SnapshotAck`, canal 3) de
  cada snapshot aceito. O buffer (`NET_SnapshotBuffer`) guarda os 64 últimos e serve de baseline.
- **Animação** não é replicada ainda (campo provisório da frente A).
- Violações por ack inválido não são contadas: `ServerSession` não expõe isso; proposta: um
  `ServerSession::reportViolation(ClientId)` para a frente G usar também.

## Benchmark (`net_bench`)

16 clientes, 300 objetos dinâmicos (todos se movendo a cada tick), 30 Hz, 75 ms de latência em cada
ponta (150 ms RTT), 2% de perda, 10 s medidos depois de 2 s de aquecimento. CPU = `ServerSession::update`
+ `Replicator::update` por tick. Build Release (GCC 13, `-O3`), container Linux x64 da sessão.

| Cenário | CPU servidor por tick (média / pior) | Banda por cliente (média / máx) | Meta |
|---|---|---|---|
| Tudo relevante | 1,01 ms / 1,81 ms | 32,2 / 32,2 KB/s | < 1 ms, < 40 KB/s |
| Raio de relevância 60 m | 0,64 ms / 0,85 ms | 22,5 / 29,6 KB/s | idem |

- A banda fica abaixo da meta porque o pacote de 1200 bytes a 30 Hz limita em ~35 KB/s.
- Com tudo relevante a CPU fica no limite da meta (300 objetos mudando todo tick para 16 clientes); o
  custo restante é cópia do estado enviado (histórico por cliente) e encode. Em build sem otimização
  (padrão do build isolado) os números são ~5× maiores.
