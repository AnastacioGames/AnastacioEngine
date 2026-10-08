# Complemento Steam: desenvolvimento local

Primeira plataforma: Windows x64. O complemento é opcional e fica separado do build
normal da engine. SDK oficial local necessário; não versionar o SDK nem seus binários.
O projeto CMake está em `source/complements/anastacio_steam/`.

No mesmo processo configurado por `vcvars64.bat`, com `VSLANG=1033`:

```text
cmake -S source/complements/anastacio_steam -B build-steam -G Ninja -DCMAKE_BUILD_TYPE=Release -DANASTACIO_STEAM_SDK="caminho/do/sdk"
cmake --build build-steam
```

O build local gera `AnastacioSteam.dll` e copia `steam_api64.dll` para o mesmo
diretório. O complemento usa CRT estático; buffers/contextos são liberados pelo
lado que os criou. Não instala essas DLLs no pacote comum da engine.
Isto não é um release; publicação e revisão de licenças permanecem pendentes.
O carregador usa ABI **v2**; reconstruir complemento e engine juntos ao atualizar o contrato.

## API durante o jogo

```python
from Range.network import steam

steam.initialize("D:/meu-complemento/AnastacioSteam.dll", 480)
state = steam.status()  # loaded, ready, steam_id (int sem perda de precisão)
steam.shutdown()
```

As sessões existentes aceitam seleção explícita de transporte:

```python
from Range import network
network.host(port=7777, transport="steam", websocket_port=0)
network.join("7656...:7777", transport="steam")  # SteamID real do host, não IP
```

`port` é virtual na Steam. ENet continua sendo o padrão de host/join.
Salas usam portas virtuais de 1 a 65535; zero continua reservado à configuração
de cena na API nativa, portanto não é aceito como porta publicada de lobby.
O adaptador mantém Control/Rpc confiáveis em lanes independentes e Snapshot/Input
não confiáveis; payload ANET e handshake são os mesmos da rede nativa.
`steam.shutdown()` rejeita descarregamento durante uma sessão Steam; desconectar antes.

Operações de sala são assíncronas: `create_lobby`, `list_lobbies`, `join_lobby`,
`leave_lobby`, `invite_friends` e `set_joinable`. Consumir `poll_events()` ou usar
o componente pronto abaixo. Eventos: criado (1), entrou (2), item da lista (3), fim
da lista (4), convite (5), erro (6), host saiu (7). Sala não equivale a handshake concluído.
Filtros incluem jogo/build/protocolo; IDs permanecem inteiros de 64 bits.
Invites abertos usam callback Steam; lançamento fechado usa `+connect_lobby` do SDK.
Esses dois fluxos de convite ainda precisam do teste com uma segunda conta.

`steam.force_relay(True)` desabilita ICE direto antes de abrir transportes.
`steam.connection_routes()` consulta a rota reportada pelo SDK por conexão: `direct`,
`relay` ou `unknown`. Sala criada, flag configurada ou lista vazia não comprovam relay.
`steam.language()` e `steam.achievement(name, unlock=False)` compartilham o mesmo runtime.
Persistência real de conquistas depende do AppID/schema e ainda não foi validada no jogo comercial.

## Componente entregue pela engine

Anexar `anastacio_network.component.AnastacioNetworkComponent` a um objeto.
O pacote está em `source/release/scripts/modules/anastacio_network/`, instalado
em `2.79/scripts/modules/`. O player adiciona esse diretório antes de importar componentes;
o editor remove imports feitos com Range temporário para evitar bases de classe inválidas no Play.

Argumentos: `enable_steam`, `steam_app_id`, `steam_dll`, `game_id`, `build`,
`default_port`, `max_players`, `force_relay`, `enable_lan` e `open_on_start`.
Steam vem desabilitada e AppID vem 0 por padrão; configurar por projeto.
O menu ImGui oferece host, salas/lista/convite, LAN/IP, pronto, chat, iniciar e sair.
Regras de jogo usam os hooks `connected()` / `start_match()` ou a API nativa de eventos.
UI e estado de sessão são separados. Fechar um overlay não encerra a sessão.

