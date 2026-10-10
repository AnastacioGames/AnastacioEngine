# RA3 — cache de ordenação com validação visual

Estado vigente nesta retomada: RA3 concluido, validado no jogo pelo usuario e integrado
em `12741810`. A/B de tempo/FPS inconclusivo; cobertura adicional continua opcionalmente
ampliavel. As notas abaixo preservam os limites dos testes anteriores ao aceite final.

## Objetivo e limites

Evitar ordenar e reescrever índices de polígonos transparentes quando a ordem já gravada
no buffer continua válida. Preservar a imagem e o algoritmo de ordenação atuais.

O caminho está em `RAS_MeshSlot::RunNode`, `RAS_DisplayArray::SortPolygons` e
`RAS_StorageVbo::GetIndexMap`/`FlushIndexMap`. O IBO pertence ao display array e pode ser
compartilhado entre objetos: guardar validade apenas por objeto seria incorreto.
`SortPolygons` usa a direção Z de view × object; a translação não participa da comparação.

Confirmar que os materiais do teste ativam `IsZSort()`. Usar explicitamente
`material.game_settings.alpha_blend = 'ALPHA_SORT'` no caso principal. A cena não deve
apenas parecer transparente: precisa exercitar o trecho auditado. Materiais Opaque,
Alpha Blend, Alpha Clip e Add serão controles, com as flags efetivas conferidas no código.

Não ampliar esta peça para corrigir limitações existentes de transparência, interseções,
billboards ou deformação em shader. Se o comportamento anterior já apresentar defeito,
registrá-lo separadamente; ele não vira o resultado esperado de uma nova correção visual.

## Etapas e pontos de revisão

1. **Preparar a referência visual, antes de alterar C++.** Criar gerador reutilizável em
   `tools/debug/cenas/`, aproveitando estrutura dos geradores de câmera e transparência
   existentes. Gerar `.range`, inspeções e logs em diretório temporário exclusivo.
   Reabrir pelo editor e inspecionar câmera, materiais, malhas compartilhadas e lógica.
   Executar no player atual e entregar a cena com controles e roteiro visual ao usuário.
   Aguardar a avaliação da referência antes da implementação.
2. **Implementar uma peça pequena.** Associar a validade à ordem atual do IBO compartilhado,
   com comparação exata da direção de profundidade. Invalidar após mudança de posições,
   topologia, substituição/recriação do storage ou sobrescrita dos índices. Não validar após
   falha de map; conferir também o resultado do unmap antes de considerar a gravação aceita.
   Inicialização e cópia de arrays precisam começar com estado GPU inválido. Manter a
   fórmula, o comparador e o tratamento de empates existentes. Não usar epsilon.
3. **Validar código e execução.** Fazer teste diferencial de índices contra a implementação
   anterior, compilar editor/player no ambiente exigido pelo `AGENTS.md` e executar a mesma
   cena. Corrigir falhas antes de entregar para avaliação visual. Pausar para revisão desta
   peça antes de ampliar o cache ou iniciar outra infraestrutura.
4. **Comparar visualmente no player real.** Repetir o roteiro abaixo com a mesma cena,
   resolução, configuração e pontos de câmera. Guardar uma cópia isolada do player anterior
   com suas dependências para facilitar a comparação. Não depender de captura headless ou
   PrintWindow. O usuário pode registrar imagens/vídeo da janela real para comparação.
5. **Medir e encerrar.** Só após equivalência funcional e aprovação visual, medir repouso
   e movimento. Registrar resultado, limites e pendências no changelog, roadmap e relatório.
   RA3 só fica concluído quando todos os critérios de saída passarem.

## Cena e roteiro visual

Usar fundo/chão opacos com referências contrastantes, Sun inclinado e câmera mirando
explicitamente o conjunto. Materiais transparentes com alpha intermediário e cores
distintas, sem refração na cena principal, para tornar a ordem fácil de observar.
Cada caso deve ter identificação na tela. Oferecer pausa, reinício e seleção de caso;
movimentos determinísticos por tempo, com posições de referência reproduzíveis.

