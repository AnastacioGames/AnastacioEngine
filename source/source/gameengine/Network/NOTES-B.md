# Notas da frente B (`net/transport`)

Interpretações onde o contrato era omisso (seguindo a mais conservadora).

- **ENet 1.3.18** (última release estável, MIT) em `source/extern/enet/`, alvo `extern_enet`. Como não
  posso editar os CMakeLists da engine, o `CMakeLists.txt` do `Network/` faz `add_subdirectory` do ENet
  se o alvo ainda não existir.
- `ITransport` ganhou `virtual uint16_t localPort() const` com implementação padrão (retorna 0), para
  descobrir a porta efêmera depois de `listen(0)`. É uma adição, os métodos do contrato não mudaram.
- `NetSimSettings` ganhou `clock` (função de tempo em ms) para os testes usarem relógio falso.
- Loopback: além do `createLoopbackPair` do contrato, há `createLoopbackHub()` +
  `createLoopbackTransport(hub)` para ter um servidor e vários clientes na memória. O loopback entrega
  tudo, mas responde `reliableAll() = false` porque mantém os canais (assim o simulador pode descartar
  os não confiáveis).
- Simulado: perda e duplicação só nos canais não confiáveis (Snapshot/Input); latência/jitter em tudo, com
  ordem preservada por peer nos canais confiáveis e nos eventos de conexão. Atua no lado que recebe;
  envolver as duas pontas simula os dois sentidos.
- ENet: Control/Rpc `RELIABLE`, Snapshot/Input `UNSEQUENCED`. Payload não confiável > 1200 bytes e
  confiável > 65 536 bytes são descartados no envio. `disconnect()` usa `enet_peer_disconnect_later`
  (entrega o `Reject` antes de cair) e gera o evento `Disconnected` na hora.
- Sessão (`NET_Session`): tempo vem do chamador (`update(nowMs, ...)`). O servidor escuta com
  `maxClients + 16` peers, para conseguir mandar `Reject ServerFull`.
  - Ordem das checagens no `Hello`: versão/gameId/gameVersion → banido (por token) → cena → token já
    conectado (`BadToken`) → reconexão → cheio → partida em andamento.
  - Slot de reconexão (30 s) só para queda/timeout de cliente com token ≠ 0. `Quit`, `Kicked` e violação
    não guardam slot. Ids reservados não são dados a novos jogadores enquanto o slot existe.
  - O destrutor do `ClientSession` não manda `Quit` (conta como queda); `disconnect()` manda.
  - Ping/Pong: os dois lados pingam a cada 1 s em canal não confiável (servidor no 2, cliente no 3).
    RTT por EMA alfa 0,1 (primeira amostra entra direto). O cliente estima o tick do servidor pelo
    `Pong.serverTick` + meio RTT.
  - Violações: mensagem só de servidor vinda do cliente, `Hello` repetido, corpo inválido, pacote mal
    formado, mais de 120 RPC/s, mais de 64 KB/s, não confiável > 1200 bytes. 10 em 10 s =
    `Disconnect ProtocolViolation`.
  - Mensagens que a sessão não trata (Input, Rpc, Chat, SnapshotAck, FullStateRequest, Spawn, Snapshot...)
    sobem como evento `Message` para a camada de replicação.
- `net_echo` (manual): `net_echo server [porta]` e `net_echo client <host> <porta> [nome] [n]`; o servidor
  reenvia os `Chat` para todos. Testado em 127.0.0.1 no Linux.
