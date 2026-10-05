# Plano: Multiplayer nativo

Criado em 2026-10-03. Status: **implementação avançada, funcional e validada**.

O núcleo e a integração com a engine já estão implementados na main. Desktop/Linux, Windows/MSVC,
wasm32 e o runtime Web foram exercitados com cenários automatizados; o cliente Web também foi validado
em Chrome real contra um `RangeRuntime --server` nativo. Este documento continua sendo o plano de
arquitetura e o inventário de pendências, enquanto o estado factual mais recente fica no
[`roadmap.md`](roadmap.md) e os detalhes de cada sessão no [`changelog.md`](changelog.md).

Documentos ligados: contrato do formato e das interfaces em [`multiplayer-protocol.md`](multiplayer-protocol.md);
tarefas prontas para sessões na nuvem (frentes A–D, em paralelo com o trabalho local) em
[`multiplayer-cloud-tasks.md`](multiplayer-cloud-tasks.md).

Objetivo: multiplayer **dentro da engine** (C++), configurável pela UI sem código, com API Python curta
para quem quiser mais. Rodar em Desktop, Web e Android (APK WebView, mesmo caminho do Web) com o mesmo `.range`.

Escopo por versão (para não prometer antes da hora):

- **v1 (etapas 0–6):** implementada no Desktop: host/servidor dedicado, replicação de
  transform e propriedades com interpolação, spawn/ownership, RPC, UI, logic bricks e ferramentas de teste.
- **v1.1 (etapas 7–8):** implementada em grande parte: predição no cliente, compensação de lag,
  prioridade/orçamento de banda e relevância por distância.
- **v1.2 (etapas 9–10):** Web via WebSocket com cross-play implementado e validado; Android WebView,
  descoberta LAN completa e alguns itens de endurecimento ainda estão pendentes.

## 1. Por que nativo e não um SDK em Python

Um SDK em Python por cima da engine (caso do SDK anunciado para a Range) esbarra em limites que nós não temos:

| Problema do SDK em Python | Como resolvemos no núcleo |
|---|---|
| Socket e serialização rodam sob a GIL, no tempo do script | Thread de rede em C++; o loop só troca filas prontas |
| `pickle`/JSON: bytes demais por objeto | Bitstream binário com quantização e delta |
| Tick de rede depende de quando o script roda | Tick preso ao acumulador de passo fixo (`KX_KetsjiEngine::NextFrame`, Plano 8) |
| Sem acesso a rewind da física | Histórico de transforms no servidor para compensação de lag |
| Configuração só por código | Painel Network no objeto, flag "Replicated" na propriedade, logic bricks |
| Web não tem UDP | Abstração de transporte: ENet (nativo) e WebSocket (Web), WebTransport depois |

## 2. Decisões de arquitetura

1. **Servidor autoritativo + snapshots.** Bullet não é determinístico entre máquinas/compiladores, então
   lockstep ou rollback de física completa ficam fora. Modelo Quake 3 / Source: o servidor simula, envia
   snapshots com delta; clientes interpolam e predizem só o próprio jogador. [R1][R2][R5]
2. **Host e servidor dedicado com o mesmo código.** Servidor dedicado = blenderplayer sem janela
   (`--server`, sem rasterizer/áudio). Host = servidor + cliente local no mesmo processo, sem socket
   (transporte "loopback").
3. **Tick de rede = passo de lógica, com passo fixo obrigatório na sessão.** Hoje `m_useFixedTimestep`
   começa desligado (construtor de `KX_KetsjiEngine`). Contrato:
   - `KX_NetworkManager` chama `SetUseFixedTimestep(true)` ao abrir sessão (host, servidor ou join) e
     restaura o valor anterior ao sair. Jogos offline não mudam.
   - A taxa (`ticrate`) é do **servidor**: vai no handshake, o cliente adota e não pode mudá-la durante a
     sessão (`SetTicRate` avisa e ignora).
   - Cada passo fixo incrementa `tick` (u32). Snapshots, inputs e RPCs são carimbados com ele. Taxa de
     envio separada (ex.: lógica 60 Hz, snapshot 20–30 Hz).
   - Atraso: o acumulador já limita a `m_maxLogicFrame` passos por frame e descarta o excesso. No
     **servidor** o descarte é contado (overlay) e os ticks seguem contínuos; no **cliente**, se ficar mais de
     N ticks atrás, ressincroniza o relógio e pede snapshot completo em vez de tentar alcançar.
