# Integração do núcleo na engine (branch `net/engine`)

Criado em 2026-10-04. A integração fica fora do núcleo (`NET_*`), em `Ketsji/KX_NetworkManager.*`,
`Ketsji/KX_PyNetwork.*`, DNA/RNA, painéis Python e CMake. O núcleo só mudou em dois pontos da predição (seção
"Predição, input e lag compensation"): `ReplicaClientConfig::skipFilter` e o throttle do ENet. Este arquivo registra as decisões, as dúvidas e o que
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
| Input, predição, lag compensation | `Ketsji/KX_NetworkManager.*` (`ClientPredict`, `ServerStepPredicted`, `RecordHitboxes`, `RaycastPast`), `Ketsji/KX_PyNetwork.cpp` (`predict`, `set_input`, `raycast_past`...) |
| RPC do jogo, `obj.net` | `Ketsji/KX_NetworkManager.*` (`RegisterRpc`, `CallRpc`, `BuildRpc`), `Ketsji/KX_PyNetwork.cpp` (`rpc`, `call`, `ObjectNet`), `Ketsji/KX_GameObject.cpp` (atributo `net`) |
| Servidor headless (`RangeRuntime --server`) | `GamePlayer/GPG_Ghost.cpp` (opção), `Launcher/LA_Launcher.*` (`SetServerMode`), `Ketsji/KX_KetsjiEngine.*` (`SetServerMode`, `ServerSleep`), `Ketsji/KX_SimulationPipeline.cpp` (sem skinning) |

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

- **Servidor sem janela no Windows.** No Linux o `--server` não abre janela nem precisa de display (seção abaixo); no
  Windows ainda abre a janela pequena do GHOST (não bloqueia, mas existe). Um contexto offscreen WGL ficaria para depois.
- **Predição de corpos dinâmicos.** A predição move o objeto pela função de passo do jogo (cinemática); física do
  Bullet não é re-simulada no replay. Só o transform é previsto e comparado (as propriedades seguem o servidor, ver
  abaixo).
- **Troca de cena durante a partida** (`SceneChange`): o cliente avisa e responde `SceneLoaded` para a mesma cena; seguir o servidor para outra não existe.
- **Relevância por distância.** `Replicator::setClientView` não é chamado (tudo relevante); o painel só tem "Always Relevant".
- **Web/Android.** O caminho (`createWebClientTransport`) está ligado sob `__EMSCRIPTEN__`, mas o build Web não foi feito aqui.
- **Editor completo no Linux**: ver "Testes" abaixo. Windows/MSVC validado em 2026-10-04 (seção "Windows").

## RPC do jogo e `obj.net`

Feito em 2026-10-04 na branch `claude/project-thread-l2znr0`, sobre `NET_RPC` (núcleo sem mudança).

```python
@net.rpc                                    # target 'server'; nome = nome da função
def hello(sender, n, text): ...

@net.rpc(target="owner")                    # servidor -> dono do objeto da chamada
def poke(obj, sender, n): ...

@net.rpc(target="server", owner_only=True, reliable=False, name="move")
def move_req(obj, sender, dx): ...

net.call("hello", 3, "oi")                  # global
rig.net.call("poke", 7)                     # chamada no objeto (igual a net.call("poke", 7, obj=rig))
```

- **Alvos:** `server`, `owner` (só o servidor chama; roda no dono do objeto, ou no servidor se ele é o dono),
  `all` (servidor e todos os clientes, inclusive quem chamou), `others` (todos menos quem chamou).
- **Assinatura:** `fn(sender, *args)` global, `fn(obj, sender, *args)` no objeto. `sender` é o cliente que chamou;
  0 quando quem chamou foi o servidor. Um `all`/`others` de um cliente é repassado pelo servidor como `200 RpcFrom`
  (provisória, ver `NOTES-G.md`), então os outros clientes e o próprio autor (no `all`) recebem o id dele.
- **Argumentos:** bool, int, float, str, objeto de jogo (vai como net id; volta como o objeto ou `None`), 3 números
  (`mathutils.Vector`), 4 números (quaternion w, x, y, z; volta `mathutils.Quaternion`). Até 1024 bytes por chamada.
- **Registro:** antes de `host()`/`join()` (durante a sessão levanta `RuntimeError`), com os mesmos nomes em todos os
  peers. Os ids seguem os nomes em ordem alfabética, então a ordem de registro não importa; nomes `net.` são
  reservados. Registrar de novo o mesmo nome troca a função (script rodado outra vez).
