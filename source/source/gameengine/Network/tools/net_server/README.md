# net_server

Linux image with the `net_echo` server (frente B session + frente C transports): ENet on UDP and
WebSocket on TCP, both feeding the same `ServerSession` (cross-play).

Build from the repository root:

```sh
docker build -f source/source/gameengine/Network/tools/net_server/Dockerfile -t anastacio-net-server .
```

Run with the default ports (UDP 7777, TCP 7778):

```sh
docker run --rm -p 7777:7777/udp -p 7778:7778/tcp anastacio-net-server
```

Other ports: set `UDP_PORT` and `WS_PORT` and publish the same ones (`WS_PORT=0` turns WebSocket off):

```sh
docker run --rm -e UDP_PORT=9000 -e WS_PORT=9001 -p 9000:9000/udp -p 9001:9001/tcp anastacio-net-server
```

Native client test: `net_echo client <host> 7777 name 3`. Browsers connect to `ws://<host>:7778/`;
for `wss://` put a TLS reverse proxy in front (see `NOTES-C.md`). Stop with Ctrl+C or `docker stop`
(SIGTERM sends `Disconnect(ServerShutdown)` to everyone).
