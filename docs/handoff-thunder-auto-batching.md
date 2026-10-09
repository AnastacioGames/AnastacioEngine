# Handoff: auto-batching do ThunderPlayer confirmado em A/B

Data: 2026-10-08  
Responsável pela próxima etapa: Claude

## Resultado principal

O teste A/B no proprio executavel Thunder de junho confirma que permitir auto-batching explica a maior parte da vantagem do Thunder na cena estatica de 1.600 objetos. Com a mesma cena e o mesmo binario, o controle ligado fez 2.602 FPS; desligado fez 664,5 FPS (3,92x). MDEI estava desligado. A geometria permaneceu igual, com 128.600 primitivas por rodada.

O proximo trabalho e avaliar um prototipo opt-in na Anastacio para geometria estatica ou raramente alterada. O ganho nao deve ser extrapolado para carros e outros objetos dinamicos: alteracoes de matriz separam os usuarios do batch no Thunder e precisam ser tratadas sem quebrar transformacao, fisica ou logica.

## Evidências já encontradas

## Auditoria da infraestrutura de batching da Anastacio

A Anastacio já tem batching estático por `KX_BatchGroup`; não é necessário portar o mecanismo Thunder do zero. `KX_BatchGroup::MergeObjects()` chama `RAS_BatchGroup::MergeMeshUser()`, que agrega os vértices por material em `RAS_BatchDisplayArray`. `RAS_DisplayArrayBucket::GenerateTree()` escolhe o caminho `RunBatchingNode()` quando o display array é do tipo `BATCHING`. A lacuna identificada é a seleção automática de objetos compartilhando mesh/material e elegíveis para batch.

O fluxo já protege parte do ciclo de vida: `RAS_MeshUser::~RAS_MeshUser()` separa os slots antes de destruir o usuário; `KX_GameObject::ReplaceMesh()` remove e recria o usuário; objetos invisíveis/fora de culling não entram na lista de slots ativos, e `RunBatchingNode()` emite os intervalos dos slots ativos. `RAS_MeshUser::SetMatrix()` agora compara a matriz e separa o usuário do batch somente quando ela muda; o hook RAS→KX também atualiza a lista/referência do grupo. Essa peça foi compilada e testada em runtime. Falta confirmação visual humana do objeto movido e teste de reload/troca de cena. Qualquer auto-batching deve manter esse fallback e ainda auditar elegibilidade, falha parcial e semântica de materiais/atributos.

Há restrições adicionais no caminho atual: `RunBatchingNode()` usa o mesh user de referência para atributos de objeto e força `frontFace=true`; transparência exige ordenação por slot; deformers e atributos que variam por objeto podem não manter a semântica individual. `MergeMeshUser()` agrupa por material, mas a inicialização do array também depende do formato/tipo compatível, e a falha pode ocorrer após slots anteriores do mesmo usuário já terem sido mesclados. A proposta deve auditar rollback/falha parcial e definir elegibilidade conservadora antes de automatizar chamadas à API existente.

Direção recomendada: fazer a validação visual do movimento e testar reload/troca de cena; depois auditar falha parcial de merge e definir elegibilidade conservadora antes de propor um protótipo opt-in para objetos estáticos. Não adicionar batching por objeto no pipeline de sombras sem verificar as passadas e os atributos de cada uma. Não tocar no código em andamento de profiler/upload counters sem reconciliar seu estado e build.

## Validação do batch manual na Anastacio (2026-10-08)

Executado no standalone local, sem rebuild, em cena comum de 64 objetos, 16 meshes compartilhados e material comum. `KX_BatchGroup` completou o ciclo de merge/split/destruct; `getRenderStats()` mediu 1 draw call em batch e 64 após desfazer o grupo.

No teste pré-correção, mover um membro após o merge deixava `batchGroup` ativo; a matriz mudava, mas a geometria agregada não era reconstruída. A posição visual ainda precisa de confirmação humana no jogo após a correção.

O teste pré-correção também chamou `endObject()` num membro: `KX_BatchGroup.objects` ainda listava 64 elementos no intervalo observado. A correção posterior remove o membro e atualiza a referência; reload dentro do mesmo processo continua sem teste. Relatório, scripts, cenas e logs em `D:/ThunderPlayer-investigacao/benchmark/diagnostico/anastacio_batch_manual/RESULTADO.md`.

