# Tarefas de multiplayer para sessões na nuvem

Criado em 2026-10-03. Instruções prontas para disparar sessões do Claude Code na nuvem (frentes A–D do
[`multiplayer-plan.md`](multiplayer-plan.md)). Rodada 1 (A–D) concluída e na `main` em 2026-10-03. Rodada 2 (E–J) no fim deste arquivo.

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

---

# Rodada 2: frentes E–J (2026-10-03)

Esta rodada cobre tudo o que dá para fazer sem compilar a engine. O que mexe em `KX_`, DNA, conversor,
Python embutido, painéis e logic bricks fica para o trabalho local (lado da engine nas etapas 2–6 do
plano).

- As frentes são **independentes**. Podem rodar ao mesmo tempo (uma sessão por frente) ou em sequência
  numa sessão só, na ordem E → F → G → H → I → J.
- Cada frente cria arquivos novos. No `CMakeLists.txt` do `Network/`, só **acrescente linhas** em `NET_SRC`
  e na lista de testes, em ordem alfabética. Não reorganize o arquivo; o merge local resolve o resto.
- O contrato foi atualizado: veja a seção 11 de `docs/multiplayer-protocol.md` (interpretações aceitas na
  rodada 1).
- Se a frente precisar de mensagem nova ou de mudar um formato, não mexa em `NET_Messages`. Proponha a
  mudança em `NOTES-<frente>.md` e implemente com um tipo novo `>= 200`, marcado como provisório.
- Cole sempre o bloco "Regras comuns" acima junto com o texto da frente.

## Frente E: replicação (`net/replication`)

```
Tarefa E (branch net/replication). Em source/source/gameengine/Network/, sem headers da engine:
- NET_Replicator.h/.cpp, lado servidor:
  - registro de objetos replicados: NetId, dono, esquema de propriedades, flag "sempre relevante" e
    prioridade base;
  - baseline por cliente a partir do SnapshotAck e snapshot delta por cliente;
  - objeto em repouso gasta 0 bytes depois do ack;
  - Spawn/Despawn/Ownership na ordem certa (o spawn sai antes do primeiro snapshot que cita o objeto);
  - FullStateRequest;
  - pacote <= 1200 bytes, com orçamento de banda por cliente (padrão 64 KB/s) e acumulador de
    prioridade (plano, seção 4).
- Relevância: grid espacial (tamanho de célula configurável), raio por cliente e "sempre relevante".
- Lado cliente: NET_ReplicaClient aplica Spawn/Snapshot/Despawn num mundo abstrato (callbacks), envia
  SnapshotAck, descarta snapshot mais antigo que o último aceito (vale também no WebSocket) e alimenta
  o NET_SnapshotBuffer existente.
- Mundo abstrato: interface NET_IWorld em NET_IWorld.h (ler/escrever transform, velocidade,
  propriedades e "está dormindo"). A engine vai implementá-la depois com KX_GameObject.
- tests/, com servidor e 2 clientes sobre o transporte simulado com semente fixa:
  - o delta leva só os campos que mudaram;
  - objeto parado não gasta bytes depois do ack;
  - com 10% de perda, o estado converge;
  - o orçamento de banda é respeitado;
  - a relevância liga e desliga o spawn conforme a distância;
  - um cliente que reconecta recebe o estado completo.
- tools/net_bench.cpp: 16 clientes, 300 objetos dinâmicos, 30 Hz, transporte simulado com 150 ms e
  2% de perda. Imprime a CPU por tick do servidor e os KB/s por cliente, comparando com as metas da
  seção 4 do plano. Registre os números em NOTES-E.md.
```

## Frente F: predição, lag compensation e relógio (`net/prediction`)

```
Tarefa F (branch net/prediction). Em source/source/gameengine/Network/, sem headers da engine:
- NET_Prediction.h/.cpp, lado cliente:
  - buffer de inputs por tick, enviando os 8 últimos em cada pacote (seção 7);
  - reconciliação ao receber o estado do servidor, com um callback "reaplicar input N" fornecido
    pelo jogo;
  - correção suavizada: o erro decai em X ms em vez de saltar; acima de um limite, teleporta.
- NET_Prediction, lado servidor:
  - fila de input por cliente; cada tick é aplicado uma vez e em ordem, e os repetidos são descartados;
  - quando falta input, repete o último por no máximo N ticks;
  - conta os inputs atrasados.
- NET_LagCompensation.h/.cpp:
  - histórico de ~1 s de transforms das hitboxes por tick (esfera, cápsula e AABB orientada);
  - rebobinar para um tick fracionário e fazer raycast contra o histórico;
  - limite máximo de rebobinar configurável (anti-abuso).
- NET_Clock.h/.cpp: offset do relógio do servidor e interp_delay adaptativo ao jitter (plano, seção 5),
  usando as amostras de Ping/Pong que a sessão já tem.
- tests/:
  - personagem simples (integração de velocidade) predito com 150 ms e 2% de perda no simulado: erro
    final < 1 cm e nenhum salto acima do limite;
  - o raycast acerta o alvo onde o cliente o viu;
  - interp_delay sobe com jitter e desce quando a rede melhora.
```