- **Recusas locais** (`call()` devolve `False`): sem sessão, `owner` chamado por cliente, `owner_only` num objeto de
  outro, argumentos grandes demais. Nome desconhecido levanta `KeyError`. O servidor recusa e conta violação para
  chamadas forjadas (núcleo).
- **`obj.net`:** `id`, `replicated`, `owner`, `isOwner`, `call(name, *args)`, `predict(fn)`. O atributo é criado
  pelo `Range.network` (`_object_net`), então `KX_GameObject` não depende do código de rede.
- **Teste:** `run_net_test.sh rpc`: todos os alvos, todos os tipos de argumento, `sender`, objeto da chamada,
  `owner_only`, `others` sem eco para quem chamou, `sender` de um `all` repassado de volta ao cliente, RPC não confiável (≥ 15/30), nome trocado, `obj.net`, e as
  recusas locais. O cenário `predict` passou a mandar a posição do rig por RPC (`rig_pos`) em vez de chat.

## Predição, input e lag compensation

Refeito em 2026-10-04 na branch `claude/project-thread-l2znr0` (a `net/engine-predict` original se perdeu no limite
de uso). Liga `NET_Prediction` e `NET_LagCompensation` na engine.

**API (`Range.network`):**

```python
INPUT = struct.Struct("<fB")                     # o formato é do jogo; até 57 bytes

def step(obj, data):                             # um tick do objeto com o input do dono; mesmo código nos dois lados
    vx, fire = INPUT.unpack(data) if len(data) == INPUT.size else (0.0, 0)
    obj.worldPosition.x += vx / logic.getLogicTicRate()
    if net.isServer and fire:
        hit = net.raycast_past(origin, direction, 50.0, client=net.owner(obj), ignore=obj)

net.predict(obj, step)                           # servidor e cliente dono (objeto replicado); None desliga
net.set_input(INPUT.pack(vx, fire))              # cliente, todo quadro; no host vale para os objetos do cliente 0
net.set_hitbox(alvo, 0.35)                       # servidor: esfera (ou cápsula com half_height) guardada 1 s
```

Também: `net.input(client)` (servidor: input aplicado neste tick), `net.view_time(client=0)` (cliente: tempo em
que os objetos remotos são desenhados; servidor: o que o cliente mandou), `net.prediction_stats(obj)` (cliente:
inputs, reconciliações, correções, teleportes, erro, ticks).

**Como funciona:**

- **Cliente.** A cada tick, antes de aplicar os snapshots, `ClientPredict()` escolhe o tick previsto
  (`NetClock::predictionTick`, crescendo de um em um por passo; segue a deriva suavizada em relação à estimativa do
  relógio com dois passos num quadro quando fica para trás e nenhum quando fica à frente; só volta direto à estimativa
  se divergir mais de meio segundo), manda o `Input` (redundância 8) e, para cada objeto previsto do próprio cliente: reconcilia com o snapshot
  mais novo (`PredictionClient::reconcile`: se o estado do servidor difere da previsão daquele tick, volta a ele e
  re-executa os inputs seguintes), roda o passo com o input atual e guarda o estado. A correção visual
  (`visualOffset`, decai em 100 ms) é somada à posição depois do passo e retirada antes do próximo.
- **`skipOwned` ligado** no `ReplicaClient`, com um filtro novo no núcleo (`skipFilter`): só os objetos do cliente
  **com `predict()`** deixam de seguir o transform e a velocidade dos snapshots; os outros objetos dele continuam
  interpolados. As propriedades replicadas do objeto previsto continuam chegando ao dono (testado no `predict`
  com `ammo` do `Rig`) (o `apply` só pula o
  movimento; antes pulava o objeto inteiro).
- **Servidor.** `Input` vai para `PredictionServer` (bloco inválido conta violação na sessão). No começo do tick,
  `ServerStepPredicted()` consome o input de cada cliente para este tick (o núcleo repete o último por até 4 ticks
  se faltar) e chama o passo de cada objeto previsto com o input do dono; objetos do host (cliente 0) usam o
  `set_input()` local (não em Dedicated).
