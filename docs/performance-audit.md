# Auditoria estruturada de performance

Data da primeira varredura: 2026-09-16

Este documento organiza a procura por regressões de performance na engine. Um
achado só deve ser tratado como bug confirmado quando houver evidência no código
e um teste que demonstre o custo ou o crescimento ao longo do tempo.

## Taxonomia

| Código | Classe | Pergunta principal |
|---|---|---|
| LIFE | Ciclo de vida | Tudo que é registrado é removido, ou apenas suspenso? |
| DUP | Duplicação | O mesmo objeto, evento ou trabalho pode ser registrado duas vezes? |
| CPU | CPU por frame | Há busca, recálculo ou atualização fora da necessidade real? |
| MEM | Memória | Há alocação, cópia ou crescimento de contêiner em caminho quente? |
| GPU | GPU | Há overdraw, troca de estado ou recurso processado sem aparecer? |
| SYNC | Sincronização | A CPU força espera pela GPU ou outra thread? |
| POOL | Pool/reuso | O objeto reciclado volta a um estado completamente neutro? |
| ALG | Algoritmo | A complexidade cresce com o número total de objetos/eventos? |

## Achados atuais

### Confirmados

- **LIFE/CPU — animação persistente:** 'GetActionManager()' insere o objeto em
  'm_animatedlist', enquanto 'stopAction()' não o retirava. Objetos de pool
  permaneciam sendo varridos. A engine recebeu 'suspendAnimations()' e
  'resumeAnimations()'.
- **LIFE/CPU — componentes ignoravam suspensão:** com
  'logicCulling' e 'logicCullingComponents' ativos simultaneamente,
  'UpdateComponents()' executava componentes mesmo quando 'm_suspended' era
  verdadeiro. Corrigido em 'KX_GameObject.cpp'.

### Candidatos prioritários

- **DUP — listas de partículas e sombras:** os métodos 'AddGpuParticleObject()',
  'AddGpuParticleColliderObject()', 'AddStaticShadowCasterObject()' e
  'AddDynamicShadowCasterObject()' usam 'push_back()' direto. Os pontos de
  conversão atuais parecem chamar cada método uma vez, mas a API não é
  idempotente. Deve haver teste de réplica/reconfiguração e, se necessário,
  usar inserção “se não encontrado”.
- **MEM/CPU — mensagens de rede:** 'GetMessages()' retorna um 'vector' por
  valor e usa 'operator[]' em mapas para consultas. Uma consulta sem mensagens
  pode criar entradas vazias e cada sensor recebe uma cópia. Medir com muitos
  sensores e mensagens antes de alterar a API.
- **SYNC — queries OpenGL:** 'RAS_OpenGLQuery::Result()' usa
  'GL_QUERY_RESULT', que pode bloquear até a GPU terminar. Confirmar se algum
  caminho de profiling chama 'Result()' no mesmo frame; preferir resultado
  disponível ou atrasado.
- **MEM/CPU — vetores temporários de renderização:** há vetores locais de
  ordenação e contagem em caminhos de rasterização. Não são automaticamente
  bugs, mas devem ser medidos para verificar alocação por frame e capacidade
  reaproveitável.
- **MEM/CPU — culling aloca por frame:** `KX_Scene::CalculateVisibleMeshes()`
  reserva um vetor com a capacidade de toda a lista de renderização e
  `KX_CullingHandler::Process()` cria outro vetor temporário de objetos ativos.
  Em cenas grandes, isso pode causar pressão no allocator a cada câmera/camada,
  mesmo quando a visibilidade muda pouco. É um hotspot confirmado por leitura
  do caminho quente; falta medir o custo antes de trocar a API por buffers
  reutilizáveis.
- **MEM/CPU — sorting de transparência/batching:**
  `RAS_BucketManager::RenderSortedBuckets()` e
  `RAS_DisplayArrayBucket::RunInstancingNode/RunBatchingNode()` criam vetores
  (`SortedMeshSlot`, `counts`, `indices`) durante o draw. O custo cresce com
  cada slot transparente/instanciado e se repete por bucket. A otimização
  provável é manter capacidade por bucket, sem alterar a ordem do sort.
- **DUP/LIFE — callbacks de colisão:** sensores inserem ponteiros em
  `KX_ClientObjectInfo::m_sensors` com `push_back()` em construção/reparent.
  O sensor Near remove a entrada herdada no construtor, mas `ReParent()` volta
  a inserir sem uma guarda. Reparent repetido pode deixar o mesmo sensor
  contado mais de uma vez. Ainda não confirmado em runtime; cobrir com teste
  de reparent/replica antes de mudar a estrutura.
