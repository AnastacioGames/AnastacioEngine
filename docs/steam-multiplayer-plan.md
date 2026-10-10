# Plano: complemento Steam para multiplayer

Criado em 2026-10-07. Estado: **integração Windows implementada e testada localmente;
prova externa e corrida real ainda pendentes**.

Objetivo: no RolimaRacer distribuído pela Steam, um jogador cria uma sala e os amigos entram pela
lista ou convite, sem compartilhar IP ou configurar encaminhamento de portas. A Anastacio Engine
continua oferecendo sua rede nativa sem exigir Steam ou `steam_api64.dll`.

## 1. Base existente e escopo

Reutilizar sessões, protocolo, replicação, RPC, ownership, relógio, interpolação e predição do
multiplayer nativo. O jogador que hospeda continua sendo o servidor autoritativo; o relay encaminha
pacotes, não executa a simulação. Não prometer predição de veículos Bullet: continua fora da v1.

No RolimaRacer, `scripts/net_menu.py` desenha a interface ImGui e usa a rede nativa;
`scripts/NetworkManager.py` contém regras da corrida e `scripts/VehicleSystem/NetworkVehicleSync.py`
usa replicação nativa. `scripts/SteamComponent.py`, `scripts/steamworks.py` e `steam_api64.dll`
existem, mas a presença deles não comprova transporte Steam ativo. Antes de mudar o jogo, inspecionar
os componentes anexados no `.range` e o histórico da migração; não restaurar o antigo sincronizador
JSON nem o antigo multiplayer em malha.

Primeira entrega: host/jogadores Windows pela Steam, salas públicas ou de amigos, convites,
replicação e fluxo completo de corrida. Linux vem após essa prova. Web/Android WebView continuam
usando WebSocket: não recebem Steamworks nem acesso automático às salas Steam. Cross-play com esses
clientes e servidores dedicados via Steam exigem uma etapa própria.

## 2. Arquitetura proposta

| Camada | Responsabilidade |
|---|---|
| Rede nativa existente | Sessão de jogo, handshake e sincronização |
| Complemento Steam opcional | Inicialização, callbacks, identidade e transporte Steam |
| Salas Steam | Encontrar host, capacidade, versão e convites |
| Menu ImGui | Escolher LAN/IP ou Steam, mostrar salas e estado da conexão |
| RolimaRacer | Escolha de pista, carregamento, spawn e regras da corrida |

**Preferência do usuário: o componente reutilizável é entregue pela engine.** O menu ImGui e
o componente de conexão Steam pertencem aos scripts/componentes distribuídos com a Anastacio
Engine, disponíveis para anexar a um objeto de qualquer jogo. O AppID e as opções da sala são
configurados por projeto. O RolimaRacer mantém apenas suas regras específicas; não precisa
manter uma cópia própria do sistema de salas, transporte ou menu genérico.

Na etapa A, definir o local de instalação e como o exportador inclui o componente e, quando
selecionado, o complemento Steam. A engine padrão pode oferecer o componente/menu e detectar
que o complemento não está instalado, sem exigir `steam_api64.dll` para iniciar. O transporte
e acesso ao SDK são do complemento nativo, não de código de rede duplicado em Python no jogo.

Usar `ISteamNetworkingSockets` do Steamworks SDK para conexões orientadas a handles e
`ISteamMatchmaking` para salas. O núcleo já tem `net::ITransport`; implementar um adaptador que
produza seus eventos `Connected`, `Received` e `Disconnected`, sem alterar o formato dos snapshots.
Sala identifica o host por SteamID; conectar ao host com `ConnectP2P`, que escuta com
`CreateListenSocketP2P`. A porta virtual Steam não é encaminhamento de porta do roteador.