- **Bloco de input.** 7 bytes do motor + até 57 do jogo: `[1][render tick u32][alpha u16]`. O tempo é o que estava
  na tela quando o jogo chamou `set_input()` (e não o do tick em que o bloco saiu): um bloco que chega atrasado e é
  repetido não muda o instante do tiro. Por isso `set_input()` deve ser chamado todo quadro.
- **Lag compensation.** O servidor grava as hitboxes no fim de cada tick (`RecordHitboxes`, 1 s). `raycast_past`
  usa o tempo de vista do cliente, limitado a `max_rewind_ms` (400 por padrão, anti-abuso; o limite agora é do
  `RaycastPast`, a história fica com 1 s); `client=-1` testa o presente.
- **Throttle do ENet desligado** (`NET_TransportENet.cpp`, `enet_peer_throttle_configure(peer, ..., 0, 0)` ao
  conectar). Com quadros lentos o RTT varia e o ENet passava a descartar a maior parte dos pacotes não confiáveis
  (snapshots, `Input`, `Pong`) por segundos: o relógio do cliente ficava sem `Pong` (sem sincronizar, sem input) e
  os snapshots só chegavam pelo pedido de estado completo, a cada 1 s. Problema anterior a esta branch (o `rtt` do
  cenário `spawner` ficava parado), achado pelo teste novo.
- **`view_time` é o que foi desenhado.** Quando o tempo de render passa do snapshot mais novo (atraso, perda), o
  `SnapshotBuffer` segura esse snapshot, mas o manager informava o `renderTick`: o input levava um tempo 1–3 ticks à
  frente do desenhado e o servidor rebobinava para lá (0,1–0,4 m a 4 m/s, hitbox de 0,35), errando ~1 tiro por
  rodada do `predict`. `ClientTickBegin` agora informa o tick do snapshot mais novo (alpha 0) nesse caso.
- **`NodeUpdate()` depois de mover o objeto** (`SetPredictedState`, `ApplyOffset`, `setTransform`). Os setters do
  nó só mudam a transformação local; a posição mundial ficava velha até o fim do quadro. Na reconciliação, o passo do
  jogo lia a posição antiga no replay e desfazia a volta ao estado do servidor: o cliente ficava preso a até metros
  do servidor, com `corrections` subindo e `last_error` 0. O `predict` falhava 7 de 20 vezes; depois, 0 de 20 na
  predição.

**Decisões provisórias:**

1. O passo é uma função Python por objeto, chamada pelo motor; não há passo de física no replay.
2. Input é por cliente (um por tick), não por objeto: todos os objetos previstos de um cliente recebem o mesmo bloco.
3. O motor não deduplica ações: um bloco repetido pelo servidor (input atrasado) chega ao passo de novo. O teste
   usa um número de sequência no input para contar cada tiro uma vez; o jogo deve fazer o mesmo.

**Teste:** `run_net_test.sh predict` (spawner + simulador 40 ms/5 ms/1 % de cada lado, tic rate 30). O servidor
cria um `Rig` do cliente movido por `predict()`; o Spawner gira por `predict()` do host (um passo por tick) com
hitbox de 0,35 m e o cliente atira nele pelo input a cada 0,4 s. Confere: o rig responde ao input em ≤ 2 ticks (sem
predição seria um RTT, ~13 ticks aqui), termina na posição do servidor (±5 cm), correções < 0,5 m, o servidor
aplicou o input, e os tiros acertam o Spawner no passado (17/17) e erram no presente (0/17). `NET_DEBUG=1` loga
cada tiro e o estado da predição.

Limites medidos na máquina de teste (4 núcleos, dois players em llvmpipe): a 60 Hz nenhum dos dois mantinha o tic
rate e a linha do tempo da predição não fechava com os snapshots; a 30 Hz fecha. O RTT medido fica em ~450 ms (80 ms
simulados + quadros lentos) e o atraso de interpolação passa de 400 ms, por isso o teste chama `raycast_past` com
`max_rewind_ms=1000`. Não testado: cenário de cena (painel) com predição, corpos dinâmicos previstos.

**Windows/MSVC validado** (2026-10-04, `run_net_test_win.sh predict`, mesmo rig/sim/tic rate do Linux): 5 rodadas
seguidas, todas PASS, lag compensation 22/22 a 23/23 tiros no passado (nenhuma rodada abaixo de 100%, não precisou
de `NET_DEBUG=1`). `run_net_test_win.sh server` também passou de primeira, sem o problema de janela GL
offscreen que trava no Linux sem xvfb (o GHOST do Windows abre a janela 320×240 sem bloquear mesmo em
`--server`); `headless=True`, sem render, hospeda como Dedicated, tudo certo.

