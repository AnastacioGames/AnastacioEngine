# Changelog — AnastacioEngine

Registro histórico do que foi feito, alterado ou adicionado no fork. Entradas antigas preservam o contexto
da época e podem conter hipóteses corrigidas em entradas posteriores. Para o estado vigente, consulte
`docs/roadmap.md` e `relatorio-melhorias-anastacioengine.md`.

**Como está organizado.** Este arquivo guarda as entradas mais recentes (novas entradas vão no topo, logo abaixo desta tabela). O histórico mais antigo está em `docs/changelog/`, dividido em arquivos de até ~70 KB para caber na leitura de uma IA. Quando este arquivo passar de ~60 KB, mova as entradas mais antigas para um novo arquivo em `docs/changelog/` e acrescente uma linha na tabela abaixo.

## 2026-10-09 - GL5/GL6/GL9/GL10: auditoria GameLogic integrada

- Integrado o lote validado em worktree isolada: cache seguro de literais no Property Actuator (GL5), uma só leitura de texto no Property Sensor Changed (GL6), retorno cedo do TimeEventManager sem Timer (GL9) e menos lookups/varreduras invariantes nos sensores de teclado/mouse (GL10).
- Cena de 300 objetos, 1.800 atuadores e 300 sensores de cada tipo: seis rodadas alternadas mantiveram valores finais idênticos e reduziram a média de 1,82 para 1,26 ms/frame (-31%). GL6 e GL9 foram falsos positivos em grande parte; o relatório preserva limites e ramos não alterados em [auditoria-claude-resultados.md](auditoria-claude-resultados.md).

## 2026-10-09 - RA3: benchmark A/B isolado

- Reconstruidos dois players isolados com os mesmos objetos/headers atuais, variando apenas a chamada zsort em RAS_MeshSlot (map/sort/unmap antigo versus cache). Ambiente VSLANG/vcvars; builds e dependencias fora de build/bin. Isso isola ativacao do cache, sem alegar baseline historico completo. Fontes C++ e trabalho do Claude preservados.
- Copia da cena aprovada com `tools/debug/cenas/preparar_benchmark_ra3.py`: post_draw conta frames, movimento por tempo real, 1280x720, vsync OFF, limites logica/render 10000 Hz, 3 s warmup + 10 s medidos. Tres rodadas por versao/modo, alternadas; 12 runtimes exit 0/END e sem erros Python/shader. Pilotos limitados descartados; diferencial anterior reexecutado com PASS.
- Medianas sem/com cache: repouso 0,6498/0,6497 ms; movimento 0,6225/0,6336 ms. Faixas sobrepostas e variacao alta: ganho/regressao inconclusivos. Profiling separado em repouso passou, mas draw.mesh_slot inclui mais que zsort e nao isola seu custo. Resultados completos, limites e evidencias no [plano RA3](ra3-transparencia-plan.md) e `%TEMP%/anastacio-ra3-benchmark/`.
- Usuario autorizou RolimaRacer/Pista_1; preparada e aberta copia temporaria com caminhos absolutos, sem salvar sobre o original. Visual do jogo real e casos adicionais continuam pendentes. Sem commit.

## 2026-10-09 - RA3: execucao no RolimaRacer/Pista_1

- O jogo original encerrava apos cerca de 20 s porque continha acidentalmente `audit_work.py`: 27 controladores `audit_py` e sensores `audit_always` chamavam `Range.logic.endGame()`. Copia de seguranca criada ao lado do jogo; a instrumentacao foi removida e a cena inicial restaurada para `0_SCN_System` (a limpeza inicial tinha salvo `Speed_FX` como ativa, produzindo tela cinza).
- O player atual carregou o fluxo `0_SCN_System` -> Loading -> `Pista_1`, com `Contagem_3_2_1`, HUD e minimapa. Uma copia de teste no diretorio do projeto solicitou Pista_1 ao BrainCore, preservando caminhos relativos dos componentes; o usuario confirmou que ficou rodando. A tecla I foi enviada apos a carga para testar o piloto automatico, sem inferir visual por log.
- Isto confirma abertura estavel da pista no jogo real e remove o fechamento artificial; nao mede FPS nem substitui inspeção visual detalhada de fumaça/transparencia e dos casos adicionais do plano.
- Revisao final simplificou `UpdateSize`: o VBO ja invalida os centros de poligono, e esta invalidacao propaga a ordem do IBO. Editor/player foram recompilados depois disso; o diferencial MSVC passou novamente (9.600 ordenacoes, 2.005+ comparacoes e retry map/unmap) e a cena automatica concluiu 240 frames, exit 0, sem erros Python/shader.

## 2026-10-09 - RA3: aceite visual da cena controlada

- Usuario confirmou a cena corrigida como correta apos esclarecer T: alterna o objeto esquerdo entre 9 e 5 camadas e restaura a topologia original. Aceite visual registrado no plano, roadmap e relatorio vigente.
- Diferencial/build/runtime ja passaram. Validacao no jogo real e benchmark continuam pendentes; casos adicionais ausentes da cena nao foram considerados aprovados. Nenhum commit nesta etapa.

## 2026-10-09 - RA3: primeira peca do cache de zsort

- Usuario confirmou a cena de referencia adequada para comparacao. Gerador `tools/debug/cenas/criar_cena_ra3_transparencia.py`: ALPHA_SORT, objetos compartilhando malha, duas cameras, movimento/escala negativa, deformacao e substituicao de topologia; controles Opaque/Alpha/Clip/Add. Inspecao bpy e runtime com marcador END passaram.
- Cache no RAS_DisplayArrayStorage representa a ultima direcao efetivamente escrita no IBO compartilhado. Comparacao exata; sorter/comparador preservados. Posicoes, topologia, recriacao/redimensionamento e mapeamento invalidam. FlushIndexMap retorna sucesso do unmap; falhas nao validam o cache.
- Teste isolado MSVC extrai sorter/cache reais com adaptadores minimos e map/unmap simulados: 9600 ordenacoes de referencia e mais de 2000 comparacoes passaram; 1000 chamadas repetidas nao acrescentaram maps apos a primeira. Nao comprova OpenGL real, mathfu, visual ou FPS.
- Editor/player compilados com VSLANG/vcvars. Primeira ligacao do editor falhou LNK1104; ausencia de processo conferida e repeticao passou. Player corrigido terminou 240 frames, exit 0, sem erros Python/shader. Referencia/detalhes em [plano RA3](ra3-transparencia-plan.md).
- Comparacao visual da versao corrigida, jogo real e benchmark pendentes. Sem commit. A copia tentada do player anterior ocorreu depois da ligacao: nao e baseline binario valido.

## 2026-10-09 - RA3: planejamento com checagem visual obrigatoria

- Pedido do usuario incorporado no [plano RA3](ra3-transparencia-plan.md): referencia visual antes de mudar C++, cache em peca pequena, diferencial/build/runtime, comparacao visual antes/depois no player real e medicao separada. Sem avaliacao visual, item permanece pendente.
- Roteiro cobre faces sobrepostas, IBO compartilhado entre objetos com rotacoes diferentes, movimento/escala negativa, troca de camera, geometria/topologia e empates. Materiais de controle e passes adicionais exigem conferir flags/caminho efetivo; ALPHA_SORT e configuracao explicita do caso principal. Map/unmap e recriacao do storage fazem parte dos testes de validade.
- Planejamento e documentacao apenas; nenhuma cena gerada, mudanca C++ ou benchmark nesta etapa. Proxima acao: preparar e executar a cena de referencia para avaliacao do usuario.

## 2026-10-09 - RA3: diagnostico da ordenacao e do IBO compartilhado

- Retomada apos RA2/GP8. `RAS_MeshSlot::RunNode` mapeia o IBO antes de `SortPolygons`; este conserva centros de poligonos, mas cria vector de PolygonSort e executa std::sort por chamada. `FlushIndexMap` desmapeia apos escrever todos os indices. Nao existe teste de repouso nesse caminho.
- O storage pertence ao display array, compartilhado entre slots; cache por objeto permitiria usar a ordem deixada por outro objeto. A chave deve representar a ultima ordem efetivamente escrita no buffer compartilhado. O algoritmo usa apenas a direcao Z da transformacao view x object para comparar profundidades: translacao nao altera a ordem. Posicoes/topologia e recriacao do IBO exigem invalidacao independente; falha de map nao pode validar o cache.
- Refinada a alegacao sobre sombras: RunNode ignora zsort com shader override; BucketManager desliga override para sombras alpha nao-variance, permitindo esse caminho. Nao ocorre em todas as sombras.
- Plano registrado no roadmap para uma primeira peca autocontida, preservando algoritmo e empates, com diferencial para slots/cameras alternados, geometria, recriacao e falha de map, seguido de build/runtime. Apenas leitura e documentacao nesta etapa; sem mudanca C++, benchmark ou ganho alegado. Skill do Claude modificada anteriormente e artefatos nao relacionados preservados.

## 2026-10-09 - Consolidacao KX14 e RA2/GP8 em commit

- Consolidado o cache de Text-Res/estado espacial dos speakers, reutilizacao do produto view x object, Damage seletivo/cache do contador e nome AnastacioRuntime nos textos do dialogo/log Windows. Builds editor/player e testes registrados nas entradas abaixo; player final apos ajuste de nome encerrou com exit code 0 e mesmas seis amostras dent/reset. Inicio do log atualizado confirmado.
- Validacao documental e diff sem erros. Benchmark de FPS, visual e audio no jogo real permanecem pendentes; matrizes inversas continuam por draw. Artefatos e mudancas nao relacionados permanecem fora do commit.

## 2026-10-09 - RA2/GP8: Damage seletivo e contador por programa

- `GPU_material_use_damage` consulta pass e localizacao do uniform no shader linkado; `BL_BlenderShader::UpdateObjectMatrix` so faz dynamic_cast do deformer se o contador Damage esta ativo. Nao conserva ponteiro de deformer nem depende de tipo de material no editor; reload consulta o novo GPUMaterial.
- `GPU_material_bind_damage` usa o helper existente `GPU_shader_uniform_int_cached` para count. Unico escritor desse uniform confirmado por busca; cache pertence ao GPUShader e preserva materiais que compartilham programa, transicoes hit -> zero e programa recriado. Arrays de hits/strength continuam enviados por chamada com count positivo, inclusive quando hits mudam mantendo a contagem.
- Teste C++ extraiu o binder antes/depois e o helper cached real, com estado/GL simulados. 6000 draws diferenciais com dois materiais compartilhando programa: count/arrays finais iguais, arrays com mesma quantidade de envios; contador 6000 -> 3001, sendo 3000 draws em repouso -> 1. Programa novo, sem uniform e sem shader passaram. Sem medida de FPS.
- Editor/player compilados com vcvars64/VSLANG=1033; header GPU recompilou dependencias. Primeira linkagem do player falhou LNK1104; destino ausente/gravavel e processo ausente conferidos, segunda linkagem passou. Sem crash de layout de header.
- Skill `anastacio-cena-de-teste` aplicada: gerador existente `tools/create_damage_marks_test.py` adaptado em `%TEMP%/anastacio-ra2-damage/make.py`, com objeto sem deformer compartilhando material Damage e controlador de dent/reset. Cena gerada e reaberta/inspecionada: material compartilhado, no Damage, Dent, camera e pulso/modulo confirmados. Runtime final exit code 0; tres dent e tres reset aceitos. Logs sem erro de shader; avaliacao visual no jogo real pendente.
- Erro inicial do teste: script temporario chamado `inspect.py` ocultou modulo padrao importado pelo NumPy; falha `No module named bpy` seguida de crash em AUD_initPython. Renomeado para `verify_scene.py`, runtime passou. Nenhum clean rebuild necessario: causa identificada no log como colisao de modulo do teste, nao layout C++.
- Usuario apontou nome RangeRuntime no dialogo. Textos fixos em `GamePlayer/GPG_ghost.cpp` (titulo/mensagem de crash e inicio do log Windows) atualizados para AnastacioRuntime; arquivo de log e variavel RANGE_NO_CRASH_DIALOG preservados. Executavel ja era AnastacioRuntime.exe; este era um texto legado.
- Evidencias em `%TEMP%/anastacio-ra2-damage/`: `before.c`, `after.c`, `damage_test.cpp`/`.exe`, `make.py`, `verify_scene.py`, `test.range`, `inspection.json`, `result.json`, `runtime-valid.txt`. Alteracoes KX14 e primeira peca RA2 preservadas, sem commit. Matrizes inversas continuam por draw; cache adicional depende de justificativa por medicao.

## 2026-10-09 - RA2: produto view x object compartilhado dentro do draw

- Retomada apos KX14; alteracoes locais de texto/speaker preservadas e sem commit. `BL_BlenderShader::UpdateObjectMatrix` delega as matrizes a `GPU_material_bind_uniforms`. Confirmadas ate tres multiplicacoes identicas de view x object quando os builtins local-to-view, normal e inversa coexistem.
- Produto calculado uma vez por chamada, somente com viewmat e algum desses builtins. Inversas, transposta e uploads permanecem no caminho original; sem estado novo, header alterado ou cache entre draws. Objeto, camera, passes de sombra/reflexao e matriz explicita de halo/billboard continuam entradas atuais de cada chamada.
- Teste C temporario extraiu as funcoes anterior/corrigida, com estruturas/API GPU simuladas e helpers matematicos controlados (nao os helpers Blender). 6400 casos diferenciais: todas as 16 combinacoes de builtins de matriz, view nula, info de particulas nula, translacao, shear, escala negativa e matriz zero. Uniforms capturados identicos byte a byte; inversas com contagens iguais; produtos 8400 -> 4900. Primeira compilacao do harness falhou por faltar `true` no stub; definicao adicionada e compilacao/execucao passaram.
- Editor/player compilados com vcvars64/VSLANG=1033. Cena existente e previamente inspecionada do KX11 executada pelo player atualizado com exit code 0: 22 amostras iguais a `after-final.json`, incluindo movimento de camera/luz e escala. Teste funcional sem comparacao visual; nao mede FPS nem a reducao das multiplicacoes dentro desse runtime.
- Damage (RA2/GP8): `GPU_material_bind_damage` retorna antes do upload se damagecountloc == -1; portanto nao ha envio de count=0 para materiais sem o uniform. O dynamic_cast em BL_BlenderShader ocorre antes desse retorno e continua por objeto; materiais com Damage ainda enviam count por draw. Cache de RA1 usa helpers cached explicitos, nao cobre genericamente esses uploads. Esta parte fica para a proxima peca, assim como eventual cache de inversas que exigiria validar todas as entradas e o estado de programas compartilhados.
- Evidencias em `%TEMP%/anastacio-ra2/`: `before.c`, `after.c`, `matrix_test.c`/`.exe`, `runtime-result.json` e logs de runtime. Ganho de tempo/FPS e visual no jogo real pendentes. RA2 parcial, sem commit.

## 2026-10-09 - KX14: cache de Text-Res e estado espacial dos speakers

- KX11 e registros KX12 commitados em `c3a1daf6` (`perf: cache seletivo de transformacao e cone das luzes KX11`). KX13 conferido: travessia direta dos filhos ja corrigida; nenhum novo trabalho nesse item.
- `KX_FontObject::UpdateTextFromProperty` guardava `m_resolution` (float) em `m_res` (string), invocando a atribuicao de um caractere e frustrando o cache. Agora le `Text-Res` uma vez e guarda o texto, inclusive entradas invalidas. So tenta `std::stof` quando o texto muda; falhas preservam a resolucao. Uma propriedade constante deixa de reaplicar a resolucao a cada frame, conforme o cache textual previsto; alteracoes de `Text` continuam pelo caminho existente.
- Teste C++ extraiu os metodos anterior/corrigido com propriedades simuladas e a conversao real `std::stof`. Em 6000 updates diferenciais (numericos, invalido, overflow, mudanca de texto e remocao da propriedade), resolucao/texto coincidiram. Conversoes 6000 -> 6; excecoes 2000 -> 2. Cena reaberta/inspecionada e player com exit code 0: 16 amostras confirmaram repouso, mudancas, preservacao da resolucao em entradas invalidas e remocao/recriacao da propriedade.
- `KX_Speaker` conserva os 10 floats de posicao/velocidade/orientacao relativos a camera, com validade independente. O helper compara bytes e chama apenas setters cujos valores mudaram; so conserva dados aceitos pela API, permitindo nova tentativa apos falha. `play()` e `ProcessReplica()` invalidam os caches, inclusive se o endereco de um handle for reutilizado. Culling/3D math, consulta de status, efeitos e outros parametros de audio continuam no caminho existente.
- Confirmado no backend OpenAL que cada setter espacial trava o device e chama `alSourcefv`; backend Software apenas atribui dados. Teste do helper extraido, com setters simulados: 3000 chamadas em repouso -> 3, mais transicoes, falha/retry e invalidacao de handle passaram. Cena com WAV mono de 4 s empacotado, speakers 3D/2D e template inativo: movimento de speaker/camera, rotacao, pausa/retomada, stop/play e replica. Reaberta/inspecionada; runtime exit code 0, 12 amostras com tempos de reproducao esperados, replica ativa e log sem erros. Tentativas iniciais do gerador usavam objeto ativo para `addObject`; corrigido para template em camada inativa, conforme a API. Estes dados nao substituem avaliacao auditiva do posicionamento/Doppler.
- Particulas: `RAS_ParticleBuffer::SetModelMatrix` apenas copia 16 floats na CPU; o upload do model ocorre depois no draw. Nenhuma mudanca nessa parte de KX14. Editor/player compilados com vcvars64/VSLANG=1033 apos mudanca do header do speaker; dependencias afetadas recompiladas e runtime sem crash.
- Evidencias em `%TEMP%/anastacio-kx14/`: `font_cache_test.cpp`/`.exe`, `make.py`, `test.range`, `verify_scene.py`, `inspection.json`, `result.json`; `audio_cache_test.cpp`/`.exe`, `make_audio.py`, `audio.range`, `verify_audio.py`, `audio-inspection.json`, `audio-result-valid.json` e `audio-runtime-valid.txt`. Reducao de trabalho comprovada nos testes isolados; ganho de FPS/tempo e visual/audio no jogo real nao medidos. KX14 sem commit; usuario pediu encerrar esta conversa apos o item atual. Proxima retomada: RA2, pois RA1 ja consta corrigido.

## 2026-10-09 - KX11: cache seletivo de transformacao e cone implementado

