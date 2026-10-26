# Revisão de KX_GameObject: bindings Python

Data: 2026-10-26. Continuação da frente 1 do [levantamento](levantamento-modulos-criticos.md),
complementando a [revisão do núcleo](revisao-kx-gameobject.md). A frente 8 permanece com Claude.

## Correções posteriores validadas em 2026-10-26

PY-01 a PY-08 corrigidos nos dois arquivos de bindings:

- `meshes` transfere a referência do proxy à lista; `lodManager` ausente usa `Py_RETURN_NONE`.
- Setters de damping retornam falha antes de alterar o controller quando a conversão falha.
- Todos os caminhos de raycast vazio escolhem a aridade conforme `poly`.
- Torque/RPM e relações de marcha verificam o intervalo de float antes da conversão. Overflow
  lança `OverflowError` e preserva os parâmetros anteriores, inclusive o vetor de marchas inteiro.
- O getter por chave só converte Unicode quando a chave é textual e propaga erros reais do dicionário.
- Pose matching usa destino `int` para o formato `p`. Half animations exige exatamente um argumento;
  uma segunda entrada agora produz `TypeError`, em vez de ser aceita por um parser sem destino.
- Os setters de peso e velocidade de camada aceitam as keywords registradas, mantendo chamadas
  posicionais e mistas. Cada método usa sua própria lista de nomes com o parser público do Python.

O teste de keywords detectou que `EXP_ParseTupleArgsAndKeywords` mantém um `_PyArg_Parser` estático
por instanciação de tipos do template, não por método/formato. Duas chamadas com destinos `short*`
e `float*` acabaram compartilhando nomes. A correção local evita esse helper nesses dois métodos.
O header comum não foi alterado nessa primeira rodada. Na continuação, o cache compartilhado e
o lifetime dos nomes foram corrigidos globalmente; os 25 usos receberam conferência de formatos
e destinos. Resultados e limites estão na [revisão do helper](revisao-parser-python.md).

Build de `RangeEngine` e `RangeRuntime` concluído. O modo `verify` completou dez frames e confirmou
referências estáveis, rejeição de entradas inválidas sem mutação, overflow, raycast com/sem acerto,
chaves textuais/inteiras/tuplas, keywords e contratos dos parsers. Consultas de `None` são aquecidas
antes da medição: a primeira passagem mostrou variação única de -1; a passagem medida variou zero,
em vez da perda de uma referência a cada consulta observada antes da correção. Esse teste verifica
equilíbrio após inicialização, sem atribuir uma causa definitiva à variação inicial do interpretador.

Os modos `half_one` e `soft_pose` também completaram dez frames. Os quatro modos do núcleo
completaram 45 frames. Todos encerraram com código zero e hash estável do runtime:
`042772db68293d0e9b347ca97495ac0a6625771c04327a6359c01026e2c42960`.
CTest final: 15/15 testes passaram. Verificador de trabalho repetido e selftest passaram; na cena
estática, os cinco contadores de atualização acompanhados ficaram em zero após aquecimento.
`passUniforms`, binds e draw calls continuam presentes por serem trabalho de desenho; não se afirmou
que todo trabalho por frame foi eliminado.

Evidências em `artifacts/correcoes-gameobject-20261026/`: JSONs das duas suítes, inspeções de cenas,
log do detector e manifesto de fontes/binários. O primeiro início de testes foi descartado porque
outro build substituía o executável; o build e os testes finais foram executados após essa concorrência.
O [mapa atualizado](code-map-kx-gameobject.md) aponta para o código após as correções. As contagens,
linhas e hashes nas seções seguintes registram a análise original, anterior às mudanças.

## Escopo e resultado da análise original

Leitura integral de `KX_GameObject_Python.cpp` (2.871 linhas) e `KX_GameObject_PyMethods.cpp`
(1.857 linhas), acompanhando argumentos, retornos, exceções, posse e alterações de estado.
São mais 4.728 linhas; junto ao núcleo e header, 8.881 linhas da classe revisadas nas duas rodadas.
Dependências externas à classe receberam consulta seletiva, não auditoria integral.

Seis problemas novos foram reproduzidos sem encerramento anormal do processo. Duas chamadas violam
o contrato do parser C, mas os testes delas terminaram normalmente neste binário; não há crash
demonstrado nesses casos. Nenhuma correção de C++ foi aplicada.

