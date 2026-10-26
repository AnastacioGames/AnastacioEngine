# Revisão de KX_GameObject: núcleo e contratos de estado

Data: 2026-10-26. Continuação da frente 1 do [levantamento](levantamento-modulos-criticos.md),
após a [revisão de KX_Scene](revisao-kx-scene.md). A frente 8, dados/editor/exportação, está com Claude.

Continuação: a [revisão dos bindings Python](revisao-kx-gameobject-python.md) cobre integralmente
os dois arquivos de bindings e registra os testes posteriores. O escopo abaixo descreve a primeira rodada.

## Correções posteriores validadas em 2026-10-26

OBJ-01, OBJ-02 e OBJ-03 foram corrigidos no núcleo, sem alterar o header:

- Autoatribuição de LOD retorna antes de liberar ou reinicializar o manager existente.
- Ao retirar um objeto já culled da última opção de atividade, a lógica também é retomada.
- A inversão da escala verifica cada eixo do pai. Setters mundiais preservam os valores locais
  quando a transformação é singular; `SetParent` rejeita o novo vínculo antes de alterar a hierarquia.

Editor e player recompilados. Os modos `basic`, `culling`, `lod_control` e `lod_self`, com
`GAMEOBJECT_REVIEW_VERIFY=1`, completaram 45 frames e saída zero. O caso de autoatribuição preserva
os dois níveis do LOD; ambos os objetos de culling voltam ao estado 1 e a contagens iguais de lógica.
O teste de transformação cobre separadamente escala zero em X, Y e Z e rejeição de parenting singular.
Os contratos de réplica OBJ-04/05 e riscos OBJ-06/07 continuam pendentes.

Evidências posteriores em `artifacts/correcoes-gameobject-20261026/`, separadas das reproduções
originais. O detector em cena parada registrou zero em `sceneNodeUpdates`, `transformSyncs`,
`boundsPushes`, `meshMatrixChanges` e `updateNotifies` após aquecimento. Não é medição de ganho de FPS.
As correções dos bindings e a validação conjunta estão no [relatório complementar](revisao-kx-gameobject-python.md).

## Escopo e resultado da análise original

Leitura integral, em ordem, de `KX_GameObject.cpp` (2.731 linhas) e `KX_GameObject.h` (1.422 linhas):
4.153 linhas, incluindo declarações, condicionais de compilação e comentários. Os dois arquivos de
bindings Python foram consultados nos caminhos necessários às reproduções; ainda não receberam leitura
integral nesta rodada. Conversor, SceneGraph, contagem de referências e suspensão de lógica foram
seguidos seletivamente para conferir os contratos do núcleo.

Três defeitos reproduzidos no standalone. Dois outros comportamentos de réplica foram confirmados,
mas precisam de decisão sobre o contrato esperado. Nenhuma correção de C++ foi aplicada.

| ID | Prioridade/estado | Resultado |
|---|---|---|
| OBJ-01 | P1, reproduzido | Autoatribuição de LOD libera o próprio manager; processo termina com corrupção de heap |
| OBJ-02 | P2, reproduzido | Desligar o último culling de física deixa a lógica suspensa |
| OBJ-03 | P2, reproduzido | Escala zero em um eixo do pai produz posição/escala local infinita |
| OBJ-04 | Contrato pendente | Réplicas compartilham a lista de callbacks de colisão |
| OBJ-05 | Contrato pendente | Parâmetros armazenados de veículo são zerados na réplica |
| OBJ-06 | Risco estático, sem reprodução | Ponteiro do chão das partículas não acompanha remoção do objeto |
| OBJ-07 | Risco estático, sem reprodução | Liberação de recursos não examina todas as malhas guardadas pelo LOD |

P1 corresponde a encerramento do processo no teste. P2 corresponde a estado incorreto observado.
Não são prioridades baseadas em medição de desempenho. Os achados anteriores de `KX_Scene`, incluindo
mutação da lista no executor comum de callbacks, não são contados novamente como defeitos novos.

## Responsabilidade e posse dos dados

`KX_GameObject` é a ligação entre objeto lógico, nó hierárquico, física e desenho. A cena organiza o
ciclo de vida coletivo; o objeto mantém seu estado individual e encaminha operações aos controllers.
Uma referência Python ao proxy não equivale automaticamente a uma referência nativa ao objeto exposto.

O nó, controllers, action manager e buffers de partículas usam posse expressa por `unique_ptr`.
Malhas e dados de conversão são referências a recursos administrados externamente. O LOD usa
`AddRef`/`Release`, enquanto callbacks são objetos Python com contagem própria. Misturar esses modelos
sem preservar o objeto durante uma substituição é a causa de OBJ-01.

