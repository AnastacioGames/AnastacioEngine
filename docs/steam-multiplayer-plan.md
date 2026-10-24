# Plano: complemento Steam para multiplayer

Criado em 2026-10-07. Estado: **Windows implementado e testado localmente (SDK 1.55, AppID 480);
prova externa e corrida real pendentes**. Nenhum release publicado. Uso e testes no
[guia de desenvolvimento](steam-complement-development.md). Histórico das etapas A–G em
[`changelog.md`](changelog.md) (2026-10-07).

Objetivo: no RolimaRacer pela Steam, um jogador cria sala e amigos entram pela lista ou convite, sem
IP nem encaminhamento de portas. A engine continua com rede nativa sem exigir Steam ou `steam_api64.dll`.

## 1. Pendente

- Duas contas em redes diferentes com relay confirmado (`connection_routes()`), sem encaminhar portas.
  Uma conta com sockets locais não satisfaz C–G.
- Convites com jogo aberto e fechado (`+connect_lobby`) vindos de outra conta.
- Espera de até 3 s por atualização de membro antes de recusar conexão: testar entre contas.
- Corrida real do RolimaRacer (etapa F): pista, spawn com dono certo, rodas remotas, resultado,
  saída/reentrada e host saindo. Sem carros duplicados nem objetos remotos simulados localmente.
- AppID comercial, conquistas persistidas no schema real, idioma.
- Revisão de distribuição: termos Steamworks x licença da engine; pacote extraído e instalação pela Steam
  com duas contas. Antes de empacotar Windows, ler `distribution-0.1.md` inteiro.
- Linux; depois registrar matriz de plataformas. Não marcar Linux/Web/Android como suportados por inferência.
- RangeArmor/Web sem seletor Steam no exportador (usar o instalador explícito).
- Avaliação visual do usuário no jogo real.
- Local final do projeto CMake do complemento ao fechar a distribuição.

## 2. Arquitetura

Reusa sessão, protocolo, replicação, RPC, ownership, relógio, interpolação e predição nativos. O host é
servidor autoritativo; o relay só encaminha. Predição de veículos Bullet segue fora da v1.

| Camada | Responsabilidade |
|---|---|
| Rede nativa | Sessão, handshake e sincronização |
| Complemento Steam opcional (`AnastacioSteam.dll`) | Init, callbacks, identidade e transporte |
| Salas Steam (`ISteamMatchmaking`) | Encontrar host, capacidade, versão, convites |
| Componente/menu ImGui da engine | LAN/IP ou Steam, salas e estado |
| RolimaRacer | Pista, carregamento, spawn e regras |

Decisões:

- Componente e menu reutilizáveis vêm com a engine (`source/release/scripts/modules/anastacio_network/`).
  AppID e opções por projeto; o jogo guarda só suas regras. AppID nunca fixo na engine.
- Transporte por `ISteamNetworkingSockets` (SDK Steamworks, não GameNetworkingSockets aberto, que não dá
  relay Valve): `CreateListenSocketP2P` / `ConnectP2P` pelo SteamID; porta virtual não é porta do roteador.
  Os pacotes do jogo passam pelo transporte Steam; divulgar IP ENet na sala não basta.
- Adaptador `net::ITransport` gera `Connected/Received/Disconnected` sem mudar snapshots.
- ABI C versionada (v2), export único `AnastacioSteam_GetApi`, tipos de largura fixa, handles opacos;
  nada de `std::` ou exceção cruzando a DLL; cada lado libera o que aloca. Carregada de diretório explícito,
  sem PATH. Web não compila a ponte. Código: `NET_AnastacioPlugin*.{h,cpp}` em `source/source/gameengine/Network/`.
- Um único serviço por processo controla `SteamAPI_Init`, callbacks (uma vez por `NextFrame`) e shutdown.
  O `SteamComponent` do RolimaRacer usa esse serviço para idioma/conquistas; nunca dois donos.
- `PeerId` é uint32 local; SteamID é uint64 separado, inteiro em Python e decimal nos metadados.
- Canais: Control (0) e Rpc (1) confiáveis em lanes independentes; Snapshot (2) e Input (3) não confiáveis,
  descartando números antigos por lane. Envelope com versão e canal. Limites nativos: 1200 B não confiável,
  65536 confiável. Orçamento proposto (a medir): 256 mensagens / 1 MiB por poll, 4 MiB por peer.
- Sala não é sessão: handshake, versão, hash de cena e capacidade continuam verificados.
- Host indisponível encerra a partida com mensagem; sem migração de host.
- Erro Steam não cai silenciosamente para LAN. Build padrão inicia sem SDK/DLL.
- Callbacks não são bombeados durante carregamento síncrono que bloqueie `NextFrame`.
- Não versionar SDK, chaves nem `steam_appid.txt` no depot publicado.

Fontes: [rede Steam](https://partner.steamgames.com/doc/features/multiplayer/networking),
[ISteamNetworkingSockets](https://partner.steamgames.com/doc/api/ISteamNetworkingSockets),
[ISteamMatchmaking](https://partner.steamgames.com/doc/api/ISteamMatchmaking),
[API Steamworks](https://partner.steamgames.com/doc/sdk/api).

## 3. Etapas

| Etapa | Estado |
|---|---|
| A — inventário e decisão | Feita (decisões acima) |
| B — carregador/ABI e init | Feita; online no AppID 480 |
| C — transporte isolado | Local OK (socket pair do SDK); falta prova externa com relay |
| D — sessão pelo transporte | Local OK (handshake, chat, transform, spawn, ownership) |
| E — salas, convites, menu | Uma conta OK; faltam convites com segunda conta |
| F — corrida real | Adaptadores testados em cena mínima; falta corrida real |
| G — distribuição e docs | Export Steam/LAN local OK; falta Steam real, licença e Linux |

Contexto do jogo (inventário de 2026-10-07): `CAM_UI` em `0_SCN_System` tem `SteamComponent` e
`NetworkManager`; `NetMenuAnchor` tem `net_menu.NetworkMenu`; quatro colliders têm
`NetworkVehicleSync`. Não restaurar o antigo sincronizador JSON nem o multiplayer em malha.

## 4. Fora da primeira entrega

Host migration, backend online fora da Steam, matchmaking competitivo, servidor dedicado Steam, relay
para navegador, cross-play Steam/Web/Android, voz e replay de veículos Bullet. Web/Android seguem com
WebSocket. Código curto de convite não é requisito inicial.