- **DUP — registro de componentes Python (contrato frágil):**
  `KX_PythonComponentManager::RegisterObject()` declara no comentário que
  registra apenas uma vez, mas implementa apenas `m_objects.push_back()`, sem
  `CM_ListAddIfNotFound`. A varredura atual encontrou um único call site
  (`KX_Scene::AddNodeReplicaObject`), portanto não há duplicação confirmada;
  qualquer novo caminho de conversão/réplica que registre o objeto novamente
  passaria a atualizar o componente duas vezes por tick. Vale endurecer com
  guarda idempotente quando houver teste de regressão.
- **MEM/CPU — cópia do registro de componentes:**
  `KX_PythonComponentManager::UpdateComponents()` copia todo `m_objects` para
  um vetor local em cada frame para permitir que componentes adicionem objetos
  durante a iteração. A proteção é correta, mas a alocação/cópia cresce com o
  número de objetos. Um buffer de snapshot reutilizável ou fila de adições
  pode eliminar esse custo depois de medir.

## Método de validação

1. Fazer busca estática por pares 'Add/Register/Subscribe' e
   'Remove/Unregister/Unsubscribe'.
2. Instrumentar tamanho e número de inserções das listas persistentes.
3. Executar testes de estresse de criação, destruição, réplica e pool.
4. Medir CPU, memória, draw calls, overdraw e esperas GPU separadamente.
5. Classificar cada item como 'CONFIRMADO', 'SUSPEITO' ou 'SEGURO'.
6. Só aplicar mudanças após um caso reproduzível e uma verificação de
   regressão.

## Próxima rodada

- adicionar testes de não duplicação para as quatro listas de GPU/sombra;
- medir cópias do sistema de mensagens;
- revisar todos os caminhos de atualização de fontes, speakers, física,
  culling e filtros 2D;
- procurar alocações em loops de frame e chamadas de sincronização.
- medir alocações do culling e dos buckets transparentes antes/depois de
  buffers reutilizáveis;
- exercitar `ReParent()` de sensores e réplicas para detectar registros
  duplicados em listas de callbacks.
- confirmar todos os call sites de `RegisterObject()` e testar a contagem de
  atualizações de um componente por tick;
- medir a cópia do snapshot de componentes e comparar com um buffer de
  capacidade reaproveitada.
### Achado adicional — ciclo de vida de sensores

`KX_CollisionSensor::ReParent()` e `KX_NearSensor::ReParent()` fazem
`m_sensors.push_back(this)` sem remover a associação anterior nem testar se o
sensor já está na lista. Reparent repetido pode deixar ponteiros duplicados;
`KX_CollisionEventManager::NextFrame()` percorre a lista e chama
`NewHandleCollision()` por entrada, multiplicando callbacks e trabalho de
colisão. Continua como candidato forte, aguardando teste de reparent/replica.

### Achado adicional — estado de partículas GPU

`KX_GameObject::UpdateParticles()` lê a propriedade Python
`GPU_Particles_Enabled` e chama `SetEnabled()` a cada emissor em todo frame
visível. `RAS_ParticleBuffer::Update()` retorna cedo quando desabilitado, então
não há vazamento aparente; em cenas com muitos emissores, a leitura de
propriedade e a chamada repetida são um hotspot candidato para cache/dirty flag,
condicionado a medição.
### Achado adicional — remoção de sensores e ponteiros pendentes

O destrutor de `KX_CollisionSensor` libera apenas a lista de colisores; ele não
remove explicitamente `this` de `KX_ClientObjectInfo::m_sensors`. Se um sensor
for removido enquanto o objeto/controlador ainda existir, a lista pode manter
um ponteiro para um sensor destruído. Isso é candidato de ciclo de vida e pode
causar tanto custo fantasma quanto acesso inválido em `NextFrame()`; confirmar
o fluxo de remoção de logic brick antes de qualquer correção.
### Resultado do teste de sensores (2026-09-16)

O estresse de 200 ciclos foi executado com `do_reparent=True` (1.103 callbacks)
e com `do_reparent=False` (1.539 callbacks), mantendo `sensors=1` e
`collision_ms=0.000`. A diferença foi menor no modo com reparent, portanto não
houve evidência de multiplicação de callbacks nesta cena. O candidato de ciclo
de vida permanece não reproduzido; uma confirmação definitiva exigiria medir a
mesma quantidade de frames/contatos ou expor a lista interna em um teste C++.