4. **Transporte trocável** (`NET_ITransport`):
   - `ENet` (MIT, C puro, pequeno) para Desktop (e Android NDK, se essa rota for reaberta): canais
     confiáveis e não confiáveis sobre UDP. [R9]
   - `WebSocket` (emscripten `websocket.h`) é **a** entrega Web e Android (o APK atual é WebView). O
     servidor precisa de um endpoint WebSocket próprio, porque ENet não atende navegador. WebTransport é
     evolução explícita posterior.
   - `Loopback` para host e testes automatizados.
   - Avaliado e não escolhido para a v1: GameNetworkingSockets (traz protobuf + OpenSSL, pesado para
     Android/Web) e yojimbo/netcode (ótimos, mas sem caminho Web). [R10][R11]
5. **Identidade de objetos:**
   - Objetos da cena marcados `Replicate` recebem `net_id` **gerado no editor e salvo no DNA** (u32
     aleatório; não muda ao renomear). Colisões são detectadas ao salvar e ao converter e corrigidas com
     aviso; duplicar objeto gera id novo.
   - O handshake compara um hash da lista de `net_id`s: cliente com `.range` diferente é recusado com
     mensagem clara.
   - Objetos criados em jogo (Add Object) recebem `NetId` do servidor (faixa separada), spawnados por
     mensagem com o nome do objeto de origem.
   - **Ciclo de vida** (no contrato da etapa 0): entrada com partida em andamento = snapshot completo
     (objetos relevantes, spawns vivos, propriedades) antes do primeiro delta; troca de cena só pelo
     servidor, com mensagem dedicada e espera do "carregado" de cada cliente; reconexão dentro de uma janela
     (ex.: 30 s) recupera o slot e os objetos possuídos; depois disso o servidor faz despawn ou transfere dono.
6. **Ownership:** cada objeto tem `authority` (Server) e opcionalmente `owner` (cliente). O owner manda
   input; o servidor decide estado. Transferência de dono por API e por actuator.

## 2.1 Web: o que o export Web existente aproveita

O export Web (Emscripten/WebGL) é a mesma engine compilada para o navegador. Por isso a replicação,
os snapshots, a predição, a UI e a API Python servem para o Web sem mudança. O que muda é só o **transporte**:
o navegador não abre sockets UDP e não aceita conexões, então:

- o jogo no navegador é sempre **cliente**. O servidor é um dedicado ou um host Desktop;
- o servidor dedicado escuta ENet (UDP) e WebSocket ao mesmo tempo. Assim, **jogadores do navegador,
  do Android (APK WebView) e do Desktop jogam juntos na mesma partida** (cross-play);
- primeira entrega: **WebSocket**. Evolução: **WebTransport** (HTTP/3 + QUIC, datagramas não confiáveis),
  mantendo WebSocket como fallback;
- WebRTC DataChannel fica só para P2P entre navegadores (um navegador como host), que não entra na v1.

## 2.2 Recursos modernos considerados