## Servidor headless (`--server`)

Refeito em 2026-10-04 na branch `claude/project-thread-l2znr0` (a `net/server-headless` original parou no limite de uso
sem ter sido enviada). Uso: `RangeRuntime --server [-p script.py] jogo.range`.

- **Sem render.** `KX_KetsjiEngine::SetServerMode(true)` desliga o render de vez: `logic.setRender(True)` é recusado com
  aviso. Lógica, física e ações (poses) seguem rodando no tic rate; o **skinning da malha** (`UpdateAnimationDeformers`)
  é pulado, porque ninguém vê os vértices (física sobre malha deformada não acompanha a animação no servidor).
- **Sem áudio.** O player força o dispositivo `None` do Audaspace.
- **Sem janela (Linux).** `GHOST_ISystem::createSystemHeadless()` (`intern/ghost/intern/GHOST_SystemHeadless.h`): sistema
  GHOST sem conexão com display; a "janela" é virtual e tem um contexto OpenGL **EGL surfaceless** do Mesa
  (`EGL_MESA_platform_surfaceless`, perfil de compatibilidade). A conversão da cena e o `GPU_init` continuam tendo GL
  corrente; o GLEW resolve as funções por `glXGetProcAddress`, que com o libglvnd despacha para o contexto EGL. O
  `libEGL` é aberto por `dlopen` (o player não linka com ele; sem EGL/Mesa o `--server` falha ao criar a janela com
  mensagem `GHOST headless: ...`). `run_net_test.sh` sobe o `--server` sem xvfb e com `DISPLAY` removido.
  Windows/macOS: `createSystemHeadless()` cai no sistema normal, ainda com janela mínima (100×100).
- **Dedicated.** Com `--server`, `host()` e o modo Host da cena abrem a sala como Dedicated (sem jogador do host no lobby).
  `join()` funciona, com aviso (um cliente que não desenha só serve de bot).
- **Pausa entre quadros.** O laço de recuperação de `UpdateSleepTime()` converte a espera em milissegundos inteiros e
  dorme 0 ms para esperas menores que alguns quadros; sem swap para bloquear, o servidor girava num núcleo inteiro.
  `ServerSleep()` dorme o resto do quadro (menos 0,5 ms que o laço antigo completa). Só vale no modo servidor; o
  caminho normal ficou como estava.
- **Python:** `Range.network.headless` (somente leitura) diz se o processo é um servidor headless.

Medido no Linux (4 núcleos, llvmpipe, `halfanim_crash.range` com armaduras, servidor sozinho, 5 s e 25 s de jogo):

| Modo | CPU (user+sys) 5 s | CPU 25 s | Ticks em 24 s |
|---|---|---|---|
| normal (janela 160×120) | 16,3 s | 37,7 s | 1176 (abaixo de 60/s) |
| `--server` | 1,5 s | 4,2 s | 1446 (60/s) |

Ou seja, ~0,13 núcleo em regime contra ~1 núcleo no modo normal. Antes do `ServerSleep()` e do corte do skinning o
`--server` gastava ~1,6 núcleo (dois terços no skinning das armaduras).

**Windows/MSVC validado** (2026-10-04, `run_net_test_win.sh server`): passou de primeira, sem o problema de
janela GL offscreen que trava o Linux sem xvfb (o GHOST do Windows abre a janela 320×240 sem bloquear mesmo em
`--server`). `headless=True`, não renderiza, hospeda como Dedicated — tudo igual ao Linux. Não testado: Android/Web
(sem sentido para servidor).

## Validado no Windows/MSVC (2026-10-04)

`run_net_test_win.sh spawner`, `car`, `predict` (5 rodadas) e `server` passam no Windows com os três commits
desta branch (`11a0c1e7` reconciliação, `45012fc0` lag compensation, `8b5885c5` propriedades de objeto
previsto), confirmando `Range.network.headless`/`isServer`, a predição completa e o servidor headless na
engine MSVC. `run_net_test_win.sh` ainda não tem os cenários `scene`/`scene-server` (dependem do editor Windows,
que também não linka — `IMB_exr`, problema pré-existente, igual ao Linux).