- `GPULamp`, struct privada em `gpu_material.c`, guarda a matriz de entrada, escala e validade. `GPU_lamp_update` normaliza/copia/inverte somente quando a entrada muda (comparacao exata dos 16 floats); `GPU_lamp_update_spot` conserva o cosseno enquanto o angulo permanece igual. Blend continua calculado a cada chamada. Inicializacao pelo Blender invalida ambos os caches; nao houve mudanca em header ou DNA.
- Layer/hide continuam atribuídos por chamada, assim como escalas Hemi/Spot e dimensoes Area (inclusive alteracoes de `Lamp` sem movimento). `gpu_lamp_calc_winmat` continua chamado quando ha shadow buffer, preservando o comportamento das matrizes compartilhadas com Point/CSM. Cores/atenuacao e Static Split nao foram alterados.
- Teste C temporario extraiu as duas funcoes do HEAD anterior e da fonte corrigida. Em 5000 atualizacoes diferenciais (5 tipos), comparou transformacoes normalizadas/inversas, posicao/direcao, escalas, Area, layer/hide, cone e projecao apos sobrescrita simulada. Incluiu translacao, rotacao, escala, angulo/blend, dimensoes/shape Area, invalidacao e matriz zero. Todas passaram; normalizacoes/inversas 5000 -> 30 e cossenos do cone 5000 -> 15. Helpers matematicos e projecao sao substitutos controlados neste teste, nao validacao da GPU ou medida de FPS.
- Cena controlada com material Principled, 2 meshes e 5 luzes (Point Auto Shadow/culling, Spot com sombra, Sun com CSM, Area e Hemi), criada e reaberta/inspecionada pelo editor. Executou por 120 ticks alterando posicao/escala, cone/blend, visibilidade, camera e cor/energia/distancia. Player anterior foi recompilado a partir do C original mantendo as outras correcoes; ambas as execucoes terminaram com exit code 0 e 22 amostras identicas de estado/contadores de sombras. Fonte corrigida restaurada byte a byte e produtos finais recompilados.
- Evidencias em `%TEMP%/anastacio-kx11/`: `make.py`, `test.range`, `verify_scene.py`, `inspection.json`, `cache_test.c`/`.exe`, `before.json`, `after.json` e logs de runtime. Editor/player compilados com vcvars64/VSLANG=1033; primeira linkagem do editor falhou com LNK1104, destino verificado ausente/gravavel e segunda tentativa passou. Visual real e benchmark de FPS permanecem pendentes; nenhum ganho percentual de FPS alegado. Sem commit.

## 2026-10-09 - KX12: UpdateBuckets verificado sem nova correcao

- `KX_Scene::RenderBuckets` chama `KX_GameObject::UpdateBuckets` para os objetos do passe. Matriz e front face so sao atualizados com `DIRTY_RENDER`; `KX_Mesh::UpdateBitmapText` retorna cedo quando o texto permanece igual. Os setters de camada, pass index e cor apenas atribuem dados CPU.
- `RAS_MeshUser::ActivateMeshSlots` preenche a lista de slots ativos para renderizar. `RAS_BucketManager` esvazia essa lista depois do passe por `RemoveActiveMeshSlots`; pular a ativacao para objetos estaticos retiraria esses objetos de passes posteriores. Nao foi identificado trabalho caro redundante que justifique novo cache neste item.
- KX12 classificado como verificado por leitura, sem alteracao C++, build ou benchmark novo. Nenhum ganho de performance atribuido a esta auditoria; KX11/RA9 permanece pendente. Documentacao validada com `tools/check_docs.py`.

## 2026-10-09 - KX11/RA9: atualizacao de luz e limites do cache

- `KX_ShadowRenderer` chama `UpdateDistanceCulling` e `KX_LightObject::Update` para cada luz antes das sombras. `RAS_OpenGLLight::Update` chama os quatro setters GPU; `GPU_lamp_update` normaliza a matriz, inverte e recalcula a projecao quando ha shadow buffer; `GPU_lamp_update_spot` recalcula o cosseno. Cores e atenuacao apenas escrevem dados CPU neste caminho; nao sao chamadas GL/uniforms por objeto.
- Um retorno antecipado baseado apenas em transformacao/parametros da luz nao basta: `GPU_lamp_shadow_point_face_bind` escreve `winmat` para as faces Point; `GPU_lamp_shadow_buffer_bind_matrices` escreve view/win para CSM. Area tambem consulta dimensoes em `Lamp`, e hide depende do culling da camera. Uma futura correcao deve separar o cache dos dados da luz da restauracao das matrizes usadas pelas sombras e preservar essas dependencias.
- A parte de RA9 sobre `dynamicCasterSet` e restrita a Static Split: o set e declarado por luz, mas so recebe casters quando `useStaticSplit` esta ativo. Nao e a reconstrucao do mapa Auto Shadow corrigida no KX10.
- Diagnostico por leitura de codigo, sem alteracao C++ ou alegacao de ganho. Medicao isolada e implementacao de cache seletivo continuam pendentes no roadmap. Documentacao conferida com `tools/check_docs.py`.

## 2026-10-09 - KX10: benchmark antes/depois com ganho medido

- Cena sintetica estatica: 1600 meshes com material, sem colisao, 16 Point com Auto Shadow e alcance 50, camera mirando a cena, Sun, 640x360, vsync OFF e logica a 1000 Hz (limite que ainda introduz espera). Gerador reutilizavel `tools/debug/cenas/criar_cena_benchmark_kx10.py`, derivado dos testes existentes. Cena reaberta e inspecionada: contagens, materiais, sombras/Auto, camera, modulo/funcao e pulso confirmados.
- Comparacao isolou o KX10: compilado temporariamente o CPP anterior, mantendo KX6/KX7; restaurado o CPP corrigido e recompilado `RangeRuntime` com vcvars64/VSLANG=1033. Tres rodadas por versao, cada uma com 3 s de aquecimento e 10 s medidos, profiler desligado: antes 704,3 / 701,9 / 717,9 FPS; depois 899,3 / 903,5 / 908,6 FPS. Medianas 704,3 -> 903,5 FPS (+28,3%); periodo medio correspondente 1,420 -> 1,107 ms. Todas as rodadas encerraram com exit code 0 e mantiveram shadowPasses/lightsShadowUpdated em zero no intervalo medido.
- Rodada separada por versao com profiler existente: media de `render.shadows` apos aquecimento 0,613 -> 0,194 ms (-68,3%, aproximadamente 0,419 ms poupados). 58/75 janelas de 120 frames. FPS acima vem das rodadas sem profiler. Rodadas agrupadas por versao, sem alternancia; resultado limitado a esta carga estatica sintetica, nao e previsao para o jogo real ou sombras continuamente invalidadas.
- Evidencias em `%TEMP%/anastacio-kx10-bench/`: `bench.range`, `inspection.json`, `before-1..3.json`, `after-1..3.json`, logs `before-profile.txt`/`after-profile.txt` e `summary.json`. Fonte corrigida conferida byte a byte com backup; player final compilado com KX10. Spot, deformadores, layers/parametros e visual real continuam pendentes. Sem commit.

## 2026-10-09 - KX10: mapa de casters somente na invalidacao de Auto Shadow

- `AutoShadowStillValid` consulta o mapa persistente da luz e conta casters no snapshot atual; so cria/substitui um `unordered_map` quando a sombra invalida. Preservados filtros de layer/alcance, tolerancia de transformacao, parametros da luz e invalidacao por deformadores. O snapshot de `BuildShadowCullCache` ja e compartilhado entre luzes/passadas no escopo de sombra do frame; varredura por frame e por luz permanece para detectar mudancas. Sem cache entre frames novo.
- `RangeRuntime` compilou com vcvars64/VSLANG=1033. Cena `%TEMP%/anastacio-kx10/test.range` com Point Auto Update, gerador `make.py` e inspecao `verify_scene.py`; `inspection.json` confirmou camera, luz, Auto Update, modulo/funcao e material. Player encerrou com exit code 0 antes e depois do patch. `before.json` e `after.json` tem 18 amostras identicas: 0 passadas em repouso e 6/1 luz apos movimento, saida/entrada do alcance, ocultar/mostrar, escala, movimento da luz e remocao do caster; volta a 0 apos cada evento.
- Removida a construcao/destruicao do mapa no caminho valido por inspecao de codigo; ganho de tempo/FPS nao medido. Spot, deformadores, layers, parametros e visual no jogo real ainda pendentes. KX10 parcial: custo da varredura permanece. KX6/KX7 e demais alteracoes locais preservadas, sem commit.

## 2026-10-09 - KX9: revisao da correcao existente e teste de frustum

- `KX_Camera::UpdateView` ja corrigido no commit `6d8c640d`: compara os 16 elementos de modelview, marca mudanca ao recalcular projecao e so entao liga `frustumDirty`. `ExtractFrustum` reconstrui sob demanda e limpa a flag. Atualizada a linha desatualizada da auditoria; nenhuma alteracao C++ nesta rodada. Culling de objetos continua por frame.
- Cena `%TEMP%/anastacio-kx9/test.range`, gerador `make.py`, inspecao `verify_scene.py` e resultados `inspection.json`/`result.json`. Camera, modulo, funcao e pulso conferidos; player encerrou automaticamente com exit code 0. Consultas `pointInsideFrustum` estaveis em repouso: origem e ponto lateral dentro; mover camera +1000 em X colocou ambos fora, retornar colocou ambos dentro. Lente 16 para 120 colocou ponto lateral fora, mantendo origem dentro; restaurar 16 recuperou classificacao original.
- Teste confirma resposta funcional de modelview/projecao; nao mede numero de reconstrucoes nem ganho em ms/FPS. Stereo, Camera FX e visual no jogo real pendentes. KX6/KX7 e demais alteracoes locais preservadas, sem commit.

## 2026-10-09 - KX8: Auto World Sun sem invalidacao continua reproduzida

- Auditoria de `UpdateAutoWorldSun`: `SG_Node::SetLocalPosition` e `SetLocalOrientation` ja ignoram valores iguais; a recaptura do World compara assinatura (incluindo direcao do sol) antes de `ForceUpdate`. Nenhuma mudanca C++ neste item.
- Cena temporaria `%TEMP%/anastacio-kx8/test.range`, gerador `make.py` e inspecao `verify_scene.py`: Auto World Sun ligado, camera e controlador MODULE conferidos em `inspection.json`. Player encerrou com exit code 0 e escreveu `result.json`. Frames 160/175 e 330/345: `sceneNodeUpdates`, `transformSyncs` e `meshMatrixChanges` zerados. Ao mover camera x=4 para x=8, sol acompanhou +4 em X, mantendo orientacao.
- A primeira execucao falhou porque o script temporario `inspect.py` ocultou o modulo padrao usado por numpy; renomeado para `verify_scene.py`, execucao passou. Nao foi erro de build/engine.
- Evidencia limitada a transformacoes em cena controlada; sombras com cascatas, sol com parent, alteracao de hora/direcao e visual no jogo real pendentes. Sem alegacao de ganho em ms/FPS. KX6/KX7 preservados, sem commit.

## 2026-10-09 - KX7: slow parent dorme no ponto fixo

- `KX_SlowParentRelation` compara exatamente posicao, escala e orientacao antes/depois da interpolacao. Resultado igual deixa de reagendar e de propagar `parentUpdated`. Primeira chamada preserva o reagendamento inicial; mudancas no pai/filho reativam pelo scene graph. Formula mantida, sem epsilon.
- `RangeRuntime` compilou. Cena temporaria `%TEMP%/anastacio-kx7/test.range` inspecionada via bpy e executada ate encerramento automatico: filho convergiu para x=4, retomou ao mover pai e convergiu para x=8. Frames 160/175 e 330/345: `sceneNodeUpdates`, `transformSyncs` e `meshMatrixChanges` em 0; frame 182: x=7.9375 com atualizacoes ativas. Evidencias `inspection.json` e `result.json` na mesma pasta.
- Translacao/repouso/retomada validados; rotacao/escala, visual no jogo real e ganho em ms/FPS pendentes. KX6 preservado, sem commit.

## 2026-10-09 - KX6: anexos de osso dormem com a armature parada

- `BL_ArmatureObject::UpdateTimestep()` agora agenda os filhos com relacao de osso quando uma acao, constraint actuator ou `armature.update()` avanca a pose. A relacao deixou de se reagendar incondicionalmente; armas e acessorios de uma armature ociosa nao percorrem mais sua subarvore a cada frame.
- A relacao ainda marca os descendentes quando executa, preservando anexos ligados ao objeto preso ao osso. `RangeRuntime` recompilou; falta apenas a conferencia visual no jogo real de um objeto preso a osso durante uma animacao.

## 2026-10-09 - KX13: animacao percorre filhos sem alocar vetor temporario

- Os passes de pose e de deformer de `KX_Scene` agora visitam diretamente os filhos de `SG_Node`, preservando a travessia por links sem objeto e encerrando assim que encontra um filho que exige pose. Armatures com muitos filhos deixam de alocar e preencher dois vetores por atualizacao.
- A investigacao tambem descartou a parte de strings do suspeito: `KX_AnimationEventManager::EventCall` armazena `const char*`; a conversao para a string Python so ocorre quando ha evento e callback a chamar.
- `RangeRuntime` recompilou com os warnings preexistentes de ordem de inicializacao e variavel nao usada em `KX_Scene.cpp`.

## 2026-10-09 - KX5: probe nao atualiza animacao seis vezes durante a captura

- A simulacao ja atualiza poses e deformers antes do pipeline de render. `KX_TextureRendererManager` deixou de chamar `UpdateAnimations()` dentro do loop de faces da probe; assim `setHalfAnimations()` continua alternando uma vez por passo, e uma probe cubica nao reavalia a mesma animacao ate seis vezes.
- A selecao de LOD por face foi mantida. A distancia correta para uma reflexao e a distancia da probe, portanto substituir a malha quando ela difere da camera principal e necessario para a imagem capturada.
- `RangeRuntime` recompilou. A confirmacao visual de uma probe atualizada com um objeto em `setHalfAnimations()` permanece para teste no jogo real.

## 2026-10-09 - CV5/CV6: shape keys paradas nao deformam a malha outra vez

- `BL_Action` pede nova deformacao apenas quando a avaliacao e os blends alteram algum `KeyBlock::curval`. `BL_ShapeDeformer` conserva os coeficientes usados anteriormente; curvas em hold deixam de chamar `BKE_key_evaluate_relative`, reskin e upload da malha a cada frame.
- `LoadShapeDrivers()` so habilita `BKE_animsys_evaluate_animdata` e `ForceUpdate()` se a key copiada tiver curvas de driver. Uma armature pai sem driver nao aciona esse caminho.
- `RangeRuntime` recompilou. A cena temporaria criada para medir no player confirmou a estrutura (acao, controlador, camera 16 mm, Sun e materiais contrastantes), mas o player desta sessao encerrou antes de executar o primeiro controlador e nao gerou marcador; a medicao em runtime permanece pendente.

## 2026-10-09 - CV7/CV8: objetos sem acao ativa deixam a atualizacao por frame

- `GetActionManager()` nao registra mais o objeto apenas porque um getter Python consultou nome, frame ou estado da acao. `PlayAction()` so adiciona a lista depois que iniciou uma layer com sucesso.
- Ao fim de `KX_Scene::UpdateAnimations`, depois de disparar eventos, objetos comuns sem nenhuma layer ativa saem de `m_animatedlist`; por isso deixam de gerar task e de entrar em `m_animNeedsUpdateCache` nos frames seguintes. Armatures permanecem na lista, pois constraints e deformers podem precisar de pose mesmo sem uma acao KX.
- Regressao controlada no `AnastacioRuntime.exe`: uma acao one-shot chegou a `x=4.000`, terminou, foi iniciada de novo e chegou a `x=3.556` antes de terminar (`PASS=True`). A mudanca elimina o trabalho ocioso, mas esta rodada nao mediu tempo de CPU numa cena grande.

## 2026-10-09 - PH3: deformer de soft body só invalida a malha quando ela mudou

- `KX_SoftBodyDeformer::Apply`: compara exatamente cada posição e normal de saída antes de escrever o array; `NotifyUpdate` recebe somente os atributos que mudaram. AABB deixa de ser percorrido, reinicializado e invalidado quando nenhuma posição mudou. Não há limiar nem estado artificial de sono: uma deformação real continua atualizando e subindo ao VBO.
- Medição temporária com grade triangular de 6 561 nós, câmera 16 mm, materiais contrastantes e Sun: com gravidade zerada o solver ainda altera nós e, corretamente, manteve `updateNotifies=1` e `boundsPushes=1` por frame (física ~7,5 ms). Após `suspendDynamics()`, os frames estáveis tiveram ambos os contadores em 0; a física ficou ~5,1 ms, mostrando que o custo do solver é independente do envio da malha.
- Correção complementar do defeito visual: pose matching não é criado para mesh planar, pois Bullet inverte uma matriz singular e a malha cresce sem limite. `soft_body_test.py` passou 16/16 no runtime recompilado.

## 2026-10-09 - Cache de uniforms de luz e sombra no GPUShader (GP1/GP2/RA1 corrigidos)

- `GPU_shader_uniform_vector_cached` / `GPU_shader_uniform_int_cached` (`gpu_shader.c`): guardam o último
  valor enviado por location dentro do `GPUShader` (os programas são compartilhados entre materiais pelo
  shader_cache) e pulam o `glUniform` quando o valor não mudou.
- `GPU_material_bind_shadow_lamps` e `GPU_material_bind_scene_lights` usam essas funções para persmat, bias,
  point, enabled, sampler das sombras e as 11 uniforms das luzes de cena. Os binds de textura de sombra
  continuam a cada draw, porque outros draws reusam as unidades.
- Medido na cena `tools/debug/cenas/criar_cena_luzes_sombra.py` (3 spots com sombra, 164 draws por frame com os cubos visíveis):
  `lightUniforms` de ~902 para ~334 por frame. RolimaRacer não muda (já era 0). O script da cena criava o plano no
  cursor 3D (acima dos cubos, que ficavam escondidos); agora o plano vai para a origem e os cubos são vermelhos.

## 2026-10-09 - Contador de uniforms de luz (GP1/GP2/RA1 medidos)

- Novo contador `lightUniforms` em `bge.logic.getRenderStats()` (`CM_WORK_LIGHT_UNIFORMS`): chamadas GL de
  `GPU_material_bind_shadow_lamps` e `GPU_material_bind_scene_lights` por frame. Também entra no detector
  `tools/debug/auditar_trabalho_repetido.py`.