| Recurso | Uso aqui | Quando |
|---|---|---|
| WebTransport (HTTP/3/QUIC) [R13] | transporte Web não confiável, baixa latência | após a etapa 9 (WebSocket primeiro) |
| QUIC no nativo (ex.: msquic, MIT) | alternativa futura ao ENet, com criptografia nativa | avaliar após v1 |
| Token assinado + criptografia (estilo netcode.io) [R11] | autenticação real e tráfego cifrado | pós-v1; ver 2.3 |
| Steam Datagram Relay / Epic Online Services (relay, lobby, NAT, gratuitos) | lobby online sem servidor próprio | plugin opcional pós-v1 |
| Tick e interpolação adaptativos ao jitter (Overwatch [R8]) | menos atraso visível | etapa 7 |
| Física em rede de veículos (Rocket League, GDC 2018 [R14]) | carros preditos com o sistema de veículos | pós-v1 |
| Host migration | partida continua se o host sair | pós-v1 |
| Servidor dedicado headless em container (Docker) | deploy simples em VPS/nuvem | etapa 9 |
| Replay/espectador | snapshots ajudam, mas exige gravar estado inicial, eventos/RPCs e inputs | pós-v1, trabalho próprio |

## 2.3 Segurança e limites do protocolo

Definidos no contrato da etapa 0, porque mudam o formato:

- **Versão do protocolo** + versão do jogo + hash da cena no handshake; incompatível = recusa com motivo.
- **Limites:** pacote não confiável ≤ 1200 B, mensagem confiável com teto (ex.: 64 KB), máximo de RPCs e
  bytes/s por cliente, máximo de conexões pendentes. Excedeu = descarta; repetiu = desconecta.
- **Validação no servidor:** RPC só se registrado e com o alvo certo; argumentos com tipo e faixa
  verificados; cliente só altera objeto/propriedade de que é dono; o bitstream nunca lê além do buffer
  (erro = pacote descartado, nunca crash).
- **Sem criptografia na v1.** O token simples só identifica a sessão, **não autentica**. A v1 é documentada
  para LAN/amigos de confiança. Partidas públicas exigem token assinado + criptografia (pós-v1) ou WSS (TLS)
  no caminho WebSocket.
- **"Client authoritative"** (veículos/física) aparece na UI com aviso: o cliente decide a posição daquele
  objeto, abrindo trapaça e divergência; o servidor só limita velocidade e teleporte.

## 2.4 Convivência com o KXNetwork legado

`Ketsji/KXNetwork/` (`KX_NetworkMessageSensor/Actuator/Manager/Scene`) faz mensagens **locais** entre
objetos e cenas (Message sensor/actuator), sem rede de verdade apesar do nome. Decisão:

- O legado continua intacto, com o mesmo comportamento; arquivos antigos não mudam.
- O módulo novo usa prefixo `NET_`/`KX_Net*` e nomes de UI "Multiplayer"/"Network Sync", para não confundir
  com "Message".
- Opção futura (fora da v1): checkbox "Send over network" no Message actuator, encaminhando como RPC.

## 3. Módulo e onde entra no código

Novo `source/gameengine/Network/` (biblioteca `ge_network`):

```
NET_ITransport.h        interface (connect, send(canal, confiável?), poll)
NET_TransportENet.cpp   extern/enet (vendorizado)
NET_TransportWeb.cpp    WITH_WEB / __EMSCRIPTEN__
NET_TransportLoopback.cpp
NET_BitStream.h         escrita/leitura em bits, quantização
NET_Session.cpp         conexão, handshake, versão do jogo, timeout, ping/RTT
NET_Replicator.cpp      snapshots, delta, prioridade, interesse
NET_Snapshot*.cpp       buffer de snapshots, interpolação
NET_Prediction.cpp      buffer de inputs, reconciliação
NET_LagCompensation.cpp histórico de transforms por tick
NET_RPC.cpp             registro e despacho de RPCs
KX_NetworkManager.cpp   ponte com KX_Scene/KX_GameObject
KX_PyNetwork.cpp        módulo Python Range.network (alias bge.network)
```

Pontos de integração:

- `KX_KetsjiEngine::NextFrame`: antes do passo de lógica, `net.ReceiveAndApply(tick)`; depois da física,
  `net.CaptureAndSend(tick)`. Recepção/envio do socket ficam na thread de rede, com filas lock-free.
