# Pesquisa independente: processamento da Anastacio Engine (Claude)

Pesquisa estática em 2026-11-04, feita antes de ler o [estudo do Codex](estudo-modernizacao-processamento.md)
e comparada com ele no fim. Nenhum código da engine foi alterado, nenhuma biblioteca foi integrada e
nenhum teste abriu editor ou jogo. Os tempos citados vêm do changelog; nada foi medido nesta pesquisa.

Legenda usada no texto:

- **[código]** fato conferido no código desta árvore (`main`, `ccf26bd9` + alterações locais não relacionadas);
- **[medido]** número já registrado no [changelog](changelog.md), com a data da entrada;
- **[hipótese]** estimativa ou expectativa ainda sem medição nesta engine.

## Conclusão

1. **Os custos medidos não estão onde estão os candidatos principais do Codex.** No RolimaRacer com
   20 IA, os scripts Python ficam em ~7 ms e a física varia de 2,2 a 4,75 ms conforme o número de contatos
   **[medido, 2026-10-30]**. Com 400 personagens, `Animations` gasta 8,6 ms e `Skinning` 11,5 ms
   **[medido, 2026-10-29]**. A filtragem em `SynchronizeActiveMotionStates`, o mapa de `UpdateAnimations`
   e os testes de esfera das sombras não têm medição e provavelmente custam microssegundos **[hipótese]**.
2. **O candidato com mais potencial na CPU é uma técnica, não uma biblioteca:** cada fcurve resolve o seu
   caminho RNA em texto (`pose.bones["..."].rotation_quaternion`) em todo quadro **[código]**. Guardar o
   destino já resolvido segue a ideia dos clips preparados do ozz sem trocar o modelo de animação do Blender.
3. **Física: o Codex olhou o laço menor.** Por quadro também há laços sobre o `std::set` com todos os
   controladores: um por substep (`SimulationSubtickCallback`) e dois no caminho "Use Frame Rate"
   (`ProceedDeltaTimeCar`) **[código]**. O Bullet já mantém `m_nonStaticRigidBodies`, que serve à
   sincronização sem lista nova **[código]**.
4. **Caminhos SIMD explícitos desligados em duas plataformas:** o Bullet 2.84 desta árvore liga os caminhos
   `BT_USE_SSE` no Windows/MSVC e em Mac x86, mas não no Linux com GCC; o Bullet atual (3.26) faz o mesmo
   **[código]**. Isso não quer dizer código sem SIMD: no x86-64 o compilador usa SSE2 e pode vetorizar por
   conta própria. O que fica de fora são os trechos escritos à mão para SSE. O build Web não passa
   `-msimd128` **[código]**, e esse modo não exige SharedArrayBuffer **[documentação Emscripten]**. Os dois
   são experimentos sem ganho garantido. O `-msimd128` é o único deles que vale para Web/Android sem mudar a
   hospedagem.
5. **meshoptimizer continua sendo a biblioteca mais isolável, mas o primeiro passo deve ser offline:**
   o `.cooked` só guarda uma lista de índices quando desenho e triângulos coincidem **[código]**.
   Na iGPU, o gargalo medido em 2026-10-25 foi o resolve de MSAA, não vértices (registro nas notas de sessão; não achei a entrada no changelog). Primeiro medir
   ACMR/ATVR das malhas reais e testar o *shadow index buffer* (passadas só de profundidade); só depois
   decidir se a biblioteca entra no conversor.
6. **Trocar o agendador continua sem justificativa**, como o Codex concluiu. Mas o quadro já usa **três**
   pools de threads, não dois: o agendador da engine (animação, conversão), o agendador global do Blender
   (colisão em paralelo) e o TBB (culling) **[código]**.
7. **Rejeitados:** substituir Bullet por Jolt, migrar para Flecs/ECS, adicionar ISPC ao build, trocar
   BLI_task por enkiTS/oneTBB e usar ozz como backend nos personagens atuais. Motivos na seção 9.

Os três primeiros experimentos recomendados estão no fim do documento.

## 1. Método e fontes

Levantamento próprio, nesta ordem: código da engine, Bullet embutido (`source/extern/bullet2`, versão
`BT_BULLET_VERSION 284`), animação do Blender embutido, caches de build (`build/`, `build-web-release/`) e
changelog. Depois as fontes externas, e só então o estudo do Codex.

