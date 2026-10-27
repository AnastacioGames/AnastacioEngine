# Revisão da frente 2: SceneGraph e sequência da simulação

Data: 2026-10-26. Continuação da [lista de módulos críticos](levantamento-modulos-criticos.md).
As três primeiras rodadas foram de análise, sem correções no código de produto. A continuação
ao fim registra INP-01/02/03 e ANI-01 corrigidos, com regressões e validação em segundo plano.
Nenhuma janela foi aberta.
As alterações concorrentes dos outros trabalhos foram preservadas.

## Escopo e método

Leitura integral de 13 arquivos, 2.354 linhas na fotografia registrada no manifesto:

- `SceneGraph/SG_Node.cpp` e `.h`;
- `SceneGraph/SG_DList.h`, `SG_QList.h`, `SG_ParentRelation.h`;
- `SceneGraph/SG_Familly.cpp` e `.h`;
- `Ketsji/KX_NodeRelationships.cpp` e `.h`;
- `Ketsji/KX_BoneParentNodeRelationship.cpp` e `.h`;
- `Ketsji/KX_SimulationPipeline.cpp` e `.h`.

Consulta seletiva de `KX_KetsjiEngine.cpp` (`NextFrame`, relógios e setters), `KX_Scene.cpp`
(`UpdateParents`, réplica), `KX_GameObject.cpp` (movimento e sincronização), macros e locks.
Não é revisão integral do engine principal, física, animação ou arquivos geométricos de SceneGraph.
O índice mecânico e os mapas foram consultados antes das leituras. A consulta auxiliar ao Ollama
falhou por conexão recusada; nenhum resultado do modelo local foi usado como evidência.

O [teste serial](../tools/debug/revisao_scenegraph.cpp) compila os próprios `SG_Node.cpp`,
`SG_Familly.cpp` e `KX_NodeRelationships.cpp`, sem copiar os algoritmos testados. As implementações
de locks do harness são deliberadamente vazias. Portanto, ele demonstra comportamento serial das
transformações e filas, não segurança entre threads, integração Bullet ou comportamento visual.
Saída zero desse diagnóstico significa que os defeitos esperados foram reproduzidos, não que os
algoritmos estão corretos. Fontes, hashes, HEAD observado e resultados estão no manifesto.

## Compreensão do fluxo

1. Setters locais conferem igualdade e só marcam `m_modified` quando necessário. Operações relativas
   seguem outro caminho e sempre marcam modificação. `SetModified` solicita agendamento; a fila
   principal evita inserir o mesmo nó duas vezes.
2. `UpdateParents` retira nós da fila principal e atualiza a subárvore. A relação de parenting
   calcula a transformação mundial e comunica por `parentUpdated` se os descendentes precisam
   recalcular, inclusive quando eles próprios não sofreram edição local.
3. Relação normal multiplica transformações e decompõe escala/posição/orientação. Relação vertex
   herda apenas a posição do pai. Slow parent interpola a transformação e reagenda enquanto houver
   alteração; bone parent depende da pose da armature.
4. Quando a relação informa atualização, o nó chama o callback que sincroniza o objeto cliente.
   `ClearModified` limpa a modificação local e marca os consumidores de render/culling como dirty.
   Os setters mundiais internos não devem disparar esse ciclo recursivamente.
5. `SG_QList` usa dois pares de links: agendamento atual e reagendamento. Ao terminar a passada,
   `UpdateParents` transfere a fila secundária para a principal para a próxima sincronização.
6. A família compartilha o lock entre nós da mesma hierarquia. A implementação paralela existe,
   mas `KX_Scene::UpdateParents` consultado chama a versão serial. Isso não autoriza remover locks
   nem prova ausência de outros consumidores concorrentes.

### Ordem da simulação

`KX_SimulationPipeline::Update` envolve as cenas entre `network->BeginTick` e `EndTick`. Em cada
cena: atividade, animação, cutscene, sensores/controladores, callback lógico, pais, componentes,
atuadores/limpeza, pais, terremoto/física e serviços finais. A última sincronização dos pais vem
depois de Trace Rail e atualização automática do sol, antes dos efeitos de câmera e partículas.

Os três `UpdateParents` são fronteiras de sincronização, não três recomputações incondicionais de
todos os objetos. Cena suspensa evita os blocos de simulação e acumula o tempo suspenso; a consulta
de atividade ocorre antes desses testes. O servidor preserva poses, mas não chama deformação de
malhas nesse bloco. O modo fixo pode executar vários passos, tratando bordas de input entre eles.
Relógio, acumulação e suspensão foram aprofundados na segunda rodada abaixo.

## Achados

| ID | Prioridade | Evidência | Resultado |
|---|---|---|---|
| SG-01 | P2 | Reproduzido com fontes reais, serial | Relação vertex não propaga atualização para descendentes limpos |
| SG-02 | P2 | Reproduzido com fontes reais, serial | Escala singular gera orientação não finita na relação normal |
| SG-03 | P2 | Reproduzido com fontes reais, serial | Deslocamento global é multiplicado pela escala do pai |
| SG-04 | P3 | Reproduzido em fila isolada; sem chamador atual | `QAddFront` verifica a fila errada e permite reinserção inconsistente |
| SG-05 | P2 | Leitura; impacto no runtime ainda não reproduzido | Construtor de cópia de nó deixa `m_modified` sem inicialização |
| SG-06 | P2 | Contagem de callbacks no teste serial | Movimento relativo zero produz sincronização desnecessária |

### SG-01 — um vertex parent alterado não avisa seus descendentes

