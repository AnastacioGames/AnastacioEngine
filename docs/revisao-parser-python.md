# Revisão do helper de argumentos Python

Data: 2026-10-26. Continuação da [revisão dos bindings de KX_GameObject](revisao-kx-gameobject-python.md).
Escopo: leitura linha por linha do helper `EXP_ParseTupleArgsAndKeywords` e conferência das
declarações, formatos, keywords e destinos dos seus 25 usos em nove arquivos do runtime.
Não é revisão integral desses nove arquivos. A frente 8 permanece com Claude.

## Funcionamento e problema confirmado

Em [EXP_PyObjectPlus.h](../source/source/gameengine/Expressions/EXP_PyObjectPlus.h), o template
recebe a tupla, o dicionário opcional, o formato, a lista de nomes terminada em nulo e os endereços
que receberão as conversões. O assert confere um nome por destino, excluindo o terminador.

Antes da correção, a linha seguinte criava um `_PyArg_Parser` estático. Em C++, esse objeto pertence
à instanciação do template pelos tipos de `Args`; formato e nomes são valores, não participam da
instanciação. Por isso, o primeiro método chamado escolhia formato e nomes para métodos posteriores
com os mesmos tipos de destino. Além disso, `keyword.begin()` apontava para o array temporário do
`initializer_list`, cujo lifetime terminava ao concluir a chamada externa. O cache retinha esse
endereço. Não foi demonstrado um crash decorrente desse segundo problema.

Caso concreto: `setParent` e `replaceMesh` recebem `PyObject **, int *, int *`. Inicializar pelo
primeiro faz `replaceMesh(mesh=...)` reclamar de `parent` ausente; inicializar pelo segundo faz
`setParent(parent=...)` reclamar de `mesh` ausente. Ambos foram reproduzidos em processos separados
no binário anterior. Chamadas posicionais podem esconder o problema porque seus formatos de
conversão coincidem; nomes das keywords e mensagens de erro continuam distintos.

A correção copia os ponteiros dos nomes para um `std::array` local, com espaço para o terminador,
e chama `PyArg_ParseTupleAndKeywords` com o formato da chamada atual. Não guarda referências ao
array temporário. O cast em cada nome adapta a assinatura legada `char **`; o helper não escreve
nas strings. Exceções e status de conversão continuam sendo os devolvidos pelo parser do Python.
Não foi medido o custo da troca do parser privado com cache pelo parser público.

## Conferência dos chamadores

Caminhos relativos a `source/source/gameengine/Ketsji/`. Todos os usos têm um nome por destino e
terminador nulo. Os argumentos opcionais têm valores iniciais nos trechos conferidos. A revisão
dos destinos do parser não demonstra correção de toda a operação que cada método executa.

| Arquivo | Chamadas conferidas | Observação |
|---|---|---|
| `KX_2DFilter.cpp` | `addOffScreen` | Seis destinos `int *`; obrigatório e opcionais conferem |
| `KX_GameObject_PyMethods.cpp` | `setParent`, `alignAxisToVect`, `lookAt`, `getCurvePoints`, `rayCastTo`, `rayCast`, `sendMessage`, `playAction` | Oito usos; `setParent` colide com `replaceMesh`; os dois alinhamentos compartilham tipos e nomes, mas `lookAt` ainda usa o nome `alignAxisToVect` no formato de erro |
| `KX_GameObject_Python.cpp` | `replaceMesh`, `shatter`, `dent`, `reinstancePhysicsMesh` | Quatro usos; colisão confirmada entre `replaceMesh` e `setParent` |
| `KX_InputSystem.cpp` | `changeKeyMap`, `changeSensitivity`, `changeJoystickIndex` | Quantidade/tipos conferem; não se revisou a manipulação de JSON/arquivos nesta rodada |
| `KX_Mesh.cpp` | `constructBvh` | `PyObject **` e `float *` para os dois opcionais |
| `KX_MeshBuilder.cpp` | `addVertex`, construtor, `addSlot` | Quantidade e destinos conferem |
| `KX_PyConstraintBinding.cpp` | `createConstraint` | Dois `unsigned long long *`, tipo inteiro, seis floats e flag inteira |
| `KX_PythonInit.cpp` | `LibLoad` | Pendências de buffer e signedness descritas abaixo |
| `KX_Scene.cpp` | `addObject`, `convertObject`, `explode` | Quantidades e destinos conferem; `p` usa `int *` |

