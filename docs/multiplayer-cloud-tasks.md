# Tarefas de multiplayer para sessões na nuvem

Criado em 2026-10-03. Instruções prontas para disparar sessões do Claude Code na nuvem (frentes A–D do
[`multiplayer-plan.md`](multiplayer-plan.md)). Status: aguardando liberação do usuário e push da `main`.

## Pré-requisitos (antes de disparar)

1. `main` com commit e push no GitHub, contendo `docs/multiplayer-plan.md`, `docs/multiplayer-protocol.md`
   e este arquivo.
2. Repositório conectado em claude.ai/code.
3. Cada sessão recebe o texto da sua seção abaixo + o bloco "Regras comuns".

## Regras comuns (colar em toda sessão)

```
Repositório AnastacioEngine (fork da Range Engine/UPBGE, C++17, CMake).
Leia antes: AGENTS.md, docs/multiplayer-plan.md, docs/multiplayer-protocol.md (contrato; fonte única).

- Trabalhe só nos arquivos listados na sua tarefa. Não edite nada fora de
  source/source/gameengine/Network/ (ou do caminho indicado), nem docs/roadmap.md ou docs/changelog.md.
- O núcleo Network/ não inclui headers da engine (KX_, SCA_, DNA_, Python, CM_).
- Build isolado: cmake -S source/source/gameengine/Network -B build-net -DNET_STANDALONE=ON
  && cmake --build build-net -j && ctest --test-dir build-net --output-on-failure
  NÃO tente compilar a engine inteira.
- Se o contrato estiver ambíguo ou errado, não invente: escreva a dúvida em
  source/source/gameengine/Network/NOTES-<frente>.md e siga a interpretação mais conservadora.
- Estilo: tabs, nomes como no contrato, comentários curtos em inglês como o resto do código C++.
- Pronto = todos os testes passam no build isolado, sem warnings novos com -Wall -Wextra.
- Commits pequenos na branch indicada; no fim, push da branch. Não faça merge na main.
- Não altere licenças. Bibliotecas de terceiros só as listadas na tarefa.
```

## Ordem e dependências

- **A** cria o `CMakeLists.txt` do núcleo, `NET_Types.h` e `NET_BitStream`. **B, C e D podem começar ao
  mesmo tempo**: B e C criam seus próprios arquivos e, se o `CMakeLists.txt` de A ainda não existir na
  branch deles, criam um mínimo com o mesmo nome de alvo (`ge_network`, `net_tests`); o merge resolve.
- Merge local, nesta ordem: A → B → C → D.

## Frente A: bitstream, mensagens e snapshots (`net/core`)

```
Tarefa A (branch net/core). Implemente em source/source/gameengine/Network/:
- CMakeLists.txt: biblioteca ge_network; com NET_STANDALONE=ON também add_subdirectory de
  source/extern/gtest e executável net_tests registrado no ctest. Sem NET_STANDALONE, só a biblioteca
  (será incluída pela engine depois; não edite os CMakeLists da engine).
- NET_Types.h (seções 2, 3 e enums da 5 do contrato).
- NET_BitStream.h/.cpp (seção 9.1 e 6.1), incluindo writePosition/readPosition e smallest-three.
- NET_Messages.h/.cpp: encode/decode de todas as mensagens da seção 5 e o cabeçalho da 4.3.
- NET_Snapshot.h/.cpp: estrutura de snapshot (seção 6), encode/decode com delta contra baseline,
  NET_SnapshotBuffer com interpolação linear de posição e slerp de rotação por tick fracionário.
- tests/: todos os testes da seção 10 que não envolvem transporte, com vetores dourados em tests/golden/
  gerados uma vez e comparados byte a byte.
```

## Frente B: transportes e sessão (`net/transport`)

