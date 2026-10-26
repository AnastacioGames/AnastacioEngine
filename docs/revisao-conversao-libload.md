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

## Pendente nesta frente

- Comparar o caminho cru com o `.cooked`, incluindo invalidação, cache incompatível e fallback.
- Medir memória ao repetir LibLoad/LibFree muitas vezes e picos de frame no merge.
- Observação: o Python recebe um `KX_LibLoadStatus` que é destruído junto com a biblioteca no
  `LibFree`. Acessar esse status depois da liberação dá exceção de proxy inválido, sem crash. Esse
  é o comportamento esperado, mas não está documentado na API.