### Resultado do teste de destruição de sensores (2026-09-16)

O estresse `sensor_destroy_stress_test.py` completou 200 ciclos criando e
destruindo um clone com sensor, mantendo a cena estável em 8--9 objetos e sem
crash na execução repetida. Não houve evidência de ponteiro pendente ou
crescimento de registros; o candidato permanece não reproduzido. Um
encerramento isolado da primeira execução, sem log de falha, não é suficiente
para classificá-lo como defeito da engine.

### Resultado do teste de culling (2026-09-16)

Com 500 objetos e a camera em movimento, `CameraCulling` variou entre 0,079 e
0,113 ms no inicio e permaneceu estavel em torno de 0,084--0,104 ms ate o fim
(2.837 frames). Nao houve crescimento monotono; o candidato de alocacao
acumulativa nao foi reproduzido.

### Resultado do teste de transparência e ordenação (2026-09-16)

Com 300 objetos transparentes e a câmera em movimento, `MainRender` permaneceu
estável entre aproximadamente 0,09 e 0,12 ms durante 30 segundos. Não houve
crescimento monotônico nem acúmulo de objetos; o candidato de alocação/sorting
por frame não foi reproduzido nesta carga.

### Resultado do teste de snapshot de componentes (2026-09-16)

O teste criou e destruiu 30 lotes de 100 objetos com componente Python. Após a
remoção deferida do primeiro lote, a cena estabilizou em 107 objetos e `Logic`
permaneceu entre 0,006 e 0,008 ms, sem crescimento progressivo. O candidato de
cópia/registro acumulativo de componentes não foi reproduzido.

### Resultado do teste de shadow casters (2026-09-16)

Com 200 casters e a luz em movimento, `Shadows` permaneceu estável por 30
segundos. Com cascaded shadows, variou aproximadamente entre 0,25 e 0,28 ms;
sem cascaded, entre 0,067 e 0,082 ms. A diferença é o custo esperado do modo
cascaded, sem crescimento acumulativo ou duplicação aparente de casters.

### Resultado do teste de mensagens de rede (2026-09-16)

`network_message_stress_test.py` enviou 40.080 mensagens em 2.004 frames.
O custo de `Logic` permaneceu estável, aproximadamente entre 0,039 e 0,054 ms,
sem crescimento progressivo ou falha. A cópia do vetor de mensagens é um
custo mensurável, mas não apresentou vazamento ou degradação acumulativa nesta
carga; candidato não reproduzido.

### Resultado do teste de corpos físicos (2026-09-16)

O estresse criou e removeu 30 lotes de 100 corpos dinâmicos. Após o pico
transitório da remoção deferida, a cena estabilizou em 106 objetos. O custo de
`Physics` permaneceu aproximadamente entre 0,69 e 0,85 ms (13,9--17,0% do
frame), sem crescimento monotônico, crash ou acúmulo de corpos. O candidato de
registro/alocação acumulativa na física não foi reproduzido nesta carga.

### Resultado do teste de filtros 2D (2026-09-16)

O teste alternou o filtro grayscale 60 vezes durante 30 segundos e coletou 30
amostras. `MainRender` permaneceu estável entre aproximadamente 0,038 e
0,052 ms, sem crash ou crescimento monotônico. O candidato de vazamento na
criação/remoção de filtros 2D não foi reproduzido.

### Correção preventiva das listas GPU/sombra (2026-09-16)

As quatro funções `Add*` de partículas GPU e shadow casters agora verificam
`std::find` antes de inserir. Chamadas repetidas para a mesma instância deixam
de criar entradas duplicadas; a remoção continua apagando todas as ocorrências
legadas. Build de `ge_ketsji` e link de `RangeRuntime` concluídos com sucesso.

### Verificação estática dos candidatos restantes (2026-09-16)

- `GL_QUERY_RESULT` bloqueante aparece apenas na interface opcional de
  estatísticas de renderização (`SHOW_RENDER_QUERIES`). A resolução dinâmica
  normal consulta `Available()` e usa `ResultNoWait()`; não há espera GPU no
  caminho padrão.
- O culling usa vetores temporários por processamento e reserva capacidade antes
  do preenchimento. Isso é um custo de alocação por frame, mas o estresse de 500
  objetos não mostrou crescimento acumulativo.
- A atualização de speakers é limitada por `audio3d_update`; fontes consultam
  propriedades a cada frame, mas só recalculam o texto quando o valor muda.
  Ambos permanecem como hotspots de baixo risco, sem correção necessária sem
  uma medição específica.