```
Tarefa B (branch net/transport). Implemente em source/source/gameengine/Network/:
- Vendorize ENet (github.com/lsalzman/enet, licença MIT, última release estável) em
  source/extern/enet/ com CMakeLists.txt próprio (biblioteca extern_enet) e o arquivo de licença.
- NET_ITransport.h (seção 9.2), NET_TransportLoopback.cpp, NET_TransportENet.cpp (canais da 4.1 mapeados
  para canais ENet; Control/Rpc confiáveis, Snapshot/Input unsequenced/unreliable),
  NET_TransportSimulated.cpp (latência, jitter, perda, duplicação, semente fixa).
- NET_Session.h/.cpp: máquina de estados de servidor e cliente sobre ITransport: Hello/Welcome/Reject,
  Ping/Pong com RTT por EMA, timeouts e limites da 4.2, reconexão por token (5.1), contagem de violações.
  Pode usar NET_BitStream/NET_Messages se já existirem; se não, implemente só a camada de sessão com uma
  interface mínima de encode e deixe NOTES-B.md explicando o encaixe.
- tests/: loopback e simulado com semente fixa (entrega, perda, ordem); sessão completa servidor+2 clientes
  em loopback; ENet em 127.0.0.1 com porta efêmera; timeout; rejeição por versão e por servidor cheio.
- Ferramenta de linha de comando net_echo (servidor/cliente) para teste manual.
```

## Frente C: servidor dedicado com WebSocket (`net/server`)

```
Tarefa C (branch net/server). Implemente:
- source/source/gameengine/Network/NET_TransportWebSocketServer.cpp: lado servidor de WebSocket (RFC 6455:
  handshake HTTP, frames binários, ping/pong, close), sem dependência externa além de sockets do SO
  (Windows: winsock2; Linux: POSIX). Um byte de canal no início de cada mensagem (seção 4.1).
  Implementa ITransport com reliableAll() = true.
- NET_TransportMulti.cpp: junta vários ITransport de servidor (ENet + WebSocket) num só, para cross-play.
- NET_TransportWebClient.cpp: lado cliente para Emscripten (emscripten/websocket.h), compilado só com
  __EMSCRIPTEN__; no build isolado, só precisa compilar fora desse define (stub vazio).
- tools/net_server/Dockerfile e README curto: imagem Linux com o net_echo/servidor da frente B escutando
  ENet (UDP) e WebSocket (TCP) nas portas configuráveis.
- tests/: handshake WebSocket com cliente de teste escrito no próprio teste; frames fragmentados;
  frame acima do limite da 4.2 rejeitado; multi-transporte entregando eventos dos dois lados.
TLS (WSS) fica fora: documente em NOTES-C.md como colocar um proxy reverso (Caddy/nginx) na frente.
```

## Frente D: menu ImGui em Python (`net/menu`)

```
Tarefa D (branch net/menu). Implemente em source/release/scripts/... (procure onde ficam os módulos
Python do jogo, ex. Range/; se houver dúvida, use tools/net_menu/ e explique em NOTES-D.md):
- net_menu.py: componente KX_PythonComponent "NetworkMenu" com as telas da seção 6.4 do plano, usando só
  Range.imgui (funções existentes: begin, end, text, button, checkbox, slider_float, slider_int,
  input_text, combo, listbox, radio_button, open_popup, begin_popup_modal, end_popup,
  close_current_popup, push_style_color, pop_style_color, load_font, push_font, pop_font,
  get_display_size, draw_rect_filled, separator, same_line, set_next_window_pos,
  set_next_window_size, image, invisible_button, set_cursor_pos, get_cursor_pos,
  get_cursor_screen_pos, get_io_want_capture_mouse, get_io_want_capture_keyboard, set_game_ui_open).
  Confira as assinaturas reais em source/source/gameengine/Ketsji/KXImgui/KX_PythonImgui.cpp.
- Chama só a API Python da seção 6.2 do plano (Range.network: host, join, disconnect, isServer, clients,
  eventos). Como ela ainda não existe, crie net_api_stub.py que simula conexão, lista de jogadores, ping e
  erros, e faça o menu importar o real quando existir e o stub caso contrário.
- Escala por tamanho de tela, botões ≥ 48 px no modo touch, teclado na tela para campos de texto,
  navegação por teclado/gamepad, textos em tabela por idioma (en, pt, es), tema configurável por args.
- tests/: testes pytest da lógica de telas (máquina de estados, validação de IP/porta/código de sala,
  tabela de idiomas completa) sem depender do Range (mock de Range.imgui).
```

## Depois das sessões (local)

1. `git fetch`, revisar cada branch, rodar o build isolado e os testes no Windows também.
2. Merge A → B → C → D na `main`.
3. Etapa E/F local: DNA, painéis, `KX_NetworkManager`, ligação do `ge_network` no CMake da engine.