O jogo pode chamar `component.show()` / `hide()` para abrir/fechar o menu, inclusive
durante uma partida. Para conservar a sessão ao terminar, o host chama
`component.return_to_lobby(nome_da_cena)` ou `controller.return_to_lobby(nome_da_cena)`.
A cena muda pela rede nativa; só depois de carregar no host a sala reabre, a prontidão
é zerada e `Range.network.on_lobby` avisa os clientes. Sem argumento, o retorno é imediato
e o jogo assume a escolha da cena. `Range.network.return_to_lobby()` é a operação nativa
somente do host; usar o controlador também atualiza a sala Steam. Sair da partida com
`leave()` continua encerrando a conexão e deixando a sala, sem conservá-la.

Cada controlador precisa de **um único responsável por `tick()`** durante o jogo.
No componente genérico é o próprio menu, que deve permanecer em um objeto persistente,
mesmo quando oculto. No RolimaRacer o SteamComponent ativo é persistente e processa o
controlador mesmo sem overlay; NetworkMenu usa o fallback apenas na ausência desse
responsável. Callbacks do SDK continuam exclusivamente no frame nativo da engine.

Convites durante uma sessão pedem confirmação antes de desconectar. Chat usa nomes;
host LAN mostra IPv4 locais e porta (não descobre IP público nem configura NAT).
O campo de capacidade é um slider de 2 a 64; a validação do controlador permanece.
O nome do jogador só é escrito na API quando editado.