- `KX_GameObject`: componente `KX_NetObject` opcional (só existe se o objeto for replicado; custo zero
  para objetos comuns).
- `KX_Scene::AddReplicaObject` / remoção: gancho para spawn/despawn replicado.
- DNA: bit novo em `bProperty.flag` (`PROP_REPLICATED`, ao lado de `PROP_DEBUG`) e struct
  `bNetworkSettings` no `Object` (replicate, authority, taxa, prioridade, campos). Configurações globais
  em `GameData` da cena (porta, máximo de jogadores, tick de envio).
- Converter (`BL_BlenderDataConversion.cpp`): cria `KX_NetObject` a partir do DNA.
- Logic bricks em `GameLogic/`: `SCA_NetworkSensor`, `KX_NetworkActuator`.

## 4. Formato na rede (performance)

Técnicas de [R3][R4], medidas por objeto:

- **Quantização:** posição em fixo (ex.: 1 mm, faixa configurada pela cena); rotação "smallest three"
  (29–32 bits em vez de 128); velocidade em 16 bits por eixo; floats de propriedade com faixa/precisão
  definidas na UI.
- **Delta contra o último snapshot confirmado** pelo cliente (ack por tick); campo não mudou = 1 bit.
- **Objetos em repouso** (Bullet "sleeping") não são enviados.
- **Prioridade acumulada** + orçamento de banda por cliente (ex.: 64 KB/s): objetos com mais prioridade
  e mais tempo sem envio entram primeiro. [R4]
- **Relevância/interesse:** distância, grid espacial e flag "sempre relevante" (inspirado na Replication
  Graph do Unreal). [R7]
- **Pacote ≤ 1200 bytes** (abaixo do MTU), sem fragmentação no caminho não confiável.

Metas da v1 (medidas no simulador de rede, seção 7):

| Métrica | Meta |
|---|---|
| Custo de CPU da rede no servidor, 16 jogadores, 300 objetos dinâmicos | < 1 ms por tick |
| Banda por cliente, mesma cena, 30 Hz | < 40 KB/s |
| Cliente com 150 ms RTT e 2% de perda | sem teleporte visível em objetos remotos |
| Objeto parado | 0 bytes por snapshot após o ack |

## 5. Netcode (sensação de jogo)

1. **Interpolação de entidades remotas:** buffer de snapshots, renderizar ~2 snapshots atrás
   (`interp_delay` adaptativo ao jitter); extrapolação curta se faltar pacote. [R1][R6]
2. **Predição no cliente** para o objeto do próprio jogador: aplica input local já, guarda inputs por tick,
   reaplica ao receber o estado do servidor; correção suavizada em vez de salto. [R6][R5]
   - Para personagens (`KX_CharacterController`) é viável. Para veículos/física complexa, v1 usa só
     interpolação + autoridade do cliente opcional ("client authoritative" marcado na UI), como muitos jogos
     cooperativos.
3. **Input redundante:** cada pacote de input leva os últimos N inputs, para sobreviver à perda. [R2]
4. **Compensação de lag:** servidor guarda ~1 s de transforms dos hitboxes por tick; ray/hit de tiro é
   testado no tick que o cliente viu. Exposto como `rayCast(..., lagCompensated=True)` e opção no Ray
   Sensor. [R5][R8]
5. **Relógio sincronizado:** offset/RTT estimados por ping-pong com média móvel. [R1]

## 6. Facilidade para o usuário

### 6.1 Sem código (UI + logic bricks)

- **Painel Network** em Properties > Object: `Replicate`, `Authority` (Server/Owner), `Sync`
  (Transform, Velocity, Animation state, Visibility), `Rate`, `Priority`, `Relevance distance`,
  `Interpolate`/`Predict`.
- **Checkbox "Rep"** em cada game property: replicada automaticamente.
- **Painel Multiplayer** na cena (Render/Game settings): modo padrão no Play (Offline/Host/Client),
  porta, máximo de jogadores, objeto "Player Prefab" spawnado por conexão.
