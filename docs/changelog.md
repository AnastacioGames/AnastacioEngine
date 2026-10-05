# Changelog — AnastacioEngine

Registro histórico do que foi feito, alterado ou adicionado no fork. Entradas antigas preservam o contexto
da época e podem conter hipóteses corrigidas em entradas posteriores. Para o estado vigente, consulte
`docs/roadmap.md` e `relatorio-melhorias-anastacioengine.md`.

**Como está organizado.** Este arquivo guarda as entradas mais recentes (novas entradas vão no topo, como sempre). O histórico mais antigo está em `docs/changelog/`, dividido em arquivos de até ~70 KB para caber na leitura de uma IA. Quando este arquivo passar de ~60 KB, mova as entradas mais antigas para um novo arquivo em `docs/changelog/` e acrescente uma linha na tabela abaixo.

Para achar uma entrada por assunto: `grep -rn "^## .*termo" docs/changelog.md docs/changelog/`.
Entradas antigas não estão em ordem cronológica estrita; a data no título é a referência.

## Logic: registro de properties Timer em `addObject`/`endObject` deixa de ser O(n²) (2026-10-05)
- Achado na varredura pelo mesmo padrão do `::timebomb`: estado interno ou busca cara em código que roda por objeto criado/destruído. `KX_Scene::AddReplicaObject` e `KX_Scene::RemoveObject` percorriam as properties com `GetProperty(i)`, mas o container é um `std::map` e `EXP_Value::GetProperty(int)` anda desde o início a cada chamada — com n properties, n²/2 passos por `addObject` e de novo no `endObject`. O índice também era `unsigned short`.
- Agora os dois loops iteram o map direto pelo novo `EXP_Value::GetProperties()` (referência const). Comportamento igual; a checagem `GetProperty("timer")` continua (é no map de sub-properties de cada valor, quase sempre vazio).
- Padrão para futuras revisões: (1) estado interno guardado como property de usuário; (2) `GetProperty("nome")` em loop de frame ou por objeto; (3) `new EXP_*Value` onde bastaria um número; (4) `GetProperty(i)` por índice; (5) estado escondido aparecendo em `getPropertyNames`/replicação/2DFilter. Varredura de `gameengine/` (GameLogic, Ketsji, Rasterizer, Converter) não achou outros casos: o restante são properties do usuário lidas por logic bricks, `Text`, sol, veículo e uniforms do 2DFilter (já filtrados às usadas pelo shader) — mantidos por design; `probe*`/`earthquake_level` só rodam na conversão.
- Teste: `projects-teste/object_life/gen_timer_props.py` (43 properties com 3 Timers, 200 `addObject`+`endObject`, timers da réplica avançam) — PASS no Windows; `gen_object_life.py` segue PASS.
- Revalidado após o rebase sobre o trabalho da nuvem (SIGTERM do RangeRuntime, warning do ENet): build `RangeEngine`/`RangeRuntime` limpo no Windows e os dois testes PASS (2026-10-05). As saídas `.blend`/`_log.txt` desses testes ficam no `.gitignore`.

## Logic: tempo de vida de objetos (`addObject(..., time)` / `obj.life`) nativo, sem property `::timebomb` (2026-10-05)
- Sugestão do Kitsuy (Discord, 2026-10-04), revisada antes de aplicar. Antes, cada objeto com tempo de vida guardava uma property oculta `"::timebomb"` (`EXP_FloatValue` alocado no heap, com refcount) e `KX_Scene::LogicBeginFrame` fazia `GetProperty("::timebomb")` (busca por string num `std::map`) para cada objeto temporário, a cada frame. Agora é um `float m_lifeTime` em `KX_GameObject` (segundos restantes, 0 = vive para sempre).
- Efeitos colaterais da property antiga que somem junto: `::timebomb` aparecia em `getPropertyNames()`, contava em `GetPropertyCount()`, era replicada (`GetReplica`) a cada cópia do objeto e entrava como uniform no `SCA_2DFilterActuator` (que liga todas as properties do dono).
- `obj.life` passou a ser leitura **e escrita**, em frames lógicos de 50 Hz (mesma unidade de `scene.addObject(obj, ref, time)`; constante única `KX_GameObject::LifeFramesPerSecond` no lugar dos `0.02`/`50.0` duplicados). Escrever > 0 arma/reajusta o timer de qualquer objeto ativo; `0` ou `None` cancela. Continua retornando `None` (não `0.0`) para objeto sem tempo de vida, para não quebrar scripts.
- Corrigido em relação ao patch original: (1) o setter guardava o valor sem converter de frames para segundos (`obj.life = obj.life` mudava o valor); (2) escrever `life` num objeto que não nasceu com tempo não fazia nada, porque ele não entrava em `m_tempObjectList` — agora `KX_Scene::SetObjectLifeTime` mantém a lista sincronizada; (3) escrever `life` num objeto inativo (template) é recusado com `ValueError`, senão o template seria removido e `addObject` quebraria; (4) o construtor de cópia não herda `m_lifeTime`.
- Bug antigo corrigido junto: `KX_Scene::MergeScene` (LibLoad com merge) não transferia `m_tempObjectList`, então objetos temporários da cena mesclada nunca morriam.
- Outros `GetProperty("...")` por frame no C++ revisados (`Text`/`Text-Res` de fontes e texto bitmap, `sun_hour`/`sun_direction` do mundo, debug de veículo): ficam como estão, porque são properties de usuário que precisam ser controláveis por logic bricks e custam 1–2 buscas por objeto, não uma por objeto temporário.
- Teste: `projects-teste/object_life/gen_object_life.py` (gera a cena com o editor em `-b`, roda no `RangeRuntime`, log em `object_life_log.txt`) — PASS no Windows: vida via `addObject`, escrita via Python, cancelamento com `None`, ida e volta sem perda, erros de tipo/negativo, template inativo protegido e ausência de `::timebomb` em `getPropertyNames()`.

## RangeRuntime: corrige SIGTERM ignorado (2026-10-05)
- O item do roadmap ("handler instalado, processo segue rodando") estava com a causa errada: não havia handler
  nenhum de `SIGTERM` — só `SIGSEGV`/`SIGABRT` (dump de crash) em `GPG_Ghost.cpp`. Adicionado
  `signal(SIGTERM, sigHandleTerm)` (seta `LA_SigTermRequested`, `std::atomic<bool>` novo declarado em
  `LA_Launcher.h`/definido em `LA_Launcher.cpp`), checado em `LA_Launcher::EngineNextFrame()` uma vez por
  quadro — como o loop já processa eventos de forma não bloqueante (`m_system->processEvents(false)`), a
  checagem nunca fica presa esperando. Reaproveita `KX_ExitInfo::OUTSIDE`, o mesmo código de saída do fechar
  de janela (WINCLOSE/WINQUIT), então o shutdown é idêntico ao caminho já testado.
- Relevante sobretudo para `RangeRuntime --server` (modo Dedicated headless, usado em `run_net_test.sh
  server`/`scene-server` e por qualquer orquestrador que precise parar o processo com `kill`/`SIGTERM` em vez
  de `SIGKILL`).
- Testado manualmente: `RangeRuntime --server` iniciado sem display (`env -u DISPLAY -u WAYLAND_DISPLAY`),
  `kill -TERM <pid>` — saída limpa em ~0,1 s (antes, o processo não saía sozinho). Regressão
  `run_net_test.sh server` e `spawner` PASS no Linux (`build-linux-editor`), sem warnings novos no build.

## Multiplayer: corrige warning do switch em NET_TransportENet (ENET_EVENT_TYPE_DISCONNECT_TIMEOUT) (2026-10-05)
- `NET_TransportENet.cpp:161`: o `switch` sobre `event.type` não tratava `ENET_EVENT_TYPE_DISCONNECT_TIMEOUT` (valor de enum exclusivo do fork `zpl-c/enet`, ausente no ENet clássico), gerando warning `-Wswitch` no build. Corrigido empilhando esse case junto de `ENET_EVENT_TYPE_DISCONNECT` (mesmo tratamento: reporta `Disconnected` e limpa o peer — timeout é só outra forma do peer cair).
- Revalidado: build sem warnings e testes 100% PASS em Linux (`build-linux`, 0,30 s) e wasm32 (Emscripten 6.0.11, `build-wasm`, 0,18 s).

