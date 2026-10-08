# Changelog — AnastacioEngine

Registro histórico do que foi feito, alterado ou adicionado no fork. Entradas antigas preservam o contexto
da época e podem conter hipóteses corrigidas em entradas posteriores. Para o estado vigente, consulte
`docs/roadmap.md` e `relatorio-melhorias-anastacioengine.md`.

**Como está organizado.** Este arquivo guarda as entradas mais recentes (novas entradas vão no topo, logo abaixo desta tabela). O histórico mais antigo está em `docs/changelog/`, dividido em arquivos de até ~70 KB para caber na leitura de uma IA. Quando este arquivo passar de ~60 KB, mova as entradas mais antigas para um novo arquivo em `docs/changelog/` e acrescente uma linha na tabela abaixo.

Para achar uma entrada por assunto: `grep -rn "^## .*termo" docs/changelog.md docs/changelog/`.
Entradas antigas não estão em ordem cronológica estrita; a data no título é a referência.

| Arquivo | Datas | Entradas | Tamanho |
|---|---|---|---|
| [este arquivo](changelog.md) (entradas recentes) | 2026-10-07 | 33 | 44 KB |
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
