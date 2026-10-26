# Revisão de KX_Scene: execução, referências e ciclo de vida

Data: 2026-10-26. Frente escolhida: cenas e objetos, primeira prioridade do
[levantamento](levantamento-modulos-criticos.md).

## Escopo e resultado

Leitura integral, em ordem, de `KX_Scene.cpp` (4.698 linhas) e `KX_Scene.h` (862 linhas), com
acompanhamento seletivo das chamadas que estabelecem contratos de réplica, remoção, referências Python,
gravidade, merge e callbacks. A tabela ao final registra a compreensão por trecho. Não é uma auditoria
integral de todos os arquivos de Ketsji; `KX_GameObject` e `KX_SceneCutscene` foram consultados nos fluxos
relevantes, não revisados integralmente nesta rodada.

Quatro defeitos foram reproduzidos no player instalado: dois crashes nativos, restauração indevida da
gravidade e índice de nomes de templates desatualizado. Há também problemas observados estaticamente
e hipóteses que precisam de reprodução própria. Nenhuma correção de C++ foi aplicada nesta revisão.

| ID | Prioridade | Resultado | Gatilho |
|---|---|---|---|
| SCN-01 | P1 | Crash reproduzido | Callback limpa a lista que está sendo executada |
| SCN-02 | P1 | Crash reproduzido | `explode(ignore=...)` recebe sequência cujo acesso lança exceção |
| SCN-03 | P2 | Falha reproduzida | Alterar gravidade após o primeiro tick, sem terremoto |
| SCN-04 | P2 | Falha reproduzida | Renomear template e chamar `addObject` pelo nome novo |
| SCN-05 | P2 | Desequilíbrio de referências observado no código | Executar callbacks de desenho com câmera |
| SCN-06 | P2 | Registros ausentes no merge, sem teste de runtime | Transferir cena com culling de atividade/navmesh dinâmico |
| SCN-07 | P2 | Referência não liberada no código, sem medição | Editar Game Property pelo popup ImGui |

P1 indica encerramento do processo nos casos exercitados. P2 indica comportamento incorreto ou problema
de manutenção de estado/memória. Essas prioridades não são resultados de benchmark.

## O que a classe faz e quem possui os dados

`KX_Scene` coordena os objetos de uma cena em execução. Ela mantém listas com referências contadas
(`m_objectlist`, raízes, inativos, luzes, câmeras, fontes, speakers e render), registros auxiliares de
ponteiros sem posse (animação, culling, partículas, sombras, temporários), managers e o vínculo com o
`Scene` do editor. O mesmo objeto pode aparecer em várias listas: cada inserção com `CM_AddRef` precisa
ter uma liberação correspondente.

O SceneGraph fornece a estrutura hierárquica. A remoção segue `DelayedRemoveObject` → fila de eutanásia
→ `RemoveObject` → `SG_Node::Destruct` → callback `RemoveNodeDestructObject` → `NewRemoveObject`.
`Destruct` percorre filhos antes do pai. A fila é drenada sem remover sua frente antecipadamente, pois
`NewRemoveObject` precisa retirar também filhos que estavam agendados; isso evita removê-los duas vezes.

`NewRemoveObject` avisa a rede, invalida o proxy Python, desregistra lógica/timers, grupos, obstáculos,
componentes e destruição, remove meshes e referências das listas possuídas. Depois da última liberação,
restam apenas comparações de endereço e limpeza de registros auxiliares. Esse limite é essencial:
qualquer consumidor novo precisa limpar seu ponteiro antes de voltar a usá-lo.

Na réplica, primeiro são criados os objetos e controllers; só depois são replicados/religados os Logic
Bricks. Sensores e atuadores são localizados pela posição original nas listas, logo sua ordem faz parte
do contrato. DupliGroups usam mapas/listas temporários compartilhados na cena e adiam a recursão para
não invalidar a iteração corrente.

## SCN-01 — mutação da lista de callbacks derruba o player