- **Network Sensor:** Connected, Disconnected, RPC recebido (nome), Is Owner, Is Server.
- **Network Actuator:** Host, Join (IP), Disconnect, Send RPC (nome + propriedade), Spawn, Give Ownership.
- **Template "Multiplayer Starter"** (Add > template ou arquivo exemplo): dois jogadores andando,
  lobby simples, chat. Um jogo funcional em 1 minuto.

### 6.2 Python curto

```python
import Range.network as net
from Range.types import KX_PythonComponent

class Player(KX_PythonComponent):
    args = {"speed": 5.0}

    def start(self, args):
        self.object.net.replicate("health", on_change=self.update_hud)

    @net.rpc(target=net.SERVER, reliable=True)
    def shoot(self, origin, direction):
        hit = self.object.scene.rayCast(origin, direction, lagCompensated=True)
        ...

    def update(self):
        if self.object.net.isOwner:
            ...
```

API mínima: `net.host(port)`, `net.join(addr)`, `net.disconnect()`, `net.isServer`, `net.clients`,
`net.spawn(name, owner=None)`, `obj.net.owner`, `obj.net.isOwner`, `@net.rpc(target, reliable)`,
eventos `net.on_connect/on_disconnect`.

### 6.3 Ferramentas de teste

- **Play com N clientes:** botão no header do Play que abre o host + N blenderplayers lado a lado.
- **Simulador de rede** (UI e `--net-sim lat=100,jitter=20,loss=2`): latência, jitter, perda e duplicação
  aplicados no transporte.
- **Overlay de debug** (ImGui, já existe na engine): RTT, banda in/out, bytes por objeto, dono de cada
  objeto (cor), "fantasma" do último snapshot do servidor vs. posição predita.
- **Validação no editor:** aviso se objeto replicado não tem `Replicate`, se RPC chama propriedade
  inexistente, se Player Prefab não está numa camada inativa.

### 6.4 Menus de multiplayer com ImGui

O ImGui já roda no Desktop e no Web (backend com `#version 300 es` em `KX_Imgui.cpp`; o overlay de debug
funciona lá) e, portanto, no Android WebView. Os menus prontos de multiplayer usam o módulo Python
`Range.imgui` que já existe (`begin/end`, `button`, `input_text`, `listbox`, `combo`, `begin_popup_modal`,
`load_font/push_font`, `push_style_color`, `set_game_ui_open`), sem dependência nova.

**Entrega:** script `Range/net_menu.py` (componente `NetworkMenu`) incluído no template Multiplayer Starter.
O usuário adiciona o componente a um objeto e tem o menu funcionando; tudo é configurável por `args`
(título, porta padrão, máximo de jogadores, mostrar/ocultar telas, cor de destaque, fonte).

Telas:

| Tela | Conteúdo | Chama |
|---|---|---|
| Principal | Hospedar, Entrar, Servidores LAN, Configurações, Sair | — |
| Hospedar | nome da sala, máximo de jogadores, porta, senha opcional, botão Criar | `net.host()` |
| Entrar | campo IP/porta ou código da sala, Conectar, estado ("conectando…", erro com motivo do handshake) | `net.join()` |
| Servidores LAN | lista com nome, jogadores/máx, ping; Atualizar; clique duplo entra | descoberta LAN (etapa 10) |
| Sala (lobby) | lista de jogadores com ping e "pronto", chat curto, Pronto, Iniciar (só host), Sair | estado da sessão, RPC |
| Pausa em jogo | Continuar, jogadores conectados, Desconectar | `net.disconnect()` |
| Configurações | nome do jogador, simulador de rede (só em build de desenvolvimento) | — |
| Avisos | modal para desconexão, versão incompatível, sala cheia, timeout | eventos de sessão |

Regras de design para funcionar em todas as plataformas:

- **Escala automática** pelo tamanho da tela (`get_display_size`) e por `args`; no celular, botões com
  altura mínima de ~48 px lógicos e espaçamento maior, para o dedo.
