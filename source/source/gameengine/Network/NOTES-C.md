# Notas da frente C (`net/server`)

Pontos em que o contrato ou a tarefa deixavam margem, e a interpretação adotada (a mais conservadora).

## WebSocket (servidor)

- Arquivos: `NET_TransportWebSocketServer.cpp` (servidor), `NET_Socket.h` (sockets TCP não bloqueantes,
  winsock2/POSIX, interno) e `NET_TransportWeb.h` (fábricas). SHA-1 e base64 do handshake são próprios
  (nenhuma biblioteca nova).
- Mensagem = **um frame binário** (ou fragmentos `binary` + `continuation`) cujo primeiro byte é o canal
  (0–3). O limite da 4.2 vale para a mensagem montada: 1 byte de canal + 65 536 = `kMaxWebSocketMessage`
  (65 537). Acima disso: close **1009**, checado já no cabeçalho do frame (não espera chegar o payload) e na
  soma dos fragmentos. Pacotes não confiáveis acima de 1200 bytes passam no WebSocket (é tudo confiável);
  quem limita isso é a sessão.
- Erros de protocolo do cliente → close com código e o TCP é fechado logo depois de enviar o close, sem
  esperar resposta (RFC 6455 7.1.7):
  - frame sem máscara, bits RSV ligados (sem extensões), opcode desconhecido, controle fragmentado ou
    com mais de 125 bytes, `continuation` sem início, novo `binary` no meio de fragmentos, mensagem vazia
    ou canal ≥ 4 → **1002**;
  - frame de texto → **1003** (o protocolo é só binário).
- Handshake: exige `GET ... HTTP/1.1`, `Upgrade: websocket`, `Connection` com o token `upgrade`,
  `Sec-WebSocket-Key` de 24 caracteres e `Sec-WebSocket-Version: 13`. Falha → `400` (versão errada →
  `426` com `Sec-WebSocket-Version: 13`), cabeçalho acima de 8 KB → `431`; nos dois casos o TCP fecha.
  Path, `Host`, `Origin` e subprotocolos são ignorados (não há checagem de `Origin`: o servidor não usa
  cookies; se precisar, é no proxy). Handshake não concluído em 5 s (timeout de pendente da 4.2) fecha.
- `Connected` só sai depois do `101`. Conexões TCP acima de `maxPeers` (contando as em handshake) são
  fechadas na hora; a `ServerSession` escuta com `maxClients + 16`.
- `ping` → `pong` com o mesmo payload (também entre fragmentos); `pong` é ignorado. O servidor não manda
  ping próprio: o `Ping` da sessão (seção 5) já mede RTT e derruba por timeout de 10 s.
- `disconnect()` envia close **1000**, reporta `Disconnected` na hora (como o ENet) e espera o close do
  cliente por até 2 s antes de fechar o TCP. Close do cliente: eco do código, `Disconnected`, fecha.
  `shutdown()` manda close **1001** a todos e fecha sem eventos.
- Quadros do servidor nunca são mascarados nem fragmentados. Se o buffer de saída de um cliente passar
  de 4 MB (cliente que não lê), a conexão cai com `Disconnected`.
- Leitura limitada a 256 KB por cliente por `poll()`, para um cliente não monopolizar o loop.
- Só IPv4 (`INADDR_ANY`). IPv6 fica para depois (o ENet da frente B também está em IPv4).

## Multi-transporte

- `createMultiTransport({ {transport, port}, ... })`: `listen(port, maxPeers)` chama cada transporte com
  a sua porta (ou com `port` se a da entrada for 0). Se um falhar, todos são desligados e retorna `false`.
- `maxPeers` vale para cada transporte (o total pode passar); quem limita jogadores é a sessão
  (`maxClients`, `Reject ServerFull`).
- PeerIds externos são novos e únicos; o mapeamento some no `Disconnected` do transporte interno.
- `reliableAll() = false` (o mais restritivo): a sessão aplica o limite de 1200 bytes nos canais não
  confiáveis para todo mundo, mesmo para quem está no WebSocket.
