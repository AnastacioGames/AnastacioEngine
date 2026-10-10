# Complemento Steam: inventário e decisão da etapa A

Data: 2026-10-07. Inventário executado; ABI e carregador B1 implementados e validados
em Windows/MSVC. Transporte, salas e componente foram implementados depois do inventário;
o estado validado está no [guia de desenvolvimento](steam-complement-development.md).

## Evidência no jogo real

`build/bin/RangeEngine.exe --background` abriu
`D:/ProjetoRolimaRacer/RolimaRacer.range` e consultou os componentes com `bpy`,
sem salvar nem executar gameplay. Processo encerrado com código 0.

| Cena / objeto | Componente anexado |
|---|---|
| `0_SCN_System` / `CAM_UI` | `scripts.SteamComponent.SteamComponent` |
| `0_SCN_System` / `CAM_UI` | `scripts.NetworkManager.NetworkManager` |
| `_network_menu` / `NetMenuAnchor` | `scripts.net_menu.NetworkMenu` |
| `Kits` / quatro colliders de veículos | `scripts.VehicleSystem.NetworkVehicleSync.NetworkVehicleSync` |

O SteamComponent inicializa Steam, bombeia callbacks, consulta idioma e oferece
conquistas. A rede atual usa a sessão nativa. No git do jogo, SteamNetworkManager
está removido na árvore de trabalho e NetworkManager/net_menu ainda não rastreados;
o histórico confirma a implementação Steam anterior. Preservar essa migração.

SDK encontrado em `D:/ANASUTASHIO_GAMES/Documentos Da Steam/steamworks_sdk_155/sdk`.
O arquivo de desenvolvimento do jogo contém AppID **480** (Spacewar), portanto
não comprova disponibilidade do AppID comercial do RolimaRacer. Não copiar SDK
para o repositório. Acesso ao AppID comercial e duas contas de teste ainda precisam
ser confirmados antes da prova externa.

## Local do componente e exportação

Proposta: pacote `source/release/scripts/modules/anastacio_network/`, com
componente `AnastacioNetworkComponent` e menu reutilizável. Imports de rede/ImGui
ocorrem no ciclo de execução, pois o editor importa componentes usando um Range
temporário em `blenkernel/intern/python_component.c`.

O install de `source/source/creator/CMakeLists.txt` já distribui `release/scripts`.
O exportador legado `game_engine_save_as_runtime.py` copia scripts somente quando
essa opção está habilitada: incluir o pacote necessário de forma explícita nos
exportadores suportados e validar import no pacote extraído. Não presumir que a
instalação do editor basta para tornar o módulo disponível no jogo exportado.
O exportador efetivamente usado pelo RolimaRacer ainda deve ser identificado.

## Complemento nativo e ABI proposta

Não foi encontrado registro de transportes carregáveis em gameengine. Hoje
`KX_NetworkManager.cpp` cria ENet/WebSocket diretamente. Adicionar ponte genérica
opcional; engine comum não inclui headers ou links Steamworks.

DLL proposta: `AnastacioSteam.dll`, carregada de diretório explícito do complemento,
sem busca arbitrária no PATH. Export único versionado `AnastacioSteam_GetApi`.
ABI C com tipos de largura fixa, tamanho de tabela, versão e handles opacos;
nenhum `std::string`, `std::vector`, exceção ou classe C++ atravessa a DLL.
Chamador fornece buffers de leitura/erro; cada lado libera o que aloca. Rejeitar
versão/tamanho incompatíveis antes de chamar funções.

Tabela inicial: criar/destruir contexto, inicializar/encerrar runtime, consultar
estado/identidade e bombear callbacks. Transporte e matchmaking entram em etapas
posteriores com versionamento. Descarregar somente após fechar conexões, descartar
callbacks e destruir todos os contextos. Web não compila nem carrega essa ponte.

Uma entidade da engine por processo controla inicialização, callbacks e shutdown.
O componente de jogo adquire o serviço, sem inicializar outra cópia. A migração
do SteamComponent deve preservar conquistas/idioma antes de remover seu init;
não ativar os dois donos simultaneamente. A forma de distribuição continua sujeita
à revisão dos termos Steamworks e licença da engine prevista no plano.

## Contrato do transporte

`NET_ITransport.h` já oferece listen/connect/send/poll/disconnect/shutdown.
`PeerId` é uint32 local; SteamID é uint64 separado, exposto em Python sem conversão
para float e em metadados como decimal. Handles SDK não viram ClientId.

| Canal | Entrega proposta |
|---|---|
| Control (0) | Confiável, ordenada no próprio canal |
| Rpc (1) | Confiável, ordenada no próprio canal |
| Snapshot (2) | Não confiável; sessão descarta estado antigo |
| Input (3) | Não confiável; protocolo trata ticks/redundância |

O SDK local possui `ConfigureConnectionLanes` e `m_idxLane`: usar quatro lanes,
com envelope contendo versão e canal para recepção; não depender de lane recebida
como identificador de canal. `reliableAll()` retorna false. Preservar limites
nativos: 1200 bytes não confiáveis e 65536 confiáveis, mais envelope do complemento.
Proposta de orçamento inicial: 256 mensagens / 1 MiB por poll e 4 MiB enfileirados
por peer; excesso encerra conexão com erro, sem descarte silencioso de confiáveis.
Esses valores devem ser medidos na prova de transporte.

Connect recebe SteamID decimal e porta virtual; seleção explícita Steam no
manager, sem passar essa identidade ao resolvedor ENet. Listen cria socket P2P.
Somente o evento de conexão SDK abre o handshake nativo. Lobby não implica sessão
pronta. Callbacks produzem eventos enfileirados na thread principal; sem bombeamento
duplo por componente. Auditar loading antes de prometer progresso durante bloqueios.

## Próxima peça verificável

Etapa B1 concluída: ABI e carregador genérico, ainda sem Steam SDK. DLLs de prova exercitam
versão incompatível, biblioteca ausente, init/shutdown e descarregamento; validar
build e execução nativos. Não alterar gameplay nem selecionar novo transporte.
Depois da revisão, B2 adiciona inicialização real no complemento com o SDK local.
Steam comercial/relay continuam pendentes da prova com duas contas em redes distintas.

Implementação: `NET_AnastacioPluginABI.h`, `NET_AnastacioPlugin.h` e
`NET_AnastacioPlugin.cpp` em `source/source/gameengine/Network/`. Testes em
`tests/NET_AnastacioPlugin_test.cpp` e `tests/AnastacioPluginFixture.cpp`.
Tabela incompleta, versão/tamanho incompatíveis, caminho relativo/ausente,
falha de init, callbacks, identidade uint64 e recarga são cobertos. A DLL de prova
aborta se for destruída antes de shutdown ou bombeada antes da inicialização.
Carregador excluído no CMake Web; não houve build Web nesta etapa.
Atualização B2: serviço por processo anexado ao ciclo da engine e API Python implementados;
complemento SDK separado compilado. Testes offline e online no player passaram;
init, identidade, callbacks e reinit com conta conectada confirmados no AppID 480.
Instruções e limites em [desenvolvimento local](steam-complement-development.md).

Arquivos previstos: novos contratos/carregador em `source/source/gameengine/Network/`,
CMake desse módulo, ponte em `Ketsji/KX_PyNetwork.cpp` e dono do serviço no runtime.
Transporte posterior modifica também `KX_NetworkManager.*`; componente/menu entram
no pacote Python acima. A localização final do projeto CMake separado do complemento
deve ser definida ao fechar sua distribuição.