Não basta usar uma sala Steam que divulga o IP ENet: os pacotes do jogo precisam passar pelo
transporte Steam para aproveitar relay. A biblioteca aberta GameNetworkingSockets sozinha não
concede acesso à infraestrutura Valve; para este objetivo, usar a versão do SDK Steamworks.
Fontes: [rede Steam](https://partner.steamgames.com/doc/features/multiplayer/networking) e
[ISteamNetworkingSockets](https://partner.steamgames.com/doc/api/ISteamNetworkingSockets).

### Contratos a fechar antes do adaptador

- Mapear SteamID e handle para `PeerId`, com remoção de conexões antigas e identidade obtida do SDK.
  Representar IDs de 64 bits sem perda, especialmente nos metadados e na API Python.
- Preservar canais lógicos: confiabilidade, ordenação e descarte de snapshots antigos devem
  corresponder ao protocolo atual. Auditar lanes/envelope e limites reais do SDK; não pressupor que
  uma chamada confiável reproduz canais ENet independentes.
- `poll()` não bloqueia; callbacks são bombeados uma vez por frame, inclusive durante loading,
  e apenas enfileiram eventos. Fixar limites por conexão, tamanho e orçamento de fila.
- Sala e conexão são estados diferentes. Entrar no lobby não significa passar no handshake do jogo.
  Versionamento, hash da cena, capacidade e política de entrada tardia continuam sendo verificados.
- Host indisponível encerra a partida com mensagem clara. Migração automática de host fica fora
  desta entrega, mesmo que a Steam transfira o dono do lobby para outro membro.
- Uma única entidade controla `SteamAPI_Init`, callbacks e shutdown. Compatibilizar ou substituir
  a inicialização do `SteamComponent` sem quebrar conquistas; evitar duas inicializações independentes.

## 3. Distribuição opcional

Preferência: complemento carregável, com ponte genérica de transporte na engine e SDK encapsulado
no complemento. Definir ABI versionada, limites de memória e ciclo de descarregamento antes de
implementar; não passar objetos C++ sem contrato entre DLLs. Auditar primeiro se existe mecanismo
de extensões aproveitável no repo. Uma variante de build específica para Steam é alternativa,
caso o carregamento opcional aumente demais o escopo; registrar a decisão antes do código.

Build padrão e export LAN/IP devem iniciar sem SDK ou DLL Steam. Complemento ausente deixa Steam
indisponível no menu; erro Steam não muda silenciosamente para LAN. O AppID pertence ao jogo,
nunca fica fixo como AppID do RolimaRacer dentro da engine.

Pré-requisitos: acesso do desenvolvedor ao Steamworks do jogo, SDK oficial local, AppID e duas
contas autorizadas a testar. Não versionar SDK privado, chaves ou credenciais. Conferir a
compatibilidade da distribuição GPL da engine com os termos do SDK antes de fixar a forma de
empacotamento; uma DLL separada não decide essa questão por si só.

Distribuir somente os redistribuíveis autorizados e compatíveis com a plataforma, nos pacotes
que usam Steam. `steam_appid.txt` é recurso de desenvolvimento e deve sair do depot publicado.
Fonte: [visão geral da API Steamworks](https://partner.steamgames.com/doc/sdk/api).
Antes de empacotar release Windows, ler `distribution-0.1.md` inteiro e testar o pacote extraído.

## 4. Etapas e critérios de aceite

Implementar e verificar cada peça de infraestrutura separadamente. A sequência autônoma
das etapas restantes foi autorizada pelo usuário em 2026-10-07, conforme a exceção de `AGENTS.md`.

### A — Inventário e decisão do complemento

Inspecionar componentes do `.range`, uso atual de Steam e histórico do RolimaRacer. Auditar
`NET_ITransport.h`, `NET_Types.h`, `NET_Session.*`, `NET_TransportENet.cpp`, `NET_TransportMulti.*`,
`KX_NetworkManager.*`, `KX_PyNetwork.cpp`, CMake e eventuais mecanismos existentes de extensões.
Fechar distribuição/ABI, dono do runtime Steam e contrato de canais. Confirmar SDK e AppID disponíveis.

Aceite: decisão escrita com arquivos afetados e uma prova mínima definida, sem alterar gameplay.

### B — Inicialização opcional

Implementar carregamento, disponibilidade, identidade e erros claros: biblioteca ausente,
Steam fechada, conta/AppID indisponível e falha de inicialização. Não carregar Steam no build Web.
Definir lançamento pela Steam conforme o SDK, sem relançar o editor inesperadamente.

Aceite: runtime comum inicia sem Steam; pacote Steam inicializa com AppID do jogo; callbacks e
encerramento funcionam, sem duplicação com o componente existente.

### C — Transporte Steam isolado

Criar adaptador `ITransport` e prova de envio entre dois computadores/contas em redes diferentes.
Mapear canais, peers, falhas e limites; habilitar relay conforme SDK e registrar rota real quando
disponível. Testar conexão com relay forçado pelas opções oficiais do SDK.

Aceite: envio confiável/não confiável conforme contrato, desconexão limpa e teste externo sem
encaminhar portas, incluindo relay confirmado. Testes locais simulados não substituem essa prova.

### D — Sessão nativa pelo transporte Steam

Integrar seleção de transporte sem duplicar replicação. Reusar handshake, spawn, ownership, RPC,
input e troca de cena. API proposta, ainda sujeita ao contrato A: operações de sala e convites em
`Range.network.steam`, com o estado de partida permanecendo em `Range.network`.

Aceite: cena mínima replica transform/propriedade, spawn/despawn e RPC via Steam; rejeita
versões/cenas incompatíveis. Regressão LAN/IP e WebSocket continua passando.

### E — Salas, convites e ImGui

Criar/listar/entrar/sair de salas, limite de jogadores e filtros por jogo/protocolo/build.
Metadados incluem host, porta virtual, versão, estado e capacidade, sem dados secretos.
Processar convites com jogo aberto e argumento de lançamento `+connect_lobby` quando fechado.
Evitar conexões duplicadas, salas órfãs e callbacks atrasados após cancelamento.
Fonte: [ISteamMatchmaking](https://partner.steamgames.com/doc/api/ISteamMatchmaking).

Menu exibe Steam ou LAN/IP e estados: buscando, entrando na sala, conectando ao host, carregando,
em partida e erro. Pronto/chat/início devem ter uma única fonte de verdade, preferindo a sessão
existente após handshake. Código curto de convite não é requisito inicial: usar convite Steam
e identificador de lobby; resolução de código curto seria trabalho adicional.

Aceite: dois usuários criam/encontram sala e entram por convite; sala cheia, cancelamento,
Steam indisponível e host saindo têm comportamento claro.

### F — Corrida real do RolimaRacer

Ligar o menu às regras atuais sem reintroduzir scripts removidos. Testar escolha/carregamento
da pista, spawn com dono correto, movimento e rodas remotas, resultado e saída para o menu.
Evitar que o componente Steam antigo inicialize o mesmo runtime novamente.

Aceite: usuário joga uma corrida com outra conta em outra rede, sem encaminhamento de portas;
não há carros duplicados, donos errados ou objetos remotos simulados localmente por engano.
Repetir saída/reentrada e desligamento do host. Conferência visual feita no jogo real.

### G — Distribuição e documentação

Documentar instalação do complemento, AppID por jogo, diagnóstico e limites. Validar pacote
extraído e instalação pela Steam com duas contas. Depois validar Linux e registrar matriz de
plataformas; não marcar Linux/Web/Android como suportados pelo complemento por inferência.

Aceite: pacote padrão funciona sem DLL Steam; pacote do jogo funciona pela Steam; resultados de
build/execução e teste externo registrados. Sem esses resultados, permanece pendente.

## 5. Fora da primeira entrega

Host migration, backend online independente da Steam, matchmaking competitivo, servidor dedicado
Steam, relay para navegador, cross-play Steam/Web/Android, voz e replay completo de veículos Bullet.
Avaliar cada item depois da corrida externa validada; não são pré-requisitos do host Steam.

## 6. Próximo passo

Inventário A e carregador B1 registrados em [inventário e contratos](steam-multiplayer-inventory.md).
B2 adiciona SDK e serviço da engine, com [instruções locais](steam-complement-development.md).
B2 validado no player Windows com conta conectada e AppID 480: inicialização,
identidade, callbacks e reinicialização passaram. C/D implementados e validados por
socket pair real do SDK: quatro canais, handshake, chat, transform/propriedade,
spawn/despawn e ownership. E implementado; salas/busca/cancelamento/menu passaram
em uma conta. F recebeu adaptadores no jogo, testados numa cena mínima com troca de pista.
G recebeu exportação nativa opcional e instalador explícito; pacotes locais Steam/LAN passaram.
Revisão corrigiu cancelamento/timeout, argv de convite, filas/sequenciamento e retorno
à sala; componente e adaptadores corrigidos passaram provas locais descritas no guia.

Próximas validações: duas contas em redes diferentes com relay confirmado, convites com jogo
aberto/fechado, corrida real e saída/reentrada, AppID comercial e distribuição publicada.
Uma conta com sockets locais não satisfaz os critérios externos das etapas C–G.
Nenhum release foi publicado; a integração não está homologada para corrida externa.