- `localPort()` devolve a do primeiro transporte (o ENet); para a porta WebSocket, guarde o ponteiro do
  transporte antes de passá-lo (é o que o `net_echo` e os testes fazem).
- Contrato 4.1 diz que, no WebSocket, "o receptor ainda descarta snapshot/input mais antigo que o último
  aceito": isso é da sessão/replicação (frente E), não do transporte, que entrega tudo em ordem.

## Cliente web (Emscripten)

- `NET_TransportWebClient.cpp` usa `emscripten/websocket.h`; fora de `__EMSCRIPTEN__`,
  `createWebClientTransport()` devolve `nullptr`. `connect(host, port)` monta `ws://host:port/`; se `host`
  já for uma URL `ws://` ou `wss://`, usa ela como está (é assim que o navegador chega no proxy TLS).
- Falha de conexão (erro antes do `open`) gera `Disconnected`, para a sessão sair de `Connecting` logo.
- **Não compilado aqui** (não há emsdk no ambiente). Falta compilar com `emcmake` e testar no navegador
  contra o `net_echo`; precisa de `-lwebsocket.js` no link.

## Docker

- `tools/net_server/Dockerfile` (multi-stage, Ubuntu 24.04) compila só o `net_echo` com
  `NET_STANDALONE=ON` e roda `net_echo server $UDP_PORT $WS_PORT` como usuário sem privilégio.
- O daemon do Docker não está disponível neste ambiente: a imagem **não foi construída aqui**. Conferi só
  que a mesma lista de `COPY` (Network, extern/enet, extern/gtest) compila o `net_echo` numa pasta
  separada.

## TLS (WSS) com proxy reverso

O servidor fala só `ws://`. Navegadores em páginas `https://` exigem `wss://`, então o TLS fica num proxy
na frente, que termina o TLS e repassa o upgrade para a porta TCP do servidor (o UDP do ENet não passa
pelo proxy).

Caddy (certificado automático do Let's Encrypt):

```
game.exemplo.com {
	reverse_proxy /ws* 127.0.0.1:7778
}
```

nginx:

```
server {
	listen 443 ssl;
	server_name game.exemplo.com;
	ssl_certificate     /etc/letsencrypt/live/game.exemplo.com/fullchain.pem;
	ssl_certificate_key /etc/letsencrypt/live/game.exemplo.com/privkey.pem;

	location /ws {
		proxy_pass http://127.0.0.1:7778;
		proxy_http_version 1.1;
		proxy_set_header Upgrade $http_upgrade;
		proxy_set_header Connection "upgrade";
		proxy_read_timeout 60s;  # acima do timeout de 10 s da sessão
	}
}
```

O cliente web conecta em `wss://game.exemplo.com/ws`. Com o Docker, publique só a porta UDP para fora e
deixe a TCP 7778 acessível apenas ao proxy (ex.: `-p 127.0.0.1:7778:7778/tcp`).

## Testes (`tests/NET_WebSocket_test.cpp`)

- Cliente WebSocket mínimo escrito no próprio teste (TCP cru, frames mascarados), sobre `127.0.0.1` e
  porta livre (`listen(0)`).
- Cobertos: vetor do RFC 6455 para `Sec-WebSocket-Accept`; handshake, envio/recebimento nos 4 canais,
  ping/pong, close do cliente; handshakes inválidos (400/426/431); frames fragmentados (com ping no meio,
  com o TCP entregando 1 byte por vez, e a mensagem no limite exato); frame acima do limite e fragmentos
  somando acima do limite (1009); erros de protocolo (1002/1003); `disconnect` do servidor e limite de
  peers; multi-transporte com ENet + WebSocket entregando eventos dos dois lados; uma `ServerSession`
  com um cliente ENet e um cliente WebSocket (Hello/Welcome) ao mesmo tempo.
