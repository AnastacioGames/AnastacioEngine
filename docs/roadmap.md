# Roadmap

Somente itens abertos, pendentes de validação ou explicitamente adiados ficam neste arquivo. Recursos
concluídos estão resumidos em [`../relatorio-melhorias-anastacioengine.md`](../relatorio-melhorias-anastacioengine.md)
e detalhados no [`changelog.md`](changelog.md). O histórico Web que antes ocupava este arquivo (bloqueios de
shader/GL, causas raiz de teclado/mouse/gamepad, IDBFS, cena de filtros) está nas entradas de 2026-09-12 a
2026-09-20 do changelog.

Auditado contra o git log e o changelog em 2026-09-20.

Continuação da migração de nome em 2026-10-08: geração Web, preflight no navegador e APK pelo
editor novo passaram após corrigir falso positivo no diagnóstico de shaders. APK ainda precisa
de teste em aparelho. Exportação pela GUI RangeArmor passou em cena controlada; jogo real permanece pendente.
Evidências e limites no [plano de renomeação](executable-rename-plan.md).

## Sumário

- [Atlas de materiais](#atlas-de-materiais)
- [Prioridade atual](#prioridade-atual)
  - [Carregamento mais rápido ("Cozinhar")](#carregamento-mais-rápido-cozinhar)
  - [Dano visual por impacto (Deformation)](#dano-visual-por-impacto-deformation)
  - [Multiplayer nativo](#multiplayer-nativo)
  - [Web (WebGL/WebAssembly)](#web-webglwebassembly)
  - [VR no celular (Web, estilo Cardboard)](#vr-no-celular-web-estilo-cardboard)
  - [Idioma (English, Português, Español, Русский)](#idioma-english-português-español-русский)
  - [Linux x86_64](#linux-x86_64)
  - [Cutscene nativo](#cutscene-nativo)
  - [World Status](#world-status)
  - [Animation Events](#animation-events)
  - [Vehicle System / Vehicle Lab](#vehicle-system--vehicle-lab)
  - [Destruição e explosões](#destruição-e-explosões)
  - [Deformação por impacto](#deformação-por-impacto)
  - [Câmera: foco, rastreio e Camera FX](#câmera-foco-rastreio-e-camera-fx)
  - [Logic Bricks → Python Component](#logic-bricks--python-component)
  - [Android / iOS](#android--ios)
  - [Outros](#outros)
- [Performance](#performance)
- [Iluminação e gráficos](#iluminação-e-gráficos)
- [Validações manuais pendentes](#validações-manuais-pendentes)
- [Fora do escopo atual](#fora-do-escopo-atual)

## Atlas de materiais

- [Ferramenta nativa e plano](material-atlas-plan.md): primeira versão para um mesh com materiais PBR opacos. Pendente: usuário validar no jogo real, Escape físico/fechamento da janela, Linux e integração GI com denoise/light volume. GPU OpenCL, Undo/Redo automático na conclusão modal, restauração persistente, cancelamento via API/rollback, Web no navegador e bakes de GI nas duas ordens passaram em cena controlada. Próximas peças, após revisão: materiais legados, vários objetos, transparência e grafos mais amplos; combinação direta sem bake permanece futura.

## Prioridade atual

- Migração Windows: editor `AnastacioEngine.exe` e player `AnastacioRuntime.exe` compilados.
  Cooking, standalone pelo editor e export nativo passaram em cena controlada; usuário
  confirmou que o jogo funciona após a migração. Pendente: console,
  Steam/LAN, associações HKCU/HKLM e Windows sem Visual Studio; [plano](executable-rename-plan.md).
  Linux e artefatos Web/Android mantêm nomes anteriores.

### Carregamento mais rápido ("Cozinhar")

- RangeArmor: preparo de `.cooked` na exportação, opção de exportar sem cache, staging e launcher
  Windows atualizado passaram em cena controlada e pacote extraído. Pendente: jogo real,
  Linux/outra GPU e migração dos runtimes dos projetos antigos; [plano](rangearmor-update-plan.md).
  Cópia da instalação real, Cook e execução pelo player copiado passaram em caminho com
  espaço/acento. Aberto: codificação de destinos não ASCII em `ANASTACIO_COOK` direto no runtime.
  Painel Rust recompilado com tratamento de exit code; 26 testes e abertura/fechamento
  passaram. Exportação pela GUI e diagnóstico de falha passaram em cena controlada;
  export comprimido pela GUI também passou, com execução do ZIP extraído e uso do cache.
  Usuário confirmou execução do jogo; falta validar LibLoad, benefício do cache no jogo
  real e outras plataformas/GPU. Pacotes locais sem símbolos de debug foram extraídos e
  executados; permanece validação em Windows limpo antes de publicar.

Plano: arquivo `.cooked` preparado para o jogo ao lado do `.range`, com fallback para o cru. Etapas 1 (medição
`[Load]`) e 2 (cache de shader GLSL, merge do LibLoad só com materiais novos) feitas em 2026-10-03; comparação
visual automática sem diferenças atribuíveis ao cache. Biblioteca GLSL enxuta por shader (só as funções
usadas) também feita: compilação ~4× mais rápida, imagens idênticas. Falta o usuário conferir jogos reais.

Aberto:

- Fast Shader Loading (valores como uniform) é opção no painel Render, desligada por padrão: carrega muito
  mais rápido, mas custa ~45% do FPS em cena pesada. Ideia aberta: uniform só para materiais repetidos (mesma
  estrutura) e constante para os únicos.
- Etapa 4 parcial (2026-10-03, sem formato novo): normais/tangentes e BVH de física compartilhadas entre malhas
  de conteúdo igual (800 esferas: conversão 2,9 s → 0,8 s). Malhas únicas ainda calculam tudo; guardar pronto
  exigiria o `.cooked`.
- `.cooked` começou (2026-10-07): pontos do Convex Hull gravados ao jogar o `.blend` e copiados pelo Export
  Game (física 1,6 s → 0,04 s no teste de 12 objetos). Binário dos shaders de material também (310 → 3 ms);
  com o botão Cook o LibLoad do teste foi de 2,4 s → 0,47 s. Próximo candidato medido: buffers de malha
  (~320 ms dos 12 objetos). Falta conferir num jogo real. Jogo exportado guarda os shaders num cache do
  usuário e aquece todos na primeira abertura em cada GPU/driver, com tela de texto (sem barra de progresso).
- Texturas (2026-10-03): PNG decodificados em paralelo, 80 imagens 2048² 2,2 s → 0,7 s. O resto é upload
  serial na GPU; DDS no `.cooked` cortaria ambos.
- Tela de loading do LibLoad (2026-10-03): `asynchronous=True` agora tem progresso real (conversão por
  objeto, depois texturas e shaders um a um) e o merge se espalha em frames de ~8 ms. Falta o usuário testar
  num jogo real; a abertura/link do arquivo ainda é síncrona. Luz nova recompila a cena uma vez só depois
  de todas as bibliotecas da fila (20 arquivos com lâmpada: 9,8 s → 5,6 s); sobra o custo de compilar ~15 ms por
  shader com muitas luzes. `Range.logic.setLibLoadFrameBudget(30)` na tela de loading: 5,3 s → 3,6 s. Ideia aberta:
  com lâmpada, cada material novo compila duas vezes; esconder os objetos até a recompilação final cortaria ~metade.
  Compilação paralela no driver testada e descartada (despacho já custa ~4 ms por shader).
- Cena com tela de loading (2026-10-03): `addScene(nome, 0, asynchronous=True)` compila os shaders aos poucos e só
  então põe a cena na lista; aplicado no `BrainCore` do RolimaRacer. Falta o usuário testar no jogo.
- Último caso (decisão do usuário): etapa 3, `.cooked` v1 (`.range` enxuto + texturas DDS), interruptor e
  status na UI. Só se o `[Load]` ainda mostrar ganho a buscar.

Descartado: cache de shader em disco (`glProgramBinary`, etapa 5). Testado em 2026-10-03 com 200 esferas:
todos os binários carregaram, mas a cena ficou mais lenta (4,4 s contra 3,2 s), porque o cache do próprio
driver NVIDIA já é mais rápido; o pedido de binário recuperável ainda desliga esse cache (1ª rodada 13 s).
Código revertido.

### Dano visual por impacto (Deformation)

Feito: Dent, Bend em V, nó Damage (máscara por pontos de impacto), decals de impacto e marcas de arrasto.
Em 2026-10-02: Scrape Style Strip (faixa contínua, marca de pneu) ao lado dos carimbos, botão Add Damage Mix
(tinta → metal enferrujado) e decals que acompanham amassados posteriores. Validados pelo usuário em
`damage_marks_test.range` (`tools/create_damage_marks_test.py`).

### Multiplayer nativo

- **Complemento Steam (Windows implementado, prova externa pendente, 2026-10-07):** componente/menu
  reutilizável distribuído pela engine; SDK/transporte opcionais, salas e convites.
  [Inventário e contrato](steam-multiplayer-inventory.md): componentes reais conferidos,
  SDK local encontrado; AppID comercial e exportador do jogo pendentes. B2 compilado com SDK 1.55,
  serviço único e API `Range.network.steam`; player validou DLL real e erro de Steam fechada.
  SDK real passou canais, handshake, transform/propriedade, spawn/despawn e ownership em sockets
  locais; salas/menu, adaptadores do jogo e export Steam/LAN passaram. [Guia](steam-complement-development.md).
  Pendentes: dois jogadores em redes distintas e relay confirmado, convites aberto/fechado,
  carros/corrida real e saída/reentrada, AppID comercial, revisão de distribuição e Linux.
  Revisão local corrigiu cancelamento/timeout, argv de convites, descarte por lane,
  fila de desconexão, confirmação na UI e retorno/reabertura de sala. Dois players ENet
  passaram duas partidas e reentrada; Steam numa conta passou retorno/busca/segunda partida.
  Esses resultados locais não encerram os critérios externos de saída/reentrada e convites.
  Web continua com WebSocket; não inferir cross-play Steam. A migração de SDK é única, mas
  conquistas comerciais e avaliação visual do RolimaRacer ainda precisam de teste.
  Etapas e critérios em [steam-multiplayer-plan.md](steam-multiplayer-plan.md).

Plano em [`multiplayer-plan.md`](multiplayer-plan.md), contrato em [`multiplayer-protocol.md`](multiplayer-protocol.md). Núcleo isolado pronto na main (2026-10-04, frentes A–J, `source/source/gameengine/Network/`): protocolo, ENet + WebSocket, servidor, replicação com delta/relevância/orçamento, predição e lag compensation, relógio, RPC, descoberta LAN, menu (`tools/net_menu/`), CI (`.github/workflows/network.yml`: gcc, clang, MSVC, wasm32, pytest, Docker).

Ligado na engine (`net/engine`, na main desde 2026-10-04; registro em [`NOTES-engine.md`](../source/source/gameengine/Network/NOTES-engine.md)): `KX_NetworkManager` (host, cliente, replicação de transform/velocidade/propriedades, spawn/despawn, dono, chat, pronto/iniciar, LAN, simulador), DNA/RNA/painéis Network (cena e objeto, "Rep" nas propriedades, versioning), `Range.network` com a API de `tools/net_menu/NOTES-D.md`, `ge_network` no CMake. Testado no Linux (build headless + editor): servidor e cliente `RangeRuntime` sob xvfb, o objeto replicado se move no cliente, nos modos script e cena (`tools/net_engine_test/run_net_test.sh spawner|car|scene`). **Windows/MSVC validado** (2026-10-04): compila, `spawner`/`car`/simulador passam com dois `RangeRuntime` (`run_net_test_win.sh`) e os painéis Network aparecem certos no editor.

Servidor headless e predição refeitos em `claude/project-thread-l2znr0` (2026-10-04, na main pelo PR #4, `9e7925f`): `RangeRuntime --server` sem render nem áudio, Dedicated, ~0,13 núcleo ocioso (`run_net_test.sh server|scene-server`); predição do cliente, input e lag compensation (`net.predict`, `set_input`, `set_hitbox`, `raycast_past`, `skipOwned` com filtro, throttle do ENet desligado), testados no Linux (`run_net_test.sh predict`); RPC do jogo (`@net.rpc`, `net.call`) e `obj.net` (`run_net_test.sh rpc`), com `sender` nos clientes pela mensagem provisória `200 RpcFrom`. Reconciliação da predição corrigida (`NodeUpdate()` ao mover o objeto previsto); `view_time` corrigido para o snapshot de fato desenhado (lag compensation do `predict` 100% em 20 rodadas no Linux); propriedades replicadas de objeto previsto agora chegam ao dono (só transform/velocidade eram puladas). **Windows/MSVC parcialmente validado** (2026-10-04): `run_net_test_win.sh spawner`/`car` passam com os três commits (`net.headless`, `net.isServer` e o módulo `Range.network` completo responderam certo); achada e documentada em `NOTES-engine.md` uma armadilha de build (ninja não recompilava `KX_PyNetwork.cpp.obj` após `git checkout`, mascarando o código novo). As branches `net/server-headless` e `net/engine-predict` originais nunca chegaram ao GitHub. **Linux revalidado na main `9e7925f`** (2026-10-04): os 7 cenários de `run_net_test.sh` passam; `predict` falhou 1 vez em 4 (`max_error` 0,6 > 0,5, 21 correções): causa confirmada com `network.input_stats` (inputs do cliente chegando depois do tick simulado no servidor); a linha de ticks do cliente agora segue o relógio (dois passos ou nenhum por quadro) e a margem subiu para 2 ticks (8 rodadas PASS, erro ≤ 0,134); o servidor devolve a folga dos inputs (mensagem `201 InputTiming`, contrato fechado após revalidação no Windows: 5 rodadas PASS, erro 0, 0 correções) e o cliente ajusta o adiantamento por ela: 8 rodadas PASS com erro máximo 0. Windows: `predict`/`server` (`87fe6d1`, inclui `--server` no Windows) e `scene`/`scene-server` (`19e1437`) já validados no `run_net_test_win.sh`.

Feito em 2026-10-05: troca de cena durante a partida (`net.change_scene`, teste `scene-change`). Feito em 2026-10-04: predição de corpo dinâmico simples (cenário `predict-cube`; veículo fica de fora, ver changelog), IPv6 no transporte WebSocket `--server` sem janela nem display no Linux (contexto EGL surfaceless), relevância por distância (`Relevance Radius` da cena + `net.set_client_view`) e faixa/bits por propriedade float na UI. **Windows/MSVC revalidado (2026-10-05)** após `git pull` + build incremental: os 6 cenários do `run_net_test_win.sh` (`spawner`, `rpc`, `predict`, `server`, `scene`, `scene-server`) PASS, `predict` com 0 correções/0 teleportes. `scene-change` não tem equivalente no script Windows (só `run_net_test.sh` no Linux); não revalidado por aqui. **Runtime Web completo com rede, fechado (2026-10-05, Windows, Chrome real não-headless)**: não é mais só o transporte isolado — `RangeRuntime` Web (`build-web-release`) rodando o jogo de verdade (modo cena Client, `make_net_web_scenes.py`) contra um `RangeRuntime --server` nativo, verificado por CDP num Chrome de verdade (`tools/web/verify-package.cjs`): `NETWEB client PASS connected=True hp_changed=True moved=True` (replicação de transform e de propriedade confirmadas dentro do Python do próprio jogo, não só pelo `net_web_watch`). Achado: a cena Client para a Web precisa ter o endereço apontando para o `websocket_port` do host, não o `port` ENet (ver changelog); isso é cuidado de deploy, não bug. IPv6 no ENet/UDP: vendor trocado em 2026-10-05 (ver `NOTES-engine.md` e changelog) — `source/extern/enet` agora é o fork `zpl-c/enet` (header único), compilado em modo `ENET_IPV4_ONLY` por enquanto (a sandbox de build nem tem pilha IPv6). **API Python decidida (2026-10-05):** `net.host`/`net.join` já expõem IPv6 pela própria string de endereço — `net.join("[::1]:7777")` já é documentado e parseado (`ParseAddress` em `KX_PyNetwork.cpp`), `net.host(port=...)` já faz bind em `ENET_HOST_ANY` (que no fork dual-stack vira `in6addr_any`); não há parâmetro novo a adicionar. O guard de rejeição de IPv6 em `NET_TransportENet.cpp::connect()` passou a ser condicional (`#ifdef ENET_IPV4_ONLY`): no build IPv4-only atual o comportamento é idêntico; num build dual-stack (`-DENET_IPV4_ONLY=OFF`, numa máquina com IPv6) o `connect()` entrega o endereço ao `enet_address_set_host` do fork e o IPv6 passa a funcionar ponta-a-ponta sem mais mudança de código. Ambos os modos compilam limpos (0 warnings); IPv4-only revalidado 100% PASS no `ctest`. Regressão completa validada no Linux (`spawner`, `rpc`, `predict`, `server`, `scene`, `scene-server`, `scene-change`, `predict-cube`, `car`, todos PASS) e wasm32 (Emscripten 6.0.11, Node.js, CI core tests PASS). **`--server` sem janela visível no Windows resolvido em 2026-10-05**: o GHOST Win32 cria a janela WGL oculta no caminho headless; cenário servidor PASS e `EnumWindows` confirmou 0 janelas visíveis no processo servidor. **`::1` testado e isolado (2026-10-05, Windows)**: com `ENET_IPV4_ONLY=OFF` (`build-net-v6`), o handshake ENet em `::1` reproduz timeout real (`DisconnectReason::Timeout`). Instrumentação em `enet.h` (revertida depois, `git diff` limpo) mostrou que todo `sendto()` do cliente retorna sucesso mas o `recvfrom()` do servidor nunca dispara — perda ocorre fora do ENet/engine. Confirmado com um teste `System.Net.Sockets.UdpClient` IPv6 puro, fora do ENet e do engine, reproduzindo o mesmo timeout em `::1` — descarta bug de código. Testado então IPv6 UDP real entre dois dispositivos (PC ↔ celular via tethering USB/RNDIS, endereços link-local `fe80::`), nos dois sentidos: funcionou perfeitamente (envio e recebimento OK). Conclusão: o bug é específico de **loopback IPv6 nesta máquina Windows** (suspeita: interface `vEthernet (WSL (Hyper-V firewall))` interceptando/derrubando tráfego de loopback), não do ENet/engine nem da pilha IPv6 em geral — não é corrigível por mudança de código; depende de config local de rede/Hyper-V/AV. Predição de veículo: avaliada e mantida fora da v1 (decisão do usuário em 2026-10-05, só interpolação; replay completo do Bullet fica para pós-v1).

### Web (WebGL/WebAssembly)

Estado: o runtime Web roda no navegador com render (luz GLSL, normal map `.dds`, sombras, filtros 2D), teclado,
mouse, gamepad, save (IDBFS), áudio (WAV/MP3/OGG e módulo `aud`), transição de cenas e Python. O validador
(marcos A–D), o pré-voo (marco E, automático depois do Exportar Web) e o empacotamento estão implementados; os
pacotes de teste 8201–8211 foram aceitos pelo usuário. Planos: [web-profile-validation-plan.md](web-profile-validation-plan.md),
[web-deploy.md](web-deploy.md), [android-web-export-roadmap.md](android-web-export-roadmap.md).

Aberto:

- **Patch do SDL2/Emscripten** (gate de timestamp do gamepad): versionado em `tools/web/patch-sdl2-gamepad.py`
  e aplicado no configure (`platform_web.cmake`). Gamepad físico conferido no navegador em 2026-09-20 (D-pad
  corrigido em `DEV_Joystick`, ver changelog). Controle sem mapeamento standard ("USB Joystick", D-pad como hat
  no eixo 9) e save (IDBFS) testados e aceitos pelo usuário em 2026-09-20 ([roteiro](web-sdl2-gamepad-test.md)).
- **Erros de áudio no Web (R3)**: arquivo inexistente/corrompido em `aud` agora vira exceção Python (`-fexceptions` no
  audaspace; não abortam mais). `cache()`, `reverse()`, `pause()`/`stop()` com som válido conferidos em 2026-09-23. Custo em celular
  medido (M3, 2026-09-23): desprezível. Ver changelog de 2026-09-21. Rebuild Web limpo da `linux-sync` reverificado
  (sonda R3 `[r3] TODOS`); a branch `integracao` foi removida por estar contida nela.
- **Extração de erros de shader/Python no pré-voo (M1, encerrado)**: eventos estruturados do runtime
  (`Module.onDiagnostic`, relatório v2) para shader (estágio, material real, compile/link) e Python (tipo, texto,
  traceback, controller/componente/callback), testados no navegador; a heurística sobre o texto fica só como fallback.
  "Importar pré-voo Web" segue para JSON manual. Detalhes em [web-remaining-execution-plan.md](web-remaining-execution-plan.md).
  Falha em **material de nós** validada no Windows/Edge headless em 2026-10-04 (roteiro D em `ROTEIRO-M1.md`): fragment,
  vertex e link saem com `material` "MAMatNosQuebrado" e `structured: true`; o link também reprova. Falta só importar
  o relatório no editor (passo 5, UI).
- **Rodada Web de 2026-09-20 (M0-M3, R1, R3)**: M2 e as correções do M3 validados em runtime; R1 (ABI de
  constraints Python) integrado e verificado (nativo e Web); R3 (aborts de áudio sem exceções) **corrigido**
  no runtime Web (`FileManager` devolve leitor silencioso; sonda com 10 casos termina com `[r3] TODOS`;
  `codex/r3-audio-fix-new` superada). Bug de `aud` com `METH_NOARGS` corrigido em `ea2cfd04` (18 métodos) e
  validado no Edge headless em 2026-09-23 (`cache()`, `reverse()`, `handle.pause()/stop()` sem mismatch). Diagnosticos de shader
  trazem o nome real do material e cobrem falha de link (node-material não injetável). `frame-time-perf.js`
  (`?perf=1`, overlay, `perf-run.cjs`) integrado; `package-web.py --perf` inclui a sonda. Build de teste para celular publicado em
  <https://anastaciogames.github.io/AnastacioEngine/?perf=1> (branch `gh-pages`, First Person) em 2026-09-23.
  Regressões de áudio/bloom/resolução dinâmica/R1 repetidas após a mudança de áudio: todas OK (2026-09-23). Medição em celular
  físico (2026-09-23, OPPO Reno14 5G, Dimensity 8350, 12 GB, `?perf=1`): p50 22 ms, p95 55 ms, dpr 3, canvas
  640x480; lentidões periódicas que se recuperam sozinhas. Média aceitável; o M4 deve atacar os picos (p95:
  GC/Python/áudio/compilação de shader), não a resolução. Rodada 0.1.3 (mesmo aparelho, MP3 em loop via `aud`
  + sombra reconfigurada pelo usuário): música toca; p50 33 ms, p95 44 ms. A versão tinha `fps` 60→30 e
  sombra do Sun 2048→512 (clip 90→33,7, frustum 40→13): o p50 é o teto de 30 fps, não custo. A/B a 60 fps com
  a mesma sombra (0.1.4, `/musica/` e `/sem-musica/`): com música p50 22/p95 33 ms, sem música p50 22/p95 44 ms;
  o áudio MP3 não custa desempenho mensurável (diferença do p95 é variação entre rodadas). M3 do áudio fechado. **M4 adiado** (2026-09-23): o jogo medido não usa filtros 2D e os picos do p95 são
  esporádicos, não custo fixo de passe; reabrir só se um jogo com filtros medir mal no celular.
  Desktop (Chrome, `/musica/`, DPR 2): p50 18,1/p95 18,5 ms, sem picos; os picos são do celular. Console: aviso de
  `ScriptProcessorNode` obsoleto (resolvido em 2026-10-04: saída AudioWorklet, ouvida pelo usuário no navegador do PC e no Chrome do celular (via `adb reverse`) sem problemas; ver changelog) e um quadro de 104 ms na carga. Divisão vigente e pendências em
  [web-remaining-execution-plan.md](web-remaining-execution-plan.md).
- **Reverb Area (2026-09-29)**: validar ouvindo no jogo real (entrar/sair de uma área com um speaker 3D
  tocando). Web: EFX indisponível no backend SDL atual (`web-no-openal/efx.h`); em 2026-10-07,
  teste A/B no Edge passou alternância seco/caverna a cada 2 s e saída AudioWorklet ativa,
  usuário confirmou ausência de diferença audível mesmo com som contínuo e reverb forte em
  `build-web/dist/reverb-ab/` (gerador `tools/create_web_reverb_ab_scene.py`). Sem desenho
  da zona de efeito total no viewport (só a borda externa, pelo Empty).
- **Áudio 3D/efeitos OpenAL**: só se algum jogo precisar; `Sound.data()`/`buffer()` do `aud` indisponíveis por
  falta de numpy.
- **Filtros 2D**: refinamento visual e custo de múltiplos passes ficam para etapa posterior; tratar como
  opcionais na Internet.
- **`USE_RNA_RANGE_CHECK` no Emscripten (resolvido no M2)**: checagem reativada. Os cinco campos DNA
  (`fie_ima`, `seed1`/`seed2`, `skgen_subdivision_number`, `handle_vertex_size`) viraram `unsigned char`, com SDNA
  idêntico. Evidência em `docs/changelog.md` (2026-09-20). O MSVC nativo não executa essa checagem.

### VR no celular (Web, estilo Cardboard)

Estado: pose da cabeça pelo `deviceorientation`, head tracking
na câmera, distorção de lente no Side-by-Side e botão "Entrar em VR". OpenXR (headset) adiado até haver hardware.

### Idioma (English, Português, Español, Русский)

Editor compilado com i18n e painel Web traduzido no Windows (ver changelog de 2026-09-20). Pendente:

- Conferir na janela real do Windows: Preferências > System > **International Fonts**, escolher **Language** e ligar
  **Interface**; ver fonte, acentos e o menu (Default, English, Português, Español, Русский; cirílico depende da fonte Roboto). Decidir se o padrão de fábrica deve vir
  com a tradução ligada (hoje segue o 2.79: desligada).
- Auditoria: `RangeEngine -b --python tools/tests/web_profile/i18n_audit.py -- <idioma> [saida.txt]` lista textos sem
  tradução. Restam lacunas do catálogo do Blender 2.79 (pt_BR ~455, es ~511, ru ~1 124). Textos fixos dos layouts Python
  (`layout.label(text=...)` etc.): scan estático em `i18n_scan_labels.py` e traduções em `translations_labels.py`
  (2026-09-24; restam só nomes próprios, códigos e palavras iguais nas duas línguas). Textos em C fora do RNA
  (`IFACE_`/`TIP_`/`N_`): scan em `i18n_scan_c.py` e traduções em `translations_c.py` (2026-09-24; em pt/es restam
  códigos e nomes; no ru, 90 lacunas do catálogo russo do Blender). O russo (e o es) de `translations_ui.py`, `translations_labels.py` e `translations_c.py` precisa de revisão nativa.
- Complemento dos catálogos `.po` ausente do MO instalado: 436 entradas pt_BR e 493 es foram carregadas por
  `translations_catalog.py` (2026-09-24). Na auditoria de fonte, as lacunas passaram de 1 279 para 1 030 (pt_BR) e
  de 1 336 para 1 089 (es); o restante inclui identificadores, ícones e termos técnicos/iguais ao inglês.
- Mensagens das regras Web traduzidas (2026-09-23, `translations_rules.py`; es/ru pedem revisão nativa). Textos em
  português dos operadores da Range (flowmenu: editor externo e assistente de componente; veículo; partículas)
  passaram ao inglês com tradução (2026-09-24, bloco `MESSAGES` de `translations_labels.py`), inclusive o addon opcional
  `addon_editor_shot_tool.py` (a cópia antiga em `tools/ProjetoCutscene` ficou como estava). As mensagens `self.report` do flowmenu e do veículo já passam por `tip_()`.
- Linux: `linux-editor` recompilado com `WITH_INTERNATIONAL=ON` e `engine_i18n.py` com 36 ok (2026-09-26); os
  `blender.mo` (pt_BR, pt, es, ru) saem em `bin/2.79/datafiles/locale/` e o `package-runtime.sh` copia o `bin`
  inteiro. Seletor de idioma conferido na janela pelo usuario (2026-09-26).
- Roteiros manuais citam os botões pelo nome em português; em inglês são Validate Web, Export Web, Open in browser.

### Linux x86_64

`RangeRuntime` e `RangeEngine` compilam e rodam em Linux nativo; pacote 0.4.0 publicado. Ver
[linux-build.md](linux-build.md). Pendente:

- **Bugs do Kitsuy (2026-09-28)**: corrigidos e validados no Windows e no Linux (Intel integrada,
  NVIDIA via offload e llvmpipe sem GPU; ver changelog). Falta mandar o build ao Kitsuy.

- **Retorno do Discord (2026-09-29), testar tudo na maquina Linux:**
  - **Dependencias do pacote (Fumangy):** "instalei, mas pede dependencias". O pacote usa as `.so` do sistema
    e o `apt install` da release/`linux-build.md` so vale no Ubuntu 24.04 (nomes com versao: `boost-locale1.83.0`,
    `openexr-3-1-30`, `openimageio2.4t64`, sufixo `t64`). Todas sao exigidas mesmo sem usar o Cycles (so
    `libembree4` e exclusiva dele). Pedir distro/versao e `ldd ./RangeEngine | grep "not found"`. Solucao
    proposta: empacotar as `.so` em `lib/` (RUNPATH `$ORIGIN/lib`, ja usado pelo Python), deixando so
    GL/X11/driver no sistema; validar em Ubuntu 22.04, Debian 12 e Fedora limpos.
    **Diagnostico 2026-09-29 (pacote 0.4.4 extraido, sem apt):** na maquina de build `ldd | grep "not found"`
    sai vazio (ja tem tudo). Dependencias diretas fora de `lib/`: Runtime = GL/GLU/GLEW, X11 (Xi, Xinerama,
    Xxf86vm, Xfixes, Xrender), SDL2, OpenAL, sndfile, freetype, png, jpeg-turbo8, tiff6, fftw3, gomp, z,
    stdc++; o editor soma OpenImageIO 2.4, OpenEXR 3.1, boost_locale 1.83 e embree4. A OIIO puxa ~250 `.so`
    transitivas (GDAL, OpenCV, FFmpeg). **Bloqueio maior:** os binarios exigem `GLIBC_2.38` (`__isoc23_strtol`,
    `__isoc23_sscanf`, `fmod`) e `GLIBCXX_3.4.32`; a glibc nao pode ir em `lib/`, entao Ubuntu 22.04 (2.35) e
    Debian 12 (2.36) nao rodam nem com as `.so` empacotadas. Para cobrir essas distros, compilar o pacote numa
    base antiga (container Ubuntu 22.04/Debian 12) e empacotar as `.so` que nao sao GL/X11/glibc; para o
    editor, avaliar tirar a OIIO do pacote Linux.
    **Feito 2026-09-29:** `package-runtime.sh` empacota as `.so` e o pacote passou a ser compilado num container
    Ubuntu 22.04 (`tools/linux/container-build-22.04.sh`, glibc 2.35). Publicado na v0.4.5; falta o Fumangy
    confirmar no Ubuntu 26.04 (o pacote antigo falhava com `libOpenImageIO.so.2.4`).
  - **Som no player Linux (Kitsuy):** jogo com tela preta no 0.4.5 Linux; causa: `aud` nao lia `.mp3` (libsndfile
    1.0.31 do 22.04 sem MPEG, FFmpeg desligado no Linux). **Feito 2026-09-30:** container compila e empacota a
    libsndfile 1.2.2 com MP3; pacote 0.4.6 toca `.mp3`/`.ogg`. Falta publicar a 0.4.6 e o Kitsuy confirmar.
  - **`colormanagement` no pacote Linux (Kitsuy, 2026-09-30):** falta `2.79/datafiles/colormanagement`; so e
    instalada com `WITH_OPENCOLORIO`, que estava desligado no Linux; player rodava em "fallback mode". **Feito
    2026-09-30:** o apt do 22.04 tem a OCIO 1.1.1 (API 1.x do codigo); presets Linux ligam `WITH_OPENCOLORIO`,
    pacote 0.4.6 leva `libOpenColorIO.so.1` e a pasta, sem "fallback mode". Falta o Kitsuy confirmar.
  - ~~`RangeRuntime` ignora `SIGTERM`~~ **Corrigido (2026-10-05).** A premissa ("handler instalado") estava
    errada: não havia handler nenhum, só os de `SIGSEGV`/`SIGABRT` (crash dump) em `GPG_Ghost.cpp`. Adicionado
    `signal(SIGTERM, ...)` que seta `LA_SigTermRequested` (atomic), checada em
    `LA_Launcher::EngineNextFrame()` a cada frame (mesmo caminho de saída limpa do fechar de janela,
    `KX_ExitInfo::OUTSIDE`). Testado manualmente com `RangeRuntime --server` headless: processo saía em até
    timeout (`kill -9` externo) antes, agora sai limpo em ~0,1 s. `run_net_test.sh server`/`spawner` PASS
    (Linux, `build-linux-editor`) sem regressão.
  - ~~Menu do player Linux (Kitsuy)~~: cancelado pelo usuario em 2026-09-29.
  - **Build do zero:** Kitsuy so conseguiu compilar trocando a pasta `source` pela do RGE 1.6.13 dele (pedia
    `CMakePresets.json`) e voltando depois. Conferir que clone limpo + presets compila sem cache antigo.
    **2026-09-29:** clone limpo da `main` + `cmake --preset linux-editor -S source` configurou e compilou
    RangeEngine e RangeRuntime (2858/2858, sem erro) em Ubuntu 24.04; player abriu demo. Causa provavel: a doc
    mandava usar a branch `linux-sync` (106 commits atras); doc corrigida e branch apagada. Falta o Kitsuy
    confirmar com clone novo.
  - **`setHalfAnimations(1)`:** Kitsuy confirmou sem crash no Linux e no Windows; reconferir no build proprio.
  - **Zip Windows 0.4.4 com `\` nos caminhos** (extraido no Linux sai sem pastas): refeito em 2026-09-29 com `/`
    (Python `zipfile`), extraido e identico ao staging. Falta abrir os `.exe` da copia extraida e subir o asset
    (`gh release upload --clobber`). Nao usar `Compress-Archive` do PowerShell 5.1.
- **API float/int/bool do Kitsuy** (`KX_GameObject` com `m_float1..9`, `m_int1..9`, `m_bool1..9`, enviada em
  2026-09-29): nao integrada. Nomes genericos e limite fixo; perguntar o caso de uso e, se valer, propor
  propriedades tipadas com nome ou um vetor `own.data`.
- **Nao sao bugs (Kitsuy):** carro precisa do modo de frame rate fixo (duas atualizacoes de fisica a mais para
  as rodas); iluminacao estranha era o ajuste de environment lighting do jogo dele.

- **Pacote 0.4.0 quebrado no Linux** (`libpython3.11.so.1.0` nao encontrado; tooltip crasha o editor) —
  **ambos corrigidos e validados em Linux nativo 2026-09-21** (RUNPATH `$ORIGIN/lib`, e use-after-free de
  `ARegion` em `wm_tooltip.c` corrigido + testado em sessao grafica real; "Python Tooltips" agora vem marcado
  por padrao para exercitar o caminho de codigo, ver `linux-build.md`/`changelog.md`). A `linux-sync` foi
  testada no Linux pelo usuario em 2026-09-21 ("tudo ok"). **Pacote 0.4.1 publicado e corrigido em
  2026-09-22**: release anterior só continha `RangeEngine` (bug em `tools/linux/package-runtime.sh`, faltava
  `RangeRuntime`); script corrigido, os dois presets recompilados/reempacotados juntos e o asset do GitHub
  Release `v0.4.1` atualizado via `gh release upload --clobber`. Testado localmente com sessão gráfica real:
  `RangeEngine` abre sem erros e `RangeRuntime` carrega um `.range` de exemplo, detecta GPU/OpenGL (Mesa Intel
  RPL-P, OpenGL 4.6) e renderiza sem erros. Teste feito na própria máquina de build. **Máquina limpa testada em
  2026-09-26** (container Ubuntu 24.04 mínimo): o 0.4.1 não acha a stdlib do Python fora da máquina de build;
  `package-runtime.sh` corrigido e o editor renderiza com Cycles no container. Release `v0.4.2` corrigido
  publicado em 2026-09-26 (editor + runtime); `v0.4.3` Linux publicado em 2026-09-27. Janela testada num Ubuntu 24.04 limpo em 2026-09-28 (container, Intel Mesa; ver `linux-build.md`). Lista de pacotes de runtime em `linux-build.md`.
- **Cycles no editor Linux**: ligado no preset `linux-editor` com Embree 4, CUDA e OpenCL; CPU testada pela
  interface (com e sem Embree) e CUDA (RTX 5060, sm_120, CUDA 13.0) testada pela interface (2026-09-26).
  CUDA no Windows (CUDA 13.4, sm_120) testado pela interface, render e bake (2026-09-26).
  OpenCL no Windows (RX 6800M) testado pela interface e em `-b`, render e bake (2026-09-26).
  Pendente, sem maquina Linux com GPU AMD disponivel: testar OpenCL no Linux. O WSL nao serve (nao expoe
  o OpenCL da AMD); precisa de Linux instalado (dual boot ou pendrive). Se um usuario Linux com AMD
  aparecer, pedir o teste. Roteiro: Preferences > System > Cycles
  Compute Device = OpenCL, marcar a GPU AMD; Render Device = GPU Compute; renderizar a cena padrao e fazer
  bake de AO (chao sob cubo) comparando com a CPU. O primeiro uso compila o kernel OpenCL e pode demorar
  varios minutos. Cubins CUDA para sm_75/sm_86/sm_89/sm_120 (RTX 20/30/40/50) no release desde 2026-09-26;
  so sm_120 testado em hardware real. OSL fica desligado (sem pacote no Ubuntu
  24.04; exige OSL 1.9 com LLVM antigo).
- Portar `WITH_OPENCOLORIO` (API 1 → 2.x, dezenas de call sites em `intern/opencolorio`) e `WITH_CODEC_FFMPEG`
  do editor para OpenColorIO 2.x/FFmpeg 5+. Só necessário fora do container 22.04 (Ubuntu 24.04+ só tem OCIO
  2.x): o container usa a OCIO 1.1.1 do apt desde 2026-09-30. FFmpeg segue desligado; só o wrapper `audaspace`
  do FFmpeg foi ajustado.

### Cutscene nativo

Fases 0–2 e 4–5 implementadas; validação manual (Play → Stop → Play e standalone) aceita em 2026-09-20.
Aberto: Fase 3 (ícones PNG próprios, sem substituir os `ZOOMIN`/`ZOOMOUT`). Ver
[plano](cutscene-native-integration-plan.md) e [roteiro](cutscene-native-example.md).
Evento Camera Path (2026-09-30): falta relinkar `RangeEngine` e o usuário testar no jogo. Export/import JSON cobre
os 18 tipos de evento (schema 2) e o Wait Trigger é liberado por mensagem ou `scene.release_cutscene_trigger()`
(branch `cutscene/events`, 2026-10-04, testes headless no Linux passaram; falta o usuário testar no Windows/jogo
real). Pendente: liberar por propriedade (decisão em aberto, ver [notas](notes-cutscene-events.md)).

### World Status

Causa raiz achada e corrigida em 2026-09-20 (o World do `startup.blend` não passava por `BKE_world_init`); as oito
propriedades aparecem em `scene.world.properties` num File > New. Painel Global Properties aceito pelo usuário na janela
do editor (2026-09-20). Nomes passados para inglês em 2026-09-25 (`horario_sol` virou `sun_hour`); falta o usuário
conferir o File > New na janela do editor. Ver changelog, seções "World Status".

### Animation Events

Revisados em 2026-09-25 (crashes, threads, sensor, painel; ver changelog). Testes headless do editor e do runtime
passaram. Falta o usuário validar o painel na janela do editor e um jogo real com Animation Events (callback Python
e sensor Animation Event).

### Vehicle System / Vehicle Lab

[Plano 2](vehicle-system-plan-2.md): Fases B (direção em graus, direção sensível à velocidade, freio de mão,
volante visual), C (`has_drive`, torque/RPM, gearbox automático/manual) e A (`vehicle_com_offset` via compound
shape) já estão no código desde o snapshot 28775369. Falta validar cada uma no jogo real (usuário). Fase D
está fechada. O componente do demo `Vehicle` foi sincronizado com a versão com gearbox em 2026-09-24.

### Destruição e explosões

Plano aprovado em 2026-09-29; F0 (DNA, RNA e painéis), F1 (Generate Fragments), F2 (quebra por colisão e `shatter()` no runtime), F3 (`scene.explode()`, pavio, impacto, cadeia, Effect e `detonate()`), F4 (Max Debris, `onBreak`/`onExplode`, impulso por massa nos pedaços) e F5 (demo em `source/release/demos/Destruction/`, API no `.rst`) prontas; falta o usuário jogar a demo e ajustar a sensação: objetos
pré-fraturados (Cell Fracture) e explosivos, com os painéis Destruction e Explosive na aba Physics e
`scene.explode()`, em fases F0–F5. Protótipo Python validado por teste automático no runtime
0.4.5 (fora do git, em `tools/ADD na engine anastacioEngine/`).

### Deformação por impacto

Implementada em 2026-10-02 (painel Deformation, `KX_DentDeformer`, `dent()`/`resetDent()`; ver changelog). Falta validar no
`RangeRuntime` com `tools/create_dent_test.py` e ajustar a sensação numa cena real (lataria de carro). Possível v2: máscara de
amassado na cor de vértice para o material misturar tinta arranhada.

### Câmera: foco, rastreio e Camera FX

Implementado em 2026-09-29 (fases 1 a 5 do plano original); referência em [camera-fx.md](camera-fx.md).
Validado no `RangeRuntime` com `tools/create_camera_fx_scene.py` (foco por propriedade, Drone, shake, fallback
após remover o alvo, efeitos desligados em jogo). Pendente: conferência visual dos filtros e custo medido
(`tc_filters2d`) no Rolima Racer; troca dos scripts do jogo fica para quando o usuário decidir.

### Logic Bricks → Python Component

Fase 1 pronta em 2026-09-30: botão **To Python** no header do Logic Editor (`logic.convert_to_component`,
`bl_operators/logic_to_python.py`) gera `<objeto>_logic.py` com um `KX_PythonComponent`, registra no objeto e
desativa só os bricks convertidos. Suporta Always, Keyboard, Mouse (botões, roda, movimento), Property sensor;
And/Or/Nand/Nor/Xor/Xnor; Motion simples, Property (Assign/Add/Toggle/Copy), State, Message; estados e pulsos.
Validado com `tools/create_logic_convert_scene.py` (mesmo resultado com bricks e com componente). Próximas fases:
- F2 (parcial, 2026-09-30): feitos Collision (propriedade), Near, Radar, Ray (propriedade), Delay (frames),
  Mouse Over, controller Expression, actuators Edit Object (Add/End/Replace Mesh/Dynamics), Scene, Game,
  Visibility; depois Random (mesma cadência, sequência do `random` do Python), Track To (alvo fixo) e
  Sound (Play/Loop Stop/End e ping-pong, via `aud`) e Camera actuator. Controller
  Python fica como brick (já é código). Collision/Ray por material convertidos. Links entre objetos convertidos (sensor/actuator de outro objeto via `scene.objects.get`; actuators com helper do próprio objeto ficam como brick). Message sensor convertido
  via `logic.getMessages` (nova API).
- F3 (2026-09-30): campo Mode no operador: Python Component (padrão), Always + Python (Module) e
  Always + Python (Script). Os dois últimos criam `LC_always` (pulso contínuo) e um controller `LC_state_<n>`
  por estado usado; o código é o mesmo, com `main(cont)` no fim. Mesmo CHECK nos três modos.
- F4 (2026-10-04, branch `logic/convert-f4`, ainda sem merge): Ray por material com x-ray, Collision/Near/Radar de
  sensor ligado de outro objeto, Sound ping-pong e Track To com pai. Validado no build Linux headless com
  `create_logic_convert_scene.py`: CHECK idêntico em bricks e Component; Module/Script iguais entre si e só
  `cam y` difere (-0,03 vs -0,04, já ocorre na main). Continuam bricks, com motivo no changelog: Track To com pai de vértice; sensores Actuator/Animation Event/Movement/
  Ray Gaze/VR Head ligados de outro objeto; actuators de outro objeto que usam helper do componente.
- F5 (2026-10-04, na main): Camera, Constraint, Steering e Mouse Look de outro objeto. Runtime validado no Windows
  (detalhes no changelog); Mouse Look testado à mão com mouse real (bricks e convertido).
- F6 (2026-10-04, na main): Track To com pai, Sound loop/ping-pong/3D, Movement e Animation Event de outro objeto;
  Delay em segundos. Runtime validado no Windows (CHECK idêntico nos 4 modos, `LEFT_AS_BRICK 0`); áudio testado à mão
  (loop recomeça, ping-pong, 3D), cena `tools/create_logic_manual_test.py`.
- Pendente: usuário testar no editor com um objeto real lotado de bricks; decidir se o `cam y` do modo
  Module/Script merece ajuste de ordem; Near/Radar no componente seguem com distância ao centro (a engine usa
  esfera/cone físico) e só enxergam Actor com física, como a engine.

### Android / iOS

Android v1 concluído (2026-09-24): APK/AAB com WebView embutindo o pacote Web, validado em aparelho físico
(carga, desempenho, toque, save, ciclo de vida) e exportado pelo editor. Publicação na Play Console adiada
para o futuro por decisão do usuário. Marcos A0–A5 e critérios em [android-export-plan.md](android-export-plan.md). NDK congelado, reaberto somente
por limitação medida; bloqueios em [mobile-export-plan.md](mobile-export-plan.md). iOS fora do escopo.

- **Sensores (`bge.logic.motion`)**: antecipados por decisão do usuário (2026-09-23) e implementados no runtime Web;
  verificados com sensores emulados (`tools/web/verify-motion.cjs`) e aprovados no aparelho real dentro do APK
  (inclinação e `calibrate()`). `orientation`, taxa (~30 Hz) e latência (1–2 frames) conferidas no APK e no Chrome
  do mesmo aparelho em 2026-09-24.
- **APK WebView mínimo (A0b)**: template em `tools/android/webview-template/` rodando a cena `motion` no
  OPPO Find X3 Pro (2026-09-23): carga offline, WebGL 2, Python e sensores ok
  ([android-manual-tests.md](android-manual-tests.md)). Em 2026-09-24: botão "Tela cheia" escondido, Home/retorno e
  giro de 180° confirmados no aparelho; rotação em paisagem e retrato aprovada (proporção e câmera estáveis ao girar). First Person roda no APK
  (pointer lock do WebView neutralizado; ~60 fps parado, medidas variando). Controle por toque, música e save (IDBFS após fechar o
  app) aprovados. Comparação com o Chrome do aparelho medida (`tools/android/measure-device.py`, 3 rodadas por caso):
  APK 52–56 fps contra 36–45 no Chrome, sem frame acima de 34 ms. Sessão longa (10 min, cena padrão com filtros,
  Galaxy Tab S6 Lite) sem queda de fps nem vazamento (2026-09-24). Frames perdidos a 60 Hz no Find X3 Pro: custo de CPU
  do runtime (~20 ms por frame), não do WebView.
- **Export Android (A3/A4)**: módulo `range_web/android.py`, painel "Android (Range)" no editor e
  `tools/web/package-android.py` geram o APK debug a partir do pacote Web (2026-09-24, verificado no build e no editor
  em modo background). Aceito em 2026-09-24: APK do First Person gerado pelo painel e instalado no Find X3 Pro com
  "Instalar no celular". Release assinado implementado (chave fora do JSON e do git, verificado pelo `apksigner`).
  Release instalado e atualizado por cima no aparelho (v1→v2, mesma chave). Save preservado na atualização (cena `web-save`).
- AAB (2026-09-24): opção no release do painel e `package-android.py --aab`; AAB instalado pelo `bundletool`
  no Find X3 Pro e jogo rodando. Publicar numa faixa de teste da Play Console (conta do usuário) fica para o futuro.
- Controles por toque (A1): caminho em
  [android-touch-controls-plan.md](android-touch-controls-plan.md); T0 (ponte `Module.rangePad` → gamepad 0)
  verificada no navegador; T1 (overlay na página: stick, d-pad e botões, multitoque) verificada no navegador
  com toque emulado; T2 (alvo tecla: layouts `wasd` e `arrows`, origem separada do teclado físico) verificada
  no navegador e aceita pelo usuário no Edge do PC; T3 (layout no painel Web, herdado pelo Android; aviso
  WEB-INPUT-001; mapas `KeyMapping/*.json` do Input System passam a ir no pacote) verificada; T4 com a
  checklist conferida no navegador (`verify-touch.cjs` 25/25) e aprovada no Find X3 Pro (cena `pad`, layouts
  stick e `wasd`) e no First Person com o layout `wasd` (2026-09-24). A1 concluído. Extensão T5 (2026-09-24): layout
  `fps` (segundo stick move o mouse para olhar; botões espaço e clique) e áudio suspenso em segundo plano,
  verificados no navegador e aprovados pelo usuário no Find X3 Pro (APK 0.1.7 do First Person).

### Outros

- **Associação de arquivos**: abrir `.blend` e `.range` direto com os executáveis adequados (instalação/registro
  no Windows, duplo clique).
  Registro/remoção (`-r`/`-u`) e comandos do Registro validados em 2026-09-24; falta somente validar o duplo clique no Explorer.
- **Export presets (RangeArmor)**: falta o teste manual (projeto novo e antigo) do plano.
  `company_name`, `icon_path` e toggles desktop já são gravados por `wm.py`, com extensão do schema
  registrada no plano; a pendência é de validação manual, não de implementação desses campos.
- **Auditoria de `source/blender`**: confirmar ou descartar os candidatos de
  [`relatorio-varredura-bugs-silenciosos.md`](relatorio-varredura-bugs-silenciosos.md), com reprodução,
  correção isolada e teste.
  Reauditoria concluída em 2026-09-24: os 26 itens têm correção ou descarte registrado; a única validação
  ainda manual é GPU-001, que requer uma sessão interativa já aberta para testar `gl_load()`.
- **Loop de tempo (perguntas ao Kitsuy, 2026-09-26)**: (1) em `KX_KetsjiEngine::FrameOver()`, o ramo de
  `m_overframetime < 0` usa `m_deltaTime` (passo lógico) onde o resto usa `m_deltatime` (tempo real): erro de
  digitação herdado ou intencional? Não mudar sem a resposta. (2) `m_timeUnderRate` é `long`: com Max Logic
  Frames = 5 a 60 Hz a conta dá ~0,02 e vira `sleep_for(0ms)`, o loop gira sem dormir. É intencional?
- **Release**: antes da próxima distribuição, declarar se o fork sai como GPLv2-or-later ou GPLv3 e incluir o
  arquivo de licença correspondente na raiz/pacote.
- **Metaball no jogo (futuro, sem pressa)**: hoje o conversor (`BL_BlenderDataConversion.cpp`) ignora
  `OB_MBALL` e a metaball some no Play; a saída é Alt+C → Mesh. Proposta: converter a superfície em malha
  estática ao dar Play, como curva/texto (custo só no carregamento). Versão dinâmica (re-tessellar a cada
  frame) descartada por ora: pesada na CPU; só com caso de uso concreto, de preferência na GPU.

## Performance

- **Profiler da engine (`KX_EngineProfiler`) — feito (2026-10-06):** ver `docs/engine-profiling.md`.
  Opcional, só se fizer falta: painel ImGui com as etapas e `Range.logic.getEngineProfile()`.
- Contadores de render como opção para o usuário final (2026-10-06): `Range.logic.getRenderStats()` já
  expõe draw calls, material binds, light binds, culling, luzes/shadow passes e lógica, e o overlay ImGui
  mostra os mesmos números sob "Show Render Queries". Falta uma apresentação pensada para quem faz jogo
  (hoje o painel é de debug interno): decidir se vira um HUD próprio de FPS + contadores, ligável no painel
  Render, em vez de ficar junto das render queries.
- **Gargalo confirmado (2026-10-06) — uniforms de luz por objeto:** cena de 9 cubos com **um único
  material** deu `materialBinds` 2 e `lightBinds` 9, ou seja um upload por objeto, não por bucket.
  `BL_BlenderShader::BindShadowLamps()` roda dentro de `ActivateMeshUser()`, reenviando
  `GPU_material_bind_scene_lights` (8 luzes × ~11 uniforms) e `GPU_material_bind_shadow_lamps`
  (4 lamps, com 2 `BLI_findptr` lineares cada) com dados que são constantes por camada de luz.
  Só vale para materiais de nós/PBR (`use_scene_lights` liga com `unflightsource[]`).
  Correção planejada: contador de geração de luzes em `RAS_Rasterizer`, subindo só quando
  `ProcessLighting()` recalcula, e o bind sobe para o `Activate()` do bucket. Prova: `lightBinds` cai de
  ~objetos visíveis para ~material binds.
- Culling de sombra com occlusion: em `benchmark.range` (1920x1080, 2026-09-28) `ShadowCulling` custa
  14.3ms (60% do frame; ~13 passadas: 10 Spots + Sun em cascata, occlusion res 128). Com occlusion desligado
  na cena: 0.3ms e FPS 41→59.5 (A/B repetido 2x). `MainRender` é só ~0.5ms (o antigo "MainRender alto"
  era GPU/fill-rate). Proposta: não usar occlusion nas passadas de sombra (`is_shadowbuf`) em
  `KX_Scene::CalculateVisibleMeshes`; câmera principal mantém. Aplicada em 2026-09-28: sombras não usam DBVT (usar DBVT sem occlusion
  sumia com os personagens com skinning); 60 FPS, `ShadowCulling` 0.4ms, `Skinning` normal. Teste visual do usuário OK em 2026-09-28 (sombras dos personagens, sem sumir nem piscar).
- Avaliar folhagem e LOD na cena real; impostor e bake de atlas já existem, o resto pode ser trabalho de asset.
- Navmesh dinâmica: hoje o navmesh é gerado uma vez (`mesh.navmesh_make`). Plano (2026-09-28), passos
  pequenos, cada um compilável e confirmado antes do próximo:
  1. Vendorizar `DetourTileCache/` de `tools/recastnavigation-upstream` + compressor passthrough (CMake,
     `readme-blender.txt`).
  2. Membros novos em `KX_NavMeshObject` (tile cache, alocador, compressor, `m_dynamic`), sem mudar
     comportamento.
  3. `BuildNavMeshTiled()` opt-in (property `dynamic_navmesh`), reconstruindo a partir dos polígonos do próprio
     navmesh com parâmetros de `gm.recastData`; caminho estático intacto, sem DNA nova. Avisos ao usuário:
     no painel (Python, `layout.label(icon='ERROR')`) quando `dynamic_navmesh` existe mas não é booleana,
     quando o modo dinâmico está ligado sem navmesh gerada, e quando há obstáculo sem navmesh dinâmica na cena;
     no console, ao iniciar o jogo, se o build dinâmico falhar e cair para o estático. Tooltip avisa que os
     caminhos podem diferir levemente do estático.
  Passos 1-3 feitos em 2026-09-28 (aviso de "obstáculo sem navmesh dinâmica" fica para o passo 4). Cena de
  teste (plano + caixa): caminhos dinâmicos contornam a caixa e diferem do estático em até ~0.6 de comprimento.
  4. Obstáculos: objetos com `OB_HASOBSTACLE` (raio `obstacleRad`, altura da bbox); remover+adicionar ao mover;
     limpar ao destruir.
  5. `dtTileCache::update` por frame em `KX_Scene::LogicEndFrame`.
  Passos 4-5 feitos em 2026-09-28: `KX_Scene` guarda os objetos com "Create Obstacle" (mesmo sem Obstacle
  Simulation) e as navmeshes dinâmicas; `LogicEndFrame` chama `KX_NavMeshObject::UpdateObstacles` (cilindro
  com raio `obstacleRad` e altura da bbox; remove+adiciona ao mover mais de 0.1; remove ao destruir). Painel
  Create Obstacle avisa quando não há navmesh dinâmica na cena. Teste: cilindro no caminho aumenta a rota
  (17.89 → 18.75) e ela volta ao original quando o obstáculo sai. Segmentos de borda da Obstacle Simulation
  continuam os do build inicial.
  6. `KX_SteeringActuator` refaz `findPath` quando o navmesh mudar (contador de versão).
  Passo 6 feito em 2026-09-28: `KX_NavMeshObject::GetVersion()` sobe quando a navmesh é reconstruída ou
  quando os tiles terminam de mudar; o Steering refaz o caminho se a versão mudou, mesmo com update period -1.
  7. Python (`dynamic`, `rebuild()`, `addObstacle`/`removeObstacle`) + docs. DetourCrowd fica para depois.
  Passo 7 feito em 2026-09-28: `KX_NavMeshObject.dynamic` e `.version` (só leitura),
  `addObstacle(object, radius=0.0)` e `removeObstacle(object)`; raio automático usa o "Create Obstacle" ou
  metade da bbox. Teste visual do usuário OK em 2026-09-28: painel, console, cilindros amarelos do `draw()` e
  agente com Steering contornando obstáculo em movimento. Aviso de Create Obstacle sem navmesh dinâmica não foi
  visto na tela.
  Riscos: perda de precisão nas bordas, atraso de alguns frames, ponteiros de objetos destruídos.

## Iluminação e gráficos

- **Luz indireta (GI) baked:** lightmap Cycles + OIDN + light volume prontos (changelog 2026-10-06).
  GTAO no lugar do SSAO legado no desktop. FPS e objeto móvel medidos (desktop e iGPU). Falta:
  validar no Linux e no build Web; opcional SSGI (fase 4). UV da lightmap por xatlas.
- **Compatibilidade UPBGE 0.2.5b adiada:** ao abrir um `.blend` dessa versão, migrar somente quando
  `upbgeversionfile != 0` e o arquivo ainda não tiver versão Range. Há duas conversões verificadas que não
  devem ser misturadas à correção dos Mouse Logic Bricks: (1) em `World.skytype`, mover `Sky Texture` do bit
  `1 << 3` para `WO_SKYTEX` (`1 << 5`) e `Zenith Up` do bit `1 << 4` para `WO_ZENUP` (`1 << 6`); (2) em
  `Lamp.shadow_filter`, converter PCF `1 → 3`, PCF Bail `2 → 4` e PCF Jitter `3 → 5`, pois Range inseriu
  Clipping e Dithering antes desses filtros. Comparação feita contra `tools/arquivo_upbge.blend` na UPBGE
  oficial 0.2.5b e o source `tools/upbge-0.2.5b-source/`.
- **Sombra em materiais Principled/PBR no `BLENDER_GAME` — funcionando** (validado em 2026-09-23 no
  `projects-teste/pbr-baseline/shadow_ibl_test.range`): shadow map simples (sem CSM/VSM) nos 3 primeiros slots
  de luz, com Point/Spot corretos (direção, atenuação, cone) e loop de até 8 luzes. Ver changelog de 2026-09-23.
  Pendente, opcional: comparar lado a lado com material legado sob as mesmas luzes (o chão satura com energia
  somada 5,6 e a sombra fica fraca) e ver o efeito de `ProcessLighting(true)` agora rodar para todo material com
  nodes em uma cena maior. Diffuse/Glossy/Toon usam o mesmo loop desde a Fase 3 (abaixo).
- **Nós de material Game × Cycles × BI** (matriz em [node-material-support.md](node-material-support.md)):
  Fases 1 (correções GLSL, World como ambiente), 2 (selos `~Game`/alerta no editor) e 3 (Diffuse/Glossy/Toon no
  loop de luzes do Principled) feitas em 2026-10-01; Fase 4 (Glass/Refraction com fresnel + World,
  reflexo no Glossy, Toon Glossy, AO por concavidade local, Blackbody, Wavelength, Sky Preetham). Fase 5
  (Filmic/exposure/gamma de Color Management aplicados na saída do material nodes, aproximado) feita em 2026-10-01. Fases 3 a 5
  validadas pelo usuário em 2026-10-02 (`tools/create_node_phases_test.py`). Tangent e Anisotropic BSDF de verdade em
  2026-10-02; Holdout, Translucent, Velvet e Subsurface (aproximados) em 2026-10-02. Wireframe no Game em 2026-10-02 (vértices sem compartilhamento + `gl_VertexID % 3`). Refração screen-space no Glass/Refraction e Transmission do Principled (Alpha Blend) em 2026-10-02. Hair BSDF e Principled Hair BSDF (R, TT, TRT e absorção do Cycles, aproximados) validados pelo usuário em 2026-10-02 (`tools/create_hair_bsdf_test.py`). IES Texture nas lâmpadas Point e Spot (`tools/create_ies_test.py`) e nós de volume (Absorption, Scatter, Principled; `tools/create_volume_test.py`) em 2026-10-02, validados pelo usuário em 2026-10-02 contra render do Cycles (o Principled não ilumina o entorno como no Cycles); atenuação da Spot no Game PBR igual à do Cycles em 2026-10-02; Point Density e Script ficam sem suporte. Fase 6 decidida em 2026-10-01: o BI fica como está (Game legado segue com os nós do BI, sem migração).
- **Material rápido (receitas de nós, 2026-10-02)**: painel Quick Material com pacote de texturas, mistura por
  máscara RGB e materiais prontos (ver changelog). Falta o usuário conferir no editor e no jogo
  (`tools/create_material_recipes_test.py`, PBR e `legacy`). Normal e rugosidade por camada feitas (botão de pasta). Próximos: mistura pela
  altura e Texture Array (só se 8+ camadas).
- **Principled/PBR no Web**: luzes de cena e sombra portadas para o perfil CORE (`unflightsource[]`, changelog de
  2026-09-23); aceite visual do usuário no navegador com GPU real em 2026-09-23 (brilhos das luzes e sombras
  das esferas corretos). Falta só reconferir o desktop.
- Sombras (`gpu_lamp_wants_shadow` em `gpu_material.c`): com Shading Nodes, Sun, Spot e Point seguem o
  `Cast Shadow` do Cycles (Point por atlas de cubo 3x2, 2026-10-01, validado pelo usuário); sem Shading Nodes,
  Sun e Point exigem `RAY_SHADOW` e Spot `BUFFER_SHADOW`. Sombra da Point nos materiais BI (Game, standalone e
  viewport) em 2026-10-02, validada pelo usuário. Viewport com engine Game e materiais em nós usa as lâmpadas
  da cena e as sombras delas (como o Game) desde 2026-10-02, validado pelo usuário; IES e Wireframe no viewport,
  sombra da Point com borda suave (3x3) e 4 luzes com sombra em 2026-10-02.
- **Light probes**: reflection probe local feito em 2026-10-01 (propriedade `probe` num objeto, ver changelog);
  validado pelo usuário em `probe_reflection_test.range`. Luz difusa local (amostras do mesmo cubemap) e World em nós
  capturado num cubemap em 2026-10-02, validados pelo usuário. Paralaxe por esfera do raio do probe em 2026-10-02. Mistura entre probes vizinhos (e com o World na borda) em 2026-10-02. Paralaxe por caixa (Empty desenhado como Cube) em 2026-10-02, validada pelo usuário. Recaptura do World quando o sol ou as cores mudam, e Sky Texture seguindo o World Sun, em 2026-10-02, validadas pelo usuário em `sky_follow_sun_test.range`. Mistura entre probes validada em `probe_blend_test.range`.
- **Resolução dinâmica**: opt-in em `Game Render Properties > Dynamic Resolution`; validada em cena GPU-bound
  (aceite de 2026-09-20).
- **CSM**: blend entre cascatas e debug tint já implementados; falta medir o custo de GPU dessas duas features.
- Avaliar antialiasing temporal somente com caso de uso e critérios de qualidade definidos.
- Aceitos como no-op no core profile (reabrir só com demanda concreta): motion blur legado e texto de
  debug via `BLF_draw` (o clipping de espelho/água foi resolvido com projeção oblíqua em 2026-09-28).

## Validações manuais pendentes

- Tesla Rhythm: avaliar overlay, enquadramento e latência percebida no jogo real;
  [modo de cinco pistas via Python Component](tesla-rhythm.md) passou sonda no runtime.

Aceitas pelo usuário em 2026-09-20 e removidas daqui: sombras no jogo real (Planos 1A e 5, múltiplas luzes),
migração de `maxphystep`, Sol/Lens Flare, splash e About, Outliner, barra da 3D View, aba Particles, gamepad no
menu ImGui e Runtime Property Sensors/Actuators. Aceitas em 2026-10-02: os itens de 2026-09-25 (Game Settings,
FXAA, LOD, Foliage no Web, Shader Sources, painéis Transparency, Options e Subsurface, Asset Browser) e as
categorias `CollisionDepth`/`TextureRenderers` do Profiler em linhas próprias. O stress de captura de vídeo e
OpenAL foi cancelado por decisão do usuário.

## Fora do escopo atual

- Paralelização ampla do loop principal e remoção do GIL de Python.
- Atualização completa do Bullet apenas para obter solver multithread.
- Edição de cena durante o jogo com persistência automática.
- Reimplementação de recursos herdados listados no relatório de melhorias.