- O detector aceita `-` no lugar da cópia: põe o medidor só na memória do editor aberto (sem `-b`) e não salva.
  Assim os imports `scripts.*` dos componentes continuam resolvendo, o que não acontecia na cópia salva fora da
  pasta do jogo.
- Medição: 0 no RolimaRacer em corrida (~400 draws), que não tem lâmpada com sombra em buffer; no COMPAT as luzes vão
  por `gl_LightSource`. Na cena nova `tools/debug/cenas/criar_cena_luzes_sombra.py` (41 malhas com Principled, 3 spots
  com sombra): ~880 GL por frame, ~22 por draw, repetidas com a cena parada.
- O detector também registra `lightBinds`. Foi ele que mostrou que a primeira versão da cena não tinha shader: sem
  `use_shading_nodes` o Principled cai nos nós antigos, o material fica sem programa e nada é desenhado.

## 2026-10-08 - Varredura de trabalho repetido e os 8 bugs de correção encontrados

- [auditoria-suspeitos.md](auditoria-suspeitos.md): varredura por leitura de código de Converter, Ketsji/SceneGraph,
  Rasterizer, Physics, GameLogic/Network/VideoTexture, Python, laço principal/filtros/ImGui/áudio, gpu e
  spawn/LibLoad. Suspeitos classificados por gravidade (0 = bugs de correção, 1-4 = custo); nada medido ainda.
- `KX_GameObject::RemoveRessources`: quando um material da malha vinha da biblioteca liberada, o `break` só
  saía do laço interno e o externo seguia iterando `m_meshes` já limpo por `RemoveMeshes()` (UB no `LibFree`).
  Agora retorna nos dois ramos. `RangeEngine` compilou; sem teste de `LibFree` em jogo.
- `CcdPhysicsEnvironment::ProcessFhSprings`: desreferenciava `body` antes do teste de nulo; com algum objeto
  Fh na cena, sensores e personagens (sem rigid body) derrubavam a engine. Agora pula `body` nulo.
- `KX_GameObject::ReplaceMesh` com física: as cópias compartilham o `CcdShapeConstructionInfo`, e
  `ReinstancePhysicsShape` sem `dupli` refazia o shape de todas elas. Agora passa `dupli=true`, como o
  `reinstancePhysicsMesh(dupli=True)` do Python. Compilou; falta conferir em jogo.
- `KX_Scene::AddNodeReplicaObject`: reconstruía a navmesh do original a cada cópia e a cópia ficava sem
  navmesh (`ProcessReplica` zera `m_navMesh`). Agora constrói a da cópia.
- `worldOrientation[i] = ...` (mathutils, `MATHUTILS_MAT_CB_ORI_GLOBAL`) gravava a orientação local.
- Texto bitmap 2.4x: cada cópia registrava uma malha duplicada no conversor que só saía no fim da cena.
  O objeto guarda essas malhas (`m_bitmapTextMeshes`) e `NewRemoveObject` as desregistra.
- `KX_GameObject::UpdateComponents`: os dois ramos eram iguais e o activity culling sempre parava os
  componentes. Agora só para com a opção Components ligada; outras suspensões continuam parando.
- `RAS_2DFilter`: offsets de amostragem (`ge_TextureCoordinateOffset`) eram calculados só no 1º frame;
  agora são recalculados quando o canvas muda de tamanho.
- Todos compilados no `RangeEngine`; nenhum conferido em jogo ainda.

## 2026-10-08 - Static Batch, culling sem AABB repetida e detector de trabalho repetido

- `377a0026`: checkbox **Static Batch** (`ob.use_static_batch`) no painel Physics; o conversor junta
  os objetos marcados num `KX_BatchGroup`. Cena de 1.600 objetos: ~707 → ~2.513 FPS sem culling.
- `98f54d7f`: `RAS_MeshBoundingBox::Update()` marcava `m_modified = true` sempre; com DBVT cada objeto
  reenviava a AABB ao Bullet todo frame (~320 µs com 1.600). Agora só marca quando a malha muda.
  Com culling e Static Batch: ~1.170 → ~1.700 FPS, empatando com a referência; sem Static Batch
  ~512 → ~640. Validado no jogo do usuário (nada sumiu ou piscou).
- `61d35afc`: contadores por frame em `getRenderStats()` (`sceneNodeUpdates`, `transformSyncs`,
  `boundsPushes`, `meshMatrixChanges`, `updateNotifies`) e `tools/debug/auditar_trabalho_repetido.py`.
  Com o bug recolocado, `boundsPushes` = 1.600/frame; corrigido, 0.
- Documentos: [batching-estatico-e-culling.md](batching-estatico-e-culling.md),
  [auditoria-trabalho-repetido.md](auditoria-trabalho-repetido.md).

## 2026-10-08 - `SetMatrix()` separa membro do batch quando a matriz muda

`RAS_MeshUser::SetMatrix()` compara a matriz antes de separar; matriz igual mantém o
batch. `RAS_BatchGroup::SplitMeshUser()` notifica um hook virtual, e `KX_BatchGroup`
atualiza a lista e a referência sem acoplar RAS ao KX. `RAS_MeshUser` agora separa os
slots antes de destruí-los. `RangeRuntime` compilou. Teste estático: 64 membros/1 draw
até frame 119; mover referência: 63 membros, `batchGroup=None`, referência seguinte e
draws 1→2; `destruct()` restaurou 64. Remoção da referência e de membro comum também
passou. Validação visual do objeto movido, reload e falha parcial seguem pendentes. A
leitura do checkout da referência não confirmou rebuild integral por quadro; não portar `Reset()`
sem entender o split/restauração. Evidências em `<investigacao-local>/benchmark/diagnostico/anastacio_batch_manual/RESULTADO.md`.

## 2026-10-08 - Ciclo de remoção de membro do KX_BatchGroup corrigido

`KX_GameObject::RemoveMeshes()` agora notifica `KX_BatchGroup` antes de destruir o
mesh user. O grupo remove o ponteiro da lista não proprietária e, se o membro removido
era a referência, troca para um membro restante ou limpa a referência RAS. `RangeRuntime`
compilou; no standalone, remoção do primeiro membro e de um membro comum passou, contagem
ficou em 63, referência correta, `destruct()` completou e exit code foi 0. A próxima peça
separada é invalidação por `SetMatrix`; reload, grupo vazio e falha parcial seguem pendentes.
Evidências em `<investigacao-local>/benchmark/diagnostico/anastacio_batch_manual/RESULTADO.md`.

## 2026-10-08 - Ciclo de remoção de membro do KX_BatchGroup corrigido

`KX_GameObject::RemoveMeshes()` agora notifica `KX_BatchGroup` antes de destruir o
mesh user. O grupo remove o ponteiro da lista não proprietária e, se o membro removido
era a referência, troca para um membro restante ou limpa a referência RAS. `RangeRuntime`
compilou; no standalone, remover o primeiro membro e um membro comum passou, contagem
ficou em 63, referência correta, `destruct()` completou e exit code foi 0. A próxima peça
separada é invalidação por `SetMatrix`; reload, grupo vazio e falha parcial seguem pendentes.
Evidências em `<investigacao-local>/benchmark/diagnostico/anastacio_batch_manual/RESULTADO.md`.

## 2026-10-08 - Split manual antes de mover membro do batch

Na cena sintética de 64 objetos, `KX_BatchGroup.split([obj])` antes da alteração
de `worldPosition` removeu o membro do grupo. Após um frame, `drawCalls` subiu de
1 para 2, mantendo os outros 63 objetos agregados; `destruct()` restaurou 64. O
standalone terminou com exit code 0. Isso valida um fallback manual quando o jogo
antecipa a transformação. Não resolve invalidação automática, referências na lista
Python após `endObject()` nem reload/troca de cena. Reproduções e log em
`<investigacao-local>/benchmark/diagnostico/anastacio_batch_manual/`.

## 2026-10-08 - Auditoria do batching existente para auto-batching

Continuação da investigação da referência. A Anastacio já possui batching estático via
`KX_BatchGroup`/`RAS_BatchGroup`/`RAS_BatchDisplayArray`, mas o uso é explícito por
Python. A principal lacuna para automação é que `RAS_MeshUser::SetMatrix()` não
separa/reconstrói o membro do batch quando sua transformação muda. Também foram
registrados os limites do mesh user de referência, `frontFace=true`, transparência,
deformers/atributos por objeto, falha parcial de merge e validação das passadas de
sombra. Próxima etapa recomendada: testar o batch manual, especialmente transformação,
remoção e reload, antes de automatizar a elegibilidade. Nenhum código C++ foi alterado
nesta etapa; mudanças de profiler que já estavam no workspace foram preservadas.
Detalhes em `docs/batching-estatico-e-culling.md`.

## 2026-10-08 - Teste do KX_BatchGroup manual no standalone

Cena sintética local de 64 objetos/16 meshes compartilhados executada no
`AnastacioRuntime.exe`: batch manual resultou em 1 draw call e `destruct()` restaurou
64. Mover membro manteve `batchGroup` ativo, consistente com a matriz copiada para os
vértices agregados; confirmação visual pendente. Remover um membro com `endObject()` e
destruir o grupo completou sem crash, mas `group.objects` ainda mostrava 64 no intervalo
observado; após destruição, 63 draws. Reload de cena no mesmo processo não testado.
Nenhum C++ foi alterado. Dados e limites em
`<investigacao-local>/benchmark/diagnostico/anastacio_batch_manual/RESULTADO.md`.

Para achar uma entrada por assunto: `grep -rn "^## .*termo" docs/changelog.md docs/changelog/`.
Entradas antigas não estão em ordem cronológica estrita; a data no título é a referência.

| Arquivo | Datas | Entradas | Tamanho |
|---|---|---|---|
| [este arquivo](changelog.md) (entradas recentes) | 2026-10-08 | 35 | 45 KB |
| [14_2026-10-06_a_2026-10-05.md](changelog/14_2026-10-06_a_2026-10-05.md) | 2026-10-06 a 2026-10-05 | 42 | 54 KB |
| [15_2026-10-04_a_2026-10-03.md](changelog/15_2026-10-04_a_2026-10-03.md) | 2026-10-04 a 2026-10-03 | 60 | 63 KB |
| [16_2026-10-02_a_2026-10-01.md](changelog/16_2026-10-02_a_2026-10-01.md) | 2026-10-02 a 2026-10-01 | 76 | 68 KB |
| [17_2026-09-30_a_2026-09-27.md](changelog/17_2026-09-30_a_2026-09-27.md) | 2026-09-30 a 2026-09-27 | 48 | 63 KB |
| [18_2026-09-26_a_2026-09-25.md](changelog/18_2026-09-26_a_2026-09-25.md) | 2026-09-26 a 2026-09-25 | 54 | 62 KB |
| [13_2026-09-24_a_2026-09-24.md](changelog/13_2026-09-24_a_2026-09-24.md) | 2026-09-24 a 2026-09-24 | 22 | 30 KB |
| [12_2026-09-23_a_2026-09-23.md](changelog/12_2026-09-23_a_2026-09-23.md) | 2026-09-23 a 2026-09-23 | 9 | 13 KB |
| [11_2026-09-22_a_2026-09-20.md](changelog/11_2026-09-22_a_2026-09-20.md) | 2026-09-22 a 2026-09-20 | 25 | 39 KB |
| [10_2026-09-20_a_2026-09-20.md](changelog/10_2026-09-20_a_2026-09-20.md) | 2026-09-20 a 2026-09-20 | 12 | 19 KB |
| [01_2026-09-20_a_2026-09-14.md](changelog/01_2026-09-20_a_2026-09-14.md) | 2026-09-20 a 2026-09-14 | 45 | 69 KB |
| [09_2026-09-17_a_2026-09-06.md](changelog/09_2026-09-17_a_2026-09-06.md) | 2026-09-17 a 2026-09-06 | 51 | 71 KB |
| [02_2026-09-14_a_2026-09-11.md](changelog/02_2026-09-14_a_2026-09-11.md) | 2026-09-14 a 2026-09-11 | 24 | 71 KB |
| [03_2026-09-12_a_2026-08-23.md](changelog/03_2026-09-12_a_2026-08-23.md) | 2026-09-12 a 2026-08-23 | 49 | 90 KB |
| [08_2026-09-06_a_2026-09-02.md](changelog/08_2026-09-06_a_2026-09-02.md) | 2026-09-06 a 2026-09-02 | 26 | 68 KB |
| [07_2026-09-02_a_2026-08-31.md](changelog/07_2026-09-02_a_2026-08-31.md) | 2026-09-02 a 2026-08-31 | 23 | 69 KB |
| [06_2026-08-31_a_2026-08-26.md](changelog/06_2026-08-31_a_2026-08-26.md) | 2026-08-31 a 2026-08-26 | 7 | 71 KB |
| [05_2026-08-25_a_2026-08-24.md](changelog/05_2026-08-25_a_2026-08-24.md) | 2026-08-25 a 2026-08-24 | 2 | 68 KB |
| [04_2026-08-24_a_2026-08-24.md](changelog/04_2026-08-24_a_2026-08-24.md) | 2026-08-24 a 2026-08-24 | 4 | 81 KB |

## 2026-10-08 - Auto-batching RAS confirmado na engine de referência

Comparacao direta do checkout da referência com a Anastacio identificou `TryAutoBatch` no
RAS da referência. A cena estatica do benchmark tem 1.600 objetos em 16 meshes
compartilhados, um material; o player de junho marca `isMDEI=false`. Logo, MDEI nao
explica o resultado.

Foi feito A/B no mesmo executavel da referência de junho (SHA-256 no manifesto) e na mesma
cena, mudando apenas `bge_allow_auto_batch` nos 16 datablocks de mesh. Resolucao
1280x720, viewport 1281x721, MSAA/AF 2, VSync 0, culling desligado, ticrate 10000,
2 s de aquecimento e 4 s de amostra. Duas repeticoes alternadas: False 661,8/667,2
FPS (media 664,5); True 2610,0/2595,0 (media 2602,5), ganho de 3,92x. Todas as
rodadas produziram 128600 primitivas. A cena original sem a propriedade explicita
mediu 2636 FPS, alinhada ao valor True.

No fonte da referência, a conversao le a propriedade (default true) e configura
`RAS_Mesh::SetAllowAutoBatching`; o renderer so a consulta para decidir se tenta
`TryAutoBatch`. O A/B com o player real confirma que o auto-batching explica a maior
parte da diferenca na cena estatica. Nao houve alteracao de fonte/build da engine.
Nao foi capturado o numero exato de draws GL; a medicao de primitivas confirma que a
geometria permaneceu presente. Dados, cenas, scripts e hashes em
`<investigacao-local>/benchmark/diagnostico/autobatch_ab/RESULTADO-AUTOBATCH-AB.md`.

Proximo passo: avaliar um prototipo opt-in na Anastacio para objetos estaticos ou
raramente alterados, preservando fallback e invalidacao de transformacoes. Nao
inferir beneficio para carros dinamicos.

## 2026-10-08 — Cache da camada do objeto e validação do standalone

Usuário confirmou ausência de lag percebido na rodada sem instrumentação do
standalone e física funcionando bem, com limite de 60 FPS. Área da janela
confirmada em 2560×1440 usando configurações salvas (sem -w 1280 720). Agente
entrou pelo menu na Pista_1 e enviou I depois da contagem; teste anterior em janela
menor confirmou progresso automático pelos checkpoints. Isso valida funcionamento
da primeira otimização; não estabelece ganho de FPS no jogo.

Nova peça em gpu_material.c: GPU_OBJECT_LAY só é reenviado quando muda, com
invalidação em GPU_material_bind para programas compartilhados e novas passadas.
Nenhuma outra atualização de objeto é pulada. Editor e player recompilados.
Seis execuções de controle passaram: legado 1600 → 1 inteiros/quadro; camada
alternada 1600 → 16 (ordem de desenho por malha); ObjectInfo preserva 1600 matrizes
e vetores; PBR conserva 8 comandos de probes. Teste C do bloco real passou
troca/retorno de camada, zero, bits altos/múltiplos, reativação de programa
compartilhado e localização ausente.

Oito rodadas sem profiler, OFF/ON/ON/OFF, 5 s de aquecimento + 15 s de amostra:
MSAA 2/AF 2: 704,3 → 710,6 FPS (+0,89%, pequeno/inconclusivo). MSAA 4/AF 4:
controle variou de 561,5 a 672,8 e cache de 685,9 a 715,5; não atribuir a
diferença média ao cache sem repetição mais estável. Não há ganho consistente
demonstrado dessa peça, nem explicação da diferença grande com a referência legada.
Física/lógica intactas; validação visual no jogo dessa segunda peça pendente.
Checker mantém 30 referências antigas de física e 3 avisos preexistentes.
Evidências: `<investigacao-local>/benchmark/diagnostico/CACHE-CAMADAS.md`.

## 2026-10-08 — Segunda rodada do RolimaRacer e hipótese de desfoque

Usuário confirmou Pista_1, 10 carros e muitos efeitos; orientou continuar testes
e apenas registrar lags, investigando se forem frequentes. Suspeita de desfoque
da câmera em movimento rápido registrada como hipótese. Player de controle sem
cache executou o jogo: 37 médias e 26 picos, incluindo espera de 6,45 s em swap.
Nas duas sessões, recortes após 25 s com física tiveram mediana de 60 FPS e zero
uploads de probes. Sem ganho demonstrado do cache na pista; não comparar taxas
de picos porque trajetos/durações diferiram. Próxima rodada sem profiler/log de
animação, com efeitos preservados. Fonte/editor/player otimizado permanecem iguais.
Evidências: `<investigacao-local>/benchmark/diagnostico/rolima-real/COMPARACAO-PISTA1.md`.

## 2026-10-08 — Primeira execução do cache no RolimaRacer

Player principal abriu `D:/ProjetoRolimaRacer/RolimaRacer.range` pelo menu normal,
com profiler e log de animação, sem modificar jogo ou frequência de lógica/física
(tic rate inicial 60). Usuário relatou que chegou à corrida com alguns lags.
50 médias/19 picos: muitos trechos em 60 FPS; maiores pausas em `endframe.swap`,
incluindo 6,64 s, sem compilação/criação de textura naquele quadro. Causa ainda
não identificada; foco da janela e comparação sem cache pendentes. Houve também
picos de preparação de cenas. Probes tiveram zero uploads em todas as médias:
ganho do controle PBR não demonstrado no jogo. Pista não confirmada. Evidências:
`<investigacao-local>/benchmark/diagnostico/rolima-real/PRIMEIRA-VALIDACAO.md`.