## Frente G: RPC (`net/rpc`)

```
Tarefa G (branch net/rpc). Em source/source/gameengine/Network/, sem headers da engine:
- NET_RPC.h/.cpp:
  - registro por nome, com rpcId = índice na tabela ordenada (seção 8);
  - alvos Server/Owner/All/Others, flag "exige dono", confiável ou não;
  - despacho com os argumentos já decodificados (use os tipos de NET_Messages);
  - o servidor checa alvo e dono e conta violação para a sessão;
  - o limite de 120 RPC/s já existe na sessão: integre com ele, não duplique.
- Relay: RPC de cliente para All/Others passa pelo servidor.
- tests/:
  - tabela ordenada igual no cliente e no servidor;
  - RPC recusado por alvo e por dono;
  - Others não volta para quem chamou;
  - argumentos no limite de 1024 bytes;
  - RPC em objeto já despawnado é descartado.
```

## Frente H: descoberta LAN (`net/lan`)

```
Tarefa H (branch net/lan). Em source/source/gameengine/Network/:
- NET_LanDiscovery.h/.cpp:
  - o servidor responde a broadcast UDP numa porta própria (padrão 7779) com nome, gameId,
    gameVersion, jogadores/máximo, portas ENet e WebSocket e se tem senha;
  - o cliente envia o pedido e junta as respostas, com ping medido;
  - formato com magic e versão próprios, documentado em NOTES-H.md como proposta para o contrato;
  - use NET_Socket.h (já tem winsock2/POSIX); só IPv4.
- Limites: resposta <= 512 bytes, rate limit por IP, pedidos de outro gameId são ignorados.
- net_echo: "net_echo lan" lista os servidores achados em 2 s, e o servidor do net_echo responde.
- tests/:
  - descoberta em 127.0.0.1: broadcast no loopback quando o SO permitir; senão, unicast para
    127.0.0.1 com a mesma API;
  - filtro por gameId;
  - pacote truncado ou com tamanho mentiroso não crasha.
```

## Frente I: menu, telas restantes (`net/menu2`)

```
Tarefa I (branch net/menu2). Em tools/net_menu/ (veja NOTES-D.md):
- Telas de Pausa, Configurações completas e Servidores LAN (plano, seção 6.4). A tela LAN usa
  discover_lan() do stub, com o mesmo formato de resposta da frente H (nome, jogadores/máx, ping, senha).
- Atualize net_api_stub.py com descoberta LAN simulada, chat, ready e start_game.
- Escreva em NOTES-D.md a API Python final que o menu espera de Range.network (funções, eventos e
  atributos de cliente), como lista para a implementação local.
- tests/: pytest das telas novas, navegação por teclado e gamepad nelas, idiomas en/pt/es completos.
```

## Frente J: CI, Web e Docker (`net/ci`)

```
Tarefa J (branch net/ci). Arquivos: .github/workflows/network.yml e o que precisar em
source/source/gameengine/Network/ (só build e teste, sem mudar comportamento):
- Workflow do GitHub Actions, disparado só por mudanças em source/source/gameengine/Network/**,
  source/extern/enet/** e tools/net_menu/**:
  - build isolado + ctest no ubuntu (gcc e clang) e no windows (MSVC);
  - pytest do tools/net_menu;
  - docker build do tools/net_server/Dockerfile.
- Emscripten (emsdk pela ação mymindstorm/setup-emsdk ou instalado no próprio ambiente):
  - compile ge_network com emcmake, incluindo NET_TransportWebClient.cpp com -lwebsocket.js;
  - rode os testes do núcleo (bitstream, mensagens, snapshot, golden) em node, conferindo que a saída
    é a mesma em x64 e wasm32 (etapa 0);
  - deixe desligados no wasm os testes de socket e ENet.
- Cliente web contra o net_echo: um programa wasm mínimo que conecta via WebSocket, manda Hello e
  3 Chat e confere o eco. Rode com node + pacote "ws" se der; senão, documente o teste manual no
  navegador em NOTES-J.md.
- Antes do push, tente rodar tudo no ambiente da sessão (instale emsdk e docker se possível). O que não
  der, documente em NOTES-J.md.
```

## Texto para mandar à sessão na nuvem

```
Faça git pull da main. Leia AGENTS.md, docs/multiplayer-plan.md, docs/multiplayer-protocol.md e
docs/multiplayer-cloud-tasks.md. Execute as frentes da "Rodada 2" na ordem E, F, G, H, I, J, cada uma
na sua branch criada a partir da main, seguindo as "Regras comuns". Quando os testes de uma branch
passarem, faça push dela e só então comece a próxima. Não faça merge na main.
```