Teste adicional (2026-10-08): `split([obj])` antes de mover removeu o membro do grupo (`batchGroup is None`); depois de um frame, os draws passaram de 1 para 2, mantendo os outros 63 no batch. `destruct()` restaurou 64. O split manual oferece fallback funcional para uma transformação antecipada pelo jogo; não resolve invalidação automática, lista Python após remoção nem reload/troca de cena. A reprodução é `batch_split_move.range`, log `split_move_result.txt`.

Auditoria de remoção (2026-10-08): `KX_Scene::NewRemoveObject()` invalida o proxy e chama `RemoveMeshes()` antes de soltar o objeto da cena. A destruição do `RAS_MeshUser` remove seus slots do batch, mas `KX_BatchGroup` não remove esse objeto de `m_objects`; a lista é não proprietária (`SetReleaseOnDestruct(false)`) e conserva ponteiros crus. Além disso, `RAS_BatchGroup::m_referenceMeshUser` continua apontando para o primeiro usuário destruído: o caminho de render batching passa esse ponteiro a `ActivateMeshUser()`, que pode ler estado do shader/objeto. O teste anterior removeu exatamente `BenchObject0000`, que é a referência inicial, e sobreviveu até o próximo frame/destruct; isso não prova segurança, pois o ponteiro pendente pode resultar em comportamento indefinido. Evitar iterar/dereferenciar `group.objects` após remoção. Antes de automatizar, uma correção autocontida precisa invalidar/substituir referência e retirar o membro da lista durante o ciclo de remoção; depois testar remoção da referência e de membro comum, com renders subsequentes e destruição.

Conclusão prática: o batch manual confirma a redução 64→1 draw call neste caso controlado. A invalidação automática por mudança de matriz e o ciclo seguro de remoção da referência/lista foram implementados e testados; transformação parada mantém 1 draw após vários quadros, mover um membro resulta em 2 draws, e removê-lo resulta em 64 draws após desmontar o grupo. Permanecem pendentes confirmação visual, reload/troca de cena e auditoria de falha parcial de merge/split. A automação continua pendente. Não extrapolar para objetos dinâmicos.

## Correção e validação da remoção no grupo (2026-10-08)

A reprodução pré-correção removeu o primeiro membro (`BenchObject0000`, referência inicial), esperou a remoção atrasada, passou por um frame de render e chamou `destruct()`. Terminou com exit code 0, confirmando que o risco não é um crash determinístico.

Correção aplicada em `KX_BatchGroup::{h,cpp}` e `KX_GameObject::RemoveMeshes()`: antes de destruir o mesh user, o objeto sai da lista do grupo; se era referência, o grupo limpa o ponteiro e escolhe um membro restante, atualizando a referência RAS. O build MSVC do `RangeRuntime` passou após uma falha transitória de link (`LNK1104` na primeira tentativa; segunda tentativa linkou).

Validação pós-build: remover a referência deixou 63 membros, atualizou a referência para `BenchObject0001`, `destruct()` terminou e o player saiu com código 0; remover um membro comum deixou 63, preservou `BenchObject0000` e também completou. Depois de desmontar, ambos reportaram 63 draws. Logs e cenas em `D:/ThunderPlayer-investigacao/benchmark/diagnostico/anastacio_batch_manual/RESULTADO.md`.

A invalidação por `SetMatrix()` foi implementada e validada (2026-10-08): compara a matriz e só separa o usuário quando o grupo existe e os bytes mudaram. O split restaura os slots ainda vivos e notifica `KX_BatchGroup` por hook virtual RAS→KX para atualizar lista/referência. A destruição de `RAS_MeshUser` agora separa antes de limpar os slots. Build/runtime e resultados em `D:/ThunderPlayer-investigacao/benchmark/diagnostico/anastacio_batch_manual/RESULTADO.md`. Posição visual do membro movido ainda pede validação humana. Reload/troca de cena e falha parcial seguem sem validação.

