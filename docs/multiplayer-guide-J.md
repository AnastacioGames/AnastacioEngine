# Guia de CI, Web e Docker do núcleo de rede (frente J)

Criado em 2026-10-04. Para quem mantém o núcleo `Network/` e vai ligar o export Web. O que rodou e o que
falta: `source/source/gameengine/Network/NOTES-J.md`.

## O que existe

| Peça | Para quê |
|---|---|
| `.github/workflows/network.yml` | Build e testes do núcleo em Linux (gcc, clang), Windows (MSVC) e wasm32; `pytest` do menu; build da imagem do servidor. Roda só quando os arquivos de rede mudam. |
| Bloco `EMSCRIPTEN` no `CMakeLists.txt` | `-lwebsocket.js` no `ge_network`; testes do núcleo no node com os golden lidos do disco. |
| `tools/net_web_echo.cpp` | Cliente wasm mínimo: WebSocket, `Hello`, 3 `Chat`, confere o eco. Modelo de loop para o export Web. |
| `tools/web_echo_test.sh` | Sobe o `net_echo` nativo e roda o cliente wasm no node. |

## Rodar localmente

```sh
# Nativo
cmake -S source/source/gameengine/Network -B build-net -DNET_STANDALONE=ON
cmake --build build-net -j && ctest --test-dir build-net --output-on-failure

# wasm32 (emsdk ativo: source emsdk/emsdk_env.sh)
emcmake cmake -S source/source/gameengine/Network -B build-wasm -DNET_STANDALONE=ON -DCMAKE_BUILD_TYPE=Release
cmake --build build-wasm -j && ctest --test-dir build-wasm --output-on-failure

# Cliente web contra o servidor de eco (node 22 ou mais novo)
source/source/gameengine/Network/tools/web_echo_test.sh build-net/net_echo build-wasm/net_web_echo.js

# Imagem do servidor
docker build -f source/source/gameengine/Network/tools/net_server/Dockerfile -t anastacio-net-server .
docker run --rm -p 7777:7777/udp -p 7778:7778 anastacio-net-server
```

## Loop no export Web (modelo do `net_web_echo`)

No navegador o código não pode ficar num `while` com `sleep`: os callbacks do WebSocket só rodam quando o
controle volta ao JavaScript. O jogo registra um quadro e retorna:

```cpp
#include <emscripten.h>
#include "NET_Session.h"
#include "NET_TransportWeb.h"

static void frame(void *arg)
{
	Game &game = *static_cast<Game *>(arg);
	std::vector<net::SessionEvent> events;
	game.session->update(net::steadyClockMs(), events);
	/* tratar eventos, simular, renderizar */
}

int main()
{
	static Game game;
	game.transport = net::createWebClientTransport();  // nullptr fora do Emscripten
	game.session = std::make_unique<net::ClientSession>(*game.transport, clientConfig);
	game.session->connect("wss://jogo.exemplo.com/", 0, net::steadyClockMs());  // ou host + porta
	emscripten_set_main_loop_arg(frame, &game, 0, 1);  // 0 = requestAnimationFrame
}
```

Linkar com `-lwebsocket.js` (o `ge_network` já exporta essa opção no build Emscripten).

## Limites

| Item | Valor |
|---|---|
| Testes no wasm | só o núcleo (sem sockets nem ENet); suítes novas entram editando o filtro no `CMakeLists.txt` |
| emsdk | versão fixa em `EMSDK_VERSION` no workflow (6.0.11) |
| Node para o cliente web | 22 ou mais novo (`WebSocket` global) |
| Navegador | teste manual descrito em NOTES-J |
| Warnings | listados como aviso no job Linux, não falham o build |
