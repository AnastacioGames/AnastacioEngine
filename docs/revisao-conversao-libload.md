# Revisão da frente 5: conversão, cooking e LibLoad

Data: 2026-10-26. Frente 5 do [levantamento](levantamento-modulos-criticos.md). Primeira rodada,
concentrada no ciclo de vida das bibliotecas: `LinkBlendFile` → conversão assíncrona →
`ProcessScheduledLibraries`/`StepMerge` → `LibFree` (`FreeBlendFile`/`FreeBlendFileData`) → `RemoveScene`.
Arquivo principal: [BL_Converter.cpp](../source/source/gameengine/Converter/BL_Converter.cpp).

Regressão: [criar_cena_revisao_libload.py](../tools/debug/cenas/criar_cena_revisao_libload.py), quatro casos rodados
com `AnastacioRuntime.exe --server`. A biblioteca tem 150 cubos com material próprio, mais uma lâmpada.

## Achados corrigidos

| ID | Defeito | Reprodução antes | Correção | Depois |
|---|---|---|---|---|
| LIB-01 | `LibFree` chamado duas vezes no mesmo frame entrava duas vezes na fila. Na segunda vez, `FreeBlendFileData` recebia a `Main` já liberada | caso `duplo`: o processo saiu com 0xC0000374 (heap corrompido) | `FreeBlendFile(path)` recusa o pedido quando a `Main` já está na fila e devolve `False` | `free1=True`, `free2=False`, sem biblioteca restante |
| LIB-02 | `LibFree` durante um `LibLoad(asynchronous=True)` era descartado. A fila era limpa mesmo quando a liberação recusava, então o Python recebia `True` e a biblioteca continuava carregada | caso `livre_async`: `free=True`, mas a biblioteca seguia no `LibList` | O pedido fica na fila e é refeito a cada frame até o carregamento terminar. Saiu o `CM_Error`, que passaria a repetir a cada frame | biblioteca liberada no frame 123, ao fim do carregamento |
| LIB-03 | Remover a cena que é destino de um carregamento assíncrono deixava `m_merging` e `m_mergequeue` (ou uma tarefa ainda em execução) apontando para uma `KX_Scene` já liberada | caso `remove_cena`: a cena B foi encerrada no meio do merge e o player travou | `RemoveScene` chama `FinishMergesInto(scene)`: espera as tarefas, conclui na hora os merges para essa cena e só então libera a cena. O dado carregado sai junto com ela | sobra só a cena `Main` e o jogo segue normalmente |

Caso `controle` (carregamento assíncrono sem liberação nem remoção): termina no frame 123, igual a antes.

## Conferido sem mudança

- `FreeBlendFileData` desfaz os registros da biblioteca nos objetos, malhas, materiais, ações e
  `objectInfos` de cada `SceneSlot`. Quando sai uma lâmpada, os materiais são recompilados.
- `StepReloads` só roda quando não há merge em andamento. Se a cena sai durante um reload de luz,
  `RemoveScene` finaliza o status.
- `FinalizeAsyncLoads` no `StopEngine` termina os carregamentos antes de destruir as cenas.

## Memória em LibLoad/LibFree repetidos

Caso `ciclos`: 150 ciclos de LibLoad síncrono e LibFree da biblioteca de 150 objetos, medindo a
memória privada do processo a cada ciclo.

| Ciclo | 5 | 50 | 100 | 150 |
|---|---|---|---|---|
| MB | 484,2 | 472,8 | 473,8 | 476,0 |

A memória termina abaixo do valor após o aquecimento. Entre os ciclos 50 e 150 sobe cerca de
3 MB, sem tendência linear clara, o que é compatível com fragmentação do alocador. Não há
vazamento a corrigir.

## Cache `.cooked`

- O conteúdo é endereçado por hash. Hulls usam o conjunto de vértices; as malhas usam o hash dos
  loops, as flags dos slots de material, as camadas e as tangentes. Por isso uma malha alterada só
  deixa de achar a entrada, sem precisar de invalidação explícita.
- `BL_CookedArrays::Parse` confere limites de loops, primitivas e triângulos. Dado inconsistente
  volta ao caminho cru, e com BVH rejeitado acontece o mesmo.
- Cabeçalho desconhecido ou de outro tamanho de `btScalar` é ignorado com aviso. Arquivo truncado
  para de ler no primeiro registro incompleto e descarta esse registro.
- Suspeita sem reprodução: `ReadRecords` faz `resize(count2)` com o tamanho lido do arquivo, sem
  comparar com o tamanho real. Com um `.cooked` forjado (registro de malha de 4 GB), o jogo rodou
  normalmente em `--server`, então o defeito não foi demonstrado. Se for corrigir, basta limitar
  `count2` ao que ainda resta no arquivo.

## Pendente nesta frente

- Medir os picos de frame do merge assíncrono com janela, porque em `--server` os shaders não
  representam o custo real.
- Observação: o Python recebe um `KX_LibLoadStatus` que é destruído junto com a biblioteca no
  `LibFree`. Acessar esse status depois da liberação dá exceção de proxy inválido, sem crash. Esse
  é o comportamento esperado, mas não está documentado na API.