**Nota sobre o ciclo Thunder:** no checkout local, `RAS_MeshUser::SetMatrix()` compara bytes e separa só se mudou; `MergeMeshUser()` associa os mesh users ao grupo, e o reset do cache do bucket no fim do render não restaura os slots por si só. `RAS_BatchGroup::Reset()` só é chamado quando `m_users` chega a zero e apenas apaga arrays/cache; a restauração ocorre no `SplitMeshUser()`. Portanto, a alegação de reconstrução completa a cada quadro não é confirmada por esse checkout; pode corresponder a outra revisão/binário. Não copiar `Reset()` como substituto de split.

## Revisão do Claude sobre `endObject()` em membro do batch (2026-10-08)

O resultado "lista ainda com 64" não é só lista desatualizada: é provável referência solta.

- `KX_BatchGroup` cria `m_objects` com `SetReleaseOnDestruct(false)` (`KX_BatchGroup.cpp:40`): a lista guarda ponteiros sem segurar referência.
- Ao destruir o objeto, `RAS_MeshUser::~RAS_MeshUser()` chama `SplitMeshUser()`, que só desfaz a geometria. `m_objects->RemoveValue()` só roda pelo `split()` do `KX_BatchGroup` (`KX_BatchGroup.cpp:130`), não no `endObject()`.
- Logo `group.objects` pode expor objeto já liberado, e o destrutor do grupo usa `m_objects->GetFront()` como referência (`KX_BatchGroup.cpp:141-147`). Se o primeiro membro tiver sido removido, há risco de uso de memória liberada/crash. "Sem crash" no teste foi sorte, não prova.

Status: passo 1 reproduzido antes da correção (exit 0; risco não determinístico, portanto ausência de crash não provava segurança). Passo 2 implementado e validado após rebuild em remoção da referência e de membro comum. A antiga etapa 3 também foi implementada: `SetMatrix()` separa apenas quando a matriz difere, e os testes de membro movido e grupo estacionário passaram. A posição visual e reload/troca de cena seguem pendentes.

## Revisão do Claude sobre o auto-batching no código Thunder (commit 39bba1e3)

Leitura de `RAS_DisplayArrayBucket.cpp`, `RAS_BatchGroup.cpp`, `RAS_BucketManager.cpp`, `RAS_MaterialBucket.cpp` e `RAS_MeshUser.cpp` do checkout Thunder:

- **Ciclo por quadro ainda não confirmado no checkout.** `TryAutoBatch()` pega grupos via `GetOrCreateFrameBatchGroup(key)`; no fim do render, `RemoveActiveMeshSlots()` e `ResetGlobalBatchGroupCache()` soltam referências de cache. Porém, a leitura do código atual não prova que isso sempre leva `m_users` a zero e reconstrói o grupo seguinte quadro. O reset do cache, por si só, não restaura slots. Assim, a conclusão anterior de que o Thunder recopia vértices agregados a cada quadro e a explicação causal do ganho de 3,9x precisam ser revistas contra o ciclo real de `m_users`/`Reset()` e, se necessário, contra a revisão exata do binário de junho.
- **Gatilho:** só para slots ativos (pós-culling), sem z-sort, deformer ou instancing e com `AllowAutoBatching()`. `s_autoBatchThreshold = 10`, contado em slots sem grupo.
- **Matriz:** `RAS_MeshUser::SetMatrix()` compara com `memcmp` e, se mudou, chama `SplitMeshUser()`; também mantém `m_transformVersion`. A Anastacio implementou e testou o mesmo princípio para o batch manual.
- **`SplitMeshSlot()`** foi endurecido: verifica o slot no mapa original e reajusta `m_batchPartIndex` dos slots seguintes. Bom modelo para a Anastacio.
- **Ponto suspeito no Thunder (não copiar sem entender):** `Reset()` limpa `m_meshUsers` e apaga os buckets agregados **sem** restaurar `slot->m_displayArrayBucket` nem zerar `meshUser->m_batchGroup`, ao contrário de `Destruct()` e do destrutor. Confirmar em quais condições é chamado e se há split anterior; não copiar como substituto de split.
- **`KX_BatchGroup` do Thunder tem o mesmo problema de `m_objects`** (`SetReleaseOnDestruct(false)`, sem remoção no `endObject()`); o auto-batching não passa por ele, só pela camada RAS.