- **Teclado na tela:** a Web/Android não tem teclado físico. Campos de texto mostram um teclado ImGui
  simples (números + letras) quando a plataforma é touch; códigos de sala curtos (base 36, como no
  Rolimã Racer) reduzem a digitação.
- **Gamepad/teclado:** navegação por foco (setas/D-pad, Enter/A, Esc/B) para jogos de sofá e consoles.
- **Idiomas:** textos em uma tabela por idioma no próprio script, fácil de trocar.
- **Visual:** tema próprio (cores, cantos, fonte) carregado uma vez; o jogo pode trocar por `args` ou
  substituir o script inteiro. O menu só usa a API pública de `Range.network`, então quem preferir UI de
  objetos/texto faz o próprio menu com as mesmas chamadas.
- **Custo:** menu fechado = nenhuma janela ImGui desenhada (o `KX_Imgui::Render` já pula frames sem
  vértices).

Etapas: telas Principal/Hospedar/Entrar/Sala/Avisos na etapa 5 (com o template); Pausa e Configurações na
etapa 6; Servidores LAN na etapa 10. Teste manual em Desktop, navegador e APK a cada entrega.

## 7. Etapas e estado atual

Cada etapa termina com uma cena de teste em `tools/create_*_test.py` (padrão do repositório) e entrada no
changelog.

As etapas abaixo foram escritas como estimativa inicial e não representam mais o estado atual. As etapas
0–9 estão implementadas total ou parcialmente; a validação recente inclui Linux, Windows/MSVC, wasm32 e
o runtime Web completo. Permanecem como trabalho aberto principalmente o servidor Windows sem janela,
validação de IPv6 real, APK WebView, descoberta LAN completa e a decisão sobre recursos pós-v1.

| # | Etapa | Entrega verificável | Esforço |
|---|---|---|---|
| 0 | Contrato + bitstream | `docs/multiplayer-protocol.md` curto (tick, ids, ciclo de vida, mensagens, canais, limites, versão). Depois `ge_network` no CMake e `NET_BitStream` com gtest: ida e volta, leitura truncada, valores fora da faixa, quantização, mesma saída em x64 e wasm32. ENet ainda não entra | 3–4 dias |
| 1 | Sessão | `extern/enet`; host/join/disconnect, handshake com versão do jogo, ping/RTT, timeout; transporte loopback; flag `--server` | 1 semana |
| 2 | Replicação de transform | `NetId`, snapshots + delta + ack, interpolação; dois cubos em duas janelas | 1–2 semanas |
| 3 | Spawn, ownership, propriedades | Add Object replicado, Player Prefab, `PROP_REPLICATED`, despawn | 1 semana |
| 4 | RPC + Python | `Range.network`, `@rpc`, eventos; testes em Python Component | 1 semana |
| 5 | UI e logic bricks | painéis Network/Multiplayer, sensor e actuator, template Starter, menu ImGui `NetworkMenu` (seção 6.4) | 2 semanas |
| 6 | Ferramentas | Play com N clientes, simulador de rede, overlay de debug | 1 semana |
| 7 | Predição + lag compensation | personagem predito, reconciliação, `rayCast(lagCompensated)` | 2 semanas |
| 8 | Otimização | prioridade/orçamento, relevância por grid, medição contra as metas da seção 4 | 1 semana |
| 9 | Web/Android | `NET_TransportWeb` (WebSocket), endpoint WebSocket no servidor junto do ENet (cross-play), teste no APK WebView, imagem Docker do servidor | 2 semanas |
| 10 | Lobby | descoberta LAN (broadcast), lista de sessões; depois NAT punch/relay (fora da v1) | 1 semana+ |

- **v1 (0–6), ~7–9 semanas:** multiplayer funcional básico no Desktop, **sem** predição, compensação de lag
  nem Web.
- **v1.1 (7–8), ~3 semanas:** predição, compensação de lag e otimização de banda.
- **v1.2 (9–10), ~3 semanas:** Web/Android via WebSocket com cross-play, lobby LAN.