| Caso | Ação | O que comparar antes/depois |
|---|---|---|
| Malha única com várias faces em profundidades distintas | Permanecer parado; orbitar câmera; pausar novamente | Mesmas camadas visíveis, cores compostas e resposta à mudança de direção |
| Objetos sobrepostos com a mesma malha/material | Alternar objetos de rotações diferentes no mesmo enquadramento | Cada objeto conserva sua ordem correta; nenhuma ordem emprestada do draw anterior |
| Movimento de objeto | Transladar, girar e escalar; incluir escala não uniforme e negativa | Transparência continua respondendo como na referência, inclusive após parar |
| Troca de câmera | Alternar duas câmeras com direções opostas, voltar e pausar | Ordem atualizada em cada vista, sem usar estado da câmera anterior |
| Mudança de geometria | Alterar vértices via API existente; restaurar; substituir malha com topologia diferente | Nova geometria ordenada, sem índices/centros antigos e sem faces desaparecidas |
| Empates de profundidade | Faces distintas com centros na mesma profundidade; repetir movimento e retorno | Mesmo tratamento da versão anterior, sem tremulação nova |
| Materiais de controle | Observar Opaque, Alpha Blend, Alpha Clip e Add ao lado do caso principal | Nenhuma mudança atribuível ao cache fora do caminho zsort |
| Passes adicionais que efetivamente usem zsort | Exercitar reflexão e sombras quando as flags/configuração permitirem | Vista principal e passes preservados; confirmar execução do caminho antes de concluir |

Sombras com override ignoram o trecho. Sombras alpha sem override podem passar por ele,
mas isso não prova que um material específico tenha zsort ativo. Conferir flags e roteamento.
Billboard/halo e deformação GPU ficam como testes de regressão quando realmente ativarem
zsort; o cache deve reproduzir as entradas do algoritmo atual, sem presumir geometria GPU.

Após a cena controlada, conferir no jogo real do usuário uma área com transparência,
incluindo movimento e repouso. Usar cópia ou instrumentação apenas em memória;
não salvar alterações no projeto original.

## Evidência automática e medição

- Diferencial: comparar todos os índices finais, não apenas imagem ou contagem. Cobrir
  slots compartilhados alternados, direções iguais/diferentes, retorno a uma direção antiga,
  empates, malha deformada, topologia, cópia, recriação do IBO e falha/retry de map/unmap.
- Cena: inspeção bpy em arquivo; execução automatizada com encerramento e marcador final,
  exit code zero e logs sem novos erros de shader/Python. Execução visual permanece aberta
  até saída manual. Não chamar scripts temporários de `inspect.py`.
- Trabalho evitado: contar no teste isolado ordenações e gravações. Em repouso com uma
  direção válida, devem cessar após a primeira gravação. Objetos compartilhando IBO com
  direções diferentes podem continuar alternando ordens: custo zero não é exigido aí.
- Performance: começar pelos instrumentos de [profiling](engine-profiling.md) existentes.
  Os contadores gerais de atualização não medem zsort diretamente. Se necessário, propor
  um marcador específico separado; não criar infraestrutura ampla só para este teste.
- Benchmark: três rodadas por versão, 3 s de aquecimento e pelo menos 10 s medidos,
  em repouso e movimento, mantendo resolução, vsync e limites de lógica iguais.
  Comparar FPS/tempo de frame com profiler desligado; usar rodada separada para profiling.
  Nenhum ganho de FPS será deduzido apenas da redução de chamadas.

## Critérios de saída

Índices equivalentes no diferencial; editor/player compilados; runtime e inspeção passaram;
referência e versão corrigida conferidas visualmente pelo usuário; nenhuma regressão nos
casos que exercitam zsort nem nos controles. Medição deve comprovar redução do trabalho
redundante e informar o ganho de tempo observado, inclusive se for inconclusivo.

Sem avaliação visual, registrar **implementado/testado automaticamente, visual pendente**;
não marcar RA3 como concluído. Falha visual bloqueia a promoção da otimização até diagnóstico.
Resultados são limitados às configurações testadas; outras plataformas permanecem explícitas
como pendências quando não executadas.