A cópia não pode ser avaliada isoladamente: `KX_Scene::AddNodeReplicaObject` reconstrói nós,
controllers e buffers antes de religar a lógica. Ponteiros nulos no construtor de cópia não comprovam
por si só perda de funcionalidade. Identificador de rede e constraint física também não devem ser
reutilizados automaticamente por uma nova instância.

## OBJ-01 — autoatribuição do LOD usa memória liberada

**Código:** [SetLodManager](../source/source/gameengine/Ketsji/KX_GameObject.cpp#L1509),
[binding](../source/source/gameengine/Ketsji/KX_GameObject_Python.cpp#L2815).

O setter libera `m_lodManager` antes de guardar e incrementar a referência do argumento recebido.
Se ambos apontam para o mesmo manager e o objeto possui a última referência nativa, `Release()`
destrói o manager. A atribuição seguinte guarda um endereço inválido e `AddRef()` acessa esse endereço.
O proxy retornado pelo getter não fornece a referência nativa que impediria essa destruição.

Reprodução: `manager = obj.lodManager; obj.lodManager = manager`. A consulta anterior encontra dois
níveis. A atribuição retorna, mas a consulta seguinte lança `SystemError`, informando que os dados da
engine foram liberados. Ao encerrar, o processo termina com `3221226356` (`0xC0000374`, corrupção de
heap). Isso ocorreu nas duas execuções do caso. Não foi obtido backtrace nativo desse encerramento.

Controle: o mesmo objeto e duas consultas ao mesmo proxy, sem chamar o setter, mantêm dois níveis
e encerram normalmente após 45 frames. O hash do executável permaneceu igual entre os casos.

Direção de correção: tratar igualdade de ponteiros ou adquirir a nova referência antes de liberar
a antiga, preservando as operações de restauração da malha original. O setter de animation event
manager contém padrão semelhante de liberação antes da aquisição; não houve reprodução desse segundo
caminho, nem confirmação de um chamador que faça autoatribuição.

## OBJ-02 — desligar culling de física não restaura a lógica

**Código:** [UpdateActivity](../source/source/gameengine/Ketsji/KX_GameObject.cpp#L1688),
[SetActivityCulling](../source/source/gameengine/Ketsji/KX_GameObject.cpp#L2398).

Ao afastar um objeto com apenas `physicsCulling`, `UpdateActivity` também chama `SuspendLogic()`.
Ao desativar a opção, o setter restaura a física, mas só chama `ResumeLogic()` no ramo da flag de
lógica. Como não resta nenhuma opção de culling, remove o objeto da lista de atualização e restaura
sua elegibilidade para renderização. A lógica continua suspensa e não haverá nova passagem por
`UpdateActivity` para retomá-la.

O teste compara dois objetos: um só com culling de física e outro só com culling de lógica. Ambos
se afastam no frame 10; as opções são desligadas no frame 20; ambos voltam para perto no frame 30.

| Frame | Execuções da lógica: física | Execuções da lógica: controle | Estado: física / controle |
|---:|---:|---:|---|
| 9 | 8 | 8 | 1 / 1 |
| 15 | 10 | 10 | 536870912 / 536870912 |
| 21 | 10 | 10 | 536870912 / 1 |
| 29 | 10 | 18 | 536870912 / 1 |
| 40 | 10 | 29 | 536870912 / 1 |

O estado `536870912` corresponde ao estado usado pela suspensão em `SCA_IObject`. O controle retoma;
o objeto com culling de física continua parado mesmo perto da câmera. Ambos os flags já estão
desligados. O teste usa corpos estáticos: comprova a suspensão da lógica, sem medir retomada de
simulação dinâmica. A correção anterior de restauração da lista de render não cobre essa saída.

Direção de correção: a saída do culling precisa desfazer o estado que ele efetivamente suspendeu,
sem desfazer suspensões manuais independentes. Conferir também mudanças de flags enquanto já suspenso.

## OBJ-03 — transformação inversa aceita escala singular

**Código:** [NodeSetWorldScale](../source/source/gameengine/Ketsji/KX_GameObject.cpp#L2216),
[NodeSetWorldPosition](../source/source/gameengine/Ketsji/KX_GameObject.cpp#L2237).

Os setters verificam `mt::FuzzyZero(parentScale)` antes de dividir pelos componentes da escala do
pai. Para vetores, esse teste só retorna verdadeiro quando todos os componentes são aproximadamente
zero. Um pai com escala `(0, 1, 1)` passa pela proteção, mas o primeiro divisor é zero.

Reprodução com pai e filho vazios, sem controller físico: `child.worldPosition = (2, 3, 4)` produz
posição local `(inf, 3, 4)`; `child.worldScale = (2, 3, 4)` produz escala local `(inf, 3, 4)`.
Com o pai em escala unitária, a posição local é `(2, 3, 4)`. Os resultados são consultados diretamente
pela API; não dependem de captura visual. O gerador restaura valores finitos depois de registrar o caso.

Direção de correção: definir o contrato para transformação não invertível e verificar cada divisor
antes da divisão. `SetParent` também usa a proteção vetorial ao construir a transformação inversa;
esse caminho foi identificado por leitura, sem reprodução separada nesta rodada.

## Comportamentos de réplica que exigem decisão de contrato

**OBJ-04:** o [construtor de cópia](../source/source/gameengine/Ketsji/KX_GameObject.cpp#L165)
reutiliza `m_collisionCallbacks` e incrementa sua referência Python. As listas de callbacks de quebra,
explosão e deformação recebem cópias de lista. No teste, um template inativo com callback e suas duas
réplicas compartilham a lista de colisão; limpar a lista de uma réplica deixa as três listas vazias.
O compartilhamento é confirmado. Antes de alterar, decidir se há compatibilidade legada que o exija;
uma lista por instância também exige decidir como tratar callbacks vinculados ao template.

**OBJ-05:** o mesmo construtor reinicializa torque máximo, RPM e relações de marcha, além do handle
de constraint. O template recebe `321`, `7654` e `[3, 2, 1]`; a réplica retorna `0`, `0` e `[]`.
O reset dos parâmetros armazenados está confirmado, mas o teste não constrói um veículo nativo com
rodas. Não comprova que um veículo completo deixe de funcionar. Separar parâmetros de autoria do
handle físico e validar a herança esperada antes de corrigir.

## Riscos encontrados por leitura, ainda sem reprodução

**OBJ-06:** [UpdateParticles](../source/source/gameengine/Ketsji/KX_GameObject.cpp#L918)
consulta a posição de `m_collisionGroundObject`. O membro é ponteiro cru; seu setter só atribui o
endereço. Nos caminhos consultados não há registro para invalidá-lo quando o chão é removido.
Remover o chão enquanto o emissor sobrevive pode deixar acesso a objeto destruído. A réplica começa
com esse ponteiro nulo; a reconstrução de buffers consultada não restabelece a associação ao chão.
Falta um teste específico com atualização de partículas GPU e remoção do chão.

**OBJ-07:** [RemoveRessources](../source/source/gameengine/Ketsji/KX_GameObject.cpp#L1045)
examina as malhas atuais do objeto, mas não percorre as malhas retidas nos níveis do LOD. O conversor
posteriormente destrói os recursos da biblioteca. É necessário verificar bibliotecas com níveis
distribuídos entre recursos: uma malha de nível não atual pode sobreviver no manager como ponteiro
inválido; uma lista de malhas esvaziada também conflita com consumidores que usam `front()`.
Não foi reproduzido crash com `LibLoad`/`LibFree`; filtros de visibilidade podem impedir parte dos
caminhos. Não afirmar que toda liberação com LOD falha.

Outra inconsistência documental: o comentário de `GetParent` no header promete referência
incrementada, mas a implementação retorna ponteiro emprestado. Nenhuma falha de um chamador foi
demonstrada. A revisão integral dos bindings fica para outra rodada; não inclui conclusão sobre
todo wrapper de partículas, raycast ou conversão de argumentos.

## Registro da leitura integral

As faixas abaixo são contíguas e cobrem todo o núcleo. A tabela resume a compreensão da leitura;
não substitui o código nem afirma que cada linha tenha um teste independente.

| Linhas de KX_GameObject.cpp | Responsabilidade e contrato conferido |
|---|---|
| 1–119 | Licença, dependências e inicialização das informações de culling |
| 120–164 | Estado inicial sem controllers, registros ou buffers ativos |
| 165–232 | Cópia seletiva; separação entre recursos compartilhados e estado reconstruído; OBJ-04/05 |
| 233–302 | Destruição, managers e referências Python; ordem de liberação |
| 303–494 | Parâmetros de veículo, identidade, propriedades e vínculos de instâncias |
| 495–578 | Instalação do controller físico, constraints e replicação |
| 579–711 | Parenting, prevenção de ciclos, transformação relativa e transição física |
| 712–783 | Action manager criado sob demanda; registro na cena quando a ação inicia |
| 784–958 | Parâmetros e reconstrução de buffers, modo misto e chão das partículas; OBJ-06 |
| 959–1034 | Camadas de animação, ativação gráfica recursiva e filtros de colisão |
| 1035–1068 | Réplica e remoção de recursos; retorno após remover malhas evita iterador inválido |
| 1069–1360 | Encaminhamento de dinâmica, damping, CCD, soft body, forças e movimentos ao controller |
| 1361–1508 | Matriz do Blender, mesh users, buckets, substituição e remoção de malhas |
| 1509–1655 | Posse do LOD, seleção por distância e orientação de impostor; OBJ-01 |
| 1656–1687 | Manager de eventos de animação e religação aos sensores da réplica |
| 1688–1765 | Entrada/saída do culling por distância; lógica, física e lista de render; OBJ-02 |
| 1766–1830 | Sincronização SceneGraph/controllers, alternância de animação e LOD visível |
| 1831–1948 | Visibilidade, oclusão e debug recursivos; camadas e índice de passe |
| 1949–2087 | Velocidades, cor e alinhamento gradual de um eixo a um vetor |
| 2088–2162 | Massa, inércia, velocidades e gravidade; fallback quando não há controller |
| 2163–2335 | Setters/getters de transformação, identidade de rede e vínculo ao nó; OBJ-03 |
| 2336–2437 | Bounds/AABB e alteração das flags/registro do culling; OBJ-02 |
| 2438–2509 | Suspensão explícita e registro de callbacks no ambiente físico |
| 2510–2610 | Execução de callbacks de colisão/destruição e liberação dos argumentos temporários |
| 2611–2656 | Travessia de filhos/ancestrais e armazenamento de componentes |
| 2657–2731 | Atualização/profiling de componentes, consulta da cena e religação entre réplicas |

| Linhas de KX_GameObject.h | Contrato declarado conferido |
|---|---|
| 1–123 | Dependências, classe-base e flags/raios de atividade |
| 124–227 | Membros, modelos de posse, veículo, animação e buffers de partículas |
| 228–455 | Interface inicial, callbacks, hierarquia, controllers e configuração de partículas |
| 456–730 | Chão das partículas, dinâmica, animação e operações sobre malhas |
| 731–1075 | Transformações, visibilidade, identidade, LOD, bounds e acesso a estado |
| 1076–1149 | Suspensão, colisões, componentes e início da interface Python |
| 1150–1294 | Declarações dos métodos expostos ao Python; implementação fora deste header |
| 1295–1422 | Getters/setters Python, hooks de tipo e fechamento das condicionais |

Não classificados como defeitos: controllers ausentes antes da reconstrução de réplica; manager de
ações criado sob demanda; ativação gráfica de objetos oclusores invisíveis; cálculo de distância
ao quadrado com raios também ao quadrado; descarte de identificadores físicos na nova instância.
`GetDoAnimations` altera a alternância interna, portanto seus consumidores precisam consultá-lo na
cadência prevista; a cena já mantém cache para evitar múltiplas alternâncias no mesmo frame.

## Reprodução e rastreabilidade

Gerador versionável: [criar_cena_revisao_gameobject.py](../tools/debug/cenas/criar_cena_revisao_gameobject.py).
Cena, inspeção, JSONs de resultado e logs ficam em `artifacts/revisao-gameobject-20261026/`, ignorado
pelo Git. Nenhum projeto do usuário foi usado. O arquivo foi salvo, reaberto e inspecionado quanto
a objetos, materiais, LOD, controladores MODULE e ligações dos sensores.

```powershell
build/bin/AnastacioEngine.exe -b --factory-startup --python tools/debug/cenas/criar_cena_revisao_gameobject.py -- artifacts/revisao-gameobject-20261026
build/bin/AnastacioEngine.exe -b --factory-startup --python tools/debug/cenas/criar_cena_revisao_gameobject.py -- artifacts/revisao-gameobject-20261026 inspect
$env:RANGE_NO_CRASH_DIALOG = '1'
$env:GAMEOBJECT_REVIEW_CASE = 'basic' # repetir com culling, lod_control e lod_self
build/bin/AnastacioRuntime.exe --server artifacts/revisao-gameobject-20261026/revisao_gameobject.range
```

Geração e inspeção encerraram com código zero. `basic`, `culling` e `lod_control` completaram 45 frames
e encerraram com código zero; `lod_self` reproduziu o encerramento descrito em OBJ-01. Não houve build
novo: executou-se a instalação existente em `build/bin/`. Não há validação visual, benchmark,
sanitizer ou teste de outra plataforma nesta rodada.

`review_manifest.json` registra HEAD observado `cba665e4`, linhas e hashes dos arquivos analisados.
Os dois fontes permaneceram com estes SHA-256 durante a revisão:

- C++: `8d709430c5c2333d975d440ac4064d682e79a77b5fd58d2399355e325985f461`.
- Header: `3221f64067c875626896938dcf7f48e2bef3529da0fae57dc31e90599d25f169`.

O manifesto dos testes registra o executável com SHA-256
`d114417a22c0e0704c495353f4db2fe70f0117d8fda904f41157c22d07fa00c0`, sem alteração entre os
quatro modos. Isso identifica o binário exercitado; não equivale a provar correspondência integral
entre todas as unidades desse binário e o HEAD. Alterações concorrentes de editor/dados foram
preservadas e ficam fora das conclusões deste relatório.