## 2026-10-08 — Comparação de FPS do cache de probes ausentes

Dois players de teste compilados com o mesmo código de diagnóstico: o controle
desliga somente os retornos antecipados do cache. Fonte restaurada e editor/player
principais recompilados com a otimização. Série longa sem RANGE_PROFILE, ordem
OFF/ON/ON/OFF, 5 s de aquecimento e 15 s de amostra, 1600 objetos com Principled:
MSAA 2/AF 2: 240,2 → 288,9 FPS (+20,3%); MSAA 4/AF 4: 242,7 → 292,8 (+20,6%).
Janela 1280×720, viewport de desenho 1281×721, VSync 0 e 128602 primitivas iguais;
hardware AMD RX 6800M. O tic rate elevado só pertence à cena estática de benchmark.

Série curta exploratória teve variação grande no controle legado e não fundamenta
ganho nesse material; primeira rodada curta coincidiu com o término do rebuild.
Série longa ocorreu após os builds e é a evidência de FPS do PBR. Resultado não
mede jogo real nem compara com a referência. Cores seguem adiadas. Validação do carro
e probes visuais no jogo depende do arquivo do usuário. Dados/hashes em
`<investigacao-local>/benchmark/diagnostico/cache_long_summary.json`.

## 2026-10-08 — Cache de probes ausentes por ativação do material

`gpu_material.c` evita repetir os uniforms das duas probes ausentes durante uma
ativação do material. Reinicia em `GPU_material_bind`; probe ativa invalida o estado
ausente e continua vinculando textura por objeto. Mudança de maxlod força envio.
Não muda lógica, física, matrizes ou seleção de probes.

Editor e player compilados via MSVC. Quatro cenas executadas com MSAA 2 e AF 2:
PBR passou de 12.800 comandos de probe/quadro para 8; legado manteve 1.600 inteiros
de objeto, ObjectInfo manteve 1.600 matrizes e instancing permaneceu fora desse caminho.
Teste C com as funções reais extraídas e wrappers simulados passou repetição,
alteração de maxlod, probe ativa repetida, ativa para ausente, reinício e peso zero.
Ganho de FPS sem profiler e validação visual com probes no jogo real ficam pendentes.
Evidências: `<investigacao-local>/benchmark/diagnostico/CACHE-PROBES.md`.
Checker de docs: 30 referências antigas da física e 3 avisos preexistentes.

## 2026-10-08 — Contagem de uploads na atualização do objeto

- Novo GPU_render_profile.h e contadores no ponto de envio ao OpenGL, classificados
  por objeto, sombras, luzes/IES, probes, dano e skinning. Contagem de comandos após
  retornos por localização ausente/ponteiro nulo, não bytes nem uploads de imagem.
  Profiler grava médias por quadro e zeros; fases locais à thread.
- Na cena legada de 1600 objetos: 1600 uniforms inteiros de camada e zero uploads
  nas fases de sombra/luzes/probes/dano. No controle Principled: 30400 comandos por
  quadro, incluindo estado padrão de recursos ausentes. Controle Object Info:
  1600 matrizes 4×4 e 1600 vetores por quadro, validando os contadores positivos.
- Cenas de nós sem opt-in PBR não exercitaram o shader esperado e foram excluídas;
  os controles positivos usam game_settings.use_shading_nodes=True.
- RangeRuntime e RangeEngine compilados com VSLANG=1033/vcvars64. Execuções instrumentadas
  e controles sem profiler passaram. Nenhum corte de atualização implementado;
  frequência/passos de lógica/física e comportamento de veículos não foram alterados.
- Evidências locais: `<investigacao-local>/benchmark/diagnostico/CONTAGEM-UPLOADS.md`.
  Próxima peça: cache específico de um estado padrão, com invalidação e teste no jogo.

## 2026-10-08 — Decomposição do desenho por objeto

- RunNode dividido em medições de estado, ativação de material, push/apply/pop de
  matriz e submissão. Duas rodadas das quatro cenas, com ordem inversa na segunda,
  e quatro controles com profiler desligado encerraram com sucesso.
- Ativação do material foi a maior fase individual nas duas rodadas; matrizes e
  submissão também contribuem. Estados de alpha, front face e seleção de luzes já
  têm caches. Medições curtas continuam limitadas pelo piso do cronômetro.
- RangeRuntime compilado com ambiente MSVC correto. Controles sem profiler:
  681/1894/2186/3119 FPS (1600/400 objetos separados, instancing e mesh unido).
- Evidências locais: `<investigacao-local>/benchmark/diagnostico/FASES-DO-DESENHO.md`.
  Próxima peça: contar uploads e trabalho realmente executado na atualização do
  objeto. Nenhum corte de recursos ou otimização de comportamento aplicado.

## 2026-10-08 — Diagnóstico de render por objeto versus a engine de referência

- Adicionadas medições por amostragem ao profiler existente: mesh slot, atualização do
  objeto/uniforms, seleção/envio de luzes e submissão. Helper novo sem alterar layouts de structs.
- Quatro cenas executadas; o caminho `RAS_MeshSlot::RunNode` concentrou a maior parte do
  tempo de CPU de render na cena de 1600 objetos sem instancing. `ProcessLighting` já tem
  cache por camada/cena; contagem de entradas não indica reconstrução de luzes.
- Medição completa descartada por overhead; amostragem 1/61 inclui bloco vazio e fases
  separadas. Estimativas pequenas permanecem limitadas pelo custo do cronômetro.
- `RangeRuntime` compilado com ambiente MSVC correto e cenas instrumentadas encerraram
  com sucesso. Sem otimização gráfica aplicada; cores adiadas por decisão do usuário.
- Quatro controles com profiler desligado encerraram com sucesso: 683/2026/2179/3062 FPS
  (1600/400 objetos, instancing e mesh unido). Editor e runtime recompilados com sucesso.
- Checker de docs: 30 referências antigas no mapa de física e três avisos de tamanho,
  fora dos arquivos instrumentados.
- Evidências locais: `<investigacao-local>/benchmark/diagnostico/LOCALIZACAO-GARGALO.md`.
  Próxima investigação: decompor estado/matrizes/submissão de RunNode; culling é frente separada.

## 2026-10-08 — Conversão: normais e tangentes das malhas em paralelo

- `BL_PrepareMeshes` (`BL_BlenderDataConversion.cpp`), chamado no início de `BL_ConvertBlenderObjects`:
  junta as malhas dos objetos que vão converter (cena e grupos de dupli, na ordem da conversão) e calcula em
  threads (`std::thread`, uma por núcleo) o `CDDM_from_mesh`, o hash de loops, as normais de loop e as
  tangentes MikkTSpace. Cada thread só lê dados Blender de malhas distintas e escreve no próprio
  DerivedMesh; materiais, display arrays, `KX_Mesh`, cache de loops e `.cooked` continuam na thread principal.
  `BL_ConvertMesh` usa o DerivedMesh pronto (com o hash tirado antes das normais) e o resto do caminho é o mesmo.
- Malhas que vão sair do `.cooked` (chave prevista a partir dos materiais Blender) e cópias idênticas
  (mesmo hash; copiam do cache de loops) não calculam nada no lote. Previsão errada só devolve o trabalho
  ao caminho sequencial; o resultado não muda.
- `RANGE_NO_MESH_BATCH=1` volta ao cálculo malha a malha, para comparar. `[Load] convert` mostra
  `mesh batch N Xms` (tempo de parede do lote).
- Medido (10 núcleos), convert sequencial → lote: `level_1_home` (YoFrankie) sem `.cooked` 324–504 → 149–167 ms,
  com `.cooked` 101–134 → 74–79 ms; `make_cooked_small_test.py` 16 segmentos sem cozido 128–134 → 63 ms,
  com cozido 25–27 → 28–30 ms (todas cozidas: o lote só custa ~4 ms de threads e DerivedMesh).
- Checksum exato (posição, normal, tangente, UV, cor e polígonos em float32) idêntico entre build anterior,
  lote e `RANGE_NO_MESH_BATCH=1`, com e sem `.cooked`, em `level_1_home`, `make_cooked_small_test.py` e
  `make_cooked_mesh_test.py`.

## 2026-10-08 — Compilação paralela dos shaders de material

- Com `GL_ARB_parallel_shader_compile`, os programas de todos os materiais são enviados ao driver antes de
  montar cada material (`GPU_shader_prefetch_*` em `gpu_shader.c`, `GPU_material_prefetch`,
  `KX_BlenderMaterial::PrefetchMaterial`); o driver compila vários ao mesmo tempo e cada montagem só pega o
  programa pronto (mesma chave do binário do `.cooked`). Sem a extensão, nada muda.
- `addScene` assíncrono, LibLoad assíncrono e recarga por luzes novas enviam os materiais aos poucos, dentro do
  orçamento do frame, e só depois montam (`step_shaders` em `BL_Converter.cpp`): a tela de loading segue
  desenhando. No AMD a consulta `GL_COMPLETION_STATUS_ARB` espera a compilação acabar, por isso não é usada.
- `RANGE_NO_PARALLEL_SHADERS=1` volta à compilação um por um; `RANGE_SHADER_SALT=<texto>` põe um comentário em
  todo shader para o cache do driver errar e medir a primeira abertura.
- AMD RX 6800M, compilação a frio: `make_parallel_shader_test.py` (48 materiais) 16,5 → 4,2 s, imagens
  idênticas; RolimaRacer até a corrida 61,7 → 22,6 s (shaders da pista 49,1 → 11,2 s até ficar pronta).
  Sem testar ainda em NVIDIA.

## 2026-10-08 — `.cooked`: carregamento das malhas em bloco

- Vértices cozidos escritos em bloco (`RAS_DisplayArray::AppendVertices`/`AddVertexInfo`/`AddIndices`):
  normais e tangentes por `memcpy`, UV e cor camada por camada, em vez de um `AddVertex` por vértice.
- `hash_bytes` com 4 trilhas de 64 bits e campos juntados em bloco antes do hash (`hash_strided`); chave
  versão 4 (registros antigos de malha são regravados).
- `make_cooked_small_test.py`, 8 064 loops com cozido: 259 → 206 ms (parte cozida 141 → 96 ms, hash
  35 → 27 ms). O que sobra é limitado por memória (alocar e preencher os vértices).
  Checksum de `make_cooked_mesh_test.py` idêntico.

## 2026-10-08 — `.cooked`: normais e BVH de física

- O registro de malha (chave versão 3) guarda também a normal de cada vértice gerado: com o cozido o
  `calcLoopNormals` é pulado (200 malhas de 8 064 loops: 56 → 0 ms).
- Registro novo (tipo 4): a BVH das formas Triangle Mesh serializada pelo Bullet
  (`btOptimizedBvh::serializeInPlace`), com chave do hash dos arrays de física que o `CcdEndBvhBatch` já
  calculava. Carregar é uma cópia mais `deSerializeInPlace`. O cabeçalho repete a chave inteira e é conferido
  antes do uso. `[Load] convert` mostra `physics Xms (bvh Xms; ...)` e o `[Cooked]` conta as BVHs.
- `make_cooked_mesh_test.py` faz 400 raycasts na malha de física e põe ponto, normal e polígono no checksum:
  idêntico entre rodada normal e cozida; física do teste 15 → 1 ms.
- `make_cooked_small_test.py`, convert com cozido antes → depois: 8 064 loops 396 → 259 ms (BVH 100 → 14 ms),
  1 984 loops 98 → 78 ms. O `.cooked` desse teste foi de 42 para 87 MB.

## 2026-10-08 — `.cooked`: todas as malhas

- Removido o mínimo de 10 mil loops: o registro cozido ganha em qualquer tamanho. Novo
  `tests/convert_flag/make_cooked_small_test.py` (200 malhas únicas com UV), convert sem → com cozido:
  112 loops 45 → 21 ms (0,8 MB), 480 loops 120 → 35 ms (2,7 MB), 1 984 loops 436 → 98 ms (10 MB),
  8 064 loops 1 820 → 396 ms (42 MB). No RolimaRacer (537 malhas, só 15 com 10 mil+ loops) o mínimo
  antigo deixava quase tudo de fora.

## 2026-10-08 — `.cooked`: tangentes

- O registro de malha (versão 2 da chave) guarda também a tangente de cada vértice gerado (4 floats) quando a
  malha usa tangentes; com o registro cozido o `DM_calc_loop_tangents` (mikktspace) é pulado.
- `make_cooked_mesh_test.py` agora inclui as tangentes no checksum: idêntico entre rodada normal e cozida.
  Malha do teste (24 mil vértices): meshes 32 → 4 ms, tangentes 24 → 0 ms; `.cooked` de 849 KB.

## 2026-10-08 — `.cooked`: buffers de malha

- O `.cooked` ganhou um registro novo (tipo 3) com a montagem dos display arrays de cada malha: para cada
  vértice gerado, de qual loop ele veio (o bit alto marca face plana), mais os índices de primitiva e de
  triângulo (os de triângulo só quando diferem). Ao carregar, os vértices são remontados direto dos loops,
  sem a busca de vértices compartilhados, que era a parte lenta (`BL_CookedArrays` em
  `BL_BlenderDataConversion.cpp`).
- Chave: o hash de normais/tangentes que já existia mais slots de material, `mat_nr` das faces, todas as
  camadas de UV e de cor e uma versão. Ficam de fora malhas com menos de 10 mil loops, com dados de osso
  (GPU skinning) e com texto bitmap. Dados que não batem com a malha são rejeitados antes de tocar nos arrays.
- Primeira versão guardava os vértices prontos: 104 MB no teste de 12 objetos. Guardando só os loops ficou
  22,6 MB, com a malha um pouco mais lenta (esfera de 130 mil triângulos: 57 → 14 ms com vértices prontos,
  57 → 26 ms com loops).
- `[Load] convert` mostra `N cooked Xms` e o resumo `[Cooked]` conta as malhas.
- Validação (`tests/convert_flag/make_vs_libload.py`, Runtime, rodadas repetidas): convertObject
  834 → 332 ms e LibLoad 850 → 295 ms (convert 496 → 244 ms). Novo
  `tests/convert_flag/make_cooked_mesh_test.py` (2 materiais com um wire, faces lisas e planas, 2 UVs e cor):
  checksum de vértices, normais, UVs, cores e polígonos idêntico entre a rodada normal e a cozida.

## 2026-10-08 — Aquecimento de shaders: idiomas, reinício no editor e cache único