## Referência preparada em 2026-10-09

Gerador: `tools/debug/cenas/criar_cena_ra3_transparencia.py`. Cena e evidências em
`%TEMP%/anastacio-ra3-reference/`: `referencia.range`, `scene-check.json` e `runtime.txt`.
Inspeção confirmou materiais ALPHA_SORT, três objetos compartilhando malha e controlador
MODULE. Player terminou com exit code 0 e marcador END após 240 frames, exercitando
movimento, duas câmeras, deformação/restauração e troca/restauração de topologia.
Log final sem erros Python/shader; fonte Arial empacotada para os rótulos.
Editor reportou memória não liberada no encerramento da geração; não houve crash.

Controles: Espaço alterna movimento/pausa; C troca câmera; D alterna deformação;
T troca topologia do objeto esquerdo; R restaura estado inicial. Escape encerra.
À esquerda estão camadas, ao centro objetos sobrepostos com malha compartilhada,
à direita controles Opaque/Alpha/Clip/Add. Deformação atua na malha compartilhada.

Pendente: usuário conferir a referência na janela real. Nenhuma alteração C++ ou
comparação visual antes/depois realizada. Esta cena inicial não cobre ainda todos
os casos do plano (empates dedicados e passes adicionais, por exemplo).

## Primeira peça implementada em 2026-10-09

Usuário confirmou a referência adequada para comparação. Cache no display-array storage:
direção exata da última gravação aceita pelo IBO compartilhado. Recriação/redimensionamento,
mapeamento externo, posições e topologia invalidam o estado. Falhas de map/unmap não
validam o cache. O sorter e seu comparador permanecem iguais.

`tools/debug/test_ra3_sort_reference.py` extrai os corpos reais do sorter e do cache para
um teste MSVC isolado, com adaptadores mínimos e buffer/map/unmap simulados. Passaram
9.600 ordenações de referência e mais de 2.000 comparações de índices, incluindo direções
alternadas, geometria, topologia de mesmo tamanho, sobrescrita e falha/retry. Mil chamadas
extras na mesma direção não acrescentaram mapeamentos após o primeiro. Não testa OpenGL
real, a implementação mathfu nem prova FPS ou imagem.

Editor/player compilados. Primeira ligação do editor falhou LNK1104 (arquivo indisponível);
repetição depois de confirmar ausência de processo passou. Runtime novo: 240 frames,
exit 0, marcador END e sem erros Python/shader. Evidências `build.txt`, `build-retry.txt`
e `runtime-after.txt` na pasta temporária. A tentativa de guardar o player anterior ocorreu
após a ligação do novo player: essa cópia não é uma referência anterior válida. Comparação
visual usará a referência já vista pelo usuário; A/B binário requer reconstrução isolada.

Usuário confirmou em 2026-10-09 o visual da cena corrigida após esclarecer o comportamento
do controle T (troca/restauração de topologia). Aceite limitado à cena controlada; não
comprova os casos adicionais ainda ausentes nem o comportamento no jogo real.
Pendente: jogo real e benchmark de tempo/FPS.

## Benchmark isolado em 2026-10-09

Cena aprovada adaptada por `tools/debug/cenas/preparar_benchmark_ra3.py`:
1280x720, vsync OFF, Use Frame Rate desligado, limites de logica/render em
10.000 Hz e maximo de um passo de logica. Medicao por callbacks post_draw,
3 s de aquecimento e pelo menos 10 s medidos; movimento por tempo real.
Tres rodadas por variante e modo, alternando off/on, com profiler desligado.
Pilotos limitados a 60/1000 Hz foram descartados.

Reconstrucao isolada em `%TEMP%/anastacio-ra3-benchmark/`: recompilacao de
RAS_MeshSlot e recriacao da biblioteca/player para ambas as variantes, com
VSLANG=1033/vcvars64. Off restaura apenas a chamada antiga map/sort/unmap;
on usa o cache. Objetos restantes e headers atuais sao iguais. Isso mede o
efeito de ativar o cache no build atual; nao representa um build historico
completo anterior. Build compartilhado e fontes C++ ficaram intactos.
Comandos, fontes, hashes, logs e summary.json permanecem na pasta temporaria.

