# Revisão do multiplayer (frente 7)

Data: 2026-10-26. Frente 7 do [levantamento](levantamento-modulos-criticos.md). Caminho seguido:
pacote → mensagens → snapshot → sessão → replicação → cliente de réplica → `KX_NetworkManager`.

## Corrigido

| ID | Local | Problema | Correção |
|---|---|---|---|
| NET-01 | `NET_Session.cpp` — `closeConnection` | `Quit`, `Kicked` e violação não guardam slot de reconexão, mas também não geravam `ClientExpired`. Os objetos do jogador ficavam no mundo com dono inexistente; um jogador novo que recebesse o mesmo id herdava esses objetos. | `ClientExpired` sai sempre que não há slot. |
| NET-02 | `NET_Session.cpp` — `kick` | Os eventos `ClientLeft`/`ClientExpired` iam para uma lista descartada; a camada de cima nunca sabia do kick. | Ficam em `m_deferredEvents` e saem no próximo `update()`. |
| NET-04 | `NET_TransportENet.cpp` — host | O ENet aceita por padrão pacotes de 32 MiB e 32 MiB em espera por peer; a sessão só descartava acima de 64 KiB depois de o ENet montar tudo na memória. | `maximumPacketSize = kMaxReliableMessage` e `maximumWaitingData = 4 MiB` no host (servidor e cliente). |
| NET-03 | `KX_NetworkManager.cpp` — `ClientExpired` | O replicador devolve objetos de cena ao servidor, mas a entrada do manager mantinha o dono antigo: `ServerStepPredicted` aplicaria o input de um jogador novo com o mesmo id. | Entrada de cena volta para `kServerClientId`; as criadas em jogo continuam sendo removidas. |

Testes: `NetSession.FullHandshakeAndLobby` (Quit gera `ClientExpired`) e `NetSession.KickAndShutdown`
(kick gera `ClientLeft` + `ClientExpired`). `net_tests` 121/121.

## Conferido sem mudança

- **BitStream:** leitura além do fim marca erro e devolve zero; VarU limitado a 10 bytes, com o 10º
  só carregando 1 bit; NaN e quaternion degenerado tratados; posição de 32 bits cabe no offset.
- **Messages:** comprimento por mensagem com até 3 bytes, conferido contra o resto do pacote; enums de
  motivo validados; strings ≤ 255; RPC com limite de 1 KiB de argumentos; corpo precisa terminar no
  byte (`finish`).
- **Snapshot:** ids estritamente crescentes (delta 0 rejeitado), contagem limitada por bits restantes /
  9, propriedades novas exigem todos os valores; buffer circular e interpolação sem divisão por zero.
- **Sessão:** ordem das checagens do `Hello`, limite de pendentes, janela de bytes/RPC, timeout de
  pendente e de conectado, reconexão por token, ids reservados não reaproveitados.
- **Replicator:** o snapshot guardado como baseline reproduz exatamente o que o cliente reconstrói
  (inclusive remoções adiadas acima de 128); orçamento de banda; dono enviado na ativação.
- **RPC:** dono conferido no servidor, tipos de argumento validados, `fromClient` preenchido pelo
  servidor; alvo `Owner` recusado vindo do cliente e `Server` recusado vindo do servidor.
- **Predição:** fila de input limitada por `maxAheadTicks`; atrasado/duplicado contados à parte;
  repetição limitada; reconciliação com teleporte acima de `teleportDistance`.
- **Compensação de lag:** rewind preso entre 0 e `maxRewindMs`; tick futuro vira 0; raio contra
  esfera/cápsula/caixa conferido (origem dentro = distância 0).
- **WebSocket servidor:** tamanho checado antes do payload chegar, máscara obrigatória, controle
  ≤ 125 bytes, buffer de saída 4 MiB, sem `Disconnected` duplicado.
- **LAN:** pacote ≤ limite, nonce conferido, limite por endereço, no máximo 256 servidores na lista.
- **Multi:** mapeamento de peers por transporte some no `Disconnected` interno.
- **ReplicaClient:** descarta snapshot antigo, pede estado completo sem baseline (1/s), restaura o
  protótipo se o Spawn falha.

## Observações

- Floats crus de RPC e de animação (`frame`, `speed`) não são filtrados contra NaN/Inf no decode.
  Não há caminho demonstrado de crash; o jogo deve validar argumentos de RPC.
- `Pong.echoTimeMs` vem do cliente: um cliente pode inflar o próprio RTT medido pelo servidor.
  Esse valor só aparece como ping no lobby; a compensação de lag usa o tick de visão, limitado.
- `despawnOnExpire = false` não tem efeito no motor: o manager remove os objetos criados em jogo de
  qualquer forma. Nenhum código liga essa opção hoje.

- Steam e cliente WebSocket do navegador: só os caminhos de tamanho/canal foram conferidos (o Steam
  passa pela ABI do plugin, já validada por `NET_AnastacioPlugin_test`).

## Validação pendente

Host/cliente real com jogador saindo por Quit e outro entrando no mesmo id, para ver o avatar sumir
e o objeto de cena voltar ao servidor. Executáveis precisam de relink (runtime estava aberto).
