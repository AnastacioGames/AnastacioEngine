# Referências para modernizar o processamento da Anastacio

Pesquisa e comparação estática em 2026-11-04. Escopo principal: CPU, tarefas, física,
animação e dados; inclui preparo de malhas, que pode reduzir trabalho de renderização.
Não foram integradas bibliotecas, alterados fontes da engine ou executados benchmarks.
As prioridades são de investigação, não ganhos demonstrados nem um plano de migração aprovado.

## Conclusão

Há oportunidades para adaptar partes pequenas. Não há evidência suficiente para trocar o
agendador inteiro, substituir Bullet por Jolt ou migrar todos os objetos para ECS.
O caminho mais promissor é reduzir a quantidade de dados percorridos e o trabalho repetido
antes de acrescentar threads. A engine já recebeu otimizações relevantes nessa direção.

| Referência | Decisão para este projeto | Primeiro uso possível |
|---|---|---|
| Jolt | Estudar organização de corpos ativos; adiar troca da física | Medir o custo de filtrar todos os objetos na sincronização Bullet |
| Flecs | Aproveitar organização de dados; adiar migração global para ECS | Dados compactos de animação/culling e atualizações controladas |
| ISPC | Estudar SIMD; integração condicionada a perfil e portabilidade | Testar esferas contra planos em lote sobre o snapshot de sombras existente |
| ozz-animation | Estudar; backend opcional só após prova de compatibilidade | Avaliação de clips pré-calculados em personagens simples |
| enkiTS | Referência de escalonamento; não substituir agora | Comparar balanceamento e esperas com o BLI_task atual |
| oneTBB | Auditoria de dependência antes de atualizar | Inventariar consumidores e pools; medir concorrência total |
| meshoptimizer | Melhor candidato de biblioteca isolada para um protótipo | Otimizar índices de desenho de malhas estáticas opacas no cooking |

## Fontes e versões consultadas

Foram obtidos arquivos de código, não apenas páginas de apresentação. As cópias ficam em
`artifacts/modernization-study/`; `sources.json` registra revisão, arquivos e tamanho de cada download.
As revisões fixam o material consultado; não são recomendações de usar o último commit em produção.

