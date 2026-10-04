# Frente H: descoberta LAN

Criado em 2026-10-04. Branch `net/lan`. Arquivos: `NET_LanDiscovery.h/.cpp`, funções UDP em
`NET_Socket.h`, modo `lan` no `tools/net_echo.cpp`, `tests/NET_LanDiscovery_test.cpp`.

## Formato proposto para o contrato

UDP, IPv4, porta própria (padrão **7779**), little-endian, mesma notação da seção 5 (`str` = `varu`
comprimento + UTF-8). Fora do protocolo de jogo: não passa por `ITransport` nem pela sessão.

```
Pedido   (cliente → broadcast 255.255.255.255:7779 ou unicast)
  u32 magic = 'ALAN' (bytes 'A','L','A','N')
  u8  version = 1
  u8  kind = 1
  u32 nonce          ecoado na resposta (casa resposta e pedido, mede o ping)
  str gameId         ≤ 64 bytes

Resposta (servidor → endereço e porta de origem do pedido)
  u32 magic, u8 version = 1, u8 kind = 2, u32 nonce
  str gameId         ≤ 64 bytes
  u32 gameVersion
  str name           ≤ 64 bytes (nome da sala)
  str sceneName      ≤ 64 bytes
  u16 players
  u16 maxPlayers
  u16 enetPort       0 = sem ENet
  u16 webSocketPort  0 = sem WebSocket
  u8  flags          bit 0 = tem senha; outros bits = inválido na versão 1
```

- Pacote ≤ 512 bytes (com strings ≤ 64 bytes a resposta fica abaixo de 230). Decode estrito: magic, versão,
  tipo, tamanhos de string e bytes sobrando são conferidos; nada lê fora do buffer.
- O servidor só responde pedidos do seu `gameId` e limita a 4 respostas por segundo por IP (balde de tokens,
  até 256 IPs lembrados). O cliente descarta respostas de outro `gameId` ou com nonce que ele não mandou
  (guarda os 32 últimos).
- Nomes maiores que 64 bytes são cortados pelo servidor sem quebrar UTF-8.

## Interpretações e limites

- **Endereço:** o cliente lista o endereço de onde veio a resposta. Uma máquina com várias interfaces (ou
  pedido por broadcast + `127.0.0.1`) aparece uma vez por endereço; a chave é endereço + portas.
- **Ping:** tempo entre o pedido e a resposta, medido no cliente com o relógio que o chamador passa.
- **Porta compartilhada:** o servidor abre a 7779 com `SO_REUSEADDR`, para mais de um servidor na mesma máquina
  ouvir o broadcast (o unicast vai para um só). No Windows o `SO_REUSEADDR` também deixa outro processo tomar
  a porta; aceitável numa LAN, a revisar se virar problema.
- **Teste em 127.0.0.1:** tenta broadcast `255.255.255.255`, depois `127.255.255.255`, depois unicast
  `127.0.0.1`, com a mesma API. Neste container o broadcast funcionou e a resposta veio do endereço da
  interface (não do `127.0.0.1`).

## Dúvidas para o contrato

1. **Amplificação:** a resposta (~70–230 bytes) é maior que o pedido (~25 bytes). O limite por IP segura, mas
   como o pedido é UDP sem handshake, dá para forjar a origem. Proposta: exigir pedido com pelo menos o tamanho
   da resposta (preenchimento com zeros) numa versão 2.
2. `name` vem de onde na engine? Proposta: `Server Name` nas configurações de rede da cena (painel), com padrão
   = nome do computador.