**Windows/MSVC revalidado com `08816d92`** (2026-10-04, Rig com propriedade replicada `ammo`): `spawner` PASS,
`predict` 3/3 rodadas PASS (22-23/22-23 hit in the past em cada uma, sem necessidade de `NET_DEBUG=1`), com a
nova checagem `prediction: the owner gets the rig's replicated property ammo values [19, 20, 21, 22, 23]`
passando igual ao Linux — confirma que `8b5885c5` (propriedades de objeto previsto chegam ao dono) também
funciona no nível de engine, não só no núcleo de rede. `server` PASS de novo, sem erro de janela GL.

**Armadilha de build encontrada:** depois de um `git checkout` para esta branch, `ninja RangeRuntime` não
recompilou `KX_PyNetwork.cpp.obj` mesmo com o `.cpp` já mais novo que o `.obj` (`ninja -n` não via nada
pendente). O binário rodava com o módulo `Range.network` antigo (sem `predict`, `rpc`, `headless`...),
causando `AttributeError: module 'Range.network' has no attribute 'headless'` mesmo com o código-fonte
correto. Causa não totalmente isolada (suspeita: cmake regenerando o `build.ninja` e perdendo o stat do
arquivo, ou timestamp do checkout não propagado a tempo do primeiro scan do ninja). **Contorno**: apagar o
`.obj` suspeito antes de rebuildar (`rm build/.../KX_PyNetwork.cpp.obj && ninja RangeRuntime`) força a
recompilação; depois disso o `ninja -n` volta a detectar mudanças normalmente. Se depois de um `git
checkout`/`pull` um símbolo novo "não existir" em runtime apesar de estar no `.cpp`, suspeite disto antes
de supor bug de código.

## Uso rápido

Sem código: Properties > Export Game > **Network** (modo, portas, Server Name, máximo de jogadores, tick rate,
taxa de envio, game id/versão), Properties > Object > Game > **Network** (Replicate e opções), checkbox **Rep** nas
Game Properties. O modo da cena (Host, Client, Dedicated) abre a sessão ao iniciar o jogo; no modo Client o endereço
é `host`, `host:porta` ou `[v6]:porta`. Todos precisam do mesmo `.range`.

Com script:

```python
import Range.network as net

net.replicate(obj, props=["hp"], velocity=True)   # antes de host()/join(), na mesma ordem em todos
net.on_connect(lambda client_id: print("conectado", client_id))
net.on_player_join(lambda client_id, name: print(name, "entrou"))

net.playerName = "Maria"                           # vale para o próximo join()
net.host(7777, max_players=4, room_name="Sala")    # ou net.join("192.168.0.10:7777")
car = net.spawn("Car", owner=1, position=[0, 0, 2])  # servidor; "Car" fica numa camada inativa
```

## Testes

Resultados no `docs/changelog.md` (entrada "Multiplayer: núcleo ligado na engine"). Como repetir no Linux:

```bash
cmake --preset linux-runtime -S source -DPYTHON_ROOT_DIR=/usr -DPYTHON_EXECUTABLE=/usr/bin/python3.11
cmake --build build-linux --target RangeRuntime -j4
# Python 3.11 precisa de numpy < 2 (o do apt serve ao Python 3.12): pip install --target /opt/py311-site "numpy<2"
PYTHONPATH=/opt/py311-site tools/net_engine_test/run_net_test.sh spawner     # ou car; 3o argumento: "100,20,2" (simulador)
PYTHONPATH=/opt/py311-site tools/net_engine_test/run_net_test.sh server      # spawner com o servidor em --server (Dedicated)
# modo cena (precisa do editor: cmake --preset linux-editor ... -DWITH_CYCLES=OFF -DWITH_OPENIMAGEIO=OFF
#   -DWITH_OPENCOLORIO=OFF -DWITH_COMPOSITOR=OFF -DWITH_CYCLES_EMBREE=OFF; cmake --build build-linux-editor --target RangeEngine)
PYTHONPATH=/opt/py311-site tools/net_engine_test/run_net_test.sh scene        # ou scene-server (cena Host + --server)
```

O `RangeEngine -b` precisa de `BLENDER_SYSTEM_SCRIPTS=source/release/scripts` e `BLENDER_SYSTEM_DATAFILES=source/release/datafiles`
fora de uma instalação (o runner já define). O editor completo e o preset `linux-editor` com Cycles/OIIO/OCIO/Embree **não** foram
compilados aqui (só a versão enxuta acima).