- Tela de aquecimento (`LA_Launcher.cpp`) em inglês, português, espanhol e russo, pelo idioma da engine (`BLT_lang_get`).
- Editor: o reinício pedido pelo aquecimento vinha sem arquivo e lia um caminho inválido (`Error: loading C:\ failed`). `BL_KetsjiEmbedStart.cpp` agora reinicia com os dados da memória quando não há arquivo, mantendo alterações não salvas.
- Cache do usuário (`CcdCookedData.cpp`): o hash do caminho trata `/` como `\` no Windows. O editor passava `D:/...` e o player `D:\...`, criando dois caches do mesmo jogo.
- Validado com RolimaRacer no editor: aquecimento de 321 shaders, reinício sem erro, e na abertura seguinte o editor reusou o cache do player (menu: 33 shaders em 55 ms). Tela traduzida não foi verificada visualmente.

## 2026-10-08 — Player Windows AnastacioRuntime.exe e integração com RangeArmor

- Usuário autorizou a segunda etapa. Alvo `RangeRuntime` mantém seu nome interno e
  produz `AnastacioRuntime.exe` no Windows; recurso e registro de `.range` atualizados.
  Linux e artefatos Web/Android mantidos. Standalone, Cook e export nativo adaptados.
- RangeArmor cria caminhos novos, aceita configuração legada e mantém prioridade de
  caminhos existentes/personalizados. Somente config da entrega é ajustado ao runtime
  copiado. Templates antigos conhecidos por hash usam launcher atual no Run/Export;
  descoberta da instalação portátil não exige variáveis de ambiente.
- Build editor/player passou (14 etapas). Launcher: três testes/build; painel: 26 testes
  release/build. Link dos testes debug falhou com LNK1104 no artefato antigo; perfil release
  passou. Doze testes Python e 132 Web/Android passaram. Quatro avisos herdados do painel.
- Player novo, Cook pelo editor, standalone e export nativo executaram a cena controlada;
  hull preparado usado. Corrigido fixture do editor que tentava abrir `.rasec` como `.range`.
  Artefatos antigos do player retirados da raiz de `build/bin/` para backup reversível.
- ZIPs atuais em `build/dist/validation-20261008-113829/`, CRC/caminhos/extração conferidos.
  Primeiro ensaio sem override usou pacote anterior enquanto o novo staging terminava;
  repetido sequencialmente com o pacote atualizado. Projeto/config/launcher legados,
  Cook, export e jogo extraído passaram. Evidências e limites na seção 14 do
  [plano](executable-rename-plan.md#14-player-windows-renomeado--2026-10-08).
  Nenhuma publicação ou alteração das associações no Registro.

## 2026-10-08 — Pacotes Windows atuais preparados e executados após extração

- Staging isolado da instalação atual gerou engine (188.011.888 bytes) e RangeArmor
  (10.435.006 bytes), com SHA256, caminhos `/` e CRC conferidos. Símbolos, logs,
  caches Python, testes e backup Godot excluídos; CRT e licenças preservados.
- Editor/painel extraídos iniciaram. Scripts e Python extraídos copiaram runtime,
  prepararam `.cooked` e exportaram fixture; launcher executou e confirmou uso do hull.
  Preferências restauradas. Corrigido campo DataSource ausente no primeiro fixture.
- Sem publicação nem rebuild nativo. Pacotes em `build/dist/validation-20261008-111756/`;
  evidências, instrução de instalação da ferramenta e limites no
  [plano de migração](executable-rename-plan.md#13-pacotes-windows-atualizados--2026-10-08).

## 2026-10-08 — Mapas atualizados e export comprimido pela GUI validado

- `check_docs.py --fix` atualizou 91 referências/contagens do mapa. Checagem posterior:
  zero erros e zero avisos. Alteração documental, sem necessidade de rebuild nativo.
- 132 testes Web/Android e nove testes de segurança/cópia da RangeArmor passaram.
- Export Windows64 pela GUI com compressão gerou ZIP, preservando entrega anterior.
  Integridade e caminhos `/` conferidos; pacote extraído em pasta com espaços executou
  launcher com exit 0 e confirmou uso do hull preparado. CRT e `.cooked` presentes.
- Preferências restauradas; nenhuma publicação. Evidências e limites no
  [plano da ferramenta](rangearmor-update-plan.md). Runtime de desenvolvimento torna
  ZIP grande; staging público deve excluir símbolos e arquivos internos.

## 2026-10-08 — Jogo confirmado pelo usuário e sobras do editor retiradas

- Usuário confirmou execução do jogo; plataforma/pacote e desempenho não especificados.
- Cinco artefatos antigos do editor movidos de `build/bin/` para backup reversível,
  incluindo executável de teste de setembro e símbolos antigos. Editor atual executou
  com startup de fábrica e retornou 0. Nenhum rebuild limpo necessário.
- Runtime e RangeArmor mantêm os nomes da primeira etapa. Inventário e backup no
  [plano de migração](executable-rename-plan.md).

## 2026-10-08 — Exportação pela GUI da RangeArmor testada e logotipo ampliado

- Projeto temporário aberto pelo botão Open Project/seletor de pasta; botão Export
  Windows64 gerou cache/entrega e mostrou sucesso. Launcher exportado executou a lógica
  da cena e utilizou hull preparado. MainFile inexistente mostrou falha na GUI e manteve
  entrega anterior. Controles reais acionados por automação de acessibilidade do Windows.
- Logotipo do cabeçalho ganhou área fixa de 280 × 84 pontos, com proporção preservada.
  Build release passou; painel instalado aberto para conferir aparência. Backup em
  `build/safety-backups/rangearmor-logo-20261008-105253/` e imagem em
  `build/rangearmor-logo-validation.png`.
- Lista de recentes/config do painel restaurada byte a byte. Sem alteração de projeto
  real ou publicação. Limites e evidências no [plano](rangearmor-update-plan.md).

## 2026-10-08 — Painel RangeArmor recompilado com tratamento de exit code

- Runner Rust considera exit code além de mensagens `X ` e aguarda leitura dos dois
  streams antes de marcar conclusão. Novo teste cobre saída 7 sem prefixo de erro.
- 26 testes passaram e build release concluiu com MSVC/vcvars64/VSLANG. Rust 1.92
  não satisfazia dependências egui/eframe; instalado toolchain 1.95.0 separado e usado
  explicitamente, sem mudar o compilador padrão. Avisos de campos não lidos em `project.rs`.
- Executável novo criou janela e fechou com exit 0 antes/depois da instalação; hashes
  SHA256 conferem. Backup em `build/safety-backups/rangearmor-panel-20261008-104444/`.
  Nenhuma publicação. Exportação pela GUI/jogo real continua pendente; [plano](rangearmor-update-plan.md).

## 2026-10-08 — Inicialização do painel RangeArmor verificada

- Painel instalado Rust/eframe criou sua janela e fechou normalmente, exit 0.
  Teste identificou janela por PID/título e enviou fechamento; `WaitForInputIdle`
  não era adequado ao executável. Evidência em `build/rangearmor-panel-startup.json`.
- GUI Godot permanece como backup. Interação com projetos/botões ainda pendente.
  Fonte Rust do runner ignora exit code e depende de prefixo `X `; correção para
  falhas silenciosas ficou registrada no [plano](rangearmor-update-plan.md).

## 2026-10-08 — Erros na cópia de runtimes da RangeArmor propagados ao chamador

- Script de cópia retornava sucesso após diagnóstico de falha. Agora encerra com código 1
  para projeto inválido, runtime ausente, plataforma não suportada ou exceção na cópia.
- Nove testes passaram, incluindo CLI real e restauração do runtime anterior após falha
  na substituição pelo staging. Script instalado atualizado com backup; execução sem
  config retornou 1. GUI permanece pendente; [plano](rangearmor-update-plan.md).

## 2026-10-08 — Runtime copiado pela RangeArmor executado fora do build

- Script instalado copiou instalação real para projeto temporário em caminho com espaço
  e acento. CRT/Python/player presentes, editores excluídos. Preparador instalado gerou
  `ANACOOK2` usando player copiado; execução de `.rasec` confirmou uso do cache e marcador
  da lógica da cena. Evidência em `build/rangearmor-real-copy-validation.txt`.
- Teste direto anterior revelou limitação de codificação do destino de `ANASTACIO_COOK`
  com acento; preparador atual passou com arquivo temporário e cópia Python. Limitação
  nativa registrada no [plano](rangearmor-update-plan.md), sem alteração de C++.
- GUI, jogo real, outra GPU/Linux e APK em aparelho continuam pendentes.

## 2026-10-08 — Cópia dos runtimes da RangeArmor atualizada

- Script instalado legado foi preservado em backup e substituído pelo fonte recuperado.
  Removida dependência de corte fixo do caminho Python e de lista fixa de DLLs que omitia CRT.
- Cópia exclui editores RangeEngine/AnastacioEngine, preserva player e dependências,
  usa staging e mantém runtime anterior em pasta `.previous-*`. Destinos sobrepostos
  à origem ou fora do projeto são recusados.
- Oito testes Python passaram; cópia executada sobre instalação simulada, com falha
  injetada e preservação do destino anterior. GUI, instalação completa e jogo real
  continuam pendentes. Ver [plano](rangearmor-update-plan.md).

## 2026-10-08 — Exportadores Web/Android verificados com o editor renomeado

- Usuário confirmou funcionamento do editor novo. 131 testes puros Web/Android passaram.
- Integração `engine_web_export.py` passou no `AnastacioEngine.exe`: pacote/manifesto,
  controles e preservação da exportação anterior verificados. Preflight inicial reportou
  `WEB-GFX-002`: falso positivo causado por log de tempo com "shaders" e "compiled".
  Heurística em `tools/web/package-web.py` agora exige indicação de falha. Teste JavaScript
  de regressão passou para logs de sucesso, falha real e diagnóstico estruturado; novo
  export/preflight real passou sem problemas. Diagnóstico inicial preservado em
  `build/editor-rename-web-preflight.json`. Jogo real continua exigindo validação visual.
- Integração `engine_android_export.py` passou, incluindo Gradle `assembleDebug`, relatório
  e conteúdo do APK. APK de teste gerado no diretório temporário registrado no plano;
  não instalado em aparelho nem publicado. Android NDK permanece congelado.
- Nomes `RangeRuntime.exe` e artefatos `RangeRuntime` Web preservados. Nenhuma alteração
  de C++ ou do formato de cooking nesta continuação. Ver [plano](executable-rename-plan.md).

## 2026-10-08 — Editor Windows renomeado para AnastacioEngine.exe

- `OUTPUT_NAME` no ramo executável Windows do alvo `RangeEngine`; módulo `bpy`, alvo interno,
  player, APIs, preferências, ProgIDs e nomes Linux/Web preservados. Recurso Windows compartilhado
  distingue `OriginalFilename` do editor e do player. Detecção do processo pai aceita nomes
  novo/legado com comparação exata sem distinção de caixa; ícones externos não dependem do nome novo.
- Build inicial teve LNK1104 no player e falha no install do editor por arquivo ausente.
  A instalação global do pós-build podia concorrer com o link do player. Dependência Windows
  `RangeEngine` → `RangeRuntime` agora ordena essas etapas; segundo build completo passou.
  CMake informou ausência do compilador CUDA neste ambiente; recompilação de cubins não foi validada.
- 32 arquivos de ferramentas/templates tiveram comandos Windows atualizados, além das instruções
  vigentes. README distingue fonte atual de releases anteriores, cujos executáveis não mudaram.
- Backup em `build/safety-backups/editor-rename-20261008-095726/`; editor antigo movido de
  `build/bin/` para esse backup. Não foi encontrado Registro apontando ao antigo executável desta
  instalação, portanto não foi criada nem removida associação de arquivos.
- Validação: `ninja RangeEngine RangeRuntime` passou com vcvars64/VSLANG; editor iniciou e expôs
  novo caminho; metadados dos dois executáveis corretos; Cook real, abertura de `.range`, save
  de cópia e resolução do painel pelo editor novo passaram. Caminho do painel foi capturado em
  teste, sem iniciar a GUI. Sete testes Python do backend RangeArmor continuam passando.
- ZIP local `build/dist/AnastacioEngine-rename-validation-20261008-100156.zip` extraído em pasta
  com espaços: editor iniciou; player gerou `.cooked` e executou `.rasec`. `blender.crt/` presente,
  executável antigo ausente do ZIP. Pacote de validação não publicado.
- Pendente: jogo real/GUI/console, Steam/LAN, registro e remoção HKCU/HKLM em ambiente de teste,
  Windows sem Visual Studio. Ver [plano de migração](executable-rename-plan.md).
  Verificador de docs mantém os 30 erros/61 avisos anteriores dos mapas de código.

## 2026-10-08 — RangeArmor: preparo do cooking e exportação com staging

- Backup em `build/safety-backups/rangearmor-20261008-093834/`: módulos de fonte antes da edição,
  scripts instalados originais da RangeArmor, launcher original e comparação com o snapshot.
  Fonte histórico `69df19d9` recuperado em `tools/rangearmor/`, fora da pasta ignorada.
- Cook manual prepara saída temporária, substitui o cache após sucesso e preserva o anterior em
  falha/timeout. Uma preparação vazia bem-sucedida remove o resultado antigo.
- Backend RangeArmor prepara o `.cooked` do `MainFile` protegido antes de empacotar. Export de um
  clique fornece o runtime do host; save protegido e JSON precisam terminar com sucesso.
  Painel usa caminho derivado do diretório do editor, sem corte fixo pelo nome do executável.
- Opção `Cook before export`, ligada por padrão no export de um clique. Desligada usa `--no-cook`:
  entrega sem `.cooked`, preservando os caches de autoria. Painel independente mantém preparo padrão.
- Release em staging, com entrega anterior preservada em `.previous-*`, falhas com exit code 1,
  nomes de saída confinados ao projeto e ZIP com `/`; formato escolhido pelo alvo Windows/Linux.
- Teste inicial do pacote extraído encontrou launcher obsoleto com panic `Option::unwrap()`.
  Launcher Windows recompilado do fonte recuperado, template instalado atualizado e hash do
  template antigo registrado para substituição apenas na entrega. Launchers personalizados e
  binários originais dos projetos existentes permanecem preservados.
- Validação: build `RangeEngine RangeRuntime` com vcvars64/VSLANG passou após um LNK1104 transitório
  no primeiro link; Cook, preset e opção de export executados no editor; sete testes Python de segurança e dois
  testes Rust passaram. Exportador instalado gerou ZIP, extraído em outra pasta, cujo launcher
  retornou 0 e cujo jogo gravou marcador de execução. Incluiu `blender.crt/` e `.cooked`.
- Pendente: jogo real, interação visual da GUI, Linux, outra GPU e
  migração dos runtimes de projetos antigos. GUI preservada; executáveis da engine não renomeados.
  `check_docs.py` continua apontando 30 erros/61 avisos anteriores nos mapas de código.

## 2026-10-08 — YoFrankie: fases cozidas e ReplaceMesh sem malha

- Medição no porte do YoFrankie (`D:\yofrankie`): o carregamento lento das fases era compilação de shaders
  (ex. `level_1_home`: 9,6 s com cache do driver frio, 1,1 s com ele quente, 0,2 s com o `.cooked`).
  Cook de todas as fases: minilevels 6–8 s → ~0,1 s, `level_underworld` 5,7 s → 0,19 s, seletor 2,1 s → 0,08 s.
  Sobra por fase ~0,3 s de conversão (tangentes ~0,2 s) e ~0,25 s de texturas.
- ReplaceMesh (`BL_ConvertActuators.cpp`): malha que nenhum objeto da cena usa agora é convertida na hora,
  como no Blender 2.4x. Actuator sem malha não avisa mais: os scripts do HUD a definem por nome
  (`actuator.mesh = ...`); o aviso aparecia 14 vezes em toda fase.

## 2026-10-07 — Arquivo cozido: pontos do Convex Hull em `.cooked`

- Medição por etapa (teste `tests/convert_flag/make_vs_libload.py`, que agora grava o `getLoadLog()` em
  `vs_results.txt`): LibLoad de 12 objetos 2336 ms = física 1604 ms (cada esfera Convex Hull de 130k
  triângulos ~210 ms no `btConvexHullComputer`), malhas 406 ms, 1º shader 317 ms; terreno Triangle Mesh
  ~13 ms. Tangentes e texturas 0.
- Novo `CcdCookedData` (Physics/Bullet): guarda os pontos do casco por hash dos vértices em
  `<arquivo principal>.cooked`, aberto/fechado pelo `BL_Converter`. Grava só quando o principal é `.blend`
  (jogar no editor); jogo exportado só lê. O hash ignora a ordem dos vértices: a mesma malha chegava em ordem
  diferente a cada objeto (8 esferas iguais davam 8 hashes).
- Export Game copia `<blend>.cooked` para `<jogo>.cooked` (ou apaga um antigo).
- Resultado (1 entrada de 464 KB): física 1661 → 41 ms; LibLoad 2388 → 763 ms; `convertObject` 2490 → 878
  ms; assíncrono 2770 → 967 ms. Mesmo sem arquivo, a 1ª rodada cai para ~1,2 s (as esferas iguais
  reaproveitam o casco). Jogo exportado conferido: física 40 ms no LibLoad.
- Botão **Cook** (`game.cook`, `bl_operators/anastacio_cook.py`) e **Clear Cooked** (`game.cook_clear`): painel
  "Cook" logo abaixo do Engine (Render) e os dois botões antes do Play no cabeçalho e na barra flutuante da 3D
  View. O Cook salva uma cópia temporária e abre o RangeRuntime com `ANASTACIO_COOK=<blend>.cooked`: converte
  todas as cenas e objetos (inclusive On Demand; só Editor Only fica fora) e sai antes do 1º frame, sem lógica.
  Testado com o `vs_convert.blend` (tudo On Demand): gerou a entrada do casco; runtime 5,4 s.
- Ícone novo `COOK` (panela) no espaço BLANK 42: `.dat` 16/32 do atlas embutido e PNGs de `icons_blender5` e
  `icons_upbge`.
- Shaders de material cozidos: `GPU_SHADER_FLAGS_BINARY_CACHE` (só no codegen; `RAS_Shader` religa o programa e
  fica fora) faz `gpu_shader.c` procurar o binário GL (`glProgramBinary`) pelos ganchos
  `GPU_shader_binary_cache_set`, ligados pelo `BL_Converter` ao `CcdCookedData` (registro tipo 2). Chave = hash
  de todos os trechos do código + flags + vendor/renderer/versão do driver; binário recusado pelo driver volta a
  compilar e é trocado. Shader do LibLoad 310 → 3 ms; com o Cook, LibLoad 2388 → 473 ms e `convertObject`
  2490 → 536 ms. Imagem conferida igual com e sem cache.
- Bug antigo achado pela chave instável: em `gpu_material.c`, sem sol no mundo (céu atmosférico e névoa), a
  direção/energia/tamanho do sol eram ponteiros para variáveis de bloco já encerrado quando o `GPU_link` lia —
  o shader recebia lixo (ex. `cons35 = vec3(2.2e38, ...)`), diferente a cada execução. Agora `static`.
- Cook não roda mais um passo de lógica: a cena inicial fica suspensa e o launcher desenha um frame (compila os
  shaders do desenho) e sai. Conferido com script que marca arquivo: não rodou. Cena sem Convex Hull agora gera
  `.cooked` (shaders), então o botão de limpar acende.
- `hash_bytes` do cache de normais/tangentes (`BL_BlenderDataConversion.cpp`) passa a ler 4 bytes por passo:
  hash 79 → 35 ms nos 12 objetos; LibLoad do teste 473 → 427 ms. Sobra a montagem dos buffers (~370 ms).
- Shaders no PC do jogador: o binário GL só vale na mesma GPU/driver, então o jogo exportado guarda os seus num
  cache do usuário (`%LOCALAPPDATA%\AnastacioEngine\ShaderCache\<jogo>-<hash do caminho>.shaders`; Linux
  `$XDG_CACHE_HOME` ou `~/.cache`), com cabeçalho `ANASHAD1` + chave da GPU/driver
  (`GPU_shader_binary_device_key`). O `.cooked` ao lado do jogo segue só leitura. Shaders novos durante o jogo
  entram no cache ao fechar.
- Aquecimento na primeira abertura (ou GPU/driver trocado): sem cache válido, `BL_SetShaderWarmUp` liga o mesmo
  modo do Cook (todas as cenas convertidas, cena inicial suspensa, um frame) e o launcher pede `RESTART_GAME`; o
  jogo volta já lendo o cache. Uma vez por arquivo e processo, e o cache é gravado mesmo vazio, para não reiniciar
  em loop. Teste exportado sem `.cooked`: 1ª abertura compilou (314 ms) e reiniciou; 2ª abertura 3 ms.
- Tela do aquecimento: `LA_Launcher` desenha fundo escuro e "Preparing shaders for this graphics card (first
  start only)..." (BLF, perfil compat) antes de converter. Conferido lendo os pixels (a captura do Windows não
  enxerga a janela GL). Launcher passa a incluir blenfont/glew com `GL_DEFINITIONS_RASTERIZER`.
- Testes do cache do usuário: chave de driver trocada no arquivo → aquece de novo; pasta impossível de gravar →
  aquece uma vez, avisa "could not write" e segue sem loop; shader de LibLoad no meio do jogo 310 ms → 3 ms na
  abertura seguinte. Aviso "compiling every shader" saiu do `CcdCookedData` para o `BL_Converter` (só quando
  aquece de fato).

## 2026-10-07 — Teste auditivo Web de Reverb Area com alternância de dois segundos

- Revisão a pedido do usuário: versão 0.1.1 troca pulsos por som contínuo em loop sem
  descontinuidade; gain 1, decay 10 s, reflections 3 e late gain 10. Mantém a limitação EFX.

- Novo gerador `tools/create_web_reverb_ab_scene.py`: Speaker 3D com WAV empacotado,
  pulsos idênticos e pausas, listener fixo e área CAVERN movida para dentro/fora a cada 2 s.
- `tools/web/reverb-ab-status.js` mostra o estado emitido pelo jogo;
  `tools/web/verify-reverb-ab.cjs` verifica logs, intervalo e saída AudioWorklet sem screenshots.
- Editor executou o gerador com exit 0; pacote usa o runtime release existente de 2026-10-04,
  sem recompilação. Edge passou seis estados (0–10 s), alternância ~2 s, effect 0/1 e gain 0,9
  na caverna; AudioWorklet running, 518144 frames, peak 0,12725. Não comprova reverb audível.
- Limitação confirmada no cache (`WITH_OPENAL=OFF`) e no header de compatibilidade:
  o backend SDL não oferece EFX. Estado Python ativo não significa aplicação de reverb no mixer.
  Usuário confirmou nenhuma diferença audível na versão contínua com reverb forte;
  pacote local em `build-web/dist/reverb-ab/`. Segunda execução: peak 0,12844, 518144 frames,
  seis estados PASS. Parser do verificador corrigido para aceitar tempo inicial -0.000.
- Suíte pura Web executada nesta sessão: 131 testes, todos OK (17,329 s).

## 2026-10-07 — Add Object carrega o objeto On Demand só quando dispara

- O atuador Add Object com alvo em Load Mode "On Demand" não converte nada na carga: guarda o nome e
  chama `BL_Converter::ConvertSceneObject` na primeira vez que adiciona (com os filhos). As vezes
  seguintes só replicam. Alvo "Editor Only" gera um aviso no console. Não é mais preciso deixar o
  atuador com o objeto vazio para evitar a carga antecipada.
- Nome vindo de propriedade: depois das camadas inativas e do External Files, procura um objeto
  On Demand da cena.
- O atuador mostra os botões With Scene / On Demand / Editor Only do objeto alvo (`logic_window.c`).
- Teste `tests/convert_flag/make_vs_libload.py`: mesmos 12 objetos por `convertObject` e por LibLoad.
  Tempo igual (~2,3 s), `convertObject` usa ~55 MB a menos; o LibLoad assíncrono não trava o frame.

## 2026-10-07 — Load Mode do objeto: com a cena, sob demanda ou só no editor

- Nova propriedade `Object.game_load_mode` (`SCENE` / `ON_DEMAND` / `EDITOR_ONLY`) sobre os bits
  `OB_TASK_CONVERT` e o novo `OB_TASK_EDITOR_ONLY` (bit 27 de `gameflag`, sem mudança de struct).
  `convert_object` continua valendo; ligá-lo tira o modo Editor Only.
- Editor Only nunca é convertido: `scene.convertObject()` e `setObjectConvert()` recusam o objeto, e filhos
  Editor Only ficam de fora quando o pai é convertido com `children=True`.
- `scene.unconvertedObjects`: nomes que `convertObject()` ainda pode criar (sem Editor Only nem malha liberada).
- `getLoadLog()`: o detalhe de "convert" traz "N left out (M editor only)".
- Outliner (motor de jogo): checkbox de Load with Scene à esquerda do olho; Editor Only aparece como fantasma.
- Painel "Loading" com os 3 modos e botões para os selecionados e filhos; textos traduzidos (pt_BR, es, ru).

## 2026-10-07 — Flag Convert vira "Load with Scene", com avisos no painel

- O rótulo da flag (`Object.convert_object`, bit `OB_TASK_CONVERT`) passa a ser "Load with Scene";
  o nome no Python e no arquivo não mudam. O tooltip cita `scene.convertObject()`.
- O painel "Game Object Tasks" virou "Loading" e vem aberto. Ele avisa os casos que antes falhavam
  em silêncio: objeto ligado sob um ancestral desligado (sai da carga do mesmo jeito), membro desligado
  de um grupo usado por um dupli group ligado, e malha compartilhada com objetos ligados
  (`freeUnconvertedData` não a libera). Com a flag desligada, mostra a chamada `scene.convertObject("nome")`
  e quantos filhos ficam de fora junto.
- Operador `object.game_load_with_scene` (botões "Load All" / "Leave Out All"): liga ou desliga a
  flag nos objetos selecionados e nos filhos deles, com undo.
- `BL_Converter::FindSceneObject` e `BL_Converter::IsChildOf` substituem as cópias que existiam em
  `BL_Converter.cpp` e `KX_PythonInit.cpp`. O teste de runtime de `tests/convert_flag/` sai igual.

## 2026-10-07 - Tesla Rhythm via Python Component

- Planejado e implementado `AnastacioTeslaRhythm`, anexado à câmera da nova
  `build/bin/demos/TeslaPiano/TeslaPiano_Rhythm.range`; fonte cinematic preservada.
- Cinco pistas A/S/D/F/G, 116 notas com acordes, música original sintetizada a 112 BPM,
  pontuação/combo/precisão, pausa, reinício, resultado e calibração de offset.
- WAV e mapa compartilham timestamps; áudio Audaspace é o relógio da descida e câmera.
  Sonda revelou oscilações pequenas na posição do backend; relógio tornado monotônico.
- Overlay post_draw preserva estado GL; câmera alterna lados frontais olhando ao Terminal,
  com fundo parentado à câmera. Controlador de piano anterior fica em estado inativo na variante.
- Núcleo passou fronteiras de julgamento, prevenção de duplicatas, perdas e mapa inteiro.
  RangeRuntime passou sonda com desenho real do HUD, relógio, julgamento, direção da câmera,
  pausa, resultado, reinício e limpeza. Evidência: `rhythm_probe_result.txt` na pasta da demo.
- `python tools/check_docs.py`: zero erros; 36 avisos de mapas existentes desatualizados.
  Aparência e latência percebida aguardam avaliação do usuário no jogo real.
- Contrato e fontes em [tesla-rhythm.md](tesla-rhythm.md).

## 2026-10-07 - Revalidacao das melhorias do Material Atlas

- Nova execucao em build/bin, sem alterar codigo: quatro casos modais passaram com exit 0
  (cancelamento inicial, cancelamento apos dois mapas, falha intermediaria e sucesso com Undo/Redo).
- Suite principal de pixels e persistencia, restauracao com save/reload e objeto compartilhado,
  integracao GI/atlas nas duas ordens e GPU AMD Radeon RX 6800M passaram com exit 0.
- Logs em debug-logs/material-atlas-{core,restore,integration}-retest.log e
  debug-logs/material-atlas-modal-*.log. Aparencia no jogo e Escape fisico seguem pendentes.

## 2026-10-07 - Cancelamento seguro do Material Atlas

- Interface passa a coordenar cinco jobs nativos do baker; Escape e a API
  material.anastacio_atlas_cancel solicitam parada. Main/mesh/nodes, validacao, packing e
  commit ficam na UI thread; a interface e operadores concorrentes de atlas ficam bloqueados.
- object_bake_api.c compartilha o inicio de job sem criar operador modal filho. Completion sink
  recebe FINISHED/CANCELLED na liberacao do job. Callback verifica G.is_break e stop do job;
  imagem parcial nao vira sucesso. ReportList privado evita leitura concorrente pela UI; report
  e callback do Render deixam de apontar para o job depois de liberar sua memoria.
- Rollback aguarda job finalizar/join antes de liberar IDs. Remove timer, restaura configuracao,
  selecao, malha e interface; commit so depois dos cinco mapas validados. Scripts/background
  permanecem sincronos; use_async=True habilita modo modal no editor com janela. Preparacao UV
  e validacao/packing continuam sincronos; nao prometer cancelamento instantaneo.
- Build RangeRuntime e depois RangeEngine, vcvars64 e VSLANG=1033: exit 0. Erro inicial C2664
  em RNA_def_property_flag corrigido com cast explicito de PropertyFlag, sem repetir cegamente.
- tools/run_material_atlas_modal_tests.py: quatro processos isolados com janela, todos exit 0.
  Cancelamento no inicio e apos dois mapas, erro Metallic fora de 0-1 e sucesso com pixels/packed
  maps/Undo/Redo automatico. Fonte/usuarios/UVs/selecao/settings preservados, sem IDs temporarios.
  A tecla fisica Escape nao foi validada: GHOST usa Raw Input e ignora PostMessage de teclado.
  Harness chama a mesma rotina nativa via API. Corrigidos Event.timer inexistente e quit dialog
  que mantinha o processo aberto; runner Python registra exit codes reais (PowerShell retornou null).
- Suites de pixels/rollback, GI nas duas ordens/GPU OpenCL e restore/save/reload passaram.
  Alguns encerramentos do harness modal avisaram 458 bytes nao liberados, origem nao determinada;
  caso final de sucesso encerrou com aviso de 64 bytes tambem visto antes desta mudanca.
  IDs de dados foram conferidos. Player final: exit 0 e ANASTACIO_ATLAS_RUNTIME_PASS.
  check_docs.py: 63 documentos, 0 erros e 36 avisos em mapas existentes; diff --check passou.

## 2026-10-07 - Restauracao explicita do Material Atlas

- Operador C++ material.anastacio_atlas_restore no painel Material Atlas. O commit do bake
  registra fonte e slot ativo com IDProperties da malha. Referencia ID sobrevive a renomeacao,
  duplicacao e salvar/reabrir; sem mudancas de DNA/headers.
- Restaura a malha fonte inteira e slots data-linked, preserva atlas com fake user e nao remove
  materiais/imagens compartilhados. Recusa modifiers, shape keys e slots object-linked.
  Atlas antigos nao recebem busca heuristica. Edicoes posteriores nao sao transferidas;
  GUI/report explicam rebake de GI quando a iluminacao foi feita depois do atlas.
- RangeRuntime compilou/linkou; RangeEngine terminou com exit 0 via vcvars64/VSLANG=1033.
  Teste --restore passou com fonte renomeada, reload, atlas compartilhado, recusa de modifier,
  slot ativo, UV fonte, packed maps e novo save/reload. Suite original de pixels/rollback passou.
  Player executou native_atlas_test.range, exit 0 e ANASTACIO_ATLAS_RUNTIME_PASS.
- Cancelamento permanece separado: object_bake_api.c bake_exec nao processa Escape em execucao
  sincrona. Exige jobs/controle de interrupcao; proxima peca aguardando revisao pelo workflow.
  Logs material-atlas-restore-{build,player-build,test,runtime}.log em debug-logs.

## 2026-10-07 — Física de malha de triângulos na conversão: metade do tempo

- A caixa local da forma (`btTriangleMeshShape::recalcLocalAabb`) varria todos os triângulos 6 vezes.
  `CreateBulletShape` agora calcula o mesmo mínimo/máximo numa passada pelos vértices dos triângulos e
  entrega pronto (`setPremadeAabb`), antes de cada forma, então vale também para `reinstancePhysicsMesh`.
- Durante a etapa de física do conversor (`CcdBeginBvhBatch`/`CcdEndBvhBatch`), o hash e a BVH de cada
  malha diferente ficam para o fim da etapa e rodam em todos os núcleos; cópias idênticas seguem
  dividindo uma BVH. Fila por thread, então o LibLoad assíncrono monta a sua. O hash agora lê 8 bytes
  por vez. `RANGE_NO_BVH_BATCH=1` volta à construção uma a uma, para comparar.
- 8 pilotos de ~327k triângulos: física 295 → 147 ms, load da cena 779 → 627 ms.
- Conferido com `tests/convert_flag/make_bvh_test.py` (malhas únicas, Shift+D, Alt+D com escala,
  LibLoad assíncrono e `reinstancePhysicsMesh`): 900 raios por grupo e 6 bolas caindo por 120 frames
  saem byte a byte iguais ao caminho original.

## 2026-10-07 — `scene.convertObject` e `bge.logic.freeUnconvertedData`

- `scene.convertObject(nome, children=True)` (`BL_Converter::ConvertSceneObject`): converte em runtime
  um objeto da própria cena deixado de fora pelo Convert, mais os filhos não convertidos. Usa a
  cena temporária de `FindOrConvertMainObject` com os layers da cena de origem: vai para `objects`
  se estiver num layer ativo, senão para `objectsInactive`. Objeto já convertido é devolvido como
  está. Pai já vivo na cena: o filho é convertido como raiz, religado com `SetParent` e posto sob
  um nó de `parentinv` com a relação da carga normal (normal, vértice, pai lento ou osso). Pai não convertido
  ou em layer ativo/inativo diferente: `ValueError`, como o load que descarta esse filho.
- Conferido no Play do editor (`make_editor_test.py` + `run_editor_test.py`, roda o player
  embutido e confere depois): os flags mudados por `setObjectConvert` voltam ao valor original e
  `freeUnconvertedData` dá `RuntimeError` sem tocar na malha.
- `bge.logic.freeUnconvertedData(scene)`: só no player standalone (`initPlayerPython` marca o Main
  como do jogo; no player embutido o Main é o do editor e a chamada dá `RuntimeError`). Libera a
  geometria (CustomData) das malhas cujos únicos usuários são objetos da cena com Convert
  desligado e não convertidos; `Mesh`, materiais e shape keys ficam. Depois disso
  `convertObject`, `setObjectConvert(..., True)` e `ConvertMeshSpecial` recusam esses dados.
  Teste de 8 pilotos, 2 convertidos: 37,5 MB liberados em 5 ms (a diferença para o `LibLoad`
  era ~45 MB). Testes: `tests/convert_flag/make_runtime_test.py` e `FREE_UNCONVERTED=1` em
  `make_test.py`.

## 2026-10-07 — Membros de dupli group respeitam o Convert

- `BL_ConvertBlenderObjects`: objetos de grupo com `convert_object` desligado não são mais
  convertidos ao instanciar o grupo (antes o flag só valia para objetos da cena). `DupliGroupRecurse`
  já ignora membros não convertidos. Teste: `tests/convert_flag/make_group_test.py`.

## 2026-10-07 — Conversão de malhas ~33% mais rápida, `getLoadLog` e armature sem pose

- `BL_ConvertDerivedMeshToArray`: a lista de vértices compartilhados (um `std::vector` por vértice
  da malha, uma alocação cada) virou cadeias num pool único (`BL_SharedVertexMap`), mesma ordem de
  busca; `RAS_DisplayArray::Reserve` pré-aloca vértices/índices por material. Vale para qualquer
  cena e para malhas de modifiers em runtime (`BL_ModifierDeformer`). Teste de 8 pilotos (~327k
  tris cada): etapa de malhas 595 → ~399 ms, load da Pista_1 ~976 → ~793 ms. Verificação
  temporária comparando busca nova x antiga: 0 diferenças em 2,46 M vértices (com e sem UV).
- `[Load] convert` detalha objetos, logic, mesh users, culling, bounds e malha (dm, normals, end).
  Nova `bge.logic.getLoadLog(clear=False)`: lista de dicts (scene, stage, ms, detail, total).
- `BL_ArmatureObject`: armature nunca avaliada (sem `pose`, ex. criada por script numa cena
  inativa) travava o player; a pose é construída com `BKE_pose_rebuild` antes da cópia.
- Medições (`tests/convert_flag/make_test.py`, opções `mat` e `arm`): material de nó com textura +
  Normal Map soma ~135 ms de tangentes (calculadas uma vez e copiadas para malhas iguais), shader
  1 compilado e 7 reutilizados; 20 armatures de 60 ossos com Action em layer inativo: ≤5 ms.
  Ainda dominam malha (~400 ms) e física triangle mesh (~345 ms). Build `RangeEngine RangeRuntime`.

## 2026-10-07 - Validacao adicional do Material Atlas

- `tools/test_material_atlas_integration.py`: GI -> atlas -> GI e atlas -> GI passaram com bake
  real de World, 256px/8 samples, sem denoise/light volume. Pixels finitos e iluminacao nao preta;
  atlas preserva pixels/UV de GI e rebake de GI preserva as cinco imagens/UV do atlas.
- GPU OpenCL AMD Radeon RX 6800M selecionada, CPU desabilitada nas preferencias: cinco passes
  e cores esperadas passaram; configuracao GPU preservada depois da operacao.
- Editor com janela: Undo/Redo restaurou dois materiais/UV fonte e depois material unico/cinco
  imagens packed. Script insere undo_push explicitamente; clique habitual permanece pendente.
  Primeira tentativa do harness perdeu contexto apos factory reset; corrigido preservando a janela.
  Ao encerrar, editor avisou um bloco nao liberado de 64 bytes; origem nao determinada.
- Pacote Web exportado por validate-web.py; preflight sem incompatibilidades. Edge 154.0.4258.62
  headless/WebGL 2 carregou cena, compilou shaders e emitiu ANASTACIO_ATLAS_RUNTIME_PASS.
  `tools/test_material_atlas_web.cjs` usa playwright-core e navegador instalado; nao captura telas.
- Logs em debug-logs/material-atlas-{integration,undo,web,web-runtime}.log. Nenhuma mudanca de
  producao nesta validacao; executaveis existentes usados. Linux sem binario atual disponivel;
  visual real, GI com denoise/volume e clique habitual de Undo seguem abertos.
- check_docs.py: 0 erros, 36 avisos de mapas existentes antes da atualizacao documental.

## 2026-10-07 — `bge.logic.setObjectConvert`: escolher objetos convertidos antes do load

- Novas funções `bge.logic.setObjectConvert(scene, object, convert, children=True)` e
  `getObjectConvert(scene, object)` em `KX_PythonInit.cpp`. Ligam/desligam o flag Convert
  (`OB_TASK_CONVERT`, painel Game Object Tasks) de um objeto e, por padrão, dos descendentes, numa
  cena ainda não carregada (busca inclui set scenes). Uso: no menu, desligar pilotos não escolhidos
  antes de `replace("Pista_1")`. `ValueError` se cena/objeto não existir; retorna quantos mudaram.
- Flags originais são guardados e restaurados em `exitGamePython()`, só para objetos ainda no
  `G.main`: no Play embutido as mudanças não vazam para o editor nem para o `.blend` salvo.
- Limites: só vale antes da conversão da cena; membros de dupli group ignoram o flag; logic bricks
  apontando para objeto desligado perdem o alvo; objeto ligado a várias cenas é afetado em todas;
  dados brutos do mesh continuam na RAM (economiza conversão: GPU, física, logic).
- Teste `tests/convert_flag/make_test.py` (8 pilotos pesados, 3 rodadas): load da Pista_1 com todos
  ~972 ms / 680 MB; com 2 via setObjectConvert ~356 ms / 466 MB; com 2 via LibLoad de arquivos
  separados ~377 ms / 421 MB. Custo dos flags ~0,05 ms. Build `RangeEngine RangeRuntime` passou.

## 2026-10-07 — Material Atlas nativo em C++ e correções de bake

- Nova ferramenta em Properties > Material > Anastacio Material Atlas. Operador C++
  `material.anastacio_atlas_bake`; painel padrão apenas invoca o operador, sem depender do addon.
  Um mesh ativo, materiais PBR opacos com Principled: Base Color, Roughness, Metallic, Specular e
  Normal, packed PNG 16 bits, UV AnastacioAtlas e material único. Malha fonte fica como backup;
  materiais fonte e demais objetos compartilhando a malha não são alterados.
- Reutiliza `ae_uvatlas` diretamente; triangulação real e detecção de UV conflitante por loop.
  Bake de cor/scalars por emissão evita iluminação duplicada e Base Color preto em materiais
  metálicos. Normal usa tangent space do atlas, preservando a UV fonte do Normal Map.
  Não aplica denoise de GI em mapas físicos; Lightmap e configuração de iluminação permanecem.
- `bake_api.c`: busca de UV nomeada corrigida de CD_MTFACE para CD_MLOOPUV; inicialização de
  primitivas inválidas acontece antes de retornar por UV ausente; stride da normal por polígono
  corrigido para poly * 3. A UV nomeada incorreta provocou crash reproduzido durante o teste.
- Execução prepara cópias, verifica os cinco passes/pixels, cria o material e só então aplica.
  Restaura render, samples/device e seleção; falha no pack libera temporários. Node tree final é
  embedded ID do material. Stubs de progresso adicionados ao player para permitir link do editor
  compartilhado, sem UI de bake no standalone.
- `ninja RangeEngine RangeRuntime` com vcvars64 e VSLANG=1033 passou; instalação em build/bin.
  No rebuild final, player e editor foram construídos em chamadas separadas, nessa ordem:
  a chamada conjunta apresentou LNK1104 no player e a instalação do editor tentou ler o EXE ausente.
  `ninja RangeRuntime` e depois `ninja RangeEngine` passaram sem alterar flags de compilação.
  `tools/test_material_atlas.py` passou: seis materiais, metal total, gradiente na UV fonte, normal
  inclinada reconstruída na UV de atlas, source/Lightmap preservadas, mesh compartilhado,
  rejeição de transmissão, rollback de pack degenerado, proteção contra rebake e save/reload.
  Também valida UV fonte ausente e rollback após passes executados com valores fora de 0–1;
  o formato PNG não pode cortar silenciosamente mapas HDR/dados inválidos.
  RangeRuntime carregou a cena, compilou shaders e confirmou material único, encerrando com código 0.
- Limites e pendências no [plano](material-atlas-plan.md): materiais legados, vários objetos,
  transparência, modifiers/shape keys e grafos mais amplos não entram nesta primeira peça.
  Visual no jogo real, Undo na interface, GPU e Web/Linux ainda pendentes.
- Check documental padrão encontrou arquivos rastreados removidos por outra tarefa (ex.
  `docs/parallel-work-plan.md`); execução do mesmo verificador filtrando arquivos ausentes passou
  com 0 erros e 35 avisos de mapas existentes. Nenhum arquivo removido foi restaurado.

## 2026-10-07 — pesquisa e preparação do atlas de materiais

- Complemento: auditoria do Baked Lighting atual, matriz de reutilização de UV/xatlas, bake Cycles, GPU, padding e progresso; contrato de coexistência Lightmap + AnastacioAtlas. Na etapa de preparação somente documentação foi alterada.

- Auditoria estática do `automate_atlas_bake.py` 1.3: gera mapas, mas não cria material final; falhas de passe podem terminar em FINISHED; UVs, materiais e imagens requerem proteção.
- Pesquisa de Material Combiner, Bake Groups, BakeToSingleMaterial e Auto-Bake, com versões/API e licenças observadas. Recomendação: evolução própria e reutilização das capacidades locais de UV/bake.
- [Plano](material-atlas-plan.md) registra contrato, etapas, limites, matriz de validação e fontes. A implementação foi autorizada posteriormente e registrada em entrada separada.

## Texture Paint: traços Line e Curve voltam a pintar (2026-10-07)

- `paint_image.c`: a checagem "mouse sobre face do objeto ativo" (`fff04797`) lê o backbuf de seleção a cada
  pincelada. Line e Curve geram as pinceladas de uma vez, sem redesenho; depois da primeira o backbuf devolve
  as cores da viewport (índices como 466210 numa malha de 6 faces) e o traço inteiro era descartado. Esses
  traços agora pulam a checagem (`texture_paint_brush_is_batched`); o traço livre continua com ela.
- Dicas do rodapé: modo Curve mostra os atalhos da curva (Ctrl LMB ponto, Enter pinta); Line diz
  `Drag + release`.
- Validado: curva por script altera os pixels; usuário confirmou pintura com Line e Curve.
- Em aberto: crash por corrupção de heap (`0xc0000374`) visto em 06/10 e 07/10 pintando, sem reprodução.

## Editor: dicas de atalho nos modos de pintura e sculpt (2026-10-07)

- `view3d_draw.c`: faixa no rodapé da 3D View, alinhada à esquerda e acima da barra flutuante Play/Standalone,
  com tecla + ação para Texture Paint, Sculpt, Vertex Paint e Weight Paint (tirado dos keymaps de
  `paint_ops.c`). Contextual: traço Line mostra `Drag Draw line · Alt Snap angle`; Fill com degradê mostra
  `Drag Gradient direction`. Quebra em linhas quando a viewport é estreita. O BLF desliga `GL_BLEND` a cada
  texto, por isso o blend é religado antes de cada moldura.
- Textos em inglês via `IFACE_`/`N_`, traduzíveis por Preferences > International Fonts.
- Liga/desliga: `UserDef.uiflag2` `USER_HIDE_PAINT_HINTS` (negativa, prefs antigas mostram as dicas), RNA
  `show_paint_hints`, em Preferences > Interface e no menu de botão direito do cabeçalho da 3D View
  (`screen_ops.c`). Nada novo no .blend da cena.
- `properties_paint_common.py`: topo do painel do pincel com `Free | Line | Curve` (`stroke_method`) e
  `Solid | Gradient` (`use_gradient`); o checkbox de degradê do fim do painel saiu.
- Build `RangeEngine` OK; screenshot validado em Texture Paint e Sculpt. Botões do painel ainda sem teste manual.

## Viewport: overlays restantes no estilo Blender 5 (2026-10-07)

Linhas com `GL_LINE_SMOOTH` + blend (desligado no picking, estado de blend do chamador restaurado),
larguras e pontos escalados por `U.pixelsize`, pontos redondos (`GL_POINT_SMOOTH`).
- `view3d_draw.c`: cursor 3D com anel de 8 traços vermelho/branco, halo escuro e cruz com vão; eixo Z do
  grid fino e suave; nome da vista e info do canto com sombra (novo `BLF_shadow_default` em `blf.c`).
- `drawobject.c`: origem do objeto quase opaca com borda escura; wire de curva/texto/superfície/metaball;
  edição de curvas (alças, splines, pontos); lattice; normais e marcas seam/sharp/crease/bevel do Edit Mode;
  bounds, colisão, rigid body e texture space; moldura do empty de imagem; particle edit.
- Transform: linhas de restrição, círculo proporcional, snap e helplines suaves; snap ativo vira anel com
  halo e ponto central. Knife suave e com pontos redondos. Motion paths suaves com pontos redondos.
- Anel do pincel: 96 segmentos, 1,5 px, halo escuro; no Sculpt alpha 0,8.
- Sem mudança: ruler e gestos de seleção (já seguiam o padrão), desenho de partículas fora do particle edit.
- Build `RangeEngine` OK; validação visual pendente.

## Viewport: bones e cursor de pintura no estilo Blender 5 (2026-10-07)

- Referência: fonte do Blender 5.0 em `D:\blender5-ref` (sparse: `sculpt_paint`, `uvedit`, `blenkernel`,
  `geometry`, `draw/engines/overlay`). Só overlays; shading dos meshes e formato do .blend inalterados.
- Bones (`drawarmature.c`): sólidos sem luz GL, com a mistura de 2 tons do
  `overlay_armature_shape_solid_vert.glsl` (luz `(0.1, 0.1, 0.8)` em view space, tom escuro = 35% da cor) em
  Octahedral, B-Bone (caixas) e Envelope (esfera/cilindro próprios no lugar do GLU). No Object Mode, arestas
  finas suaves na cor de wire do objeto (laranja quando selecionado); a primeira tentativa, um contorno escuro
  grosso por silhueta, foi rejeitada pelo usuário. Wire e Stick com linha suave, 2 px no bone selecionado.
  Seleção por clique (`G_PICKSEL`) continua com o desenho antigo.
- Axes dos bones (`drawaxes_colored` em `drawobject.c`): X/Y/Z em vermelho/verde/azul misturados com a cor do
  texto (0.1 selecionado, 0.65 não selecionado), letras mais claras, linhas suaves. Empties sem mudança.
- Cursor do pincel (`paint_cursor.c`): fora do Sculpt, cinza 0.75 com alpha 0.9 como os brushes essentials do
  5.2; só substitui o vermelho padrão, então uma cor de cursor customizada salva no arquivo é mantida.
- Texture Paint em plano grande perto da câmera: o Blender 5.0 tem o mesmo descarte do triângulo inteiro
  quando um vértice fica antes do near clip (`project_paint_flt_max_cull`, com `TODO`); não há correção para
  portar, e o teste de bucket da engine já é mais completo (aresta `v3-v1`).

## Multiplayer: correções da revisão Steam, retorno à sala e adaptadores (2026-10-07)

- ImGui Python: `push_style_var`/`pop_style_var` com constantes `STYLE_*` e
  `load_default_font(size)`, fonte da engine com ícones ForkAwesome em outro tamanho. O atlas
  fica travado durante o frame, então o tamanho é montado no `NextFrame` seguinte (retorna
  `None` até lá). Menu `AnastacioNetworkComponent` redesenhado (16 px, tema, ícones); capturas
  de configuração, sala e espera conferidas no player.
- Testes de plataforma da rede (local, 2026-10-07): Linux (WSL Ubuntu, GCC 15) build isolado com
  121/121 gtests, incluindo o plugin ABI via `.so`; wasm (emsdk local) 60/60 no filtro do CI, golden
  incluídos (rodar no node Linux: com `NODERAWFS` no Windows o gtest aborta sem cwd, e o caminho
  `D:/…` do golden precisa de um link `D:` → `/mnt/d` na pasta atual). Interoperabilidade:
  `net_echo` cliente Linux→servidor Windows (ENet) e Windows/wasm→servidor Linux (ENet e
  WebSocket), 3/3 ecos. Navegador: `RangeRuntime --server` no Windows + `net_web_watch` no Chrome
  headless (`--enable-logging=stderr`, sem playwright): `NETWEB PASS spawns=1 snapshots=40`,
  servidor `NETTEST server PASS`. Falta o RangeRuntime completo no Linux e o player web da engine.
- ImGui Python: `push_item_width`/`pop_item_width`/`set_next_item_width`; campos, slider e chat
  do menu de rede agora ocupam a largura do conteúdo. `load_font` não mexe mais no atlas no meio
  do frame: valida o arquivo, enfileira e devolve o id definitivo (fila única com
  `load_default_font`, montada em ordem no `NextFrame`); `push_font` com id ainda na fila usa a
  fonte atual, mantendo push/pop balanceados.
- Revisão final: sair da sala preserva convites não lidos; "Iniciar partida" some durante a
  partida; o controlador guarda a cena da sessão ao hospedar (`lobby_scene`). No RolimaRacer,
  o botão de resultado online faz o host chamar `return_to_lobby` (cliente aguarda) e `on_lobby`
  limpa HUD/resultado e reabre `_network_menu`. Só checagem de sintaxe; falta teste no jogo real.
- Complemento Windows lê `+connect_lobby` dos argumentos reais do processo, com tokens
  completos, validação de ID e suporte a caminhos com espaços. Mantido fallback da API Steam.
  Player externo aceita argumento de convite após o arquivo, sem tratá-lo como filename.
- Cancelamento e timeout retiram CCallResults, zeram pending e permitem nova operação.
  Handles tardios de create/join são recolhidos separadamente para deixar salas abandonadas;
  acompanhamento limitado a 64 operações. Teste SDK passou cancelar e recriar sem espera.
- Eventos de desconexão não são descartados; novas conexões são limitadas quando a fila
  acumula. Snapshot/Input descartam mensagens antigas por número da lane. ReplicaClient
  já descartava snapshots antigos por tick e InputQueue já descartava inputs consumidos.
  Membro cuja lista local ainda não atualizou aguarda até 3 segundos, com limite de conexões.
- `Range.network.return_to_lobby()`/`on_lobby` resetam partida/prontidão e notificam clientes.
  Controlador reabre Steam; retorno com nome de cena espera seu carregamento no host.
  Componente tem show/hide/return_to_lobby e reaparece ao voltar; show explícito funciona
  durante a partida. Convite em sessão pede confirmação, chat usa nomes, LAN mostra IPv4
  locais/porta, nome só é escrito ao editar e capacidade usa slider 2..64.
- Agente solicitado pelo usuário corrigiu adaptadores RolimaRacer: início delegado uma vez
  ao NetworkManager, responsável persistente pelo tick no SteamComponent e fallback no menu,
  enable_steam=False evita init e seleção de pista/carro fica com host. Pacote instalado
  foi adicionado ao ignore do jogo. Assets/veículos não alterados nem mudanças commitadas.
- Builds MSVC do complemento/editor/player e CTests passaram. Teste determinístico do
  complemento cobre argv, cancelamento/timeout, fila e sequenciamento; teste dos adaptadores
  simula on_start atrasado e confirma início único, tick, convite e chat. Dois players ENet
  passaram duas partidas, retorno/reset e reentrada; regressão spawner passou.
- SDK socket pair passou canais/handshake/replicação; menu Steam passou retorno, busca
  pública após propagação de metadados e segunda partida. Primeiro teste de busca consultou
  antes da publicação; aguardada propagação e PASS. Cena mínima de adaptadores passou
  pista → menu: corrigido o teste para resolver o componente vivo após a troca, em vez de
  conservar proxy destruído. Exportado Steam passou convite argv entregue ao componente
  e menu real; exportado LAN passou sem DLL Steam. Teste de lobby de baixo nível não pode
  competir com o componente pela mesma fila; prova de convite exportado usa o controlador.
- Exportador foi conferido contra distribution-0.1.md: RangeRuntime como player, Python
  completo e blender.crt são requisitos do pacote testado, já registrados na entrada anterior.
  Nenhum release publicado. Convites reais entre contas, relay externo, condição de ordem
  dos membros e corrida/carros reais continuam pendentes; argv com ID fictício não os prova.

## Multiplayer: transporte Steam, salas, componente e exportação nativa (2026-10-07)

- ABI C v2 do complemento, adaptador ITransport em Network e seleção `transport='steam'`
  em host/join. Control/Rpc confiáveis em lanes separadas; Snapshot/Input não confiáveis;
  envelope versionado preserva payload/protocolo nativo. Unload bloqueado com transportes vivos.
- Complemento SDK: P2P, poll groups, limites de payload/orçamento, identificação de peers,
  consulta de rota e desativação de ICE direto para prova de relay; callbacks compartilhados.
  Salas públicas/amigos, filtros jogo/build/protocolo, convites, cancelamento/tardios,
  host saindo e acesso por membros quando há lobby. Sem migração automática de host.
- Componente e estado reutilizáveis em `release/scripts/modules/anastacio_network/`, com menu
  ImGui LAN/Steam, pronto/chat/iniciar/sair. Player adiciona scripts/modules; editor purga
  helpers com Range temporário, inclusive quando importados por adaptadores de jogo.
- RolimaRacer: net_menu virou adaptador da engine, configuração em network_settings;
  SteamComponent compartilha init/callbacks e idioma/conquistas; NetworkManager coordena
  sala/saída e pista. RPC de pista não chama change_scene no cliente (SceneChange é do host).
  Assets `.range` e veículos originais preservados. Scripts anteriores do menu/Steam guardados
  localmente em build-steam/game-script-backup antes da alteração.
- Exportador legado: módulo reutilizável incluído mesmo sem Copy Scripts, seleção opcional de
  pasta Steam, Python completo e blender.crt, player RangeRuntime e perf_counter. Instalador
  explícito para outros exports nativos. AppID dev só entra com opção explícita; nada publicado.
- MSVC: complemento, RangeEngine/RangeRuntime, CTest rede PASS. SDK socket pair passou quatro
  canais nos limites 1200/65536, handshake, chat, transform/propriedade, spawn/despawn/ownership.
  Primeiro probe de spawn não inseria objeto no IWorld do teste; corrigido o fixture e PASS.
- Steam online numa conta: criar/listar sala pública com filtros, metadados, cancelamento,
  host nativo e unload guard PASS. Componente com ImGui no player PASS. Cópias dos adaptadores
  RolimaRacer em cena mínima passaram init compartilhado e transição para Pista_1.
- Regressão LAN spawner em dois players PASS (movimento, propriedade, spawn, pronto/chat/início
  e descoberta). Exports Steam/LAN executados e players passaram; LAN sem DLL Steam.
  ZIP local extraído para build-steam/export-extracted: Game.exe passou com sala real e componente.
- Pendentes: relay real entre duas redes/contas, convites aberto/fechado, corrida/carros reais,
  AppID comercial/conquistas, review da distribuição pública e Linux. Testes locais não são
  evidência desses itens. [Procedimentos](steam-complement-development.md).

## Multiplayer: inicialização Steam online validada, B2 (2026-10-07)

- Steam iniciada localmente; smoke test no RangeRuntime headless com AppID 480 e conta
  conectada confirmou inicialização SDK, identidade, callbacks e shutdown/reinit.
- `STEAMTEST real SDK online PASS` e `STEAMTEST PASS`; contexto de prova final permaneceu
  ativo até StopEngine, que o encerrou corretamente. Log local em build-steam/online-runtime-test.log.
- B2 encerrado para Windows/AppID de desenvolvimento. Transporte, salas, migração de
  conquistas/idioma e validação com AppID comercial continuam pendentes; jogo não foi alterado.

## Multiplayer: inicialização opcional Steam, B2 offline (2026-10-07)

- Novo projeto separado `source/complements/anastacio_steam/`: SDK local, DLL opcional,
  validação do AppID de lançamento, cliente/conta e dono existente; sem relançar editor.
- Serviço por processo em Network, API Python initialize/status/shutdown e bombeamento no
  NextFrame; StopEngine libera após destruir componentes. Nenhum script do RolimaRacer alterado.
- Builds Windows/MSVC de complemento, RangeEngine e RangeRuntime passaram. CTest da rede PASS.
  Smoke test no player headless: API, uint64, callbacks, duplicação e limpeza PASS; DLL real
  carregou e reportou `Steam client is not running`. Init online não validado, Steam fechada.
- Diagnóstico do erro Windows 126: dependência CRT inicial removida com CRT estático;
  a falha persistiu até normalizar separadores de caminho para busca DLL_LOAD_DIR. Provas
  isoladas WinDLL com caminho nativo carregaram; reteste no player passou depois do fix.
- [Guia local](steam-complement-development.md) e script `tools/net_engine_test/steam_runtime_test.py`.
  SDK mantém warnings C4996 nos próprios headers. Sem export/release, transporte ou salas.

## Multiplayer: carregador opcional do complemento, B1 (2026-10-07)

- ABI C v1 e carregador RAII em Network, sem SDK Steam: caminho absoluto, busca Windows
  restrita ao diretório da DLL/System32, validação de tabela e limpeza de contexto/biblioteca.
- Quatro DLLs de prova testam ciclo de vida, identidade uint64, falha/retry de init,
  recarga, versões/tamanhos incompatíveis e ponteiro ausente. Não são complemento Steam real.
- Builds MSVC `build-net/net_tests` e `build/ge_network` passaram. CTest da rede passou.
  Sem API Python ou ligação do serviço ao runtime; próximos passos na etapa B2.

## Multiplayer: inventário inicial do complemento Steam (2026-10-07)

- Consulta bpy no RolimaRacer.range pelo editor de build/bin, sem salvar: SteamComponent,
  NetworkManager, NetworkMenu e quatro NetworkVehicleSync confirmados; processo saiu com c?digo 0.
- SDK 1.55 local encontrado, incluindo lanes; AppID de desenvolvimento ? 480, comercial pendente.
- [Decis?o proposta](steam-multiplayer-inventory.md): pacote reutiliz?vel da engine, complemento
  opcional por ABI C, ?nico dono do runtime e canais compat?veis com a sess?o atual.
- Pr?xima pe?a isolada: carregador e DLL de prova antes da integra??o SDK. N?o houve mudan?a C++
  nem gameplay; exportador efetivo e distribui??o do complemento ainda precisam ser fechados.

## Multiplayer: plano do complemento Steam (2026-10-07)

- Criado [plano do complemento Steam](steam-multiplayer-plan.md), com salas/convites Steamworks e
  adaptador opcional para o transporte da rede nativa. Componente e menu reutilizáveis devem ser
  distribuídos pela engine; RolimaRacer mantém configuração e regras da corrida.
- Etapas incluem inicialização única, contrato de canais/identidade, prova de relay em duas redes,
  integração de sessão, corrida real e distribuição. Não implementado; nenhum C++ ou jogo alterado.
- Fontes oficiais Steamworks consultadas; SDK/AppID e forma de distribuição precisam ser conferidos
  no inventário inicial. Engine padrão continua independente da biblioteca Steam.

## Sombra: atualização automática para Spot/Point (2026-10-07)

- Nova opção por lâmpada **Auto Update** (Spot/Point, painel de sombra; `LA_AUTO_SHADOW`, RNA
  `use_auto_shadow_update`, Python `light.autoShadowUpdate`), desligada por padrão. Com ela, a sombra só é
  redesenhada quando a lâmpada (transform, distância, cone, clip, bias, layer) ou algum objeto dentro da distância
  dela mudou, entrou ou saiu; objetos com deformador (armature/shape keys) contam sempre como movidos.
  Comparação no snapshot de bounds das passadas de sombra (`KX_Scene::GetShadowCullSnapshot`) em
  `KX_ShadowRenderer.cpp` (`AutoShadowStillValid`); `updateShadow()` e mudança na lista de casters forçam
  o redesenho. Limitação: movimento só por shader de vértice (vento/grama) não é detectado; deixe Auto desligado
  nessas lâmpadas. Etapa 1 do plano de otimização de luzes (etapas 2-3 sem GLSL; 4-5 dependem dos shaders).
- Teste `tools/create_auto_shadow_test.py` (`projects-teste/auto_shadow/`): 8 Points com sombra, 441 cubos,
  um cubo girando perto de 2 lâmpadas. Auto desligado: 48 passadas/8 lâmpadas por frame; ligado: 12/2.
  FPS travado em 60 nos dois (RX 6800M), então o ganho de tempo ainda não foi medido; falta a checagem visual
  do usuário (sombra acompanhando o cubo, sem sombra congelada).

## Demos de nós: cópias revisadas com frames e controles robustos (2026-10-07)

- Revisadas as 11 receitas da lista do usuário, com cópias `_revisado.range` em
  [`demos/revisados/`](../demos/revisados/README.md). Originais `.range` e geradores preservados.
  `tools/review_recipe_nodes.py` abre os assets existentes e organiza materiais, World, lâmpadas e
  grupos em frames por etapa, com notas separadas e colunas por dependência. Parentes são atribuídos
  antes das posições, evitando deslocamentos relativos da API 2.79; nós altos têm espaço reservado.
- Dissolve: extremos exatos (q <= 0 inteiro, q >= 1 invisível), brasa limitada à parte visível e
  largura única ligada à faixa e ao gradiente. Neve/musgo: extremos exatos de Amount, independentemente
  de ruído/suavidade; ruído em Object acompanha o objeto, normal do mundo mantém orientação da cobertura.
- Água: espuma acompanha Bump das ondas; materiais da costa usam Geometry Position para a altura do
  mundo. Triplanar: Bump discreto pela luminância (aproximação desligável por Strength = 0).
  Interior Mapping: dimensões limitadas a 0.001 nos divisores; limites nas entradas do grupo.
  Escudo, lava e shaders de vértice de vento/grama/pelos mantêm a lógica original; frames indicam
  o texto GLSL correspondente. Nenhuma mudança em C++ ou no build.
- Toon: a primeira rodada do player avisou que o material de contorno não tinha vértices/primitivas.
  O casco Solidify ainda estava no modificador, mas o conversor usa a malha base (`CDDM_from_mesh`).
  Aplicado somente o modificador Contorno na cópia, preservando espessura, normais invertidas e slot
  de material; o gerador verifica que as faces do contorno existem. As faixas de iluminação não mudam.
- `python tools/validate_recipe_nodes.py`: **11/11 PASS** no player atual de `build/bin/` (RX 6800M),
  cada cópia temporária executando 120 ticks de lógica e encerrando, sem erros de shader/Python detectados.
  Testes percorrem conexões Math reais para os extremos, verificam limites dos frames e comprovam por
  SHA-256 a preservação dos originais. Os assets entregues não encerram automaticamente; logs e cópias
  de teste ficam em TEMP. A primeira execução do gerador expôs uma falha no avaliador de testes
  (override de quantidade no nó Math de Time); corrigido antes da validação completa.
- Validação visual da qualidade dos efeitos e do layout permanece para o usuário no editor/jogo real;
  não foi usada captura automatizada. `check_docs.py` antes da atualização: 54 erros/4 avisos já existentes
  nos mapas/referências, relacionados a linhas de código fora desta revisão.

## Tesla Piano: acentos de partículas GPU (2026-10-07)

- `tools/add_tesla_gpu_effects.py` adiciona 11 emissores nativos, com pool total de 348 partículas:
  oito Sparkle azulados nos toros (32 cada), carga sutil na bola central (20) e dois Smoke baixos
  nas laterais (36 cada). Sem texturas externas, shaders novos ou alterações em C++.
- Controlador musical aciona o emissor correspondente por 0.45 s; espaço aciona todos por 0.75 s.
  A opacidade cai nos últimos 0.2 s antes de desligar. Névoa e carga central são ambientes contínuos.
- Atualizada `TeslaPiano_Cinematic.range`, preservando backup `TeslaPiano_Cinematic_before_gpu_effects.range`.
  Sonda no runtime passou: acionamentos reais de nota/espaço, emissores ativos, redução temporizada
  e desligamento (`debug-logs/tesla-gpu-result.txt`). `check_docs.py`: mesmos 35 erros/23 avisos anteriores.
  Aparência e desempenho precisam ser avaliados pelo usuário no jogo real.

## Tesla Piano: UV do fundo e tremor reduzido (2026-10-07)

- Fundo preto diagnosticado na cena salva: plano `Anastacio_Fundo_Industrial` sem qualquer UV.
  A cena já usava Game PBR, no qual Image Texture/Emission são suportados. Corrigido com UV
  completo 0..1 e nó UV Map ligado explicitamente à imagem; textura convencional adicional
  disponível para fallback legado. A autoria usa `uv_textures.new` da API 2.79.
- Amplitude do tremor 0.045 → 0.012, frequência 18 → 14 Hz, decay 0.65 → 0.85/s, roll desligado;
  impulso por nota 0.24 → 0.18 e espaço 1 → 0.85. Fator do blur associado 0.75 → 0.35.
- `tools/fix_tesla_background_shake.py` atualiza a cena com backup separado; corrigida também a
  criação de UV em `tools/upgrade_tesla_atmosphere.py`. Gravação e verificações de UV/nós/amplitude
  bem-sucedidas no editor. Validação visual do fundo deve ser feita pelo usuário no jogo real.

## Tesla Piano: foco central e Camera FX (2026-10-07)

- `tools/configure_tesla_camera_fx.py` configura a câmera de `TeslaPiano_Cinematic.range`
  com foco Object no `Terminal` (bola central), faixa nítida de 8 m, suavização de 0.2 s,
  DOF Medium com blur de 3.5 px e diafragma de seis lâminas.
- Speed Blur e Directional Blur ligados com forças moderadas e Protect Focus; Cat Eye Bokeh
  suave e vinheta de 0.12. O Speed Blur acompanha trauma² via `speedOverride`, pois o tremor
  por lens shift não translada a câmera. Sem trauma, o override volta a zero.
- Cena atualizada com backup `TeslaPiano_Cinematic_before_camera_fx.range`. Sonda separada
  no runtime confirmou foco válido no Terminal, efeitos ligados, blur seguindo o impacto
  e voltando a zero, além da inicialização musical (`debug-logs/tesla-focus-result.txt`: PASS).
  Avaliação visual permanece no jogo real pelo usuário.

## Tesla Piano: tremor musical e fundo industrial (2026-10-07)

- `tools/upgrade_tesla_atmosphere.py` aplica o tremor existente de `KX_Camera` ao controlador
  musical: cada nota chama `shake(0.24)` e espaço chama `shake(1.0)`. O trauma nativo acumula,
  limita em 1 e decai a 0.65/s; amplitude 0.045, frequência 18 Hz e roll ligado no Camera Game FX.
- Gerada paisagem industrial noturna com imagegen integrado, salva em
  `build/bin/demos/TeslaPiano/textures/tesla_background.png` e empacotada na cena. Plano de fundo
  emissivo, alinhado à câmera, sem colisão e com margem para tremor.
- Entrega em `build/bin/demos/TeslaPiano/TeslaPiano_Cinematic.range`, preservando as versões
  original e PBR. Execução no editor e teste no runtime bem-sucedidos; sonda separada confirmou
  inicialização do piano, impulso isolado, acumulação rápida, redução até zero e impacto forte.
  Resultado em `debug-logs/tesla-shake-result.txt`. Aparência/enquadramento e sensação do tremor
  aguardam avaliação do usuário no jogo real; nenhuma captura automática usada como prova visual.

## Tesla Piano: materiais procedurais PBR (2026-10-07)

- `tools/upgrade_tesla_materials.py` transforma uma cena existente sem recriar sua lógica e grava
  uma cópia irmã `TeslaPiano_PBR.range`. Aplicado a 35 objetos da demo em `build/bin/demos/TeslaPiano/`.
- Nós editáveis: cobre com espiras horizontais, aço com microtextura, bases grafite, concreto com
  variação de cor/relevo e máscara procedural de rugosidade molhada, terminal e teclas emissivos.
  Game Shading Nodes ligado; luz Hemi convertida em Sun, compatível com Game PBR.
- Build `RangeEngine` bem-sucedido com `vcvars64.bat` e `VSLANG=1033`; execução do script e gravação
  bem-sucedidas. Runtime manteve-se aberto no teste de inicialização; validação visual e musical
  no jogo real pendente. A geometria/cenário da referência artística não foi recriada.
- `check_docs.py` encontra 35 erros e 23 avisos preexistentes, sobretudo linhas dos mapas de código
  alteradas por trabalho paralelo; nenhum mapa foi reescrito nesta tarefa.

## Chuva: poças d'água (2026-10-07)

- Weather > Rain > Puddles (`WO_WEATHER_RAIN_PUDDLES`, bit 11). Campos novos no DNA: `rain_puddle_amount`,
  `_size`, `_darkness`, `_reflection`, `_distance`, `_min_up` (versioning dá os padrões 0.5/4/0.4/0.8/40/0.9).
- No filtro de chuva (jogo e viewport): ruído em XY do mundo nas superfícies viradas para cima; borda
  molhada escura, água refletindo a cor horizonte/zênite do World com fresnel, e a normal dos Ripples
  distorce o reflexo. Profundidade/normal agora calculadas uma vez para poças e ripples.
- Game property `puddles_effect` com a mesma regra dos outros efeitos (bit 4 de `KX_RainSurfaceMask`).
- Com Intensity 0 o filtro continua desenhando as poças (secam pelo Amount). `setWeather`: `puddles`,
  `puddle_amount`, `puddle_size`, `puddle_darkness`, `puddle_reflection`, `puddle_distance`, `puddle_min_up`.
- Ripples + Puddles: o fresnel usa a água plana e a refração dos ripples dentro da poça foi reduzida,
  para os anéis não ficarem azuis demais.
- Screen Space Reflection opcional (`WO_WEATHER_RAIN_PUDDLE_SSR`, bit 12; `setWeather('puddle_ssr')`): 32 passos
  em world space contra o depth, refino por bisseção, cai no céu onde o raio sai da tela ou passa atrás de objeto.
- Only in Puddles em Ripples (bit 13) e Splash (bit 14), `ripple_puddle_only`/`splash_puddle_only`: o efeito só
  aparece na água da poça e liga o Puddles junto. As duas podem ficar ligadas: vão em `Puddle1.x = 1 + 1 + 2`.
- Revisão: `fwidth` da borda das poças saiu de dentro do branch por pixel (derivada indefinida em fluxo
  não uniforme) e `setWeather('puddle_ssr')` ganhou o setter que faltava.

## Chuva: Ripples/Splash/Aura por propriedade, ajustes iguais e raios laterais (2026-10-07)

- UI do Weather > Rain: checkbox Droplets no topo; Ripples e Splash com a mesma lista e ordem
  (Intensity, Size, Rate, Normal, Distance, Upward Surface). Campos novos no DNA: `rain_ripple_size`,
  `rain_ripple_rate`, `rain_splash_normal`, `rain_splash_min_up` (antes fixos no shader: 1, 0.8, 1, 0.7);
  viewport e engine usam os mesmos valores.
- Game properties `ripples_effect`/`splash_effect`: se algum objeto tiver, só ele recebe o efeito; sem
  nenhum, continua em toda superfície. `KX_RainSurfaceMask` desenha os objetos marcados numa textura RG32F
  (bits + profundidade de vista) e o filtro de chuva compara com a profundidade da cena. Não segue
  armature/shape key. Só no jogo (a viewport mostra em tudo).
- Aura: propriedade padrão `aura_chuva` → `aura_rain_effect` (versioning renomeia no World e nos objetos);
  sem objeto marcado, todo objeto com malha dentro de Distance recebe a aura.
- Lightning > Sideways Bolts (`WO_WEATHER_RAIN_LIGHTNING_SIDE`): metade dos raios corre na horizontal
  entre nuvens. `setWeather`: `ripple_size`, `ripple_rate`, `splash_normal`, `splash_min_up`, `lightning_side`.
- Otimizações: a máscara pula objetos fora da câmera ou além da Distance (pela esfera do AABB) e não
  redesenha quando câmera/objetos não mudaram; Aura mede a Distance pelo AABB (não pela origem) e, sem
  objeto marcado, usa só os 32 mais próximos; splash rejeita pela máscara antes de reconstruir
  profundidade/normal. Corrigido teste de bit da máscara (objeto com as duas propriedades perdia o splash).

## Sombra com materiais Clip / código de vértice corrigida + demo de pelos (2026-10-07)

- Materiais que fazem a sombra com o próprio shader (Clip, alpha-to-coverage e, desde 2026-10-06, opacos
  com código de vértice) deixavam a cena inteira "na sombra" e travavam a GPU (~60 ms). Na passada de
  sombra o material ligava como sampler a textura de profundidade da lâmpada que era o próprio alvo
  (feedback) e recalculava luzes/matrizes compartilhadas da lâmpada com a vista dela. Agora, com
  `GetShadowMode() != RAS_SHADOW_NONE` (`GetDrawingMode()` não marca a passada de sombra): sem
  `ProcessLighting`/`UpdateLights` e sem lâmpadas ligadas (unidades de textura de sombra esvaziadas).
  Objetos com esses materiais passam também a receber sombra corretamente (a grama da demo de vento
  ficou mais escura por isso).
- Código de vértice do usuário: `UV`, `ORCO`, `TANGENT` e `COLOR` eram globais inicializadas com
  atributo (inválido no GLSL atual: o shader não compilava e o material ficava branco); viram `#define`.