| Fonte | Revisão | O que foi lido |
|---|---|---|
| Bullet 3 (upstream) | `d3afe761` (3.26) | `src/LinearMath/btScalar.h`: seleção de SSE/NEON por plataforma. Cópia em `artifacts/pesquisa-processamento-claude/bullet3/` |
| [Emscripten: SIMD](https://emscripten.org/docs/porting/simd.html) | página acessada em 2026-11-04 | `-msimd128`, autovetorização, tradução de SSE/SSE2, navegadores suportados |
| meshoptimizer | `f0a684f1` (cópia do Codex) | README: Vertex cache, Overdraw, Vertex fetch, Shadow indexing, Mesh compression, Efficiency analyzers, Deinterleaved geometry |
| ozz-animation | `744eb9d9` (cópia do Codex) | README (plataformas); `sampling_job.h` (`Context::Step`); `sampling_job.cc` (`Interpolates`: Lerp/NLerpEst) |
| Jolt Physics | `0f69a6b8` (cópia do Codex) | README (plataformas, determinismo); `BodyManager.cpp` (`mActiveBodies`, `mIndexInActiveBodies`) |
| enkiTS | `c947c2c4` (cópia do Codex) | README (plataformas) |

Manifesto das fontes acrescentadas: `artifacts/pesquisa-processamento-claude/sources.json`. As fontes do
Codex estão listadas em `artifacts/modernization-study/sources.json`; li os trechos acima a partir das
cópias dele, sem baixar de novo. O modelo local (Ollama) não foi usado: os trechos lidos eram curtos.

## 2. Física (Bullet)

### 2.1 O que roda por quadro **[código]**

- [ProceedDeltaTime](../source/source/gameengine/Physics/Bullet/CcdPhysicsEnvironment.cpp#L1087) (modo padrão):
  `stepSimulation` + N × `stepSimulationRun`, depois
  [SynchronizeActiveMotionStates](../source/source/gameengine/Physics/Bullet/CcdPhysicsEnvironment.cpp#L1154),
  que percorre `getCollisionObjectArray()` inteiro (estáticos inclusive) com `upcast` e quatro testes.
- [ProceedDeltaTimeCar](../source/source/gameengine/Physics/Bullet/CcdPhysicsEnvironment.cpp#L1165), usado quando
  `FIXED_FRAMERATE` ("Use Frame Rate") está ligado
  ([KX_SimulationPipeline.cpp:137](../source/source/gameengine/Ketsji/KX_SimulationPipeline.cpp#L137)), chama
  `CcdPhysicsController::SynchronizeMotionStates` para **todos** os controladores duas vezes por quadro
  (linhas 1189 e 1216), percorrendo o `std::set m_controllers`. Para estáticos a função ainda chama
  `SyncCollisionScaling()` ([CcdPhysicsController.cpp:1601](../source/source/gameengine/Physics/Bullet/CcdPhysicsController.cpp#L1601)).
- Em **todo substep** o callback
  [SimulationSubtickCallback](../source/source/gameengine/Physics/Bullet/CcdPhysicsEnvironment.cpp#L1076)
  (registrado na linha 750) percorre o mesmo `std::set` e chama `SimulationTick`, que só faz algo em corpos
  não estáticos **com** limite de velocidade configurado
  ([CcdPhysicsController.cpp:1564](../source/source/gameengine/Physics/Bullet/CcdPhysicsController.cpp#L1564)).
- O próprio Bullet também percorre `m_collisionObjects` inteiro por quadro em `saveKinematicState`
  ([btDiscreteDynamicsWorld.cpp:262](../source/extern/bullet2/src/BulletDynamics/Dynamics/btDiscreteDynamicsWorld.cpp#L262)).

O RolimaRacer roda 11 substeps por quadro **[medido, 2026-10-30]**. O laço de substep percorre, portanto,
11 vezes por quadro um `std::set` (nós espalhados na memória) com todos os controladores, para quase nunca fazer
nada. **[hipótese]** Com alguns milhares de controladores, esse custo pode superar o de
`SynchronizeActiveMotionStates`, que percorre uma vez um vetor contíguo.

### 2.2 O Bullet já tem a lista de que a sincronização precisa **[código]**

`btDiscreteDynamicsWorld::addRigidBody` coloca em `m_nonStaticRigidBodies` todo corpo que não é estático na
entrada; `removeRigidBody` tira
([btDiscreteDynamicsWorld.cpp:562](../source/extern/bullet2/src/BulletDynamics/Dynamics/btDiscreteDynamicsWorld.cpp#L562)).
O `synchronizeMotionStates` original já percorre essa lista testando `isActive()` (linha 391).

Conferências de equivalência para `SynchronizeActiveMotionStates`:

- A lista inclui adormecidos e cinemáticos; o filtro `!isStaticOrKinematicObject() && isActive()` precisa ficar.
  Não vira uma lista de ativos, como o Codex já advertiu. O que se evita é visitar os estáticos.
- Estático → cinemático em tempo real (`RelativeTranslate`, `SetPosition` etc. ligam `CF_KINEMATIC_OBJECT`
  sem readicionar, [CcdPhysicsController.cpp:1816](../source/source/gameengine/Physics/Bullet/CcdPhysicsController.cpp#L1816)):
  o corpo fica fora da lista, mas a sincronização o ignoraria de qualquer forma.
- Suspend/Restore Dynamics e mudança de massa ou grupo passam por
  [UpdateCcdPhysicsController](../source/source/gameengine/Physics/Bullet/CcdPhysicsEnvironment.cpp#L971),
  que remove e readiciona, e a lista é refeita. Não achei código que limpe `CF_STATIC_OBJECT` sem readicionar.
  É o caso que um teste precisa cobrir.
- A lista é `protected`. O acesso exige subclasse ou acessor; a engine já modifica o Bullet embutido
  (`stepSimulationRun`), então um acessor não abre precedente.

**Jolt como referência:** `BodyManager` guarda corpos ativos num array com índice reverso
(`mIndexInActiveBodies`) e remoção por troca com o último. É a estrutura certa para "só os ativos", mas
exigiria ganchos de ativação e desativação no Bullet (`updateActivationState`, ilhas). Só vale se o primeiro
passo (não visitar estáticos) não bastar.

### 2.3 SIMD do Bullet por plataforma **[código]**

[btScalar.h](../source/extern/bullet2/src/LinearMath/btScalar.h#L80) define `BT_USE_SSE` e
`BT_USE_SIMD_VECTOR3` para MSVC; fora do Windows, só para `__APPLE__` x86 (linha 179). Linux com GCC e
Emscripten compilam sem os caminhos SSE escritos à mão do Bullet. O compilador ainda gera SSE2 escalar no
x86-64 e pode autovetorizar laços comuns; quanto depende da versão e das flags (o build Release usa `-O2`,
e o GCC só autovetoriza em `-O2` a partir da versão 12, a conferir no contêiner Ubuntu 22.04). O Bullet 3.26 tem a mesma seleção (cópia em `artifacts/`).
Consequências:

- **[hipótese]** No Linux o solver é mais lento que no Windows com a mesma cena. O Windows já usa o layout
  `BT_USE_SIMD_VECTOR3`, o que reduz o risco de alinhamento ao ligar SSE no Linux: as estruturas da engine
  já convivem com ele no MSVC.
- O BVH do `.cooked` é gravado no layout de memória e validado por compilador + `sizeof(btOptimizedBvh)`
  ([changelog 2026-10-18](changelog.md)). Ligar SSE só no Linux precisa entrar nessa chave, mesmo que o
  `sizeof` não mude.
- Física não é idêntica entre Windows e Linux hoje (SSE de um lado, escalar do outro). Isso interessa ao
  multiplayer: igualar o modo das duas plataformas pode **aproximar** os resultados, mas não promete
  determinismo entre compiladores.

### 2.4 Conclusão da física

O Bullet fica. O experimento cobre os três laços por controlador (substep, Car e sincronização) e o SSE no
Linux. A troca por Jolt continua rejeitada pelos motivos do Codex (soft body, veículos, `stepSimulation`
modificado, callbacks, compatibilidade dos jogos), aos quais acrescento: a colisão paralela própria
(`CcdCollisionDispatcher`) e o determinismo dela só foram validados em 2026-10-30.

## 3. Animação

### 3.1 Onde o tempo pode estar **[código]**

Por armature e por quadro: `BL_Action::Update` → `SetPoseByAction` →
[animsys_evaluate_action](../source/source/blender/blenkernel/intern/anim_sys.c#L1845) →
[animsys_evaluate_fcurves](../source/source/blender/blenkernel/intern/anim_sys.c#L1719). **Para cada fcurve**,
[animsys_store_rna_setting](../source/source/blender/blenkernel/intern/anim_sys.c#L1519) chama
`RNA_path_resolve_property` sobre o texto `pose.bones["Nome"].rotation_quaternion`, confere se é animável e
o tamanho do array, avalia a curva e escreve pelo RNA. Depois vêm `GetPose`/`BlendInPose` (cópia e mistura
da pose), `ApplyPose` → `BKE_pose_where_is` (hierarquia, constraints, IK) e o skinning.

Um personagem com 30 ossos × 10 canais tem ~300 resoluções de caminho em texto por quadro; 400 personagens,
~120 mil **[hipótese baseada na contagem; o custo unitário não foi medido]**. A engine não guarda esse
resultado: busquei `RNA_path`, `rna_path` e caches em `Ketsji/` e `Converter/`, e os únicos usos são de
conversão e NLA ([BL_NlaPlayer.cpp:254](../source/source/gameengine/Ketsji/BL_NlaPlayer.cpp#L254)).

### 3.2 Técnica proposta: amarração de fcurves (inspirada no ozz, sem o ozz)

Na primeira avaliação de cada par (action, armature), guardar para cada fcurve o destino já resolvido
(ponteiro do `bPoseChannel` e do campo `loc`/`quat`/`eul`/`size`, mais o índice). Nos quadros seguintes,
avaliar a curva com o mesmo `evaluate_fcurve` do Blender e escrever direto no campo. A matemática da curva
(Bézier, handles, modificadores) não muda; só a resolução de texto sai do quadro.

Contratos que precisam ser preservados:

- invalidar o cache quando a action, a armature, a pose (`pose` refeita por LibLoad, `replaceMesh`, troca
  de armature) ou a lista de fcurves mudam; curvas mudas ou desligadas (`FCURVE_MUTED`, `AGRP_MUTED`) seguem
  sendo puladas a cada quadro, porque o Python pode mudar a flag;
- canais que não são de osso (propriedades do objeto, shape keys pelo `Key`) seguem o caminho genérico;
- tarefas paralelas: o cache por (action, armature) só é escrito pela tarefa daquela armature;
- eventos de animação, half animations, catch-up, `setBoneRotationOffset` e blending não são tocados: atuam
  antes ou depois da escrita da pose.

### 3.3 ozz-animation

O ozz amostra trilhas próprias com interpolação **linear** (`Lerp` para translação/escala, `NLerpEst` para
rotação em `Interpolates`) a partir de um *ratio* em [0,1] e um `Context` que acompanha o cursor por trilha.
As actions do Blender são Bézier com handles e modificadores, em vários modos de rotação. Converter exige
reamostrar, com perda controlada por tolerância, e não reproduz IK, constraints, NLA nem offsets de osso.
Conclusão igual à do Codex (estudar), com uma diferença: a parte aproveitável agora é a ideia de preparar a
amarração e o cursor de keyframes, não a biblioteca. Cursor de keyframes por fcurve (evitar a busca binária
a cada quadro) é um segundo passo opcional, só se o perfil mostrar a busca depois do primeiro.

### 3.4 `m_animNeedsUpdateCache` (ponto 3 do Codex)

**[código]** Em [UpdateAnimations](../source/source/gameengine/Ketsji/KX_Scene.cpp#L2742): `clear()` + `emplace`
num `unordered_map` por atualização, `find` pelos workers, cópia para o `unordered_set`
`m_pendingAnimationDeformers` e depois para um `vector` em
[UpdateAnimationDeformers](../source/source/gameengine/Ketsji/KX_Scene.cpp#L2853); `anim_run_in_chunks` aloca o
vetor de blocos em cada chamada. Uma versão compacta caberia em vetores paralelos: `poseTasks[i]` e
`needsUpdate[i]`, com cada worker escrevendo só o próprio índice, e deduplicação por carimbo de quadro no
objeto ou por ordenação de ponteiros.

**[hipótese]** Para 400 objetos isso custa dezenas de microssegundos, contra 8,6 ms de `Animations`. Concordo
com o Codex: só fazer se aparecer no perfil. Os contratos que ele listou estão corretos e conferidos no
código (comentário longo sobre `GetDoAnimations()` em `UpdateAnimations`, eventos fora dos workers, pendentes
preservados no catch-up).

### 3.5 Skinning

**[código]** O caminho "RanGE Optimized" ([BGEDeformVerts](../source/source/gameengine/Converter/BL_SkinDeformer.cpp#L164))
percorre os pesos de comprimento variável (`MDeformVert::dw`) e soma matrizes Eigen por vértice. O GPU
Skinning já existe e cai para a CPU quando nenhum material liga "GPU Skinning" ou há grupos demais
([UseGPUSkinning](../source/source/gameengine/Converter/BL_SkinDeformer.cpp#L286)). O vetor
`boneIndices`/`boneWeights` de 4 influências já é montado na conversão para a GPU.

Antes de qualquer SIMD/ISPC no skinning, a pergunta é por que a cena de 400 personagens gasta 11,5 ms de
skinning na CPU com GPU Skinning disponível. Se for o material sem a opção, a solução existente vale mais
que uma biblioteca nova. Se a CPU continuar necessária (Web, muitos ossos), reaproveitar as 4 influências
compactas na CPU é o passo seguinte, sem dependência.

## 4. Culling de sombras e SIMD

**[código]** [BuildShadowCullCache](../source/source/gameengine/Ketsji/KX_Scene.cpp#L2127) monta um vetor de
`ShadowCullEntry` (ponteiro, layer, raio, centro, AABB e `mat3x4`,
[KX_Scene.h:325](../source/source/gameengine/Ketsji/KX_Scene.h#L325)). O teste de esfera usa centro, raio e
layer, cerca de 20 bytes de uma entrada de ~100 ou mais. [SphereInsideFrustum](../source/source/gameengine/SceneGraph/SG_Frustum.cpp#L54)
percorre 6 planos com saída antecipada, o que impede o compilador de vetorizar entre objetos.

**[hipótese]** Com os números da cena de 900 objetos e 43 passadas **[medido, 2026-10-30]**: ~39 mil
esferas × 6 planos por quadro, da ordem de 0,1–0,4 ms em escalar, dentro de `Shadows` = 4,7 ms. O ganho
máximo do SIMD é uma fração disso. Antes de ISPC, duas mudanças em C++ simples dariam a maior parte:

1. separar os dados quentes (centro, raio, layer) dos frios (AABB, matriz, ponteiro);
2. testar 4 objetos por vez sem saída antecipada, classificando INSIDE/INTERSECT/OUTSIDE por máscara. O
   compilador gera SSE2 no desktop e, com `-msimd128`, SIMD na Web.

A ordem de saída, as layers, `m_shadowDrawAllPending` e o teste de caixa para INTERSECT ficam iguais. O
experimento é barato porque o snapshot já existe, mas a prioridade é baixa enquanto não houver medida do
trecho. O DBVT continua fora das sombras por decisão registrada no próprio código (~14 ms nas passadas de
sombra, comentário em `KX_Scene::CalculateVisibleMeshes`).

**ISPC:** rejeitado para o build. Acrescenta um compilador a Windows, Linux e Emscripten para um kernel que
o C++ com dados separados já vetoriza. Não confirmei o suporte atual do ISPC a WebAssembly; mesmo com ele,
o custo de manter o compilador nas três plataformas continua.

## 5. Tarefas e threads

### 5.1 Estado atual **[código]**

| Pool | Quem usa no quadro | Onde |
|---|---|---|
| Agendador da engine (`BLI_task_scheduler_create(AUTO)`) | animação (pose, skinning), conversão assíncrona | [KX_KetsjiEngine.cpp:278](../source/source/gameengine/Ketsji/KX_KetsjiEngine.cpp#L278), [KX_Scene.cpp:2724](../source/source/gameengine/Ketsji/KX_Scene.cpp#L2724) |
| Agendador global do Blender (`BLI_task_scheduler_get`) | colisão paralela, um `BLI_task_parallel_range` por chamada de dispatch, ou seja, por substep | [CcdCollisionDispatcher.cpp:375](../source/source/gameengine/Physics/Bullet/CcdCollisionDispatcher.cpp#L375), [task.c:1135](../source/source/blender/blenlib/intern/task.c#L1135) |
| TBB 2020.3 (`parallel_reduce`, grão 256) | culling da câmera, só desktop | [KX_CullingHandler.cpp:101](../source/source/gameengine/Ketsji/KX_CullingHandler.cpp#L101) |
| `std::thread` avulsas | BVH compartilhado no carregamento | [CcdPhysicsController.cpp:198](../source/source/gameengine/Physics/Bullet/CcdPhysicsController.cpp#L198) |

O Codex escreveu "não iniciar um terceiro pool competindo com BLI_task e TBB", mas o agendador da engine e o
global do Blender já são dois pools `BLI_task` separados. Cada um cria threads conforme o número de CPUs.
`BLI_task_parallel_range` cria e libera um `TaskPool` por chamada, sobre o agendador global já existente:
as threads não são recriadas. Na colisão isso acontece no máximo uma vez por substep (11 no RolimaRacer), e
só quando há pelo menos 8 pares (`CCD_DISPATCH_MIN_PAIRS`); abaixo disso o caminho é serial. O skinning
tinha um padrão parecido (um pool por malha, aninhado), removido em 2026-10-29 **[medido]**. Lá eram
centenas de pools por quadro; aqui são até 11, então o custo provável é menor **[hipótese]**.

**[hipótese]** As fases quase não se sobrepõem no quadro (física, depois animação, depois culling), então o
risco de excesso de threads é baixo. A exceção é a conversão assíncrona (LibLoad), que roda no pool da
engine enquanto a física usa o global. Pode haver espera quando o TBB ainda gira (*spin*) logo depois do
culling, mas não tenho evidência.

### 5.2 Conclusão

Concordo que enkiTS/oneTBB não se justificam. O experimento útil é medir o tempo de criar o pool por substep
e as esperas por fase, e unificar o pool da colisão no agendador da engine **se** o tempo de criação
aparecer. Isso não exige biblioteca nova e reduz o número de pools em vez de aumentar. Atualizar TBB 2020 →
oneTBB só faria sentido por manutenção das dependências que já usam TBB (OpenVDB, OIDN, Embree estão em
`lib/`), não por desempenho do jogo.

## 6. Malhas e meshoptimizer

### 6.1 O contrato atual **[código]**

- Na conversão, vértices são compartilhados por posição + normal + tangente + UV + cor
  (`BL_SharedVertexPredicate`, [BL_BlenderDataConversion.cpp:1495](../source/source/gameengine/Converter/BL_BlenderDataConversion.cpp#L1495)).
  Em low poly com sombreamento chapado e UV por face, como na pintura por paleta, quase toda face tem
  vértices próprios. A reordenação para cache ajuda pouco quando há pouco compartilhamento.
- Material com nó Wireframe/baricêntrico **não** compartilha vértices e depende de `gl_VertexID % 3`
  (linha 1448). Reordenar triângulos inteiros mantém o canto; remapear vértices quebra o nó.
- Material invisível adiciona triângulos sem índices de desenho, e wire converte para arestas: as duas
  listas já diferem nesses casos.
- `.cooked`: [BL_CookedArrays::Save](../source/source/gameengine/Converter/BL_BlenderDataConversion.cpp#L1065)
  grava os índices de desenho e só grava os de triângulo quando diferem (`sameIndices`). Reordenar só os de
  desenho dobra os índices no arquivo para essas malhas.
- O `.cooked` é um **cache** da conversão: jogar um `.blend` sem `.cooked` refaz tudo. Se a reordenação
  existir só no cooking, a mesma cena renderiza com ordem diferente com e sem cache. Ela teria de rodar na
  conversão, com a chave e a versão do cooking atualizadas, e o cooking guardaria o resultado.
- Consumidores dos índices de desenho que tratam cada trio como um triângulo: `KX_DentDeformer`,
  `KX_DestructionManager`, `SortPolygons` (transparência). Reordenar trios inteiros não os quebra. O
  `KX_MeshBuilder` expõe os índices ao Python
  ([KX_MeshBuilder.cpp:177](../source/source/gameengine/Ketsji/KX_MeshBuilder.cpp#L177)); a ordem muda o que um
  script lê se ele copiar uma malha convertida. Raios, `getPolygon` e o BVH de picking usam os índices de
  triângulo ([KX_Mesh.cpp:613](../source/source/gameengine/Ketsji/KX_Mesh.cpp#L613)), que ficam como estão.
- Vertex fetch remap muda os índices dos vértices: `KX_VertexProxy` no Python, `m_vertexInfos`, shape keys,
  soft body e deformadores dependem deles. Rejeitado para malhas que o Python ou um deformador possam tocar.

### 6.2 O que eu faria diferente do Codex

1. **Medir offline antes de integrar.** `meshopt_analyzeVertexCache` e `meshopt_analyzeVertexFetch` rodam na
   CPU sem GPU. Basta exportar os arrays convertidos de malhas controladas geradas por script (low poly
   chapado com paleta, malha suave, grade de referência; casos no [plano](plano-processamento.md)) e comparar ACMR/ATVR antes e depois de `meshopt_optimizeVertexCache`. Se o ACMR atual
   já estiver perto do ótimo da topologia, o protótipo no conversor não vale.
2. **Considerar o shadow index buffer.** A engine faz dezenas de passadas só de profundidade (43 na cena de
   900 objetos). Com muitas costuras de UV/normal, `meshopt_generateShadowIndexBuffer` funde vértices pelos
   atributos escolhidos e reduz invocações nessas passadas. A chave precisa incluir tudo o que a passada de
   sombra lê: UV quando o material usa Shadow Casting Alpha ou recorte por alpha, ossos e pesos com GPU
   Skinning, e o que o vertex shader desloca (vento). Fundir só pela posição serve apenas a malhas opacas,
   sem deformação, com sombra comum. O próprio README avisa que, com poucas costuras, o ganho some.
   Exige um segundo IBO por array e a troca no caminho de override de sombra: é maior que a reordenação, mas
   mira o caso em que o low poly com costuras perde mais.
3. **A GPU fraca não é limitada por vértices hoje:** na medição da iGPU de 2026-10-25 o gargalo era o
   resolve de MSAA (notas de sessão; sem entrada correspondente no changelog). Qualquer ganho de vértice precisa ser medido na RX 6800M e na iGPU
   antes de entrar na prioridade.
4. **Compressão para a Web:** o codec de vértice/índice do meshoptimizer reduz o tamanho baixado sem perder
   dados. Só vale se o tamanho do `.cooked` e dos `.range` pesar no tempo de abertura fria da Web, o que não
   está medido (os 31 s de primeira abertura registrados em 2026-10-25 não foram decompostos entre download,
   compilação de shaders e conversão).
   Fica como estudo.

## 7. Web e Android

**[código]** `build-web-release`: `-O2`, sem `-pthread`, sem `-msimd128`, sem `WITH_TBB` nos defines do
`ge_ketsji` (o cache diz `WITH_TBB:BOOL=ON`, mas o alvo não recebe o define). O manifesto declara o
TaskScheduler serial ([make-runtime-manifest.py:45](../tools/web/make-runtime-manifest.py#L45)).

Separação pedida:

| Proposta | Exige mudar | Ganho portável? |
|---|---|---|
| `-msimd128` (autovetorização; opcional `-msse2` para o Bullet usar o caminho SSE) | só flags de build e empacotamento | Sim. Chrome 91+, Firefox 89+, Safari 16.4+; não exige SharedArrayBuffer |
| Dados compactos (amarração de fcurves, laços físicos sem estáticos, culling por blocos) | código C++ comum | Sim, em todas as plataformas |
| Threads (pthreads) | build separado, COOP/COEP na hospedagem (GitHub Pages não envia esses cabeçalhos), WebView do APK servindo com os cabeçalhos, áudio e Python revalidados | Não; projeto à parte |
| Trocar o agendador | nada habilita multicore sozinho | Não |

Riscos do `-msimd128`: um navegador sem SIMD não carrega o módulo, então seria preciso um segundo `.wasm` ou
aceitar o requisito mínimo. Intrinsics SSE mal traduzidas viram caminhos lentos (`WASM_SIMD_COMPAT_SLOW`
avisa no build). Ligar `BT_USE_SSE` no Emscripten exigiria mexer em `btScalar.h`; a autovetorização sozinha
é o primeiro passo.

## 8. O maior custo medido: Python

Nenhuma das sete bibliotecas toca no maior custo medido no jogo real: ~7 ms de scripts por quadro no
RolimaRacer **[medido, 2026-10-30]**. O CPython embutido já é 3.11 (`platform_win32.cmake`). Não proponho
trocar o interpretador sem perfil. O registro aqui é para a prioridade: um ganho de 0,2 ms na física pesa
menos que qualquer redução nos scripts, e a ferramenta de amostragem (`tools/debug/sampler`) e o Range Trace
já servem para medir os dois.

## 9. Propostas rejeitadas

- **Jolt no lugar do Bullet:** sem soft body equivalente ao `btSoftRigidDynamicsWorld`; veículos,
  constraints, callbacks, `stepSimulation` modificado, colisão paralela própria e `.cooked` de BVH teriam de
  ser refeitos e revalidados nos jogos. Fica só como referência de estrutura de corpos ativos.
- **Flecs/ECS:** a lição de dados em colunas já está aplicada onde pesa (snapshot de sombras,
  `RAS_DisplayArray::VertexData`, propriedades em vetor com hash). Integrar a biblioteca não tem benefício
  plausível sem reescrever `KX_GameObject` e a API Python.
- **ISPC:** ver seção 4.
- **enkiTS/oneTBB como troca de agendador:** nenhuma medida mostra desequilíbrio ou espera. A mudança
  acrescentaria pools.
- **ozz como backend dos personagens atuais:** interpolação linear reamostrada, sem IK/constraints/NLA. Seria
  um segundo sistema de animação a manter.
- **Vertex fetch remap no meshoptimizer:** quebra índices observáveis pelo Python, shape keys e o nó
  Wireframe; o ganho em low poly é incerto.
- **SIMD do culling antes de medir:** não rejeitado como técnica, mas rejeitado como prioridade.

## 10. Comparação com o estudo do Codex

Conferi as afirmações factuais do Codex no código: `RAS_Mesh::GetPolygon`, `BL_ConvertDerivedMeshToArray`,
`BuildShadowCullCache`, `anim_run_in_chunks`, TBB `2020_U3` em `versions.cmake`, o manifesto Web serial e o
`use_sleep = True` em `tools/create_perf_physics_anim_test.py`. Todas batem. As divergências estão no peso
dado a cada item e no que ficou de fora.

| Candidato | Conclusão do Codex | Minha conclusão | Concordância | Evidência | Experimento necessário | Prioridade final |
|---|---|---|---|---|---|---|
| Sincronização física (`SynchronizeActiveMotionStates`) | 1º experimento: medir filtragem; procurar lista no Bullet | Usar `m_nonStaticRigidBodies` (já existe); o custo provável é pequeno | Parcial: mesma direção, peso menor | Lista no Bullet 2.84 (linhas 562/391); vetor contíguo, uma vez por quadro | Junto com o item abaixo: contador de visitados/elegíveis + tempo | Média (dentro do experimento 3) |
| Laços por controlador (substep e caminho Car) | Não citado | Candidato maior que a sincronização: `std::set` inteiro 11×/quadro e 2×/quadro no Use Frame Rate | Lacuna do Codex | `SimulationSubtickCallback`, `ProceedDeltaTimeCar` linhas 1189/1216 | Tempo dos três laços em cenas controladas (mista, substeps, veículos) | **Alta (experimento 3)** |
| Bullet SSE no Linux | Não citado | Linux compila sem os caminhos SSE do Bullet; Windows usa | Lacuna do Codex | `btScalar.h` local e upstream 3.26 | Build Linux com `BT_USE_SSE`: tempo da física + cena de determinismo + chave do BVH cozido | Média |
| `-msimd128` na Web | Cita SIMD em geral para Web | Única melhoria Web/Android sem mudar hospedagem | Lacuna parcial | `build-web-release`; doc Emscripten | Build Web A/B nas cenas de física/animação, Chrome e Safari, tamanho do `.wasm` | **Alta (experimento 2)** |
| Mapa `m_animNeedsUpdateCache` | Candidato; medir preparação vs pose | Concordo: provável microssegundos; só se aparecer | Concordo | `UpdateAnimations`; 8,6 ms em `Animations` | Coberto pelo perfil do experimento 1 | Baixa |
| Resolução de caminho RNA por fcurve | Não citado (cita `animsys_evaluate_action` só como contrato) | Candidato principal da CPU em animação | Lacuna do Codex | `animsys_store_rna_setting` → `RNA_path_resolve_property` por curva e quadro | Perfil por amostragem da cena de 400 personagens; depois protótipo de amarração com comparação de poses | **Alta (experimento 1)** |
| ozz-animation | Estudar; backend restrito futuro | Estudar só a técnica; backend rejeitado para personagens atuais | Parcial | `Interpolates` linear; Blender Bézier + IK/NLA | Nenhum agora | Baixa |
| Skinning na CPU | GPU Skinning já existe; benefício estaria na pose | Concordo, e acrescento: entender por que a cena de 400 usa CPU | Concordo + extensão | `UseGPUSkinning`, 11,5 ms medidos | Mesma cena com GPU Skinning ligado nos materiais | Média |
| SIMD esferas × planos (sombras) | 3º experimento, com ISPC só após kernel | Técnica válida, ganho máximo < 0,4 ms; separar dados quentes antes de SIMD; sem ISPC | Parcial | `ShadowCullEntry` ~100 B; 39 mil testes/quadro estimados | Medir o trecho; se > 0,3 ms, blocos de 4 em C++ | Baixa |
| Agendador (enkiTS/oneTBB) | Não trocar; medir esperas | Não trocar; há 3 pools, não 2; pool criado por substep | Concordo + correção | `CcdCollisionDispatcher` usa o agendador global; `task.c:1135` | Tempo de criação do pool por substep e espera por fase | Baixa/Média |
| Web/Android multicore | Exige build/hospedagem | Concordo; separar o SIMD | Concordo | Manifesto, cache do build Web | Nenhum agora | Adiar |
| meshoptimizer: reordenar índices de desenho | Melhor candidato de biblioteca; protótipo no cooking | Primeiro análise offline; reordenar na conversão, não só no cooking; cuidado com `sameIndices` e com o Python | Parcial | `BL_CookedArrays::Save`, compartilhamento por atributo, iGPU limitada por MSAA | ACMR/ATVR offline das malhas reais | Média (4º) |
| meshoptimizer: shadow index buffer | Não citado | Mais promissor que a reordenação em low poly com costuras | Lacuna do Codex | README (Shadow indexing); 43 passadas de sombra | Contar a redução de vértices offline nas mesmas malhas | Média, depois do item acima |
| meshoptimizer: vertex fetch remap | "Depois, se útil" | Rejeitado para malhas acessíveis ao Python/deformadores | Divergência | `KX_VertexProxy`, `gl_VertexID % 3` | — | Rejeitado |
| Jolt / Flecs / ISPC no build | Adiar/estudar | Rejeitado como integração | Concordo | Seção 9 | — | Rejeitado |
| Scripts Python | Fora do escopo | Fora das bibliotecas, mas é o maior custo medido | Lacuna de prioridade | ~7 ms no RolimaRacer | Perfil separado (fora desta pesquisa) | Registro |

## 11. Três primeiros experimentos

**1. Perfil por amostragem da pose na cena de 400 personagens.** Rodar `tools/create_perf_physics_anim_test.py`
(400) com o amostrador de `tools/debug/sampler` e separar, dentro de `Animations`: `RNA_path_resolve_property`,
`evaluate_fcurve`, `GetPose`/blend, `BKE_pose_where_is` e o tempo de preparo/espera das tarefas. Rodadas de
~10 s, A/B não é necessário. **Por quê:** é o maior custo de CPU medido fora do Python e nenhum código muda.
Se a resolução RNA passar de ~20% do trecho, o protótipo de amarração de fcurves vem a seguir, aceito só com
poses idênticas em quadros fixos (o mesmo critério de "0 pixels diferentes" de 2026-10-29). Cada hipótese é julgada pelo próprio
custo no mesmo perfil: o mapa de `UpdateAnimations` e o preparo das tarefas têm linhas próprias, e o ozz só
volta à pauta se a avaliação das curvas, e não a resolução RNA, for o que pesa.

**2. Build Web com `-msimd128`, A/B.** Mesmo código, dois `.wasm`: medir física, animação e quadro nas cenas
de perfil Web existentes ([web-profile-validation-plan.md](web-profile-validation-plan.md)) em Chrome e,
se possível, Safari/Android WebView, e conferir o tamanho do `.wasm`. **Por quê:** a Web roda numa thread só
e é a plataforma com menos CPU por quadro. Entre as propostas, é a única para Web/Android que dispensa COOP/COEP e
mudanças no código. O ganho depende do código e precisa ser medido. A decisão depende de dois números: o ganho e se perder navegadores antigos é aceitável.

**3. Os laços por controlador da física.** Com `CM_WorkCount` (já usado para substeps) e o profiler, contar e
cronometrar separadamente `SimulationSubtickCallback`, `SynchronizeActiveMotionStates` e os laços de
`ProceedDeltaTimeCar`. Usar cenas controladas geradas por script (poucos ativos e milhares de estáticos,
substeps variáveis, veículos), com e sem Use Frame Rate; o jogo fica fora das medições (ver o
[plano](plano-processamento.md)). **Por quê:** cobre a hipótese do Codex e a que ele não viu com uma
única instrumentação. Se a soma passar de ~0,2 ms, as correções são pequenas e locais: percorrer
`m_nonStaticRigidBodies` e manter um vetor só dos controladores com limite de velocidade, que é atualizado
nos mesmos pontos em que o controlador entra e sai do mundo. O teste de determinismo
(`tools/debug/cenas/criar_cena_determinismo_fisica.py`) confere se a ordem dos efeitos ficou igual.

Logo depois desses três: a análise offline do meshoptimizer (ACMR/ATVR e shadow index). É barata, mas não
entra entre os três porque a GPU fraca hoje é limitada por MSAA, não por vértices.

## Revisão do Codex (2026-11-04)

O Codex conferiu este documento e propôs cinco correções. Cada uma foi conferida no código antes de entrar:

| Ponto do Codex | Decisão | Conferência |
|---|---|---|
| O pool por substep usa o agendador existente; com poucos pares a colisão é serial | Aceito | `BLI_task_pool_create_suspended(task_scheduler, …)` em `task.c`; `CCD_DISPATCH_MIN_PAIRS = 8` em `CcdCollisionDispatcher.cpp` |
| Sem `BT_USE_SSE` não é ausência de SIMD; "SIMD de graça" promete demais | Aceito | x86-64 sempre gera SSE2; o build Release usa `-O2` (`macros.cmake` troca `-O3` por `-O2`); a autovetorização depende da versão do GCC |
| `-msimd128` sem ganho garantido | Aceito | Já tratado como experimento; texto da conclusão ajustado |
| O índice de sombra precisa preservar os atributos lidos no passe | Aceito | Shadow Casting Alpha descarta pelo alpha na passada de sombra (changelog 2026-10-19); GPU Skinning lê ossos; o próprio README do meshoptimizer cita UV e skinning |
| Perfil sem destaque para RNA não elimina o mapa da animação | Aceito | Texto do experimento 1 reescrito: cada hipótese pelo próprio custo |

A ordem de experimentos que o Codex propôs coincide com a da seção 11, com o meshoptimizer como 4º. O
plano consolidado está em [plano-processamento.md](plano-processamento.md).

## Conferência deste documento

`tools/check_docs.py` só enumera arquivos rastreados pelo Git, e este arquivo ainda é novo. Ele foi conferido
à parte, importando `conferir_links` e `conferir_arq_linha` do próprio script: **0 erros e 0 avisos**
(o estudo do Codex, conferido do mesmo jeito, também deu 0/0). As âncoras `#L` deste documento foram
conferidas uma a uma contra a linha de destino. A conferência global antes desta pesquisa tinha 168 erros e 58 avisos, todos nos
mapas de código (`docs/code-map-*.md`) e anteriores a este documento (saída em
`artifacts/pesquisa-processamento-claude/check-docs-global-antes.txt`).