Implicação para a Anastacio: o caminho persistente para estáticos opt-in agora tem invalidação por matriz e remoção cobertas nos testes sintéticos. Ainda é preciso validar visualmente e testar reload/troca de cena, além de auditar visibilidade e falha parcial antes de automatizar. Não adotar a hipótese de batch por quadro no Thunder até fechar a auditoria do ciclo de grupo.

- A cena `D:/ThunderPlayer-investigacao/benchmark/create_scene.py` cria 16 malhas compartilhadas, todas com o mesmo material, e distribui 1.600 objetos entre elas (100 cópias por malha). A comparação não usa 1.600 malhas geométricas únicas.
- O log `D:/ThunderPlayer-investigacao/benchmark/diagnostico/results/thunder_june_n1600_separate_draws_cull0_r1.json` registra `isMDEI: false`. Portanto, o caminho MDEI não foi usado nessa medição.
- No código Thunder do commit `39bba1e3a18870c057dcb48ac38c2219e1f9efb5`, `source/gameengine/Rasterizer/RAS_DisplayArrayBucket.cpp` tenta auto-batching quando o contador ultrapassa o limiar 10 (na sequência simples, por volta do 12º slot ativo), desde que não haja z-sort, deformer, instancing ou bloqueio em `AllowAutoBatching`.
- `TryAutoBatch()` agrupa slots do mesmo `RAS_DisplayArrayBucket`; `RAS_BatchGroup::MergeMeshSlot()` usa a matriz de cada objeto ao mesclar a geometria em `RAS_BatchDisplayArray`.
- `RAS_MeshUser::SetMatrix()` separa o objeto do grupo quando a matriz muda. Isso torna o mecanismo especialmente relevante para geometria parada ou raramente movida; não se deve supor que acelere objetos móveis.
- No caminho equivalente da Anastacio, `RAS_DisplayArrayBucket::ActivateMesh()` só adiciona o slot à lista e `RAS_MeshSlot::RunNode()` ativa/desenha cada objeto. A engine tem `RAS_BatchGroup`, mas não encontramos esse gatilho automático por quantidade de slots.
- O checkout de fonte examinado e posterior ao pacote de junho, portanto nao prova correspondencia de versao. O A/B com o executavel de junho contorna essa lacuna para o efeito do recurso: a propriedade de auto-batching ligada/desligada muda o desempenho de forma repetivel.

## A/B direto no executavel de junho (2026-10-08)

- Player Thunder de junho usado no benchmark, SHA-256 `f9c08ce75d005f9ec76ce099ecc9848fa807b0f1bf55ce78fd2445d0d53a1753`.
- A cena de origem tem 1.600 objetos em 16 meshes compartilhados (100 cada), um material e 128.600 primitivas; 1.602 objetos com camera e Sun. Foram salvas duas copias identicas pela Anastacio, mudando apenas `bge_allow_auto_batch` nos 16 datablocks de mesh.
- Player, resolucao, viewport, MSAA/AF, VSync, culling e duracao foram verificados iguais em todas as rodadas: 1280x720, viewport 1281x721, MSAA 2, AF 2, VSync 0, culling desligado, ticrate 10.000, 2 s aquecimento e 4 s de amostra; `isMDEI=false`.
- Ordem alternada: False/True, depois True/False. Desligado: 661,8 e 667,2 FPS (media 664,5). Ligado: 2.610,0 e 2.595,0 FPS (media 2.602,5), ou 3,92x / aproximadamente +292%. As quatro rodadas emitiram exatamente 128.600 primitivas.
- A cena original sem a propriedade explicita havia medido 2.636 FPS, alinhada ao controle ligado.
- No checkout Thunder, `BL_BlenderDataConversion.cpp` le a propriedade (default `true`) e atribui o valor a `RAS_Mesh::SetAllowAutoBatching`; a unica leitura do estado no renderer bloqueia o gatilho antes de `TryAutoBatch`. O A/B com o player real de junho confirma que esse toggle explica a maior parte da diferenca estatica.
- Limite: nao capturamos individualmente chamadas GL/draws; a consulta de primitivas apenas confirma que a geometria foi mantida. O teste confirma o efeito de desempenho do recurso, nao a contagem exata de draws. Nenhum fonte/build do player foi alterado.
- Relatorio reprodutivel: `D:/ThunderPlayer-investigacao/benchmark/diagnostico/autobatch_ab/RESULTADO-AUTOBATCH-AB.md`; dados brutos, scripts, manifesto e cenas estao na mesma pasta.