| Projeto | Revisão consultada | Trechos conferidos |
|---|---|---|
| [enkiTS](https://github.com/dougbinks/enkiTS/tree/c947c2c4acfc1af535a28ab0bc9af0081242305c) | `c947c2c4` | `src/TaskScheduler.cpp`: divisão, roubo e espera de tarefas; header e README |
| [oneTBB](https://github.com/uxlfoundation/oneTBB/tree/c3d4627dc433cb132a9386a7a80ce921636c5e41) | `c3d4627d` | `include/oneapi/tbb/task_arena.h`, CMake e README |
| [ozz-animation](https://github.com/guillaumeblanc/ozz-animation/tree/744eb9d99f606eda849acb0b1204f7a3dc20bca1) | `744eb9d9` | `sampling_job.cc`, `local_to_model_job.cc` e contexto de sampling |
| [Jolt Physics](https://github.com/jrouwe/JoltPhysics/tree/0f69a6b8f0bd562f23a29b27a665d2dab1524917) | `0f69a6b8` | listas ativas de `BodyManager.cpp`, grafo de jobs de `PhysicsSystem.cpp`, pool e build |
| [Flecs](https://github.com/SanderMertens/flecs/tree/2b4772598071087bb38ac39ba5c7c14c6c556cf5) | `2b477259` | armazenamento por tabelas/colunas e movimentação em `src/storage/table.c` |
| [ISPC](https://github.com/ispc/ispc/tree/e1d896f50606570ab5b75114136f471f8ebd3b36) | `e1d896f5` | exemplo CPU `examples/cpu/aobench/ao.ispc`, laço em lotes e dados uniformes/variáveis |
| [meshoptimizer](https://github.com/zeux/meshoptimizer/tree/f0a684f11ead064e176775c9b796f82a55910e92) | `f0a684f1` | `vcacheoptimizer.cpp`, `vfetchoptimizer.cpp`, geração de remaps e pipeline documentado |

Também foram conferidos o [guia de migração TBB](https://uxlfoundation.github.io/oneTBB/main/tbb_userguide/Migration_Guide.html),
a [arquitetura do Jolt](https://jrouwe.github.io/JoltPhysics/) e a
[documentação do ozz](https://guillaumeblanc.github.io/ozz-animation/documentation/).
Ollama estava indisponível nesta sessão (conexão recusada); leitura direta como fallback.

## 1. Física: evitar percorrer objetos que nunca precisam ser sincronizados

No Jolt, `BodyManager` mantém listas de corpos ativos com índice reverso. A remoção troca
o último elemento para a posição removida e atualiza seu índice, evitando deslocar toda a lista.
O processamento físico é organizado em jobs com dependências; isso não pode ser copiado isoladamente
para o solver Bullet sem respeitar suas estruturas e ordenação.

Na Anastacio, [SynchronizeActiveMotionStates](../source/source/gameengine/Physics/Bullet/CcdPhysicsEnvironment.cpp#L1154)
percorre `getCollisionObjectArray()` inteiro, faz upcast e só publica a transformação de corpos
rígidos ativos, dinâmicos e com motion state. O nome da função descreve os destinatários,
não uma lista de entrada já restrita aos ativos.

**Hipótese testável:** cenas com muitos objetos estáticos ou adormecidos e poucos ativos podem
gastar CPU nessa filtragem. Primeiro instrumentar quantidade percorrida, elegível e tempo da função.
Antes de criar qualquer registro paralelo, procurar na versão Bullet efetivamente vinculada uma
lista apropriada de corpos não estáticos ou eventos de ativação. Uma lista de não estáticos
ainda inclui adormecidos; não equivale a lista ativa.

Uma lista própria teria de cobrir acordar por colisão/força, dormir, remover, adicionar,
suspend/restore, troca de cena e mudança de tipo. Não basta registrar os corpos que um script moveu.
Não introduzir atualização baseada em listas incompletas nem alterar a transformação publicada:
o caminho atual contém correção específica de substeps e rodas.

**Menor experimento:** comparar cenas com o mesmo número de ativos e quantidades crescentes de
estáticos/adormecidos, e depois uma cena com todos ativos. Medir esta função separada do solver.
O teste existente `tools/create_perf_physics_anim_test.py` mantém corpos acordados; sozinho não
exercita a hipótese. Reaproveitar seu protocolo, acrescentando uma variante mista se autorizado.

**Decisão:** estudar a lógica agora; não migrar para Jolt. A engine usa `btSoftRigidDynamicsWorld`,
solvers diferentes, veículos, constraints, callbacks e alterações em `stepSimulation`.
Um backend novo exigiria provar compatibilidade das APIs e do comportamento dos jogos, além do custo.

## 2. Dados compactos: Flecs como referência, sem reconstruir a engine

Flecs organiza componentes em colunas e movimenta entidades entre tabelas. A lição útil é
percorrer sequências compactas dos dados necessários, evitando buscar cada atributo em vários objetos.
Isso não obriga transformar `KX_GameObject`, Python e SceneGraph em ECS.

A Anastacio **já aplica isso** em [BuildShadowCullCache](../source/source/gameengine/Ketsji/KX_Scene.cpp#L2127):
uma fotografia compacta dos bounds alimenta vários passes. `RAS_DisplayArray::VertexData` também
já separa posições, normais e outros atributos em vetores; não é correto tratar todos os dados como dispersos.

Um candidato restante está em [UpdateAnimations](../source/source/gameengine/Ketsji/KX_Scene.cpp#L2742):
`m_animNeedsUpdateCache.clear()` seguido de `emplace` reconstrói os nós do mapa a cada atualização;
há ainda vetores de tarefas e conjuntos de deformadores pendentes. Os workers fazem busca no mapa.
Uma tabela compacta de trabalho por atualização pode reduzir alocação e buscas, se isso aparecer no perfil.

**Não eliminar os contratos já corrigidos:** deduplicação de objetos antes de despachar workers,
`GetDoAnimations()` avaliado uma vez (alterna o estado de half animations), eventos Python na thread
principal e deformação pendente preservada entre passos de catch-up. Reutilizar memória também precisa
ser seguro contra callbacks que removem/adicionam objetos e contra reentrada.

**Menor experimento:** medir alocações e tempo de preparação das tarefas nas cenas de 100/400 personagens,
separando preparação, avaliação da pose, espera e deformação. Se o mapa for insignificante diante
de `BKE_pose_where_is`, não vale uma nova estrutura só para eliminá-lo.

## 3. SIMD: testar primeiro sobre dados que já estão juntos

O exemplo ISPC processa amostras em lotes (`foreach_tiled`), distinguindo dados comuns e variáveis.
No ozz, `LocalToModelJob` constrói matrizes de quatro joints por vez em estruturas SoA e depois
compõe a hierarquia. Isso ilustra duas aplicações diferentes de SIMD, não um ganho automático.

Na engine, [SphereInsideFrustum](../source/source/gameengine/SceneGraph/SG_Frustum.cpp#L54) faz
testes explícitos dos seis planos por esfera. O snapshot de sombras oferece entrada compacta
para experimentar quatro/oito esferas por lote, sem mudar a lógica de visibilidade final.
O caminho atual ainda pode ser vetorizado pelo compilador; é preciso comparar código gerado e tempos.

**Experimento:** usar o snapshot existente, preservar classificação INSIDE/INTERSECT/OUTSIDE,
o teste de caixa dos casos intermediários, layers e ordem de saída. Medir cópias/transposição e
cauda dos lotes, além do kernel. Conferir resultados contra o escalar em limites de planos,
escalas e coordenadas grandes. Não substituir culling DBVT por varredura SIMD sem medir os dois.

**Decisão:** estudar técnica; não adicionar ISPC ao build antes de demonstrar benefício de um kernel
pequeno. Uma implementação também precisa de fallback para CPUs e plataformas sem o conjunto SIMD escolhido.

## 4. Animação: ozz como possibilidade de backend restrito

O ozz oferece sampling com contexto reutilizável, blending e transformação hierárquica em dados
compactos. `SamplingJob::Context::Step` preserva o estado de sampling e invalida quando muda
a animação. O projeto tem ferramentas de conversão offline; poderia inspirar clips preparados no cooking.

A engine atual usa as estruturas Blender, `animsys_evaluate_action` e `BKE_pose_where_is`, com
constraints, IK, offsets de osso, Action/NLA, eventos e ligações por osso. Produzir matrizes pelo ozz
não reproduz automaticamente essas regras. GPU Skinning já existe; o possível benefício aqui é na
avaliação de pose/clip, não simplesmente transferir deformação de vértices para a GPU outra vez.

**Experimento futuro:** um esqueleto simples, um clip preparado e reprodução equivalente dos mesmos
tempos, comparando transformações e CPU com o caminho atual. Primeiro restringir a esqueletos sem
constraints/IK/NLA e com fallback explícito. Avaliar também tamanho do clip, conversão, loops,
seek para trás e custo de manter o estado. Personagens reais continuam no caminho legado até equivalência.

**Decisão:** bom estudo, migração parcial de complexidade alta. Antes, medir se pose domina o quadro.

## 5. Tarefas: enkiTS e oneTBB não justificam uma troca imediata

enkiTS tem divisão de tarefas, redistribuição de trabalho e esperas com spin/suspensão. oneTBB
oferece arenas e controle de concorrência. São referências para balanceamento, limite de workers
e concorrência entre subsistemas; a existência de APIs novas não prova que trocar será mais rápido.

O projeto é C++17 (`source/CMakeLists.txt`). A receita de dependências registra TBB 2020_U3;
isso não prova a versão dos binários de cada instalação. O culling possui `tbb::parallel_reduce`,
enquanto animação usa `BLI_task`.

**Trabalho já feito em 2026-10-29:** [anim_run_in_chunks](../source/source/gameengine/Ketsji/KX_Scene.cpp#L2724)
agrupa objetos (~quatro blocos por thread) e o skinning evita abrir outro pool internamente.
O changelog registra melhoria medida. Propor essas mesmas mudanças novamente seria redundante.

**Primeiro passo útil:** medir tempo gasto executando, esperando e preparando tarefas, variação de
custo entre personagens e número de workers ativos de cada biblioteca. Só experimentar balanceamento
mais dinâmico se houver desequilíbrio. Não iniciar um terceiro pool competindo com BLI_task e TBB.

Atualizar para oneTBB exige inventário de API/ABI e dependências que compartilham TBB (incluindo
as bibliotecas habilitadas no build), distribuição e validação desktop. Não substituir DLLs isoladamente.
Uma eventual experiência com enkiTS deve começar num harness independente, não no frame do jogo.

**Web/Android:** o runtime atual não usa pthreads/SharedArrayBuffer; o manifesto informa TaskScheduler
serial. Trazer um agendador não habilita multicore automaticamente. Isso exige outra avaliação de build,
hospedagem e interoperabilidade; SIMD e melhoria de dados podem ser estudados separadamente.

## 6. Cooking: meshoptimizer é a integração mais delimitável

O código oferece reordenação de triângulos para reutilização de vértices e remaps para melhorar
acesso aos atributos. Não exige migrar OpenGL para outra API.
A busca nos fontes e ferramentas não encontrou integração `meshopt` nem otimizador de cache de
vértices com os nomes pesquisados; isso não exclui todos os algoritmos equivalentes herdados.

Na engine, `RAS_DisplayArray` separa `m_primitiveIndices` (desenho), `m_triangleIndices`
(consulta de triângulos) e `m_vertexInfos` (origem/deformação). `RAS_Mesh::GetPolygon` usa
os índices lógicos. O `.cooked` já prepara arrays via `BL_ConvertDerivedMeshToArray`.

**Protótipo mais seguro:** reordenar somente os índices de desenho de arrays de triângulos
estáticos opacos, preservando vértices e ordem lógica de polígonos. Primeiro confirmar que não
há consumidores supondo igualdade de ordem entre os dois índices e que IDs de primitivas não
são observáveis nos shaders desse caminho. Excluir transparência, soft body, deformers, linhas
e shaders com dependência de ordem/identidade não coberta.

Depois, se útil, testar vertex-fetch remap. Nesse caso aplicar o mesmo remap a todos os vetores
de atributos e metadados, sem usar diretamente a função de buffer intercalado sobre nosso layout
separado. Atualizar chaves/versão do cooking para não aceitar dados preparados com contrato antigo.
Não começar por quantização nem simplificação que alterem a aparência.

**Métricas:** tempo de preparo/load, RAM/VRAM, invocações de vertex shader quando disponíveis,
GPU em ms e igualdade das consultas de polígonos. Medir uma malha com índices já bons e outra
ruim: otimizar algo já ordenado pode não ajudar. Validar em GPU real e jogo, Windows/Linux/Web.

## Ordem de trabalho sugerida

1. **CPU, experimento pequeno:** medir a filtragem em `SynchronizeActiveMotionStates` numa cena mista;
   aproveitar listas existentes do Bullet se houver caminho compatível, sem substituir o backend.
2. **Biblioteca isolada:** prova de otimização de índices com meshoptimizer em malhas estáticas opacas.
3. **CPU em lotes:** medir preparação da animação e comparar kernel escalar/SIMD do snapshot de sombras.
4. **Somente se os perfis justificarem:** backend restrito de clips ozz ou comparação de agendadores.
5. **Adiar:** substituição global por Jolt/ECS, troca geral de agendador e habilitação de threads no Web.

As cenas existentes, Range Trace e contadores devem ser reaproveitados. Comparar A/B na mesma sessão,
mesma carga, vários pares alternados e tempos em ms; não somar ganhos de benchmarks diferentes.
Nenhuma implementação nem benefício percentual foi demonstrado por esta pesquisa.
