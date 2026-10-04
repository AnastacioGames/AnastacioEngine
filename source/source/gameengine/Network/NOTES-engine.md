# Integração do núcleo na engine (branch `net/engine`)

Criado em 2026-10-04. O núcleo (`NET_*`) **não foi alterado**: tudo está fora dele, em `Ketsji/KX_NetworkManager.*`,
`Ketsji/KX_PyNetwork.*`, DNA/RNA, painéis Python e CMake. Este arquivo registra as decisões, as dúvidas e o que
não deu para testar.

## Onde está cada peça

| Peça | Arquivo |
|---|---|
| Ponte com a engine (`net::IWorld` sobre `KX_GameObject`, sessões, replicação, lobby, LAN) | `Ketsji/KX_NetworkManager.h/.cpp` |
| Passo de rede = passo fixo de lógica | `Ketsji/KX_SimulationPipeline.cpp` (`BeginTick` antes da lógica, `EndTick` depois da física) |
| Posse do gerente, tic rate do cliente | `Ketsji/KX_KetsjiEngine.*` (`GetNetworkManager`, `GetOrCreateNetworkManager`, `SetTicRate`) |
| Esquecer objeto removido | `Ketsji/KX_Scene.cpp` (`NewRemoveObject`) |
| Id do objeto na engine | `Ketsji/KX_GameObject.*` (`GetNetId`/`SetNetId`, nunca copiado para réplicas) |
| `Range.network` (alias `bge.network`) | `Ketsji/KX_PyNetwork.*`, registrado em `KX_PythonInit.cpp` |
| Abrir a sessão pelo modo da cena | `Launcher/LA_Launcher.cpp` (fim de `InitEngine`) |
| DNA | `DNA_scene_types.h` (`RangeNetworkSettings` em `GameData.network`), `DNA_object_types.h` (`RangeNetObjectSettings` em `Object.net`), `DNA_property_types.h` (`PROP_REPLICATED`) |
| Defaults, versioning | `BKE_scene_network_defaults`, `BKE_object_net_defaults`, `BKE_object_net_id_generate`; bloco `GameData.network` em `versioning_range.c` |
| RNA | `rna_scene.c` (`game_settings.network`), `rna_object.c` (`object.game.network`), `rna_property.c` (`GameProperty.use_replicate`) |
| Painéis | `properties_game.py`: `SCENE_PT_game_network`, `OBJECT_PT_game_network`, botão "Rep" em Game Properties |
| CMake | `gameengine/CMakeLists.txt` (`add_subdirectory(Network)`), `Ketsji/CMakeLists.txt` (`ge_network` na LIB), `blenderplayer/CMakeLists.txt` (`ge_network extern_enet`) |
| Teste | `tools/net_engine_test/` (dois `RangeRuntime`, servidor + cliente) |

## Decisões

- **Um passo de lógica = um tick.** Ao abrir a sessão o gerente liga `SetUseFixedTimestep(true)` e, no servidor,
  aplica `tick_rate` da cena (0 = Logic tic rate atual); o cliente adota a taxa do `Welcome`. Ao sair, restaura os dois.
  `KX_KetsjiEngine::SetTicRate` avisa e ignora chamadas de script enquanto o cliente está numa sessão
  (plano, seção 2.3); o gerente usa `IsAdoptingTickRate()` para poder aplicar a do servidor.
- **Gerente criado sob demanda.** Cenas Offline que nunca chamam `Range.network` não criam nada: custo zero.
- **Quem registra os objetos.** (1) `Replicate` no painel do objeto, lido na abertura da sessão; (2) `net.replicate(obj, ...)`
  em script, antes de `host()`/`join()`. Os dois dão o mesmo resultado (entrada com esquema de propriedades).
- **net_id.** Gerado no editor ao ligar `Replicate` (u32 aleatório de 1 a 0x7FFFFFFF, único entre os objetos do
  arquivo, salvo no `.range`); duplicar o objeto gera outro. Na conversão, id 0 ou repetido vira um id derivado
  do **nome** (FNV-1a), com aviso; objetos com id salvo reivindicam primeiro, os demais em ordem de nome, então
  servidor e cliente chegam ao mesmo resultado com o mesmo `.range`. Objeto criado só por script usa o mesmo caminho.