- `tools/create_fur_test.py` → `demos/pelos.range`: pelo em 40 cascas no vertex shader
  (`pelos_vertex.glsl`, `#define` ajustáveis), fios afinando, gravidade e vento, xadrez e malhado; ~42 FPS
  com duas Suzannes e sombra na RX 6800M.

## Efeitos de câmera não recompilam mais ao ligar/desligar (2026-10-07)

- `KX_2DFilterManager::UpdateCameraFX` removia os passes `FILTERPASS_CAMERA_DOF`/`FILTERPASS_CAMERA_LENS`
  quando o efeito desligava e recriava (compilando o shader) quando voltava. No RolimaRacer isso
  acontecia a cada nitro e a cada troca de câmera, com travada visível.
- Agora o passe é criado uma vez e só alterna `SetEnabled`; desligado, o `RAS_2DFilter::Render` já
  devolve a entrada sem desenhar.

## Coleção "fora do jogo" deixava a layer 20 ligada (2026-10-07)

- Marcar uma coleção do outliner como "fora do jogo" liga a layer 20 da cena (para os objetos movidos
  continuarem visíveis), mas religá-la não desligava. Sem nenhuma coleção excluída, o conversor deixa de
  ignorar a layer 20, e tudo que mora nela (no RolimaRacer, o molde `group_Cameras` da Pista_1) entrava
  ativo no jogo: um segundo rig de câmera parado longe do carro. `outliner_collection_game_exclude_set()`
  agora desliga a layer 20 quando a última coleção excluída volta ao jogo. Arquivos já salvos com a layer
  presa precisam desligar a layer 20 da cena uma vez (ou excluir e religar uma coleção).