| ID | Estado | Resultado |
|---|---|---|
| PY-01 | Reproduzido | Cada leitura de `meshes` deixa uma referência extra por proxy de malha |
| PY-02 | Reproduzido em Python 3.11 | `lodManager` ausente retorna `None` sem incrementar referência |
| PY-03 | Reproduzido | Atribuição inválida de damping altera o valor e retorna sucesso com exceção pendente |
| PY-04 | Reproduzido | Raycast de comprimento zero retorna três itens mesmo com `poly=1/2` |
| PY-05 | Reproduzido | Número finito em double vira infinito ao armazenar parâmetro de veículo em float |
| PY-06 | Reproduzido | Chave inteira pode ser armazenada e lida por `get`, mas falha com colchetes |
| PY-07 | Contrato C incorreto; sem crash no teste | Parser `p` recebe endereço de `bool` em `setSoftPoseMatching` |
| PY-08 | Contrato C incorreto; sem crash no teste | `setHalfAnimations` anuncia dois argumentos e fornece um destino ao parser |

PY-01 a PY-06 são problemas de referências, consistência de API e estado, tratados como P2 nesta
revisão. Para PY-07/08, corrigir o contrato antes de inferir a gravidade prática em outras compilações.
Não repetir OBJ-01: a autoatribuição do LOD já está documentada no relatório do núcleo.

## Como os bindings funcionam

A tabela `Methods` escolhe a convenção de chamada: nenhum argumento, um objeto, tupla, argumentos
nomeados ou FASTCALL. As macros geram wrappers que conferem a validade do proxy antes de encaminhar
ao método C++. Isso protege objetos já invalidados na entrada; não substitui a validação de cada
conversão nem resolve reentrância durante uma chamada.

A tabela `Attributes` aponta para campos ou funções. Para atributos com funções, o despachante
comum devolve diretamente o status do setter: cada setter deve detectar erros antes de alterar o
controller. Esse detalhe explica PY-03. O nome do atributo também seleciona campos das estruturas
de destruição, com offsets e tipos declarados em tabela.

Vetores e matrizes mathutils podem ser views com callback: ler consulta o objeto atual e escrever
encaminha ao setter C++. Uma view não é um snapshot independente. As operações sobre posição,
orientação e escala chamam a sincronização apropriada; atribuições de matrizes completas seguem
outro caminho e merecem teste específico de sincronização imediata, ainda não realizado aqui.

Propriedades usam dois armazenamentos: `EXP_Value` para valores compatíveis e `m_attr_dict` para
objetos Python. Acesso, atribuição, exclusão, pertencimento e `get` precisam concordar sobre a chave
e sobre exceções. O caminho rápido de números modifica o `EXP_Value` existente; não o classificamos
como defeito simplesmente por evitar uma alocação.

## PY-01 — leitura de meshes deixa referência extra