## 8. Avaliação

**Vale a pena?** Sim. É o recurso que mais muda o tipo de jogo que dá para fazer na engine, e o desenho
nativo dá vantagem real sobre um SDK em Python: performance, configuração sem código e netcode que um
script não alcança (rewind de física, tick fixo).

**Riscos e mitigação**

| Risco | Impacto | Mitigação |
|---|---|---|
| Bullet não determinístico | predição de física complexa diverge | predizer só personagem; resto interpolado |
| Python Components/logic bricks com efeitos colaterais em cliente e servidor | estado duplicado (ex.: dano aplicado duas vezes) | `net.isServer` no template, aviso no editor, guia "o que roda onde" |
| Web sem UDP | WebSocket tem head-of-line blocking | folga de interpolação maior no Web; WebTransport como evolução |
| Mudança de DNA | compatibilidade de `.range` | só campos novos com padrão zero; arquivos antigos abrem iguais |
| Escopo cresce (lobby online, matchmaking, anti-cheat) | atraso | fora da v1; servidor autoritativo já dá a base anti-cheat |
| LibLoad/troca de cena em rede | ids divergentes | v1: troca de cena só pelo servidor, com mensagem dedicada |

**Fora da v1:** matchmaking online, relay/NAT punch, rollback (GGPO) para jogos de luta [R12], voz,
replicação de malha deformada e de destruição (precisa de sementes determinísticas; avaliar com o plano
de destruição).

## 9. Referências

- [R1] Glenn Fiedler, *Gaffer On Games* — "Snapshot Interpolation", "State Synchronization",
  "Networked Physics" (gafferongames.com).
- [R2] John Carmack / id Software, modelo de rede do Quake 3 (delta snapshots, inputs redundantes);
  análise em fabiensanglard.net, "Quake 3 Source Code Review: Network Model".
- [R3] Glenn Fiedler, "Snapshot Compression" (quantização, smallest three, delta) — gafferongames.com.
- [R4] Glenn Fiedler, "Reliable Ordered Messages" e "Packet Fragmentation and Reassembly";
  Frohnmayer & Gift, "The TRIBES Engine Networking Model" (GDC 2000) — prioridade e orçamento de banda.
- [R5] Yahn W. Bernier, "Latency Compensating Methods in Client/Server In-game Protocol Design and
  Optimization" (GDC 2001); Valve Developer Wiki, "Source Multiplayer Networking".
- [R6] Gabriel Gambetta, "Fast-Paced Multiplayer" (partes I–IV) — predição, reconciliação, interpolação,
  lag compensation (gabrielgambetta.com).
- [R7] Epic Games, documentação "Actor Replication" e "Replication Graph" do Unreal Engine — relevância e
  prioridade.
- [R8] Tim Ford, "Overwatch Gameplay Architecture and Netcode" (GDC 2017); David Aldridge, "I Shot You
  First: Networking the Gameplay of Halo: Reach" (GDC 2011).
- [R9] ENet — enet.bespin.org / github.com/lsalzman/enet (licença MIT).
- [R10] Valve, GameNetworkingSockets — github.com/ValveSoftware/GameNetworkingSockets.
- [R11] Glenn Fiedler, netcode e yojimbo — github.com/mas-bandwidth.
- [R12] GGPO (rollback) — github.com/pond3r/ggpo.
- [R13] W3C WebTransport (developer.mozilla.org/docs/Web/API/WebTransport_API); IETF RFC 9000 (QUIC).
- [R14] Jared Cone, "It IS Rocket Science! The Physics of Rocket League Detailed" (GDC 2018).
- Referências de usabilidade: Godot `MultiplayerSpawner`/`MultiplayerSynchronizer`, Unity Netcode for
  GameObjects (`NetworkObject`, `NetworkVariable`, RPCs) — modelo de "marcar e replicar" que seguimos na UI.