No complemento Windows, o convite de abertura usa também os argumentos reais do
processo, além de `GetLaunchCommandLine`; o evento chega ao menu sem entrada automática.
O parâmetro segue a [documentação Steam de convites](https://partner.steamgames.com/doc/api/ISteamMatchmaking#InviteUserToLobby).
Cancelamento/timeout retiram CCallResults e liberam a próxima operação. Isso não cancela
a operação no backend: resultados tardios de criação/entrada são recolhidos separadamente
para sair de salas abandonadas. No máximo 64 resultados abandonados ficam acompanhados;
sem resposta após esse limite, a API pede reconexão, em vez de crescer sem limite.
Eventos de desconexão são preservados; novas admissões aguardam quando a fila está cheia.
Snapshot/Input descartam números antigos por lane, além dos filtros nativos por tick.
A conexão de um membro cuja atualização ainda não chegou espera até 3 segundos antes
de ser recusada; essa condição ainda precisa de teste entre contas.

RolimaRacer: `scripts/net_menu.py` é um adaptador do componente da engine;
`scripts/network_settings.py` guarda AppID/build/configuração. SteamComponent usa
o serviço compartilhado para idioma/conquistas e NetworkManager mantém regras de pista.
Os binários de desenvolvimento foram instalados em `D:/ProjetoRolimaRacer/complements/steam/`.
O `.range` original e o sistema de veículos não foram alterados nesta integração.

## Exportar o complemento opcional

No exportador nativo legado, **Steam Complement Folder** vazio gera o pacote LAN/IP.
Selecionar a pasta das duas DLLs inclui `complements/steam/`. O pacote Python reutilizável
é incluído mesmo com Copy Scripts desabilitado. Python completo e `blender.crt/`
são copiados pelas opções correspondentes; AppID de desenvolvimento não é copiado automaticamente.
O player padrão do exportador agora é RangeRuntime, e o timer usa perf_counter no Python atual.
RangeArmor/Web não receberam um novo seletor Steam nesta etapa; em export nativo compatível,
usar o instalador explícito abaixo quando o exportador não tiver essa opção.

```text
python tools/install_steam_complement.py --target pasta-do-jogo-exportado --complement build-steam
```

`--appid 480` é opção somente para desenvolvimento e cria o arquivo de AppID explicitamente.
Para testar Play no editor sem instalar o AppID ao lado do executável compartilhado,
iniciar o editor com diretório de trabalho igual ao projeto que contém `steam_appid.txt`.
No RolimaRacer, `anastacio_steam_editor_dev.bat` faz esse lançamento usando build/bin;
um caminho alternativo de editor pode ser fornecido como primeiro argumento.
O SDK identifica o AppID real pelo lançamento/arquivo; o componente verifica se coincide.

AppID é configurado pelo jogo. A Steam deve estar aberta e conectada; o AppID
selecionado pelo lançamento Steam ou `steam_appid.txt` de desenvolvimento precisa
coincidir com o argumento. O arquivo de desenvolvimento não pertence ao depot publicado.
A implementação não altera variáveis SteamAppId nem relança o editor.

Inicialização lança RuntimeError em biblioteca ausente, contrato incompatível,
serviço já carregado, Steam fechada, falha do SDK, conta indisponível ou AppID
divergente. Valores inválidos de AppID são rejeitados antes de carregar a DLL.
`status()` permanece disponível sem biblioteca; `shutdown()` é idempotente.
Web informa indisponibilidade e não inclui o carregador nativo.

O serviço é único no processo e pertence ao ciclo de jogo da engine. Todas as cenas
compartilham o serviço; não iniciar outro SDK pelo SteamComponent antigo. A migração
de conquistas/idioma do RolimaRacer foi adaptada para compartilhar o serviço;
a validação no AppID comercial ainda está pendente.
Callbacks são bombeados uma vez por `NextFrame`; um carregamento síncrono que bloqueie
essa função ainda bloqueia callbacks. Não prometer bombeamento durante tal bloqueio.
StopEngine libera o serviço depois de destruir componentes; o destrutor também limpa.

## Verificação no player

`tools/net_engine_test/steam_runtime_test.py` é um smoke test para cena mínima,
executado pelo Python main loop (`RangeRuntime --server -p script cena.range`).
Variáveis: ANASTACIO_STEAM_FIXTURE (DLL de prova B1), ANASTACIO_STEAM_DLL (complemento)
e ANASTACIO_EXPECT_STEAM (`online`, `offline` ou `auto`).
Executar de uma pasta de desenvolvimento com AppID configurado.

O teste verifica API, IDs inteiros, callbacks por frame, inicialização duplicada,
shutdown, falha real do SDK ou sessão online e limpeza no encerramento da engine.
Confira `STEAMTEST PASS` no log `range_runtime.log.txt` do TEMP: o player não propaga
falhas Python pelo exit code. O teste não imprime a identidade da conta.
Online requer Steam conectada; offline e DLL de prova não comprovam conexão real,
transporte, salas ou relay. Esses itens continuam no plano multiplayer.

Validado em 2026-10-07: Windows, SDK 1.55, conta conectada e AppID 480;
smoke test online confirmou init, identidade, callbacks e shutdown/reinit no player.
Não substitui a futura prova de tráfego entre duas contas em redes diferentes.

Validação ampliada Windows (2026-10-07): `net_steam_probe` passou quatro canais nos
limites nativos, handshake, chat, transform/propriedade, spawn/despawn e ownership
por socket pair do SDK com loopback de rede. `steam_lobby_test.py` passou criação,
busca filtrada da própria sala pública, cancelamento e host nativo Steam.
`steam_menu_test.py` passou com componente anexado e ImGui no player.
`steam_game_adapter_test.py` passou com cópias dos scripts do RolimaRacer e troca
de cena mínima; não é prova de carros ou corrida real.
Regressão LAN spawner e CTest da rede passaram.

Exportação foi executada para Steam e LAN, e ambos os players exportados passaram
no smoke test; a variante LAN não contém DLL Steam. Pacote local de teste em
`build-steam/export-smoke.zip` (não publicado). Artefatos e SDK redistribuível locais
ficam ignorados pelo git. O ZIP foi extraído para `build-steam/export-extracted/` e o
Game.exe extraído passou com SDK real e componente anexado. Avaliação visual do usuário
e prova externa continuam pendentes.

Revisão em 2026-10-07: testes locais de política do complemento cobrem argv inválido,
sequenciamento, fila de desconexão e liberação de cancelamento/timeout sem login.
`steam_lobby_test.py` passou nova criação imediatamente após cancelamento, com SDK real.
Dois players ENet em `lobby_return_test.py` passaram duas partidas, retornos e reentrada;
menu Steam passou retorno, segunda partida e sala novamente visível na busca pública
após a propagação dos metadados. Adaptadores do RolimaRacer passaram ida/volta de cenas
mínimas; resolver novamente o componente vivo depois da troca é necessário no teste.
`network_adapter_review_test.py` cobre callback on_start atrasado (início único), responsável
pelo tick, Steam desabilitada, confirmação de convite e nomes no chat.
`steam_cold_invite_test.py` usa um ID fictício nos argumentos e comprova sua entrega ao
componente no player exportado; não é prova de convite real enviado por outra conta.
O ZIP local foi atualizado e extraído em `build-steam/export-final-extracted/`;
executável, DLL e módulos conferidos contra a cópia validada, e o Game.exe extraído
passou a prova de argv. Menu Steam e LAN também executaram com ImGui no player exportado;
os testes verificam execução/estado, sem avaliação visual por captura automatizada.