### Windows (2026-10-04, MSVC, `build/`)

Compila sem mudança. `tools/net_engine_test/run_net_test_win.sh spawner|car ["100,20,2"]` (Git Bash) abre dois
`RangeRuntime` em janelas 320×240; cada um recebe um `TEMP` próprio, porque o player grava os `NETTEST` em
`%TEMP%
ange_runtime.log.txt` (o stdout não chega ao shell). Passaram: `spawner` (círculo 382/382 amostras, `hp`,
spawn, lobby, chat, LAN), `car` (cliente segue o carro a 4,93 m/s) e `spawner` com simulador 100,20,2. Editor:
painéis Network da cena (hoje em Properties > Export Game) e do objeto (Properties > Game, checkbox no cabeçalho) desenhados
certos numa janela (screenshot). Modo `scene` (editor gera os `.range`) não foi rodado no Windows.

Limites dos testes: a máquina de teste tem 4 núcleos e rasteriza por software (llvmpipe, 160×120), então o quadro
é lento (5–15 fps) e o servidor às vezes para por centenas de ms; o teste de trajetória tolera isso (80 % das amostras na curva).

### Windows (2026-10-04, modo cena)

`run_net_test_win.sh` ganhou `scene` e `scene-server`, espelhando a versão Linux: chama `RangeEngine.exe -b
--python make_net_scenes.py` (sem xvfb, não é necessário no Windows) para gerar `net_host.range`/`net_client.range`
a partir de `halfanim_crash.blend`, e os dois cenários passam (`NETSCENE PASS` + `NETTEST server/client PASS`),
incluindo o caso Dedicated (`scene-server`: host headless não aparece em `net.clients`). `spawner` revalidado sem
regressão depois da mudança nos caminhos de cópia do `.range` (agora por papel, `ts/scene.range` e `tc/scene.range`,
em vez de um único arquivo compartilhado).

- **Esquema de protótipo antes do spawn.** O cliente decodifica os campos do `Spawn` com o esquema do protótipo
  antes de criar o objeto; `SchemaFor` monta o esquema do objeto inativo se ainda não existe (`CacheProtoSchema`).
  Sem isso, protótipo com propriedade replicada travava toda a replicação no cliente.

## Revalidação Linux na main `9e7925f` (2026-10-04, nuvem)

- `PYTHONPATH=/opt/py311-site tools/net_engine_test/run_net_test.sh <cenário>`: spawner, car, server, scene,
  scene-server e rpc PASS; predict PASS 3/4.
- Falha intermitente do predict: `max_error` 0,6 com 21 correções (normal: 0–0,067, 0–1 correção). Investigar.
- Sem o `PYTHONPATH` acima o player cai em `AUD_initPython` (segfault por `numpy` ausente): não é bug de rede.

### Investigação do `predict` intermitente (Linux)