**Código:** [pyattr_get_meshes](../source/source/gameengine/Ketsji/KX_GameObject_Python.cpp#L2607),
[GetProxyPlus_Ext](../source/source/gameengine/Expressions/intern/PyObjectPlus.cpp#L1173).

`GetProxy()` já incrementa a referência Python para entregar seu retorno. O getter de `meshes`
incrementa novamente antes de `PyList_SET_ITEM`, que recebe a referência destinada à lista.
Quando a lista temporária desaparece, sobra um incremento sem liberação.

Teste: manter uma referência ao primeiro proxy, medir `sys.getrefcount`, consultar e descartar
`obj.meshes` 100 vezes. A contagem aumenta exatamente 100. Não foi medido crescimento de RSS:
o resultado comprova o desequilíbrio de referências ao proxy, não 100 novas malhas nativas.

Direção de correção: transferir à lista somente a referência retornada por `GetProxy()`.

## PY-02 — ausência de LOD retorna referência emprestada de None

**Código:** [pyattr_get_lodManager](../source/source/gameengine/Ketsji/KX_GameObject_Python.cpp#L2815).

O ramo com manager retorna o proxy com referência incrementada; o ramo vazio retorna `Py_None`
diretamente. O chamador Python recebe ambos como referências possuídas e libera o resultado.
O ramo vazio, portanto, reduz uma referência que não adquiriu.

Teste no Python embarcado 3.11.7: 30 consultas e descartes de `animationEventManager` ausente,
que usa `Py_RETURN_NONE`, variam a contagem de `None` em zero. As mesmas 30 consultas de `lodManager`
ausente variam em -30. O teste terminou normalmente; não se tentou esgotar referências nem provocar
encerramento. Outras versões de Python podem tratar singletons de forma diferente; este é o
resultado do runtime local, não uma afirmação sobre todas as versões.

Direção de correção: usar retorno de `None` com a referência exigida pela API, como no getter de
animation event manager. O contrato de retornos possuídos está na
[documentação C do Python](https://docs.python.org/3.11/c-api/structures.html#c.PyCFunction).

## PY-03 — erro de conversão também altera damping

**Código:** [linearDamping](../source/source/gameengine/Ketsji/KX_GameObject_Python.cpp#L2529),
[angularDamping](../source/source/gameengine/Ketsji/KX_GameObject_Python.cpp#L2543).

Os setters chamam `PyFloat_AsDouble` e aplicam o resultado sem conferir `PyErr_Occurred()`.
Para uma string inválida, a conversão deixa exceção e devolve -1. O setter passa -1 ao controller
e informa sucesso. O Bullet limita damping ao intervalo permitido; no teste, isso altera o valor
para zero. A camada Python detecta o retorno incompatível com a exceção pendente e gera `SystemError`.

Teste: damping linear inicial aproximadamente 0,4 e angular 0,3. Atribuir `'invalid'` a cada atributo
lança `SystemError`, mas ambos passam a zero. Assim, capturar a exceção no jogo não preserva o estado.

Direção de correção: detectar a falha de conversão e retornar falha antes de chamar o controller.
Decidir separadamente o contrato de limites e valores não finitos.

## PY-04 — raycast degenerado quebra o formato do retorno

**Código:** [rayCast](../source/source/gameengine/Ketsji/KX_GameObject_PyMethods.cpp#L1367),
retornos antecipados nas linhas 1444 e 1451.

Os retornos antecipados para origem e destino coincidentes usam sempre `none_tuple_3()`.
O restante da função escolhe três, quatro ou cinco itens conforme `poly`.

Teste: `obj.rayCast(tuple(obj.worldPosition), poly=p)`, para `p` igual a 0, 1 e 2, retorna tamanhos
`[3, 3, 3]`. Um raio não degenerado sem acerto retorna `[3, 4, 5]`. Um jogo que desempacota quatro
ou cinco resultados pode falhar apenas quando os pontos coincidem. Não é preciso haver colisão.

Direção de correção: centralizar a escolha do retorno vazio, incluindo os retornos antecipados.

## PY-05 — validação ocorre antes do estreitamento numérico

**Código:** [py_vehicle_float](../source/source/gameengine/Ketsji/KX_GameObject_PyMethods.cpp#L1033),
[setVehicleGearRatios](../source/source/gameengine/Ketsji/KX_GameObject_PyMethods.cpp#L1067).

A validação rejeita double não finito, mas aceita double finito fora do intervalo representável
em float. A conversão posterior para float perde essa garantia.

Teste: `setVehicleMaxTorque(1e100)` e `setVehicleGearRatios([1e100])` aceitam os valores;
os getters retornam números não finitos. O gerador restaura parâmetros pequenos após registrar.
O setter de RPM usa o mesmo helper; não foi exercitado separadamente.

Direção de correção: validar representabilidade no tipo armazenado antes de alterar o vetor ou
parâmetro. Não foi testado o comportamento de um carro completo com esses valores.

## PY-06 — chave não textual falha no getter com colchetes

**Código:** [Map_GetItem](../source/source/gameengine/Ketsji/KX_GameObject_Python.cpp#L1182),
[Map_SetItem](../source/source/gameengine/Ketsji/KX_GameObject_Python.cpp#L1263),
[Pyget](../source/source/gameengine/Ketsji/KX_GameObject_PyMethods.cpp#L1761).

O setter limpa o erro da tentativa de interpretar uma chave não textual como Unicode e a aceita
no dicionário Python. O getter tenta a mesma conversão, mas, quando encontra a chave não textual
no dicionário, não limpa o erro: a condição de limpeza está invertida em relação a esse caso.

Teste: `obj[7] = ['stored']` funciona; `obj.get(7)` devolve a lista; `obj[7]` lança `TypeError`.
O dado foi armazenado, mas duas formas de consulta divergem.

Direção de correção: alinhar os caminhos de consulta e o contrato das chaves não textuais, evitando
deixar exceção de uma tentativa de conversão que não determina o resultado final.

## Contratos incorretos do parser, sem crash reproduzido

**PY-07:** [setSoftPoseMatching](../source/source/gameengine/Ketsji/KX_GameObject_PyMethods.cpp#L644)
fornece endereço de `bool` ao formato `p`. Esse formato requer destino C do tipo `int`, conforme
a [especificação do parser](https://docs.python.org/3.11/c-api/arg.html#other-objects).
É uma incompatibilidade de tipo/tamanho; trocar o local para `int` e converter para bool na chamada
ao controller resolve o contrato. A chamada com `True` retornou e completou dez frames em objeto
rígido, sem crash. Isso não valida uma deformação de soft body nem elimina o problema de tipo.

**PY-08:** [setHalfAnimations](../source/source/gameengine/Ketsji/KX_GameObject_PyMethods.cpp#L671)
declara formato `i|i`, mas entrega somente `&halfanimations`. Há um destino a menos que as unidades
do formato. O teste com um argumento e o teste com dois argumentos retornaram normalmente e
completaram dez frames. Não inferir que a ausência de crash torna a chamada correta: corrigir o
formato para a aridade pretendida ou fornecer e usar o segundo destino, após decidir o contrato.

Esses dois testes são observações do build atual. Nenhuma corrupção de memória foi demonstrada
ou medida nesses modos. Não houve instrumentação C++ ou execução com sanitizer.

## Outras observações e limites

- `setActionLayerWeight` e `setActionLayerSpeed` estão registrados com suporte a keywords, mas seus
  corpos leem somente a tupla posicional. Chamadas somente com `layer=...` e valor nomeado falham
  por ausência de argumento posicional. Conferir quais métodos devem aceitar keywords antes de
  uniformizar a tabela; isso não é a incompatibilidade de assinatura dos wrappers já corrigida para Web.
- O wrapper de partículas guarda ponteiro cru do buffer, sem vínculo de validade ao objeto dono.
  O núcleo pode reconstruir/destruir esse buffer. O risco exige teste de proxy retido após remoção
  ou reconstrução; não foi reproduzido nesta rodada. O wrapper de bounds e as listas de bricks
  possuem mecanismos explícitos de validade, consultados como comparação.
- Os aliases antigos `position`, `orientation`, `scaling` e velocidades têm combinações históricas
  de leitura/escrita local/global. Não foram classificados como regressão sem contrato de migração.
- Não foi feita auditoria integral dos helpers de conversão mathutils, da implementação de listas,
  do destruction manager ou de objetos de outra cena. Foram seguidos apenas os caminhos necessários.

## Registro da leitura integral

| Linhas de KX_GameObject_Python.cpp | Compreensão e contrato conferido |
|---|---|
| 1–139 | Dependências, condicionais Python e proteção de controller físico |
| 140–420 | Views mathutils; leitura, escrita integral/por índice e callbacks de matrizes |
| 421–545 | Registro dos métodos, convenções de chamada e criação do acesso `net` |
| 546–729 | Tabelas de destruição, defaults de partículas, leitura por grupo e templates |
| 730–910 | Escrita por tipo, enumerações, cores, limites e notificação de mudanças |
| 911–1040 | Tabela completa dos atributos e aliases |
| 1041–1181 | Substituição de malha/física, remoção adiada e chamadas de destruição |
| 1182–1262 | Leitura por chave e alteração numérica no valor existente; PY-06 |
| 1263–1393 | Atribuição/exclusão, fallback ao dicionário Python e pertencimento |
| 1394–1441 | Slots de mapping/sequence e declaração do tipo derivado |
| 1442–1625 | Nome, pais/grupos, callbacks, filtros de colisão e cena |
| 1626–1852 | Tempo de vida, massa/atrito, destruição, callbacks próprios e fuse |
| 1853–2037 | Limites de velocidade, camadas, visibilidade, câmera e half animations |
| 2038–2165 | Bounds, flags de atividade e conversão dos raios para distância ao quadrado |
| 2166–2397 | Posição, inércia, orientação, escala e decomposição de matrizes |
| 2398–2578 | Velocidades, gravidade, damping e slow parenting; PY-03 |
| 2579–2675 | Estados, malhas, batch, cor, distância de atividade e componentes; PY-01 |
| 2676–2814 | Wrappers de bricks, hierarquia e debug |
| 2815–2871 | LOD, eventos de animação e wrappers dos buffers de partículas; PY-02 |

| Linhas de KX_GameObject_PyMethods.cpp | Compreensão e contrato conferido |
|---|---|
| 1–135 | Dependências, condicionais e proteção de física |
| 136–268 | Conversão de forças, rotações, movimentos, velocidades e damping |
| 269–643 | CCD, parâmetros/coeficientes e iterações de soft body |
| 644–695 | Pose matching, visibilidade, half animations e oclusão; PY-07/08 |
| 696–833 | Velocidade em ponto, força de reação, rigid body, parenting e teste de colisão |
| 834–982 | Impulso, suspensão/retomada, alinhamento, lookAt e identificador físico |
| 983–1090 | Veículo, proxies, parâmetros e conversões numéricas; PY-05 |
| 1091–1228 | Nomes de propriedades, distância, pontos de curva e vetores de direção |
| 1229–1366 | Filtros e callbacks de raycast, rayCastTo e tuplas vazias |
| 1367–1519 | Raycast com opções, origem/destino, máscara, polígono, UV e debug; PY-04 |
| 1520–1589 | Mensagens, validação das camadas e reprodução de ações |
| 1590–1739 | Parada/consulta/ajuste de ações e propriedades de debug |
| 1740–1797 | Disparo de raio climático e `get` com FASTCALL |
| 1798–1857 | Conversão de None, nome ou proxy de GameObject e mensagens de falha |

## Reprodução e evidências

Gerador: [criar_cena_revisao_gameobject_python.py](../tools/debug/cenas/criar_cena_revisao_gameobject_python.py).
Reutiliza câmera, iluminação, materiais e ligações do gerador anterior, em diretório próprio.
Cena e evidências locais em `artifacts/revisao-gameobject-python-20261026/`, ignorado pelo Git.

```powershell
build/bin/AnastacioEngine.exe -b --factory-startup --python tools/debug/cenas/criar_cena_revisao_gameobject_python.py -- artifacts/revisao-gameobject-python-20261026
build/bin/AnastacioEngine.exe -b --factory-startup --python tools/debug/cenas/criar_cena_revisao_gameobject_python.py -- artifacts/revisao-gameobject-python-20261026 inspect
$env:GAMEOBJECT_PYTHON_CASE = 'basic' # outros modos: half_one, half_two, soft_pose
build/bin/AnastacioRuntime.exe --server artifacts/revisao-gameobject-python-20261026/revisao_gameobject_python.range
```

Geração, reabertura/inspeção e quatro modos encerraram com código zero. Cada modo completou dez
frames. A inspeção confirma câmera, materiais, corpo rígido e controladores MODULE com sensores
ligados e funções presentes. O modo `basic` foi repetido após acrescentar o controle de referências
de `None`; as demais chamadas permaneceram iguais. Não houve build novo, alteração de C++ ou
teste visual. Nenhum projeto do usuário foi modificado.

O Python embarcado registra versão 3.11.7. O executável usado tem SHA-256
`64f7e6fffd9f49bf4b791f0dddcf47a561f6ea38e014efd8a670c983d83f8a08`, estável entre os casos.
É outro binário em relação à revisão anterior do núcleo; não confundir as duas séries de evidências.
`review_manifest.json` registra HEAD observado `1c73d08d` e os hashes dos fontes lidos:

- Python.cpp: `a0a881026458104fcb7a5980742b257e2754b5d66cc76d853a9a80b898ef5159`.
- PyMethods.cpp: `bb8fce5c1def76361369017ed52b0d1cb504ad09401f4dcecd48a3f855cf6e99`.

Esses registros identificam fontes e binário, sem provar a correspondência de todas as unidades
compiladas com o HEAD. As conclusões de runtime se restringem ao binário exercitado.