**Código:** [KX_Scene.cpp](../source/source/gameengine/Ketsji/KX_Scene.cpp#L3689),
[PythonCallBack.cpp](../source/source/gameengine/Expressions/intern/PythonCallBack.cpp#L197).

1. `RunDrawingCallbacks` entrega a própria lista Python armazenada na cena ao executor comum.
2. `EXP_RunPythonCallBackList` captura o tamanho inicial e percorre com `PyList_GET_ITEM`, sem snapshot.
3. O primeiro callback executa `scene.thread_logic_1.clear()`.
4. A iteração tenta ler o próximo elemento usando o tamanho anterior. A macro não verifica limites.

**Reprodução:** duas funções em `thread_logic_1`; a primeira limpa a lista. O arquivo de evidência
registra a entrada no callback, mas não o segundo callback nem a conclusão. O player sai com código 11;
o handler registra `0xC0000005`, leitura de endereço `0x8`, em `EXP_RunPythonCallBackList`, chamado por
`KX_Scene::RunDrawingCallbacks`.

**Direção de correção:** executar um snapshot que possua as referências dos callbacks e manter os
argumentos vivos durante a chamada. Testar também substituição da lista, auto-remoção e remoção de outro
callback. Decidir/documentar se callbacks adicionados durante a execução valem só para a próxima rodada.
O executor é compartilhado: uma correção precisa conferir outros consumidores, como callbacks de colisão.

## SCN-02 — falha de acesso à sequência vira crash em explode

**Código:** [KX_Scene.cpp](../source/source/gameengine/Ketsji/KX_Scene.cpp#L4558), especialmente o laço
que usa `PySequence_GetItem` e depois `Py_DECREF(item)`.

`ignore` aceita uma sequência. Se `__getitem__` levanta uma exceção, `PySequence_GetItem` retorna nulo.
O código continua para `ConvertPythonToGameObject` e executa `Py_DECREF` nesse nulo. O conversor pode
retornar falso para nulo, mas a liberação incondicional acontece antes do teste de `ok`.

**Reprodução:** sequência Python com comprimento 1 cujo `__getitem__` lança `RuntimeError`. O `try/except`
do script não recebe uma exceção tratável: o processo termina com código 11. O relatório nativo registra
`0xC0000005`, escrita no endereço `0x0`, em `KX_Scene::Pyexplode`.

**Direção de correção:** tratar imediatamente retorno nulo, preservar a exceção original e verificar
também falha de `PySequence_Size`. Cobrir lista/tupla válidas, proxy inválido e sequências que falham em
`__len__` ou `__getitem__`. Trocar somente por `Py_XDECREF` não encerra a análise do fluxo de erro.

## SCN-03 — gravidade do jogo é anulada mesmo sem terremoto

**Código:** [KX_Scene.cpp](../source/source/gameengine/Ketsji/KX_Scene.cpp#L983),
[SetGravity](../source/source/gameengine/Ketsji/KX_Scene.cpp#L3352),
[KX_SimulationPipeline.cpp](../source/source/gameengine/Ketsji/KX_SimulationPipeline.cpp#L130).

`UpdateEarthquake` é chamada antes de cada passo de física. Na primeira chamada, guarda a gravidade base.
No ramo do efeito inativo, restaura essa base sempre que a gravidade atual difere dela. Não há estado
que demonstre que a diferença foi causada pelo terremoto. `SetGravity` apenas escreve na física e não
atualiza a base. O comentário de que alterações do usuário seriam preservadas não corresponde ao fluxo.

**Reprodução:** gravidade inicial Z `-9.800000190734863`; no tick 3 o script define `-3.0` e lê `-3.0`
imediatamente. No tick 4 e seguintes ela já voltou a `-9.800000190734863`, com terremoto desligado.
O teste termina normalmente, código 0, após oito ticks.

**Direção de correção:** distinguir gravidade solicitada pelo jogo do deslocamento temporário aplicado
pelo efeito. Restaurar apenas um deslocamento realmente aplicado, preservando mudanças explícitas.
Testar efeito desligado, ligar/desligar, mudar gravidade durante o efeito e suspender/retomar a cena.

## SCN-04 — renomear template deixa o índice de inativos inconsistente

**Código:** [índice de nomes](../source/source/gameengine/Ketsji/KX_Scene.cpp#L1596),
[setter Python](../source/source/gameengine/Ketsji/KX_GameObject_Python.cpp#L1448),
[SetName](../source/source/gameengine/Ketsji/KX_GameObject.cpp#L357).

O setter Python atualiza o registro do LogicManager e o nome do objeto, mas não atualiza
`m_inactiveNameIndex`. `IndexInactiveObject` usa o nome vigente na inserção e a busca de `addObject`
consulta esse índice. `UnindexInactiveObject` também procura pelo nome vigente, logo a remoção posterior
de um template renomeado pode deixar a chave antiga apontando para um objeto já removido.

**Reprodução:** `ReviewTemplate` é renomeado para `RenamedTemplate`. `scene.addObject('RenamedTemplate')`
lança `ValueError`; `scene.addObject('ReviewTemplate')` ainda cria um objeto cujo nome é
`RenamedTemplate`. A busca antiga deveria ter deixado de resolver esse template.

**Direção de correção:** atualizar o índice dentro da operação de rename com a regra de primeiro objeto
da lista preservada, considerando rollback em nome conflitante. Testar rename, merge, nomes repetidos
e remoção/LibFree após rename. O possível acesso a ponteiro liberado ainda não foi reproduzido.

## Outros problemas e riscos verificados por leitura

### SCN-05 — referências Python dos argumentos não são devolvidas

`RunDrawingCallbacks`, quando recebe câmera, obtém `camera->GetProxy()` e não faz `Py_DECREF` depois da
chamada. `RunOnRemoveCallbacks` tem o mesmo padrão com a cena. O contrato foi conferido em
[GetProxyPlus_Ext](../source/source/gameengine/Expressions/intern/PyObjectPlus.cpp#L1173): ele incrementa
a referência para o retorno. O executor cria/deleta a tupla dos argumentos, mas isso equilibra apenas
a referência adicional da tupla. Comparar com `KX_GameObject::RunCollisionCallbacks`, que libera seus
argumentos após executar a lista.

O desequilíbrio está no código; crescimento de memória não foi medido. Para desenho, o problema pode se
repetir por câmera/passe. Validar com contagem de referências por várias chamadas e callback que falha.

### SCN-06 — merge não transfere todos os registros de atualização

[MergeScene](../source/source/gameengine/Ketsji/KX_Scene.cpp#L3475) transfere listas possuídas,
componentes, destruição, temporários, partículas, reverb e sombras, mas não transfere `m_cullinglist`,
`m_navObstacles` nem `m_dynamicNavMeshes`. `MergeScene_GameObject` não os reconstrói. Em
[BL_Converter::MergeScene](../source/source/gameengine/Converter/BL_Converter.cpp#L1744), a pós-conversão
é feita na origem antes da transferência, e a cena de origem é destruída ao final.

Assim, transferir um objeto não garante que ele participe dos loops de atividade ou navegação da cena
destino. A ausência foi verificada no código, mas não foi reproduzida numa cena com LibLoad nesta rodada.
Também conferir objetos comuns com ação já ativa: o merge insere armatures na animação, sem transferir
genericamente a lista de objetos animados da origem. Um novo `playAction` pode mascarar esse caso.

### SCN-07 — edição de propriedade no ImGui perde a referência inicial

[RenderDebugPropertiesImGui](../source/source/gameengine/Ketsji/KX_Scene.cpp#L2348) cria um
`EXP_BoolValue`, `EXP_FloatValue`, `EXP_IntValue` ou `EXP_StringValue` e o passa a `SetProperty`, sem
liberar a referência inicial. [EXP_Value::SetProperty](../source/source/gameengine/Expressions/intern/Value.cpp#L148)
retém sua própria referência com `AddRef`; substituir a propriedade depois libera somente essa posse.
Conferir a liberação local após cada edição. Não houve teste de memória nem interação no popup.

O popup também usa índice salvo da lista de debug sem conferir novamente tamanho/identidade e presume
que a propriedade ainda existe. Remover objeto/propriedade enquanto o popup está aberto merece teste.

### Hipóteses que ainda precisam de reprodução

- Eventos de animação retêm ponteiros de objetos/eventos em `eventCalls`; o cache da deformação também
  retém ponteiros até o fim do tick. Um callback que força remoção imediata por outro caminho, como
  `LibFree` ou `stop_cutscene`, pode invalidá-los. `endObject` sozinho é adiado e não basta para provar
  esse problema. Montar reprodução específica antes de classificar como use-after-free confirmado.
- `trace_visible` mantém conjuntos estáticos de endereços e nomes durante a vida do processo, sem
  limpeza por cena/sessão de trace. Reutilização de endereços pode suprimir evidência de novos objetos;
  investigar separadamente de qualquer alegação de vazamento do jogo.
- O construtor depende de a conversão preencher `m_worldinfo` e `m_obstacleSimulation`. Os setters foram
  encontrados na conversão; uma leitura isolada do construtor não prova crash no caminho normal.

## Pontos conferidos que não devem virar falsos positivos

- A referência `m_worldSun` é limpa no destrutor de `KX_LightObject`. Sua ausência na limpeza explícita
  de `NewRemoveObject` não basta para concluir ponteiro pendente.
- Partículas, colisores de partículas, reverb e casters estáticos/dinâmicos já verificam duplicação na
  inserção. O texto antigo da auditoria de performance precisa ser relido à luz dessa implementação.
- As tarefas de pose recebem uma entrada pré-criada por objeto no mapa de animação, escrevem em chaves
  distintas e esperam a conclusão antes dos callbacks Python. Não há inserção concorrente nesse trecho.
- `GetDoAnimations` é avaliado uma vez no despacho; chamá-lo duas vezes alteraria o estado de half animation.
- O tempo de vida público é convertido de frames legados para segundos; o contador interno usa o passo
  de simulação. Não trocar essa unidade como se fosse apenas uma simplificação de nomes.
- Os três pontos de atualização do SceneGraph no pipeline sincronizam etapas diferentes. Sua quantidade
  não demonstra atualização inútil; medir nós efetivamente agendados antes de mudar a ordem.

## Registro da leitura integral do arquivo

Faixas referentes ao `KX_Scene.cpp` identificado no manifesto das evidências. Comentários, includes,
tabelas e ramos de compilação também foram lidos. “Sem achado específico” significa ausência de um
defeito identificado nesta revisão, não prova formal de correção nem teste de todos os caminhos.

| Linhas | Compreensão e contrato conferido |
|---|---|
| 1–154 | Licença e dependências: cena integra lógica, física, GPU, Python e serviços; nenhum código de frame aqui |
| 155–278 | Presets de explosão em três camadas, criação de buffers, cores/escala/tempo; falha de criação retorna nulo |
| 279–360 | Divisor de fog, callbacks de réplica/destruição, leitura de sockets de nós World com valores de fallback |
| 361–380 | Callbacks de agendamento do SceneGraph e três passes iniciais de aquecimento de LOD |
| 381–685 | Construtor: listas, qualidade, filtros, World FX, managers e pool; configuração de filtros capturada na carga |
| 686–786 | Destrutor: debug/cutscene, raízes recursivas, listas, managers e Python; depende de callbacks de remoção |
| 787–912 | Acessores, framing, World e ativação de sol automático; ponteiros retornados não ganham posse |
| 913–982 | Sol segue referência de chão derivada da câmera e órbita das World Properties |
| 983–1065 | Terremoto altera gravidade e shift de câmera; restauração indevida identificada em SCN-03 |
| 1066–1144 | Suspensão de som, flags, debug properties e callback de remoção; zombie gera erro/assert |
| 1145–1304 | Réplica de objeto: timers, nó, listas, partículas, controllers e destruição; lógica fica para depois |
| 1305–1346 | Speakers iniciais e tempo de vida; templates inativos não entram no contador automático |
| 1347–1432 | Religa sensores/atuadores pelo índice correspondente depois de todos os bricks existirem |
| 1433–1574 | DupliGroup: filtra membros/raízes, replica hierarquia, aplica transformação e adia grupos aninhados |
| 1575–1626 | Busca de templates entre cenas, índice primeiro-nome-vence e remoção com promoção do próximo homônimo |
| 1627–1724 | addObject C++: limpa estado temporário, cria árvore, posiciona, religa lógica e devolve referência ao chamador |
| 1725–1773 | Remoção adiada inclui instâncias e evita duplicação; drenagem depende da limpeza feita no callback |
| 1774–1939 | Desregistro da rede/lógica/recursos, liberações contadas e limpeza de registros sem desreferenciar objeto liberado |
| 1940–2019 | Câmera ativa, referência de otimização, estatísticas e ordem de desenho; setters C++ assumem câmera válida |
| 2020–2082 | Filtra LOD invisível, callback DBVT e aquecimento sem frustum; não atualizar LOD pela distância de sombra |
| 2083–2139 | Snapshot de bounds para vários passes de sombra, válido apenas no escopo sem movimento dos objetos |
| 2140–2252 | Trace de visibilidade e culling por snapshot, DBVT ou frustum; coleta contadores da câmera principal |
| 2253–2347 | Desenho de bounds/armatures e debug textual; listas de debug mantêm referências próprias |
| 2348–2498 | Debug ImGui, seleção por índice e edição com novos EXP_Value; questões de posse em SCN-07 |
| 2499–2530 | Decrementa temporários e agenda remoção; registros de animação/culling usam inserção sem duplicação |
| 2531–2603 | Visita filhos atravessando nós sem objeto e decide pose de armature por visibilidade/atualização periódica |
| 2604–2659 | Tarefas de pose e deformação; separação de barreiras e referência a filhos/deformers |
| 2660–2766 | Restrição de taxa, cache pré-criado, espera do pool, callbacks de eventos na thread principal e limpeza de inativos |
| 2767–2826 | Despacha deformação, atualiza componentes/atuadores/áudio e encerra lógica com destruição/navmesh/texto |
| 2827–2905 | Drena nós agendados, renderiza buckets/RTT, escolhe LOD normal ou de aquecimento e configura hysteresis |
| 2906–2989 | Criação tardia e atualização de chuva, máscaras, abrigo, áudio e relâmpagos |
| 2990–3126 | Simula partículas visíveis, expira explosões, desvanece luz e desenha buffers de explosão |
| 3127–3204 | Registros de emissores/colisores/reverb; influência da área em espaço local com escala não uniforme |
| 3205–3301 | Escolhe reverb por influência/prioridade, aplica a speakers/áudio e gerencia casters/dirty flag |
| 3302–3376 | Culling de atividade pela câmera ativa, serviços de física/rede, gravidade e tempo suspenso |
| 3377–3474 | Migra bricks, controllers, clientInfo e registros nome/mesh; armatures ganham registro de animação |
| 3475–3602 | Merge das listas/managers/física/timers; registros de atividade/navegação ausentes em SCN-06 |
| 3603–3688 | Filtros fog com World Properties, hot reload e registros de navegação; setters usam posse externa convencionada |
| 3689–3762 | Executor de callbacks, tipo Python e métodos; lista mutável e posse de argumentos em SCN-01/05 |
| 3763–3902 | Dicionário da cena, deleção e teste de pertinência; revisar separadamente tratamento de erro de chaves não textuais |
| 3903–4056 | Getters de listas/World/câmeras e conversão dos setters; unconvertedObjects percorre dados do editor |
| 4057–4188 | Listas de callbacks, limites de debris, gravidade e tabela de atributos; setters retêm a lista recebida |
| 4189–4303 | addObject Python: busca/conversão tardia/LibLoad sync ou async, valida referência e entrega proxy sem posse do C++ |
| 4304–4355 | convertObject, end/restart e nomes dos presets; agendamento de cena passa pelo engine |
| 4356–4438 | Preset altera dados e alguns uniforms em tempo real; resolução/sombras dependem de recarga conforme contrato |
| 4439–4557 | replace/suspend/resume e comandos de cutscene; manager ausente gera erro explícito |
| 4558–4622 | explode: parse, conversão, máscara e sequência ignore; retorno nulo ignorado em SCN-02 |
| 4623–4698 | get com default e conversão Python→cena por nome/proxy, incluindo None e proxy inválido |

## Reprodução e evidências

Gerador: [criar_cena_revisao_kx_scene.py](../tools/debug/cenas/criar_cena_revisao_kx_scene.py).
Cena e evidências locais ficam em `artifacts/revisao-kx-scene-20261026/` (não versionadas).

```powershell
& .\build\bin\AnastacioEngine.exe -b --factory-startup --python .\tools\debug\cenas\criar_cena_revisao_kx_scene.py -- D:\AnastacioEngine\artifacts\revisao-kx-scene-20261026
& .\build\bin\AnastacioEngine.exe -b --factory-startup --python .\tools\debug\cenas\criar_cena_revisao_kx_scene.py -- D:\AnastacioEngine\artifacts\revisao-kx-scene-20261026 inspect
```

Escolher `basic`, `callback_mutation` ou `explode_sequence`; os dois últimos são reproduções de crash:

```powershell
$reviewPreviousCase = $env:SCENE_REVIEW_CASE
$reviewPreviousDialog = $env:RANGE_NO_CRASH_DIALOG
try {
    $env:SCENE_REVIEW_CASE = 'basic'
    $env:RANGE_NO_CRASH_DIALOG = '1'
    & .\build\bin\AnastacioRuntime.exe --server D:\AnastacioEngine\artifacts\revisao-kx-scene-20261026\revisao_kx_scene.range
} finally {
    $env:SCENE_REVIEW_CASE = $reviewPreviousCase
    $env:RANGE_NO_CRASH_DIALOG = $reviewPreviousDialog
}
```

Arquivos relevantes: `inspection.json`, `result_basic.json`, `result_callback_mutation.json`,
`result_explode_sequence.json`, `native_runs.json`, `review_manifest.json` e os relatórios
`callback_mutation_revisao_kx_scene.crash.txt` / `explode_sequence_revisao_kx_scene.crash.txt`.
Os arquivos de crash foram copiados do temporário imediatamente após cada caso; não usar um crash
antigo de outra cena como evidência.

O editor gerou e reabriu a cena; a inspeção confirmou câmera, template no layer inativo, controlador
MODULE, função e ligação Always. O caso básico terminou em oito ticks. Os crashes têm marcadores de
entrada e backtrace nos símbolos correspondentes. A primeira execução de callback encontrou o diálogo
de crash e expirou; os testes finais usaram `RANGE_NO_CRASH_DIALOG=1` e encerraram com código 11.

Houve um build externo concorrente durante a revisão. Após a atualização dos executáveis, os três casos
foram repetidos; o manifesto identifica os fontes e o runtime, com verificação de que o executável não
mudou durante os testes finais de crash. Não foi iniciado build por esta revisão, pois não houve mudança
no código da engine. Teste foi de runtime standalone headless; Play embutido, renderização visual,
Linux e Web não foram exercitados.

Ordem recomendada para correções posteriores: executor de callbacks, entrada `ignore` de explode,
gravidade e rename; depois posse de referências e merge. Cada correção precisa de validação própria,
preservando o comportamento dos caminhos válidos.