Os dois setters de camada corrigidos anteriormente já usam listas locais próprias e não estão
nesses 25 usos. A correção comum não altera seus contratos.

## Pendências encontradas no limite desta revisão

- `LibLoad`: o formato `I` de `load_scripts` recebe `int *`; conferir o contrato e os limites de
  entrada antes de padronizar signedness. Não foi demonstrada falha prática dessa diferença.
- `LibLoad`: depois de adquirir um `Py_buffer` com `y*`, o retorno antecipado por erro em
  `ConvertPythonToScene` não passa por `PyBuffer_Release`. Os caminhos normais com buffer fazem
  a liberação. É um caminho estático identificado; reproduzir retenção do buffer antes de corrigir.
- `lookAt`: o sufixo do formato permanece `alignAxisToVect`, então erros do parser podem mencionar
  o nome errado. Não muda a conversão dos argumentos, mas merece ajuste pontual.

## Validação

Gerador: [criar_cena_revisao_parser_python.py](../tools/debug/cenas/criar_cena_revisao_parser_python.py).
Ele reaproveita a cena isolada anterior, substitui o módulo de teste e salva outra cena. A inspeção
reabre o arquivo e registra câmera, materiais, sensores, modo MODULE e funções dos controladores.

As duas ordens são selecionadas por `PARSER_REVIEW_ORDER=parent_first` ou `mesh_first`, cada uma
em novo processo do player com `--server`. O teste alterna oito vezes as duas APIs com keywords,
confere a identidade do pai, testa chamadas mistas e rejeição de duplicatas, nomes indevidos,
tipos incorretos e aridade errada. Inclui smoke de keywords de curva, alinhamentos, raycast e BVH.

As 41 verificações de cada ordem passaram no player atualizado: 82 no total. Os sete cenários
anteriores do núcleo/bindings também completaram sem exceções e com saída zero. CTest: 15/15,
46,41 segundos. O hash do runtime foi conferido antes/depois das nove execuções e permaneceu igual;
está em `after_manifest.json`. Não há validação visual nem alegação de ganho de FPS nesta rodada.

O primeiro build de editor/player compilou os usos do header, mas parou na criação de
`ge_ketsji.lib` com LNK1104 para `KX_ShadowRenderer.cpp.obj`. Outro `ninja RangeEngine RangeRuntime`
foi observado na mesma pasta, e o objeto ausente reapareceu. Após encerrar essa concorrência,
`ninja RangeRuntime` passou, informando que não havia trabalho pendente. O player atualizado
recebeu os testes acima. O editor continuou aberto nessa primeira etapa e não foi encerrado pelo
agente; não se tentou clean/rebuild às cegas.

Após o usuário fechar o editor, `ninja RangeEngine RangeRuntime` concluiu com saída zero e atualizou
o executável. Uma nova linkedição concorrente impediu a primeira tentativa de abertura com WinError
32; após esse outro build terminar, o editor atualizado abriu e reabriu a cena de teste em background
com saída zero. A inspeção confirmou nove objetos, câmera e três controladores MODULE com sensores
e funções válidas. O runtime manteve o mesmo hash das nove execuções já aprovadas. Os dois produtos
estão compilados e validados; hashes e resultado do smoke do editor foram acrescentados ao manifesto.

Evidências em `artifacts/revisao-parser-python-20261026/`: resultados anteriores/posteriores,
inspeção, inventário mecânico dos chamadores, logs de build, CTest e manifesto do runtime.
