# Guia da descoberta LAN (frente H)

Criado em 2026-10-04. Para quem vai ligar a descoberta LAN do núcleo `Network/` na engine
(`KX_NetworkManager`, `Range.network.discover_lan()` e tela "Servidores LAN" do menu). Formato e
limites: `source/source/gameengine/Network/NOTES-H.md`.

## O que a API faz

| Peça | Lado | Papel |
|---|---|---|
| `net::LanResponder` | servidor | Ouve a porta UDP 7779 e responde aos pedidos do mesmo `gameId` com nome, cena, jogadores, portas ENet/WebSocket e se tem senha. Limita respostas por IP. |
| `net::LanDiscovery` | cliente | Manda o pedido por broadcast (ou para um endereço) e junta as respostas, com o ping medido. |
| `encodeLan*` / `decodeLan*` | ambos | O formato (magic `ALAN`, versão 1), para testes e ferramentas. |

Nada bloqueia: os dois têm `update(nowMs)`, chamado uma vez por frame.

## Exemplo: servidor

```cpp
#include "NET_LanDiscovery.h"

net::LanResponder lan;
if (!lan.start(net::kLanDiscoveryPort)) {
	/* porta ocupada: o jogo segue, só não aparece na LAN */
}
net::LanServerInfo info;
info.gameId = serverConfig.gameId;
info.gameVersion = serverConfig.gameVersion;
info.name = "Sala do Fábio";
info.sceneName = serverConfig.sceneName;
info.maxPlayers = uint16_t(serverConfig.maxClients);
info.enetPort = 7777;
info.webSocketPort = 7778;
info.password = !password.empty();

// A cada frame:
info.players = uint16_t(session.clients().size());
lan.setInfo(info);
lan.update(nowMs);
```

## Exemplo: cliente (tela "Servidores LAN")

```cpp
net::LanDiscovery lan;
lan.start();

// Ao abrir a tela e a cada ~1 s:
lan.request(gameId, nowMs);  // broadcast 255.255.255.255:7779
// A cada frame:
lan.update(nowMs, 5000);  // some da lista quem não responde há 5 s
for (const net::LanServerEntry &s : lan.servers()) {
	// s.address, s.info.name, s.info.players / s.info.maxPlayers, s.pingMs, s.info.password
}
// Entrar: clientSession.connect(s.address, s.info.enetPort, nowMs);
```

Na Web (wasm) não há UDP: a tela LAN fica escondida.

## Ferramenta

`net_echo server` responde na 7779; `net_echo lan [segundos]` lista o que achou:

```
2 server(s) found
  127.0.0.1       net_echo             0/64 players, ENet 17777, WebSocket 0, open, ping 5 ms
  192.0.2.2       net_echo             0/64 players, ENet 17777, WebSocket 0, open, ping 5 ms
```

## Limites

| Item | Valor |
|---|---|
| Rede | IPv4, UDP, porta 7779 (configurável) |
| Pacote | ≤ 512 bytes; strings ≤ 64 bytes (servidor corta nomes maiores) |
| Respostas | 4 por segundo por IP no servidor |
| Lista no cliente | até 256 servidores; um por endereço + portas (máquina com 2 interfaces aparece 2 vezes) |
| Filtro | servidor e cliente ignoram outro `gameId` |
| Web | sem suporte (navegador não tem UDP) |