- 16 rodadas com `NET_DEBUG=1`: todas PASS, mas o erro máximo varia de 0 a 0,33, com 0 a 15 correções por rodada; a falha anterior (0,6) é a cauda dessa distribuição.
- O erro é sempre múltiplo de 1 tick de input (2,0/30 ≈ 0,067), inclusive em trechos de velocidade constante. Hipótese: o servidor não recebe o input a tempo do tick e aplica `InputQueue::consume` com repetição (até `maxRepeatTicks = 4`) ou sem input (`missing`). Com o simulador 40,5,1 e a renderização por software, quadros lentos do cliente atrasam os inputs.
- Carregar a CPU não reproduz: a falha passa a ser "server applied the client's input" (poucos frames), não o erro de predição.
- Os contadores `late`/`repeated`/`missing` da `InputQueue` não estão expostos ao Python, então a hipótese ainda não foi confirmada. Próximo passo proposto: expor esses contadores no servidor (por exemplo, em `prediction_stats` do lado do servidor) e cruzá-los com as correções do cliente, antes de decidir entre corrigir o motor ou ajustar a margem do teste.
- **Confirmada** com `network.input_stats(client)` (novo, só no servidor: `received`, `duplicates`, `late`, `too_far`, `applied`, `repeated`, `missing`, `invalid`), logado pelo `predict` a cada mudança. Em 6 rodadas: as 5 com `late` 0 a 5 tiveram 0 correções; a com `late` 95 (`repeated` 95) teve 2 correções (erro 0,13). Os ~30 `missing` de toda rodada são os ticks antes do primeiro input do cliente (início), não afetam o erro.
- Causa: o tick de predição do cliente às vezes não fica adiantado o bastante em relação ao servidor e o input chega depois do tick simulado; o servidor repete o anterior e o cliente reconcilia. Próximo passo: medir a folga (tick do input − tick do servidor na chegada) e ajustar a margem de adiantamento do `NetClock::predictionTick`, em vez de afrouxar o 0,5 do teste.
- **Folga medida** (log temporário em `InputQueue::receive`: tick do input − próximo tick do servidor): a linha de ticks do cliente só crescia de um em um e ficava em qualquer ponto até ±8 ticks do alvo, diferente a cada rodada (folga de 3 a 11 nas boas, de −3 a 5 na ruim). Corrigido: `ClientPredict` segue a deriva suavizada (média 0,1; passa de 1,5 tick → dois passos no quadro ou nenhum), o passo foi para `ClientPredictTick`, e a margem do `predictionTick` subiu de 1 para 2 ticks. Em 8 rodadas: todas PASS, erro máximo ≤ 0,134, folga com espalhamento de ±4 ticks e centro ainda variando de ~0 a ~4 entre rodadas (3 rodadas com `late` 47 a 82).
- Resta um viés por rodada na estimativa do relógio (offset dos `Pong`). Próximo passo proposto: o servidor devolver a folga medida (por exemplo, no `Pong` ou numa mensagem nova) e o cliente ajustar a margem por ela; é mudança de protocolo, então fica para uma tarefa própria.
- **Feito com a mensagem `201 InputTiming`** (contrato fechado em 2026-10-04, `docs/multiplayer-protocol.md` seção 5, após o `predict` passar no Windows: 5 rodadas PASS, erro 0, 0 correções) (S→C, canal 2, a cada 15 ticks): `InputQueue::slack()` suaviza a folga de cada `Input` recebido; `KX_NetworkManager::SendInputTiming()` manda a cada cliente; o cliente chama `NetClock::addInputSlack()`, que move o adiantamento 30% do erro em relação ao alvo de 3 ticks por relato (limitado a ±1 s). `prediction_stats(obj)` ganhou `lead_adjust`. Em 8 rodadas do `predict`: todas PASS com erro máximo 0 e 0 correções; `lead_adjust` final de −2,4 a +3,5 ticks (o viés de cada rodada); `late` 3 a 21 por rodada, sem correção. Testes do núcleo: 113 PASS (build `NET_STANDALONE`).
- **De onde vêm os `late` restantes** (2026-10-04, log temporário em `InputQueue::receive`, 7 rodadas PASS): 0 a 11 por rodada, espalhados pela rodada inteira (não só na convergência); todos são o bloco de **1 ou 2 ticks** antes do `nextTick`, quase sempre numa mensagem cujo `newestTick` já está à frente (folga média 2 a 3,3 no momento). Ou seja: o pacote original daquele tick e as cópias redundantes seguintes não chegaram a tempo (perda de 1% do simulador ou um quadro atrasado), não um viés do relógio. Nenhum gerou correção. Decisão: alvo (3) e ganho (0,3) ficam; não vale subir o alvo (custa latência sempre para cobrir um tick raro). **Causa confirmada** (mesmo dia): com perda 0 (`net-sim 40,5,0`) o Linux ainda dá 5 a 8 `late` por rodada (com 1%: 9 a 12), e a redundância de 8 blocos torna impossível um `late` só por perda de 1%; logo são soluços de agendamento do container (4 vCPUs, servidor e cliente na mesma máquina), não perda. No Windows (máquina dedicada) o `predict` deu `late` 0 em 5 rodadas, PASS, 0 correções: coerente, não é falha da contagem (a lógica de `late` é a mesma nas duas plataformas).

## Predição de corpo dinâmico e IPv6 (2026-10-04)
- Cliente dono reativa a física do corpo previsto (`SetDynamicPredicted`); grava o estado após o Bullet em `ClientTickEnd`; replay = passo + `pos += v*dt`; reconcilia só o transform. Validado com `run_net_test.sh predict-cube`. Veículo não funciona (suspensão por raycast não é refeita no replay).
- Objetos da cena com dono: `Ownership` reenviado quando o cliente fica ativo.
- IPv6 só no WebSocket (dual-stack, `AF_UNSPEC`); ENet 1.3.x é só IPv4 e recusa literal IPv6.