- **Esquema de propriedades** = propriedades de jogo com "Rep" ligado, na ordem da lista do objeto, só Boolean/Integer/Float
  (string e timer ficam de fora; aviso). Float sai com 32 bits crus (a UI ainda não tem faixa/bits por propriedade).
- **Cliente não simula.** Objetos replicados dinâmicos têm a dinâmica suspensa no cliente (`SuspendDynamics(false)`:
  ainda colidem, só os snapshots os movem) e voltam ao normal ao desconectar.
- **Interpolação.** O cliente renderiza em `NetClock::renderTime` com `applyInterpolated`, e `applyLatest` enquanto o
  relógio não sincronizou. A opção "Interpolate" do painel é salva, mas o núcleo interpola tudo igual (não há flag
  por objeto no `ReplicaClient`).
- **Host como cliente 0.** A sessão não anuncia o servidor; o gerente manda um `ClientInfo(0, nome, conectado|pronto)` a
  cada cliente que entra, para o lobby do cliente listar o host (`isHost`).
- **Pronto/Iniciar do lobby.** O protocolo não tem mensagem para isso. Usei três RPCs internos registrados sempre na
  tabela (`net.ready` cliente→servidor, `net.ready_state` e `net.start` servidor→cliente, alvo `Owner`, que um cliente
  não consegue chamar). `start_game()` só vale se todos os clientes estão prontos; o host conta como pronto.
- **Chat.** `ChatMsg` pelo canal `Rpc`; o servidor carimba o remetente e reenvia a todos (inclusive quem mandou).
- **Simulador.** `net.set_simulation(...)` vale para o **próximo** `host()`/`join()` (o transporte é embrulhado ao ser criado).
- **Sleeping.** `PHY_IPhysicsController` não expõe o "sleeping" do Bullet: `isSleeping` = corpo dinâmico com velocidade
  linear e angular zeradas (equivalente para o replicador, que mantém o último estado).

## Dúvidas e decisões provisórias

1. **Senha** (`host(password=)`, `join(password=)`): o `Hello` v1 não tem campo, então a senha é **ignorada com aviso** e
   `discover_lan()` devolve `password=False`. Não fingi proteção. Decisão pendente de NOTES-D (7 `WrongPassword` + campo no `Hello`).
2. **Código de sala** (4–8 caracteres base 36) em `join()`: sem serviço de lobby não dá para resolver; `join()` avisa e devolve `False`.
3. **`Server Name`**: virou `game_settings.network.server_name` (padrão "Anastacio Server"), como sugerido em NOTES-H.
4. **`game_id`/`game_version`** entraram no painel (o handshake exige) em vez de ficarem fixos.
5. **IPv6**: o núcleo só fala IPv4 (NOTES-C); `join("[::1]:7777")` é aceito pelo parser mas o ENet não conecta.
6. **Versão do DNA**: não mexi em `RANGE_MINSUBVERSION`; o bloco de versioning usa `DNA_struct_elem_find` (como os blocos vizinhos), então não depende do número.

## O que não está feito (e por quê)

- **Servidor sem janela.** `RangeRuntime` ainda abre canvas e rasterizer; o teste usa `xvfb-run`. O modo "Dedicated" da cena
  só dispensa o jogador local (`IsDedicated()`), não a janela. Falta um `--server` que pule rasterizer/áudio.
- **Predição, lag compensation, input.** As classes do núcleo (`NET_Prediction`, `NET_LagCompensation`) não foram ligadas;
  o dono de um objeto também só segue os snapshots. `skipOwned` fica `false`.
- **`@net.rpc` / RPC do usuário e `obj.net`.** Só os três RPCs internos. A API de NOTES-D não pede mais que isso.
- **Troca de cena durante a partida** (`SceneChange`): o cliente avisa e responde `SceneLoaded` para a mesma cena; seguir o servidor para outra não existe.
- **Relevância por distância.** `Replicator::setClientView` não é chamado (tudo relevante); o painel só tem "Always Relevant".
- **Web/Android.** O caminho (`createWebClientTransport`) está ligado sob `__EMSCRIPTEN__`, mas o build Web não foi feito aqui.
- **Windows/MSVC e editor completo no Linux**: ver "Testes" abaixo.

## Testes

Ver o resultado de cada um no `docs/changelog.md` (entrada "Multiplayer: núcleo ligado na engine").