## Medições anteriores para contexto

Os resultados iniciais, antes do A/B isolado, foram Anastacio 557 FPS vs Thunder 1.860 FPS com culling ligado e Anastacio 708 vs Thunder 2.628 com culling desligado. No controle de instancing, a Anastacio ficou a frente. O A/B abaixo identifica auto-batching como a causa principal da diferenca estatica sem instancing.

## Tarefa para o Claude

1. Auditar o ciclo de vida de batching existente na Anastacio antes de editar C++. Ler o roadmap, o relatorio vigente e as regras de `AGENTS.md`. Conferir criacao/destruicao de mesh users, buckets/materials, transformacoes, visibility/culling e shadow slots.
2. Propor a menor implementacao opt-in para objetos realmente estaticos ou raramente alterados, com fallback por padrao. Definir como invalidar/reconstruir o batch se mesh, material, visibilidade ou matriz mudarem. Nao presumir que `RAS_BatchGroup` da Anastacio tem o mesmo contrato que o Thunder.
3. Validar primeiro a cena sintetica comum com resolucao, MSAA/AF, culling e primitivas controlados; comparar FPS e contagem de draws se houver meio confiavel. Testar alteracao de transformacao e remocao/reload de objetos para garantir fallback seguro.
4. Manter carros, fisica e logica fora da primeira otimizacao. Depois do prototipo estatico, planejar um teste separado com objetos dinamicos e com o RolimaRacer; nunca reduzir a frequencia de updates para obter o ganho.
5. Para mudancas grandes em C++, seguir a regra do repositorio: implementar e verificar uma peca autocontida por vez, pausando para revisao antes da proxima. Usar o ambiente MSVC/vcvars64 indicado em `AGENTS.md`.

O A/B justifica investigar/prototipar; ainda nao autoriza concluir que o caminho e seguro para todo tipo de objeto. Nao mexer em cores nesta etapa.

## Arquivos para leitura direta
- Relatorio do A/B, com parametros, hashes e interpretacao: `D:/ThunderPlayer-investigacao/benchmark/diagnostico/autobatch_ab/RESULTADO-AUTOBATCH-AB.md`
- Dados reproduziveis (`manifest.json`, scripts, cenas e quatro logs/JSON): `D:/ThunderPlayer-investigacao/benchmark/diagnostico/autobatch_ab/`
- Conversor Thunder que le a propriedade: `D:/ThunderPlayer-investigacao/source/gameengine/Converter/BL_BlenderDataConversion.cpp`
- Regras do repositorio: `AGENTS.md`

- Thunder: `D:/ThunderPlayer-investigacao/source/gameengine/Rasterizer/RAS_DisplayArrayBucket.cpp`
- Thunder: `D:/ThunderPlayer-investigacao/source/gameengine/Rasterizer/RAS_BatchGroup.cpp`
- Thunder: `D:/ThunderPlayer-investigacao/source/gameengine/Rasterizer/RAS_BatchDisplayArray.cpp`
- Thunder: `D:/ThunderPlayer-investigacao/source/gameengine/Rasterizer/RAS_MeshUser.cpp`
- Anastacio: `source/source/gameengine/Rasterizer/RAS_DisplayArrayBucket.cpp`
- Anastacio: `source/source/gameengine/Rasterizer/RAS_MeshSlot.cpp`
- Cena e medições: `D:/ThunderPlayer-investigacao/benchmark/` e `D:/ThunderPlayer-investigacao/benchmark/diagnostico/`

Nenhum código da engine foi alterado por esta investigação. Cores continuam adiadas. A validação visual deve ser feita no jogo real conforme `AGENTS.md`.