| Modo | Sem cache: ms/frame (3 rodadas) | Com cache: ms/frame (3 rodadas) | Mediana sem/com |
|---|---|---|---|
| Repouso | 0,5830 / 0,6498 / 0,8507 | 0,6413 / 0,6746 / 0,6497 | 0,6498 / 0,6497 |
| Movimento | 0,6225 / 0,6203 / 0,6378 | 0,6336 / 0,6368 / 0,6117 | 0,6225 / 0,6336 |

Todas as 12 execucoes terminaram com exit 0 e marcador END, sem erros
Python/shader. Inspecao da copia confirmou ALPHA_SORT, malha compartilhada
e controlador. Maquina: Ryzen 9 5900HX, GPUs Radeon integrada/RX 6800M;
a GPU efetivamente escolhida pelo driver nao foi identificada.

Resultado inconclusivo para ganho/regressao: faixas se sobrepoem, especialmente
em repouso. A cena tem poucas faces e objetos que alternam direcoes no mesmo
IBO, onde o cache pode continuar ordenando. Nao extrapolar para malhas densas
nem para o jogo real. O diferencial isolado foi reexecutado e passou; a prova
de mil chamadas repetidas sem novos maps permanece limitada ao adaptador.

Rodadas separadas de profiling em repouso terminaram com exit 0, sem erros.
Depois de 3 s, mediana das janelas AVG de draw.mesh_slot: 0,15 ms sem cache
(faixa 0,08-0,24) e 0,12 ms com cache (0,08-0,21). Marcador amostrado engloba
RunNode inteiro, nao apenas zsort; uma rodada por variante e faixas sobrepostas
nao isolam o custo do sorter nem estabelecem ganho de FPS. Sem marcador novo.

Usuario autorizou abrir RolimaRacer na Pista_1. Copia temporaria preparada
com essa cena ativa e recursos em caminhos absolutos; original preservado.
Inspecao encontrou o material MadeiraCaixa em ALPHA_SORT, mas isso sozinho
nao prova sua visibilidade ou passagem por zsort na corrida. Avaliacao visual
do jogo real e casos adicionais do plano continuam pendentes; RA3 nao encerrado.

## RolimaRacer/Pista_1 em 2026-10-09

O arquivo original continha por engano a instrumentacao `audit_work.py`, com
27 controladores/sensores adicionados em cameras e limite padrao de 20 s que
chamava `Range.logic.endGame()`. Uma copia de seguranca foi criada no projeto;
removidos somente `audit_work.py`, `audit_py` e `audit_always`. A cena inicial
foi restaurada a `0_SCN_System`, pois a limpeza em background havia deixado
`Speed_FX` ativa e a janela ficava cinza.

O player atual voltou a percorrer Sistema, Loading e Pista_1, carregando
contagem, HUD e minimapa. Para evitar os caminhos quebrados de uma copia fora
do projeto, a prova usou uma copia temporaria no diretorio de RolimaRacer que
solicita Pista_1 ao BrainCore; os recursos relativos e componentes reais foram
mantidos. Usuario confirmou que a pista permaneceu rodando. I foi enviado apos
a carga para acionar o piloto automatico, mas o log nao prova a imagem nem a
entrada processada pelo componente.

Aceite limitado: abertura real estavel apos remover a auditoria. Permanecem
pendentes a avaliacao visual explicita de fumaça/transparencia em repouso e
movimento, e os empates/passes adicionais definidos acima. RA3 nao esta fechado.

Revisao final: `UpdateSize` deixa a invalidacao para
`RAS_StorageVbo::UpdateSize`, que chama `InvalidatePolygonCenters` e por sua
vez invalida a ordem. Editor e player recompilados depois da revisao; diferencial
isolado passou novamente e `referencia.range` terminou 240 frames com exit 0 e
marcador END, sem erros Python/shader.