Em [KX_VertexParentRelation::UpdateChildCoordinates](../source/source/gameengine/Ketsji/KX_NodeRelationships.cpp#L90),
o ramo detecta `child->IsModified()`, atualiza a transformação mundial, mas não liga
`parentUpdated`. `SG_Node::UpdateWorldData` passa esse valor aos descendentes. Uma relação normal
no nível seguinte vê seu próprio nó limpo e `parentUpdated=false`, então retorna sem atualizar.

Reprodução: raiz normal, filho com relação vertex e neto normal. Neto local em X=1; depois de
inicializar, mudar a posição local do filho para X=3 e atualizar apenas esse ramo. Filho mundial
fica em 3; neto permanece em 1, embora devesse estar em 4. Relação normal, no mesmo contrato,
liga `parentUpdated=true` quando recalcula. Validar também no conversor a combinação de vertex
parenting e descendentes antes de quantificar o alcance em projetos reais.

### SG-02 — decomposição divide por uma componente de escala zero

[KX_NormalParentRelation](../source/source/gameengine/Ketsji/KX_NodeRelationships.cpp#L60)
calcula `1 / scale` por eixo para extrair a rotação. Após parenting válido, zerar um eixo da
escala da raiz faz a orientação mundial do filho conter valores não finitos. O teste alterou a
raiz de `(1,1,1)` para `(0,1,1)` depois da primeira atualização.

É um caminho diferente das guardas de atribuição mundial e `SetParent` corrigidas no núcleo:
essas guardas não impedem que um pai já conectado receba escala zero. Slow parent e bone parent
possuem divisões equivalentes por leitura; não foram executados no teste desse achado. Uma correção
precisa definir como preservar orientação em uma transformação singular, sem simplesmente proibir
todo uso de escala zero nem produzir valores inválidos para os consumidores.

### SG-03 — movimento prometido como global usa apenas a rotação inversa

[SG_Node::RelativeTranslate](../source/source/gameengine/SceneGraph/SG_Node.cpp#L366) converte
o deslocamento global pela orientação do pai, mas não pela escala. Com pai em escala `(2,1,1)`,
solicitar deslocamento global `(1,0,0)` deslocou o filho em 2 unidades mundiais. O caminho
`KX_GameObject::ApplyMovement` encaminha o vetor e chama `NodeUpdate`, sem compensação adicional.

O harness confirma o problema matemático no SceneGraph; não testa a interação com controller
físico. Ao corrigir, cobrir pai girado, escala não uniforme/negativa e a relação vertex, cuja
posição é herdada sem a escala do pai. Não aplicar uma divisão genérica a toda relação.

### SG-04 — guarda de QAddFront consulta a outra lista

Em [SG_QList.h](../source/source/gameengine/SceneGraph/SG_QList.h#L125), `QAddFront` usa
`item->Empty()` em vez de `item->QEmpty()`. Um item que já está na fila secundária de A, mas fora
da principal, é aceito na secundária de B; ambas passam a apontar para ele. O caso oposto também
recusa participação legítima nas duas filas. O harness demonstrou a primeira inconsistência e
restaurou explicitamente os links antes de destruir os objetos.

A busca de usos encontrou somente a declaração/definição de `QAddFront`. O runtime de
reagendamento consultado usa `QAddBack`, cuja guarda confere a fila correta. Portanto, não há
crash demonstrado no jogo nem razão para atribuir a esse método o custo atual da simulação.

### SG-05 — estado de modificação ausente no construtor de cópia

O [construtor de cópia](../source/source/gameengine/SceneGraph/SG_Node.cpp#L62) inicializa os
transforms, relação, família e dirty, mas omite `m_modified`; o construtor comum inicializa esse
bool como true. `GetReplica` utiliza a cópia. A réplica precisa estabelecer o estado antes de
qualquer consulta a `IsModified`. O callback de réplica da cena foi consultado, mas não se
reproduziu uma leitura inválida no runtime nem se assumiu que toda réplica falha. Inicializar o
membro explicitamente evita depender da memória anterior do allocator; conferir antes se o
contrato esperado é forçar atualização inicial ou copiar o estado do original.

### SG-06 — movimento zero ainda dispara atualização

No teste serial, 50 chamadas ao setter de posição com o valor atual produziram zero callbacks.
As mesmas 50 atualizações usando `RelativeTranslate((0,0,0), ..., false)` produziram 50 callbacks,
sem deslocamento. `SetModified` é chamado incondicionalmente nesse caminho. `RelativeRotate` e
`RelativeScale` têm marcação equivalente por leitura; não se mediram esses dois casos.

O resultado mede callbacks, não FPS nem tempo de CPU. A guarda deve ficar onde o valor final
permite detectar ausência de alteração com baixo custo. O detector estático e seu selftest não
substituem esse caso: o selftest passou, apesar de o trabalho redundante existir no caminho relativo.

## Validação e continuidade

Harness compilado com MSVC e `vcvars64.bat`, `VSLANG=1033`, e executado com saída zero.
Evidências em `artifacts/revisao-scenegraph-20261026/`: `build.log`, `result.log` e `manifest.json`.
Para recompilar, use `cl /EHsc /std:c++17 /MD /O2 /DNDEBUG`, incluindo SceneGraph, Ketsji, Common,
blenlib, `lib/win64_vc15/pthreads/include`, `source/intern/mathfu` e `source/intern/debugbreak`.
Compile o harness junto de `SG_Node.cpp`, `SG_Familly.cpp` e `KX_NodeRelationships.cpp`, com objetos
e executável direcionados a `artifacts/`, sempre no processo que carregou `vcvars64.bat`.

Não houve novo build dos produtos porque o código de produto não foi alterado. Não houve benchmark
nem validação de aparência/concorrência. A revisão não encerra a frente 2; a continuação está abaixo.

## Segunda rodada: relógio, acumulador e suspensão

### Escopo e compreensão

Leitura linha a linha dos trechos de `KX_KetsjiEngine.cpp`: inicializadores 189–265,
`StartEngine` 453–474, `NextFrame` 689–897, espera/agendamento 899–1045,
`UpdateAnimations` 1105–1112, relógios 1165–1219 e setters/getters 1300–1409 e 1451–1514.
Consulta dos bindings de tempo/limite em `KX_PythonInit.cpp`, suspensão e passagem de tempo em
`KX_SimulationPipeline.cpp`, `KX_Scene.cpp`, `BL_Action.cpp`, `KX_CutsceneManager::Update`,
`SCA_TimeEventManager::NextFrame`, limpeza de inputs e implementação de `CM_Clock`.
Essas consultas não equivalem à revisão integral dos arquivos maiores.

`FrameTiming` calcula `m_timestep = 1/ticrate` e `m_framestep = m_timestep * timescale`.
Física, tempo de vida de objetos, propriedades Timer e delta exposto ao Python recebem o passo
escalado. `AdvanceStepTime`, porém, soma o passo sem escala aos três relógios absolutos.
No modo legado isso ocorre em `FrameTiming`; no modo fixo, antes de cada `Update`.

No modo fixo, o acumulador recebe tempo real escalado. Para escala positiva estável, a escala
se cancela na razão acumulador/passo: muda a quantidade de tempo simulado por update, sem mudar
a cadência desejada de updates. O limite restringe o catch-up; o clamp posterior retém até mais
um lote de backlog, em vez de descartar todo o saldo imediatamente. Essa política não é, por si,
um defeito. A animação é solicitada só no último passo do lote; isso merece conferência específica
para bone parents e eventos que influenciam a física dos passos intermediários.

`SetUseFixedTimestep` ressincroniza o acumulador ao entrar no modo fixo. A espera nesse modo tem
guarda `timescale > 0`; a divisão que calcula quantos passos executar não tem a mesma guarda.
`ServerSleep`/`SleepUnderRate` usam microssegundos e margem de 0,5 ms; não foi medido consumo de CPU
nesta rodada. O histórico de 2026-10-06 foi consultado: os testes anteriores com escala 1 continuam
relevantes, mas não demonstram pausa zero nem coerência entre escalas.

### Achados de tempo

| ID | Prioridade | Evidência e consequência |
|---|---|---|
| CLK-01 | P2 | Passo fixo zero produz quociente não finito antes de converter para `int`; contagem de passos indefinida pela linguagem. |
| CLK-02 | P2 | Em 64 updates a 64 Hz, escala 0,5 integra 0,5 s de delta, mas os relógios absolutos avançam 1 s; suspensão desconta outra unidade. |
| CLK-03 | P2 | `setMaxLogicFrame(-1)` chega sem validação ao acumulador: retorna -1 passos, não atualiza e deixa backlog negativo. |
| CLK-04 | P2 | Cutscene recebe relógio global sem desconto de suspensão; o gerenciador real dispara um evento de 2 s ao retomar de 1 para 3 s. |
| CLK-05 | P2, estático | A flag pública de relógio externo não tem consumidor que altere o avanço da simulação; `ClockTiming` sobrescreve o horário fornecido. |

#### CLK-01 — pausa zero e conversão antes do limite

Em [NextFrame](../source/source/gameengine/Ketsji/KX_KetsjiEngine.cpp#L816), o cast para `int`
ocorre antes de `std::min`. O binding permite explicitamente zero como pausa. Após
`FrameTiming`, `m_framestep` vale zero. Com acumulador zero, `0/0` produz NaN no MSVC testado;
com saldo positivo, a divisão também não é finita. Converter um valor não representável em
`int` não tem comportamento definido em C++. Não é correto descrever o código atual como apenas
cinco updates vazios, como na observação antiga do Plano 8: o laço mudou desde aquela leitura.

O teste mede o quociente antes do cast, sem executar deliberadamente a conversão inválida.
Não se afirmou crash no jogo. A correção deve definir pausa sem consumir indevidamente input,
mensagens ou backlog. Mesmo com passo positivo, o limite após o cast não protege contra saldo
fora do intervalo de `int`: foi conferido numericamente com intervalo artificial de `1e8` s a
64 Hz. É uma borda extrema, não um travamento comum reproduzido.

#### CLK-02 — relógios absolutos e duração por passo divergem

Os corpos atuais de `FrameTiming`, `AdvanceStepTime` e acumulador produziram:

| Escala | Updates em 1 s real | Relógios absolutos | Soma dos deltas da física |
|---|---:|---:|---:|
| 0,5 | 64 | 1 s | 0,5 s |
| 1 | 64 | 1 s | 1 s |
| 2 | 64 | 1 s | 2 s |

`BL_Action::SetLocalTime` usa a diferença entre relógio de animação e início da ação, sem outro
fator global de time scale. Cutscenes recebem `GetLogicTime`; timers e lifetime recebem
`framestep`. Portanto, os consumidores não compartilham o mesmo tempo de jogo. No caminho
legado, a mesma soma sem escala existe, embora não se tenha executado a engine nesse modo.

Durante suspensão, o pipeline soma `GetFrameStep` ao delta suspenso; ações subtraem esse delta
do relógio de animação. Em 64 passos suspensos, o resultado aritmético é avanço indevido de
0,5 s com escala 0,5, zero com escala 1 e recuo de 1 s com escala 2. É reprodução das contas,
não execução de uma armature. Unificar o contrato dos relógios antes de corrigir consumidores
separadamente; avaliar também efeitos existentes, ações e rede para evitar dupla aplicação.

#### CLK-03 — limite negativo aceito pela API

O [binding](../source/source/gameengine/Ketsji/KX_PythonInit.cpp#L557) só verifica se o argumento
cabe em `int`; o [setter](../source/source/gameengine/Ketsji/KX_KetsjiEngine.cpp#L1381) o armazena.
Com -1 e um passo devido, o bloco real calcula -1 passos, executa zero updates e limita o saldo
a -0,015625 s. Zero também impede a simulação enquanto mantido. Definir mínimo e contrato de
zero; validar tanto a entrada Python quanto o setter C++, sem prometer que o tipo RNA do editor
protege chamadas Python ou internas.

#### CLK-04 — suspensão não pausa a linha do tempo da cutscene

O pipeline deixa de chamar a cutscene durante suspensão, mas o relógio global continua avançando.
Ao retomar, `UpdateCutscene(GetLogicTime())` passa esse horário ao manager sem descontar o tempo
suspenso. Diferentemente de ações, não consulta `GetSuspendedDelta`.

O `KX_CutsceneManager.cpp` real foi compilado no diagnóstico: evento no segundo 2, update no
segundo 1, intervalo sem chamadas e novo update no segundo 3 resultam no evento disparado.
Isso confirma o comportamento do manager com os horários enviados pelo pipeline; não é teste
da cena inteira. Resolver o relógio local da cutscene e seus WAIT_TIME/paths juntos; conferir
também início de uma sequência depois que o jogo já está rodando.

#### CLK-05 — contrato do relógio externo sem efeito na simulação

Busca em `source/source/gameengine` encontrou `USE_EXTERNAL_CLOCK` no enum e nos bindings de
get/set da flag, sem leitura que selecione outra origem temporal. `setClockTime` atribui
`m_clockTime`; `ClockTiming` o substitui por `m_clock.GetTimeSecond`. O acumulador também consulta
diretamente `m_clock`. Alguns consumidores de vídeo/filtros leem `GetClockTime`, logo uma
atribuição ainda pode afetá-los temporariamente; não se afirmou que a API inteira é inerte.
Achado estático: falta teste de compatibilidade que defina o efeito esperado sobre passos,
render e vídeo antes de restaurar ou descontinuar esse contrato público.

### Evidência, limites e próxima leitura

O [gerador do diagnóstico](../tools/debug/revisao_relogio.py) extrai os corpos atuais de quatro
métodos e do bloco do acumulador para uma classe pequena. Ela usa `CM_Clock.cpp` e
`KX_CutsceneManager.cpp` reais, mas substitui pipeline, mensagens e input por stubs. Portanto,
o diagnóstico valida contas e o manager, não instancia `KX_KetsjiEngine`, não executa física,
Python, animação, suspensão real de cena nem temporização do sistema operacional.

Gerar com `python tools/debug/revisao_relogio.py`; compilar o `.cpp` gerado junto de
`CM_Clock.cpp` e `KX_CutsceneManager.cpp`, usando `vcvars64.bat`, `VSLANG=1033`,
`cl /EHsc /std:c++17 /MD /O2` e includes Common, Ketsji, mathfu, blenlib e debugbreak.
Build e execução passaram (exit 0). Fonte gerado, hashes, HEAD observado, `build.log` e
`result.log` ficam em `artifacts/revisao-relogio-20261026/`. Exit zero confirma as observações
esperadas; nenhum defeito foi corrigido nesta rodada e não houve build dos produtos.

Input: a limpeza de teclado/mensagens no fim de `NextFrame` e entre passos tem guardas coerentes
com o comentário de preservação em frames sem passo. `ReleaseMoveEvent` é chamado antes disso,
e joystick Python é atualizado fora da guarda; não se concluiu perda de borda só por essa
posição. Próxima leitura: backend de eventos/joystick, agendamento de pose/eventos/bone parent
no catch-up e mudanças de tic rate/time scale durante um lote. Integração dos achados permanece
pendente, respeitando a restrição de não abrir jogo ou janelas.

## Terceira rodada: input, joystick e animação no catch-up

### Escopo e compreensão

Conferidos linha a linha os corpos de `NextFrame`, `UpdateAnimations`, `UpdateSleepTime` e setters
de taxas já delimitados na rodada anterior; `SCA_InputEvent` (construtores, Clear, Find, End e
getters de estado), `SCA_IInputDevice::ClearInputs/ReleaseMoveEvent`, conversão de eventos em
`DEV_InputDevice` e `KX_PythonJoystick` (construção, destruição, UpdateJoystickEvents e inputs).
Lido `DEV_JoystickEvents.cpp` inteiro (280 linhas), com consulta de botões/eixos vivos em
`DEV_Joystick.cpp`, manager e `SCA_JoystickSensor::Evaluate` (94–222). Isso cobre os caminhos
selecionados, não uma revisão integral de Device e GameLogic.

Animação: `KX_Scene.cpp` 2530–2775 (visita de filhos, decisão de atualização, pose, callbacks e
deformação), `BL_ActionManager.cpp` inteiro (209 linhas), `BL_Action.cpp` 318–337, 369–500 e
543–578; `BL_ArmatureObject::ApplyPose`, `SetPoseByAction`, `UpdateTimestep` e `GetBoneTransform`;
relação bone parent e pipeline já lidos. Consulta pontual dos consumidores de joystick em
`KX_InputTable`, sem afirmar revisão integral desse arquivo.

O teclado/mouse registra valores, estados e bordas separadamente. `Clear` conserva o último
estado/valor e apaga as bordas; entre passos do lote isso permite ver uma tecla como pressionada
sem repetir sua ativação. `ReleaseMoveEvent` só solta movimento quando resta um único valor,
indicando ausência de novo evento desde a limpeza. Não se confirmou perda de movimento só pela
chamada inicial em `NextFrame`, hipótese que permanecia aberta na rodada anterior.

Joystick tem dois caminhos distintos. Sensores consultam `DEV_Joystick` durante a lógica,
condicionados por flags de mudança. A API Python e os bindings de botões do Input System usam
`SCA_InputEvent` preenchidos por `KX_PythonJoystick`, atualizado somente depois do lote.
`HandleEvents`, por sua vez, roda antes do lote, limpa flags e compara o estado vivo com o cache.
Nenhum desses dois caminhos usa a mesma política de consumo por passo do teclado.

### Achados

| ID | Prioridade | Evidência e consequência |
|---|---|---|
| INP-01 | P2 | Corpo atual de UpdateJoystickEvents reproduz `m_status` vazio ao soltar; viola a invariante de SCA_InputEvent e deixa NONE falso durante a soltura. |
| INP-02 | P2 | Bordas Python envelhecem por passagem externa, não por passo: quatro passos leem a mesma ativação; passagem sem passo pode apagá-la antes da leitura lógica. |
| INP-03 | P2 | Reset e sincronização reais reproduzem flag de sensor perdida quando a mudança ocorre numa passagem sem simulação. |
| ANI-01 | P2, integração pendente | Gate do acumulador só permite animação no último passo: pose e eventos de gameplay também são adiados, junto da deformação visual. |

#### INP-01 — soltura deixa a lista de estados vazia

Em `KX_PythonJoystick::UpdateJoystickEvents` (73–107), o botão pressionado troca NONE por ACTIVE.
Ao soltar, adiciona JUSTRELEASED à fila e faz `m_status.pop_back()`, sem inserir NONE. O diagnóstico
executou apertar → soltar e obteve `status_size=0`, `released=1`. Só a atualização posterior
recoloca NONE. Portanto `Find(NONE)`, usado por `inputs[botão].inactive`, retorna falso na soltura.

O header de `SCA_InputEvent` estabelece que `m_status` sempre contém um valor. `Clear` e
`End(ACTIVE/NONE)` indexam o último elemento sem guarda. Esses acessos inválidos não foram
executados pelo diagnóstico. A busca de consumidores consultados encontrou `Find` para joystick,
não um caminho atual demonstrado para `End`/`Clear` desse objeto: não se afirma crash no jogo.
Testar também soltar e apertar novamente em atualizações consecutivas antes de corrigir a fila,
pois o método remove a última borda com `pop_back`, em vez de consumir uma transição identificada.

#### INP-02 — borda Python depende da passagem externa

`NextFrame` atualiza `KX_PythonJoystick` depois de toda a simulação (855–863), sem guarda por
`steps`. Ao contrário do teclado, não há limpeza desse estado entre os passos. Assim, uma borda
publicada ao final da passagem anterior é vista como JUSTACTIVATED por cada passo do próximo lote.
O bloco real do acumulador com pipeline de contagem produziu quatro leituras em quatro passos.
As leituras de botões do Input System em `KX_InputTable` também usam `GetJoyStickInput().Find`.

Se a passagem seguinte deve zero passos, o mesmo UpdateJoystickEvents remove JUSTACTIVATED
mesmo sem consumo pela lógica. O diagnóstico obteve `python_activated=0` com o botão ainda
fisicamente pressionado. Há ainda defasagem entre `activeButtons`, que consulta estado vivo,
e `inputs`, que conserva o snapshot anterior durante a lógica; não foi medido atraso em ms.

A correção precisa separar captura de hardware, publicação e consumo das bordas por passo.
Só mover a chamada para antes do lote não resolve os frames sem passo nem a repetição no catch-up.
Cobrir tanto ativação quanto soltura, e não alterar o estado entre duas cenas do mesmo passo.

#### INP-03 — sensores perdem a flag quando nenhum passo consome a mudança

`DEV_Joystick::HandleEvents` chama `OnNothing` para zerar `m_istrig_axis/button` antes de processar
SDL e executar `SyncLiveState`. Esta última atualiza o cache `m_live_*` imediatamente. Se o lote
tem zero passos, nenhum sensor observa a flag. Na próxima passagem, OnNothing apaga a flag e
SyncLiveState já encontra o mesmo valor no cache, não a restabelecendo na ausência de novo evento.

O diagnóstico executou os corpos atuais de OnNothing e SyncLiveState com botão falso → verdadeiro,
sem consumo, seguido de nova captura mantendo-o pressionado: a flag passou de 1 para 0, enquanto
o botão continuou verdadeiro. `SCA_JoystickSensor::Evaluate` retorna antes da leitura quando a
flag está desligada e `reset` é falso (122, 161, 184). O cenário vale para sensor já inicializado;
reset/level e novos eventos podem mascará-lo. Eixos têm a mesma estrutura, mas só botão foi
executado. O efeito na máquina de estados de um sensor real ainda precisa de integração.

Isso não desfaz o diagnóstico histórico de 2026-09-20 sobre eventos drenados pelo GHOST: a leitura
viva resolve aquela perda na captura, mas a vida útil da flag ainda não acompanha o consumo lógico.

#### ANI-01 — gate da animação também adia pose e eventos

`NextFrame` (829–833) habilita `m_needsAnimation` apenas no último passo do lote. O comentário cita
pose desenhada e economia de skinning, mas `KX_SimulationPipeline::Update` (63–75) usa essa mesma
flag para chamar tanto `UpdateAnimations` quanto `UpdateAnimationDeformers`.

`UpdateAnimations` atualiza ações, pose e eventos antes de sensores e física. `BL_Action::Update`
calcula o frame e processa triggers mesmo quando `applyToObject` é falso; porém nada disso roda
se a chamada inteira for omitida. Callbacks Python são despachados na thread principal ao fim
da passada de poses. Portanto triggers que influenciam gameplay só chegam no último passo.
Não se afirma que todo evento seja perdido: ProcessAnimationEvents cobre o intervalo cruzado;
loops/ping-pong que atravessam mais de uma volta merecem teste separado.

Para bone parents, SetPoseByAction avalia a ação, UpdateTimestep marca os filhos e GetBoneTransform
chama ApplyPose. ApplyPose só resolve de novo quando `m_lastframe` muda. Nos passos intermediários,
sem ação/atualização explícita que mude esse marcador, consultar o osso não avança a ação por conta
própria. A lógica e a física desses passos recebem uma pose anterior, ainda que a pose final
desenhada seja correta. Isso também alcança servidor: ele evita deformação, mas compartilha o gate.

O diagnóstico do acumulador substitui a animação por um número de revisão de pose: quatro passos
produziram `physics_pose_epochs=0,0,0,4`. Isso demonstra o agendamento, não executa armature,
callbacks ou Bullet. O impacto integrado e visual permanece pendente. Definir quais poses/eventos
são necessários a cada passo lógico antes de separar a economia de deformação; evitar simplesmente
ativar todo o skinning em cada passo de recuperação.

### Mudanças de taxas dentro do lote

SetTicRate armazena a taxa; SetTimeScale armazena a escala. `m_timestep/m_framestep` só são
recalculados em FrameTiming, chamado no fim de UpdateSleepTime. A contagem `steps` já foi calculada
quando scripts do lote rodam. Mudar taxa ou escala durante um passo não recalcula o orçamento nem
interrompe os passos restantes desse lote, que seguem o passo anterior. Não há divisão nova por zero
dentro do laço apenas por chamar setTimeScale(0) nesse ponto; CLK-01 aparece no cálculo subsequente.

Não se classificou essa aplicação adiada, isoladamente, como outro defeito sem contrato público
de vigência imediata. Antes de corrigir o relógio, definir a fronteira de aplicação e testar pausa,
troca de taxa da sessão e mudança de modo fixo durante callbacks, para não misturar unidades.

### Diagnóstico e continuidade

[Gerador](../tools/debug/revisao_input_catchup.py): extrai corpos atuais de construtor/Clear/Find/End
de SCA_InputEvent, UpdateJoystickEvents, OnNothing, SyncLiveState, AdvanceStepTime e bloco do
acumulador. As classes pequenas não herdam EXP; hardware SDL e pipeline são substituídos por probes.
Enums/campos necessários estão declarados no diagnóstico; os headers correspondentes entram no
manifesto para rastreabilidade. Não é teste integrado dos binários da engine.

Gerar com `python tools/debug/revisao_input_catchup.py`. Compilar o arquivo gerado junto de
`CM_Clock.cpp`, com includes Common e Device, usando `cl /EHsc /std:c++17 /MD /O2`, sempre no
processo que carregou vcvars64 e VSLANG=1033. Build e execução passaram; hashes dos fontes
conferidos após executar. Logs, manifesto e executável em `artifacts/revisao-input-catchup-20261026/`.
Saída zero confirma as observações; nenhum acesso inválido deliberado foi executado.

Esta rodada acrescenta quatro achados, totalizando 15 na frente 2, com níveis de evidência distintos.
Nenhuma correção de produto, benchmark ou janela nesta rodada. Próxima peça: corrigir primeiro a
invariante da soltura (INP-01), com regressões de apertar/segurar/soltar/reapertar; em seguida,
resolver captura/consumo por passo (INP-02/03) e validar a separação pose/eventos/deformação.
Permanecem as correções SG/CLK e a integração dos cenários na engine.

## Continuação: correção INP-01

`UpdateJoystickEvents` agora usa `SCA_InputEvent::Clear` no início da atualização de cada botão:
consome as bordas anteriores e conserva o estado/valor. As transições substituem o único estado
por ACTIVE ou NONE, sem deixar a lista vazia. Isso também evita carregar JUSTRELEASED de uma
soltura anterior quando o botão é apertado de novo imediatamente. A atualização continua no
mesmo ponto do loop: esta correção não resolve INP-02/03.

O gerador de diagnóstico passou a exigir o comportamento corrigido para INP-01. Compilado com
MSVC, executou os corpos atuais de Clear/Find/End e UpdateJoystickEvents, com hardware substituído:
15 botões, apertar/segurar/soltar/reapertar, 100 ciclos consecutivos por botão, ausência de bordas
antigas e independência dos outros botões. `Clear` e `End` agora são executados depois da soltura.
Todos passaram; hashes dos fontes conferidos. O mesmo teste ainda reproduz INP-02/03 e ANI-01.

`RangeEngine` e `RangeRuntime` recompilados com sucesso (seis etapas incrementais). O editor
iniciou e encerrou em `--background --factory-startup`, executando Python com saída zero.
O smoke do player em `--server` segue o procedimento de `tools/pre_release.bat`; sua verificação
é de inicialização, não de joystick físico. Logs em `artifacts/revisao-input-catchup-20261026/`.
Teste com hardware real continua pendente; nenhuma janela foi aberta.

Estado da frente: 15 achados registrados, INP-01 corrigido e 14 abertos. Próxima peça: definir e
implementar publicação/consumo por passo de INP-02/03, preservando bordas nas passagens sem
simulação e oferecendo o mesmo estado a todas as cenas de um passo.

## Continuação: captura e consumo do joystick (INP-02/03)

A captura de `KX_PythonJoystick` agora ocorre antes da simulação, depois de `HandleEvents` e
da atualização dos wrappers adicionados/removidos. `UpdateJoystickEvents` acumula as transições
observadas e conserva um único estado NONE/ACTIVE. A limpeza saiu da captura para
`ClearJoystickEvents`, chamada depois de cada `KX_SimulationPipeline::Update`, tanto no modo
fixo quanto no variável. Assim, todas as cenas do passo leem as mesmas bordas, passos posteriores
do catch-up não as repetem e passagens com zero passos não as consomem.

`HandleEvents` também deixou de apagar as flags dos sensores antes de capturar SDL. A nova
`DEV_Joystick::ClearEvents` limpa essas flags depois de todas as cenas do passo. `SyncLiveState`
continua detectando mudanças do estado combinado físico/virtual; uma mudança observada sem
passo lógico permanece sinalizada até a avaliação dos sensores.

O diagnóstico passou a extrair também os métodos de limpeza, o trecho de captura/limpeza do
loop e `SCA_JoystickSensor::Evaluate`. Com hardware e pipeline substituídos, passou em:

- Regressão INP-01 dos 15 botões, com 100 ciclos por botão.
- Zero, um e quatro passos, mais o caminho variável; quatro passos leem JUSTACTIVATED uma vez.
- Vinte capturas sem passo preservam as bordas e a ordem soltura/reaperto até o consumo.
- Duas cenas simuladas veem a mesma borda antes da limpeza; passos seguintes não a repetem.
- O corpo real de Evaluate detecta pressão/soltura de botão e deslocamento/retorno do eixo
  após vinte capturas sem avaliação, nas duas instâncias de sensor.

Limites: não é integração com SDL físico nem teste de jogo. Pressionar e soltar inteiramente
entre duas capturas de estado vivo continua sujeito à limitação já comentada em HandleEvents;
esta alteração preserva transições observadas entre capturas, não reconstrói eventos que nunca
foram capturados. Sensores continuam avaliando o estado final, enquanto a fila Python pode
conservar ambas as bordas. O cenário ANI-01 continua reproduzido, sem correção nesta peça.

Validação dos produtos pendente: a compilação dos fontes alterados passou, mas a ligação parou
em LNK1104 ao substituir `AnastacioRuntime.exe`, em uso por um teste de física do Claude em
`--server` (`fisica_remove_con.range`, PID 37380). A tentativa com o alvo RangeEngine mostrou
que ele também depende desse executável e encontrou o mesmo bloqueio. Após duas falhas, nenhuma
nova tentativa foi feita; o usuário foi avisado para aguardar/encerrar o teste pelo Claude.
Nenhum processo dele foi interrompido. Evidências e manifesto de 13 arquivos conferido em
`artifacts/revisao-input-catchup-20261026/`; diagnóstico encerrou com saída zero.

INP-02/03 ficam implementados, aguardando build completo e smoke dos dois programas para
fechar esta peça. INP-01 permanece validado; os outros 12 achados SG/CLK/ANI não foram corrigidos.

### Preparação da próxima peça: ANI-01

A leitura adicional confirmou duas restrições distintas: `SetAnimationRate` configura a taxa
global usada por `UpdateSleepTime` para definir `m_needsAnimation`; a opção RESTRICT_ANIMATION
também faz `KX_Scene::UpdateAnimations` retornar false antes das poses quando o intervalo é menor
que o FPS da cena. `GetDoAnimations` ainda implementa a alternância por objeto de half animations.
Portanto retirar toda a guarda do pipeline mudaria também essas escolhas existentes, além do
catch-up. Não foi feita essa alteração.

Outro caso necessário na regressão: a pose pode atualizar num passo intermediário e ser
restringida no último. Se apenas mover a guarda para a deformação, a condição `animationsRan`
do último passo pode impedir que a pose intermediária seja deformada para o desenho final.
Testar separadamente atualização de ações/eventos, pose e deformação, incluindo taxa global
menor que a lógica, restrição por FPS da cena, half animations e servidor. Estas são condições
de projeto e leitura, não uma nova reprodução integrada nem uma correção de ANI-01.

O usuário escolheu aguardar os testes do Claude antes de liberar o player. O PID 37380 encerrou,
mas a sequência continuou em outro player de física (`fisica_end_obj.range`, PID 32820).
Nenhum processo foi encerrado e nenhum build foi repetido enquanto o player permaneceu ocupado.

### Validação final de INP-02/03

Depois da liberação dos testes de física, foi aguardado o Ninja do Claude. A primeira tentativa
encontrou outro Ninja gerando novamente o player durante a instalação do editor: a ligação
passou, mas o CMake não encontrou o arquivo completo para copiar. Aguardado esse processo e
confirmada a ausência de Ninja/player/editor em execução, o build de `RangeRuntime RangeEngine`
terminou com saída zero, incluindo a instalação. Não houve alteração de flags/configuração
nem interrupção de processos do Claude.

As regressões INP-01/02/03 foram reexecutadas com sucesso; os 13 hashes do manifesto continuam
correspondendo aos fontes. O editor executou Python em `--background --factory-startup` e
encerrou com código zero (`INP0203_EDITOR_BACKGROUND_OK`). O player carregou a cena de smoke
`ui_tree_proto.range` em `--server`, permaneceu ativo por dez segundos e foi encerrado pelo
próprio teste, conforme o procedimento de pre_release. Isso valida inicialização, não input físico.

Logs: `engine-build-final-retry.log`, `editor-smoke-inp0203.log`, `player-smoke-inp0203.log` e
`player-smoke-inp0203-status.txt`, na pasta de evidências já indicada. INP-01/02/03 ficam corrigidos
e validados nesses limites; teste com controle físico e integração do joystick no jogo continuam
pendentes. Restam 12 achados sem correção na frente 2 (SG-01..06, CLK-01..05 e ANI-01).

## Continuação: poses/eventos por passo e deformação ao fim do lote (ANI-01)

O acumulador não desliga mais `m_needsAnimation` nos passos intermediários. A taxa global
continua decidindo se o lote é elegível para animação; `KX_Scene::UpdateAnimations` conserva a
restrição de FPS da cena e a seleção de half animations por objeto. O argumento
`KX_SimulationPipeline::Update(bool deformAnimations)` adia somente a deformação para o último
passo. No modo variável, o argumento padrão mantém a deformação na única atualização.

A cena mantém um conjunto de objetos com pose pendente de deformação, separado do mapa de
resultados da passada atual. Ele é preenchido na thread principal depois de esperar as tarefas
de pose, antes dos callbacks de eventos. Assim, uma pose que mudou no passo 3 não some quando
o passo 4 é restringido; half animations também não apaga o trabalho da passada anterior.
`NewRemoveObject` retira o objeto das duas estruturas antes de liberar referências. O conjunto
é consumido e limpo ao deformar; servidor o descarta sem tarefas de skinning. `ImageRender`
também consome deformações pendentes mesmo quando a atualização de pose atual é restringida.

O [diagnóstico de política](../tools/debug/revisao_animacao_catchup.py) extrai os trechos atuais
de seleção de tarefas, restrição da cena, seleção de half animations, coleta/consumo do conjunto,
remoção do objeto e ramo de animação do pipeline. Compilou e passou com poses/deformadores/pool
substituídos: pose normal por passo, deformação única, último passo restringido ou pulado por
half animations, objeto culled, servidor, suspensão, gate global, remoção e entrada duplicada.
O [diagnóstico do acumulador](../tools/debug/revisao_input_catchup.py) passou a exigir a sequência
de poses 1,2,3,4 em quatro passos e uma única deformação; as regressões de input continuam passando.

O [gerador de cenas](../tools/debug/cenas/criar_cena_revisao_animacao.py) cria quatro casos:
normal, restrição ao FPS da cena, half animations e taxa global menor que a lógica. Cada cena
tem ação de objeto, ação de osso com filho, callbacks densos de eventos e dois atrasos controlados
de 90 ms. Salva, reabre e inspeciona a câmera, os objetos, a ação preservada e o controlador MODULE.
A armature usa culling NONE para medir poses independentemente da visibilidade em servidor.
O [validador do player](../tools/debug/revisao_animacao_player.py) verifica avanço das ações e
do filho de osso durante catch-up, identidade/ordem dos triggers e preservação das restrições.

Evidências em `artifacts/revisao-animacao-20261026/`. Os quatro casos passaram novamente nos
binários finais: 56 passos cada, avanço das ações e do filho de osso durante catch-up e triggers
sem duplicação ou lacunas no intervalo efetivamente percorrido. O caso normal disparou os 54
triggers esperados, disponíveis antes da leitura pela lógica. Os outros casos mantiveram passos
sem pose conforme suas restrições; o total final do caso de taxa global depende de onde termina
o último intervalo de animação. `cenas/validation-summary.json` registra o hash do player testado.

O primeiro build completo passou; uma edição posterior somente de comentário no header exigiu
recompilar dependentes (132 etapas planejadas). Os fontes compilaram, mas o link encontrou o
player ocupado por testes gráficos/físicos do Claude. Após aguardar a liberação, o build final de
`RangeRuntime RangeEngine`, incluindo instalação, terminou com saída zero. Logs em
`engine-build.log`, `engine-build-final.log` e `engine-build-retry.log`. Editor executou Python
em background e encerrou com código zero (`editor-smoke.log`). Nenhum processo do Claude foi
encerrado e nenhuma janela foi aberta por esta revisão.

Detector estático de trabalho repetido e selftest executados: selftest passou, quatro suspeitos
na varredura completa, sem achados novos nos C++ alterados em relação ao HEAD (comparação em
`work-check-diff.json`). Os manifestos dos dois probes foram conferidos após executar. As cenas
de servidor não exercitam skinning, renderização nem ImageRender real. Validação visual,
auditoria de trabalho numa cena parada com render e custo de CPU do catch-up continuam pendentes;
os contadores publicados em BeginFrame não aferem esse custo num servidor sem render.
Interação da pose com contatos de corpos dinâmicos também não foi medida nesta cena.

Estado: INP-01/02/03 e ANI-01 corrigidos nos limites descritos; 11 achados SG/CLK sem correção.
## Continuação: vertex parent propaga para os descendentes (SG-01)

`KX_VertexParentRelation::UpdateChildCoordinates` agora liga `parentUpdated = true` quando recalcula, como a relação normal. No teste serial o neto passou de 1 para 4; numa cena `--server` (pai, filho por vértice, neto normal), mover o filho em +3 manteve o neto a 2 unidades dele. Restam 10 achados (SG-02..06, CLK-01..05).

## Continuação: escala zero mantém a orientação (SG-02)

`KX_RotationWithoutScale` substitui a divisão por eixo nas relações normal, slow parent e bone parent. Com um eixo de escala zero (ou resultado não finito), o filho mantém a última orientação; posição e escala continuam vindo da transformação. Escalas não nulas seguem exatamente o cálculo antigo. Teste serial: `orientation_finite=true`. Restam 9 achados (SG-03..06, CLK-01..05).

## Continuação: movimento global e movimento zero (SG-03, SG-06)

`RelativeTranslate` global agora aplica a rotação inversa e divide pela escala mundial do pai por eixo (eixo zero não divide). Relação vertex recebe o deslocamento sem conversão, porque herda só a posição. As três operações relativas retornam cedo com valor neutro exato (zero, identidade, um), sem `SetModified`. Teste serial: `world_delta=1` e `zero_movement_callbacks=0`; teste extra com pai girado 0,7 rad em escala (2; 0,5; 3), pai em escala (-2,1,1) e vertex parent: erro < 3e-7. Restam 7 achados (SG-04, SG-05, CLK-01..05).

## Continuação: fila e réplica (SG-04, SG-05)

`QAddFront` usa `QEmpty()` como `QAddBack`, e o comentário diz "front". O construtor de cópia inicializa `m_modified(true)`: a réplica força a primeira atualização, igual ao construtor comum. O harness serial agora valida as correções e sai 0 só com SG-01/02/03/04/06 corrigidos. Rodado com as mudanças: todos os valores esperados. Validado em 2026-10-27: build completo `RangeEngine RangeRuntime` OK; regressões em `--server` com o binário novo — física (8 cenas) e colisão (5) com resultados idênticos aos anteriores, vertex parent (neto a 2 do filho) e animação (4 casos, `ANI_PLAYER_ALL_CASES_PASSED`). Restam CLK-01..05.

Próxima peça: validar SG-04/05 no build, depois relógio (CLK-01).

## Continuação: pausa zero e limite de passos (CLK-01, CLK-03)

`NextFrame` só divide quando `m_framestep > 0` e limita o quociente em `double` antes do cast; escala 0 pausa com zero passos, sem consumir input nem acumular saldo. `SetMaxLogicFrame` guarda no mínimo 1 (cobre também o valor lido do arquivo) e `Range.logic.setMaxLogicFrame` recusa valores < 1 com `ValueError`. Cena `--server` com `RANGE_ANIM_LOG`: -1 e 0 recusados, limite segue 5; após `setTimeScale(0)`, 175 frames com `steps=0 acc=0.0000` e relógios parados, sem crash. Física (8), colisão (5) idênticas e animação (4 casos) passaram. O harness `tools/debug/revisao_relogio.py` ainda reproduz o estado antigo e não foi convertido. Retomar a pausa exige chamada externa à lógica (thread Python não ganha o GIL com a lógica parada); contrato de retomada fica com CLK-02. Restam CLK-02, CLK-04 e CLK-05.

## Continuação: contrato único do relógio (CLK-02, CLK-04, CLK-05)

Decisão do usuário (2026-10-27): a escala de tempo vale para todos os relógios, a cutscene pausa com a cena e o relógio externo é descontinuado.

- **CLK-02:** `AdvanceStepTime` soma `m_framestep` (passo × escala), a mesma duração da física, dos timers e do `SuspendedDelta`. Frame, lógica e animação andam juntos, e a suspensão desconta exatamente o que o relógio avançou. Por isso não há dupla aplicação nas ações: `BL_Action` não tinha fator de escala próprio.
- **CLK-04:** `KX_CutsceneManager::Advance(dt)` avança o relógio da própria sequência, que começa em 0 no `Start`. A cena passa `GetFrameStep()` só quando não está suspensa. Uma sequência iniciada no meio do jogo começa no primeiro evento, e WAIT_TIME e paths continuam relativos a `GetTime()`.
- **CLK-05:** `setUseExternalClock` emite `DeprecationWarning` e não tem efeito, e a doc da API foi atualizada. `setClockTime`/`getClockTime` continuam como estão (tempo real usado por vídeo e Camera FX).
- **Efeitos visuais** que leem `GetFrameTime` (chuva, flicker, terremoto, tempo de shader) passam a seguir a escala. Camera FX e vídeo usam `GetClockTime` (tempo real).
- **Retomada da pausa por escala 0:** fica documentada em `setTimeScale`. A lógica não roda, então a retomada precisa vir de fora da lógica do jogo; para pausar com scripts ativos, use `scene.suspend()` em outra cena.

**Validação (`--server`, cena com cena A e overlay B):**
- `getFrameTime` avança 0,5 / 1,0 / 2,0 passo por passo com escala 0,5 / 1 / 2. Antes eram 1,0 nas três.
- Cutscene com evento em 1 s: `play_cutscene` no frame 30, A suspensa de 45 a 165, spawn no frame 210, ou seja, 60 frames de cena ativa (1,0 s). Antes, disparava na retomada.
- Física (8), colisão (5) e vertex parent deram resultados idênticos aos anteriores, e a animação passou nos 4 casos.

`tools/debug/revisao_relogio.py` foi convertido e agora confere o contrato corrigido (ver abaixo).

## Continuação: espera da cutscene congela a linha do tempo

Achado da revisão do 3fde104b, já existente antes dele: durante Wait Trigger e Wait Camera End o tempo da sequência seguia andando com os eventos retidos, e ao fim da espera todos os eventos vencidos disparavam no mesmo frame.

`KX_CutsceneManager` separa agora dois relógios: `GetTime()` é a posição na linha do tempo e fica parada durante qualquer espera; `GetPlayTime()` conta todo o tempo tocado desde o `Start()` e move os caminhos de câmera e o prazo do Wait Time. Ao vencer o prazo do Wait Time, só a sobra do passo avança a linha do tempo. Os eventos depois de uma espera mantêm o espaçamento de autoria, o que atrasa cutscenes antigas que contavam com o disparo em lote.

Validação: `tools/debug/revisao_relogio.py` gera o diagnóstico, compilado com `CM_Clock.cpp` e `KX_CutsceneManager.cpp` reais. Passaram pausa por escala zero, relógios em 0,5/1/2, limite negativo, lacuna grande, suspensão da cutscene, Wait Trigger (eventos a 1 s de intervalo depois de 10 s de espera), Wait Time e o relógio da ação sem salto na suspensão. A biblioteca `ge_ketsji` compilou; o link dos executáveis ficou bloqueado pelo editor aberto, então o teste `--server` com cena fica para depois.

Validado em `--server` em 2026-10-27 com `RangeEngine RangeRuntime` religados. Foram geradas duas cenas com Spawn Object em 1 s e 2 s, com taxa de lógica de 64 Hz:
- Wait Trigger em 0 s, liberado no tick 320: os objetos surgiram nos ticks 383 e 447, ou seja, 1 s depois da liberação e 1 s entre eles.
- Wait Time de 2 s em 0,5 s: os objetos surgiram nos ticks 192 e 256, ou seja, em 3 s e 4 s de tempo tocado.

As regressões de animação ANI-01 deram de novo `ANI_PLAYER_ALL_CASES_PASSED`.

Custo de CPU da recuperação de passos atrasados (ANI-01), medido em `--server`, duas rodadas:
- Cena: 150 armatures com esfera deformada (512 vértices cada), lógica a 64 Hz e limite de 5 passos.
- Atraso forçado: pausa de 80 ms a cada 20 ticks.
- Método: os passos de um mesmo lote rodam colados, então o intervalo entre eles é o custo de um passo.

| Modo | Custo de cada passo do lote (mediana) |
| --- | --- |
| Sem restrição | 2,0 a 2,6 ms |
| Com Restrict Animation Updates | 0,035 a 0,043 ms |

Com a restrição, a deformação fica só para o último passo do lote, que custa cerca de 2,5 ms (p90). Assim um lote de 5 passos sai de cerca de 12 ms para cerca de 2,6 ms. A pose e os eventos continuam sendo calculados em todos os passos.

Estado da frente: os 15 achados e este estão corrigidos. Falta a conferência com janela: joystick com controle real, `setTimeScale` no RolimaRacer e o render da recuperação de passos atrasados numa cena parada.