## Multiplayer: troca do ENet pelo fork zpl-c/enet (IPv4-only por ora), validado no Linux e wasm32 (2026-10-05)
- Vendor `source/extern/enet` trocado: o ENet clássico 1.3.18 (multi-arquivo, IPv4-only) saiu, entrou o header único do [`zpl-c/enet`](https://github.com/zpl-c/enet) (`include/enet/enet.h`, upstream sem modificações) + `enet_impl.c` novo (TU que faz `#define ENET_IMPLEMENTATION`, exigido pela lib single-header). `CMakeLists.txt` do vendor reescrito para biblioteca header-only.
- O fork por padrão cria socket dual-stack (IPv6 com mapeamento IPv4). A sandbox de build não tem pilha IPv6 (`AF_INET6` indisponível), e nesse modo `host()` falhava com uma mensagem enganosa ("could not listen on port NNNN (in use?)"). Como a API (`net.host`/`net.join`) ainda não expõe IPv6, mantido **IPv4-only** por enquanto via nova opção de CMake `ENET_IPV4_ONLY` (ON por padrão, propagada `PUBLIC` porque muda o layout de `ENetAddress`) — comportamento e layout de `ENetAddress` idênticos aos do vendor antigo.
- Regressão completa no Linux (build incremental, sem rebuild total): `spawner`, `rpc`, `predict`, `server`, `scene`, `scene-server`, `scene-change`, `predict-cube`, `car` — todos PASS. Regressão wasm32 (Emscripten 6.0.11, Node.js): core tests via CI filter (sem sockets/ENet) — **PASS** (100%, 0,18 s).
- Falta: rebuild/teste no Windows (MSVC); teste de `::1` real (desligando `ENET_IPV4_ONLY` numa máquina com IPv6); decisão sobre expor IPv6 na API Python. Detalhes em `NOTES-engine.md` ("IPv6 no ENet/UDP — investigação").

## Multiplayer: cliente no navegador real contra o `RangeRuntime --server` (2026-10-05)
- `Network/tools/net_web_watch.cpp` (Emscripten, gera `net_web_watch.html`): cliente wasm do núcleo que entra por WebSocket num servidor da engine (opções `host`, `port`, `game`, `version`, `hash` na query da página ou como `chave=valor` no node), responde `SceneLoaded` e conta `Spawn`/`Snapshot`; o resultado vai para `document.title` (`NETWEB PASS|FAIL`).
- O servidor imprime o hash da cena no log de "network: hosting ..." (`scene hash <hex>`), que o cliente avulso precisa para o `Hello`.
- `tools/net_engine_test/run_net_web_test.sh` (+ `net_web_server.py`, `net_web_browser.js`): `RangeRuntime --server` hospeda `halfanim_crash.range` com porta WebSocket, a página é servida por HTTP e aberta no Chromium headless (Playwright). 3 rodadas PASS (1 Spawn, 40 snapshots distintos, Chromium 141); `spawner` PASS. Emscripten 6.0.11.
- Não coberto (então): o runtime Web completo (`RangeRuntime` em wasm com o `KX_NetworkManager`) não foi compilado aqui; o caminho `createWebClientTransport` dele é o mesmo transporte exercitado por este teste.
- **Runtime Web completo, ponta a ponta (2026-10-05, Windows, Chrome real não-headless)**: validado com o build já existente (`build-web-release`, preset `web-runtime-release`) servido via `python -m http.server` e aberto num Chrome de verdade (não headless) com `--remote-debugging-port`, dirigido por `tools/web/verify-package.cjs` (CDP: clica "Jogar", lê console). Cenário: `tools/net_engine_test/make_net_web_scenes.py` (novo) autora `net_host.range`/`net_client.range` a partir de `halfanim_crash.blend` com o editor real (Spawner replicado, `hp` replicado) — o host roda nativo (`RangeRuntime --server`, modo cena HOST com `websocket_port`), o client é o pacote Web (modo cena CLIENT) empacotado por `package-web.py`. Como o pacote não aceita `-p` (sem CLI no navegador), o client leva um Always+Python controller embutido (`net_web_client_check.py`, criado via `bpy.data.texts`) que mede `net.isConnected`, a propriedade `hp` mudando e o Spawner se movendo, e imprime `NETWEB client PASS|FAIL ...` no console. Resultado: `NETWEB client PASS connected=True hp_changed=True moved=True`; servidor confirma `a client joined` com nome `Player` e replicação do `spawn()`. Primeira validação real de replicação de objeto + propriedade de ponta a ponta entre o `RangeRuntime` nativo e o build Web no navegador (não é mais só o transporte isolado do `net_web_watch`).
- **Achado (cuidado de deploy, não bug)**: a cena Client, quando o destino é o navegador, precisa ter o endereço (`game_settings.network.address`) apontando para a **porta WebSocket** do host (`websocket_port`), não a porta ENet (`port`) — `NET_TransportWebClient` envolve `host:port` em `ws://host:port/` literalmente. Usar a porta ENet (como no teste `scene`/`scene-server` nativo) faz o handshake WS falhar e o cliente cair (`disconnected reason 2`). Documentar isso em qualquer guia futuro de export multiplayer para a Web.
- Troca de cena durante a partida (`net.change_scene`, commit WIP 7df911c) agora testada: `run_net_test.sh scene-change` PASS (servidor, cliente que acompanha a troca e cliente que entra depois dela; Box e Shot replicados na Arena2). A falha era da fixture, não do motor: `scene.objects.link()` dá à base as camadas da cena, e `Object.layers` só atualiza a base da cena do contexto (Arena1), então o `Shot` ficava na camada 1 da Arena2, ativo, e `net.spawn("Shot")` não achava o protótipo inativo. `make_scene_change.py` agora define `scene.object_bases[nome].layers`. `spawner` e `rpc` PASS.

## Multiplayer: relevância por distância e faixa/bits por propriedade float (2026-10-04)
- **Relevância**: campo `Relevance Radius` da cena (`RangeNetworkSettings.relevance_radius`, Export Game > Network; 0 = tudo relevante, o padrão, sem versioning). O servidor chama `Replicator::setClientView` a cada tick (`KX_NetworkManager::UpdateClientViews`): centro = primeiro objeto replicado do cliente; sem objeto, tudo relevante. `Range.network.set_client_view(client, center=None, radius=None)` sobrescreve (centro = objeto seguido ou posição; raio 0 = tudo; tudo `None` volta ao padrão da cena). "Always Relevant" segue valendo.
- **Float quantizado**: `bProperty.net_min/net_max/net_bits` (RNA `net_min`, `net_max`, `net_bits` em `GameFloatProperty`); a linha "Bits / Min / Max" aparece sob a propriedade Float com "Rep". 0 bits = 32 bits crus; faixa inválida avisa e cai para cru. Vale também para `net.replicate(props=[...])`.
- Testes: cenário novo `relevance` (Spawner sai da vista e congela no cliente, Rig dentro continua) PASS; `scene` checa o round trip do DNA e que o float `heat` (8 bits, 0..10) chega na grade 10/255; `spawner` e `server` PASS.

## Multiplayer: `--server` sem janela nem display no Linux (2026-10-04)
- `GHOST_ISystem::createSystemHeadless()` + `intern/ghost/intern/GHOST_SystemHeadless.h`: sistema GHOST sem display, janela virtual com contexto OpenGL EGL surfaceless do Mesa (`libEGL` por `dlopen`, sem dependência de link). `GPG_Ghost.cpp` usa esse sistema com `--server`; nos outros sistemas cai no `createSystem()` (Windows segue com a janela pequena).
- `run_net_test.sh`: o `--server` roda sem `xvfb-run` e com `DISPLAY` removido. `server`, `scene-server` e `spawner` PASS (servidor 0,98 s user de CPU em 10 s).

## Multiplayer: predição de corpo dinâmico, posse de objeto da cena e IPv6 no WebSocket (2026-10-04)
- **Posse de objeto da cena**: `Replicator::update` reenvia `Ownership` dos objetos da cena com dono ao cliente que fica ativo (objeto da cena não tem `Spawn`, então um `set_owner` feito antes do cliente ficar pronto se perdia). Teste `SceneObjectOwnerReachesClientThatWasNotReady`.
- **Predição de corpo dinâmico**: no cliente dono, `net.predict` reativa a física do corpo (`SetDynamicPredicted`); o estado do tick é gravado depois do passo do Bullet (`ClientTickEnd`, chamado no `EndTick`); o replay aplica o passo e integra `pos += v*dt`; a reconciliação compara só o transform. Cenário `predict-cube` (`tools/net_engine_test/make_dyn_scene.py`, caixa dinâmica sem atrito, `40,5,1`): PASS, resposta em 0 tick, termina a 0,0004 do servidor, erro máximo 0,195, 0 teleportes.
- **Limitação**: veículo (`createVehicle`) não é previsto direito: o replay não refaz a suspensão por raycast e o carro fica ~0,5 atrás do servidor com correção quase todo tick (cenário `predict-car` removido). Para veículo, usar só interpolação, ou um replay que rode o passo completo do Bullet.
- **IPv6 (núcleo)**: o WebSocket escuta em socket dual-stack (fallback IPv4) e `connectTcp` resolve com `AF_UNSPEC` (`::1`, `[::1]`, nomes); o cliente browser põe literal IPv6 entre colchetes na URL. O ENet embutido (1.3.x) é só IPv4 (`ENetAddress.host` de 32 bits): o cliente ENet recusa literal IPv6 logo de início; IPv6 por UDP exige um fork do ENet com IPv6. Descoberta LAN segue IPv4. O teste por `::1` pula em máquina sem IPv6 (o container não tem; não exercitado aqui). Testes do núcleo: 117 PASS.

## Multiplayer: contrato do `201 InputTiming` fechado (2026-10-04)

- `201 InputTiming` deixa de ser provisória em `docs/multiplayer-protocol.md`, como a `200 RpcFrom`: aditiva, fora do `protocolVersion`. Revalidada no Windows (5 rodadas do `predict` PASS, erro 0, 0 correções) e no Linux. Só documentação; o código já era o definitivo.

## Multiplayer: inputs atrasados restantes medidos (2026-10-04)

- Log temporário (removido) em `InputQueue::receive`: 0 a 11 `late` por rodada do `predict`, espalhados pela rodada, cada um 1 ou 2 ticks antes do `nextTick` e com folga média de 2 a 3,3: pacotes perdidos ou atrasados isolados, não viés do relógio. Sem correções; alvo 3 e ganho 0,3 mantidos. Detalhes em `NOTES-engine.md`.
- Causa: soluços de agendamento do container Linux (persistem com perda 0). No Windows o `predict` com `201` deu PASS, 0 correções e `late` 0 em 5 rodadas.

## Multiplayer: servidor devolve a folga dos inputs (`201 InputTiming`) (2026-10-04)

- Mensagem provisória `201 InputTiming` (S→C, canal 2, ~4 Hz): `u32 tick`, `i16 slack` em 1/16 de tick (tick mais novo de cada `Input` − próximo tick a simular, suavizado). Aditiva como a `200 RpcFrom`: cliente antigo descarta. Documentada em `docs/multiplayer-protocol.md`.
- `InputQueue::slack()`, `KX_NetworkManager::SendInputTiming()`, `NetClock::addInputSlack()`/`leadAdjustTicks()` (alvo 3 ticks, ganho 0,3, limite ±1 s); `network.prediction_stats(obj)` ganhou `lead_adjust`.
- Resultado: 8 rodadas do `predict`, todas PASS, erro máximo 0 (antes até 0,134, e a falha original 0,6); `rpc`, `spawner` e `car` PASS; testes do núcleo 113 PASS com testes novos de mensagem, folga e ajuste.
- Roadmap: os cenários `predict`/`server`/`scene`/`scene-server` e o `--server` no Windows já estavam feitos (`87fe6d1`, `19e1437`); removidos dos abertos.

## Multiplayer: predição do cliente segue o relógio (2026-10-04)

- `KX_NetworkManager::ClientPredict` não cresce mais o tick previsto cegamente de um em um: segue a deriva suavizada em relação a `NetClock::predictionTick` (dois passos num quadro quando fica para trás, nenhum quando fica à frente; ressincroniza só acima de meio segundo, como antes). O passo de um tick foi para `ClientPredictTick`.
- `NetClock::predictionTick`: margem de 1 para 2 ticks (teste `NET_Prediction_test` ajustado).
- Medição (folga = tick do input − próximo tick do servidor na chegada): antes, a linha de ticks ficava em qualquer ponto até ±8 ticks do alvo, diferente a cada rodada, e as rodadas com folga negativa geravam inputs atrasados e correções. Depois, 8 rodadas do `predict`, todas PASS, erro máximo ≤ 0,134. Resta um viés por rodada da estimativa do relógio (0 a 4 ticks), detalhado em `NOTES-engine.md`.

## Multiplayer: `network.input_stats` e causa do `predict` intermitente (2026-10-04)

- `KX_NetworkManager::GetInputStats` e `network.input_stats(client)` (servidor): contadores da `InputQueue` do cliente.
- `net_engine_test.py` (`predict`) loga os contadores no servidor. Confirmado: as correções do cliente vêm de inputs que chegam depois do tick simulado (`late`/`repeated`); detalhes em `NOTES-engine.md`.

## Multiplayer: revalidação no Linux após o merge do PR #4 (2026-10-04, main `9e7925f`)

- `run_net_test.sh` `spawner`, `car`, `server`, `scene`, `scene-server` e `rpc` passam na main; `predict` passou
  3 de 4 rodadas. A falha: `prediction: corrections stay small` com `max_error` 0,6 (limite 0,5), 21 correções,
  0 teleportes; nas rodadas boas `max_error` fica entre 0 e 0,067. Intermitente, ainda sem causa: fica aberto.
- Armadilha do ambiente: sem `PYTHONPATH=/opt/py311-site` o `RangeRuntime` não acha o `numpy`, o módulo `aud`
  falha e `AUD_initPython` dá segfault (`PyModule_AddObject` com módulo nulo) antes de qualquer teste rodar.

## Multiplayer: spawner/car validados no Windows com as 3 correções da predição; armadilha de build achada (2026-10-04, branch `claude/project-thread-l2znr0`)

- `run_net_test_win.sh spawner` e `car` passam no Windows/MSVC com os commits `11a0c1e7` (reconciliação),
  `45012fc0` (lag compensation) e `8b5885c5` (propriedades de objeto previsto) já integrados: `net.headless`,
  `net.isServer` e o módulo `Range.network` completo (predict/rpc/call/...) respondem certo.
- Achado durante a validação: depois de `git checkout` para a branch, `ninja RangeRuntime` não recompilou
  `KX_PyNetwork.cpp.obj` mesmo com o `.cpp` mais novo que o `.obj` (`ninja -n` não via nada pendente); o
  binário rodava com o módulo de rede antigo (sem `headless`/`predict`/`rpc`), dando `AttributeError` em
  runtime apesar do código-fonte estar certo. Contorno: apagar o `.obj` suspeito força a recompilação. Ver
  `NOTES-engine.md` ("Armadilha de build encontrada").
- Pendente: `run_net_test_win.sh` ainda não tem os cenários `server`/`predict`/`scene`/`scene-server` para
  cobrir essas correções direto no Windows.

## Multiplayer: `spawn()` de protótipo com propriedade replicada (2026-10-04, branch `claude/project-thread-l2znr0`)

- Bug: se o protótipo do `net.spawn()` tinha propriedade replicada, o cliente nunca decodificava o `Spawn` nem os
  snapshots (Spawner parado, `Rig` nunca aparece). O cliente pede o esquema do protótipo para decodificar os
  campos do `Spawn`, mas o esquema só era montado em `CreateReplica`, depois do decode. Agora `SchemaFor` monta e
  guarda o esquema a partir do objeto inativo (`CacheProtoSchema`) quando ainda não o tem.
- Achado ao dar ao `Rig` de `projects-teste/halfanim_crash` uma propriedade replicada `ammo` (pelo editor). O
  cenário `predict` agora confere que o dono do objeto previsto recebe `ammo` (cobre `8b5885c` no motor).
- Linux: `predict` ×4 (16/16 a 18/18 no passado), `rpc`, `server`, `car`, `scene`, `scene-server`, `spawner` PASS;
  net_menu 102 passed. Falta Windows.

## Build Linux do editor: `RangeRuntime` linka sem OpenEXR (2026-10-04, branch `claude/project-thread-l2znr0`)

- No `build-linux-editor` (`WITH_IMAGE_OPENEXR=OFF`, `WITH_PLAYER=ON`) o `RangeEngine` linkava, mas o
  `RangeRuntime` falhava com `undefined reference to IMB_exr_*` vindo de `libbf_render.a`. O stub
  (`openexr_stub.cpp`) está em `bf_imbuf`, mas `bf_render` não declarava essa dependência e ficava depois do último
  `libbf_imbuf.a` na linha de link. `source/blender/render/CMakeLists.txt` agora lista `bf_imbuf` em `LIB`.
- Os cenários `scene` e `scene-server` (que usam o editor para gerar os `.range`) passam no Linux.

## Multiplayer: propriedades de objeto previsto chegam ao dono (2026-10-04, branch `claude/project-thread-l2znr0`)

- `ReplicaClient::apply` (núcleo) pulava o objeto inteiro quando ele era do cliente e previsto (`skipOwned` +
  `skipFilter`), então o dono nunca recebia as propriedades replicadas dele (vida, pontos). Agora só o transform e
  a velocidade são pulados; as propriedades seguem o servidor.
- Teste `NetReplication.SkipOwnedLeavesPredictedObjectsAlone` estendido: posição do previsto fica com o cliente,
  propriedade vem do servidor. Núcleo: 111/111. Motor (Linux): `predict` ×3, `spawner`, `rpc`, `car`, `server`
  PASS. O cenário `predict` não cobre isso porque o protótipo `Rig` do `.range` não tem propriedade replicada
  (precisa do editor, que ainda não linka).

## Multiplayer: `view_time` da lag compensation segue o snapshot desenhado (2026-10-04, branch `claude/project-thread-l2znr0`)

- Quando o tempo de render passava do snapshot mais novo, o cliente desenhava esse snapshot mas mandava o
  `renderTick` como tempo de visão; o servidor rebobinava 1–3 ticks à frente do que foi visto e errava ~1 tiro por
  rodada do `predict` (às vezes abaixo dos 80%). `KX_NetworkManager::ClientTickBegin` passa a informar o tick do
  snapshot mais novo com alpha 0. Núcleo não mudou.
- Teste: limite da lag compensation de 80% para 90%; com `NET_DEBUG` o servidor registra a posição do Spawner por
  tick e a mostra em cada tiro.
- Testes (Linux): `predict` 20 de 20 com 100% dos tiros acertando no passado (antes ~94% por rodada); `rpc`,
  `server`, `scene-server`, `spawner`, `car`, `scene` passam; `tools/net_menu/tests` 102 passaram.

## Multiplayer: correção da reconciliação da predição (2026-10-04, branch `claude/project-thread-l2znr0`)

- `KX_NetworkManager` chama `NodeUpdate()` depois de `SetPredictedState`, `ApplyOffset` e `setTransform`. Sem isso
  a posição mundial ficava velha, o replay do passo partia dela e desfazia a correção: o rig do cliente terminava
  longe do servidor (`predict` falhava 7 de 20 vezes, `corrections` subindo com `last_error` 0).
- Testes (Linux): `predict` 19 de 20 (a predição passou nas 20; a falha restante é a lag compensation, 14/18 tiros
  no passado contra 80% exigidos, já vista antes); `rpc`, `server`, `scene-server`, `spawner`, `car`, `scene`
  passam; `tools/net_menu/tests` 102 passaram. Núcleo não mudou.

## Multiplayer: `sender` do RPC nos clientes (`200 RpcFrom`) (2026-10-04, branch `claude/project-thread-l2znr0`)

- Mensagem provisória `200 RpcFrom` (S→C, `u16 fromClient` + corpo do `Rpc`): o servidor repassa `All`/`Others`
  vindos de um cliente com o id de quem chamou; `RpcClient` preenche `RpcCall::caller`, e o `sender` do `@net.rpc`
  deixa de ser sempre 0 nos clientes. Cliente que manda 200 conta violação. Os dois lados precisam desta versão.
- Testes (Linux): núcleo 111 passaram (novos `RelayCarriesTheCaller`, `ClientCannotSendRpcFrom`, ida e volta do
  `RpcFrom`, fuzz do cliente com 200); `run_net_test.sh rpc` com o `sender` no cliente, `predict`, `server`,
  `scene-server`, `spawner`, `car`, `scene` passam; `tools/net_menu/tests` 102 passaram.

## Multiplayer: RPC do jogo (`@net.rpc`) e `obj.net` (2026-10-04, branch `claude/project-thread-l2znr0`)

- `Range.network.rpc` (decorador, alvos `server`/`owner`/`all`/`others`, `reliable`, `owner_only`, `name`) e
  `net.call(name, *args, obj=None)`. Argumentos bool, int, float, str, objeto de jogo, vetor e quaternion; a função
  recebe `sender` (e o objeto, em chamadas de objeto). Registro antes de `host()`/`join()`.
- `obj.net` em todo objeto de jogo: `id`, `replicated`, `owner`, `isOwner`, `call()`, `predict()`.
- `KX_NetworkManager` refaz a tabela de RPC com os internos e os do jogo a cada registro; o núcleo não mudou.
- Testes (Linux): novo `run_net_test.sh rpc` passou; `predict` (agora com RPC no lugar do chat), `server`,
  `scene-server`, `spawner`, `car` e `scene` passam; `tools/net_menu/tests` 102 passaram.
- Não testado: Windows. Detalhes em `source/source/gameengine/Network/NOTES-engine.md`, seção "RPC do jogo".

## Multiplayer: predição do cliente, input e lag compensation na engine (2026-10-04, branch `claude/project-thread-l2znr0`)

- Refaz a `net/engine-predict`, perdida no limite de uso. `NET_Prediction` e `NET_LagCompensation` ligados no
  `KX_NetworkManager`; `Range.network` ganha `predict(obj, fn)`, `set_input(bytes)`, `input(client)`,
  `view_time()`, `prediction_stats(obj)`, `set_hitbox(obj, radius, half_height)` e
  `raycast_past(origin, direction, distance, client, ignore, max_rewind_ms)`.
- Cliente prevê os próprios objetos com `predict()` (passo do jogo com o input, reconciliação com o snapshot, correção
  visual suavizada); servidor aplica o input do dono a cada tick. O bloco de input leva o tempo de vista do cliente
  (no momento do `set_input()`), usado pelo `raycast_past`.
- Núcleo: `ReplicaClientConfig::skipFilter` (o `skipOwned` agora é ligado e pula só os objetos previstos; teste
  `NetReplication.SkipOwnedLeavesPredictedObjectsAlone`) e throttle do ENet desligado ao conectar (descartava
  snapshots, `Input` e `Pong` por segundos com quadros lentos; o relógio do cliente não sincronizava).
- Testes (Linux, `linux-runtime` + editor enxuto): novo `run_net_test.sh predict` passou (rig responde em 0 tick de
  atraso, termina na posição do servidor, 17/17 tiros acertam no passado e 0/17 no presente), 5 de 5 rodadas com a
  versão final; `server`, `scene-server`, `spawner`, `car`, `scene` passam; `tools/net_menu/tests` 102
  passaram; `net_tests` do núcleo 109 passaram.
- Não testado: Windows, predição de corpos dinâmicos, predição pelo modo cena. Detalhes em
  `source/source/gameengine/Network/NOTES-engine.md`, seção "Predição, input e lag compensation".

## Multiplayer: servidor headless `RangeRuntime --server` (2026-10-04, branch `claude/project-thread-l2znr0`)

- Refaz o trabalho da `net/server-headless`, que parou no limite de uso sem chegar ao GitHub (a `net/engine-predict` também
  se perdeu e segue pendente).
- `RangeRuntime --server`: render desligado de vez (`logic.setRender(True)` recusado), dispositivo de áudio `None`, janela
  mínima 100×100, `host()` e cena Host viram Dedicated; `join()` avisa. Lógica, física e poses seguem; o skinning da malha
  é pulado. Novo `Range.network.headless`.
- `KX_KetsjiEngine::ServerSleep()`: o laço de `UpdateSleepTime()` dormia 0 ms (espera truncada para milissegundos) e o
  servidor sem swap girava num núcleo. Só o modo servidor usa o sleep novo.
- Medido (Linux, llvmpipe, `halfanim_crash.range`, servidor sozinho 25 s): `--server` 4,2 s de CPU e 60 ticks/s;
  modo normal 37,7 s de CPU e ~49 ticks/s.
- Testes (`tools/net_engine_test/run_net_test.sh`, Linux, build `linux-runtime` + editor enxuto): novos `server` e
  `scene-server` passaram, `server` com simulador 100,20,2 passou; `spawner`, `car` e `scene` seguem passando.
  `tools/net_menu/tests`: 102 passaram.
- Não testado: Windows (`run_net_test_win.sh` sem o cenário `server`). Detalhes em
  `source/source/gameengine/Network/NOTES-engine.md`, seção "Servidor headless".

## Multiplayer: validação no Windows/MSVC (2026-10-04)

- A integração de rede (`KX_NetworkManager`, `Range.network`, painéis Network) compila no MSVC sem mudança.
- Novo `tools/net_engine_test/run_net_test_win.sh` (Git Bash): servidor e cliente `RangeRuntime` em janelas pequenas, um
  `TEMP` por processo (os `NETTEST` vão para `%TEMP%
ange_runtime.log.txt`). Passaram `spawner`, `car` e `spawner` com
  simulador 100 ms/20 ms/2 %.
- Editor: painéis Network da cena e do objeto (aba Game) conferidos por screenshot numa janela real.
- Painel Network da cena movido para a aba **Export Game** (junto do RangeArmor/Web/Android); o do objeto segue na aba
  Game. Cada um tem uma linha apontando para o outro.
- Não rodado no Windows: modo `scene` do teste. Registro em `source/source/gameengine/Network/NOTES-engine.md`.

## Áudio Web: AudioWorklet no lugar do ScriptProcessorNode (2026-10-04, branch `claude/project-thread-8r9ysi`)

- Novo dispositivo Audaspace `WebAudio` (`extern/audaspace/plugins/webaudio/`, só no Emscripten): `AudioWorkletNode` alimentado pela thread principal via `MessagePort`, sem `SharedArrayBuffer` (não exige COOP/COEP; GitHub Pages e o WebView do APK seguem servindo). O worklet pede o que falta para a fila chegar ao alvo (2 blocos de `mixbufsize`); se faltar dado, toca silêncio e, quando os dados voltam, soma ao alvo o que faltou (até ~0,5 s).
- Só é registrado quando o navegador tem AudioWorklet em contexto seguro; senão, ou com `?audio=sdl` na URL, o player usa o SDL (ScriptProcessor) como antes (`GPG_Ghost.cpp`). Sem exceções: o construtor nunca lança.
- Estado em `Module.rangeAudio` (contexto, blocos, pico, underruns, alvo). `package-web.py` suspende/retoma esse contexto ao esconder a página; `verify-capabilities.cjs audio` lê os contadores dele e confere a ausência do aviso de API obsoleta.
- Validação (Linux, emsdk 6.0.11, `web-runtime-release` completo, Chromium headless): demo Destruction toca a música por AudioWorklet, nenhum aviso `ScriptProcessorNode is deprecated` (com `?audio=sdl` o aviso volta), suspender/retomar ok. Teste isolado Audaspace+WebAudio com carga simulada (quadros de 40 ms, pico de 300 ms a cada 25): 66 quanta silenciosos no primeiro pico, depois 0 em 15 s. No Chromium sem GPU daqui (3–4 fps, pausas de até 1,3 s na thread principal) ainda há buracos, porque essas pausas passam do limite de 0,5 s. **Falta o teste audível no navegador/celular real.**
## Pré-voo Web: teste de falha em material de nós (2026-10-04, branch `claude/project-thread-cya89w`)

- Fecha (no lado de código) a lacuna "link e materiais de nós não foram testados" do M1. A nota do Codex que dizia não haver como injetar GLSL num material de nós estava errada: `Material.script_frag`/`script_vert` são acrescentados por `GPU_generate_pass` ao shader gerado do grafo (`gpu_material_construct_end` → `code_generate_fragment`/`code_generate_vertex`). Nota corrigida em `projects-teste/teste-editor-web/NOTA-SHADER-MATERIAL-NODES.md`.
- `projects-teste/teste-editor-web/criar_m1c_nos.py`: gera `m1c-nos-{fragment,vertex,link}.range` (Shading Nodes, Image Texture → Diffuse BSDF, material `MatNosQuebrado`) com GLSL inválido no fragment, no vertex ou varying de tipos diferentes entre estágios. Roteiro D em `ROTEIRO-M1.md`.
- `tools/tests/web_profile/test_preflight_node_material.py` (7 testes) + `fixtures/preflight-node-material.json`: `WEB-GFX-002` com origem `MA…`, estágio e log; mesmo log em materiais diferentes não é fundido; vertex/link; guarda estática do caminho de injeção (codegen, `gpu_shader.c` e RNA). Suíte `tools/tests/web_profile`: 131 testes, OK (3 pulados), Python 3.11 no Linux.
- **Sem build da engine nesta sessão (nuvem Linux):** as cenas não foram geradas nem executadas no navegador. O modo `link` pode não reprovar, porque o `fragment()` do usuário não é chamado em material de nós.
## Debug Mode: tempos de carregamento no painel de profile (2026-10-04)

- `BL_LoadStats.h`: novo `BL_LoadLog`, log circular de 64 eventos (cena, etapa, segundos, linha completa do console como tooltip, marca de "total") protegido por mutex porque a conversão assíncrona roda em thread de trabalho. Só escreve quando algo carrega; nada por frame.
- Quem alimenta: `BL_Converter` (convert, textures, merge, shaders, `open file`, `link`), `KX_LibLoadStatus::Finish` (`LibLoad total`), `LA_Launcher::InitEngine` (`start scene total`) e `KX_SceneScheduler` (`async scene total`, `add scene total (overlay)`, `add scene total (background)` e `replace scene total`). Cada cena carregada custa um timestamp a mais.
- `KX_DebugMode`: seção **Scene Load** no painel de profile (tabela Cena/Etapa/Tempo, mais recente no topo, totais em amarelo, tooltip com a linha do console e botão Clear). As **Render Queries** e o bloco verde/vermelho de categorias viraram abas recolhíveis (`CollapsingHeader`, abertas por padrão) para o painel não crescer sem limite.
- Correção: o checkbox "Show Render Queries" do menu ImGui guardava um estado próprio iniciado em `false`, enquanto a flag podia já vir ligada da cena (`GAME_SHOW_RENDER_QUERIES`) ou de `-g show_render_queries` — a caixa aparecia desmarcada com o painel visível e era preciso ligar e desligar. Agora o valor é lido da engine a cada frame.
- Compilado no Windows/MSVC (`RangeRuntime`, `RangeEngine`). **Não validado em runtime** nesta sessão.

## Logic Bricks → Python Component, fase 6 (2026-10-04, branch `logic/convert-f6`)

- `logic_to_python.py`: Track To com pai, Sound (loop/ping-pong/3D), Movement e Animation Event agora funcionam em sensores/actuators de **outro objeto** (`own=`, estado `Dono/Actuator`, `_plm_init` por dono). Sound reescrito em `_snd_play/_snd_stop/_snd_update` com a flag `m_isplaying` da engine (recomeça após pulso negativo). Novos: Sound 3D e Delay em segundos (antes `Unsupported`).
- Testes: `tools/create_logic_convert_scene_f6.py` (Ray material+x-ray, Collision, Near, Radar, Movement, Delay, Track To com pai e Sound em outros objetos) e `tools/test_logic_convert_f6_codegen.py` (geração + fluxo do Sound com `aud` falso; F5 como regressão: OK). **Sem build da engine**: runtime/CHECK e API 3D do `aud` não validados; roteiro Windows e o que segue brick em `NOTES-logic-f6.md`.

## Logic Bricks → Python Component, fase 5 (2026-10-04, branch `logic/convert-f5`)

- `logic_to_python.py`: actuators **Camera, Constraint (Loc/Ori/Dist/FH), Steering e Mouse Look** de outro objeto agora são convertidos. Os helpers (`_follow`, `_mouse_look`, `_cst_*`, `_steer`) recebem `own=` e agem sobre `scene.objects[dono]`; estado separado por `Dono/Actuator`. Os demais helpers de outro dono seguem como brick.
- Testes: `tools/create_logic_convert_scene_f5.py` (cena com os 4 actuators em outros objetos) e `tools/test_logic_convert_f5_codegen.py` (geração, python puro). **Sem build da engine nesta sessão**: runtime não validado; roteiro Windows em `NOTES-logic-f5.md` (CHECK idêntico nos 4 modos, `LEFT_AS_BRICK 0`).

## Python: atrito anisotrópico em tempo de jogo (2026-10-04)

- Pedido do Kitsuy (Discord). `KX_GameObject.anisotropicFriction` (bool) e `KX_GameObject.anisotropicFrictionCoefficients` (vetor X/Y/Z, valores >= 0) leem e mudam o atrito anisotrópico com o jogo rodando; antes só valia o que o painel Physics gravava no carregamento.
- `PHY_IPhysicsController`/`CcdPhysicsController`: `Get/SetAnisotropicFrictionEnabled` e `Get/SetAnisotropicFriction`, que atualizam `m_cci` e chamam `btCollisionObject::setAnisotropicFriction` (modo 0 desliga sem perder os coeficientes).
- Teste: `tools/create_anisotropic_friction_test.py` gera um `.range` com duas caixas deslizando; com coeficientes (0, 1, 1) a caixa mantém 5,76 m/s contra 4,03 da caixa normal: `ANISO_FRICTION_TEST PASS` no Windows/MSVC.

## Logic Bricks → Python Component, fase 4 (2026-10-04)

- `logic_to_python.py`: **Ray por material com x-ray** (marca os objetos com o material numa propriedade privada `__lcmat_*` e usa o `rayCast` x-ray; vale também no eixo Gaze); **Collision/Near/Radar** de sensor ligado de outro objeto (`_near`/`_radar` com o objeto dono, `_take` com callback de colisão por objeto); **Sound ping-pong** (`aud.Sound.pingpong()`, Loop Bidirectional e Stop) e som tolerante a falta de dispositivo de áudio; **Track To com pai** (porta de `vectomat` + interpolação Euler, orientação local inicial do pai guardada no `start`).
- Achado: Near/Radar da engine só enxergam objetos **Actor** com física; o helper detectava qualquer objeto com a propriedade. Corrigido com a lista de Actors do carregamento. Sensores Movement/Gaze/VR Head de outro objeto liam o objeto errado sem aviso; agora ficam como brick.
- `tools/create_logic_convert_scene.py`: Veil/Target (x-ray), Faller/Floor/Decoy (Collision, Near, Radar e controle negativo), Turret filho de Pivot (Track To com pai, time=3), Sound ping-pong; `LEFT_AS_BRICK` lista o que sobrou (0).
- Validado no build `linux-editor` headless (`RangeRuntime` sob xvfb): CHECK idêntico em bricks e Component; Module e Script iguais entre si, só `cam y` difere (-0,03 vs -0,04), igual na `origin/main`. Ambiente e contornos de build em [notes-logic-f4.md](notes-logic-f4.md).

## Cutscene: export/import de todos os eventos e Wait Trigger liberado (2026-10-04, branch `cutscene/events`)

- **Export/import JSON.** `cutscene_native_events.py` mapeia as 18 ações (`spawn_object`, `dialog`, `camera_path`, `wait_trigger`…) para o tipo e as propriedades RNA de cada evento; `cutscene_native_export.py` grava `schema_version: 2` (`{cena: {"sequences": [{name, cutscene_id, events}]}}`, preserva nome e `cutscene_id`) e `cutscene_native_import.py` aceita legado, v1 e v2, valida objetos obrigatórios/valores antes de criar o evento e rejeita ações desconhecidas.
- **Wait Trigger.** `KX_CutsceneManager::ReleaseTrigger()` encerra a espera (com latch para trigger liberado antes da espera). `KX_Scene::UpdateCutscene` libera por mensagem com *subject* = nome do trigger; novo `scene.release_cutscene_trigger(name)` em Python. `Start()`/`Stop()` agora limpam espera e latches (antes um restart herdava o Wait anterior). Liberação por propriedade não foi feita (ver `docs/notes-cutscene-events.md`).
- **Testes.** Headless do editor: `cutscene_native_export_regression.py` (ida e volta de todos os tipos campo a campo, enum RNA × tabela, export estável, recusa de obrigatório ausente), `cutscene_native_import_regression.py` (legado/v1/tipos não-spawn/erros) e `cutscene_persistence_regression.py`. Runtime: `tools/create_cutscene_wait_test.py` gera um `.range` que o `RangeRuntime` (xvfb) executa — Wait Trigger por Python, por mensagem, com latch e restart: `CUTSCENE_WAIT_TEST PASS`.
- **Build Linux (headless).** `linux-editor` e `linux-runtime` compilaram com Python 3.11 do apt (python.org bloqueado pelo proxy) e sem Cycles/Compositor/OCIO no editor, sem OCIO no runtime; ver notas. Windows/MSVC não compilado nesta sessão.
## Multiplayer: núcleo ligado na engine (branch net/engine, 2026-10-04)

- **`KX_NetworkManager`** (`Ketsji/`): cria servidor/cliente do núcleo (ENet, mais WebSocket no servidor se a porta existir), implementa `net::IWorld` sobre `KX_GameObject` (transform, velocidades, propriedades Boolean/Integer/Float, "dormindo", spawn/despawn por réplica de objeto inativo, dono) e roda no passo fixo: `KX_SimulationPipeline::Update` chama `BeginTick` (recebe e aplica) antes da lógica e `EndTick` (captura e envia) depois da física. Liga `SetUseFixedTimestep` ao abrir a sessão e restaura ao sair; o cliente adota o tick rate do servidor e `SetTicRate` de script é ignorado com aviso enquanto conectado. Cena Offline não cria o gerente.
- **Lobby**: chat pelo `ChatMsg`, pronto/iniciar por três RPCs internos (`net.ready`, `net.ready_state`, `net.start`), host listado como cliente 0, LAN (`LanResponder`/`LanDiscovery`), simulador de rede para o próximo host/join.
- **DNA/RNA/UI**: `RangeNetworkSettings` em `GameData.network` (modo Offline/Host/Client/Dedicated, portas ENet e WebSocket, tick rate, taxa de envio, Server Name, máximo de jogadores, endereço, game id/versão, LAN, late join), `RangeNetObjectSettings` em `Object.net` (Replicate, `net_id` aleatório salvo no `.range`, transform/velocidade/velocidade angular, sempre relevante, interpolar, prioridade) e `PROP_REPLICATED` em `bProperty.flag`. Versioning: cenas antigas ganham os defaults (`BKE_scene_network_defaults`); objetos antigos ficam zerados e o primeiro "Replicate" semeia os valores. Duplicar objeto gera outro `net_id`; na conversão id 0 ou repetido vira um id derivado do nome (determinístico) com aviso. Painéis "Network" na cena e no objeto (aba Game) e botão "Rep" em Game Properties (`properties_game.py`).
- **`Range.network`** (alias `bge.network`, `KX_PyNetwork.cpp`): `host`, `join`, `disconnect`, `set_ready`, `send_chat`, `start_game`, `discover_lan`, `set_simulation`, eventos `on_connect/on_disconnect/on_reject/on_chat/on_start` (+ `on_player_join/leave`), atributos `isServer`, `isConnected`, `playerName` (escrita), `roomName`, `maxPlayers`, `clients` (`id`, `name`, `ping`, `ready`, `isHost`), `tick`, `rtt`, `localId`; extras `replicate`, `spawn`, `despawn`, `set_owner`, `owner`, `is_owner`, `net_id`. Senha de sala ignorada com aviso (o `Hello` v1 não tem campo) e código de sala não resolve (sem lobby).
- **CMake**: `add_subdirectory(Network)` em `gameengine/`, `ge_network` na LIB do `ge_ketsji`, `ge_network extern_enet` nas libs do `blenderplayer`, `../Network` nos includes do Ketsji e do Launcher. Núcleo `Network/` **sem alteração** (só `NOTES-engine.md` novo).
- **Início pela cena**: `LA_Launcher::InitEngine` abre a sessão quando o modo da cena não é Offline (`StartFromScene`).
- **Testes (Linux, 2026-10-04)**: build headless `linux-runtime` (`-DPYTHON_ROOT_DIR=/usr`, Python 3.11 do apt + numpy<2 em `PYTHONPATH`) e `linux-editor` sem Cycles/OIIO/OCIO/compositor. Núcleo: 108/108 gtests. Engine: `tools/net_engine_test/run_net_test.sh` sobe dois `RangeRuntime` sob `xvfb-run`: `spawner` (halfanim_crash, objeto cinemático numa circunferência, propriedade `hp`, spawn de `Rig`; o cliente fica a 3,98–4,00 de raio; com a máquina ocupada pelo build do editor, algumas amostras caíram dentro do círculo, que é a interpolação cruzando uma pausa do servidor, e por isso o teste exige 80 % na curva; em máquina livre foram 57/57 e 62/62), `car` (Car dinâmico a 5 m/s; cliente mede 4,93 m/s com a dinâmica suspensa), também com `100 ms ± 20 ms e 2 % de perda`, e `scene` (o editor gera os `.range` com `make_net_scenes.py`: versioning, RNA, `net_id`, duplicado, propriedade "Rep" e ida e volta do DNA, depois host/cliente só pelo modo da cena). Lobby, chat, pronto/iniciar, `discover_lan` (achou a sala por broadcast), host de novo depois de `disconnect()`.
- **Não testado / pendente**: Windows/MSVC (nada compilado lá); painéis desenhados numa janela do editor; servidor sem janela (`--server` não existe: o teste usa xvfb); `RangeRuntime` Web/Android; predição, lag compensation e input não ligados; troca de cena em partida; IPv6. Ver `source/source/gameengine/Network/NOTES-engine.md`.

## Multiplayer: núcleo de rede completo (frentes A–J, 2026-10-04)

- Frentes E–J feitas em sessões na nuvem e revisadas no Windows: replicação (`NET_Replicator`, `NET_ReplicaClient`, `NET_IWorld`, `net_bench`), predição/lag compensation/relógio (`NET_Prediction`, `NET_LagCompensation`, `NET_Clock`), RPC (`NET_RPC`, `ServerSession::reportViolation`), descoberta LAN (`NET_LanDiscovery`, `net_echo lan`), telas de pausa/configurações/LAN do menu e CI com wasm32 e Docker.
- Correções na integração: `ASSERT_NE(ptr, nullptr)` não compila com o gtest do repo no MSVC (trocado por `ASSERT_TRUE`); conflitos do `CMakeLists.txt` do `Network/` resolvidos à mão.
- Verificado no MSVC: 108/108 gtests, 102/102 pytest, `net_echo lan` acha o servidor local, `net_bench` 0,79 ms/tick e 32 KB/s por cliente.

## Edit Mode, UV editor, tema e Logic Bricks com visual no estilo Blender 5

- Edit Mode (`drawobject.c`): face ativa com preenchimento translúcido sólido (sem stipple); arestas suaves de 1,5 px escalados por DPI; vértices e face dots redondos.
- UV editor (`uvedit_draw.c`): face ativa sem stipple; arestas sempre suaves (antes só com a opção Smooth), 1,2 px por DPI; modo Outline com halo escuro translúcido em vez de linha preta de 3 px; pontos redondos escalados por DPI. Grade sem imagem ganhou borda clara no espaço 0..1 (`ED_region_grid_draw`).
- Tema: Active Vert/Edge/Face = `#ff5d0033` (laranja, alpha 0,2) em todos os presets de `interface_theme`, no default de `resources.c` e via versioning em preferências salvas (`RANGE_MINSUBVERSION` 115 → 116; bloco 1.6.116 em `versioning_userdef.c`, 3D View, tema global e Image Editor).
- Logic Bricks (`ui_draw_link_bezier`): curva com 64 segmentos, halo escuro de 4,5 px + linha de 2 px escalados por DPI; cor padrão cinza claro em vez de preto.

## 3D View: contorno de seleção, prévia do Ctrl+R e wireframe com linhas suaves

- Contorno do objeto selecionado (`draw_mesh_object_outline`) desenhado com `GL_LINE_SMOOTH` + blend, como grid, eixos, câmera e empty; desligado no picking.
- Prévia do loop cut (`ringsel_draw`): linha magenta suave com 2 px escalados por DPI e alpha leve; pontos redondos de 4 px.
- Wireframe de mesh no Object Mode (modo Wireframe e opção Wireframe do objeto): suave e com 1,5 px escalado por DPI, em vez de 2 px fixos.
- Pendentes: wire do Edit Mode e de curvas/texto/metaball ainda sem suavização; ruído pontilhado do contorno em arestas de fundo não verificado.

## Vários UV maps: tangentes do UV pedido, fallback para o ativo e transformUV

- Tangentes passam a ser calculadas a partir do UV map que o material pede (campo UV Map do Normal Map/Tangent node), não sempre do ativo; antes um normal map no UV2 ficava com relevo torto. Como os shaders só são criados depois da conversão dos meshes, `BL_ConvertDerivedMeshToArray` lê a árvore de nós (`BL_NodeTreeTangentUv`, entra em grupos) e usa o primeiro UV nomeado entre os materiais do mesh, ou o ativo; o cache de loop data inclui esse UV no hash. O `m_layer` de `RAS_ATTRIB_TANGENT` também passou a guardar o índice do UV. Limite: um só conjunto de tangentes por mesh.
- Python: `KX_VertexProxy.tangent` (somente leitura, xyz + sinal da bitangente), documentado em `bge.types.KX_VertexProxy.rst`.
- `BL_ModifierDeformer`: mesh dinâmico (refeito a cada frame) não calcula mais tangentes enquanto nenhum material lê `RAS_ATTRIB_TANGENT`; atributos vazios (shader ainda não montado) mantêm o cálculo, e um shader que passe a pedir tangente recebe no frame seguinte. Mesh estático continua sempre com tangentes.
- Conferido: pedaços do `KX_DestructionManager` já preenchem todos os UV maps.
- Teste: `tools/create_uv_layers_test.py` (dois planos iguais com UV2 girado; confere tangente X/Y, cache e `transformUV`, grava `uv_layers_test.log` ao lado do `.range` e fecha; `UV_LAYERS_TEST ok`).
- UV/vertex color por nome inexistente no mesh (layer renomeado/removido) caía sem atributo ligado (lixo/zero no shader); agora usa o layer ativo, como o Blender. Vale para nodes (`BL_BlenderShader`) e MTex/shaders Python (`BL_Shader`).
- `mesh.transformUV()`: índice 8 era aceito (leitura fora do array), `uv_index=-1` com `uv_index_from` escrevia no layer -1, a cópia não checava o layer destino e a mensagem de erro de `uv_index_from` mostrava o valor errado.

## Property actuator: lista de Weather Effects atualizada e conversão para Python

- Categorias novas no modo Weather Effects: Rain Splash, Rain Aura, Lightning e Earthquake; Rain ganhou Droplets, Streak Width e Ripple Normal. IDs `ACT_RUNTIME_PROP_WEATHER_*` 28–49 (sem mudar struct); tabela única caminho/tipo/categoria em `DNA_actuator_weather.h`, usada por RNA, Logic Editor e conversor.
- Corrigido: campo Property vazio quando o efeito gravado não pertencia à categoria (agora mostra o liga/desliga dela, e o conversor usa o mesmo fallback); valor Float aparecia como X/Y/Z e o conversor mandava `"x,y,z"` para efeitos Float, que `CM_StringTo` rejeitava.
- Novo `world.getWeather(nome)` (bool ou float). `KX_WorldInfo::SetWeatherRuntimeProperty`/`world.setWeather()`: `droplets`, `earthquake`, `earthquake_level`, `earthquake_scale`, `earthquake_camera`.
- `logic_to_python.py`: Weather Effects vira `scene.world.setWeather(nome, valor)`; World Property (Assign/Add/Toggle) vira `scene.world[prop]`.
- Teste: `projects-teste/weather_logic/make_weather_logic_test.py` gera a versão em bricks e a convertida; as duas conferem com `getWeather` os valores gravados pelos actuators e a ida e volta set/get de todos os nomes (`WEATHER_CHECK ok`).

## Sombra: bias escalado pelo ângulo da luz (fim das colunas em luz rasante)

- `shadow_proj_coord` (`gpu_shader_material.glsl`) agora escala o offset na normal por `0.5 + sin(θ)` e o bias de profundidade por `1 + min(tan(θ), 8)`, com θ = ângulo luz/superfície. Antes ambos eram constantes e a luz quase paralela ao plano gerava faixas de acne.
- A direção da luz vem da própria `shadowpersmat` (ortográfica: linha de profundidade; perspectiva: interseção dos planos x=y=w=0), sem mudar assinaturas nem o codegen. Vale para simple/PCF/cascatas; VSM e sombra pontual não usam essa função.
- Teste: `tools/create_grazing_shadow_test.py` (sol varrendo de a pino até rasante sobre chão + cubo).

## Film Grain vira pós-processamento da cena

- O grão saiu da câmera (`useGrain`/`grainStrength` e `CAM_GFX_GRAIN` removidos; `DNA_camera_types.h` voltou ao `pad`) e foi para `SCENEFXSettings` (`use_grain`, `grain_strength`, padrão 0.035 também por versionamento). A UI fica em Render > Post Processing Shaders, com expandir/viewport/checkbox como os outros efeitos (bit `SCENE_FX_UI_GRAIN` em `expand_flag`/`editor_render_flag`).
- Em jogo continua no passe Lens da câmera; Python: `filterManager.changeGrainValues(enabled, strength=-1)`.
- Viewport: novo passe `GPU_SHADER_FX_GRAIN` (`gpu_shader_fx_grain_frag.glsl`) no compositor, flag interna `SCENE_FX_FLAG_GRAIN`.

## Camera FX: grão de filme nativo e Rolima Racer migrado

- Novo efeito **Film Grain** no passe Lens da câmera (`useGrain`, `grainStrength`; DNA `grain_strength` no lugar do `pad`, flag `CAM_GFX_GRAIN`). Substitui o `NoiseFilterFX.py` do jogo.
- `KX_RenderPipeline::PostRenderScene`: a posição do sol para Lens Flare/Light Scatter não lê mais a câmera ativa quando ela é nula (crash `NodeGetWorldOrientation` visto uma vez na contagem).

## 2026-10-03 - Carregamento assíncrono: materiais compilados com o mundo da cena certa (tom ciano)

- Sintoma (RolimaRacer, `addScene("Pista_1", 0, asynchronous=True)` com a tela de Loading na frente): toda a pista
  com tom ciano (preto do quadriculado verde-azulado, grama ciano), permanente. Síncrono e assíncrono com orçamento
  enorme (tudo num frame) ficavam corretos; `RANGE_NO_SHADER_CACHE=1` não mudava nada.
- Causa: materiais com "constant world/mist" (`MA_CONSTANT_WORLD`/`MIST`, `GPU_select_uniform`) gravam o `GPUWorld`
  global como constante na compilação. A conversão aplica o mundo da cena nova (`UpdateWorldSettings` /
  `UpdateBackGround`) e o síncrono compila em seguida; no assíncrono, entre um lote e outro a cena Loading
  renderiza e deixa o mundo dela no `GPUWorld`.
- Correção: `BL_Converter::UseSceneWorld(scene)` reaplica o mundo da cena destino antes de cada lote em
  `CompileSceneShaders` (addScene assíncrono), no estágio de shaders do LibLoad assíncrono e em `StepReloads`.
- A "câmera TV / pose T / contagem que não termina" não era trava: é a contagem `Contagem_3_2_1` (~200 frames depois
  do Loading, igual nos dois modos); o probe antigo capturava no meio dela. RolimaRacer volta com
  `ASYNC_SCENE_LOAD = True`.

## 2026-10-03 - `addScene(..., asynchronous=True)`: shaders compilados aos poucos, tela de loading segue animando

- `KX_SceneScheduler`: cena pedida com `asynchronous=True` é convertida (sem shaders, `BL_Converter::ConvertScene(scene,
  false)`) e fica fora de `getSceneList()` (sem lógica nem desenho) enquanto `BL_Converter::CompileSceneShaders`
  compila materiais dentro do orçamento de `setLibLoadFrameBudget` (pelo menos um por frame). Pronta, entra na
  lista como um `addScene` normal (overlay no fim, fundo no início). Pedido repetido com o mesmo nome é ignorado
  como hoje; `StopEngine` libera as cenas ainda pendentes (`DestructPendingScenes`). Padrão (`False`) não muda.
- `[Load] async scene "<nome>": N materials, shaders X ms, ready after Y ms`.
- Teste (cena com 80 materiais e 5 lâmpadas): `addScene` volta em 0 ms, primeiro frame 127 ms (conversão), depois
  ~55 ms por frame (um shader com 5 luzes já passa do orçamento); pronta em 4,6 s, lógica da cena só começa aí.
- RolimaRacer: `BrainCore` (estado 3/4 do loading) usa `asynchronous=True` com orçamento 30 ms e espera a cena
  aparecer em `getSceneList()` (limite de 120 s).

## 2026-10-03 - Nó Object Info também em materiais Blender Internal

- `node_shader_object_info.c`: compatível com `NODE_OLD_SHADING | NODE_NEW_SHADING`. Antes só Cycles; em material
  BI o nó era pulado (saídas zero) e o runtime avisava "nodes not supported in the game: Object Info" (visto em
  5 materiais de efeito do RolimaRacer). O jogo já enviava matriz e info do objeto (`UpdateObjectMatrix`).
- Testado: cena BI com Location → Color, cubo em (2, 0, 1) magenta, em (−2, 0, 0) preto.
- Medição do RolimaRacer: Pista_1 21,3 s de shaders com o cache do driver frio (1ª execução após build) e
  0,82 s na segunda; a variação entre rodadas vem desse cache.

## 2026-10-03 - LibLoad assíncrono: orçamento por frame configurável (`setLibLoadFrameBudget`)

- `Range.logic.setLibLoadFrameBudget([ms])` (`BL_Converter::SetMergeFrameBudget`): tempo por frame do merge
  assíncrono, padrão 8 ms; devolve o valor atual. Tela de loading pode subir para ~30 ms.
- `create_load_bench.py` aceita `budget=<ms>`. 20 bibliotecas com lâmpada: 8 ms → 5,3 s (pior frame 20 ms);
  30 ms → 3,6 s (~26 fps).
- Testado e descartado: pré-compilar shaders em paralelo (`GL_ARB_parallel_shader_compile`, presente na NVIDIA)
  antes de usá-los. Só despachar a compilação já custa ~4 ms por shader na thread principal (o driver analisa o
  GLSL na hora); com a reconstrução do material, ganho nulo no total (5,8 s). Código revertido.
- Achado: com lâmpada, cada material novo compila duas vezes (antes de entrar na cena, para não aparecer sem
  shader, e de novo na recompilação final pelas luzes). Evitar exigiria esconder os objetos até a recompilação.

## 2026-10-03 - LibLoad assíncrono: recompilação por luz nova uma vez só, não por biblioteca

- Antes: cada biblioteca assíncrona com lâmpada recompilava todos os materiais da cena logo depois do seu
  merge. 20 bibliotecas com uma lâmpada cada = 20 passadas crescentes.
- Agora (`BL_Converter::StepReloads`, `PendingReload`): toda biblioteca compila só os materiais novos antes
  do merge (os objetos nunca aparecem sem shader); luz nova marca a cena para uma recompilação única, que só
  começa quando nenhuma outra biblioteca está em merge e recomeça se chegar outra luz. As bibliotecas que
  trouxeram luz ficam em `finished = False` (progresso 0,95 → 1) até ela terminar. `RemoveScene` descarta a
  pendência; `FinalizeAsyncLoads` termina tudo.
- `tools/create_load_bench.py` agora registra frames acima de 25 ms (`[LoadBench]`).
- Medido (`create_load_bench.py -- <dir> 20 15 0 async`, 300 materiais): com lâmpadas 9,8 s / 583 frames →
  5,6 s / 311 frames; sem lâmpadas 647 → 301 ms. O que sobra com lâmpadas é a passada única: ~15 ms por
  shader com 21 luzes, um por frame; e um frame de ~230 ms no primeiro merge com lâmpada (não investigado).

## 2026-10-03 - LibLoad assíncrono: progresso real e merge espalhado em frames (tela de loading)

- Antes: `LibLoad(..., asynchronous=True)` pulava de 0 para 0,9 ao fim da conversão na thread, e o merge
  (texturas + shaders) rodava inteiro num frame. `lib_spheres.range` (200 materiais, 4 lâmpadas): um frame de
  ~1 s no fim.
- Conversão na thread: `BL_SceneConverter::SetProgressCallback` relata objeto a objeto
  (`BL_ConvertBlenderObjects`), 0 → 0,6 do `status.progress`.
- Merge na thread principal (`BL_Converter::StepMerge`, `PendingMerge`): ~8 ms por frame, no mínimo um passo.
  Texturas (0,7), depois shaders um material por passo (até 0,95), depois o merge da cena; `finished` só no fim.
  Sem lâmpada nova, os materiais novos compilam contra a cena de destino antes dos objetos entrarem (mesmo
  shader do merge síncrono). Com lâmpada nova, o merge vem antes e todos os materiais da cena recompilam um por
  passo, de trás para frente (os novos, ainda sem shader, primeiro); até lá os shaders antigos seguem válidos,
  só sem a luz nova. `FinalizeAsyncLoads` (fim do jogo) termina tudo de uma vez.
- `MergeScene(to, converter, postConvert)`: com `false` não roda texturas nem recompila (o chamador faz).
  LibLoad síncrono não muda.
- Medido com `projects-teste/shader_cache_test/make_async_test.py` (log por frame em `async_log.txt`):
  com lâmpadas, 1,71 s com frame de 1015 ms → 1,58 s, nenhum frame acima de 19,3 ms, 90 frames de barra;
  sem lâmpadas, 694 ms, máximo 17 ms (uma rodada com cache do driver frio teve um frame de 464 ms: um shader
  sozinho não divide). Síncrono igual ao anterior.
- Limite: o `LibLoad` em si (abrir e linkar o arquivo) continua síncrono, 28 ms neste teste. `onProgress`
  segue desativado; a tela de loading lê `status.progress` a cada frame.

## 2026-10-03 - Carregamento: imagens das texturas decodificadas em paralelo

- Medição (80 PNG 2048², `[Load]` + cronômetros temporários): a etapa de texturas levava 2,2 s, sendo ~1,9 s
  de decodificação do PNG e ~0,6 s de upload. Mipmaps já eram gerados na GPU (`U.use_gpu_mipmap`).
- A decodificação era serial porque `BKE_image_acquire_ibuf` segura o spin lock global de imagem durante a
  leitura. Novo `BKE_image_prefetch` (`image.c`) decodifica em paralelo (`BLI_task_parallel_range`) com as
  mesmas flags, colorspace e fonte (arquivo ou packed) de `load_image_single`, que depois só pega o buffer
  pronto; o resto do caminho (alpha, fonte bitmap, autopack, upload) não muda. Só imagens de arquivo simples,
  não multiview e ainda não carregadas.
- `BL_PostConvertBlenderObjects` junta as imagens dos materiais (texture slots e nós, inclusive grupos) antes
  de `InitTextures`; vale para a cena inicial e para o LibLoad. `RANGE_NO_IMAGE_PREFETCH=1` desliga.
- Resultado: texturas 2,18 s → 0,69 s; captura de tela idêntica (diferença zero) com e sem.

## 2026-10-03 - Carregamento: normais/tangentes e BVH de física compartilhadas entre malhas iguais

- Etapa 4 do plano "Cozinhar" sem formato novo. Cópias Shift+D são Mesh separadas com dados idênticos, então o
  reaproveitamento por ponteiro (`FindGameMesh`, `FindMesh`) não as pegava.
- `BL_ConvertDerivedMeshToArray`: normais por loop e tangentes MikkTSpace ficam num cache por conteúdo
  (`BL_LoopDataHash`: vértices, arestas com sharp, loops, faces com smooth, autosmooth e UV ativa), válido só
  durante `BL_ConvertBlenderObjects`. Malhas com normais customizadas não entram. A camada `CD_TANGENT` tem 16
  floats por elemento (legado), então a cópia cria a camada e copia só os 4 de cada loop.
  `RANGE_NO_LOOPDATA_CACHE=1` desliga para comparação.
- `CcdPhysicsController.cpp`: a BVH da malha triangular (`btOptimizedBvh`) era construída por objeto, até em
  duplicatas linkadas, e era quase todo o tempo de física. `CcdSharedBvhTriangleMeshShape` reaproveita a BVH de
  arrays de vértices/triângulos idênticos (dois hashes de 64 bit + tamanhos); cada objeto mantém a própria forma
  e arrays, então trocar a malha física de um não afeta os outros. A BVH é liberada com a última forma que a usa
  (mutex por causa do LibLoad assíncrono). Sem welding (soft body) e Gimpact continuam como antes.
- 800 esferas (`tools/create_shader_fps_test.py`): conversão 2,9 s → 0,8 s (malhas 1,8 s → 0,54 s com 93 ms de
  hash; física 1,03 s → 0,25 s). Imagem com e sem cache de normais/tangentes (`spheres.range`): 22 pixels
  diferentes, abaixo do ruído de alpha entre rodadas iguais. Colisão: bolas sobre chãos copiados, linkados e uma
  cópia deslocada param cada uma na altura do próprio chão.

## 2026-10-03 - Fast Shader Loading no painel Render

- O modo de valores como uniform (entrada abaixo) virou opção por jogo: Render > Shading > Shader Compilation >
  Fast Shader Loading (`use_fast_shader_loading`, flag `GAME_FAST_SHADER_LOAD`, bit 5 de `GameData.flag`). O painel
  mostra o ganho (carregamento: 800 materiais 64 s → 5 s) e a perda (até metade do FPS com muitas luzes).
- `LA_Launcher::InitEngine` liga o modo com `GPU_material_uniform_values_set` antes de converter os materiais;
  `ExitEngine` desliga, então o viewport segue compilando com constantes. `RANGE_SHADER_UNIFORM_VALUES=1` ainda
  força ligado.
- O bit 5 era `GAME_DISPLAY_LISTS` em arquivos 2.7x: `versioning_range.c` limpa o bit em arquivos anteriores a
  1.6.115 (`RANGE_MINSUBVERSION` 114 → 115).
- Teste: cena de `tools/create_shader_fps_test.py` com a opção ligada compilou 30 programas (770 reaproveitados,
  shaders 1,2 s) e rodou a 29,5 fps; o arquivo antigo abriu com a opção desligada.

## 2026-10-03 - Carregamento: medição por etapa, cache e biblioteca GLSL enxuta, merge do LibLoad

- Etapas 1 e 2 do plano "Cozinhar" (arquivo preparado para o jogo). `BL_LoadStats.h` e o console agora mostram
  linhas `[Load]` com o tempo de cada etapa (abrir, link, conversão, merge/shaders) e quantos shaders foram
  compilados ou reaproveitados.
- `gpu_codegen.c`: cache de programas GLSL. Materiais cujo código gerado, flags e biblioteca são idênticos
  compartilham o mesmo `GPUShader`; os uniforms continuam sendo enviados a cada bind. Os programas sem uso
  ficam guardados até 256, com descarte do mais antigo, então voltar a uma cena reaproveita os shaders.
  `RANGE_NO_SHADER_CACHE=1` desliga o cache para comparação.
- `BL_Converter::MergeScene`: o LibLoad sem lâmpada nova compila só os materiais novos. Com lâmpada nova continua
  recompilando tudo, porque cada shader percorre as lâmpadas da cena.
- Benchmark (`tools/create_load_bench.py`, opções `async`/`nolamp`): shaders da cena inicial (200 materiais)
  12,2 s → 5,1 s; 10 LibLoads sem lâmpada ~13 s cada → 214 ms no total; LibLoad com lâmpada 12–25 s → ~5 s.
- Limite: com "constante" ligado (padrão), cor/especular entram fixos no GLSL, então só materiais de valores
  idênticos compartilham programa. Cada compilação custa ~48 ms.
- Validação visual: `tools/create_shader_cache_test.py` (200 esferas, vários modelos de shading, shadeless,
  emit, alpha, ramp, textura) e `tools/compare_images.py`. Com e sem cache, as imagens diferem só em 48 pixels
  na fileira transparente; duas rodadas sem cache já diferem em 26 pixels ali (ordenação de alpha).
- Biblioteca GLSL enxuta (`glsl_lib_strip` em `gpu_codegen.c`): o fragment shader recebia a biblioteca de
  materiais inteira (~195 KB) em cada compilação. Agora ela é dividida uma vez em blocos de nível superior e
  cada shader leva só as funções que o código gerado alcança, direta ou indiretamente, com todas as sobrecargas
  do mesmo nome. Diretivas `#` (inclusive com recuo), uniforms, structs e constantes ficam sempre.
  `RANGE_NO_GLSL_STRIP=1` volta a enviar a biblioteca inteira. Cena de 200 esferas compilando cada material
  sozinho: 11–14 s → 3,2 s no total. Comparação pixel a pixel com e sem corte: idêntica em 7 cenas de nós
  (vidro, probe, céu Hosek, cabelo, IES, sombra de ponto, nós) e nas esferas (só o ruído de alpha já conhecido);
  `ripple_normal_test` é animada e varia entre rodadas iguais. Cenas com print injetado:
  `projects-teste/shader_cache_test/inject_shot.py`.
- Modo opcional `RANGE_SHADER_UNIFORM_VALUES=1` (`codegen_input_is_uniform` em `gpu_codegen.c`): os valores
  fixos do material (float a vec4) viram uniforms em vez de constantes, então materiais com os mesmos nós e
  valores diferentes compartilham o programa; o valor é enviado a cada bind a partir de `GPUInput.vec`. Esferas:
  shaders 1030 ms → 310 ms (160 → 41 compilados). Imagem: 97 pixels diferentes, no nível do ruído entre rodadas
  iguais (40). Custo por quadro medido com `tools/create_shader_fps_test.py` (800 esferas, 18 luzes,
  1920×1080, sem vsync): normal 57–60 fps, uniform 31 fps (16,7–17,5 ms → 32 ms); com 10 luzes, 60 → 50 fps.
  A compilação nessa cena cai de 64 s para 5 s, mas o custo no quadro é alto: fica desligado e não vira padrão.

## 2026-10-03 - Undo: crash ao voltar muitos passos e continuar editando

- `undo_system.c` (`BKE_undosys_stack_limit_steps_and_memory`): o hack `WITH_GLOBAL_UNDO_KEEP_ONE` testava
  `us->type` em vez de `us_exclude->type`, então nunca preservava o último passo de Global Undo (memfile) ao
  aparar a pilha; passos de edit-mode ficavam sem base e desfazer até eles travava.
- `library_query.c`: `scene->world_sun` não era percorrido; apagar/remapear o objeto do sol deixava ponteiro
  solto na cena.

## 2026-10-03 - Emissor de raio em Empty (onde e quando o raio cai)

- Novo `RangeLightningSettings` no `Object` (`ob->lightning`, opt-in por `gameflag2 & OB_LIGHTNING`, só Empty),
  painel Properties > Object Data > Lightning. Área círculo/quadrado de `empty_drawsize` no plano XY local
  (segue escala/rotação/pai), altura da nuvem, Hit Ground (raycast até a primeira superfície), Target opcional
  (o raio vai da área até o objeto, em qualquer direção), modo Automatic (raios/min, chance de bolt, janela
  Start/End em tempo de jogo) ou Manual, intensidade, largura, cor do glow e distância de fade do flash.
- Disparo pela lógica: `obj.strikeLightning(bolt=True)` e Edit Object > Lightning Strike (`KX_LightningActuator`,
  flag Flash Only).
- `KX_RainLightning` passou a cuidar de vários raios (World + emissores). Os flashes somam no filtro da chuva
  (o clarão de tela precisa de World > Rain ligado); o halo segue o raio mais forte. O raio do World não mudou.
- BKE (`rain_lightning.c`): `schedule_ex` com salt por nome (editor e jogo na mesma agenda), `strike_point`,
  `bolt_at`, `bolt_between`; geometria comum em `build_bolt`. 3D View: preview dos raios automáticos
  (`view3d_rain.c`, mantém o timer de redraw) e overlay da área + linha até a nuvem/target (`drawobject.c`).
- Header da 3D View: o campo de nome do objeto ativo continua visível (apagado) quando o objeto não está num
  layer visível; antes sumia ao trocar de layer. Demo `release/demos/Lightning/Lightning.range` (um exemplo por layer).
- Convert to Python: Edit Object > Lightning Strike vira `ob.strikeLightning(True)` (ou `False` com Flash Only).
  Traduções PT-BR/ES/RU (`translations_ui.py`) de todos os textos do emissor e do raio do World; `i18n_audit.py`
  sem pendências de lightning nos três idiomas.

## 2026-10-03 - Weather: Live UI sem travar, nuvens e chuva na 3D View

- Live UI: editar World > Weather durante o Play travava/crashava porque `ED_render_id_flush_update` liberava
  os GPUMaterials ainda em uso pelo jogo. Agora retorna cedo com `WM_game_live_ui_active()`; os previews de
  shader/ícone (`render_preview.c`) também ficam suspensos nesse modo. O jogo lê chuva, nuvens e flare do
  World a cada frame (`KX_RenderPipeline.cpp`) e o painel desativa os toggles que exigem recompilar.
- `GPU_fx_compositor_initialize_passes` (`gpu_compositing.c`): `scenefx_flag` era `char`. CLOUDS (bit 8) era
  truncado, então as nuvens nunca apareciam na viewport fora do Play; RAIN (bit 7) virava negativo e ligava
  passes sem buffers (SSAO/SSR...), sumindo com os objetos. Agora é `int`.

## 2026-10-03 - Widget de navegação da 3D View no estilo do Blender 5

- `draw_view_axis` (`view3d_draw.c`): saiu o cubo translúcido. Cada eixo positivo termina numa bolinha cheia
  na cor do eixo (cores padrão do Blender 5) com a letra dentro e linha do centro até ela; o negativo é um
  anel translúcido. Ordenado de trás para frente, pontas afastadas um pouco mais escuras, linhas suaves e
  escaladas por DPI. Continua só indicativo (sem clique/hover).
- Revertida a coloração dos eixos de objeto (Display → Axis) em `drawobject.c`, que entrou por engano no
  commit 250ae0ce.

## 2026-10-03 - Edição proporcional: distâncias com KD-tree e Random estável

- `set_prop_dist` (`transform_conversions.c`): o vizinho selecionado mais próximo de cada elemento não
  selecionado agora vem de uma KD-tree (`set_prop_dist_kdtree`), O(N log M) em vez de O(N×M). Vale para o modo
  normal, Projected e ilhas de faces. Só é usada quando todos os elementos têm a mesma `mtx` (edit-mesh) e há
  ao menos 8 selecionados; senão, cai no laço antigo. O início do G/R/S em malhas densas fica bem mais rápido.
- PROP_RANDOM (`transform_generics.c`): o fator vem de um hash do `iloc` em vez de `BLI_frand`, então o
  padrão não pisca ao mudar o raio com a roda do mouse.
- As fórmulas dos outros modos foram conferidas com o Blender e não mudaram.

## 2026-10-03 - Sculpt e pintura mais leves no editor (fases 1 a 3)

Diagnóstico: o código dos pincéis já roda em várias threads; o custo estava no que acontece a cada passo do
pincel. O redesenho da 3D view refazia todos os shadow maps (6 passes por luz pontual, um por cascata) e o
compositor de FX em tela cheia. No weight paint dos bones, cada passo também refazia a pilha de modificadores
(deformação do Armature, numa thread só), recalculava as cores de peso da malha inteira, reenviava o VBO
completo e redesenhava todas as views com `NC_OBJECT|ND_DRAW`.

- Fase 1 (`view3d_draw.c`, `paint_stroke.c`): enquanto `ups->stroke_active` estiver ligado com o objeto ativo
  num modo de pintura (`view3d_paint_stroke_active`), a 3D view reaproveita os shadow maps do último redesenho
  e pula o compositor de FX (sem destruí-lo). Com FX ligado, o redesenho parcial vira completo, para não
  aparecer um retângulo sem FX sobre o último quadro composto. No fim do traço, `stroke_done` envia
  `NC_SPACE|ND_SPACE_VIEW3D`, que traz sombras e FX de volta. O shading final não muda.
- Fase 2 (`paint_vertex.c`, `DerivedMesh.c`): no weight paint, se o `derivedFinal` ainda referencia o
  `me->dvert` (só modificadores de deformação, como Armature), cada passo só refaz as cores de peso
  (`DM_update_weight_mcol` + `DM_DIRTY_MCOL_UPDATE_DRAW`); a pilha de modificadores roda uma vez, no
  `wpaint_stroke_done`. Com modificadores construtivos (Subsurf, Mirror…), cai no caminho antigo. O passo
  agora redesenha só a própria região, em vez de `NC_OBJECT|ND_DRAW`. Novo `DM_weight_paint_draw_flag`.
- Fase 3 (`armature.c`, `DerivedMesh.c`): o laço por vértice de `armature_deform_verts` virou
  `armature_deform_vert_cb` em `BLI_task_parallel_range` (acima de 1024 vértices), lendo o `CD_MDEFORMVERT`
  do DerivedMesh como array em vez de `getVertData` por vértice; `calc_weightpaint_vert_array` calcula as
  cores de peso em paralelo (acima de 4096 vértices). Acelera também animação e Play com Armature.
- Build `RangeEngine` OK. Validado pelo usuário em 2026-10-03 com `projects-teste/perf_paint/perf_paint_test.range`
  (esfera de 32.514 vértices + Armature): weight paint, pose e sculpt OK. Teste em background: deform de 8,1 ms/frame,
  resultado determinístico. Fases 4 e 5 descartadas (vertex/weight paint não desenha via PBVH; sculpt GLSL via
  PBVH mudaria o shading do viewport).

## 2026-10-03 - Gizmo: ajustes do hover; speaker, force fields e metaball suaves

- Hover do gizmo só roda a checagem de seleção com o mouse perto do gizmo (raio ~1.3 × `tw_size` + hotspot) e
  só na janela com o contexto GL ativo (`wm->windrawable`), evitando custo a cada movimento e erro em 2ª janela.
- Círculos de rotação livre (visão e trackball) passam por `manipulator_setcolor_theme`: acendem no hover e
  ficam pretos na passada de contorno (antes eram desenhados com a cor do tema também nela).
- Speaker: antialias e passada transparente, como lâmpada/empty/câmera.
- Metaball: os círculos de raio e rigidez vão para a passada transparente com antialias; a superfície fica no
  desenho normal. Nova flag `DRAW_OVERLAY_ONLY` (`view3d_intern.h`) faz a 2ª passada pular a superfície.
  Com essa flag, `draw_object` só desenha os círculos e retorna cedo (antes repetia contorno de seleção,
  extras, bounds, motion path, centro etc.).
- Force fields: antialias quando o objeto já é desenhado na passada transparente (empties, lâmpadas, câmeras,
  speakers); em malhas continuam como antes.

## 2026-10-03 - Câmera: linhas suaves

- Câmera usa os mesmos consertos de lâmpada e empty: antialias e passada transparente (depois das malhas).
- Largura de linha por `U.pixelsize`. O volume de culling (`GAME_CAM_SHOW_CULLING_BOX`) restaura o depth mask
  e o blend anteriores em vez de forçá-los, para não quebrar a passada transparente.

## 2026-10-03 - Empty: linhas suaves

- Empties (exceto imagem) usam os mesmos consertos da lâmpada: antialias (`GL_LINE_SMOOTH` + blend) e desenho
  na passada transparente, depois das malhas, para não haver contorno preto sobre malhas.
- `drawaxes` com largura escalada por `U.pixelsize`; círculo com 64 segmentos (eram 32); esfera com 48 (eram 16).

## 2026-10-03 - Linhas da lâmpada: sol e linha até o chão

- `drawlamp`: no sol, a linha de direção deixou de ir até `la->dist` (cruzava a cena) e virou um traço curto,
  de tamanho constante na tela, que esmaece na ponta; os 4 raios (antes brancos e fixos em 5 unidades) ficam
  mais curtos, na cor da luz e também esmaecem.
- Linha até o chão: sólida e translúcida, com um pequeno anel no ponto de contato (era um ponto de 2px).
- Lâmpadas desenhadas com `GL_LINE_SMOOTH` + blend.
- Lâmpadas passam a ser desenhadas na passada transparente (`afterdraw_transp`, depois das malhas, com teste
  de profundidade e sem gravar profundidade): as bordas suavizadas não abrem mais buracos pretos nas malhas
  desenhadas depois, e malhas na frente continuam cobrindo a lâmpada.

## 2026-10-03 - Gizmo de transformação: hover e contorno (fase 2)

- Destaque ao passar o mouse: `BIF_manipulator_hover_update` (chamado pelo cursor callback da 3D view a cada
  movimento) usa `manipulator_selectbuf` com os mesmos hotspots do clique e clareia o handle sob o mouse.
- Contorno escuro: o gizmo é desenhado em duas passadas; a primeira desenha só as linhas (hastes, círculos,
  bordas dos planos) em preto translúcido e 2px mais largas. Sólidos (cones, cubos, anéis) não têm contorno.
- Feito em OpenGL imediato com `GL_LINE_SMOOTH`, não com shader GLSL.

## 2026-10-03 - Gizmo de transformação: visual renovado (fase 1)

- `transform_manipulator.c`: linhas com antialias (`GL_LINE_SMOOTH`) e largura escalada por `U.pixelsize`;
  cones/cilindros com 24 lados (eram 8); anéis de rotação 12×96 (eram 8×48); círculos com 64 segmentos
  (`manipulator_circle`); quadrados de plano com contorno opaco (`manipulator_planar_quad`); círculo central
  cinza-claro em vez de preto. Seleção por clique usa a mesma geometria.

## 2026-10-03 - Triângulo "lado de cima" da câmera de volta

- `drawcamera` (`drawobject.c`) volta a desenhar o triângulo acima do frame da câmera, como no Blender 2.79/5:
  contorno em toda câmera, preenchido só na câmera da cena (`scene->camera`); não desenha olhando pela câmera.
  Ícones 3D da câmera continuam iguais.

## 2026-10-02 - Live UI: veículo, componentes, UI escurecida e atalhos de debug

- Veículo ao vivo no Play (`LA_BlenderLauncher::LiveSyncVehicle`): raio, atrito, suspensão, Steering/Drive
  (FWD/RWD/AWD), Max Torque/RPM, câmbio e marchas, volante. Raio, rest length e steering entraram na fila
  `PHY_VehicleParameterCommand` (`PHY_VEHICLE_PARAM_WHEEL_RADIUS`, `_SUSPENSION_REST_LENGTH`, `_WHEEL_HAS_STEERING`),
  aplicada entre passos da física. Painel Vehicle marca com * (e desativa durante o Play, via
  `bpy.app.is_game_live_ui`) o que só vale no próximo Play: Enabled, Center of Mass Offset, objeto da roda,
  Add Wheel, Add Vehicle Component.
- Argumentos de componentes Python ao vivo (`KX_PythonComponent::LiveUpdateArgs`): chama `update_args(args)` se o
  componente definir, senão atualiza `self._args`. O template do Vehicle Player relê teclas, papéis das rodas e
  volante; componentes já copiados para projetos antigos só têm o `_args` atualizado.
- Cadeado fechado: a UI travada é recomposta escurecida (45%) durante o Play (`WM_game_locked_ui_draw`).
- Botão do console ao lado do cadeado (barra da 3D view e painel Player) e do Start do Standalone. Show Profile e
  Debug Mode como ícones flutuantes ao lado do nome da vista, no topo da 3D view.
- Legenda "* Not applied while the game is running" traduzida (PT-BR, ES, RU).

## 2026-10-02 - UI do editor liberada durante o Play (Live UI)

- Cadeado `scene.game_settings.use_live_ui` (`GAME_LIVE_UI`, desligado por padrão) ao lado do Play na barra
  flutuante da 3D view, do Start em Game Settings e do Play (Embedded) do flowmenu. Só no Play embutido; o
  Standalone é outro processo e não é afetado.
- Com o cadeado aberto, `LA_BlenderLauncher::EngineNextFrame` chama `WM_game_live_ui_step` em vez de descartar os
  eventos: cliques/roda/teclas sobre a região do jogo continuam do jogo (nada é filtrado com handler modal ativo),
  o resto vai para o editor. `wm_draw_update_game_live` compõe a janela (método Triple) no back buffer sem trocar
  buffer, antes do quadro do jogo, isolando o estado GL que o jogo deixa ligado (VAO/IBO causava crash no
  `glDrawElements` dos widgets; luz/blend/sRGB escureciam a UI). `DEV_EventConsumer::SetFocusGate`: o jogo só recebe
  cliques e teclas com o cursor na tela dele.
- Bloqueados durante o Play (`WM_operator_poll`): undo/redo, abrir/reverter arquivo, apagar/adicionar/duplicar
  objeto, troca de modo, nova cena, dividir/juntar/maximizar áreas.
- Sincronização (`LiveSyncFromBlender`): a cada evento compara o DNA com a cópia anterior e empurra só o que mudou.
  Partículas GPU (principal e Mix) via `KX_GameObject::ApplyGPUParticlesLive` (quantidade, origem, textura, shader,
  look e curvas recriam o emissor) e Game Properties (valor trocado no lugar). Desligado se o jogo carregar outro .blend.
- Limitações: menu suspenso sobre a tela do jogo fica escondido; edição do formato das curvas de partícula não é
  detectada. Validado pelo usuário no editor (partículas ao vivo, UI sem escurecer).

## 2026-10-02 - Refletor de pista (luz falsa) nas Partículas GPU

- Novo modo **Emit From: Mesh Vertices** (`RangeGPUParticleSettings.emit_from`, antigo `pad5`; layout DNA igual):
  uma partícula fixa por vértice da malha do próprio objeto (malha base, sem modificadores), sem simulação nem
  idade. `RAS_ParticleBuffer::SetStaticPositions` grava as posições locais; `Update()` pula o transform feedback e
  o draw usa `u_model` (transform de mundo atualizado em `KX_GameObject::UpdateParticles`), então acompanha o objeto.
  `Resize()` é recusado nesse modo. Tamanho mínimo aparente pela distância evita sumir/piscar longe.
- Novo look **Reflector** (`GPU_PARTICLE_LOOK_REFLECTOR`): olho-de-gato sem luz real. A "luz do farol" é a própria
  câmera: cone em torno de -Z da view (12°–40°) e alcance 40–120 m. Color = brilho aceso (alfa = intensidade),
  End Color = ponto fraco apagado. Escolher o look já liga Mesh Vertices, aditivo e valores iniciais.
- Objeto com emissor Mesh Vertices ignora o frustum culling do objeto (`KX_GameObject::HasStaticParticles`, em
  `KX_Scene::UpdateGpuParticleEmitters` e `KX_RenderPipeline`): malha só de vértices tem bounding box degenerada
  e os refletores sumiam ao olhar para trás ou com a câmera baixa. A GPU recorta os sprites fora da tela.
- Draw shader ganhou `v_viewPos` (centro em view space), disponível também para `.glsl` customizados.
- Cena de teste `reflector_test.range` (raiz): pista em S, 152 refletores, câmera W/S/A/D. Compila e roda sem erro
  de shader; validação visual pendente.

## 2026-10-02 - Material rápido: receitas de nós prontas no painel do material

- Painel **Quick Material** (Material rápido) no editor de Propriedades > Material, engine Game, para quem não
  quer ligar nós à mão (`bl_operators/anastacio_material_recipes.py`, painel em `bl_ui/properties_material.py`).
  Cada receita monta a árvore nos dois caminhos: PBR (Shading Nodes, Principled) e legado (nós do BI, nó Material
  apontando para um material "<nome> Base", imagens pelo nó Texture com um Texture do tipo Image).
- **Material from Texture Set** (`material.recipe_texture_set`): escolhe um arquivo do pacote e acha os irmãos
  pelo sufixo (albedo/basecolor/diffuse/col, normal/nor/nrm, roughness/rough, gloss, metallic/metal, ao), com
  Mapping de repetição. AO multiplica a cor; normal passa pelo Normal Map; no legado a rugosidade invertida vai no Spec.
- **Blend Textures by Mask** (`material.recipe_mask_blend`): ideia do makcooper no Discord (vários materiais num só,
  1 draw call). Base + 3 camadas (R, G, B) por uma máscara pintada; cria a máscara (imagem preta, Non-Color), a UV
  se faltar, imagens de cor provisórias e um Mapping único de repetição. O painel lista as camadas com o botão de
  abrir imagem, o **Paint the Mask** (Texture Paint com a máscara como canvas) e botões de cor do pincel por camada,
  e avisa quando a máscara pintada ainda não foi salva. Cada camada tem um botão de pasta (`material.recipe_layer_set`): escolhe uma textura do conjunto e a
  normal/rugosidade irmãs entram junto. A árvore é remontada com uma coluna por mapa (cor, normal, rugosidade), as 4
  camadas misturadas pela mesma máscara; camada sem o mapa usa imagem neutra (normal plana, rugosidade 0.8). Normal
  misturada passa por um Normal Map só; no legado a rugosidade invertida vai no Spec. Mapas que nenhuma camada tem
  não geram nós. Imagens trocadas à mão no painel são mantidas na remontagem.
- **Ready-made Material**: Plástico, Metal, Ouro, Borracha, Madeira, Vidro (Glass BSDF e Alpha Blend) e Brilhante
  (Principled + Emission); no legado monta nós: nó Material com difuso/especular do preset + brilho de borda Fresnel (Geometry Normal·View) somado por MixRGB; metal/ouro com borda na própria cor, vidro mais opaco na borda, brilhante soma a cor de emissão. O preset grava `specular_metallic_bsdf`/`specular_roughness_bsdf` (Metallic/Roughness do nó Material, padrão 0.5/0.5 deixava todas as esferas iguais).
- Botão de nós do material (ícone ao lado de Data) no Game legado: `ED_node_shader_default` agora cria um
  **Extended Material** já ligado a uma cópia do material (`<nome> Base`, sem nós, com cor/especular atuais) e liga
  Color e Alpha no Output. Antes vinha o nó Material vazio. As receitas usam o Extended e reaproveitam essa base.
- Malha sem UV ganha Smart UV Project (`ensure_uv`). A UV padrão do `uv_textures.new()` punha cada face na imagem
  inteira: pintando a máscara numa UV Sphere (512 faces) cada pincelada virava 512 e o editor travou com 6 GB.
- Nós achados pelo nome (`AE_*`) e a receita marcada em `material["anastacio_recipe"]`. Neste fork a escala do
  Mapping é socket (`inputs["Scale"]`), não propriedade. Textos traduzidos em `translations_labels.py` (`MATERIAL_RECIPES`).
- Teste: `tools/create_material_recipes_test.py` (com `legacy` gera a cena do BI; a Sun recebe `RAY_SHADOW` porque o
  legado só faz sombra de Sun assim). As duas cenas montam em `-b` e rodam no `RangeRuntime` sem erro de shader;
  pintura da máscara numa esfera sem UV validada pelo usuário (rápida); falta conferir o resultado visual no jogo.

## 2026-10-02 - Deformação: faixa contínua de arrasto, Add Damage Mix e decal que acompanha amassados

- **Scrape Style** (`scrape_style`, bit novo `DEFORM_SCRAPE_STRIP` em `flags`, sem campo novo no DNA): Stamps
  (carimbos, como antes) ou **Strip**. Strip desenha uma faixa plana contínua com a largura do Size e o material do
  Decal, um segmento por Spacing (`KX_DestructionManager::AddStripSegment`). A malha é pré-alocada com 128
  segmentos; os vértices ainda sem uso ficam sobre a última borda (área zero) e cada amostra só move posições
  (sem realocar). Cheia, a trilha continua numa faixa nova a partir da mesma borda. UV: U de lado a lado, V repete a
  cada Size. Não usa a cópia privada da malha nem recorta triângulos (mais leve; melhor em chão plano). Max e Life
  contam faixas inteiras. A normal do contato agora aponta para o objeto que desliza.
- **Add Damage Mix** (`node.damage_mix_add`, botão no painel Deformation quando há material): põe um Mix Shader
  entre a superfície atual e a saída, com Fac = Mask do nó Damage e um Principled metálico enferrujado.
- **Decal acompanha amassados**: cada vértice de um carimbo guarda o triângulo de origem e as baricêntricas;
  `FollowDents` (em `Dented` e `ResetDent`) recoloca os decals do alvo na superfície nova.
- Refatoração: `GetDecalTemplate`, `SpawnDecal` e `TrimDecals` saem de `AddDecal`.
- Teste: `tools/create_damage_marks_test.py`. Validado: build, execução sem avisos e teste visual do usuário.

## 2026-10-02 - Sombra suave da Point, 4 luzes com sombra, Wireframe e IES no viewport

- `shadow_point` (`gpu_shader_material.glsl`): 3x3 amostras a 1 texel, cada uma comparação bilinear e presa
  dentro do tile da face. Vale para Game PBR, materiais BI e viewport.
- Luzes com sombra no loop de luzes: 3 → 4 (`GPU_MATERIAL_NUM_SHADOW_LAMPS`, `NUM_SHADOW_LIGHTS`,
  `RAS_Rasterizer::GPU_SHADOW_LAMPS_COUNT`). Uma unidade de textura a menos para o material (as de sombra ficam no topo).
- Wireframe no viewport: `cdDM_drawMappedFacesGLSL` manda o canto do triângulo por loop (atributo `attbary`),
  com 3-coloração da triangulação de cada polígono (`cdDM_loop_triangle_corners`). O vertex shader usa o
  atributo quando `unfbaryattrib = 1` (só o viewport liga, `GPU_material_viewport_barycentric`); o Game segue
  com `gl_VertexID % 3`. Edit Mode e Subdivision (outros DerivedMesh) ficam sem arestas.
- IES no viewport: `gpu_scene_lights` (`gpu_draw.c`) preenche perfil e eixos por slot e chama
  `GPU_material_bind_scene_lights`.
- Teste: `tools/create_viewport_parity_test.py` → `viewport_parity_test.range`. Validado pelo usuário no Game
  contra o Cycles; log com `--debug-gpu` sem erros de GL.

## 2026-10-02 - Viewport: materiais em nós com as lâmpadas da cena e sombras

- Com engine Blender Game e Shading Nodes, o viewport (modo Material) acendia os materiais em nós com as luzes
  de estúdio (`GPU_default_lights`) e sem sombra. Agora `GPU_begin_object_materials` (`gpu_draw.c`) põe as
  lâmpadas da cena em `gl_LightSource` (`gpu_scene_lights`, mesmos valores de
  `RAS_OpenGLLight::ApplyFixedFunctionLighting`: No Diffuse/No Specular, cone até 90°) e guarda o `GPULamp`
  dos 3 primeiros slots; cada material chama `GPU_material_bind_shadow_lamps`, como o Game.
  `GPU_end_object_materials` volta às luzes de estúdio.
- Fora: IES Texture no viewport (uniforms de `GPU_material_bind_scene_lights` não são enviados) e viewport com
  engine Cycles (fica como antes).
- Log com `--debug-gpu` sem erros de GL. Validado pelo usuário em `point_shadow_test.range`.

## 2026-10-02 - Sombra de luz Point nos materiais BI e no viewport

- Sem Shading Nodes, a Point com `Ray Shadow` ganha o mesmo atlas de cubo 3x2 da entrada de 2026-10-01
  (`gpu_lamp_wants_shadow`). `shade_one_light` lê com `shadow_point_bi` (wrapper de `shadow_point`), com
  `dynpersmat` em espaço da luz. Sem VSM, filtros PCF ou Only Shadow para Point.
- Viewport do editor desenha as 6 faces (`gpu_update_lamps_shadows_world`, `view3d_draw.c`), com
  `GPU_lamp_shadow_buffer_unbind` depois de cada face, igual ao Game: cada `GPU_lamp_shadow_point_face_bind`
  empilha o estado de viewport. Assim a Point passa a ter sombra nos materiais BI do viewport.
- Viewport com materiais em nós continua sem sombra de nenhuma luz (o loop de luzes só é ligado pelo Game).
- Custo: Points com Ray Shadow em cenas BI antigas passam a fazer 6 renders de casters por frame.
- Validado pelo usuário em `point_shadow_bi_test.range` (viewport, Game no editor e RangeRuntime).

## 2026-10-02 - Avisos de GL das texturas com `--debug-gpu`

- Origem dos avisos de textura das sombras: `GPU_texture_bind`/`unbind` e `GPU_shader_uniform_texture` chamavam `glEnable`/`glDisable(target)`, que só serve ao pipeline fixo e é `GL_INVALID_OPERATION` em unidades acima de `GL_MAX_TEXTURE_COORDS` (8), onde o jogo liga shadow maps e probes. Em `point_shadow_test.range` eram milhares de erros por execução. Agora `GPU_texture_unit_fixed_function()` limita essas chamadas às unidades válidas (nenhuma no perfil core). Log com `--debug-gpu` limpo depois da correção; sem mudança visual.

## 2026-10-02 - RangeRuntime: crash ao sair quando o arquivo não carrega

- `GPG_Ghost.cpp`: com um arquivo inválido (ou só `-h`, que vira nome de arquivo por ser o último argumento) o runtime imprimia a ajuda e travava ao sair. A limpeza chamava `BKE_icons_free()` sem `BKE_icons_init()` (a fila `g_icon_delete_queue` nunca foi criada) e `GPU_exit()` sem `GPU_init()`, e usava `window` antes de conferir se a janela existia. Agora as três chamadas só rodam se a parte correspondente foi iniciada. Conferido: sai com código -1, sem crash.

## 2026-10-02 - Loop de tempo validado a 60 Hz

O usuário rodou o jogo real com o monitor em 60 Hz, com v-sync ligado e desligado: comportamento igual, sem perda de tecla nem mudança no veículo, e o FPS não travou em 30. Com v-sync ficou mais suave, sem diferença de FPS. Sem mudança de código.

## 2026-10-02 - Shader Sources recompila ao editar o Text; pré-passada morta removida

- Shader Sources: o shader do material ficava em cache e editar o Text (Vertex/Fragment) não o invalidava, nem no viewport nem ao apertar P. Agora o listener do Text Editor, em `NA_EDITED`, chama `GPU_materials_free_text()`, que descarta os GPUMaterials (normal, instancing e skinning) dos materiais que usam aquele Text e pede redesenho. Recompila a cada tecla; com código incompleto o console mostra o erro até o código voltar a ser válido. Um Text alterado só por Python não dispara a recompilação. Validado pelo usuário em `shader_sources_test.range`.
- `RAS_BucketManager`: removida a pré-passada de profundidade de Clip/Alpha to Coverage (`ALPHA_DEPTH_CUTOUT_BUCKET` e a versão instancing). Esses materiais não passam em `IsAlpha()`, são desenhados no bucket sólido com discard e já gravam profundidade, então o bucket ficava sempre vazio. Sem mudança visual.

## 2026-10-02 - Light probes validados

O usuário validou no jogo a luz difusa local e o reflexo do probe (`probe_reflection_test.range`), a mistura entre probes vizinhos e com o World (`probe_blend_test.range`) e a recaptura do World com a Sky Texture seguindo o World Sun (`sky_follow_sun_test.range`). Sem mudança de código.

Também aceitas pelo usuário as validações manuais de 2026-09-25: Game Settings, FXAA, LOD, Foliage no Web, Shader Sources, painéis Transparency, Options e Subsurface do modo jogo e Asset Browser.

## 2026-10-02 - Spot no Game PBR com a atenuação do Cycles; IES e volumes validados

- **Bug:** no loop de luzes do Game PBR (`scene_light_dir`) a Spot usava o modelo do GL fixo,
  `pow(cos, spotExponent)` com `spotExponent = 128 * Spot Blend` (`RAS_OpenGLLight`): com Blend 0.3 uma Spot
  de 120° virava uma mancha de ~25°. Achado ao validar o IES numa Spot (`tools/create_ies_test.py -- <saida> spot`).
- **Correção:** `smoothstep((cos - cosCutoff) / ((1 - cosCutoff) * Blend))`, o `spot_attenuation` do Cycles; o
  Blend vem de `spotExponent / 128`. Só os BSDFs nodais usam esse caminho; Spots existentes ficam mais largas.
- IES (Point e Spot) e nós de volume validados pelo usuário contra render do Cycles. Comparar com a lâmpada na
  mesma escala de brilho: a Energy do Game não é a Strength do Cycles, e com a lâmpada forte o Absorption e o
  Scatter parecem claros demais (o fundo e a luz é que estão claros). O Principled Volume não ilumina o entorno.

## 2026-10-02 - Nós de volume no Game PBR

Volume Absorption, Volume Scatter e Principled Volume deixam de ser "sem suporte" e viram `~Game`.
Ligados na saída Volume do Material Output sem Surface (`node_shader_output_material.c` passa o Volume
como resultado), desenham nas faces do objeto um meio homogêneo:

- **Espessura:** o raio de visão atravessa a caixa local `[-1, 1]^3` do objeto (o cubo padrão; escala e
  rotação contam) e para na profundidade da cena opaca (cópia do passe sólido), então objetos dentro
  da neblina aparecem. Com as duas faces desenhadas, conta uma vez: face da frente de fora, face de
  trás com a câmera dentro da caixa (`volume_segment`).
- **Luz:** Beer-Lambert por canal; espalhamento simples das luzes da cena no meio do trecho (fase
  Henyey-Greenstein, normalizada como o difuso; com sombra naquele ponto), cor do World como ambiente;
  emissão e blackbody (Stefan-Boltzmann como o Cycles) do Principled (`volume_shade`).
- **Coeficientes:** os do Cycles (absorção `(1 - Color) * Density`, espalhamento `Color * Density`,
  Principled com Absorption Color); atributos (density, temperature) ignorados.
- **Composição:** com Blend Mode Alpha Blend a cópia da cena (a mesma do Glass) é tingida por canal;
  sem a cópia a transmitância vira alpha média. `KX_BlenderMaterial` desliga a sombra de material só
  com Volume, que antes projetava uma caixa sólida.

Teste: `tools/create_volume_test.py` (neblina com esfera dentro, absorção laranja num cubo escalado,
fumaça escura com blackbody 2500 K). Validado por screenshot; falta a validação visual do usuário.

## 2026-10-02 - IES Texture nas lâmpadas do Game PBR

- O nó IES Texture na árvore de nós de uma lâmpada Point ou Spot molda a luz dela no jogo, em todos os BSDFs com loop de luzes (fator em `scene_light_dir`).
- O perfil é lido em C como no Cycles (`util_ies.cpp`, sem editar o Cycles; só tipo fotométrico C), reamostrado em 64×32 (horizontal × vertical), normalizado para pico 1 e guardado numa textura atlas única de até 16 perfis (`GPU_lamp_ies_slot`, `gpu_material.c`). Strength multiplica; a Energy da lâmpada continua dando o brilho.
- Uniforms `unfiesinfo`, `unfiesaxes` e `unfiesatlas` enviados por `GPU_material_bind_scene_lights` nos dois perfis de GL; `RAS_OpenGLLight` resolve o perfil uma vez por lâmpada e manda os eixos dela no espaço de vista.
- Num material o nó continua sem suporte (alerta). O selo do editor mostra `~Game` quando a árvore é de uma lâmpada.
- Teste: `tools/create_ies_test.py` (cone, lâmpada sem IES e perfil assimétrico). Validado por screenshot; falta a validação do usuário.

## 2026-10-02 - Hair Info no Game PBR

- Novo `node_hair_info`: numa malha não há fios, então todas as saídas são zero (Tangent Normal inclusive), como
  o Cycles devolve para geometria que não é curva. Sai da lista de não suportados; selo `~Game`.
- Cena de teste: `tools/create_hair_info_test.py` (saída no Fac de um Mix verde/vermelho; tudo verde = certo).
- Validado: screenshot no RangeRuntime (5 esferas verdes, sem warning de nó não suportado).

## 2026-10-02 - Deformação: marcas de arrasto (Scrape Marks)

- Caixa Impact Decal ganhou **Scrape Marks** (`DEFORM_SCRAPE`), **Speed** (`scrape_speed`) e **Spacing**
  (`scrape_spacing`), com aviso de recurso pesado na UI e no tooltip (cada marca é uma malha nova e o objeto ganha
  cópia privada da malha). DNA: `pad` virou `scrape_speed`, mais `scrape_spacing` e `pad`.
- `KX_DestructionManager::Scrape`: em cada contato (callback de colisão também pedido só por Scrape), mede a
  velocidade de deslizamento no ponto (velocidade relativa sem a componente da normal); acima de Speed, enfileira uma
  marca a cada Spacing percorrido (salto > 8× Spacing começa outro rastro). As marcas saem no Update (fora do passo
  de física), via `AddDecal` alinhado à direção do deslize em vez de rotação aleatória. Recebe a marca o objeto que
  tem Scrape ligado.
- Teste: `tools/create_scrape_test.py` (caixa empurrada uma vez desliza no chão). Validado: build e teste visual do
  usuário.

## 2026-10-02 - Deformação: decals de impacto (mesh decal)

- Painel Deformation ganhou a caixa **Impact Decal**: objeto-modelo (`deform.decal`, numa camada inativa, com o
  material da marca), Size, Max e Life. DNA: `RangeDeformSettings` ganhou `decal`, `decal_size`, `decal_life`,
  `max_decals` (lib-link/expand/library_query como `explosive.effect`).
- Em cada batida que passa do Dent Impulse (e em explosões, no ponto mais perto do centro),
  `KX_DestructionManager::AddDecal` recorta os triângulos já amassados (`KX_DentDeformer::GetTriangles`) por uma
  caixa projetada no ponto (Sutherland–Hodgman), só as faces viradas para a batida, UV 0..1 da projeção, rotação
  aleatória e leve afastamento pela normal. Monta um `KX_Mesh` com o material do modelo (como `KX_MeshBuilder`),
  replica o modelo, troca a malha e parenta ao alvo. Passou de Max, o mais velho do alvo some; Life usa lifespan.
  A malha é liberada (`UnregisterMesh`) no Update seguinte à remoção do decal.
- Limitação: o decal não acompanha amassados feitos depois dele.
- Normal da marca vem da face mais próxima do ponto (a direção da batida pode apontar para dentro).
- Validado: build e teste visual do usuário em `decal_test.range` (`tools/create_decal_test.py`: placa + 5 bolas).

## 2026-10-02 - Deformação: Bend em V no ponto da batida e nó Damage (máscara de dano)

- Bend passa a dobrar em **V no ponto de contato**: as duas pontas ficam paradas e o ponto atingido afunda na
  direção do empurrão (cada lado gira o ângulo que mantém sua ponta no lugar, somando o ângulo da batida). Batida
  numa ponta tomba o resto, como antes. Corrige a barra atingida no meio que abaixava só a ponta de cima.
- Ícones no seletor Mode (Dent = Shrinkwrap, Bend = Simple Deform).
- **Máscara de dano sem cor de vértice**: cada batida/explosão que deforma grava um ponto (xyz local, raio = Radius,
  força 0..1 = 1 − e^(−excesso/Dent Impulse)) em `KX_DentDeformer` (até 16; próximos se fundem, cheio troca o mais
  fraco; Reset Dent limpa). `BL_BlenderShader::UpdateObjectMatrix` envia por objeto via
  `GPU_material_bind_damage` (uniforms `unfdamagehits[16]`, `unfdamagestrength[16]`, `unfdamagecount`).
- Nó novo **Damage** (Input, `SH_NODE_DAMAGE` 1004): entrada Softness, saídas Mask e Strength, calculadas por pixel
  em espaço de objeto (`node_damage` no GLSL). Instâncias da mesma malha têm manchas próprias.
- Validado: build RangeRuntime/RangeEngine. Teste visual do nó Damage pendente.

## 2026-10-02 - Deformação: modo Bend (entortar) e getAppliedImpulse de constraints

- Painel Deformation ganhou **Mode: Dent | Bend**. Bend entorta a parte do objeto além do ponto de impacto
  (poste, placa, grade) em volta de um eixo ⟂ ao eixo comprido (`bend_axis`) e à direção do empurrão, com zona de
  transição suave. Ângulo por N*s acima de Dent Impulse (`bend_angle`), somado até `bend_max_angle`.
  Implementado em `KX_DentDeformer::AddBend` sobre os mesmos offsets por vértice original: UVs, costuras, normais,
  tangentes e Update Physics funcionam igual ao Dent. Explosões entortam na direção centro → objeto; `dent()` em
  Python segue o modo do objeto.
- DNA: `RangeDeformSettings.pad` virou `mode`/`bend_axis`, mais `bend_angle`/`bend_max_angle` (arquivos antigos
  recebem defaults ao ligar Bend).
- `bge.constraints.getAppliedImpulse(id)` sempre retornava 0: `CcdPhysicsEnvironment` implementava
  `getAppliedImpulse` (g minúsculo), que não sobrescrevia `PHY_IPhysicsEnvironment::GetAppliedImpulse`. Renomeado com
  `override`; liga o feedback da constraint para o assert de debug do Bullet.
- Validado: build. Validação visual do usuário pendente.

## 2026-10-02 - Principled Hair BSDF no Game PBR

- Novo `node_bsdf_hair_principled`: absorção σ como no Cycles (Color via sigma_from_reflectance, Melanin com
  eumelanina/feomelanina + Tint, Absorption direto); lobos R, TT e TRT com fresnel dielétrico, larguras pelo mapeamento
  de Roughness/Radial Roughness do Cycles; corpo difuso com a refletância do fio; Coat apaga o R. Random ignorado.
- Sai da lista de não suportados; selo `~Game`. Selos atualizados de Glass, Refraction, Hair e Light Falloff; removido
  o selo desatualizado do Sky Hosek.
- Cena de teste: fileira de cima de `tools/create_hair_bsdf_test.py`.
- Validado: screenshot de versão anterior; último ajuste (corpo difuso) sem build, bloqueado pelo BL_BlenderShader.cpp
  de outra sessão. Validação visual do usuário pendente.

## 2026-10-02 - Hair BSDF com luz (Game PBR)

- `node_bsdf_hair` deixa de ser cor chapada: lobo longitudinal gaussiano em sin(θi) + sin(θo) deslocado pelo Offset
  (2·Offset na Reflection, −Offset/2 na Transmission, como o Cycles), largura RoughnessU; lobo azimutal cos(φ/2) na
  Reflection e gaussiano em torno de φ = π (largura RoughnessV) na Transmission. World entra como ambiente suave.
- Numa malha fechada a Reflection some depois do terminador e a Transmission só passa perto da silhueta (contraluz),
  porque o corpo do objeto bloquearia a luz de trás, como no Cycles.
- Tangent desligado: radial em torno do Z do objeto, como no Anisotropic (fios horizontais, faixa de brilho vertical).
- Cena de teste: `tools/create_hair_bsdf_test.py`.
- Validado: build do RangeRuntime e screenshot (`RangeEngine.exe` não religado, editor aberto). Validação visual do
  usuário pendente.

## 2026-10-02 - Sky Texture segue o World Sun e recaptura do World (Game PBR)

- Com uma lâmpada Sun em Scene > World Sun, o nó Sky Texture (Preetham e Hosek / Wilkie) usa a direção dela em vez
  da gravada no nó. Os coeficientes ficam num slot (`GPU_sky_texture_slot`, até 8 nós) lido por uniforms dinâmicos e
  são recalculados quando o sol gira (`GPU_sky_texture_follow_sun`, chamado em `KX_WorldInfo::UpdateBackGround`).
  Sem World Sun o céu segue a direção do nó, como antes.
- O cubo do World capturado é refeito quando muda o sol (direção, cor, energia), as cores Horizon/Zenith, o sun size
  ou a exposição (`KX_TextureRendererManager::CheckWorldChanged`); reflexos e luz difusa do World acompanham o céu.
- No editor o céu usa a direção do World Sun no momento em que o material compila.
- Cena de teste: `tools/create_sky_follow_sun_test.py` (sol baixando por Python do zênite ao horizonte).
- Validado: build; screenshots nos quadros 90 e 400 mostram o céu e o reflexo passando de azul a pôr do sol.
  Validação visual do usuário pendente.

## 2026-10-02 - Deformação por impacto (amassar a malha)

- Novo painel **Deformation** na aba Physics, abaixo de Explosive (`Object.deform`, `gameflag2 & OB_DEFORMABLE`): Dent Impulse, Dent on Collision, Radius, Depth (m por N*s acima do Dent Impulse), Max Depth e Update Physics. Num objeto também destrutível, batidas abaixo do Break Impulse amassam e as mais fortes quebram.
- `KX_DentDeformer`: cópia privada dos display arrays por instância, criada só na primeira batida (`KX_GameObject::GetDentDeformer`); objetos nunca atingidos continuam com a malha compartilhada e o instancing. Offset por vértice original (`GetOrigIndex`), então costuras de UV e arestas duras não abrem; as UVs não mudam. Normais giradas pela variação das faces vizinhas (preserva arestas duras e normais custom). Nada roda por frame.
- `KX_DestructionManager`: no máximo um amassado por objeto por frame (o contato mais forte), cooldown de 0.1 s por objeto, nada é reenviado quando o vértice já está no Max Depth; explosões amassam o lado voltado para o centro; collision shape (Triangle Mesh/Convex Hull) reconstruído uma vez por frame com Update Physics.
- Python: `KX_GameObject.dent(point, direction, impulse)`, `resetDent()` e `onDent` (callbacks `(object, point, impulse)`, para som e faíscas).
- Direção do amassado orientada para o centro da bounding box (não da origem); aviso de "can't dent" uma vez por objeto; tangentes giradas com as normais (normal map correto no amassado).
- Limitações: objetos com modificadores, armature, shape keys ou soft body não amassam; troca de LOD descarta os amassados.
- Teste: `tools/create_dent_test.py`.

## 2026-10-02 - Refração screen-space no Glass e Refraction (Game PBR)

- Com Blend Mode Alpha Blend, Glass e Refraction refratam a cena atrás: depois dos buckets sólidos o blit de
  `RAS_OFFSCREEN_BLIT_DEPTH` (o mesmo da profundidade) copia também a cor, com mips, em
  `GPU_texture_global_scene_color_ptr`; só é feito quando algum Glass/Refraction compilou e há bucket alpha.
- O raio refratado anda uma espessura fixa (1.0) e é projetado na tela; a Roughness escolhe o mip (desfoque).
  A saída fica opaca (a cena já está na cor). Sem cópia (blend sólido, viewport, captura de probe) usa o World, como antes.
- Limitações: não inverte a imagem como uma lente real; o que está fora da tela ou na frente do vidro não aparece
  na refração; vidro atrás de vidro não se vê.
- Principled: Transmission (× (1 − Metallic), menos o fresnel) mistura a mesma refração, com IOR e rugosidade
  1 − (1 − Roughness)(1 − Transmission Roughness); a cópia só é pedida quando a Transmission é usada. Sem cópia
  (blend sólido) continua ignorada.
- Teste: `tools/create_glass_refraction_test.py`. Validado pelo usuário.

## 2026-10-02 - Paralaxe por caixa no reflection probe e probe sem World (Game PBR)

- Probe cujo Empty é desenhado como Cube usa paralaxe por caixa: meia-medida = Display Size × escala do Empty, nos eixos do mundo (a rotação é ignorada). O raio refletido sai pela primeira face à frente (`unfprobebox`/`unfprobebox2`, campo `box` do `ProbeSlot`). O raio do probe continua escolhendo quais objetos o usam e a mistura.
- Sem World na cena, Principled/Glossy/Glass continuam lendo o probe (antes o ambiente inteiro caía e o espelho ficava preto); fora dos probes o ambiente é preto.
- Teste: `tools/create_probe_box_test.py` (sala com uma cor por parede, chão xadrez e esferas espelhadas).

## 2026-10-02 - Mistura entre reflection probes (Game PBR)

- Cada objeto recebe até dois cubemaps: o probe que melhor o contém (nota 1 no centro, 0 no raio) e o vizinho de nota maior, com peso nota2 / (nota1 + nota2). Sem vizinho, o World capturado entra no quarto externo do raio. Na troca os pesos são zero, então o reflexo não pula.
- Segundo cubemap em `unfprobecube2` (unidade de textura logo abaixo do primeiro), `GPU_material_bind_probe2`; `FindProbe` devolve `ProbeSlot[2]` e o peso. Reflexo e luz difusa misturam; cada cubemap usa a própria paralaxe.
- Teste: `tools/create_probe_blend_test.py` (sala vermelha e verde, esfera espelhada indo e voltando).

## 2026-10-02 - Paralaxe no reflection probe (Game PBR)

- O reflexo do probe local deixa de supor o cubemap no infinito: o raio refletido parte do ponto da superfície e bate numa esfera centrada no probe, com o raio do probe; a direção do centro até esse ponto lê o cubemap (`env_probe_mirror`, uniform `unfprobepos`).
- A correção diminui com a Roughness (acima de 0.5 vale só a direção), onde o desfoque esconde o erro. A luz difusa e o World capturado não mudam.
- `KX_TextureRendererManager::FindProbe` devolve centro e raio; `GPU_material_bind_probe` recebe os dois.

## 2026-10-02 - Sky Texture Hosek / Wilkie no Game PBR

- O modelo Hosek / Wilkie (padrão do nó) deixa de cair no Preetham no jogo. Os 9 coeficientes por canal e a
  radiância são calculados na CPU ao compilar o material, com os datasets do Cycles
  (`intern/cycles/util/util_sky_model_data.h`, só incluído, sem alteração) e uma cópia das funções Cook em
  `node_shader_tex_sky.c`; o GLSL `node_tex_sky_hosek` é o `sky_radiance_new` do Cycles.
- Teste: `tools/create_sky_hosek_test.py`. Validado: build e execução no RangeRuntime sem erro de shader;
  validação visual pendente.

## 2026-10-02 - Light Falloff e Ray Length no Game PBR

- Light Falloff deixa de devolver só Strength: usa a distância até a câmera como comprimento do raio, igual ao
  Cycles num raio de câmera (Smooth, Quadratic = Strength, Linear × distância, Constant × distância²).
- Light Path: Ray Length passa a ser a distância até a câmera (antes, 1 fixo).
- Teste: `tools/create_light_falloff_test.py`. Validado: build e execução no RangeRuntime sem erro de shader;
  validação visual pendente.

## 2026-10-02 - Direção do Auto World Sun (giro em Z)

- Nova World Property `sun_direction` (graus, padrão 0) e campo "Direction" no painel Sun. Ela gira o plano da
  órbita do sol automático em torno de Z, no ponto de chão à frente da câmera: muda o lado em que o sol nasce e
  se põe, e o meio-dia continua a pino. Antes, girar a lâmpada à mão era desfeito ao mudar a hora.
- Mesma conta no editor (`properties_scene.py`) e no runtime (`KX_Scene.cpp`); com 0 o resultado é idêntico ao anterior.
- Validado: build de `RangeEngine` e `RangeRuntime`. Validação visual pendente.

## 2026-10-02 - World em nós capturado num cubemap (Game PBR)

- Com Shading Nodes e World em nós, o jogo captura o fundo do World num cubemap 256 (half float, com mips) no
  primeiro quadro (`KX_TextureRendererManager::AddWorldProbe`, sem objeto de ponto de vista, só `RenderBackground`).
  Onde nenhum probe local alcança, Principled, Glossy e Glass refletem esse cubo em vez das cores Horizon/Zenith.
- `env_probe_mirror` agora troca também a luz difusa (5 amostras em torno da normal num mip baixo) pelo cubo
  ligado: o World capturado, ou o probe local dentro do raio (luz difusa local do probe, antes só reflexo).
- Limites: captura única (mudar o World pelo Python não atualiza o cubo); com Filmic a captura já sai com a curva
  e volta por sRGB→linear (aproximado, igual ao probe local); Glass transmitido segue a cor do World.
- Validado: build; `node_phases_test`, `probe_reflection_test` e `world_ibl_test` rodam sem erro de shader.
  `RangeEngine.exe` não foi religado (editor aberto). Validação visual pendente.

## 2026-10-02 - Nome visível: Anastacio Engine (fork of Range Engine)

- Título da janela do editor, propriedades do `.exe` (`winblender.rc`), About, mensagens e descrições das
  associações de arquivo no Windows, atalho `.desktop` do Linux e título reserva do runtime passam a usar
  "Anastacio Engine". No Linux o título inicial vira o WM_CLASS, por isso `StartupWMClass` foi atualizado junto.
- Mantidos por compatibilidade: `RangeEngine.exe`/`RangeRuntime.exe` (o RangeArmor procura `RangeRuntime`),
  pasta `%APPDATA%\RangeEngine\`, ProgIDs `RangeEngine.*`, `.range`, `import Range`, `bge`. Regra registrada
  no AGENTS.md. README ganhou parágrafo explicando o fork.
- Validado: build do editor e do runtime; `RangeEngine.exe` abre com o título "Anastacio Engine" e
  ProductName/CompanyName/FileDescription novos. Builds Web e Android não foram recompiladas.

## 2026-10-02 - Luz do World (textura) mais fiel no Game PBR

- Textura do World (equirect, angular, cube): o difuso passa a ser a média de 5 amostras em torno da normal num mip
  baixo (antes, uma cor única do último mip); o mip máximo do reflexo vem do tamanho da textura (antes, 9 fixo).
- Principled: reflexo do World multiplicado pela BRDF de ambiente split-sum (`env_brdf_approx`, Karis).
- World montado em nós ainda reflete as cores Horizon/Zenith; próximo passo: capturar o World num cubemap.
- Teste: `tools/create_world_ibl_test.py` (sem lâmpadas, luz só da imagem). Build e execução sem erro de shader;
  validação visual pendente.

## 2026-10-02 - Nó Wireframe no Game PBR

- Wireframe (`node_shader_wireframe.c`, GLSL `node_wireframe`): ganhou código GPU, com selo `~Game`. As arestas
  ficam a até Size / 2 da borda do triângulo, em unidades do mundo ou em pixels (Pixel Size), com ~1 pixel de suavização.
- Baricêntricas: builtin novo `GPU_BARYCENTRIC` (bit 31, `varbarycentric`), calculado no vertex shader por
  `gl_VertexID % 3`.
- Conversor (`BL_BlenderDataConversion.cpp`, `BL_ModifierDeformer.cpp`): `BL_MaterialUsesWireframe` procura o nó
  no material (inclusive em grupos); nas malhas desse material cada triângulo ganha 3 vértices próprios, sem
  compartilhar.
- Limites: não funciona na viewport do editor; quads mostram a diagonal; mais memória por malha; batching e texto
  bitmap com esse material podem quebrar o padrão.
- `tools/create_node_phases_test.py`: 6ª esfera na terceira fileira (Wireframe 0.03, arestas amarelas). Validado
  pelo usuário.

## 2026-10-02 - Holdout, Translucent, Velvet e Subsurface Scattering no Game PBR

- Holdout (`node_shader_holdout.c`, GLSL `node_holdout`): ganhou código GPU, sai preto com alpha 0. Saiu da lista de
  nós sem suporte (`node.c`, `node_draw.c`).
- Translucent, Velvet e Subsurface Scattering passam a usar as luzes da cena (`scene_light_dir`) e a cor do World como
  ambiente, com selo `~Game` e tooltip próprio:
  - Translucent: Lambert em -N, sem shadow map (o mapa dava listras de acne no lado de trás);
  - Velvet: brilho de borda `pow(1-NdotV, mix(6,1.5,Sigma))` somado a meio Lambert;
  - Subsurface: wrap lighting por canal (Radius × Scale, Sharpness reduz); a sombra some perto do terminador
    para não cortar a faixa avermelhada.
- Bevel e Wireframe ficaram como estavam: Bevel não tem derivadas úteis em malha flat; Wireframe precisa de
  baricêntricas (geometry shader só no caminho OpenSubdiv e o enum `GPUBuiltin` não tem bit livre).
- `tools/create_node_phases_test.py`: terceira fileira com Translucent, Subsurface, Velvet, Holdout e um Diffuse
  de referência. Validado visualmente pelo usuário.

## 2026-10-02 - Sidebars N e T flutuantes, aba Operator e nomes de states nos tooltips

- Sidebars N e T da 3D View com *Region Overlap* ligado viram painéis flutuantes:
  - o fundo só cobre os painéis abertos e as abas, com cantos arredondados; a região continua com a altura
    toda, então a rolagem, o arrastar de painéis e o redimensionar seguem iguais;
  - `ED_region_contains_xy` (`area.c`) faz o teste de clique: abaixo do conteúdo o evento vai para a 3D View.
    É usado em `wm_event_system.c` e em `ED_screen_set_subwinactive`;
  - a altura vem de `UI_panels_content_ymin` e `UI_panel_category_tabs_ymin` (`interface_panel.c`);
  - a borda (emboss) da região não é desenhada nesse modo.
- Painel do último operador (o mesmo do F6): a região `TOOL_PROPS` da 3D View fica sempre fechada e sem azone.
  O painel foi registrado na sidebar N, na aba "Operator", com poll em `WM_operator_last_redo`. A aba aparece
  depois de uma operação com opções e some quando não há nenhuma. O listener da sidebar redesenha em
  `ND_HISTORY`.
- States do Logic Editor: o tooltip da grade do State actuator e o do menu de máscara do controller mostram
  "State N: nome", com o nome vindo do objeto dono do controller.

## 2026-10-02 - Nós Tangent e Anisotropic BSDF no Game PBR

- Tangent (`node_shader_tangent.c`, GLSL `node_tangent`/`node_tangentmap`): ganhou código GPU. Radial no eixo X/Y/Z
  a partir das coordenadas Generated (`CD_ORCO`) ou tangente do UV Map (`CD_TANGENT`), ortogonalizada contra a
  normal e em espaço de mundo, como no Cycles. Saiu da lista de nós sem suporte (`node.c`, selo em `node_draw.c`).
- Anisotropic BSDF deixou de virar Diffuse: GGX anisotrópico (`GTR2_aniso`) das luzes da cena, com a divisão de
  roughness e a rotação do Cycles; sem Tangent ligado usa a tangente radial em Z. Reflexo do World isotrópico, como
  o Glossy. Selo `~Game` atualizado; o tooltip do Ambient Occlusion foi corrigido (dizia "AO sempre 1").
- Wireframe continua sem suporte: precisa de coordenadas baricêntricas, que o fragment shader não tem.
- `tools/create_node_sweep_test.py` no `RangeRuntime`: sem erro de shader, Tangent fora dos avisos.
- `tools/create_node_phases_test.py`: cena das Fases 3 (luzes), 4 (Glass, Refraction, AO, Blackbody, Wavelength,
  espelho do Sky) e 5 (Filmic), mais o Anisotropic. Validada visualmente pelo usuário, inclusive com o céu Atmospheric.

## 2026-10-02 - Lens Flare aparecia do lado oposto ao sol

- `KX_RenderPipeline.cpp` projetava na tela o `-Z` do sol, que é a direção para onde a luz vai, e não para onde o
  sol está. O céu desenha o disco do sol no `+Z` (`KX_WorldInfo` copia esse eixo para `world_sun->obmat[2]`), então o
  flare aparecia olhando para o lado contrário. Agora usa o `+Z`. A mesma posição alimenta o Light Scattering, que
  também passa a seguir o sol.
- Céu Atmospheric: com o sol bem abaixo do horizonte (perto de 0h), `chapman_depth` estourava a precisão de float
  (`exp(X - x0)` enorme) e desenhava anéis em volta do ponto oposto ao sol. Quando o raio até o sol atravessa o
  planeta, a função agora devolve sombra total sem avaliar a fórmula. Validado pelo usuário no P e no standalone.

## 2026-10-02 - Céu Atmospheric: revisão do shader, parâmetros próprios e painéis Sky/Environment/Fog novos

- `sky_atmosphere` (`gpu_shader_material.glsl`):
  - os raios primário e secundário agora avançam (antes todas as amostras caíam no mesmo ponto, com a
    densidade do ar do chão no raio inteiro; era daí que vinha o laranja forte);
  - o raio começa na câmera e para no chão;
  - a fase usa o ângulo real com o sol;
  - o tamanho do sol não multiplica mais o espalhamento.
- `rsi` calcula a interseção a partir do ponto mais próximo do centro. A forma `dot(r0,r0) - R²` perdia
  precisão de float na escala do planeta e gerava chuvisco no horizonte.
- `do_sky_atmospheric`: o disco do sol não divide por zero e o alpha é 1. As estrelas usavam `coord.x - starPos`
  e agora usam `coord - starPos`. No reflexo, o termo difuso usava rough 1.318 e passou para 1.831, igual ao
  `env_sky`.
- Parâmetros novos no DNA do World, `atmo_*`, com defaults em `BKE_world_atmosphere_defaults`. Arquivos antigos
  recebem os defaults em `versioning_range.c` (ar da Terra); o visual deles muda porque o laranja vinha do bug.
  Em RNA são `atmosphere_intensity`, `_altitude`, `_rayleigh_color`, `_rayleigh_density`, `_mie_density` e
  `_mie_direction`.
  - O brilho do céu não depende mais da energia da lâmpada Sun.
  - A cor do Rayleigh não vem mais do `horizon_color`, que fica só como cor da neblina.
- O céu só aplica o próprio tonemap `1 - exp` quando o Filmic não vem depois (Shading Nodes + Filmic).
  `gpu_world_atmosphere_links` (`gpu_material.c`) monta os dois vec4 para as três chamadas.
- `World.sky_type` (Flat / Gradient / Procedural / Atmospheric) é um enum sobre os bits Blend/Real/Paper/Atmospheric.
- Painéis do World no `flowmenu/custom_pt_world.py`:
  - **Sky**: tipo de céu, opções do tipo, Sol e Noite. O botão Earth (`world.atmosphere_reset`) volta os valores
    para a atmosfera da Terra.
  - **Environment**: ambiente, luz de ambiente e exposição.
  - **Fog**: no Atmospheric, mostra as cores da neblina.
  - Traduções PT-BR/ES/RU em `translations_ui.py`.
- Testado em cena de teste no `RangeRuntime` com o sol a 4° e a 30°: céu azul de dia, horizonte quente no pôr do
  sol, sem chuvisco. Falta a validação no jogo real.
- Desempenho: o raio secundário (8 passos com 2 `exp` cada, dentro dos 16 passos do primário) foi trocado pela
  profundidade óptica analítica `chapman_depth` (aproximação de Chapman de Schüler). Isso dá cerca de 8× menos
  trabalho por pixel, e o material faz 3 chamadas por fragmento. A aproximação é exata para cima e no horizonte.
  Diferente da versão anterior, o planeta faz sombra quando o sol está abaixo do horizonte. Com o sol a 4° a imagem
  ficou igual à anterior. Uma LUT por quadro ficou de fora porque exigiria render-to-texture no pipeline do World.

## 2026-10-02 - Nós de material: varredura, crash do Particle Info e aviso de nó sem suporte

- `tools/create_node_sweep_test.py`: cena com um material por tipo de nó de shader (90), Sun/Point/Spot com
  sombra, World com Sky, Filmic e reflection probe; `--autoquit` fecha após 90 quadros, `--span=lo:hi` bisecciona.
  Rodada no `RangeRuntime`: sem crash nem erro de shader em `%TEMP%
ange_runtime.log.txt`.
- Particle Info derrubava o jogo: o jogo passa `pi = NULL` a `GPU_material_bind_uniforms` (`gpu_material.c`),
  que lia `pi->scalprops`. Sem partícula, os uniforms recebem zero.
- `BKE_node_shader_unsupported_in_game` / `BKE_node_tree_shader_unsupported_in_game` (`node.c`): regra única de
  "nó sem suporte no jogo", usada pelo selo do editor e por um `CM_Warning` por material na conversão
  (`BL_BlenderShader`; uma vez por material, inclui node groups, ignora nós mutados). Aproximados (`~Game`) não
  avisam. Custo só na carga.
- Console do jogo: caixas Errors/Warnings/Messages/Debug para filtrar por nível.
- Crash no player Windows mostra uma caixa com o caminho do log (`RANGE_NO_CRASH_DIALOG` desliga, para testes
  automáticos).
- Visto e não tratado: `RangeEngine -b` dá segfault ao sair depois de salvar (o arquivo sai certo).

## 2026-10-01 - Porte YoFrankie 2.49: texto bitmap por réplica e Action actuator com ação linkada

- Texto bitmap 2.4x fica no `KX_Mesh`, que as réplicas compartilham: placas do seletor de fases mostravam o mesmo
  texto (ou nenhum). `KX_GameObject::DuplicateBitmapTextMeshes` dá a cada réplica uma cópia própria da malha
  (`KX_Mesh::Duplicate`: cópia, `EndConversion` e registro no conversor). O construtor de cópia do `KX_Mesh`
  remapeia as faces de texto para os display arrays da cópia. `KX_Mesh` em Python (`copy`) usa o mesmo caminho.
- Action actuator: o nome guardado é a chave de busca (`nome [lib]` para ação linkada), mas a ação tocando devolve
  só o nome. As comparações (ação sobrescrita, evento negativo e `DecLink`) falhavam e a animação de andar não
  voltava para idle. `BL_ActionActuator::IsOwnAction` compara o `BL_ActionData` resolvido
  (`KX_GameObject::GetCurrentActionData`).

## 2026-10-01 - Game PBR: reflection probe local

- Objeto com a propriedade de jogo `probe` (valor = raio de influência; ≤ 0 vira 10) vira um reflection probe:
  `KX_LightProbe` (derivado do `KX_CubeMap`) captura um cubemap da posição do objeto, com textura própria
  (`GPU_texture_create_cube`, half float no desktop, RGBA8 no Web) e mipmaps.
- Propriedades opcionais: `probe_size` (pixels por face, padrão 256, 16 a 2048), `probe_clip_end` (padrão 100)
  e `probe_realtime` (captura todo frame; sem ela, captura uma vez no início).
- Por objeto, `BL_BlenderShader::Update` escolhe o probe mais próximo cujo raio contém a origem do objeto
  (`KX_TextureRendererManager::FindProbe`) e liga `unfprobecube`/`unfprobeinfo` (`GPU_material_bind_probe`).
  Sem probe, vale o reflexo do World. Sem mistura entre probes.
- Shader: `env_probe_mirror` troca o reflexo do World (`GPU_material_world_env`) pelo cubemap do probe, com
  mip pela Roughness. Vale para Principled, Glossy e Glass (Refraction usa só a luz transmitida). A luz difusa continua vindo do World.
- Durante qualquer captura os materiais ignoram probes (sem realimentação do cubemap nele mesmo).
- A captura guarda cores de tela; com Color Management o shader volta para linear com a curva sRGB
  (aproximado sob Filmic).
- Correção no mesmo dia: a Roughness sem link chega como uniform, e link de uniform é liberado no primeiro
  uso; usada pelo World e pelo probe, virava use-after-free (heap corrompido, runtime fechava ~10 s depois em
  toda cena Game PBR). `GPU_material_world_env` agora converte com `set_value` antes de reutilizar.
- Validado pelo usuário em `probe_reflection_test.range` (sala de paredes coloridas com duas esferas metálicas dentro do raio e
  uma fora, que reflete só o céu).

## 2026-10-01 - Game PBR: sombra de luz Point (atlas de cubo)

- Com Shading Nodes e `Cast Shadow` ligado, a Point ganha shadow map: as 6 faces do cubo (90°, clip start/end
  da lâmpada, `bufsize` por face) ficam num único depth 3x2 (`gpu_lamp_create_point_shadow_buffer`). Um sampler
  por luz, então cabe nos 3 slots de sombra do loop de luzes.
- `KX_ShadowRenderer` faz 6 passes por Point (`RAS_OpenGLLight::BindPointShadowFace` →
  `GPU_lamp_shadow_point_face_bind`, viewport e scissor no tile da face).
- Shader: `unfshadowenabled = 2` marca Point; `unfshadowpersmat` vira view → espaço da luz e `shadow_point`
  (`gpu_shader_material.glsl`) escolhe a face pelo eixo dominante. Bias: offset na normal de ~1,5 texel mais
  Bias/Slope Bias da lâmpada. Sem VSM, CSM ou cache estático para Point.
- Fora: viewport do editor e materiais BI (Point segue sem sombra lá).
- Custo: 6 renders de casters por Point com sombra por frame.
- Validado pelo usuário em `point_shadow_test.range` (sala com Point no centro).

## 2026-10-01 - Game PBR: sombra segue o "Cast Shadow" do Cycles

- Com Shading Nodes, Sun e Spot criam shadow map conforme `lamp.cycles.cast_shadow` (padrão ligado), lido do
  IDProperty em `gpu_lamp_wants_shadow` (`gpu_material.c`). Sem Shading Nodes, continua Ray/Buffer Shadow do BI.
- Point continua sem sombra no Game.
- Validado pelo usuário em `node_material_shadow_test.range` (Sun em No Shadow, com SSAO e SSR por Filter 2D).

## 2026-10-01 - Game PBR: sombra em materiais sem nós

- Com Shading Nodes, material sem nós usava `node_bsdf_diffuse` (ambiente fixo 0,2, luzes sem sombra): chão e
  objetos simples nunca recebiam sombra. `GPU_material_from_blender` agora liga `node_bsdf_diffuse_ambient`, o
  mesmo do nó Diffuse BSDF (luzes da cena com shadow map, cor do World como ambiente).
- Lembrete (superado pela entrada acima): a sombra do Sun exigia `Ray Shadow` na lâmpada.
- Validado pelo usuário em `node_material_shadow_test.range`.

## 2026-10-01 - Game PBR: Color Management (Filmic, exposição, gamma) na saída do material

- Com Scene > Game > Shading Nodes, a saída dos materiais de mesh e do World passa por
  `game_view_transform` (`gpu_shader_material.glsl`) em vez do `linearrgb_to_srgb` puro: aplica
  `scene->view_settings` (exposure como 2^exposure, gamma no espaço do display, view transform Filmic com o
  contraste do look). Ligação em `gpu_material_link_display_transform` (`gpu_material.c`).
- Filmic aproximado: log2 de -10 a +6,5 stops em torno de 0,18 e curva S que leva o cinza médio a ~0,5;
  looks `Filmic - * Contrast` mudam a inclinação. Standard com exposure 0 e gamma 1 é idêntico ao anterior.
- Sem custo de pós-processo: é feito no shader do material (não em 2D filter). Valores lidos ao compilar o
  shader (mudar em runtime não atualiza). Caminho BI legado e Display Device None ficam como antes.
- Build: compilação OK; link bloqueado porque RangeRuntime/RangeEngine estavam abertos. Falta rodar o runtime
  e validação visual contra o Cycles.

## 2026-10-01 - Nós de material no Game PBR: Blackbody, Wavelength, Sky Texture e AO

- Blackbody e Wavelength ganham GLSL portado do Cycles (`svm_math_blackbody_color` e tabela CIE + XYZ→Rec.709
  com escala 1/2,52) em `gpu_shader_material.glsl`; saem do alerta `Cycles` no editor.
- Sky Texture deixa de ser branca: modelo Preetham com coeficientes calculados na CPU
  (`node_shader_tex_sky.c`, porte de `sky_texture_precompute_old`) e passados como uniforms; sem Vector, usa a
  direção do raio no World. Hosek / Wilkie usa Preetham e mantém o selo `~Game`.
- Ambient Occlusion: aproximação por concavidade local (derivadas de tela da normal/posição), escurece cantos
  dentro de Distance; não oclui por outros objetos.
- Shaders compilados sem erro no RangeRuntime (Blackbody, Wavelength e Sky em materiais e World); falta
  validação visual.

## 2026-10-01 - Porte YoFrankie 2.49: IPO "Child" e material compartilhado sem TexFace

- Opção "Child" do IPO actuator 2.4x (`ACT_IPOCHILD`, RNA `use_children`): o action actuator também toca a
  action própria de cada filho com o mesmo intervalo e camada, e para os filhos junto (`BL_ActionActuator.cpp`).
  Animações de névoa/ondas do `fx_splash` voltam a rodar.
- Material de arquivo 2.4x usado por malha com e sem TexFace: a malha sem TexFace fica com o material original
  (com backface culling, sem herdar invisível/alpha das faces de outras malhas) (`material.c`). Olhos do logo
  do menu reaparecem.

## 2026-10-01 - Porte YoFrankie 2.49: texto bitmap, alpha Darken, armaduras

- Texto bitmap 2.4x (TexFace `TF_BMFONT` + propriedade `Text`): a conversão reserva 256 cópias da face por
  caractere (`BL_BlenderDataConversion.cpp`) e `KX_Mesh::UpdateBitmapText` refaz posição/UV a cada mudança de
  texto, com o layout do `GPU_render_text` do 2.79 e a tabela de glifos de `bmfont.c`. Malhas com texto bitmap
  não usam o cache de malhas (cada objeto tem a sua).
- Alpha 2.4x com textura em Darken (`min(tex, alpha)`) virava opaco no GLSL novo: `do_versions_after_linking`
  troca para Mix com alpha 0 em arquivos < 2.50 (`readfile.c`). Cópia de material com node tree corrigida
  (`material.c`).
- Action actuator LOOPSTOP sobreposto por outra action volta a tocar quando ela termina, como no 2.4x
  (idle do Frankie travava após virar) (`BL_ActionActuator.cpp`).
- Parent tipo Armature de arquivo 2.4x com armadura linkada: o modificador criado vinha com deformação desligada
  (flags da armadura ainda não lidas); agora mantém o padrão (`versioning_250.c`).
- Armadura com malha deformada sempre atualiza a pose, mesmo com a malha fora da câmera: a caixa de culling segue
  a última pose, e uma action que traz a malha de fora da tela nunca aparecia (`KX_Scene.cpp`).
- Validado só na RangeRuntime (intro do start_menu, texto das teclas, animação de virar).

## 2026-10-01 - VR no celular: correção de aberração cromática na lente

- `gpu_shader_frame_buffer_frag.glsl` (`LENS_DISTORT`): `lens_color` amostra o canal vermelho com o raio distorcido
  ×(1−c) e o azul com ×(1+c), compensando as franjas coloridas da lente do Cardboard. Uniform `lensca`.
- `RAS_Rasterizer`: `m_vrChroma` (padrão 0,01), enviado só quando a distorção está ligada.
- Python: `bge.render.setVRChromaticAberration(c)` / `getVRChromaticAberration()` (0 a 0,1).
- RangeRuntime compilado; `vr_lens.range` rodou sem erro de shader. Falta validação visual no celular e build web.

## 2026-10-01 - VR no celular: conversão dos bricks VR para Python

- `logic_to_python.py` deixou de recusar Ray com eixo VR Gaze, VR Head, Mouse com Hold e Motion com VR Gaze/Teleport.
  Helpers gerados: `_gaze` (cone, tempo, Self, mira e destaque), `_vr_head`, `_hold`, `_vr_walk`/`_vr_offset` e
  `_vr_teleport`. Actuators que precisam rodar todo frame (frear depois de soltar, teleporte 1x por toque) saem
  fora do `if controller`, recebendo o estado do controller.
- Validado em background com `vr_menu`, `vr_gesture` e `vr_teleport`; o `vr_menu` convertido dá o mesmo clique
  da versão com bricks.

## 2026-10-01 - VR no celular: destaque do objeto olhado (Highlight)

- Ray com eixo VR Gaze ganhou a opção **Highlight** (bit 8 de `gaze_reticle`, `use_gaze_highlight`, sem mudança de
  DNA): o objeto olhado (ou o dono, com Self) cresce ×1,1 e volta à escala original ao sair; objeto apagado é
  esquecido via `RegisterSensor`/`UnlinkObject` (`KX_RaySensor.cpp`).
- `tools/create_vr_menu_scene.py` liga o Highlight nos botões do `vr_menu`.

## 2026-10-01 - VR no celular: teleporte no atuador Motion

- Motion (modo Simple) com VR Gaze ganhou a opção **Teleport** (`ACT_DLOC_VR_TELEPORT`, `use_vr_teleport`): cada
  toque faz um raio da câmera na direção do olhar (até Loc Y metros) e põe o corpo no ponto atingido, mantendo a
  altura atual acima do chão; um salto por toque (`KX_ObjectActuator.cpp`).
- Validado no celular com `vr_teleport.range`.

## 2026-10-01 - VR no celular: mira (linhas de debug) na Web/celular

- `RAS_OpenGLDebugDraw::Flush` na Web desenha as linhas via `GLctx` em `EM_JS` (`ras_draw_lines_webgl`), com
  VAO/buffer próprios e restauração dos bindings, contornando a emulação legada de GL do Emscripten.
- Validado no celular: o anel da mira do Ray VR Gaze aparece no `vr_menu`.

## 2026-10-01 - Porte do YoFrankie (Blender 2.49): correções de compatibilidade

- `logic.getBlendFileList` voltou a listar os `.blend` (`KX_PythonInit.cpp`).
- Sensor de joystick em modo Hat: aviso claro em vez de "bad case statement"; nunca dispara (`BL_ConvertSensors.cpp`).
- Action actuator em LOOPSTOP: retry pendente e `DecLink` só para a própria action (`BL_ActionActuator.*`).
- `mat_nr` fora do intervalo é limitado ao número de materiais (`BL_BlenderDataConversion.cpp`).
- Materiais TexFace 2.4x com flags mistas por face: `BKE_material_tface_split_disputed` divide o material em
  `<nome>.TF.<flags>` após o linking (`material.c`, `readfile.c`); acaba o aviso "material skipped".
- `versioning_upbge.c`: checagem de nulo na conversão de atrito (crash ao abrir arquivos antigos).
- Validado: as 14 fases do YoFrankie abrem 8 s sem crash e sem "skipped". Falta validação visual e de jogabilidade.
- Relatório completo: `PORTE_ANASTACIO.md` no repositório do jogo.

## 2026-10-01 - VR no celular: texto 3D na Web/celular

- Na Web, a emulação legada de GL do Emscripten bagunçava VAO/VBO ao desenhar glifos. O BLF ganhou um caminho
  próprio (`blf_web_begin/end` em `blf_glyph.c`): shader e quad desenhados direto via `GLctx` em `EM_JS`.
- `BLF_draw_state` e `RAS_OpenGLRasterizer::RenderText3D` passam viewproj e cor ao BLF.
- `tools/create_vr_menu_scene.py` volta a gerar os botões com texto por padrão.
- Validado no celular: o menu VR mostra as letras e os botões funcionam.

## 2026-10-01 - VR no celular: painel VR e botões 3D com "Self"

- Painel próprio `RENDER_PT_game_vr` ("VR") com "Prepare VR Scene" e os parâmetros VR; o Stereo ficou só com modo.
- Ray "VR Gaze": opção `use_gaze_self` (bit 4 de `bRaySensor.gaze_reticle`, sem mudar o DNA). Em objeto que não é
  câmera, o raio sai da câmera ativa e só fica positivo ao acertar o dono ou um filho (`KX_RaySensor::IsSelf`);
  o cone também filtra pelo dono. Botão de logic editor ao lado de "Reticle".
- `tools/create_vr_menu_scene.py` → `vr_menu.range`: menu de 3 botões só com bricks. Validado no runtime nativo
  (só o botão olhado conta, após 1 s). Validado depois no celular.

## 2026-10-01 - Nós de material: Glass, Refraction, reflexo do Glossy e Toon Glossy (Fase 4, parte 1)

- `node_shader_gpu_world_env()` (`node_shader_util.c`) monta os links de reflexo/difuso da textura do World; o
  Principled passou a usá-lo e Glossy, Glass e Refraction também.
- Glossy reflete a textura do World desfocada pela Roughness (sem textura, a cor do World).
- Glass: `fresnel_dielectric_cos` (IOR invertido na face de trás) mistura reflexo + brilho GGX das luzes com o
  World desfocado como luz transmitida. Refraction: só a parte transmitida. Não há refração real da cena.
- Toon: Component Glossy mede a faixa em torno do reflexo da visão e usa o especular da luz (uniform `glossy`).
- Selos e `docs/node-material-support.md` atualizados.
- Validado: build ok; `node_material_test.range` e cenas de teste com e sem textura no World rodam sem
  `GPUShader: compile error` em `%TEMP%
ange_runtime.log.txt` (checagem conferida antes com um erro proposital).
  Falta validação visual.

## 2026-10-01 - VR no celular: painéis curvos no menu de exemplo

- `tools/create_vr_menu_scene.py --curved`: botões em arco de 3 m (malha de cilindro com normais para o olho,
  8 segmentos, 24° cada), texto girado para o centro. Botões continuam com Ray VR Gaze Self.
- Validado no celular (APK Cardboard): curvatura, textos e cliques pelo olhar.

## 2026-10-01 - VR no celular: conforto e preset Cardboard

- `GameData.vr_vignette` (0-100%) e `vr_recenter_time` (ms) no lugar do padding `dynamicResolutionPad2`; RNA e
  painel Stereo. "Prepare VR Scene" agora liga lente 30%, suavização 40 ms, vinheta 50% e recentralizar 2 s.
- Vinheta: `KX_Camera::UpdateVRComfort` mede giro/velocidade do corpo e suaviza; `RAS_Rasterizer::SetVRVignette`
  passa o uniform `vignette` ao shader da lente (usado também com lente 0).
- Recentralizar: `KX_PythonMotion` zera o yaw após olhar >60° para baixo por `recenterTime`; Python `recenterTime`.
- Snap-turn fica com bricks (VR Head/toque → Motion Rot Z em pulso).
- `package-web.py --cardboard` (sem overlay, botão VR visível) e `android.py` força paisagem nesse pacote.
- Validado: builds nativo e Web ok; APK Cardboard instalado e aberto no celular.

## 2026-10-01 - Nós de material: Diffuse, Glossy e Toon no loop de luzes do Principled (Fase 3)

- `gpu_shader_material.glsl`: `scene_light_dir()` (direção, atenuação, cone de Spot) e `scene_light_visibility()`
  (sombra das 3 primeiras luzes) saíram do Principled e agora servem também a `node_bsdf_diffuse_ambient`,
  `node_bsdf_glossy` e `node_bsdf_toon`. Antes, Diffuse e Glossy tratavam toda luz como Sun e não tinham sombra.
- Glossy: brilho GGX + Smith (mesma base do especular do Principled, fresnel branco) no lugar do Blinn misturado
  com difuso. Toon: faixas do Toon difuso do Cycles (`size`, `smooth`) e World como ambiente; Component Glossy
  ignorado. `node_bsdf_diffuse` (fallback de Glass etc.) segue sem posição do fragmento.
- Nós C passam `GPU_VIEW_POSITION`. Selos do Glossy e do Toon com textos novos.
- Validado: build ok e `node_material_test.range` (e cópia com Toon) rodam no player sem erro de GLSL.
  Falta validação visual.

## 2026-10-01 - VR no celular: botão "Prepare VR Scene"

- Operador `render.game_vr_setup` (`properties_game.py`, painel Stereo): Stereo + Side-by-Side + separação 0,064 +
  head tracking + lente num clique. Testado em `-b` no editor.

## 2026-10-01 - VR no celular: sensor VR Head (gestos de cabeça)

Novo sensor `SENS_VR_HEAD` (`bVRHeadSensor`: `mode`, `angle`, `time`; RNA `VRHeadSensor`; `KX_VRHeadSensor`). Lê a orientação de render da câmera ativa: Look Up/Down e Tilt Left/Right ficam positivos enquanto passam do ângulo; Nod (pitch) e Shake (yaw) detectam ida e volta de pelo menos o ângulo dentro de `time` e dão pulso de um tic. Python: `mode`, `angle`, `time` e só leitura `pitch`, `yaw`, `roll`. Conversão para Python recusa o sensor. Validado no celular (`vr_gesture.range`: balançar "não" inverte a tela, olhar para cima desliga, acenar "sim" pula). DNA cresceu: rebuild limpo se aparecer crash estranho.

## 2026-10-01 - VR no celular: cone e mira no Ray VR Gaze

`bRaySensor` ganhou `gaze_angle` (rad, RNA `gaze_angle` 0–45°, Python `gazeAngle`) e `gaze_reticle` (RNA `use_gaze_reticle`). Com cone > 0, se o raio central erra, `KX_RaySensor` escolhe o objeto visível (filtros de propriedade/material e máscara) de menor ângulo dentro do cone e confirma linha de visada com outro raio até a origem dele; o alvo atual tem histerese de 1,5× o ângulo. A mira desenha anéis com linhas de debug no ponto olhado (2 m sem alvo), anel interno = progresso do Gaze Time, verde ao disparar. Com Debug ligado, desenha o contorno do cone. Validado no celular (`vr_trigger.range`, cone 5°, 300 ms). DNA cresceu: rebuild limpo se aparecer crash estranho.

## 2026-10-01 - VR no celular: Hold (toque longo) no sensor Mouse

`bMouseSensor.pad1` virou `hold` (ms; RNA `hold`, painel só nos eventos de botão; Python `holdTime` em segundos). `SCA_MouseSensor` acumula o tempo pressionado (período do tic rate passado pelo conversor) e só fica positivo ao atingir o Hold. Só o Mouse simples (não o Mouse Over). Conversão para Python recusa Hold > 0. Validado no celular (`vr_trigger.range`: segurar 0,8 s pula).

## 2026-10-01 - Nós de material: selos de aproximação no Game (Fase 2)

`node_engine_badge` (`node_draw.c`): no Game com PBR Shading Nodes, nós com GLSL aproximado ganham o selo `~Game` e um tooltip com o que o jogo faz (Glossy sem reflexo; Glass, Toon etc. viram Diffuse; AO = 1; Sky branco...). Nós sem GLSL (Blackbody, Wavelength, Wireframe, volumes...) ficam com alerta. Matriz completa em `docs/node-material-support.md`; fases seguintes no roadmap. `node_draw.c` compila; o build do `RangeEngine` estava quebrado por trabalho de VR em andamento (`rna_sensor.c`, `KX_VRHeadSensor`), então falta ver os selos no editor.

## 2026-10-01 - Nós de material: selo de motor e correções GLSL (Fase 1)

Editor de nós (`node_draw.c`, `node_engine_badge`): selo "Game", "BI" ou "Cycles" no cabeçalho dos nós de um só caminho; nó incompatível com o motor ativo fica com cabeçalho avermelhado e ícone de alerta. Sprites Animation ganhou `node_type_compatibility` (antes sumia do menu). GLSL (`gpu_shader_material.glsl`): Glossy limita a roughness (roughness 0 dava NaN/preto); Diffuse e Glossy usam a cor do World (horizon, via `GPU_material_world_color`) como ambiente no lugar do `0.2` fixo e repassam `color.a`; Transparent BSDF liga o alpha blend do material. Os BSDFs que caem no Diffuse (Glass, Toon etc.) continuam com ambiente `0.2`. Validado no Game com `tools/create_node_material_test.py` (gera `node_material_test.range`; teclas 1-4 trocam a cor do World). Para a cor do World mudar em runtime o material precisa de `use_constant_world = False`. Glossy no Game ainda sem reflexo (Fase 4).

## 2026-10-01 - VR no celular: atuador Motion com "VR Gaze" (andar para onde olha)

Nova flag `ACT_DLOC_VR_GAZE` (512, em `bObjectActuator.flag`, sem mudar o DNA) e RNA `use_vr_gaze`: nos modos Simple e Character o Loc é aplicado na base do olhar da câmera ativa no plano horizontal (`vr_gaze_offset` em `KX_ObjectActuator.cpp`). Arquivos: `DNA_actuator_types.h`, `rna_actuator.c`, `logic_window.c`, `BL_ConvertActuators.cpp`, `KX_ObjectActuator.*`, `logic_to_python.py` (recusa a opção). Com VR Gaze, o `damping` do Motion Simple vira rampa de aceleração e frenagem (`m_vr_gaze_factor`, `m_vr_gaze_braking`); na UI o Damping fica ao lado da opção. Editor, runtime nativo e Web compilam; andar validado no celular (`vr_move.range`), aceleração ainda não.

## 2026-10-01 - VR no celular: sensor Ray com eixo "VR Gaze"

O sensor Ray ganhou o eixo `SENS_RAY_GAZE` (raio na direção da cabeça da câmera) e o campo `gaze_time` (ms, no antigo `pad1` de `bRaySensor`, sem mudar o tamanho do DNA). Só dispara depois de olhar o mesmo objeto pelo tempo definido. Python: `gazeTime`, `gazeProgress`. Arquivos: `DNA_sensor_types.h`, `rna_sensor.c`, `logic_window.c`, `BL_ConvertSensors.cpp`, `KX_RaySensor.*`. Compilam o editor, o runtime nativo e o Web; falta validar no celular. Pendência futura: atualizar a conversão de logic bricks para componente Python (`logic_to_python.py`) para o novo eixo/campo.

## 2026-10-01 - VR no celular: lente e suavização no painel Stereo

- `GameData.vr_lens_strength` (%) e `vr_head_smoothing` (ms) nos shorts de padding (tamanho do DNA igual; 0 = padrão 30%/40 ms, sem versionamento). RNA, painel Render → Stereo e leitura em `LA_Launcher`. Python continua sobrescrevendo em runtime.
- Runtime nativo, editor e Web compilam; falta validar no celular.

## 2026-10-01 - VR no celular, peça 4: separação 0,064, gaze, setStereoMode e sombras na view da cabeça

- Com `VR Head Tracking` ou `VR Lens Distortion` ligados e a separação ainda no padrão 0,10, o launcher usa 0,064 m.
- `KX_Camera.gazeDirection`: vetor unitário (mundo) para onde a view da cabeça aponta, para raycast de olhar.
- `bge.render.setStereoMode/getStereoMode` e constantes `STEREO_NOSTEREO/SIDEBYSIDE/ABOVEBELOW/ANAGLYPH/INTERLACED`.
- `KX_ShadowRenderer`: as cascatas usam `GetCameraToWorld()` (view com a cabeça) em vez da transformação do objeto.
- Validado no celular: sombra simples da Sun aparece no APK (exige GLSL Shadows ligado na cena). CSM ainda não testada no Web.

## 2026-10-01 - VR no celular, peça 3: distorção de lente e botão "Entrar em VR"

- Novo flag de cena `GAME_VR_LENS_DISTORTION` (RNA `vr_lens_distortion`, painel Stereo).
- `GPU_SHADER_VR_LENS`: variante `LENS_DISTORT` do shader de frame buffer; pré-distorção em barril por olho,
  aplicada em `RAS_Rasterizer::DrawOffScreen` na apresentação final do Side-by-Side (`KX_RenderPipeline` define k = 0,3).
- `package-web.py`: botão "Entrar em VR" (inicia o jogo, tela cheia e wake lock), visível com `?vr=1` ou ponteiro coarse.

## 2026-10-01 - VR no celular, peça 2: opção "VR Head Tracking"

- Novo flag de cena `GAME_VR_HEAD_TRACKING` (RNA `vr_head_tracking`, painel Stereo > "VR Head Tracking").
- `KX_Camera::UpdateHeadTracking()` (chamado em `UpdateGameFX`) lê `KX_PythonMotion::GetHeadView()` e
  `GetRenderOrientation()` aplica `ori * Rx(-90°) * cabeça` só na view: o objeto câmera (corpo/yaw) segue o jogo.
- Primeira leitura válida vira o "frente" (auto-recenter), a menos que um script já tenha chamado `recenter()`.
- Validado no celular (APK); frame ~16 ms com logic 0,2 ms e render principal 0,5 ms.

## 2026-10-01 - VR no celular: pose da cabeça por fusão giroscópio + gravidade

- Testado no celular: o quaternion do Android/Chrome (`deviceorientation` e `AbsoluteOrientationSensor`, em
  frame `device` e `screen`) tem descontinuidade perto de 90° de pitch (fusão baseada em Euler); a vista pulava
  para o chão ao olhar para cima.
- `package-web.py`: filtro complementar próprio (`fuseHead`) nos eixos da tela: integra `rotationRate` e corrige
  com o vetor gravidade (ganho 2/s). Quaternion inicial = menor arco da gravidade até +z. Sem `rotationRate`,
  cai no caminho Euler antigo. Deriva de rumo é esperada; `recenter()` corrige.
- Validado num simulador em Node e no aparelho: orientação correta e sem salto passando do zênite.

## 2026-09-30 - VR no celular, peça 1: pose da cabeça em `bge.logic.motion`

- Plano novo em [mobile-vr-plan.md](mobile-vr-plan.md) (VR estilo Cardboard no Web/APK; OpenXR adiado sem headset).
- `package-web.py`: o `deviceorientation` agora gera também `Module.rangeMotion.quat`, a orientação da câmera
  no mundo (W3C `Rz(alpha)·Rx(beta)·Ry(gamma)` seguida de `Rz(-ângulo da tela)`; os eixos do aparelho já são os
  da câmera do Blender). Conferido no Node: retrato em pé para o norte olha para +y.
- `KX_PythonMotion`: buffer passa de 13 para 18 floats (`HEAD_VALID`, `HEAD_QUAT`); novos `headOrientation`
  (Matrix 3x3; identidade sem sensor) e `recenter()` (remove o rumo atual, a vista passa a olhar para +y).
- `stubs.c` do player: stubs de `uiLayoutBoxSetCustomColor` e `UI_icons_reload_internal`, que quebravam o link do
  `build-web-release` (o RNA passou a referenciá-las). `RangeRuntime` nativo e Web compilam; falta validar no celular.
- Resolução dinâmica sem timer de GPU (Web): antes ficava em 100% e ignorava a escala; agora usa a escala
  máxima como escala fixa (`KX_KetsjiEngine::UpdateDynamicResolution`). Achado no teste VR no celular, onde
  render, filtro 2D e overhead davam picos com a cena em tela dividida.
- Filtro 2D que lê a profundidade (`bgl_DepthTexture`) desenhava no próprio off screen dono dela: o desktop
  tolera, o WebGL recusa o draw ("Source and destination textures of the draw are the same") a cada frame.
  `RAS_2DFilterManager::RenderFilters` agora desvia para um off screen de filtro livre
  (`RAS_2DFilter::UsesDepthTexture`).
- Cenas de teste `vr_fps.range` (first person, anda com stick WASD para onde olha) e `vr_test.range` (cubos por
  direção) na raiz, instaladas no aparelho como APK; cabeça seguindo o celular já roda no aparelho.
- Picos de ~20 ms/frame no WebView Android: cada `glGet*` é uma ida síncrona à GPU (~1-1,7 ms). Removidos do
  caminho por frame: `ScreenPlane::Render` não lê mais os divisores (só zera 0..1), `web_glPushAttrib` (glew-es)
  consulta só os bits pedidos, `KX_Imgui::Render` pula frames sem vértices e o backend `imgui_impl_opengl3` no
  Emscripten restaura o estado conhecido do fim de frame em vez de consultá-lo. Cubo e `vr_fps` (com o overlay de
  profile) passam a 60 fps estáveis (intervalo p95 ~17,8 ms).

## 2026-09-30 - LOD: Bake Impostor gera o próprio quad

- `Bake Impostor Texture` não texturiza mais o objeto do nível LOD. Antes ele punha a textura no material[0] desse
  objeto (às vezes compartilhado com o original) e o atlas saía nas UVs e faces de uma malha qualquer (um cubo,
  por exemplo), virado para o lado errado. Agora o operador cria ou atualiza `<objeto>_impostor`: um quad com a face
  em +Y, UV 0..1 (direita da imagem = -X do mundo) e o tamanho do enquadramento ortográfico, com material próprio.
  O nível passa a apontar para ele; o objeto e o material anteriores ficam intactos.
- O enquadramento do bake é centrado no eixo vertical da origem do objeto, não no centro do bbox, e a largura
  é a do canto mais distante desse eixo. O billboard gira em torno da origem: com o quad no centro do bbox, uma
  malha fora de centro fazia o impostor sair deslocado para o lado nas outras vistas.
- `KX_GameObject::UpdateLod`: a célula do atlas é arredondada para a vista mais próxima, em vez de truncada.
  O truncamento chegava a mostrar a vista uma célula adiantada.
- O billboard cilíndrico agora aplica a orientação em espaço de mundo (`NodeSetGlobalOrientation`). Com um pai
  rotacionado (por exemplo, o empty raiz de um modelo importado), a orientação local virava o quad para o lado
  errado, e o impostor aparecia girado ou espelhado no jogo. Testado no RangeRuntime com o pai girado 180° em Z:
  o impostor e o modelo real ficam com a mesma inclinação.
- Generate LODs (`object.lod_generate`): troca `bpy.ops.object.duplicate()`, cujo poll falhava ("context is
  incorrect") fora da 3D View ou em Edit Mode, por cópia de objeto e malha via dados; sai do Edit Mode antes.
  Testado em background partindo do Edit Mode: gera `Cubelod1` e `Cubelod2`.
- `UpdateLod` chama `NodeUpdate()` depois de girar o billboard ou restaurar a orientação original. O LOD roda
  antes do render, depois da passada do scene graph, então a matriz de mundo ficava um frame atrasada: ao voltar
  para o modelo real, ele piscava um frame com a rotação do billboard.
- Bake sem atlas (uma imagem só): a foto agora é tirada da frente do próprio objeto (-Y local, a vista Front do
  Blender, respeitando a rotação), e não do +Y do mundo. Como a imagem única aparece de todos os lados, a foto
  antiga ficava correta só olhando de +Y para -Y e espelhada no sentido mais comum, olhando ao longo do +Y.
- Validado em background: nível apontando para um cubo com material compartilhado → quad com normal +Y, atlas 4x2,
  material do original sem slot novo. Falta conferir no jogo real.

## 2026-09-30 - Collision Bounds: Oriented Box novo; Box centrado na geometria, Capsule e Convex Hull corrigidos

- `CcdPhysicsEnvironment.cpp`: Box, Cylinder, Cone e Capsule usavam a extensão da bounding box, mas ficavam
  centrados na origem do objeto (`bounds_center` era calculado e ignorado). Agora, se a origem não está no centro
  da geometria, a forma vai dentro de um compound deslocado. O centro de massa continua na origem. Character fica de
  fora, porque precisa de forma convexa simples.
- Capsule: a altura passada ao Bullet agora exclui as calotas (`2*(ext_z - raio)`). Antes, a cápsula ficava `2*raio`
  mais alta que a malha.
- `CcdPhysicsController.cpp`: Convex Hull passa pelo `btConvexHullComputer` e guarda só os vértices do casco. A forma
  é a mesma, mas com menos pontos por consulta.
- Novo tipo **Oriented Box** (`OB_BOUND_ORIENTED_BOX = 9`, só malhas, não aparece para Character/Soft Body):
  `BKE_mesh_calc_obb` (`mesh.c`) acha a menor caixa rotacionada partindo dos eixos locais e dos eixos principais
  (PCA), com refino por pequenas rotações. Nunca sai maior que o Box. No jogo vira um `btBoxShape` rotacionado dentro
  de um compound. Usa os vértices da malha original (sem modificadores). Com escala não uniforme a caixa rotacionada
  não acompanha a escala exatamente.
- Viewport (`drawobject.c`): desenha o Oriented Box, e os bounds de jogo agora aparecem centrados na geometria, igual
  à física (Character continua desenhado na origem).
- Centro de massa: em corpos dinâmicos (Dynamic/Rigid Body) com forma primitiva deslocada, o centro de massa vai
  para o centro da forma, via `SetCenterOfMassOffset` (mesma compensação do `vehicle_com_offset`). Antes o corpo
  girava em volta da origem, que podia estar fora da malha. Não vale para Character, compound e veículo com offset.
- `PostProcessReplica`: cópias (Add Object) perdiam o offset do centro de massa (inclusive o do veículo). Agora o
  offset é lido do motion state original e reaplicado.
- Collider Object (`collision_bound`): Triangle Mesh e Convex Hull chamavam `UpdateMesh(gameobj, nullptr)` e usavam a
  malha do próprio objeto; só funcionava por acaso quando o objeto colisor também tinha física Triangle Mesh (a forma
  era compartilhada pelo `FindMesh`). Agora a malha do colisor é usada. Se o colisor não existe ou não tem malha, o
  objeto usa a própria malha e avisa no console (antes ficava sem física). O campo só vale para Triangle Mesh e
  Convex Hull, e aparece na UI para os dois.
- Muda a colisão de arquivos antigos que têm a origem fora do centro da malha.

## 2026-09-30 - World Weather: ripples viram normal (onda com refração)

- `RAS_Rain2DFilter.glsl` e `gpu_shader_fx_rain_frag.glsl`: o ripple deixou de somar brilho (`rainRipples3D`) e
  passou a ser uma altura (`rainRippleHeight`, seno amortecido em anel) cuja inclinação gera uma normal Z-up. Essa
  normal distorce o que está sob a água (refração) e dá especular e fresnel. Continua sem UV: usa o XY do mundo
  reconstruído da profundidade.
- Novo campo `World.rain_ripple_normal` (reusa `rain_weather_pad`; 0 em arquivo antigo = 1.0), RNA
  `weather_settings.rain_ripple_normal`, painel World > Ripples, uniform `ge_RainRippleNormal` / `rain_ripple_normal`,
  `setWeather("weather.ripple_normal", v)`. Intensidade e normal do ripple agora são relidas a cada frame.
- Protótipo em Python: `tools/ripple_normal_test.py`.

## 2026-09-30 - Cutscene: evento Camera Path; Motion Paths escondido na Game Engine

- Novo evento de cutscene `CAMERA_PATH` (`CUTSCENE_EVENT_CAMERA_PATH = 17`): move um objeto (normalmente a câmera)
  por uma curva com velocidade constante. Reusa slots do `CutsceneEvent`: `template_object` = objeto,
  `spawn_point` = curva, `dependent_object` = Look At opcional, `param_float` = duração, `param_bool` = seguir a
  direção, `param_int` = tornar câmera ativa. RNA: `path_object`, `path_curve`, `path_look_at`, `path_duration`,
  `path_follow`, `path_set_camera`.
- A conversão amostra a primeira spline (Bezier/Poly/NURBS) em espaço local da curva (`BL_SampleCutscenePath`);
  o runtime (`KX_Scene::UpdateCutscenePaths`) aplica a transformação atual da curva, orienta com -Z à frente e
  +Z do mundo como up, e libera `WAIT_CAMERA_END` quando o último caminho termina.
- Painéis Motion Paths (Object e Armature) escondidos quando a engine é `BLENDER_GAME`; Viewport Display e Motion
  Paths passaram a usar caixas com rótulo, no padrão dos outros painéis de Object.
- Compilou; `RangeRuntime` linkou. `RangeEngine` não relinkou porque o editor estava aberto. Sem teste no jogo.

## 2026-09-30 - Barra lateral N com abas e visual arredondado

- Painéis da barra N da 3D View ganharam categorias: `Item` (Transform, Vertex Weights, Properties) e `View`
  (View, 3D Cursor, Grease Pencil, Background Images, Quad View, etc.). `rna_ui.c` aplica a categoria `Misc`
  também a painéis Python da região UI da 3D View sem `bl_category`.
- Abas de categoria ficam na borda direita em regiões alinhadas à direita (T continua à esquerda); estilo
  plano com a aba ativa preenchida e arredondada, sem contorno em relevo nem sombra no texto.
- Painéis com cabeçalho e fundo de cantos arredondados e 4 px de espaço entre eles (vale para todo o editor).

## 2026-09-30 - Grade da 3D View no estilo Blender 5 e botões flutuantes

- `drawfloor` (vista de usuário/perspectiva) desenha o chão com shader GLSL (`drawfloor_shader` em
  `view3d_draw.c`): linhas suavizadas por `fwidth`, subdivisão por LOD com transição suave, linha de ênfase,
  fade por distância e ângulo rasante, eixos X/Y infinitos. Eixo Z e grade ortográfica seguem as linhas antigas;
  se o shader falhar, volta ao desenho antigo.
- Botões flutuantes da 3D View começam no retângulo visível da região (`ED_region_visible_rect`), então não
  ficam mais cobertos pelo painel T/N com region overlap (relato do Fumangy no Discord).

## 2026-09-30 - Estilo de ícones: Blender 5

- Terceira opção em `Interface > Icons`: ícones do Blender 5.0 (SVG rasterizado para o atlas, 484 de 492 por
  nome/apelido). Atlas em `release/datafiles/icons_blender5/`, gerado por
  `tools/blender5_icons/build_blender5_icon_atlas.py`.
- Correção: SVGs com canvas diferente de 1600×1600 saíam esticados (grandes). Agora rasteriza em escala fixa
  (1600 unidades = 16 px) e centraliza na célula, como o Blender.

## 2026-09-30 - Estilo de ícones: Range ou UPBGE

- `User Preferences > Interface > Icons` escolhe entre os ícones da Range (monocromáticos, tingidos pelo tema)
  e os ícones coloridos da UPBGE 0.2.5b. A troca recarrega o atlas na hora, sem reiniciar.
- `U.icon_style` usa um byte do antigo `pad2[9]` do `UserDef` (tamanho do struct inalterado; userprefs
  antigos abrem como Range).
- Atlas em `release/datafiles/icons_upbge/`, gerados por `tools/upbge_icons/build_upbge_icon_atlas.py`
  (remapeamento por nome da ordem 2.79 para a ordem da Range). Detalhes em `docs/icon-atlas-notes.md`.
- `Files > Icons` continua sobrepondo o estilo; agora também recarrega ao mudar.

## 2026-09-30 - Aura da chuva: estilo Animated

- World › Rain › Aura ganhou `rain_aura_style` (Static / Animated), no antigo `rain_lightning_pad`
  (arquivos antigos abrem como Static). Python: `world.setWeather("aura_style", 1)`.
- Animated (`KX_RainAura`): a gota nasce no contorno e voa 0,04–0,12 × escala em 0,25–0,55 s, com uma
  gravidade leve que curva o caminho, um fade-in rápido e um fade-out longo. Os spawns caem para 12% para
  manter a densidade parecida. Continua em 1 VBO e 1 draw.
- 3D View (`view3d_rain.c`): mesmo voo sem guardar estado. Cada slot repete um ciclo pelo relógio e sorteia
  de novo a cada ciclo.
- O protótipo Python original não estava versionado; os parâmetros foram refeitos a partir da descrição no roadmap.

## 2026-09-30 - Correções nos Logic Bricks

- `rna_sensor.c`: `rna_PropertySensor_evaluation_type_itemf` lia o `bSensor` como `bPropertySensor`; o
  `runtime_enabled` lido era lixo e o enum às vezes só oferecia Equal/Not Equal (Greater Than, Interval etc.
  falhavam pelo editor e por script). Era a causa do "exit 11" intermitente do teste do conversor (o `.range`
  não chegava a ser salvo).
- `SCA_PropertySensor`: Interval e Less/Greater Than usavam `float` não inicializado quando o valor não era
  número (campo vazio/texto); agora inicia em 0 e conversão falha dá resultado falso.
- `KX_NetworkMessageSensor`: destrutor não liberava as listas de body/subject (vazamento) e a réplica
  (Add Object) compartilhava os ponteiros das listas, com release duplo no próximo frame; réplica zera as listas.

## 2026-09-30 - Logic Bricks → Python Component (fase 2, parcial)

- Random sensor, Track To (Edit Object, alvo fixo) e Sound (Play End via `aud`) no conversor.
- Message sensor: nova função `Range.logic.getMessages(to, subject="")` (C++, `KX_PythonInit.cpp`) devolve a
  lista `(subject, body)` que um Message sensor do objeto `to` enxerga no frame. O conversor usa essa função e
  dispara o controller todo frame com mensagem, como o sensor. Teste ganhou `msgs` na linha CHECK.
- Conversor de bricks, campo Mode: além do Python Component, gera sensor Always + controller Python
  (modo Module `<modulo>.main` ou Script `<modulo>_run.py`), um controller `LC_state_<n>` por estado.
  Teste: `create_logic_convert_scene.py -- <saida> convert:MODULE|convert:SCRIPT`.
- Conversor de bricks: valores dos bricks viram args do componente (`"<brick> <campo>"`): teclas
  (`"KeyW Key": "W"`, aceita `SPACE`, `LEFTARROW`, `PAD1`), propriedades/valores, distâncias, ranges,
  delay, subjects, vetores do Motion, objeto/tempo do Add Object, volume/pitch etc. Cada sensor ganha
  `"<sensor> Enabled"` (liga/desliga) e o componente ganha `Debug`, que imprime mudanças de
  sensores/controllers. Nos modos Always + Python ficam os valores padrão do texto gerado.
  Os args saem agrupados com um `C_Header` por brick ("Sensor X", "Actuator Y"); sensor e
  actuator de mesmo nome e campo ganham args separados. Primeiro cabeçalho "Logic" (ícone `LOGIC`, com o
  `Debug`); ícone por tipo de sensor (Collision `MOD_PHYSICS`, Delay `TIME`, Message `FILE_TEXT` etc.) e
  `FILE_TEXT` também no actuator Message.
- Sensores/actuators soltos (sem controller) do objeto convertido também são desativados.
- Novos tradutores: sensor Movement (posição do frame anterior, como `KX_MovementSensor`), sensor Joystick
  (botões, direções do stick, eixo único e gatilhos via `logic.joysticks`), actuator Parent (set/remove),
  Random (todas as distribuições; sequência do `random` do Python) e Mouse (Visibility e Look, porta de
  `KX_MouseActuator`). Teste ganhou `moved rv joy kid mvis` na linha CHECK, iguais nos quatro modos.
- Últimos tradutores: actuator Constraint (Loc, Distância, Orientação e Force Field, porta de
  `KX_ConstraintActuator` com damping, Time e Persistent), Steering (Seek, Flee e Path Following via
  `findPath`, com facing; sem simulação de obstáculos nem Normal Up, que ficam como brick), sensor Actuator
  (actuator ativo no frame anterior; se o actuator lido não for convertido, o controller fica como brick) e
  Animation Event. Helpers desses tipos só entram no código gerado quando usados.
- `KX_AnimationEvent.getFireCount(index=-1)` (C++): quantas vezes o gatilho disparou (-1 = todos), usado pelo
  Animation Event convertido.
- Teste à parte (bricks × convertido): os cinco Constraints deram posição/orientação iguais, Animation Event
  igual (3 disparos em 60 frames); Steering 1 frame atrás, o mesmo atraso que um contador Always + Property Add
  convertido já mostra (59 × 58).
- `sca.c`: cor padrão de sensor novo passa a ser cinza 0.17 (43/255), em vez da cor de box do tema.
- Sound também nos modos Play Stop, Loop Stop e Loop End: o componente detecta o pulso negativo do controller
  (`_fall`) e para o som ou encerra o loop no fim da volta, como `KX_SoundActuator`. A cena de teste ganhou um
  Sound Loop Stop ligado ao Delay; bricks e convertido seguem com a mesma linha CHECK.
- Links entre objetos: sensores e actuators de outro objeto ligados ao controller viram código sobre `scene.objects.get(<nome>)` (ignorado se o objeto sumir); desativação dos originais passa a olhar todos os objetos. Teste ganhou a Box (`boxn`, `boxz` na linha CHECK).
- Collision e Ray por material: helper `_has_mat` repete `RAS_Mesh::FindMaterialName` (nome sem prefixo MA); Ray sem x-ray exige o material no primeiro objeto atingido. Teste ganhou `sawmat` na linha CHECK.
- Camera actuator: helper `_follow` porta a conta de `KX_CameraActuator` (altura, atrás do eixo com damping,
  distância mín./máx., -Z para o alvo). A cena de teste ganhou a câmera "Cam" seguindo o Player e a posição
  dela entrou na linha CHECK (igual nos dois). Controller Python fica como brick, com aviso explícito.

- Novos tradutores: Collision (filtro por propriedade, via `collisionCallbacks`), Near (com histerese do reset),
  Radar (cone pelo eixo local), Ray (`rayCast` com x-ray e máscara), Delay (mesma contagem de
  `SCA_DelaySensor`, em frames), Mouse Over/Over Any (`getScreenRay` da câmera ativa); controller Expression
  (AND/OR/NOT, `=`, `<>`, nomes de sensor ou game property); actuators Edit Object (Add Object com
  velocidade, End Object, Replace Mesh, Dynamics), Scene, Game (Quit/Restart/Start) e Visibility.
- Cada sensor só é avaliado quando algum controller dele está no estado ativo, como na engine (conta certo
  para Delay/Near/Property Changed).
- Teste ampliado (Delay + Expression + Add Object no estado 3, Ray na Wall): bricks e convertido deram a mesma
  linha `CHECK score=10 ticks=32 alive=True state=4 x=3.20 y=0.00 pulses=3 bullets=3 saw=1` (Player na origem
  para o Ray acertar a Wall).

## 2026-09-30 - Logic Bricks → Python Component (fase 1)

- Botão **Convert to Python** no header do Logic Editor (e em View): `logic.convert_to_component` em
  `bl_operators/logic_to_python.py`. Gera o texto `<objeto>_logic.py` com uma classe `KX_PythonComponent`,
  registra via `logic.python_component_register` e desativa (não apaga) os bricks convertidos; sensor/actuator
  só é desativado se todos os controllers ligados a ele foram convertidos.
- `update()` segue a ordem da engine: sensores (uma vez cada), controllers, actuators, com o estado lido no
  começo do frame. Sem isso o componente ficava um frame adiantado (sensor lendo propriedade alterada por
  actuator no mesmo frame).
- Brick sem tradutor, ou controller ligado a sensor/actuator de outro objeto: controller fica ativo e vira TODO
  no código e no relatório. Teclas: identificador do RNA (`LEFT_ARROW`, `NUMPAD_1`) mapeado para `events.*KEY`.
- Teste: `tools/create_logic_convert_scene.py` no `RangeRuntime`, com bricks e convertido: mesma linha
  `score=10 ticks=32 alive=True state=4 x=-6.00`. No demo Destruction os 10 controllers ficam como pendentes
  (Python, Sound, Collision) sem erro. Obs.: o enum `evaluation_type` do Property sensor depende do tipo da
  propriedade; defina `property` antes.

## 2026-09-30 - Release 0.4.6 (Windows e Linux)

- `ANASTACIO_VERSION_STRING` 0.4.6; README com downloads e novidades da 0.4.6 (câmera FX, chuva, destruição,
  Reverb Area, soft body, Outliner, MSAA 2x). Pacote Windows montado sobre o staging da 0.4.5 com os binários e
  scripts novos de `build/bin/`, zipado com `zipfile` (caminhos com `/`). Linux 0.4.6 sai à parte na mesma release.
  O About (`wm.py`) também mostra 0.4.6.

## 2026-09-30 - Linux: MP3 no aud/Sound actuator (libsndfile 1.2.2 no pacote)

- Kitsuy: jogo abre com tela preta no player Linux 0.4.5 e funciona no Windows; causa apontada por ele: som do
  `aud`. Reproduzido com o pacote publicado: `.mp3` falha com "The file couldn't be read with any installed file
  reader", `.ogg` toca. No Linux o FFmpeg fica desligado (`WITH_CODEC_FFMPEG=OFF`) e o Audaspace le tudo pela
  libsndfile; o pacote levava a do Ubuntu 22.04 (1.0.31), que so le MP3 a partir da 1.1.0. No Windows o FFmpeg le.
- `tools/linux/container-build-22.04.sh` compila a libsndfile 1.2.2 (`ENABLE_MPEG=ON`, mpg123/lame/FLAC/Opus do
  apt) em `/usr/local`, que o `ld.so.cache` resolve antes da do sistema; `package-runtime.sh` empacota essa.
  No fim o script confere a string `libsndfile-1.2.2` na `lib/libsndfile.so.1` do tarball. Versao padrao: 0.4.6.
- Pacote 0.4.6 validado: `RangeEngine -b` toca `.mp3` e `.ogg` pelo `aud`; codecs carregados de `lib/`
  (`LD_DEBUG=libs`); maior simbolo `GLIBC_2.35`; demo `Example_ImgGui` no `RangeRuntime` tocou a musica de
  fundo (ouvido na maquina Linux). Falta publicar e o Kitsuy confirmar com o jogo dele.

## 2026-09-30 - Linux: colormanagement no pacote (OpenColorIO 1.1.1)

- Kitsuy: o pacote Linux nao tinha `2.79/datafiles/colormanagement`; o player rodava em "Color management: using
  fallback mode" (so Linear/sRGB, sem os colorspaces do `config.ocio`; o BGE nao usa Filmic/Looks, a diferenca
  aparece em texturas float EXR/HDR e colorspaces de imagem). A pasta so e instalada com `WITH_OPENCOLORIO`.
- O apt do Ubuntu 22.04 ja traz a OCIO 1.1.1 (`libopencolorio-dev`), a API 1.x de `intern/opencolorio`; os
  presets `linux-runtime` e `linux-editor` passam a ligar `WITH_OPENCOLORIO`. O container confere no fim que o
  tarball tem `lib/libOpenColorIO.so.1` e `colormanagement/config.ocio`. Host 24.04+ (so OCIO 2.x): `-DWITH_OPENCOLORIO=OFF`.
- A checagem da libsndfile no script (`ldconfig -p | grep | grep -q`) derrubava o build com SIGPIPE (141) sob
  `pipefail`; agora le o cache de um arquivo.
- Pacote 0.4.6 validado: sem a linha de "fallback mode"; cena `tools/create_rain_splash_scene.py` rodou 25 s no
  `RangeRuntime` sem erro; `libOpenColorIO.so.1` exige no maximo `GLIBC_2.33`.

## 2026-09-30 - Chuva do World: respingo, aura, raio e riscos finos

- World › Rain ganhou dois efeitos, desligados por padrão (versioning 1.6.114):
  - **Splash**: gotas que sobem ao bater nas superfícies voltadas para cima, com borda. Roda dentro do passe
    de chuva já existente (`rainSplash()` em `RAS_Rain2DFilter.glsl`, `ge_RainParams4`), sem passe a mais.
  - **Aura**: riscos parados de 15–50 ms, em leque, no contorno de cima da silhueta dos objetos com a
    propriedade `rain_aura_property` (padrão `aura_chuva`). `KX_RainAura` guarda as arestas vivas por malha,
    acha a silhueta em espaço local e desenha todos os riscos com um `glDrawElements` (VBO dinâmico, máx. 4096).
  - **Aura** com tamanho constante na tela: os riscos (em mm) escalam com distância/3 m; antes só apareciam
    a ~3 m da câmera.
  - **Lightning**: raios automáticos (`rain_lightning_rate` por minuto) ou por Python, 2–4 descargas com
    decaimento. Lógica compartilhada em `BKE_rain_lightning` (agenda, pulsos, raio com ramos por midpoint
    displacement). `KX_RainLightning` desenha uma fita contínua virada para a câmera com perfil gaussiano e
    pontas redondas (sem bordas duras), numa chamada; o clarão entra no filtro de chuva (`ge_RainLightning`).
- Chuva Classic refeita: linhas anti-aliased de largura em pixels (3 camadas, gota até ~15% da tela), no
  lugar do ruído esticado que gerava riscos grossos perto da câmera. `rain_streak_width` 1,0 = 2 px em 1080p.
- 3D View: o compositor recebe `rain_params4`, `rain_lightning` e `rain_streak_width` (respingo, riscos finos
  e clarão iguais ao jogo); `view3d_rain.c` desenha aura e raio; o timer do viewport roda com esses efeitos.
- Python: `KX_WorldInfo.setWeather(name, value)`, com os nomes do Property actuator mais `splash*`, `aura*`,
  `lightning*` e `rain_streak_width`; `KX_WorldInfo.strikeLightning(bolt=True)`. Splash, aura e largura são relidos do World a cada frame.
- Teste: `tools/create_rain_splash_scene.py` (versão Python do protótipo removida) no `RangeRuntime`: 60 FPS,
  sem erro de GLSL/Python, aura e respingo conferidos em screenshot.

## 2026-09-29 - Câmera do jogo: foco, rastreio, Camera FX e tremor

- DNA `CameraGameFX gamefx` no fim de `Camera` (defaults em `BKE_camera_gamefx_init`, versioning em
  `versioning_range.c`); RNA `Camera.game_fx`; painéis "Focus & Tracking", "Camera Effects" e "Camera Shake"
  (só Range Game). Tudo desligado por padrão.
- `KX_Camera::UpdateGameFX` roda para a câmera ativa em `KX_SimulationPipeline`, depois do scenegraph: foco
  (Manual/Object/Property/Auto), rastreio Look At/Drone como offset em `GetRenderOrientation`/`GetRenderPosition`
  (`worldOrientation` não muda), velocidade da câmera e tremor por trauma. O terremoto do World agora chama
  `SetEarthquakeShift` e soma com o `shake()`.
- Filtros reservados `FILTERPASS_CAMERA_DOF` (18) e `FILTERPASS_CAMERA_LENS` (19), shaders
  `RAS_CameraDof2DFilter.glsl` e `RAS_CameraLens2DFilter.glsl`, uniform `ge_CameraFX[6]`;
  `reservedPassIndex` passou para 20. Os passes só existem com um efeito ligado
  (`RAS_2DFilterManager::RemoveReservedFilterPass`).
- API Python e migração do Rolima Racer em `docs/camera-fx.md`. O atributo `fstop` do plano não foi exposto.
- Teste: `tools/create_camera_fx_scene.py` no `RangeRuntime`: alvo por propriedade seguido (tela ~0,55/0,59 com
  offset -0,1), trauma 0,53 → 0 em 1,5 s, alvo removido → `focusValid=False` e foco manual, efeitos desligados
  sem erro de shader.

## 2026-09-29 - Generate Fragments põe os pedaços num collection do Outliner

- Os collections do Outliner (`SceneCollection`) ganharam RNA:
  - `scene.collections` (nível de cima), com `new(name, parent=None)`, `remove(collection)` e `find(name)`, que
    busca em qualquer profundidade;
  - `SceneCollection.name`, `uid`, `use_game` (o "not in game" do Outliner, que move os objetos para a
    layer 20) e `children`;
  - `ObjectBase.collection`, que funciona só pelo `scene.object_bases`, porque o collection é da base na cena.
  Mudar `use_game` ou o collection de uma base roda `BKE_scene_collections_game_sync`, como o Outliner faz.
- O operador Generate Fragments põe os pedaços no collection `<nome>_fragments`, dentro do collection do
  objeto. Gerar de novo reaproveita o collection. Com os pedaços na layer 20, o collection fica marcado
  como fora do jogo. Conferido no editor headless: collection dentro do pai, reaproveitado, 6 pedaços, layer 20; com a layer 3, fica no jogo.
- Painel Explosive: `layout.split(percentage=...)` virou `factor=` (o UILayout do fork não aceita mais
  `percentage`); o painel dava TypeError ao ser desenhado com um Effect.
- Painéis Destruction e Explosive reorganizados no padrão do painel Physics: seções com título e ícone
  (Fragments, Break, Debris; Blast, Trigger, Effect), cada seção numa caixa (`layout.box()`), como o
  painel Physics do flowmenu (`flowmenu/custom_pt_physics.py`).

## 2026-09-29 - Ponteiros de jogo no `library_query.c` e import do `aud` sem crash

- `BKE_library_foreach_ID_link` (`library_query.c`) não listava `vehicle_steering_wheel`, `collision_bound`,
  `gpu_particles.collision_ground_object` e `gamePredefinedBound`. Apagar o objeto ou a malha apontada deixava
  o ponteiro pendurado. Agora entram com `IDWALK_CB_NOP` (o RNA não conta usuário neles) e viram None ao apagar
  o alvo. Conferido no editor headless.
- `initGamePython` (`KX_PythonInit.cpp`) chamava `Py_DECREF(NULL)` se o import do `aud` ou de um módulo interno
  falhasse. Agora imprime o erro Python e segue.

## 2026-09-29 - Destruição e explosões nativas (painéis Destruction e Explosive, `KX_DestructionManager`)

- Origem: protótipo Python (`destruction.py` + `First_Person_destruction.range`, fora do git). Plano e
  aprendizados de cada fase em `docs/destruction-plan.md`.
- DNA: `RangeDestructionSettings` (grupo de pedaços, Break Impulse, Burst Speed, Debris Lifetime, flags) e
  `RangeExplosiveSettings` (Effect, Radius, Force, Up Bias, Fuse, Impact Impulse, Effect Life, flags) no fim do
  `Object`; `OB_DESTRUCTIBLE`/`OB_EXPLOSIVE` (`gameflag2`, bits 14 e 15); `GameData.max_debris` (padrão 150).
  Ponteiros `fragments` e `effect` em `lib_link`, `expand` e `library_query`; Copy Game Physics copia os dois.
  Arquivos antigos abrem com tudo desligado; o primeiro enable semeia os padrões.
- Editor: painéis Destruction e Explosive na aba Physics (Static, Dynamic e Rigid Body) e Max Debris na física
  da cena. Botão Generate Fragments... (`object.destruction_fragments_generate`, Cell Fracture): cria o grupo
  `<objeto>_fragments` com os pedaços em Rigid Body e Convex Hull, massa repartida por volume, material interno e
  layer escolhida.
- Runtime (`KX_DestructionManager`, um por cena): quebra por colisão com o `appliedImpulse` do contato, fora do
  callback de física; pedaços replicados direto do grupo (sem Dupli Group), com velocidade herdada e burst;
  explosão por `SphereQuery` (novo em `PHY_IPhysicsEnvironment`, Bullet via `aabbTest`) com queda linear,
  oclusão só por geometria estática e impulso dos pedaços repartido por massa; explosivo com pavio contado desde a
  entrada no jogo, impacto, reação em cadeia (um elo por frame) e Effect; destrutível e explosivo ao mesmo tempo
  quebra e explode uma vez só. Detritos com tempo de vida e fila FIFO de Max Debris.
- API Python: `shatter()`, `detonate()`, `isDestructible`, `isExplosive`, `breakImpulse`, `fuse`, `onBreak`,
  `onExplode` no `KX_GameObject`; `explode()` e `maxDebris` no `KX_Scene`. Documentada nos `.rst` de
  `source/doc/python_api/rst/bge_types/`. As listas de callbacks são copiadas para cada objeto do `addObject`.
- Demo `source/release/demos/Destruction/`: a First Person com caixas, parede, barris em cadeia, granada (G) e
  explosão na mira (E), tudo pelos painéis; o componente da demo só cuida das teclas e do tremor de câmera.
- Testes automáticos no `RangeRuntime` (F2 a F5, log em arquivo): todos PASS. A cena da F4 também passa no build
  Web (Chrome). A sensação no jogo ainda depende do usuário jogar a demo.
- Fica para depois: logic brick de explosão, variações de fratura sorteadas, fade-out dos detritos e corte em
  tempo real.

## 2026-09-29 - Soft body no jogo: mapeamento com escala, transformação, velocidade, suspend e deformer

- Mapeamento vértice → nó (`CcdPhysicsController::CreateSoftbody`): a posição do vértice agora é comparada já
  escalada; com escala não uniforme a malha renderizada encolhia (extensão local 0,67 em vez de 2) e, com escala
  uniforme, cantos e arestas pegavam nós errados. Convex hull passa a usar os pontos escalados (antes o corpo tinha
  o tamanho sem escala). Retorno nulo de `CreateFromTriMesh`/hull agora é tratado.
- Transformação: `SetSoftBodyTransform` aplica o delta entre a transformação atual e a nova aos nós, então
  `worldPosition`/`worldOrientation`/`applyMovement`/`applyRotation` funcionam depois do primeiro quadro (antes só
  valiam uma vez). O estado de movimento reporta a rotação da pose (shape matching) ou a base inicial, não mais identidade.
- Velocidade: `getLinearVelocity`/`getAngularVelocity`/`setAngularVelocity` e `getVelocity(pos)` passam a funcionar
  em soft body (média ponderada por massa dos nós; angular por I⁻¹L).
- `suspendDynamics`/`restoreDynamics`: zera e restaura as massas dos nós (antes o corpo continuava caindo e o
  `restore` podia derrubar o runtime com ponteiro nulo em `SetTransform`).
- `mass`/`friction` em Python: `setTotalMass` e `kDF` (antes `mass` era ignorado e `friction` imprimia no stdout).
  Corrigida a troca entre `SetSoftAngStiff` e `SetSoftVolume`; setters de `m_cfg` não pedem mais recálculo de
  constantes a cada chamada.
- `ReplaceControllerShape`: cria o novo soft body antes de apagar o antigo, respeita física suspensa e mantém o
  filtro de colisão; `addSoftBody` recebe grupo/máscara também na criação e na atualização do controlador.
- `KX_SoftBodyDeformer::Apply`: índice checado contra o tamanho (vértices sem nó, ex. material sem física, seguem o
  objeto em vez de ler fora do vetor); AABB só é zerada quando vai ser recalculada.
- Conversão: soft body tem prioridade sobre modificador/shape key/armature (antes um Subsurf ou vertex group fazia a
  malha ficar parada enquanto a física andava); é emitido aviso no console quando isso acontece.
- Teste: `tools/tests/soft_body_test.py` (16 checagens). Código antigo: 11 falhas; com a correção: 16/16.
- Fica para depois: pular o upload da malha quando o corpo está parado — soft body do Bullet 2.x não dorme.

## 2026-09-29 - Reverb Area nativa (substitui o componente RanGE-SoundReverb)

- Origem: `tools/soundReverb.range` (Blender 2.79 da Range 1.6) trazia o componente Python `Range_SoundReverb`,
  que exigia um componente em cada speaker e propriedades de texto digitadas à mão (`ReverbArea`, `RA_*`, `FA_*`).
  Problemas dele: reverb calculado pela posição do speaker (não do ouvinte), rescan da cena por speaker
  (`reverbAreas` vs `_reverbAreas`), remoção durante iteração, cubo sem rotação, esfera só com escala X, `exec()`.
- DNA: `RangeReverbAreaSettings` inline no fim do `Object` (`reverb_area`, sem ponteiros) + `OB_REVERB_AREA`
  (`gameflag2`, bit 13). Arquivos antigos: struct zerada; ligar a flag semeia o preset Generic (`inner_factor == 0`).
- RNA/UI (`rna_object.c`, `properties_data_empty.py`): painel "Reverb Area" no Empty com Behavior
  (Generic/Underwater/Cavern/Hall/Forest/Custom), Shape (Sphere/Box, sincroniza `empty_draw_type`), Size
  (`empty_draw_size`), Full Effect Zone, Priority e Filter; painel "Advanced" com os 12 parâmetros EFX e ganhos do
  filtro. Escolher um Behavior copia os valores (tabela da Range); editar qualquer valor troca para Custom.
  `Add > Reverb Area` (`object.reverb_area_add`) cria o Empty já configurado (padrão Box, desenho Cube).
- Runtime: `KX_Scene::UpdateReverbAreas` (mesma cadência do update de áudio 3D) leva a câmera ativa ao espaço
  local de cada área dividido por `empty_drawsize * escala` (rotação e escala não uniforme; esfera vira elipsoide),
  fade linear entre `inner_factor` e a borda, vence a maior influência e a prioridade desempata.
  `KX_Speaker::ApplyAreaReverb` aplica só em speakers 3D, não toca em speaker cujo efeito veio de `SetEffect`
  (script), manda os 13 parâmetros só quando a área dominante muda e, por quadro, só ganho/filtro quando mudam.
  Áreas registradas na conversão, em `AddReplicaObject` e no `MergeScene`; removidas com o objeto.
- Teste `tools/tests/reverb_area_test.py`: 10 checagens de editor e 9 posições de câmera no `RangeRuntime`
  (fora, centro, faixa de fade, área aninhada por prioridade, caixa rotacionada com escala 2x1x1, saída
  removendo o efeito, speaker 2D e speaker de script intocados): todos PASS. O teste confere o estado mandado
  ao OpenAL, não o som; audição no jogo real pendente.

## 2026-09-29 - MSAA mínimo do jogo passa de 4x para 2x

- O piso forçado para a folhagem "Alpha Blend Hashed" (ver entrada da 0.4.4) era 4x, então "AA Samples: Off" e
  `setAntiAliasing(0)` custavam 4x em PC fraco. Alpha-to-coverage só precisa de 2 amostras (N amostras dão
  N+1 níveis de transparência: 2x = 3 níveis, 4x = 5), então o piso vira 2x em `LA_Launcher::InitEngine`,
  `BL_Converter::ConvertScene` e `setAntiAliasing(level <= 1)`. Quem quer folhagem mais suave escolhe 4x/8x.
- Padrão de cenas novas: `gm.aasamples = 2` em `scene.c` e em `BLO_update_defaults_startup_blend` (File > New
  vinha com 4x do startup.blend). Arquivos já salvos mantêm o valor deles.
- Validado com `projects-teste/foliage_aa`: `level_aa0.range` (nível chama `setAntiAliasing(0)`) loga aa=2 e
  mostra o degradê em 3 faixas, sem virar bloco sólido (`shot2x_level_aa0.png`).

## 2026-09-29 - Release 0.4.5: pacote Windows

- Numero da versao 0.4.4 -> 0.4.5 em `ANASTACIO_VERSION_STRING` (splash) e no About (`wm.py`). O pacote Linux
  0.4.5 ja publicado foi compilado antes desta troca e mostra 0.4.4 no splash e no About.
- `AnastacioEngine-0.4.5-windows-x64.zip` (+ `.sha256`) montado a partir do zip 0.4.4 publicado (4.657 arquivos,
  mesmo `blender.crt.manifest`, conferido por SHA-1 contra os DLLs), trocando so `RangeEngine.exe`,
  `RangeRuntime.exe` e `wm.py` (unicos arquivos diferentes do `build/bin`). O `blender.crt.manifest` do
  `build/bin` nao bate com os DLLs de `blender.crt/`; nao usar. Zip com `zipfile` do Python, sem `\` nos nomes.
- Antes de empacotar: regressao, ABI de `Range.constraints` (estatico e runtime) e teste de constraints de bone
  passando. Validado extraindo em `D:\t045`: `RangeEngine --version` e `-b` saem com 0 e o About le 0.4.5;
  `RangeRuntime` abre `benchmark.range` e `ImGui_example.range` e segue rodando; sem eventos SideBySide.

## 2026-09-29 - Constraints de bone: teste de correcao e custo do IK

- `tools/tests/bone_constraint_test.py`: compara a `pose_matrix` de cada bone no jogo com a avaliacao do
  editor (60 quadros, alvo mudando posicao/rotacao/escala). Resultado no Windows: erro 0 em Copy Location,
  Copy Rotation, Copy Scale, Copy Transforms, Track To, Damped Track, Locked Track, Stretch To, Floor,
  Transformation, Limit Distance, Limit Rotation e IK. Child Of (fora da lista de
  `BL_ArmatureObject::LoadConstraints`) nao acompanha o alvo, como esperado. Clamp To nao testado (precisa de curva).
- O jogo usa o proprio `BKE_pose_where_is`; a lista em `LoadConstraints` so decide quais alvos externos sao
  sincronizados com objetos do jogo (1o e 2o alvo) e ficam expostos ao Python. Constraints de objeto: so
  Rigid Body Joint e convertido.
- Pegadinhas conferidas: sem action tocando nem Armature Actuator em Run, a pose so acompanha o alvo com
  `armature.update()` a cada tick; e a pose so e recalculada se alguma malha filha da armature estiver visivel
  (`anim_needs_update`), entao ler bones fora da camera devolve valor antigo.
- Custo do IK (modo `--make-perf-scene`, 20 rigs com cadeia IK de 10 bones, na tomada): categoria Skinning
  2,0 ms/quadro com Standard e 2,6 ms com iTaSC (~0,1 ms por rig), 60 fps nos dois.

## 2026-09-29 - Linux: pacote compilado no Ubuntu 22.04, icone da Range

- Build num container `ubuntu:22.04` com Podman (`tools/linux/container-build-22.04.sh`): o maior simbolo exigido
  cai de `GLIBC_2.38` para `GLIBC_2.35` (Ubuntu 22.04 e Debian 12 passam a rodar). 257 `.so` em `lib/`, incluindo
  `libOpenImageIO.so.2.2`; o pacote antigo falhava no Ubuntu 26.04 do Fumangy com `libOpenImageIO.so.2.4`.
  Pacote: 234 MB. Publicado como release v0.4.5 (so Linux; Windows continua na 0.4.4).
- `FindEmbree.cmake`: so acrescenta a biblioteca de um componente se ela existir (o 22.04 so tem `libembree3.so`;
  sem isso faltava `rtcIntersect1` no link).
- O `cmake --install` do preset editor tambem instala o `RangeRuntime`: compilar os dois alvos em `build-linux-editor`.
- Icone: `GHOST_WindowX11.cpp` define `_NET_WM_ICON` (48x48, do `winrange.ico`); o pacote leva `range-engine.png`,
  `RangeEngine.desktop` (`StartupWMClass=Range Engine`) e `install-desktop.sh`. Conferido com `xprop` no pacote.
- Teste em containers limpos (Ubuntu 22.04, Debian 12, Ubuntu 26.04, Fedora): alem das bibliotecas de desktop
  (ALSA/Pulse, Wayland, xkbcommon, gbm), faltavam `libva*`, `libvdpau` e `libOpenCL`, puxadas pelo FFmpeg da
  OIIO. Como sao carregadores genericos (o driver fica no sistema), agora vao em `lib/`.
- Roadmap: bug do menu do player Linux (Kitsuy) cancelado pelo usuario.

## 2026-09-29 - Linux: pacote com as bibliotecas da distro, build do zero conferido

- **Retorno do Discord (Fumangy):** o pacote 0.4.4 "pede dependencias". Extraido sem `apt install`, ele usava
  as `.so` do sistema com nomes do Ubuntu 24.04 (OpenImageIO 2.4, OpenEXR 3.1, boost_locale 1.83 etc.) e exige
  `GLIBC_2.38`/`GLIBCXX_3.4.32` (`__isoc23_strtol`, `__isoc23_sscanf`, `fmod`).
- `tools/linux/package-runtime.sh` agora copia para `lib/` as dependencias diretas e indiretas (265 `.so`),
  menos glibc, libstdc++, GL/driver, X11/xcb/Wayland, audio e servicos do desktop, e troca `DT_RUNPATH` por
  `DT_RPATH` nos dois executaveis (sem isso as `.so` empacotadas nao acham umas as outras). Pacote de teste:
  197 MB (0.4.4: 85 MB).
- Teste do pacote extraido: `ldd` e `LD_DEBUG=libs` so carregam de fora de `lib/` as bibliotecas do sistema;
  `ssl`, `sqlite3`, `lzma` e numpy do Python sobem; editor abre com interface (screenshot); runtime abre demo.
- Nao resolvido: glibc 2.38 continua exigida (Ubuntu 22.04 e Debian 12 fora). Precisa de build numa base
  antiga; esta maquina nao tem Docker/Podman.
- **Build do zero:** clone limpo da `main` + `cmake --preset linux-editor -S source` compilou RangeEngine e
  RangeRuntime (2858/2858). A doc mandava usar a branch `linux-sync`, 106 commits atras; doc corrigida e branch
  apagada.
- Achado de passagem: o `RangeRuntime` trata `SIGTERM` mas nao encerra (igual no build e no pacote); `timeout`
  nao fecha o player.

## 2026-09-28 - Release 0.4.4: pacote Windows

- `AnastacioEngine-0.4.4-windows-x64.zip` (+ `.sha256`) anexado à release `v0.4.4`, que já tinha o Linux. A tag
  continua em `63e9b2e3` (build Linux); o Windows inclui também as correções de previews do Asset Browser
  feitas depois (anotado nas notas do release). README aponta para os dois pacotes 0.4.4.
- Montado como a 0.4.3: a partir do zip 0.4.3 publicado (mesmo `blender.crt.manifest` e cubins, 4.657 arquivos),
  trocando `RangeEngine.exe`, `RangeRuntime.exe` e os 6 scripts mudados desde `v0.4.3`. A pasta de staging da
  0.4.3 tinha 4.796 arquivos, diferente do zip; não usar como base.
- Validado extraindo em `D:\t044`: `RangeEngine -b` sai com 0 e carrega a opção Auto; `RangeRuntime` abre
  `benchmark.range` e segue rodando.

## 2026-09-28 - Asset Browser: previews de .range, grupos vazios e console no Windows

- **`.range`:** "Generate Previews" e o Auto só procuravam `.blend`; bibliotecas salvas como `.range` ficavam sem nenhuma miniatura (achado no teste do usuário no Windows, biblioteca "Carros Velhos").
- **Grupos vazios:** em `bl_previews_render.py` um grupo sem objetos deixava a câmera de preview em NaN, e o grupo seguinte saía em branco. Grupos vazios agora são pulados.
- **Windows:** o processo de geração em segundo plano usa `CREATE_NO_WINDOW` (antes abria um console por arquivo).
- Continuam sem miniatura, sem ser bug do script: câmeras e lâmpadas; objeto com Object Color de alpha 0; material com nó Material apontando para ele mesmo (o gerador de ícones do core não desenha).
- Teste (`-b`, cópia do arquivo do usuário): materiais, objetos e grupos com preview, incluindo o grupo que vinha depois dos vazios.

## 2026-09-28 - Runtime: Show Framerate e Debug Properties vindos da cena

- O runtime separado (`LA_Launcher.cpp`) só lia essas opções por `-g`; as marcadas na cena eram ignoradas, e só funcionavam dentro do editor, que as copia antes de rodar (`game_set_commmandline_options`). Agora o padrão é a flag da cena para Framerate/Profile, Debug Properties, Render Queries e Ignore Exit Key; `-g` continua tendo prioridade.
- Debug Mode (ligado por padrão em toda cena) e Console continuam só por `-g`, para jogos exportados não abrirem com a barra de debug.
- Achado no teste do loop de tempo (a cena teve que ligar o painel por `render.showFramerate`). Teste: cena só com as flags → painel e propriedades aparecem, sem a barra de debug (screenshot).

## 2026-09-28 - Asset Browser: Link de objeto e previews automáticas

- **Link de objeto:** com o botão Link (ou Ctrl), um objeto arrastado agora vem ligado dentro de um grupo local com o nome dele, instanciado no ponto do drop (o jeito do 2.79: objeto ligado direto não pode ser movido). O `dupli_offset` do grupo é a posição original, e drops seguintes do mesmo objeto reaproveitam o grupo. Antes, objetos sempre entravam como append (achado no teste visual do usuário).
- **Append depois de Link:** o 2.79 devolve o dado já ligado em vez de copiar; o drop agora cancela com uma mensagem clara em vez de "Could not load".
- **Previews automáticas:** opção "Auto" ao lado de "Generate Previews" (ligada por padrão). Um handler verifica a cada 2 s de atividade da UI os `.blend` das bibliotecas abertas no Asset Browser e gera em segundo plano (um processo por vez, o mesmo script do `wm.previews_batch_generate`) os nunca gerados ou modificados depois da última geração; a lista é atualizada ao final. Estado e datas ficam em `asset_previews.json`, na pasta de configuração do usuário.
- **Testes** (`-b`): link de objeto (2 drops, 1 grupo), grupo e material ligados, append após link com o erro novo, arquivo salvo e reaberto; geração automática com previews 128×128 e a fila vazia depois.
- Código comum às plataformas; no Windows só falta recompilar e conferir.

## 2026-09-28 - Versão do splash e do About; janela testada em Ubuntu limpo

- O splash mostrava "AnastacioEngine 0.4.0 Release Candidate" (texto fixo, derivado de
  `RANGE_MINSUBVERSION` = 113) e o About mostrava "0.4.1". Agora os dois mostram 0.4.4. O splash usa
  `ANASTACIO_VERSION_STRING` em `BKE_blender_version.h`, e o About (`wm.py`) tem o mesmo número. Em cada
  release, atualize esses dois lugares. Conferido com screenshot do editor no Linux.
- Pacote de teste 0.4.4 num Ubuntu 24.04 limpo (container `unshare`, Intel Mesa): não falta nenhuma
  biblioteca; runtime e editor abrem janela e as cenas do Kitsuy passam. Detalhes em `linux-build.md`.

## 2026-09-28 - Linux: bugs do Kitsuy validados (Intel, NVIDIA e sem GPU); crash GLX com vsync adaptativo

`bash projects-teste/kitsuy_check.sh` rodado no Linux (X na Intel Raptor Lake, `prime-select on-demand`):
setHalfAnimations `OK frames=600`, carro `maxErr=0.0000` nas 6 variações, folhagem `aa=4` com degradê nos PNGs. Mesmo resultado com offload NVIDIA (RTX 5060 Laptop,
`__NV_PRIME_RENDER_OFFLOAD=1 __GLX_VENDOR_LIBRARY_NAME=nvidia`; processo confirmado no `nvidia-smi`).
O `aa=0` da integrada, suspeito do menu que só funcionava na dedicada, não se reproduziu aqui.

Sem GPU (`LIBGL_ALWAYS_SOFTWARE=1`, llvmpipe) o `RangeRuntime` morria na hora com `X Error BadValue`
(GLX, valor `0xffffffff`) em `GHOST_ContextGLX::setSwapInterval(-1)`: vsync adaptativo exige
`GLX_EXT_swap_control_tear`. `GLXEW_EXT_swap_control_tear` lê a string do cliente (anuncia a extensão),
mas o Mesa valida pela lista da tela, que no llvmpipe não a tem. Fix: com intervalo negativo, consulta
`glXQueryExtensionsString` da tela e, sem a extensão, cai para vsync normal. Depois do fix, o mesmo
script passa inteiro em llvmpipe. Armaduras (`halfanim_crash`) validadas visualmente pelo usuário na bateria:
Intel 600 ticks em ~11 s (velocidade real; a cena é frenética de propósito, 150 rigs com loop de 20 frames),
llvmpipe ~73 s (~8 fps, câmera lenta: o BGE desacelera a lógica quando o render não acompanha). Esperado para
rasterização em CPU, não é regressão. O WGL só retorna falha nesse
caso, sem derrubar o processo.

## 2026-09-28 - Bugs do Discord (Kitsuy): crash com setHalfAnimations, folhagem branca/preta e rodas do carro

- **Crash no skinning CPU/IK com `setHalfAnimations(1)`** (backtrace Linux em `ApplyPose` → `iksolver`).
  `KX_GameObject::GetDoAnimations()` alterna `m_bDoAnimations` a cada chamada quando half animations está
  ligado, e `KX_Scene::UpdateAnimations` chamava duas vezes por objeto: a primeira não criava a entrada em
  `m_animNeedsUpdateCache`, a segunda disparava a `UpdateAnimPoseTask` mesmo assim, e a task inseria no
  `unordered_map` a partir das threads do pool (rehash concorrente, mapa corrompido, deform com objeto
  inválido/duplicado). Agora uma chamada por objeto decide cache e task; a task só atualiza entrada existente.
  Efeito colateral: `setHalfAnimations(1)` passa a de fato animar em quadros alternados (antes a dupla
  alternância anulava o efeito).
- Validado com `projects-teste/halfanim_crash` (gerador `gen_halfanim_crash.py`: 150 rigs com IK, skinning CPU,
  spawnados nos 5 primeiros quadros com half animations): código antigo sai com código 11 no quadro 0 em
  todas as execuções; corrigido roda 600 quadros sem crash (3/3) e as malhas deformam na tela.
- **Folhagem "Alpha Blend Hashed" branca/preta dependendo do arquivo aberto primeiro** (menu → nível).
  Launcher e conversor forçam `gm.aasamples >= 4`, então esses materiais compilam sem o dither, mas o canvas
  podia ficar sem MSAA: `LA_Launcher` passava o `m_samples` lido antes do mínimo (0) para `SetSamples`, e
  `Range.render.setAntiAliasing(0)` (o menu ImGui do template aplica 0 por padrão) derrubava o MSAA para os
  níveis carregados depois. Sem MSAA, o alpha-to-coverage some e sobra o alpha test em ~0.004.
  - `LA_Launcher::InitEngine` usa o mínimo calculado quando `m_samples <= 1`.
  - `setAntiAliasing(level <= 1)` vira 4 (**mudança de API**: AA "desligado" não desliga mais o MSAA).
  - `StartKetsjiShell` restaura o `gm.aasamples` de cada cena ao sair do jogo embutido, para o viewport não
    recompilar os materiais sem dither e o valor forçado não ir para o `.blend`.
  - Validado na tela com `projects-teste/foliage_aa` (planos Hashed com alpha em degradê): sem a correção,
    `setAntiAliasing(0)` no próprio nível deixa as folhas como blocos brancos sólidos (aa=0); com a correção
    aparece o degradê (aa=4). O menu chamando `setAntiAliasing(0)` antes de `startGame` **não** reproduz: o
    nível abre com o motor reiniciado e aa=4. O caso do Kitsuy deve ser o AA 0 aplicado no mesmo motor (script
    de opções no nível ou LibLoad); sem o arquivo dele, não confirmado. O granulado preto no terreno pode ser
    a sombra com dither, que depende do mesmo MSAA (hipótese).
- **Carro só funcionava com "Use Frame Rate"** (física). A flag só escolhe entre `ProceedDeltaTimeCar` (ligada)
  e `ProceedDeltaTime` (desligada). O `stepSimulation` modificado do Bullet guarda `m_localTime = passos *
  substep`, então o `synchronizeMotionStates` do Bullet desenhava cada corpo `(passos - 1)` substeps à frente
  da física quando `physics_step_sub > 1`, enquanto as rodas (`SyncWheels`) usam o transform real: rodas
  descoladas do chassi proporcional à velocidade (0,31 m a 28 m/s com 3 substeps). `ProceedDeltaTime` agora
  publica o transform atual dos corpos ativos (`SynchronizeActiveMotionStates`); com 1 substep nada muda.
- No modo "Use Frame Rate", `CcdPhysicsController::SynchronizeMotionStates` escrevia o transform do centro de
  massa direto no objeto e ignorava o `vehicle_com_offset`: chassi desenhado deslocado pelo offset. Agora passa
  pelo `BlenderBulletMotionState`, que compensa.
- Teste `projects-teste/car_framerate` (carro de 4 rodas, 300 quadros acelerando; mede o offset local das rodas
  no chassi desenhado): antes, 3 substeps sem Use Frame Rate dava erro máx. 0,31 m e offset 0,5 m dava 0,50 m
  com Use Frame Rate; agora 0,0000 nos 6 casos, com trajetórias iguais nos dois modos.
- Os substeps da cena só são aplicados quando ela tem World (`BL_BlenderDataConversion`, herdado do UPBGE).
- `projects-teste/kitsuy_check.sh` gera e roda os três testes (crash, carro, folhagem) para validar no Linux.

## 2026-09-28 - Lâmpadas: correções de bugs (Hemi, Spot 180°, falloff quadrático)

- Hemi não cria mais buffer de sombra: ele não tinha projeção (`gpu_lamp_calc_winmat` ignora Hemi) e custava uma
  passada de sombra por quadro. A cor de baixo (Shadow Color) agora é definida fora do bloco de sombra e não é
  trocada por branco (`GPU_lamp_from_blender`).
- `shade_hemi_spec`: `ang / up` (0/0 com `up == 0`) trocado por `sign(up)`.
- Spot de 180°: a sombra dividia por zero em `tan(90°)`; o ângulo da projeção da sombra fica limitado a 170°
  (o cone de luz continua igual). Mais que isso a resolução do mapa despenca.
- Conversão da lâmpada zerava `att2` sem `LA_QUAD` (flag que a UI 2.79 não mostra); agora usa `la->att2`,
  igual ao shader do viewport.
- Validado na tela pelo usuário comparando runtime antes/depois (`projects-teste/lamps`): Hemi com a mesma cor
  de baixo, Spot 180° com sombra. Ganho de FPS da Hemi não medido (cena leve).
- Pendente da varredura: NaN nos falloffs em casos-limite, early-out para lâmpada culled, matrizes de lâmpada
  recalculadas por material (`GPU_material_update_lamps`), `shadowColor` só leitura em runtime.

## 2026-09-28 - Espelho/água: corte do plano com projeção oblíqua

- `KX_PlanarMap::BeginRenderFace` troca o `glClipPlane` (no-op no core e no WebGL2) por projeção oblíqua
  (Lengyel): o near plane vira o plano do espelho/água, sem mudar shader e sem `discard` (preserva early-z).
  `EndRenderFace` restaura a projeção e o modo MODELVIEW.
- A textura Environment Map Realtime Planar só funciona com uma imagem associada (`BL_Texture` cria o
  `m_gpuTex` a partir dela).
- Validado na tela pelo usuário no `RangeRuntime` Windows e no build Web (cena `projects-teste/planar`):
  espelho mostra só o que está acima do plano, água só o que está abaixo.

## 2026-09-28 - Navmesh dinâmica: debug visual dos obstáculos

- `KX_NavMeshObject::DrawNavMesh` (`nav.draw(mode)`) desenha em amarelo o cilindro de cada obstáculo da
  navmesh dinâmica (círculos na base e no topo, 4 arestas verticais), lido do `dtTileCache`. O buraco na
  navmesh é maior que o cilindro porque soma o raio do agente.
- Os avisos de `dynamic_navmesh` do painel Physics (NAVMESH) também foram para o painel customizado
  `flowmenu/custom_pt_physics.py`, que é o que aparece no editor; antes só estavam em `bl_ui/properties_game.py`.
- Validado na tela: cilindro amarelo, agente com Steering contornando obstáculo que se move, aviso no painel e
  no console com `dynamic_navmesh` não booleana; sem a propriedade o painel não mostra nada, e com Boolean
  marcada mostra o aviso INFO.

## 2026-09-28 - Navmesh dinâmica: API Python (passo 7)

- `KX_NavMeshObject.dynamic` (navmesh em tiles ativa) e `.version` (sobe quando a navmesh muda), só leitura.
- `addObstacle(object, radius=0.0)` / `removeObstacle(object)`: qualquer objeto da cena passa a recortar (ou
  deixa de recortar) todas as navmeshes dinâmicas da cena. Raio 0 usa o raio do "Create Obstacle" ou metade
  da maior dimensão XY da bbox; mudar o raio refaz o obstáculo. `KX_Scene` guarda o raio por obstáculo.
- Teste: cubo sem "Create Obstacle" em (6,0); com raio 3 o caminho vai de 17.89 para 18.75, e continua
  recortado depois de `rebuild()`. Na navmesh estática as chamadas não mudam nada.

## 2026-09-28 - Navmesh dinâmica: Steering refaz o caminho quando a navmesh muda (passo 6)

- `KX_NavMeshObject` tem um contador de versão: sobe ao reconstruir a navmesh e quando `dtTileCache::update`
  termina de refazer os tiles depois de pedidos de obstáculo. `KX_SteeringActuator` (path following) refaz
  `FindPath` quando a versão difere da do caminho atual, além do período de atualização.
- Teste: agente com update period -1 indo de (-8,0) a (8,0); cilindro raio 3 aparece em (5,0) no frame 6.
  Dinâmica: caminho passa de 17.86 (5 pontos) para 18.71 (7 pontos). Estática: fica em 17.34.

## 2026-09-28 - Navmesh dinâmica: obstáculos em runtime (passos 4-5)

- Objetos com "Create Obstacle" abrem buracos nas navmeshes com `dynamic_navmesh`: cilindro com o raio do
  obstáculo e a altura da bbox, em coordenadas locais da navmesh. Mover mais de 0.1 refaz o obstáculo; destruir
  o objeto remove. Independe da Obstacle Simulation da cena.
- `KX_Scene::LogicEndFrame` sincroniza os obstáculos e chama `dtTileCache::update`; pedidos recusados (fila
  cheia) são repetidos no frame seguinte.
- Painel Create Obstacle: aviso quando a cena não tem navmesh dinâmica.
- Teste: cilindro raio 3 no caminho horizontal leva a rota de 17.89 para 18.75; ao tirar o obstáculo volta a
  17.89. Navmesh estática com obstáculo não muda. O Steering actuator ainda não refaz o caminho (passo 6).

## 2026-09-28 - Navmesh dinâmica: build em tiles opt-in (passos 2-3)

- Property de jogo booleana `dynamic_navmesh` no objeto navmesh: `KX_NavMeshObject::BuildNavMeshTiled()`
  reconstrói a navmesh em tiles (48 células) com `DetourTileCache`, a partir dos triângulos do próprio navmesh e
  de `gm.recastData`. Sem erosão, filtro de inclinação nem de bordas: a superfície já foi gerada erodida.
- Sem a property, o caminho estático é o mesmo de antes; sem DNA nova. Property não booleana ou falha no build
  dinâmico: aviso no console e fallback para o estático.
- Painel Physics (NAVMESH): aviso se `dynamic_navmesh` não é booleana, se o mesh está vazio, e nota de que os
  caminhos podem diferir levemente do estático.
- Teste (plano 20x20 + caixa): estático, dinâmico e property INT; caminhos dinâmicos contornam a caixa, com
  comprimento até ~0.6 diferente do estático; property INT cai no estático. Obstáculos em runtime ainda não.

## 2026-09-28 - Recast/Detour: cópia vendorizada já está em dia com o upstream

- Upstream baixado em `tools/recastnavigation-upstream` (commit `9f4ce64`, 2026-02-27; pasta ignorada no git).
- Comparação com `source/extern/recastnavigation`: todos os fontes de `Recast/` e `Detour/` são iguais ao
  upstream, exceto patches locais — `buildMeshAdjacency()` não-static (usado pela `recast-capi`), retorno de
  erro em vez de "Data can be corrupted" ao passar de 0xffff vértices/polígonos, checagens de alocação nula em
  `rcBuildContours`/`dtCreateNavMeshData` e guarda de `m_tiles` nulo em `dtNavMesh`.
- O item do roadmap ("cópia antiga do Blender 2.79") estava errado e saiu. Continua em aberto só a navmesh
  dinâmica, que precisaria vendorizar `DetourTileCache` (disponível no upstream baixado).

## 2026-09-28 - Python: `setTimeScale()` valida o valor

- `bge.logic.setTimeScale()` agora levanta `ValueError` para negativo, NaN e infinito, que corrompiam o
  acumulador de tempo (`KX_KetsjiEngine`). 0 continua aceito como "pausa", para não quebrar scripts; a RNA
  segue com mínimo 0,001 na interface.
- Verificado no `RangeRuntime`: 0 e 2 aceitos; -1, nan e inf rejeitados.

## 2026-09-28 - Build: Ninja volta a rastrear headers (VSLANG=1033)

- Causa: `msvc_deps_prefix` em português (`Observação: incluindo arquivo:`) não batia com a saída do `cl`, e o
  Ninja não registrava nenhuma dependência de `.h`.
- Pacote de idioma inglês instalado no Visual Studio; `build/` reconfigurado com `VSLANG=1033` (prefixo agora
  `Note: including file:`) e rebuild completo de C/C++ via `ninja install` (3078 passos, sem erro; cubins CUDA
  preservados renomeando só o `.ninja_deps`).
- Verificado: `ninja -t deps` lista 228 headers para `KX_ShadowRenderer.cpp.obj`; tocar `KX_GameObject.h`
  gera 96 passos no `ninja -n RangeRuntime`, incluindo esse objeto. `RangeEngine` e `RangeRuntime` (com
  `ValidationProject.range`) abrem.
- Comando de build do `AGENTS.md` e do skill `build-anastacio` agora começa com `set VSLANG=1033&&`.

## 2026-09-27 - Release 0.4.3: pacote Linux

- Linux alcança a 0.4.3: `RangeEngine` e `RangeRuntime` recompilados com o fix do loop de tempo (Fixed Timestep
  fora da interface, `FrameOver()` com v-sync) e o splash novo (reembutido via `datatoc`).
- Pacote `AnastacioEngine-0.4.3-linux-x86_64.tar.xz` (editor + runtime) gerado por `package-runtime.sh`.
  Validado extraindo numa pasta temporária: `RangeEngine -b` com ambiente limpo acha o Python 3.11.9 embutido.
- Testes do pacote extraído (Intel RPL-P, Mesa 25.2, monitor 144 Hz, X11), comparando com o pacote 0.4.2. Cena
  com script que mede o intervalo entre frames e conta passos de lógica por frame (`scene.pre_draw`), 8 s,
  640x360:
  - tic 60 e 144, v-sync ligado/desligado: 60,0/144,1 fps e 1,000 passo por frame nos dois, exceto tic 144 com
    v-sync na 0.4.2 (1 frame com 2 passos e pico de 13,8 ms); na 0.4.3, 0 frames irregulares, pico de 7,3 ms.
  - tic 60 com picos de 30 ms a cada 20 frames: sem v-sync os dois dão 60 fps; com v-sync a 0.4.3 dá 57,6 fps
    (não recupera o atraso, efeito esperado do fix) e a 0.4.2, 60 fps.
  - Sem erros nos logs. Uma cena demo (`Chuva com nuvens.range`) roda sem erro. O `RangeRuntime` ignora
    SIGTERM (só sai com SIGKILL), igual na 0.4.2: não é regressão.
  - Editor com janela: splash novo aparece (a imagem nova está no binário, a antiga não).
- Splash fora do centro no Linux: ele é criado com o tamanho de janela salvo no startup (2494x1371 aqui) e o
  gerenciador de janelas redimensiona depois (1854x1131). O listener de resize dos popups centralizados
  marcava a região, mas o refresh não rodava porque `can_refresh` ficava `false`. Corrigido em
  `ui_popup_block_create` (`interface_region_popup.c`): popups `UI_BLOCK_BOUNDS_POPUP_CENTER` agora podem ser
  reconstruídos. Conferido com printf temporário: o splash é recentralizado para 1854x1131. O zip Windows
  0.4.3 não foi recompilado com este fix.
- O texto de versão do splash estava fixo em "AnastacioEngine 0.4.0 Release Candidate". Isso foi resolvido
  em 2026-09-28 (ver a entrada do topo).

## 2026-09-27 - Loop de tempo: teste automático e zip 0.4.3 atualizado

- Teste automático no `RangeRuntime`: cena simples com um script que mede o intervalo entre frames e conta
  passos de lógica por frame desenhado (`scene.pre_draw`), 8 s por caso, janela 640x360, monitor de 165 Hz (AMD
  RX 6800M). Comparado com o zip anterior da 0.4.3 (antes do fix):
  - tic rate 60, com e sem limite de FPS, flag antiga ligada e desligada, v-sync ligado e desligado: os dois dão
    60,0 fps, 1 passo por frame e nenhum engasgo. O motor sempre marca o ritmo pelo tic rate (sleep), então
    60 Hz num monitor de 165 Hz não mostra o bug do v-sync.
  - tic rate 165 (igual ao monitor) com a flag antiga ligada: o antigo teve 1 a 3 frames de 12 ms sem passo de
    lógica (0,998 passo/frame); o novo teve 0 engasgos e 1,000 passo/frame.
  - tic rate 60 com picos de 30 ms a cada 20 frames: sem v-sync os dois ficam iguais (60 fps, recuperam o
    atraso). Com v-sync o novo não recupera mais (57,7 fps médios, cada pico perde ~13 ms), que é o efeito
    esperado do fix do Kitsuy; o antigo recuperava, mas teve um travão de 111 ms num dos casos.
  - Logs sem erro em todos os casos.
- Zip `AnastacioEngine-0.4.3-windows-x64.zip` refeito a partir do anterior trocando só `RangeEngine.exe`,
  `RangeRuntime.exe` e `2.79/scripts/startup/bl_ui/properties_game.py` (os mesmos 4.657 arquivos, mesmo
  `blender.crt.manifest` da 0.4.2 e mesmos cubins). Validado extraindo em `D:\t043`: `RangeEngine -b` sai com 0,
  Cycles lista CPU e OpenCL, `RangeRuntime` roda os casos acima. Tag `v0.4.3` movida para este commit.
- Falta o teste no jogo real (roadmap).

## 2026-09-26 - Loop de tempo: Fixed Timestep desligado e fix de v-sync (revisão do Kitsuy)

- **Fixed Timestep (Plano 8) desligado.** No modo fixo o `NextFrame()` rodava `m_simulationPipeline->Update()`
  até `m_maxLogicFrame` vezes por frame, mas a física de taxa fixa só aguenta 1 passo (causa provável do crash
  nesse modo). A investigação achou mais problemas no mesmo modo: o sleep antigo continuava ditando o ritmo, então
  os passos alternavam entre 0 e 2 (engasgo); num frame com 0 passos o `ClearInputs()` apagava a tecla; nos passos
  extras `m_logicTime`/`m_frameTime`/`m_animationsTime` não avançavam (só `FrameTiming()` avança, 1x por frame)
  enquanto a física andava 2x; o `JUSTACTIVATED` disparava duas vezes. Mudança: o checkbox saiu de
  `properties_game.py`, `LA_Launcher.cpp` passa sempre `SetUseFixedTimestep(false)` e a descrição RNA virou
  "Deprecated". O bit `GAME_USE_FIXED_TIMESTEP` fica no DNA: arquivos antigos abrem iguais e rodam no modo normal.
  O código do acumulador fica inerte; só o comentário do `.h` mudou (sem mudança de layout).
- **V-sync em `FrameOver()`.** Com v-sync, o tempo em que `SwapBuffers()` fica bloqueado entrava em `m_deltatime`
  e acumulava em `m_overframetime` como se fosse atraso. Agora, com `GetSwapControl() != VSYNC_OFF`,
  `m_overframetime` é zerado. Sem v-sync a lógica antiga fica igual, inclusive o `m_deltaTime` do ramo negativo,
  que aguarda resposta do Kitsuy (roadmap).
- **Comentário errado corrigido** em `KX_RenderPipeline.cpp` (e anotado na entrada antiga do changelog):
  `m_frameTime` não passa pelo acumulador, então chuva/nuvens/flare não ficam mais lentos com o Time Scale.
- `KX_SimulationPipeline.cpp` não mudou. Todo o código é compartilhado; vale para Windows, Linux e Web.
- Build incremental de `RangeEngine` e `RangeRuntime` sem erro. Falta o teste no jogo real (roadmap).

## 2026-09-26 - Release 0.4.3: pacote Windows (splash novo)

- So Windows; o Linux segue na 0.4.2. Muda o splash (embutido no `RangeEngine.exe` via `datatoc`) e os addons
  `ant_landscape`/`io_export_after_effects` (`is <numero>` -> `==`).
- Montado na maquina AMD, sem CUDA Toolkit: `build/bin` daqui nao tem cubins. Os 8 cubins
  (`kernel_`/`filter_sm_75/86/89/120`) vieram do zip 0.4.2, com o codigo dos kernels sem mudanca desde entao.
  A lista de arquivos do zip 0.4.2 serviu de referencia: 4.657 arquivos, os mesmos.
- **`blender.crt.manifest` desta maquina estava errado:** o CMake o regenerou em 12/09 com hashes de DLLs
  `api-ms-win-*` de outro SDK, mas as DLLs da `build/bin/blender.crt/` sao de abril (40 de 49 hashes nao
  batiam, e faltavam 5 DLLs no manifesto). O pacote usa o manifesto da 0.4.2, cujos 54 hashes batem com as
  DLLs. Conferir isso antes de empacotar em qualquer maquina.
- Validado extraindo o zip: `RangeEngine -b` sai com 0, Cycles lista CPU e OpenCL (RX 6800M), `RangeRuntime`
  roda um `.range`. A extracao falhou num caminho muito longo (pasta temporaria funda, arquivo `.cl` do Cycles
  com nome grande); em caminho curto extrai tudo. A nota do release recomenda caminho curto.

## 2026-09-26 - Docs: checagem automatica e guia para contribuir

- `tools/check_docs.py`: confere links locais, referencias `arquivo:linha` (arquivo existe e tem a linha) e os
  mapas de codigo (metodo ainda perto da linha citada, tamanho do arquivo). Sai com 1 em erro; `--fix` grava
  linhas, tamanhos e o `HEAD` conferido nos mapas. Na primeira rodada achou 1 link quebrado
  (`ketsji-engine-modernization-plan.md` apontava para um relatorio externo nunca versionado) e 5 tamanhos
  com 1 linha a mais (o script antigo contava a linha vazia final).
- `CONTRIBUTING.md` e `.github/ISSUE_TEMPLATE/bug_report.yml`: o modelo de bug pede versao, sistema, placa de
  video/driver e dispositivo do Cycles.

## 2026-09-26 - Docs: arquitetura atualizada para o estado atual

- `architecture.md`: mapa do repositório, loop Web (`emscripten_set_main_loop_arg`), caminho editor → `.blend`
  → conversor, export Web/Android em `range_web`, Cycles, `m_debugRenderer` e linha do `main()` corrigida.
- `code-map-*.md`: números de linha e tamanhos reconferidos com o código; índices `local-knowledge/index-*.md`
  regerados. Resumos de IA local marcados como não revisados (tinham "UPBGE = Unreal ...").
- `maintenance-guide.md`: stubs do player, GLSL ES da Web e traduções de texto novo. `docs/README.md` com
  ordem de leitura e sem o link para o inexistente `vehicle-test-guide.md`.

## 2026-09-27 - Release 0.4.2: pacote Windows

- `AnastacioEngine-0.4.2-windows-x64.zip` (159 MB) e `.sha256` anexados a `v0.4.2`, que ate entao so tinha o
  pacote Linux. Feito na maquina NVIDIA (CUDA 13.4): cubins sm_75/86/89/120 dentro de
  `2.79/scripts/addons/cycles/lib/`; Embree e OpenCL ligados.
- Montado conforme `distribution-0.1.md`: `blender.crt/` + so `ucrtbase.dll` solto, sem `.pdb`/`.lib`/`.map`
  de build, `datatoc`/`makes*`, logs, `demos/`, `rangearmor/` e `imgui.ini`. RangeArmor sem versao nova.
- Copia extraida numa pasta limpa: render Cycles em `-b` com CUDA (RTX 5060 Laptop) OK; `RangeRuntime.exe`
  abre um `.blend` de jogo e roda sem crash.
- Pegadinha: com o notebook fora da tomada a RTX 5060 some (Cycles lista so a CPU e `nvidia-smi` falha com
  "insufficient permissions"). Ligar a fonte antes de testar CUDA.

## 2026-09-26 - Windows: Cycles OpenCL testado na AMD

- Maquina AMD (RX 6800M + Radeon integrada do Ryzen 9 5900HX), preset `v142-ninja` sem CUDA Toolkit: o
  configure desliga os cubins sozinho e o CUDA fica so por dynload.
- O RX 6800M aparece duas vezes na lista (mesmo PCI `03:00.0`, a segunda com `_ID_2`): cada GPU tem seu
  driver AMD (32.0.21045 e 31.0.21923), cada um registra um `amdocl64.dll` e os dois enxergam o 6800M.
  Marcar so uma entrada.
- Usuario confirmou render com GPU (OpenCL) pela interface.
- Render em `-b` (cena padrao, 128 amostras, 50%): 1a vez 24,5 s (compila ~9 kernels split), depois 7,7 s;
  CPU 1,4 s com os tiles padrao.
- Bake de AO (chao sob cubo) com OpenCL: mesmos valores da CPU (min/max/media); 0,79 s contra 0,26 s depois
  de compilar o kernel `bake` (28 s na 1a vez). O bake imprime `Split kernel error: failed to load
  kernel_path_init`, sem efeito no resultado.

## 2026-09-26 - Cycles: cubins CUDA para RTX 20/30/40/50

- Preset `v142-ninja`: `CYCLES_CUDA_BINARIES_ARCH=sm_75;sm_86;sm_89;sm_120` (sm_75 e o minimo do CUDA 13).
  Cada arch leva ~12 min e ~9 MB (sm_120 ~28 MB). So sm_120 testado em hardware real (RTX 5060).
- Removidos de `build/bin/.../cycles/lib` cubins antigos de 2023 (sm_30 a sm_70), sobras de outro build.

## 2026-09-26 - Windows: Cycles com CUDA no build principal

- Preset `v142-ninja` liga Cycles com Embree, CUDA (binarios `sm_120`) e OpenCL no `build/`.
- CUDA 13.0 nao aceita o MSVC 14.51 do VS 18; instalado o CUDA 13.4 em `D:` (o instalador so deixa escolher
  a unidade sem versao anterior instalada). Cache reapontado com `cmake -U "CUDA_*" -DCUDA_TOOLKIT_ROOT_DIR=...`.
- O nvcc 13 usa C++20 por padrao e a STL do MSVC 14.5x da static_assert (`aligned_storage`, `result_of`);
  `-std=c++17` adicionado aos flags do kernel.
- `kernel_sm_120.cubin` nao e dependencia do `RangeEngine`: compilar `cycles_kernel_cuda` antes.
- Teste: `RangeEngine -b` renderiza a cena padrao na RTX 5060 com os kernels pre-compilados (512 amostras,
  7,1 s).
- Usuario confirmou render com GPU (CUDA) pela interface do editor.
- Bake de AO (chao sob cubo) com CUDA: mesmos valores da CPU (min/max/media), 0,86 s contra 1,80 s.
- Addons `ant_landscape` e `io_export_after_effects`: `is <numero>` trocado por `==` (SyntaxWarning no Python 3.11).

## 2026-09-26 - Linux: pacote testado em maquina limpa

- Teste num container Ubuntu 24.04 minimo (`ubuntu-base` + `unshare`, sem Docker nem sudo); roteiro em
  `docs/linux-build.md`.
- Defeito: `package-runtime.sh` punha a stdlib em `python311/lib`, mas o executavel procura em
  `<versao>/python`. Sem `/opt/anastacio-python311` o Python falhava com `No module named 'encodings'`,
  e isso afeta o 0.4.1 publicado. O script agora copia para `2.79/python`, garante o libpython em `lib/`,
  confere a stdlib e tira `datatoc`, `makesdna`, `makesrna`, `msgfmt` e `imgui.ini` do pacote.
- Depois da correcao: `RangeEngine -b` renderiza a cena de teste com Cycles e o `RangeRuntime` acha o
  Python embutido. As bibliotecas do sistema continuam fora do pacote; a lista de pacotes de runtime esta
  em `linux-build.md`.

## 2026-09-26 - Linux: i18n validado no editor

- `build-linux-editor/` com `WITH_INTERNATIONAL=ON`: `engine_i18n.py` 36 ok (pt_BR, es, ru_RU; catalogo do
  Blender e dicionarios da Range). Os `blender.mo` saem em `bin/2.79/datafiles/locale/`, e o
  `package-runtime.sh` copia o `bin` inteiro. Pela janela, o usuario trocou o idioma para pt_BR e conferiu
  menus e acentos.
- Roadmap: removido o item "validar a janela real do `RangeEngine`"; o editor ja vinha sendo usado com janela
  no Linux (Cycles, Standalone, preferencias).

## 2026-09-26 - Cycles: Embree 4 e OpenCL no editor Linux

- Embree: o Ubuntu 24.04 so tem o Embree 4, e o Cycles era escrito para o 3. `FindEmbree.cmake` acha
  `embree4/rtcore.h` e a `libembree4` compartilhada; `intern/cycles/CMakeLists.txt` define `WITH_EMBREE4`
  (sem `EMBREE_STATIC_LIB`). No codigo, headers `embree4/`, `RTCRayQueryContext` no lugar de
  `RTCIntersectContext`, e `kernel_embree_intersect1`/`kernel_embree_occluded1` (`kernel/bvh/bvh_embree.h`)
  passam o contexto por `RTCIntersectArguments`/`RTCOccludedArguments`. O Embree 3 do Windows segue igual.
- `bvh_embree.cpp`: o bloco `RTC_VERSION >= 30900` (flags de vizinho das curvas lineares) usava uma variavel
  inexistente e tratava todo o cabelo como uma curva so; nunca tinha compilado. Reescrito com um flag por
  segmento, curva a curva.
- OpenCL: `cycles_device` nao linkava o `extern_clew`, e o `RangeRuntime` falhava com `clewInit` indefinido;
  agora linka quando `WITH_CYCLES_DEVICE_OPENCL`. Este Cycles so aceita OpenCL em GPUs AMD
  (`OpenCLInfo::device_supported`), entao a RTX 5060 nao aparece em OpenCL; nao foi testado em AMD.
- Preset `linux-editor`: `WITH_CYCLES_EMBREE=ON` e `WITH_CYCLES_DEVICE_OPENCL=ON`; `quickstart-editor.sh`
  instala `libembree-dev`. OSL continua desligado: sem pacote no Ubuntu 24.04 e esta versao espera OSL 1.9.
- Teste: cubo com 300 fios de cabelo e uma copia linkada, CPU, 32 amostras, Embree ligado e desligado: as
  duas imagens batem (diferenca media 0,03/255, so ruido de amostragem). Depois de instalar o `libembree-dev`
  do sistema, o usuario testou pela interface: Embree (Render > Performance > Use Embree) e CUDA (primeiro
  render recompilou o kernel sm_120) funcionando.

## 2026-09-26 - Cycles: CUDA na RTX 5060 (sm_120) com CUDA 13

- `kernel_config.h`: o kernel CUDA so conhecia arquiteturas ate 7.x e parava com "Unknown or unsupported CUDA
  architecture". Nova faixa 8.x a 12.x (Ampere a Blackwell) com os limites do 7.x e 16 blocos por SM.
- `util_math.h`: o CUDA 13 removeu o `saturate()` que o nvcc trazia pronto; agora e definido com `__saturatef`
  quando `__CUDACC_VER_MAJOR__ >= 13` (CUDA mais antigo segue usando o dele).
- Preset `linux-editor`: `WITH_CYCLES_DEVICE_CUDA=ON` e `WITH_CUDA_DYNLOAD=ON`. Sem dynload o CMake do player
  quebrava (`target_link_libraries(${target} ...)` com variavel indefinida; corrigido para `RangeRuntime`).
- Teste: render `-b` na GPU com CUDA 13.0: primeira compilacao do kernel ~4 min, depois o render sai em < 1 s
  e a imagem confere. As duas correcoes do kernel valem tambem para o Windows com CUDA 13 e placas 8.x+.

## 2026-09-26 - Cycles: um editor Linux so, com Cycles

O preset `linux-editor` passa a ter `WITH_CYCLES=ON` (so CPU; OSL, Embree, CUDA e OpenCL desligados) e a sandbox `build-linux-cycles/` deixa de existir. O menu de engine nao listava "Cycles Render": ele depende do add-on `cycles`, que o build sem Cycles remove das preferencias (`resources.c`), e nada o religava. Agora um build com Cycles faz `BKE_addon_ensure(&U.addons, "cycles")` no mesmo ponto. O `build-linux-editor/` antigo guardava no cache a deteccao do OpenEXR 2.0 e falhava em `ImathBox.h`; apagar as entradas `OPENEXR_*`/`IMATH_*` do cache resolveu. Teste: build ok; em `-b` com as preferencias do usuario o add-on carrega e `scene.cycles` existe; `cycles-smoke-render.py` a 64 amostras renderiza certo. Pela interface, o usuario renderizou com F12 e com a viewport em Rendered.

No mesmo preset, `WITH_PLAYER=ON`: o botao Standalone do editor Linux dava "Player path ... RangeRuntime not found", porque o runtime so saia no `build-linux/`. Ligar o player no build do editor quebrava o link com dezenas de simbolos (`CLG_*`, `build_*`, `BKE_autotrack_*`, `LA_BlenderLauncher`...): as libs do editor entravam como dependencias transitivas depois do `--end-group`. `blenderplayer/CMakeLists.txt` agora poe `BLENDER_LINK_LIBS` dentro do grupo no Linux, e o stub `builtin_keyingsets` em `stubs.c` ganhou o mesmo `#ifndef WITH_BLENDER` dos outros stubs com versao real. Teste: build ok; `RangeRuntime pbr_variants.blend` abre com OpenGL 4.6 sem erros. `RangeRuntime` sem argumentos da segfault tambem no `build-linux/`, entao o bug ja existia antes (nao investigado).

## 2026-09-26 - Cycles: editor Linux renderiza com Cycles (CPU)

Sandbox `build-linux-cycles/` = preset `linux-editor` com `WITH_CYCLES=ON` (sem OSL, Embree, CUDA e OpenCL). O `RangeEngine` nao linkava: faltavam os simbolos `google::*` (glog/gflags) usados por `util_logging.cpp`, `blender_python.cpp` e outros. `cycles_util` nao declarava essa dependencia; no MSVC a ordem das `.lib` nao importa, mas o `ld` do Linux resolve estaticas na ordem. `intern/cycles/util/CMakeLists.txt` agora poe `${GLOG_LIBRARIES}`/`${GFLAGS_LIBRARIES}` no `LIB` quando `WITH_CYCLES_LOGGING`. Teste: `tools/linux/cycles-smoke-render.py` (esfera, chao, lampada pontual) em modo `-b`; `--debug-cycles` confirma sessao, device CPU com 16 threads e BVH8; 1 amostra sai com ruido e 128 amostras sai limpa com sombra e rebatimento de cor (0,7 s). GTest do Cycles recompilado: 177/177. Falta abrir o editor com janela e renderizar pela interface (F12 e viewport em modo Rendered), e testar CUDA na NVIDIA desta maquina.

## 2026-09-26 - Cycles: testes GTest validados no Linux

`GTestTesting.cmake`: o bloco `UNIX AND NOT APPLE` linkava `bf_intern_libc_compat` em `${TARGET_NAME}` (variavel inexistente), o que quebrava a configuracao de qualquer teste no Linux; agora usa `${NAME}_test`. No Windows o bloco nao roda, por isso passou. Build separado `build-linux-gtest/` com `WITH_CYCLES=ON` e `WITH_GTESTS=ON` (sem OSL/Embree/CUDA/OpenCL); faltavam `libopenexr-dev`, `libpugixml-dev` e `libtiff-dev`, e no OpenEXR 3.1 foi preciso apontar `OPENEXR_HALF_LIBRARY` para `libImath.so` e `OPENEXR_ILMIMF_LIBRARY` para `libOpenEXR.so`. O codigo compilou sem ajustes. Teste: 10 binarios `cycles_*_test`, 177/177 passando (graph_finalize 61, util_path 41, util_string 38, util_ies 13, util_image 8, util_time 5, render_tile 4, render_light_ies 3, util_task 2, util_aligned_malloc 2). Receita em `docs/linux-build.md`. O editor com Cycles esta na entrada acima.

## 2026-09-26 - Themes > Global Theme: UI atualiza numa etapa só

`rna_userdef.c`: marcar "User Interface" em Copy Global Theme To fazia `tui = tglobal_ui`, mas no `tglobal_ui` só o `wcol_regular` tinha a cor global; os outros widgets (`wcol_tool`, `wcol_num`, `wcol_option`...) ficavam com a cópia antiga. O resto só atualizava ao mexer num valor de "All Widget Colors" (Roundness, Shade...), que espalhava o `wcol_regular` por todos os widgets. Os "Widget State Colors" globais nunca propagavam sozinhos. Agora os dois caminhos (e o `wcol_state`) usam `rna_theme_global_ui_apply`, que espalha o `wcol_regular` por todos os widgets do `tglobal_ui` e copia para o `tui`. Teste: build ok; script em modo batch: com a caixa desmarcada, muda cor, Roundness e state color globais; ao marcar, `wcol_num`/`wcol_option` e `wcol_state` já saem iguais ao global, e mudar uma state color depois também propaga. Falta conferir o visual no editor.

## 2026-09-26 - Text Editor: barra lateral em painéis

`space_text.py`: a sidebar (N) virou os painéis View (Line Numbers / Word Wrap / Syntax Highlight como ícones numa linha, Highlight Line), subpainel Margin (fechado, `bl_parent_id`), Editor (Font Size, Tab Width, Tabs as Spaces, Live Edit) e Find & Replace (campos com conta-gotas ao lado, opções numa linha). Nenhuma opção removida. O cabeçalho continua forçando as três opções de View ligadas a cada redesenho (comportamento antigo). Teste: registro dos painéis em modo batch e conferido pelo usuário no editor.

## 2026-09-26 - Outliner: pasta "fora do jogo" (layer 20) e Group a partir da coleção

Primeira ligação das coleções com o jogo, sobre o sistema de layers (não é a reescrita do Blender 2.8, que trocaria layers, Groups e o conversor do BGE).

- **Caixa "In game"** à esquerda do olho em cada pasta (como o exclude do 2.8), também em Collection > Toggle Not in Game (`outliner.collection_game_exclude`). Desmarcada (`SCECOL_GAME_EXCLUDE`), os objetos da pasta, das subpastas e os filhos deles vão para o layer 20 (`SCECOL_GAME_LAYER`) e começam **inativos** no jogo, prontos para o Add Object. O layer anterior fica em `Base.collection_lay` (era `pad`) e volta quando a caixa é marcada de novo ou o objeto sai da pasta.
- **Layer 20 visível no editor:** ao desmarcar, o layer 20 é ligado na cena para os objetos não sumirem. O conversor (`BL_BlenderDataConversion.cpp`) tira o layer 20 dos layers ativos sempre que a cena tem alguma pasta fora do jogo, então o que for posto nele à mão também começa inativo nesse caso.
- **Sincronia:** `BKE_scene_collections_game_sync` roda em toda operação de pasta (mover, arrastar, apagar) e no início do jogo pelo editor (pega objetos que ganharam pai depois).
- **Create Group from Collection** (`outliner.collection_to_group`): cria um Group com o nome da pasta e os objetos mostrados nela, para instância de grupo.
- **Cabeçalho:** o botão de nova coleção passou para o lado do menu Collection.
- **Teste:** build ok. Script no editor: Cube na pasta, desmarca → layer 20 e layer 20 da cena ligado; marca → volta ao layer 1; Group "Collection" com o Cube; salvar e reabrir mantém o layer 20. Conferido pelo usuário no editor.

## 2026-09-25 - Outliner: coleções só para organizar (sem Group, sem mudar parent)

Pastas no modo Current Scene do Outliner, parecidas com as coleções do Blender 2.8, mas **só organizacionais**: não mudam parent, camadas, Groups nem nada no jogo.

- **Dados:** `SceneCollection` (nome, `uid`, subcoleções) em `Scene.collections`. `Base.collection_uid` diz a pasta de cada objeto (0 = raiz). Usa uid e não ponteiro, então cópia de cena, apagar objeto e undo não precisam de remapeamento. Arquivos antigos abrem com tudo na raiz. Funções em `scene.c` (`BKE_scene_collection_*`), leitura/escrita em `readfile.c`/`writefile.c`.
- **Árvore:** elemento `TSE_SCENE_COLLECTION` (id = cena, nr = uid, para o aberto/fechado persistir). Os objetos raiz entram na pasta depois de `outliner_make_hierarchy`, ou seja, **filho sempre aparece sob o pai**, e a coleção só vale para objetos sem pai. Ao mover um objeto, os descendentes recebem a mesma coleção.
- **Botões olho/seleção/render** da pasta aplicam a todos os objetos mostrados dentro (filhos e subcoleções inclusos).
- **Operadores:** `outliner.collection_new` (dentro da pasta selecionada), `collection_delete` (objetos e subpastas sobem para o pai), `collection_objects_select`, `collection_move_objects` (menu; também em "Move to Collection" no menu de contexto do objeto). Arrastar objeto para pasta ou para a área vazia (raiz), arrastar o ícone da pasta para dentro de outra ou para a raiz. Duplo clique renomeia (nome único na cena). Menu **Collection** e botão de nova pasta no cabeçalho do Outliner.
- **Stub:** `WM_menu_name_call` acrescentado a `blenderplayer/bad_level_call_stubs/stubs.c`; sem ele o `RangeRuntime` não linkava.
- **Teste:** build limpo de `RangeEngine` e `RangeRuntime` ok; `tools/arquivo_upbge.blend` abre com o `Base` novo. Falta teste no editor.
- **Também em All Scenes** (modo padrão do `startup.blend`; antes as pastas só existiam em Current Scene e nada aparecia): pastas dentro de cada cena, operadores e arrastar usam a cena da pasta (o drop de pasta leva o nome da cena na propriedade `scene`). Botão de nova coleção no canto direito do cabeçalho, como no Blender 2.8. Teste: build ok; `outliner.collection_new` em All Scenes no `startup.blend` (batch) cria a pasta.

## 2026-09-25 - Compatibilidade UPBGE: logic bricks revisados; corrige estouro na cor do sensor

Comparado `tools/upbge-0.2.5b-source` com a Range (DNA, RNA e `BL_Convert*` de sensores, controladores e atuadores; API Python de `GameLogic`).

- **Corrigido:** `blo_do_versions_range()` copiava 4 bytes (`copy_v4_v4_uchar`) para `bSensor.color[3]`, o último campo da struct (200 bytes): 1 byte escrito fora do bloco em todo sensor de arquivo UPBGE aberto. Agora `copy_v3_v3_char`.
- **Já compatível, sem ação:** fora o Mouse Sensor (migrado em `32f66eef`), a Range só acrescentou valores de enum e flags (2D Filter 14-19, `ACT_OBJECT_NORMAL_SET`, `ACT_EDOB_CHANGE_COLOR`, `ACT_EDOB_ADD_FROM_PROP`/`_PROP_GLOBAL`, `SENS_ANIMATIONEVENT`, `SENS_DELTATIME`/`SENS_SHOW_DESCR`); campos novos lidos como zero mantêm o comportamento antigo (Delay `repeat_times`/`use_delta`, `use_dt`, `debug` de Near/Radar/Ray, runtime do Property Sensor/Actuator, `saveloc`/`extension_name`). Atributos Python de `SCA_PythonKeyboard/Mouse/Joystick` continuam existindo em `Ketsji/KX_Python*`.
- **Teclas:** `wm_event_types.h` do UPBGE 0.2.5b é idêntico ao da Range; Keyboard Sensors antigos não precisam de migração. (`Ketsji` e `windowmanager` do UPBGE v0.2.5b copiados do GitHub para `tools/upbge-0.2.5b-source`, que é ignorado pelo git.)
- **Save/Load globalDict (Game Actuator e `logic.save/loadGlobalDict`):** o UPBGE gravava `jogo.bgeconf`, a Range grava `jogo.save`. `pathGamePythonConfig` agora tira `.blend` como já tirava `.range` (antes: `jogo.blend.save`), e `loadGamePythonConfig` lê `jogo.bgeconf` quando não há `.save` e não há nome/extensão próprios; o próximo save vai para o `.save`. Corrigido também o nome de save próprio (`saveloc`), que cortava o caminho com `sizeof` de ponteiro/array em vez do tamanho do nome do arquivo.
- **Teste:** `RangeEngine -b tools/arquivo_upbge.blend`: 8 Mouse Sensors com tipos corretos (wheel up/down, movement), cor aplicada, sem aviso de memória. `RangeRuntime` com `.blend` + `.bgeconf` (marshal) e `loadGlobalDict()`: `globalDict` carregado.

## 2026-09-25 - startup.blend de fábrica atualizado

- `source/release/datafiles/startup.blend` substituído pelo `startup.blend` salvo por Fabio pela UI (`%APPDATA%\RangeEngine\Blender\2.79\config\startup.blend`). O anterior ficou em `startup.blend1`.
- Screens: Asset Browser, Game Dev, Game Play, Script (antes só Game Dev e Game Play). Texto embutido `03_jogador_celular.py` no lugar de `02_component_properties.py`. Objetos e imagens empacotadas iguais aos de antes.
- **Teste:** `RangeEngine -b --factory-startup` lista as 4 screens e o texto novo. `RangeEngine` e `RangeRuntime` compilam.

## 2026-09-25 - Screens: Ctrl+Seta parava de navegar depois de apagar uma screen

- **Sintoma:** ao apagar uma screen (ex.: "Game Play") e criar outra pelo **+**, Ctrl+→/← deixava de trocar de screen, sem erro.
- **Causa:** as abas de screen (`uiTemplateScreenTabs`) chamam `SCREEN_OT_screen_set` com `screen_name`. Essa propriedade era guardada como "last properties" e os itens de keymap Ctrl+→/← a recarregavam. Com `screen_name` preenchido, o operador vai para a screen com esse nome e ignora `delta`. Enquanto a screen existia, isso parecia navegação normal. Depois de apagada, o nome não achava nada e o operador era cancelado.
- **Correção:** `screen_name` e `delta` agora têm `PROP_SKIP_SAVE` em `screen_ops.c`.
- A remoção da screen estava correta: o `screen delete 0000000000000000` no log `wm.event` aparece só porque a referência do notifier é zerada quando o ID é liberado.
- **Teste:** RangeEngine com `--log "wm.*"`. Depois de apagar a screen, criar outra e clicar numa aba, Ctrl+→ gera `screen_set(delta=1)` e troca de screen (confirmado pelo usuário).

## 2026-09-25 - Asset Browser (modo Assets do File Browser, arrastar para a Vista 3D)

Feito como no Blender: o File Browser ganhou um modo de navegação (`SpaceFile.browse_mode`, DNA novo), sem editor novo.

- **Como abrir:** entrada "Asset Browser" no menu de tipo de editor (subtipo no `EditorTypeItem` de `area.c`, valor `tipo | subtipo << 8`), ou Window > Asset Browser, que abre uma janela flutuante (`SCREEN_OT_asset_browser_show`, tipo `WM_WINDOW_ASSETS` em `WM_window_open_temp`).
- **Modo Assets:** lista o conteúdo dos `.blend` da pasta em vista plana (`FILE_LOADLIB`, recursão 1), só Objects, Groups e Materials, em miniaturas. `ED_fileselect_browse_mode_params_ensure` impõe esses parâmetros a cada refresh, e a lista é recriada quando o tipo dela (`filelist_type_get`) não bate. Um diálogo de arquivo aberto na área (`sfile->op`) sempre ganha do modo Assets.
- **Bibliotecas:** nova categoria do fsmenu, gravada na seção `[AssetLibraries]` do `bookmarks.txt`. Operadores `file.asset_library_add` (pasta atual ou `directory`; dentro de um `.blend` usa a pasta dele) e `file.asset_library_remove`. RNA: `asset_libraries` / `asset_libraries_active`.
- **Arrastar para a Vista 3D:** `VIEW3D_OT_asset_drop` faz append ou link e põe o objeto ou grupo no ponto do drop. Material vai para o objeto sob o cursor (ou o ativo). Duplo clique no asset (`file.asset_add`) adiciona no cursor 3D. O botão Append/Link (`params.use_link`) vale para Groups e Materials; Objects são sempre append. No modo Assets, só itens de asset podem ser arrastados; new folder, rename e delete ficam bloqueados.
- **Previews:** `file.asset_previews_generate` roda o `wm.previews_batch_generate` em todos os `.blend` da biblioteca, sem diálogo (botão "Generate Previews" no painel Asset Libraries).
- **UI Python:** header próprio do modo Assets (View, pai/refresh, tipo de vista, Append/Link, filtros Object/Group/Material, busca). Painéis Asset Libraries e Folder na aba Assets. Os painéis de Bookmarks e o Advanced Filter só aparecem no modo Files.
- **Limitação do 2.79:** ao dar append num objeto filho, o pai não vem junto (`expand_object` não expande `ob->parent`).
- **Testes automatizados** (scratchpad, `-b` e GUI com timer):
  - drop de objeto, grupo e material (append e link) e os erros esperados;
  - troca de modo, adicionar e remover biblioteca (o `bookmarks.txt` fica limpo);
  - desenho da UI sem erro de Python;
  - janela flutuante abre em modo Assets;
  - previews 128×128 gerados para os 5 assets da biblioteca de teste.
  - `RangeEngine` e `RangeRuntime` compilam.

## 2026-09-25 - Material: Subsurface Scattering no modo jogo

- O SSS do GLSL (`set_sss`) lê só Enabled, Scale e RGB Radius; a tonalidade vem da cor Diffuse.
- Painel no modo jogo: presets escondidos (calibrados para o render e mudam o Color, que o jogo ignora);
  RGB Radius exibido pela nova propriedade RNA `game_radius` (mesmo campo `sss_radius`, sem unidade "m").
- Shader: Scale <= 0 é tratado como 0.001, evitando divisão por zero no `pow` (pixels pretos/NaN).
- Lâmpadas com Diffuse desligado não somam mais SSS (antes somavam). Única mudança visual possível em cenas antigas.
- Removida a função morta `set_sss2` do GLSL. Dica do `game_radius` traduzida (pt_BR/es/ru).
- Teste: `.blend` com SSS, Scale 0, lâmpada Point e Sun sem Diffuse roda no RangeRuntime sem erro de shader.

## 2026-09-25 - Material: painel Options do modo jogo

Só interface e textos, sem mudar como o jogo desenha nem o que o `.blend` guarda:

- Escondidos no modo jogo, porque o motor não lê: `Invert Z Depth` (`MA_ZINV`, só `zbuf.c`) e `Light Group Exclusive` (`MA_GROUP_NOLAY`, só `convertblender.c`). Continuam no painel do render antigo.
- Light Group/Local ficavam cinza em todo material que não fosse Halo: o `sub.active` do Point Size pegava a coluna inteira. Agora "Halo Options" só aparece em material Halo.
- Z Offset não fica mais cinza sem Z Transparency: o jogo aplica o offset em qualquer material (`KX_BlenderMaterial`, `SetPolygonOffset`).
- Aviso quando Geometry Instancing e GPU Skinning estão ligados juntos (`BL_BlenderShader::UseInstancing` desliga o instancing nesse caso).
- Tooltips no RNA de `offset_z`, `pass_index` (chega ao shader pelo nó Object Info) e `use_full_sky` (só com céu Atmospheric e sem textura de ambiente), com traduções PT-BR/ES/RU.

## 2026-09-25 - Material: painel Transparency do modo jogo

Só interface e textos, sem mudar como o jogo desenha nem o que o `.blend` guarda. O painel agora mostra o que o motor faz de fato (`KX_BlenderMaterial`, `RAS_BucketManager`, `gpu_material.c`):

- `Alpha Blend` (Game Settings) aparece no topo, como "Blend". É ele que escolhe a passada de render (sólida ou alpha, com ou sem ordenação). Z Transparency só transforma um Opaque em Alpha Blend sem ordenação; Mask/Raytrace não. Com Enabled + Mask/Raytrace + Opaque o material é misturado na passada sólida, sem ordenar e gravando profundidade. O painel avisa essa combinação.
- Alpha fica ativo também com Enabled desligado quando Blend não é Opaque (o alpha chega ao shader nesse caso). Specular só fica ativo com Z/Raytrace e sem Shadeless, que é quando `alpha_spec_correction` é aplicado.
- Depth Transparency: checkbox primeiro e o fator renomeado para "Fade Distance" (é uma distância em unidades da cena), ativo só com Enabled e um modo com mistura (Alpha, Add, Sort). Fora disso, avisa que não tem efeito. Com Enabled desligado e Blend ligado, o motor ainda copia a textura de profundidade todo frame sem usar.
- Tooltips de `use_depth_transparency`/`depth_transp_factor` corrigidos no RNA, com traduções PT-BR/ES/RU.
- Não mexido, anotado: a pré-passada de profundidade para Clip/Alpha to Coverage (`ALPHA_DEPTH_CUTOUT_BUCKET`) nunca roda, porque esses materiais não passam em `IsAlpha()` e vão para o bucket sólido.

## 2026-09-25 - Material: Shader Sources (Vertex/Fragment GLSL)

- `library_query.c`: `Material.vertcode`/`fragcode` (os Texts de `script_vert`/`script_frag`) não eram percorridos por `BKE_library_foreach_ID_link`, e `ID_MA` não declarava uso de `ID_TXT`. Apagar o Text usado como shader deixava o material com um ponteiro para memória liberada, e a próxima compilação chamava `txt_to_buf()` nele. Agora os dois ponteiros são registrados com `IDWALK_CB_NOP`, a mesma convenção do RNA, que não conta usuários de Text. Teste em background: remover o Text zera `script_vert` no material e na cópia, `users` fica estável na cópia/remoção e save/reload está correto.
- Vazamentos: os buffers de `txt_to_buf()` eram liberados dentro do codegen, e não eram liberados quando o material não tinha saída (`used == false`) nem no vertex de material do tipo World. Agora `gpu_material_construct_end` libera os dois depois de `GPU_generate_pass`, e `code_generate_fragment`/`vertex` recebem `const char *`.
- Painel Shading: "Vertex:/Fragment:" eram alinhados aos campos por `separator(factor=3.2)`, o que desalinhava com outra escala de UI. Agora é uma linha por par (`split`) com `template_ID` (botões New/Open, que já atribuem o Text ao campo). A seção não fica mais cinza com Shadeless, porque o GLSL do usuário é aplicado antes do ramo Shadeless em `GPU_shaderesult_set`.
- Pendente: editar o texto do shader não recompila o material; é preciso reatribuir o Text.

## 2026-09-25 - Custom Viewport da câmera

- Camera Presets (lista de câmeras reais) escondidos no Range Engine; Size e Fit do sensor continuam visíveis porque definem o FOV no jogo (`RAS_FramingManager::ComputeFrustum`).
- Range Engine: o tipo da câmera mostra só Perspective/Orthographic (o conversor trata qualquer tipo que não seja `CAM_PERSP` como ortográfico) e avisa se a câmera já estiver em Panoramic. Com Stereo ligado no jogo, o painel Camera mostra "Focal Distance" (`dof_distance`, usado por `RAS_Rasterizer::GetFrustumMatrix`; 0 = 30 × Eye Separation), que tinha ficado inacessível ao esconder o Depth of Field. Display e Safe Areas continuam: não afetam o jogo, mas ajudam a enquadrar a câmera no editor.
- O viewport em pixels era calculado uma única vez na conversão, a partir do tamanho visível do canvas. Com isso, ficava errado depois de redimensionar a janela, com a escala de resolução dinâmica (o render usa `GetRenderWidth`) e no estéreo. Agora `KX_Camera` guarda os ratios (`RAS_CameraData::m_viewportRatios`), e `UpdateViewport()` resolve o retângulo a cada frame, contra a área de render daquele frame e olho, invalidando a projeção só quando ele muda. `setViewport()` do Python continua em pixels fixos.
- Os ratios são carregados mesmo com o viewport desligado, então `useViewport = True` pelo Python usa os valores do editor em vez de um retângulo 0x0.
- Ratios iguais (largura ou altura zero) passam a ser tratados como inválidos, igual aos invertidos.
- RNA: `use_viewport` tinha nome e tooltip copiados de "Show Frustum"; os ratios agora ficam limitados a 0..1. O painel avisa quando Left/Bottom não é menor que Right/Top.
- Painel Custom Viewport redesenhado: caixa de presets (Full Screen, Picture-in-Picture, metades Left/Right/Top/Bottom e os 4 quadrantes) pelo novo operador `camera.game_viewport_preset` (`bl_operators/camera.py`); ratios em pares Horizontal (Left/Right) e Vertical (Bottom/Top); linha "Result" com o tamanho em pixels na resolução do jogo, com o mesmo arredondamento do motor. Traduções em PT-BR, ES e RU.

## 2026-09-25 - Aba Camera em painéis nativos

- `properties_data_camera.py`: as seções deixaram de ser botões de expansão dentro de um único painel e viraram painéis com a seta nativa. Camera (aberto) reúne Lens, Shift & Clipping e Sensor; Depth of Field, Display, Safe Areas, Culling & LOD (Game: LOD, Culling, Shadow Cascade Cache e Optimization Reference), Custom Viewport (Game) e Stereoscopy (Render com multiview) começam fechados.
- Safe Areas e Custom Viewport passaram o checkbox para dentro ("Enabled"). As propriedades `show_expanded_cam_*` deixaram de ser definidas; arquivos que as tenham guardam só IDProperties sem uso.
- Traduções de "Lens:" e "Culling & LOD" em PT-BR, ES e RU. Registro conferido em `RangeEngine --background`.
- Depth of Field, Display e Safe Areas com o conteúdo em caixas com título. Depth of Field fica escondido no Range Engine (`BLENDER_GAME`): é só prévia do compositor do viewport (o High Quality pesa o editor) e o jogo não aplica o efeito; o runtime lê só `YF_dofdist` como distância focal do estéreo.

## 2026-09-25 - Painéis: Foliage próprio, checkbox dentro do conteúdo, Vehicle dividido

- `properties_material.py`: as opções de Foliage saíram de Game Settings para o painel `MATERIAL_PT_game_foliage` ("Foliage Shader", fechado por padrão), com o checkbox `use_foliage` no cabeçalho e duas caixas: Wind (Grass, Strength, Turbulence) e Optimization (Stop Beyond Distance, Wind Distance). As propriedades RNA não mudaram.
- `translations_ui.py`: "Wind:", "Optimization:" e "Stop Beyond Distance" em PT-BR, ES e RU.
- Aba Physics (Game): os painéis visíveis de Physics e Collision Bounds são os de `flowmenu/custom_pt_physics.py` (o `flowmenu` desregistra os de `properties_game.py`). Collision Bounds passou o checkbox para dentro ("Enabled") nas duas versões, e Create Obstacle também. Create Obstacle ganhou `bl_idname = "PHYSICS_PT_game_obstacle_create"`, para que arquivos com a posição antiga salva também o mostrem por último. O `flowmenu` e o addon `easy_ragdoll_RangeEngine` o re-registram depois dos próprios painéis, porque painel novo entra na ordem de registro (`BLI_addtail` em `rna_Panel_register`).
- Aba Vehicle dividida em painéis: Vehicle (checkbox "Enabled", Chassis: Steering Wheel e Center of Mass Offset), Engine (Drive Type e Power), Wheels, Gearbox e Player Component. Os painéis de ajuste só aparecem para Rigid Body/Dynamic e ficam apagados até o veículo ser ativado. Traduções dos textos novos em PT-BR, ES e RU.
- Registro em background (`RangeEngine --background`): todos os painéis novos registram sem erro e o id antigo `PHYSICS_PT_game_obstacles` não existe mais.
- Aba Material sem checkbox no título: Transparency (Render e Game), Mirror, Subsurface Scattering, Flare e Foliage Shader agora mostram o checkbox como primeira linha do conteúdo, com o texto "Enabled", e o restante fica apagado quando ele está desligado.

## 2026-09-25 - Foliage: correções do vento (Web, instancing, precisão, arquivos antigos)

- `gpu_shader_vertex.glsl`: `grass == 1` (float com int) não compilava em GLSL ES 3.00 (Web); agora `grass > 0.5`.
- O vento roda no espaço da malha, antes do instancing e do skinning. Antes rodava depois de `position *= instmat`, então em grama instanciada o corte `z < 0.1` comparava o Z do mundo e a base também balançava.
- Instancing nunca chamava `GPU_material_bind_uniforms()`, então `unfoliageparams` ficava zerado e folhagem instanciada não balançava. `GPU_material_bind()` agora envia os parâmetros para materiais com instancing. A distância do vento é testada no shader por instância (novo `unfoliagecamera`), e cada instância recebe fase de ruído própria (`ininstposition.xy`).
- Precisão: o tempo `time * turbulence` é reduzido com `fmod` para o período 256 no CPU, e o hash do ruído usa `mod(st, 256)`. A troca de período fica contínua, e o `sin` do hash não recebe mais valores enormes em sessões longas.
- Sem câmera ativa, `BL_BlenderShader::BindProg` passa `NULL` e o limite de distância é ignorado (antes media a partir da origem). A referência agora é definida antes do bind.
- `versioning_range.c`: arquivos sem `Material.foliage_distance` recebem 50 m. `foliage_distance <= 0` também desliga o limite, em vez de parar todo o vento.
- Build: `RangeRuntime` e `RangeEngine` compilados. Testado e aceito pelo usuário no desktop em 2026-09-25; o build Web ainda não foi testado (pendência no roadmap).
- Sem mudança: sombras (override shaders) não recebem o vento; normais não são recalculadas; corte seco no limite da distância.

## 2026-09-25 - Cycles OpenCL: validação funcional inicial na AMD

- `build_opencl_validate/` foi configurado isoladamente com `WITH_CYCLES_DEVICE_OPENCL=ON`; em modo serial, `cycles_kernel`, `cycles_device` e `RangeEngine` compilaram e linkaram. O `build/` principal não foi alterado.
- No executável isolado, `_cycles.get_device_types()` confirmou OpenCL ativo e `_cycles.available_devices('OPENCL')` enumerou a RX 6800M e a Radeon integrada. `_cycles.opencl_compile()` com zero argumentos e com índice não numérico retornou `False` e o processo terminou normalmente, validando CYC-006 nos dois casos exercitados.
- Permanecem pendentes apenas cenários de recurso alto/especiais: cópia OpenCL acima de 2 GiB (CYC-007) e a compilação em processo separado com caminho/nome contendo apóstrofo, barra e quebra de linha (CYC-010).

| Arquivo | Datas | Entradas | Tamanho |
|---|---|---|---|
| [este arquivo](changelog.md) (entradas recentes) | 2026-09-25 a 2026-09-25 | 33 | 42 KB |
| [13_2026-09-24_a_2026-09-24.md](changelog/13_2026-09-24_a_2026-09-24.md) | 2026-09-24 a 2026-09-24 | 22 | 30 KB |
| [12_2026-09-23_a_2026-09-23.md](changelog/12_2026-09-23_a_2026-09-23.md) | 2026-09-23 a 2026-09-23 | 9 | 13 KB |
| [11_2026-09-22_a_2026-09-20.md](changelog/11_2026-09-22_a_2026-09-20.md) | 2026-09-22 a 2026-09-20 | 25 | 39 KB |
| [10_2026-09-20_a_2026-09-20.md](changelog/10_2026-09-20_a_2026-09-20.md) | 2026-09-20 a 2026-09-20 | 12 | 19 KB |
| [01_2026-09-20_a_2026-09-14.md](changelog/01_2026-09-20_a_2026-09-14.md) | 2026-09-20 a 2026-09-14 | 45 | 69 KB |
| [02_2026-09-14_a_2026-09-11.md](changelog/02_2026-09-14_a_2026-09-11.md) | 2026-09-14 a 2026-09-11 | 24 | 71 KB |
| [03_2026-09-12_a_2026-08-23.md](changelog/03_2026-09-12_a_2026-08-23.md) | 2026-09-12 a 2026-08-23 | 49 | 90 KB |
| [04_2026-08-24_a_2026-08-24.md](changelog/04_2026-08-24_a_2026-08-24.md) | 2026-08-24 a 2026-08-24 | 4 | 81 KB |
| [05_2026-08-25_a_2026-08-24.md](changelog/05_2026-08-25_a_2026-08-24.md) | 2026-08-25 a 2026-08-24 | 2 | 68 KB |
| [06_2026-08-31_a_2026-08-26.md](changelog/06_2026-08-31_a_2026-08-26.md) | 2026-08-31 a 2026-08-26 | 7 | 71 KB |
| [07_2026-09-02_a_2026-08-31.md](changelog/07_2026-09-02_a_2026-08-31.md) | 2026-09-02 a 2026-08-31 | 23 | 69 KB |
| [08_2026-09-06_a_2026-09-02.md](changelog/08_2026-09-06_a_2026-09-02.md) | 2026-09-06 a 2026-09-02 | 26 | 68 KB |
| [09_2026-09-17_a_2026-09-06.md](changelog/09_2026-09-17_a_2026-09-06.md) | 2026-09-17 a 2026-09-06 | 51 | 71 KB |

## 2026-09-25 - Cycles: upscale em `util_image_resize_pixels`

- `util/util_image_impl.h`: o ramo `scale_factor > 1` alocava a saída e deixava os pixels sem preencher (`TODO`). Agora interpola linearmente por eixo, mapeando centros de pixel e prendendo nas bordas; componentes são interpolados separadamente e o valor volta ao tipo de origem (`uchar`, `uint16_t`, `half`, `float`). Entrada vazia gera saída zerada.
- Imagem 2D (profundidade 1) continua com profundidade 1 no upscale; antes a conta dava profundidade `scale_factor` e transformaria a textura em volume. O downscale já resultava em 1 e não muda.
- O único chamador (`render/image.cpp`) só reduz escala, então o fluxo de render atual não muda; a correção vale para quem reutilizar a API.
- Teste novo `test/util_image_test.cpp` (8 casos: cópia com escala 1, downscale box, upscale 2D, gradiente linear, 4 componentes, escala 1,5 em volume, `uchar`, entrada vazia). Em `build_gtest/`: 8/8 com a correção; com o header anterior, os 6 casos de upscale falham. `cycles_render` recompila sem erro.
- Subdivisão (FVar, `ATTR_ELEMENT_VERTEX_MOTION`), CUDA e OpenCL não foram tocados.

## 2026-09-25 - Cycles: testes de regressão CPU para CYC-001 a CYC-005

- GTest do Cycles volta a configurar e linkar: `GTestTesting.cmake` apontava `WORKING_DIRECTORY` para o alvo `blender`, que não existe desde a troca para `RangeEngine`; o `CMakeLists.txt` de `intern/cycles/test` agora linka `PUGIXML_LIBRARIES` e `WEBP_LIBRARIES`, dependências do OpenImageIO que no Windows só chegavam via OSL/imbuf. Nada muda com `WITH_GTESTS=OFF`.
- Testes novos em `source/intern/cycles/test/`:
  - `util_path_test.cpp` (CYC-001/004): ida e volta de `path_write_binary()`/`path_read_binary()`, escrita em diretório retorna `false`, leitura de arquivo ausente ou vazio retorna `false` com vetor limpo, e `path_file_size()` devolve o sentinela `(size_t)-1`.
  - `util_ies_test.cpp` (CYC-002): contagens zero, negativas, acima de 4.096, grade acima de 1.048.576 e números que estouram `long` são rejeitados; tilt negativo ou acima do limite também; a grade máxima 4096×256 continua aceita; falha limpa um perfil carregado antes.
  - `render_tile_test.cpp` (CYC-003): `TileManager` em 65.536² calcula `total_pixel_samples` (com e sem denoising e com prévia progressiva) e `resolution_divider` = 1024 sem overflow.
  - `render_light_ies_test.cpp` (CYC-005): tabela de offsets de `device_update_ies()` com slot inválido (-1), slot removido no meio e slots finais descartados, usando device CPU.
- Validação em `build_gtest/` separado (cópia do cache de `build/` com `WITH_GTESTS=ON`): `cycles_util_path_test` 41/41, `cycles_util_ies_test` 13/13, `cycles_render_tile_test` 4/4, `cycles_render_light_ies_test` 3/3; o `cycles_render_graph_finalize_test` já existente também passa (61/61).
- Fora do alcance em CPU/memória comum: escrita parcial real (CYC-001, exige injeção de falha no `fwrite`), remoção do arquivo entre `fopen` e `stat` (CYC-004, o Windows não apaga arquivo aberto), alocação de `RenderBuffers` em 65.536² (CYC-003, dezenas de GiB) e soma de IES acima de `INT_MAX` (CYC-005, gigabytes de perfis). Esses ramos seguem validados só por leitura.
- CYC-011: `IESTextParser` agora termina o `vector<char>` com `'\0'` antes de usar `strstr`, `strtod` e `eof()`. Antes, um IES que terminasse no último número podia provocar leitura além do fim. O teste `valid_type_c_without_trailing_newline` cobre essa entrada válida sem quebra de linha final.

## 2026-09-25 - Cycles OpenCL: compilação externa aceita nomes e caminhos especiais

- A expressão Python usada pela compilação OpenCL separada deixou de usar string bruta e passou a serializar barras invertidas, apóstrofos e quebras de linha. Antes, o “escape” de apóstrofo não inseria barra em C++, tornando inválido o `--python-expr` para determinados nomes de dispositivo ou caminhos de cache.
- Validação: `opencl_util.cpp` recompilado no MSVC; o caminho `WITH_OPENCL` continua pendente de execução em build separado.

## 2026-09-25 - Cycles CUDA: carga de kernels e cópia de buffer grande (CYC-008, CYC-009); rede marcada como insegura

- CYC-008: `CUDADevice::load_kernels()` guardava o resultado dos dois módulos na mesma variável; um cubin de render com falha e um de filtro carregado retornavam `true` e levavam `reserve_local_memory()` a lançar kernel com `CUfunction` não inicializado. Agora a carga exige os dois módulos, e `reserve_local_memory()` para se a busca da função ou a ocupação falhar.
- CYC-009: `CUDADevice::mem_copy_from()` passa a multiplicar em `size_t` (mesmo padrão de CYC-007 no OpenCL); cópias de 2 GiB ou mais davam overflow de `int`.
- Revisão estática de `device_cuda.cpp`, `.cu` e `device_network.cpp`: o device de rede ficou registrado como não suportado e inseguro no `docs/relatorio-varredura-cycles.md` (não compila, trava sem `stop` e desreferencia nulo em erro de recepção; o protocolo não tem autenticação). `WITH_CYCLES_NETWORK` continua `OFF`. A falta de suporte a sm_80+ e a CUDA atual entrou como backlog de portabilidade.
- Validação: build separado `build_cuda/` com `WITH_CYCLES_DEVICE_CUDA=ON` e `WITH_CUDA_DYNLOAD=ON` (cuew, sem toolkit NVIDIA); `ninja cycles_device extern_cuew` compilou e linkou sem avisos em `device_cuda.cpp`. O `build/` compartilhado não foi tocado. Sem execução em GPU.

## 2026-09-25 - Cycles OpenCL: cópia de buffer preserva tamanhos grandes

- `OpenCLDevice::mem_copy_from()` agora converte para `size_t` antes de multiplicar elemento, linha, largura e altura. Antes, uma região acima de `INT_MAX` podia sofrer overflow de `int` e passar offset/tamanho incorretos a `clEnqueueReadBuffer()`.
- Validação: `opencl_split.cpp` recompilado no MSVC. A configuração vigente desativa OpenCL; a compilação e o teste do ramo `WITH_OPENCL` ficam pendentes para um build separado.

## 2026-09-25 - Cycles OpenCL: API de compilação rejeita argumentos inválidos

- `device_opencl_compile_kernel()` agora valida que `_cycles.opencl_compile()` recebeu exatamente seis parâmetros e converte o índice de dispositivo sem lançar exceção: texto vazio/não numérico, valor negativo e valor acima de `INT_MAX` retornam `false`. Antes, a entrada Python inválida podia acessar um vetor fora dos limites ou deixar `std::stoi()` encerrar o processo auxiliar de compilação.
- Validação: `opencl_util.cpp` recompilado no MSVC. O build vigente está com OpenCL desligado, então a execução do ramo `WITH_OPENCL` segue pendente de uma configuração própria com OpenCL habilitado.

## 2026-09-25 - Cycles: leitura binária e produtos largura × altura (CYC-004, CYC-003)

- CYC-004: `path_read_binary()` (`util/util_path.cpp`) não passa mais o `(size_t)-1` de `path_file_size()` (stat
  falhou depois do `fopen()`) para `vector::resize()`; retorna `false` com o vetor vazio, também quando o `fread()`
  lê menos bytes. Header inalterado.
- CYC-003: produtos de dimensão passam a `size_t`/`uint64_t`/`int64_t` antes de multiplicar: alocação e cópia do
  buffer em `render/buffers.cpp` (`size` e os laços de `get_denoising_pass_rect`/`get_pass_rect` viraram `size_t`;
  a média do passe Render Time divide em `double`), `get_divider`, contagem de pixel samples em `render/tile.cpp` e o
  vetor de pixels da tile em `blender/blender_session.cpp`. Com 65.536 × 65.536 (limite da RNA) o `int` estourava.
- Validação: os quatro `.obj` compilados no MSVC (compilação só desses objetos, para não pegar o trabalho em
  andamento do Codex no IES). Depois que o Codex terminou, `RangeEngine` relinkado com todo o Cycles e render de
  teste (320×240, 16 amostras, tiles 64×64, cena padrão): saída idêntica pixel a pixel à do binário anterior.

## 2026-09-25 - Sensor Actuator detecta actuators de disparo único

- `SCA_ActuatorSensor::Evaluate` só olhava `IsActive()` no início do frame seguinte. Actuators que ativam e
  desativam no mesmo frame (Property, Message, Add Object, Scene, Game...) já estavam inativos nesse momento, e o
  sensor disparava com `positive=0` (nunca ficava positivo; um AND ligado a ele não fazia nada). O `m_midresult`
  gravado em `Update()` era descartado. Agora o resultado é `IsActive() || m_midresult`, e o `Init` zera o
  `m_midresult`. Código igual ao do Blender/UPBGE original.
- Validação: `RangeRuntime` recompilado; jogo headless gerado por script (`RangeEngine -b`) com Motion (contínuo),
  Property (um disparo), Property disparado 4 frames seguidos e sensor invertido. Antes: Property só gerava
  `positive=0`. Depois: Motion positivo do frame 7 ao 17 (igual antes); Property positivo 1 frame (27→28);
  disparos seguidos ficam positivos sem piscar (34→37); invertido correto.
- Validação no editor: `RangeEngine` relinkado depois do Cycles do Codex; o mesmo jogo, mais um sensor Actuator
  vigiando um Property e outro vigiando um Message, cada um ligado a AND → Property, rodado pelo
  `VIEW3D_OT_game_start` (o P) na janela real. Log igual ao do runtime, e cada AND disparou uma vez
  (`hitProp=1`, `hitMsg=1`).

## 2026-09-25 - Cycles: escrita binária não reporta mais sucesso falso

- `path_write_binary()` em `source/intern/cycles/util/util_path.cpp` agora exige que `fwrite()` grave todos os bytes e que `fclose()` conclua sem erro. Antes, cache binário parcial por disco cheio, quota, I/O interrompido ou falha no flush podia ser aceito como sucesso. A API preserva a assinatura e os chamadores OpenCL já propagam o `bool` retornado.
- Validação: `util_path.cpp` recompilado e `lib/cycles_util.lib` relinkada no ambiente MSVC; `git diff --check` passou. Não há alteração de header/DNA.

## 2026-09-25 - Cycles: parser IES limita contagens antes de alocar

- `IESFile::parse()` preserva os contadores textuais como `long` até validá-los. Perfis IES com eixos zero/negativos, mais de 4.096 ângulos por eixo ou mais de 1.048.576 intensidades agora são rejeitados antes de `reserve()`/`resize()`; a contagem de `TILT=INCLUDE` recebe o mesmo teto. Isso evita conversão de `-1` para `size_t` e alocações excessivas por arquivo corrompido ou embutido.
- O teto de amostras considera que o processamento pode espelhar a tabela horizontal até quatro vezes, mantendo uma IES individual abaixo dos limites de `int`. A soma/offset entre múltiplas IES foi tratada na entrada seguinte (CYC-005).

## 2026-09-25 - Cycles: empacotamento IES não trunca tabela nem offsets

- `LightManager::device_update_ies()` agora calcula a soma de tabelas IES e os índices de slot em `size_t`, e só converte para `int` depois de confirmar que a tabela de offsets e os dados cabem em `INT_MAX`, formato exigido pelo kernel. Isso remove overflow na soma e offset negativo/truncado ao empacotar muitos perfis.
- Quando a capacidade é excedida, a engine envia uma tabela de offsets `-1`: os nós IES afetados não amostram um perfil, mas a renderização não usa memória ou offsets corrompidos. `light.cpp` recompilado e `lib/cycles_render.lib` relinkada no MSVC.

## 2026-09-25 - Animation Events revisados (crashes, threads, sensor, painel)

- Revisão do sistema herdado da Range. **Editor**: o evento agora conta como usuário da Action (`id_us_plus`/`min`
  em `object.c`, `newlibadr_us` no `readfile.c`, `IDWALK_CB_USER` no `library_query.c`, `expand_doit` no append).
  Antes, apagar a Action deixava ponteiro solto (crash ao desenhar o painel) e uma Action usada só pelo evento
  sumia ao salvar. Operadores (`object_animation_event.c`) validam índices e cancelam em vez de crashar, usam a cena
  ativa (antes `G.main->scene.first`), mandam notifier; ▲ no primeiro evento não troca mais com o elemento-base
  escondido (índice 0), que fazia o evento sumir. Remover evento libera os triggers.
- **Runtime**: `BL_Action::Update` roda nas threads do pool de animação e o `KX_Scene::UpdateAnimations` lia/limpava
  a mesma fila de eventos na thread principal ao mesmo tempo. Agora os callbacks rodam depois de
  `BLI_task_pool_work_and_wait`, no mesmo frame. Trigger dispara quando a reprodução cruza o frame (antes: janela
  de ±2 frames + lista "já disparados" por valor de frame, que engolia dois triggers no mesmo frame e zerava todas
  as Actions do objeto); trata loop, ping-pong, sentido reverso e objetos culled; `setActionFrame` não dispara o que
  pulou. `KX_AnimationEvent` guarda dados por valor (acabou vazamento de `new char[64]`/vetores), mantém referência
  própria da função Python e não compartilha proxy com a cópia; evento sem Python Event não gera erro no log;
  `animationEventManager` sem manager retorna `None` com refcount certo; manager não vazava mais uma referência na
  conversão.
- **Sensor Animation Event**: sensor de objeto criado por AddObject apontava para o evento do original (nunca
  disparava) — `KX_GameObject::ReParentLogic` religa. Detecção por contador de disparos (antes comparava o último
  frame e perdia disparos seguidos; com um trigger em loop disparava só uma vez). Conversão não chama mais
  `GetEvent` em manager nulo (`this &&`, UB no clang de Web/Android).
- **Painel**: Action e Python Event em cima, linha Triggers com Add Trigger, aviso com ícone de informação, ▲/▼
  desativados nas pontas, disponível também em Empty/Camera/Lamp.
- **Validação**: compilou (`RangeEngine` + `RangeRuntime`, sem mudança de DNA). Teste headless de 27 checagens dos
  operadores/contagem de usuários/salvar-recarregar passou. Teste no runtime com Action em loop 1-20, triggers em
  1, 10, 10 e 20, callback Python e sensor, num objeto e numa cópia por AddObject: cada trigger disparou 12-13
  vezes nos dois objetos e o sensor pulsou 24/25 vezes. Não verificado: o painel na janela do editor.

## 2026-09-25 - World Status com nomes em inglês

- As 8 World Properties automáticas viraram `rain_enabled`, `rain_intensity`, `clouds_enabled`, `mist_enabled`,
  `mist_density`, `sun_hour`, `cloud_type`, `player_under_cover` (`world.c`, `BL_ConvertProperties.cpp`).
  `horario_sol` virou `sun_hour`, que o runtime já lê para o World Sun automático.
- O `startup.blend` embutido guardava os nomes em português, e o File > New mostrava os dois conjuntos.
  `BKE_world_status_props_ensure` agora renomeia o nome antigo (mantendo o valor) ou o remove quando o novo já
  existe. `.blend` do usuário não são alterados. `RangeEngine -b --factory-startup` lista só as 8 em inglês.
- Painel World: Colors em 4 colunas; Moon Size e Brightness separados.

## 2026-09-25 - Aba Input nas Propriedades (Input System saiu das Preferências)

- O Input System (mapas `KeyMapping/*.json` ao lado do `.range`) era uma seção das Preferências da engine, mas os
  mapas são do projeto e vão no pacote Web/APK. Agora fica numa aba própria **Input** no editor de Propriedades
  (`BCONTEXT_INPUT = 18`, ícone de controle, depois de Export Game), no mesmo padrão da aba Export
  (`DNA_space_types.h`, `buttons_context.c`, `space_buttons.c`, `rna_space.c`, `space_properties.py`). A seção
  das Preferências só avisa que o painel mudou de lugar.
- `bl_ui/properties_input.py`: layout em árvore que abre e fecha, para caber na coluna estreita. Cada mapa abre e
  mostra as ações (Input Tables); cada ação abre e mostra tipo de retorno, ligações e processadores. Um mapa ou ação
  aberto por vez; mapa ou ação recém-criado já abre. Painel "On-screen Controls (Web/Android)" com o layout de toque
  e as ações que ele não aperta (WEB-INPUT-001).
- Correção: o painel antigo registrava propriedades no `WindowManager` durante o desenho, o que o RNA bloqueia
  ("can't set in readonly state"); abrir uma ligação dava erro e sumiam as ligações, os processadores e o botão de
  salvar. Agora o desenho só marca `update_binding_properties` e o handler `scene_update_post`
  (`input_sync_handler`) cria as propriedades e faz o salvamento pedido ao remover uma ligação.
- Traduções pt/es/ru dos textos novos (`INPUT_PANELS` em `translations_labels.py`); "Bindings:" em pt vira "Ligações:".
- Testado no editor com screenshot: criar mapa, ação e ligação (d-pad do joystick 0 como Vector2D), salvar e remover
  a ligação, conferindo o `.json` em cada passo. O motor e o formato do `.json` não mudaram.

## 2026-09-25 - Template de componente "03 Jogador Celular" (teclado, gamepad e controle na tela)

- Novo `release/scripts/templates_components/03_jogador_celular.py`, em Text Editor > Templates > Components.
  É o exemplo recomendado para quem não programa: anexa ao jogador e ajusta `Speed`, `Jump Speed`,
  `Move Relative To Object` e `Stick Deadzone` no painel. Anda com WASD/setas, stick esquerdo ou d-pad do gamepad 0
  e pula com Espaço ou botão A; o controle na tela (layouts `stick` e `dpad`) chega como gamepad 0, então o mesmo
  código serve ao PC, ao controle USB e ao celular. O comentário do topo é o passo a passo e explica que em
  `activeButtons` o botão A é 0 (no Input System é 1).
- Chão por `collisionCallbacks` (contato abaixo do centro com normal quase vertical), não por velocidade vertical
  perto de zero: depois de cair, a física deixa ~0,18→0,02 de velocidade por ~10 quadros e o pulo era ignorado.
  Objeto sem física anda, e o console avisa que ele não pula (sem traceback).
- Teste no `RangeRuntime.exe` (Windows) com cena gerada por script e input simulado no componente: componente
  carregado do `.range`, 3,33 m em 40 quadros com `Speed` 5, pulo 1 quadro após tocar o chão (0,49→1,29 m em
  10 quadros), sem pulo duplo no ar. Teclado, gamepad e toque reais não foram apertados nesse teste. Linux não
  testado; o template é só Python e usa a numeração SDL dos botões, igual nas duas plataformas.

## 2026-09-25 - Export Game: painéis RangeArmor, Web e Android divididos em caixas

- `SCENE_PT_rangearmor_export`: caixas Platforms / Package Info / Export, com dicas (Web e Android têm painéis
  próprios; campos vazios mantêm o padrão do RangeArmor Panel; o `.blend` precisa estar em `<projeto>/data/`).
- `properties_web.py`: caixas Package / Touch Controls / Validation / Export / Browser Test. O relatório da validação
  fica dentro da caixa Validation; "Pré-voo" e "Abrir após exportar" lado a lado.
- `properties_android.py`: caixas App / Build / Release Signing (só com tipo Release) / Tools / Build and Install.
  Versão e código da versão em linhas separadas (o label "Versão do app" ficava cortado).
- Traduções que as capturas revelaram erradas: o tipo de build aparecia como "Liberar" (`.mo` do Blender traduzindo
  "Release") e o runtime Web como "Em execução" (chave genérica "Runtime"). Os itens do enum viraram
  "Debug (testing)" / "Release (players)" e a propriedade `runtime_id` virou "Web runtime", sem mudar identificadores.
  "Product Name" e "Company Name" ganharam tradução. Tudo em `EXPORT_PANELS` de `translations_labels.py`.
- Teste: capturas dos três painéis em pt_BR, es e ru_RU sem traceback; `engine_i18n.py` 36 ok.

## 2026-09-25 - Aba Export Game no editor de Propriedades

- Nova aba `BCONTEXT_EXPORT = 17` (ícone EXPORT) logo depois de Cutscene, no grupo de cima do cabeçalho
  (`DNA_space_types.h`, `rna_space.c`, `buttons_context.c` usa o caminho de cena, `space_buttons.c` desenha o
  contexto `"export"`, `space_properties.py` inclui `'EXPORT'` em `top_context`).
- Os painéis Export (RangeArmor), Web (Range) e Android (Range) saíram da aba Scene e passaram a usar
  `bl_context = "export"`. Traduções da aba em `translations_ui.py`.
- Docs com o caminho antigo (`Properties > Scene > Web (Range)`) atualizados.

## 2026-09-25 - Game Settings > Audio e Scene > Units: labels e dicas

- Audio: "Speed of Sound (m/s)" e "Doppler Factor" no lugar de "Speed"/"Doppler", com dica de que o `LA_Launcher`
  lê esses valores da cena inicial. `audio3d_update` virou "Speaker Update Skip (frames)", com dica de que vale só
  para objetos Speaker e 0 = todo quadro.
- Units: o label do sistema de unidades dizia "Length:" e virou "Unit System:". No Game Engine aparece a dica de que
  as unidades só mudam a exibição no editor (o jogo sempre usa 1 unidade = 1 m) e um aviso quando há Unit Scale
  diferente de 1.
- Traduções pt_BR/es/ru em `translations_labels.py`.

## 2026-09-25 - Build: Ninja não rastreia headers (MSVC em português) e crash ao dar play

- Sintoma: depois de adicionar membros em `KX_GameObject.h` (billboard do LOD), dar play no editor e no RangeRuntime
  fechava a engine (`EXCEPTION_ACCESS_VIOLATION` em `KX_ShadowRenderer::Render`).
- Causa: `msvc_deps_prefix` em `build/CMakeFiles/rules.ninja` é `Observação: incluindo arquivo:`; a saída do MSVC chega
  em outra codificação, o prefixo não bate e o Ninja não registra nenhuma dependência de header. Só os `.cpp` editados
  foram recompilados; `KX_ShadowRenderer.obj` ficou com o layout antigo do `KX_GameObject`.
- Contorno aplicado: apagados os 307 `.obj` de `build/source/gameengine/**` e recompilado (329/329). Engine abre sem
  crash, cena com Sun e sombra roda 120 quadros no RangeRuntime, teste de LOD passa.
- Regra registrada em `AGENTS.md` e `docs/build-notes.md`. Correção definitiva pendente: reconfigurar com `VSLANG=1033`.
  Mudanças antigas em headers da parte C podem ter deixado `.obj` desatualizados; um clean rebuild resolve.

## 2026-09-25 - LOD: billboard restaura a rotação e nível Invisible sem Occlusion Culling

- `KX_GameObject::UpdateLod`: o nível com Billboard girava o objeto para a câmera e nunca devolvia a rotação ao voltar
  para um nível sem billboard. Novos membros `m_lodBillboardActive`/`m_lodBillboardOrientation` guardam a orientação
  ao entrar no billboard e a restauram ao sair.
- `KX_Scene::CalculateVisibleMeshes`: o nível "Invisible Mesh" só escondia o objeto com Occlusion Culling (DBVT)
  ligado. Nova `CullInvisibleLods` aplicada nos caminhos sem frustum culling e sem DBVT (não em shadow buffer).
- `OBJECT_OT_bake_lod_impostor`: grade do atlas agora usa colunas que dividem o número de ângulos (8 ângulos = 4x2,
  antes 3x3 com célula vazia).
- Teste no RangeRuntime (Occlusion Culling desligado): near/billboard/near/invisible/back com nível, `culled` e rotação
  corretos em cada etapa.

## 2026-09-25 - Game Settings (aba Scene): labels, Navigation Mesh separada e Python Console

- `properties_game.py`, `SCENE_PT_game_physics`: "Physics Engine" e "Solver" no lugar de "Engine"; boxes
  "Steps & Timing" (Game Rate / Per Frame, sempre visível), "Deactivation (Sleeping Objects)" e "Culling"
  (Render / Object Activity). Corrigido o ramo com física "None", que usava a propriedade inexistente `logic_step_max`.
- Obstacle Simulation com dica "Used by the Steering actuator to avoid obstacles" e labels "Simulation",
  "Level Height", "Show Debug Visualization" (é o RVO do atuador Steering, independente da navmesh).
- Navigation Mesh virou o painel próprio `SCENE_PT_game_navmesh` (fechado por padrão); removido
  `Scene.show_expanded_game_navmesh`.
- "Level of Detail - LOD" virou "Level of Detail", com dica de que os níveis ficam na aba Object.
- Python Console: checkbox "Enable Python Console" movido para dentro do box, junto das teclas e de uma dica
  (segurar as teclas durante o jogo abre o console do sistema; o jogo pausa enquanto ele está aberto).
- Traduções pt_BR/es/ru dos novos textos em `translations_labels.py` (`RENDER_PANELS`).

## 2026-09-25 - Aba Render: painéis reorganizados, FXAA configurável e addons padrão

- Seletor de engine (`RENDER_PT_render`) movido para `properties_render_engine.py`, registrado antes de
  `properties_game` para ficar no topo da aba Render.
- Player: Embedded e Standalone lado a lado num painel "Player". System e Game Exit Key lado a lado; cursor
  customizado recolhível. Dynamic Resolution foi para dentro do painel Display, ao lado das opções de tela.
- Attachments: slots vazios aparecem como "Empty", mostra o índice `bgl_DataTextures[n]` real, avisa quando há slots
  vazios antes (os índices dos materiais deixam de bater) e quando o SSR usa o Slot 0. `active_attachment_index`
  usa `GAME_ATTACHMENT_COUNT`.
- Animations: frame rate da animação e taxa de lógica lado a lado, com dica do "Restrict Animation Updates".
- Bake: dicas de que precisa de UV e imagem, e de que usa o shading do Blender Render. Easter egg "Make GTA 6" mantido.
- FXAA: `SCENEFXSettings` ganhou `fxaa_edge_threshold`, `fxaa_edge_threshold_min`, `fxaa_subpix` e
  `fxaa_search_steps` (padrões = valores antigos fixos no shader; versioning em `versioning_range.c`). Os shaders do
  viewport (`gpu_shader_fx_fxaa_frag.glsl`) e do jogo (`RAS_Fxaa2DFilter.glsl`, uniform `ge_FxaaParams`) leem esses
  valores; filtros criados por Python/atuador usam os padrões. Painel FXAA expansível em Post-Processing.
- Userpref padrão liga os addons Icon Viewer e Game Engine Scene Statistics (vale para userpref novo; um
  `userpref.blend` salvo mantém a escolha do usuário).

## 2026-09-25 - Build: correções para Android NDK e Cycles no player

- `source/CMakeLists.txt`: sem GLU no Android mesmo com perfil compat. `mallocn_intern.h`: sem `malloc_stats()` no
  bionic. `util_profiling.cpp`: `#include <chrono>`. `blenderplayer/CMakeLists.txt`: liga `bf_intern_cycles` quando
  `WITH_CYCLES` (o `bf_python` registra o módulo `_cycles`).
- `docs/build-dirs.md`: nomes oficiais dos diretórios `build*` (o Android oficial é o APK WebView; `build-android/`
  é o experimento NDK congelado). Referenciado em `AGENTS.md`, `build-notes.md` e `mobile-export-plan.md`.
