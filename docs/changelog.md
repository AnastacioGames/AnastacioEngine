# Changelog — AnastacioEngine

Registro histórico do que foi feito, alterado ou adicionado no fork. Entradas antigas preservam o contexto
da época e podem conter hipóteses corrigidas em entradas posteriores. Para o estado vigente, consulte
`docs/roadmap.md` e `relatorio-melhorias-anastacioengine.md`.

**Como está organizado.** Este arquivo guarda as entradas mais recentes (novas entradas vão no topo, como sempre). O histórico mais antigo está em `docs/changelog/`, dividido em arquivos de até ~70 KB para caber na leitura de uma IA. Quando este arquivo passar de ~60 KB, mova as entradas mais antigas para um novo arquivo em `docs/changelog/` e acrescente uma linha na tabela abaixo.

Para achar uma entrada por assunto: `grep -rn "^## .*termo" docs/changelog.md docs/changelog/`.
Entradas antigas não estão em ordem cronológica estrita; a data no título é a referência.

## 2026-09-25 - Painéis: Foliage próprio, checkbox dentro do conteúdo, Vehicle dividido

- `properties_material.py`: as opções de Foliage saíram de Game Settings para o painel `MATERIAL_PT_game_foliage` ("Foliage Shader", fechado por padrão), com o checkbox `use_foliage` no cabeçalho e duas caixas: Wind (Grass, Strength, Turbulence) e Optimization (Stop Beyond Distance, Wind Distance). As propriedades RNA não mudaram.
- `translations_ui.py`: "Wind:", "Optimization:" e "Stop Beyond Distance" em PT-BR, ES e RU.
- Aba Physics (Game): os painéis visíveis de Physics e Collision Bounds são os de `flowmenu/custom_pt_physics.py` (o `flowmenu` desregistra os de `properties_game.py`). Collision Bounds passou o checkbox para dentro ("Enabled") nas duas versões, e Create Obstacle também. Create Obstacle ganhou `bl_idname = "PHYSICS_PT_game_obstacle_create"`, para que arquivos com a posição antiga salva também o mostrem por último. O `flowmenu` e o addon `easy_ragdoll_RangeEngine` o re-registram depois dos próprios painéis, porque painel novo entra na ordem de registro (`BLI_addtail` em `rna_Panel_register`).
- Aba Vehicle dividida em painéis: Vehicle (checkbox "Enabled", Chassis: Steering Wheel e Center of Mass Offset), Engine (Drive Type e Power), Wheels, Gearbox e Player Component. Os painéis de ajuste só aparecem para Rigid Body/Dynamic e ficam apagados até o veículo ser ativado. Traduções dos textos novos em PT-BR, ES e RU.
- Registro em background (`RangeEngine --background`): todos os painéis novos registram sem erro e o id antigo `PHYSICS_PT_game_obstacles` não existe mais.
- Aba Material sem checkbox no título: Transparency (Render e Game), Mirror, Subsurface Scattering, Flare e Foliage Shader agora mostram o checkbox como primeira linha do conteúdo, com o texto "Enabled", e o restante fica apagado quando ele está desligado.

## 2026-09-25 - Foliage: correções do vento (Web, instancing, precisão, arquivos antigos)

- `gpu_shader_vertex.glsl`: `grass == 1` (float com int) não compilava em GLSL ES 3.00 (Web); agora `grass > 0.5`.
- O vento roda no espaço da malha, antes do instancing e do skinning. Antes rodava depois de `position *= instmat`, então em grama instanciada o corte `z < 0.1` comparava o Z do mundo e a base também balançava.
- Instancing nunca chamava `GPU_material_bind_uniforms()`, então `unfoliageparams` ficava zerado e folhagem instanciada não balançava. `GPU_material_bind()` agora envia os parâmetros para materiais com instancing. A distância do vento é testada no shader por instância (novo `unfoliagecamera`), e cada instância recebe fase de ruído própria (`ininstposition.xy`).
- Precisão: o tempo `time * turbulence` é reduzido com `fmod` para o período 256 no CPU, e o hash do ruído usa `mod(st, 256)`. A troca de período fica contínua, e o `sin` do hash não recebe mais valores enormes em sessões longas.
- Sem câmera ativa, `BL_BlenderShader::BindProg` passa `NULL` e o limite de distância é ignorado (antes media a partir da origem). A referência agora é definida antes do bind.
- `versioning_range.c`: arquivos sem `Material.foliage_distance` recebem 50 m. `foliage_distance <= 0` também desliga o limite, em vez de parar todo o vento.
- Build: `RangeRuntime` e `RangeEngine` compilados. Testado e aceito pelo usuário no desktop em 2026-09-25; o build Web ainda não foi testado (pendência no roadmap).
- Sem mudança: sombras (override shaders) não recebem o vento; normais não são recalculadas; corte seco no limite da distância.

## 2026-09-25 - Cycles OpenCL: validação funcional inicial na AMD

- `build_opencl_validate/` foi configurado isoladamente com `WITH_CYCLES_DEVICE_OPENCL=ON`; em modo serial, `cycles_kernel`, `cycles_device` e `RangeEngine` compilaram e linkaram. O `build/` principal não foi alterado.
- No executável isolado, `_cycles.get_device_types()` confirmou OpenCL ativo e `_cycles.available_devices('OPENCL')` enumerou a RX 6800M e a Radeon integrada. `_cycles.opencl_compile()` com zero argumentos e com índice não numérico retornou `False` e o processo terminou normalmente, validando CYC-006 nos dois casos exercitados.
- Permanecem pendentes apenas cenários de recurso alto/especiais: cópia OpenCL acima de 2 GiB (CYC-007) e a compilação em processo separado com caminho/nome contendo apóstrofo, barra e quebra de linha (CYC-010).

| Arquivo | Datas | Entradas | Tamanho |
|---|---|---|---|
| [este arquivo](changelog.md) (entradas recentes) | 2026-09-25 a 2026-09-24 | 45 | 50 KB |
| [12_2026-09-23_a_2026-09-23.md](changelog/12_2026-09-23_a_2026-09-23.md) | 2026-09-23 a 2026-09-23 | 9 | 13 KB |
| [11_2026-09-22_a_2026-09-20.md](changelog/11_2026-09-22_a_2026-09-20.md) | 2026-09-22 a 2026-09-20 | 25 | 39 KB |
| [10_2026-09-20_a_2026-09-20.md](changelog/10_2026-09-20_a_2026-09-20.md) | 2026-09-20 a 2026-09-20 | 12 | 19 KB |
| [01_2026-09-20_a_2026-09-14.md](changelog/01_2026-09-20_a_2026-09-14.md) | 2026-09-20 a 2026-09-14 | 45 | 69 KB |
| [02_2026-09-14_a_2026-09-11.md](changelog/02_2026-09-14_a_2026-09-11.md) | 2026-09-14 a 2026-09-11 | 24 | 71 KB |
| [03_2026-09-12_a_2026-08-23.md](changelog/03_2026-09-12_a_2026-08-23.md) | 2026-09-12 a 2026-08-23 | 49 | 90 KB |
| [04_2026-08-24_a_2026-08-24.md](changelog/04_2026-08-24_a_2026-08-24.md) | 2026-08-24 a 2026-08-24 | 4 | 81 KB |
| [05_2026-08-25_a_2026-08-24.md](changelog/05_2026-08-25_a_2026-08-24.md) | 2026-08-25 a 2026-08-24 | 2 | 68 KB |
| [06_2026-08-31_a_2026-08-26.md](changelog/06_2026-08-31_a_2026-08-26.md) | 2026-08-31 a 2026-08-26 | 7 | 71 KB |
| [07_2026-09-02_a_2026-08-31.md](changelog/07_2026-09-02_a_2026-08-31.md) | 2026-09-02 a 2026-08-31 | 23 | 69 KB |
| [08_2026-09-06_a_2026-09-02.md](changelog/08_2026-09-06_a_2026-09-02.md) | 2026-09-06 a 2026-09-02 | 26 | 68 KB |
| [09_2026-09-17_a_2026-09-06.md](changelog/09_2026-09-17_a_2026-09-06.md) | 2026-09-17 a 2026-09-06 | 51 | 71 KB |

## 2026-09-25 - Cycles: upscale em `util_image_resize_pixels`

- `util/util_image_impl.h`: o ramo `scale_factor > 1` alocava a saída e deixava os pixels sem preencher (`TODO`). Agora interpola linearmente por eixo, mapeando centros de pixel e prendendo nas bordas; componentes são interpolados separadamente e o valor volta ao tipo de origem (`uchar`, `uint16_t`, `half`, `float`). Entrada vazia gera saída zerada.
- Imagem 2D (profundidade 1) continua com profundidade 1 no upscale; antes a conta dava profundidade `scale_factor` e transformaria a textura em volume. O downscale já resultava em 1 e não muda.
- O único chamador (`render/image.cpp`) só reduz escala, então o fluxo de render atual não muda; a correção vale para quem reutilizar a API.
- Teste novo `test/util_image_test.cpp` (8 casos: cópia com escala 1, downscale box, upscale 2D, gradiente linear, 4 componentes, escala 1,5 em volume, `uchar`, entrada vazia). Em `build_gtest/`: 8/8 com a correção; com o header anterior, os 6 casos de upscale falham. `cycles_render` recompila sem erro.
- Subdivisão (FVar, `ATTR_ELEMENT_VERTEX_MOTION`), CUDA e OpenCL não foram tocados.

## 2026-09-25 - Cycles: testes de regressão CPU para CYC-001 a CYC-005

- GTest do Cycles volta a configurar e linkar: `GTestTesting.cmake` apontava `WORKING_DIRECTORY` para o alvo `blender`, que não existe desde a troca para `RangeEngine`; o `CMakeLists.txt` de `intern/cycles/test` agora linka `PUGIXML_LIBRARIES` e `WEBP_LIBRARIES`, dependências do OpenImageIO que no Windows só chegavam via OSL/imbuf. Nada muda com `WITH_GTESTS=OFF`.
- Testes novos em `source/intern/cycles/test/`:
  - `util_path_test.cpp` (CYC-001/004): ida e volta de `path_write_binary()`/`path_read_binary()`, escrita em diretório retorna `false`, leitura de arquivo ausente ou vazio retorna `false` com vetor limpo, e `path_file_size()` devolve o sentinela `(size_t)-1`.
  - `util_ies_test.cpp` (CYC-002): contagens zero, negativas, acima de 4.096, grade acima de 1.048.576 e números que estouram `long` são rejeitados; tilt negativo ou acima do limite também; a grade máxima 4096×256 continua aceita; falha limpa um perfil carregado antes.
  - `render_tile_test.cpp` (CYC-003): `TileManager` em 65.536² calcula `total_pixel_samples` (com e sem denoising e com prévia progressiva) e `resolution_divider` = 1024 sem overflow.
  - `render_light_ies_test.cpp` (CYC-005): tabela de offsets de `device_update_ies()` com slot inválido (-1), slot removido no meio e slots finais descartados, usando device CPU.
- Validação em `build_gtest/` separado (cópia do cache de `build/` com `WITH_GTESTS=ON`): `cycles_util_path_test` 41/41, `cycles_util_ies_test` 13/13, `cycles_render_tile_test` 4/4, `cycles_render_light_ies_test` 3/3; o `cycles_render_graph_finalize_test` já existente também passa (61/61).
- Fora do alcance em CPU/memória comum: escrita parcial real (CYC-001, exige injeção de falha no `fwrite`), remoção do arquivo entre `fopen` e `stat` (CYC-004, o Windows não apaga arquivo aberto), alocação de `RenderBuffers` em 65.536² (CYC-003, dezenas de GiB) e soma de IES acima de `INT_MAX` (CYC-005, gigabytes de perfis). Esses ramos seguem validados só por leitura.
- CYC-011: `IESTextParser` agora termina o `vector<char>` com `'\0'` antes de usar `strstr`, `strtod` e `eof()`. Antes, um IES que terminasse no último número podia provocar leitura além do fim. O teste `valid_type_c_without_trailing_newline` cobre essa entrada válida sem quebra de linha final.

## 2026-09-25 - Cycles OpenCL: compilação externa aceita nomes e caminhos especiais

- A expressão Python usada pela compilação OpenCL separada deixou de usar string bruta e passou a serializar barras invertidas, apóstrofos e quebras de linha. Antes, o “escape” de apóstrofo não inseria barra em C++, tornando inválido o `--python-expr` para determinados nomes de dispositivo ou caminhos de cache.
- Validação: `opencl_util.cpp` recompilado no MSVC; o caminho `WITH_OPENCL` continua pendente de execução em build separado.

## 2026-09-25 - Cycles CUDA: carga de kernels e cópia de buffer grande (CYC-008, CYC-009); rede marcada como insegura

- CYC-008: `CUDADevice::load_kernels()` guardava o resultado dos dois módulos na mesma variável; um cubin de render com falha e um de filtro carregado retornavam `true` e levavam `reserve_local_memory()` a lançar kernel com `CUfunction` não inicializado. Agora a carga exige os dois módulos, e `reserve_local_memory()` para se a busca da função ou a ocupação falhar.
- CYC-009: `CUDADevice::mem_copy_from()` passa a multiplicar em `size_t` (mesmo padrão de CYC-007 no OpenCL); cópias de 2 GiB ou mais davam overflow de `int`.
- Revisão estática de `device_cuda.cpp`, `.cu` e `device_network.cpp`: o device de rede ficou registrado como não suportado e inseguro no `docs/relatorio-varredura-cycles.md` (não compila, trava sem `stop` e desreferencia nulo em erro de recepção; o protocolo não tem autenticação). `WITH_CYCLES_NETWORK` continua `OFF`. A falta de suporte a sm_80+ e a CUDA atual entrou como backlog de portabilidade.
- Validação: build separado `build_cuda/` com `WITH_CYCLES_DEVICE_CUDA=ON` e `WITH_CUDA_DYNLOAD=ON` (cuew, sem toolkit NVIDIA); `ninja cycles_device extern_cuew` compilou e linkou sem avisos em `device_cuda.cpp`. O `build/` compartilhado não foi tocado. Sem execução em GPU.

## 2026-09-25 - Cycles OpenCL: cópia de buffer preserva tamanhos grandes

- `OpenCLDevice::mem_copy_from()` agora converte para `size_t` antes de multiplicar elemento, linha, largura e altura. Antes, uma região acima de `INT_MAX` podia sofrer overflow de `int` e passar offset/tamanho incorretos a `clEnqueueReadBuffer()`.
- Validação: `opencl_split.cpp` recompilado no MSVC. A configuração vigente desativa OpenCL; a compilação e o teste do ramo `WITH_OPENCL` ficam pendentes para um build separado.

## 2026-09-25 - Cycles OpenCL: API de compilação rejeita argumentos inválidos

- `device_opencl_compile_kernel()` agora valida que `_cycles.opencl_compile()` recebeu exatamente seis parâmetros e converte o índice de dispositivo sem lançar exceção: texto vazio/não numérico, valor negativo e valor acima de `INT_MAX` retornam `false`. Antes, a entrada Python inválida podia acessar um vetor fora dos limites ou deixar `std::stoi()` encerrar o processo auxiliar de compilação.
- Validação: `opencl_util.cpp` recompilado no MSVC. O build vigente está com OpenCL desligado, então a execução do ramo `WITH_OPENCL` segue pendente de uma configuração própria com OpenCL habilitado.

## 2026-09-25 - Cycles: leitura binária e produtos largura × altura (CYC-004, CYC-003)

- CYC-004: `path_read_binary()` (`util/util_path.cpp`) não passa mais o `(size_t)-1` de `path_file_size()` (stat
  falhou depois do `fopen()`) para `vector::resize()`; retorna `false` com o vetor vazio, também quando o `fread()`
  lê menos bytes. Header inalterado.
- CYC-003: produtos de dimensão passam a `size_t`/`uint64_t`/`int64_t` antes de multiplicar: alocação e cópia do
  buffer em `render/buffers.cpp` (`size` e os laços de `get_denoising_pass_rect`/`get_pass_rect` viraram `size_t`;
  a média do passe Render Time divide em `double`), `get_divider`, contagem de pixel samples em `render/tile.cpp` e o
  vetor de pixels da tile em `blender/blender_session.cpp`. Com 65.536 × 65.536 (limite da RNA) o `int` estourava.
- Validação: os quatro `.obj` compilados no MSVC (compilação só desses objetos, para não pegar o trabalho em
  andamento do Codex no IES). Depois que o Codex terminou, `RangeEngine` relinkado com todo o Cycles e render de
  teste (320×240, 16 amostras, tiles 64×64, cena padrão): saída idêntica pixel a pixel à do binário anterior.

## 2026-09-25 - Sensor Actuator detecta actuators de disparo único

- `SCA_ActuatorSensor::Evaluate` só olhava `IsActive()` no início do frame seguinte. Actuators que ativam e
  desativam no mesmo frame (Property, Message, Add Object, Scene, Game...) já estavam inativos nesse momento, e o
  sensor disparava com `positive=0` (nunca ficava positivo; um AND ligado a ele não fazia nada). O `m_midresult`
  gravado em `Update()` era descartado. Agora o resultado é `IsActive() || m_midresult`, e o `Init` zera o
  `m_midresult`. Código igual ao do Blender/UPBGE original.
- Validação: `RangeRuntime` recompilado; jogo headless gerado por script (`RangeEngine -b`) com Motion (contínuo),
  Property (um disparo), Property disparado 4 frames seguidos e sensor invertido. Antes: Property só gerava
  `positive=0`. Depois: Motion positivo do frame 7 ao 17 (igual antes); Property positivo 1 frame (27→28);
  disparos seguidos ficam positivos sem piscar (34→37); invertido correto.
- Validação no editor: `RangeEngine` relinkado depois do Cycles do Codex; o mesmo jogo, mais um sensor Actuator
  vigiando um Property e outro vigiando um Message, cada um ligado a AND → Property, rodado pelo
  `VIEW3D_OT_game_start` (o P) na janela real. Log igual ao do runtime, e cada AND disparou uma vez
  (`hitProp=1`, `hitMsg=1`).

## 2026-09-25 - Cycles: escrita binária não reporta mais sucesso falso

- `path_write_binary()` em `source/intern/cycles/util/util_path.cpp` agora exige que `fwrite()` grave todos os bytes e que `fclose()` conclua sem erro. Antes, cache binário parcial por disco cheio, quota, I/O interrompido ou falha no flush podia ser aceito como sucesso. A API preserva a assinatura e os chamadores OpenCL já propagam o `bool` retornado.
- Validação: `util_path.cpp` recompilado e `lib/cycles_util.lib` relinkada no ambiente MSVC; `git diff --check` passou. Não há alteração de header/DNA.

## 2026-09-25 - Cycles: parser IES limita contagens antes de alocar

- `IESFile::parse()` preserva os contadores textuais como `long` até validá-los. Perfis IES com eixos zero/negativos, mais de 4.096 ângulos por eixo ou mais de 1.048.576 intensidades agora são rejeitados antes de `reserve()`/`resize()`; a contagem de `TILT=INCLUDE` recebe o mesmo teto. Isso evita conversão de `-1` para `size_t` e alocações excessivas por arquivo corrompido ou embutido.
- O teto de amostras considera que o processamento pode espelhar a tabela horizontal até quatro vezes, mantendo uma IES individual abaixo dos limites de `int`. A soma/offset entre múltiplas IES foi tratada na entrada seguinte (CYC-005).

## 2026-09-25 - Cycles: empacotamento IES não trunca tabela nem offsets

- `LightManager::device_update_ies()` agora calcula a soma de tabelas IES e os índices de slot em `size_t`, e só converte para `int` depois de confirmar que a tabela de offsets e os dados cabem em `INT_MAX`, formato exigido pelo kernel. Isso remove overflow na soma e offset negativo/truncado ao empacotar muitos perfis.
- Quando a capacidade é excedida, a engine envia uma tabela de offsets `-1`: os nós IES afetados não amostram um perfil, mas a renderização não usa memória ou offsets corrompidos. `light.cpp` recompilado e `lib/cycles_render.lib` relinkada no MSVC.

## 2026-09-25 - Animation Events revisados (crashes, threads, sensor, painel)

- Revisão do sistema herdado da Range. **Editor**: o evento agora conta como usuário da Action (`id_us_plus`/`min`
  em `object.c`, `newlibadr_us` no `readfile.c`, `IDWALK_CB_USER` no `library_query.c`, `expand_doit` no append).
  Antes, apagar a Action deixava ponteiro solto (crash ao desenhar o painel) e uma Action usada só pelo evento
  sumia ao salvar. Operadores (`object_animation_event.c`) validam índices e cancelam em vez de crashar, usam a cena
  ativa (antes `G.main->scene.first`), mandam notifier; ▲ no primeiro evento não troca mais com o elemento-base
  escondido (índice 0), que fazia o evento sumir. Remover evento libera os triggers.
- **Runtime**: `BL_Action::Update` roda nas threads do pool de animação e o `KX_Scene::UpdateAnimations` lia/limpava
  a mesma fila de eventos na thread principal ao mesmo tempo. Agora os callbacks rodam depois de
  `BLI_task_pool_work_and_wait`, no mesmo frame. Trigger dispara quando a reprodução cruza o frame (antes: janela
  de ±2 frames + lista "já disparados" por valor de frame, que engolia dois triggers no mesmo frame e zerava todas
  as Actions do objeto); trata loop, ping-pong, sentido reverso e objetos culled; `setActionFrame` não dispara o que
  pulou. `KX_AnimationEvent` guarda dados por valor (acabou vazamento de `new char[64]`/vetores), mantém referência
  própria da função Python e não compartilha proxy com a cópia; evento sem Python Event não gera erro no log;
  `animationEventManager` sem manager retorna `None` com refcount certo; manager não vazava mais uma referência na
  conversão.
- **Sensor Animation Event**: sensor de objeto criado por AddObject apontava para o evento do original (nunca
  disparava) — `KX_GameObject::ReParentLogic` religa. Detecção por contador de disparos (antes comparava o último
  frame e perdia disparos seguidos; com um trigger em loop disparava só uma vez). Conversão não chama mais
  `GetEvent` em manager nulo (`this &&`, UB no clang de Web/Android).
- **Painel**: Action e Python Event em cima, linha Triggers com Add Trigger, aviso com ícone de informação, ▲/▼
  desativados nas pontas, disponível também em Empty/Camera/Lamp.
- **Validação**: compilou (`RangeEngine` + `RangeRuntime`, sem mudança de DNA). Teste headless de 27 checagens dos
  operadores/contagem de usuários/salvar-recarregar passou. Teste no runtime com Action em loop 1-20, triggers em
  1, 10, 10 e 20, callback Python e sensor, num objeto e numa cópia por AddObject: cada trigger disparou 12-13
  vezes nos dois objetos e o sensor pulsou 24/25 vezes. Não verificado: o painel na janela do editor.

## 2026-09-25 - World Status com nomes em inglês

- As 8 World Properties automáticas viraram `rain_enabled`, `rain_intensity`, `clouds_enabled`, `mist_enabled`,
  `mist_density`, `sun_hour`, `cloud_type`, `player_under_cover` (`world.c`, `BL_ConvertProperties.cpp`).
  `horario_sol` virou `sun_hour`, que o runtime já lê para o World Sun automático.
- O `startup.blend` embutido guardava os nomes em português, e o File > New mostrava os dois conjuntos.
  `BKE_world_status_props_ensure` agora renomeia o nome antigo (mantendo o valor) ou o remove quando o novo já
  existe. `.blend` do usuário não são alterados. `RangeEngine -b --factory-startup` lista só as 8 em inglês.
- Painel World: Colors em 4 colunas; Moon Size e Brightness separados.

## 2026-09-25 - Aba Input nas Propriedades (Input System saiu das Preferências)

- O Input System (mapas `KeyMapping/*.json` ao lado do `.range`) era uma seção das Preferências da engine, mas os
  mapas são do projeto e vão no pacote Web/APK. Agora fica numa aba própria **Input** no editor de Propriedades
  (`BCONTEXT_INPUT = 18`, ícone de controle, depois de Export Game), no mesmo padrão da aba Export
  (`DNA_space_types.h`, `buttons_context.c`, `space_buttons.c`, `rna_space.c`, `space_properties.py`). A seção
  das Preferências só avisa que o painel mudou de lugar.
- `bl_ui/properties_input.py`: layout em árvore que abre e fecha, para caber na coluna estreita. Cada mapa abre e
  mostra as ações (Input Tables); cada ação abre e mostra tipo de retorno, ligações e processadores. Um mapa ou ação
  aberto por vez; mapa ou ação recém-criado já abre. Painel "On-screen Controls (Web/Android)" com o layout de toque
  e as ações que ele não aperta (WEB-INPUT-001).
- Correção: o painel antigo registrava propriedades no `WindowManager` durante o desenho, o que o RNA bloqueia
  ("can't set in readonly state"); abrir uma ligação dava erro e sumiam as ligações, os processadores e o botão de
  salvar. Agora o desenho só marca `update_binding_properties` e o handler `scene_update_post`
  (`input_sync_handler`) cria as propriedades e faz o salvamento pedido ao remover uma ligação.
- Traduções pt/es/ru dos textos novos (`INPUT_PANELS` em `translations_labels.py`); "Bindings:" em pt vira "Ligações:".
- Testado no editor com screenshot: criar mapa, ação e ligação (d-pad do joystick 0 como Vector2D), salvar e remover
  a ligação, conferindo o `.json` em cada passo. O motor e o formato do `.json` não mudaram.

## 2026-09-25 - Template de componente "03 Jogador Celular" (teclado, gamepad e controle na tela)

- Novo `release/scripts/templates_components/03_jogador_celular.py`, em Text Editor > Templates > Components.
  É o exemplo recomendado para quem não programa: anexa ao jogador e ajusta `Speed`, `Jump Speed`,
  `Move Relative To Object` e `Stick Deadzone` no painel. Anda com WASD/setas, stick esquerdo ou d-pad do gamepad 0
  e pula com Espaço ou botão A; o controle na tela (layouts `stick` e `dpad`) chega como gamepad 0, então o mesmo
  código serve ao PC, ao controle USB e ao celular. O comentário do topo é o passo a passo e explica que em
  `activeButtons` o botão A é 0 (no Input System é 1).
- Chão por `collisionCallbacks` (contato abaixo do centro com normal quase vertical), não por velocidade vertical
  perto de zero: depois de cair, a física deixa ~0,18→0,02 de velocidade por ~10 quadros e o pulo era ignorado.
  Objeto sem física anda, e o console avisa que ele não pula (sem traceback).
- Teste no `RangeRuntime.exe` (Windows) com cena gerada por script e input simulado no componente: componente
  carregado do `.range`, 3,33 m em 40 quadros com `Speed` 5, pulo 1 quadro após tocar o chão (0,49→1,29 m em
  10 quadros), sem pulo duplo no ar. Teclado, gamepad e toque reais não foram apertados nesse teste. Linux não
  testado; o template é só Python e usa a numeração SDL dos botões, igual nas duas plataformas.

## 2026-09-25 - Export Game: painéis RangeArmor, Web e Android divididos em caixas

- `SCENE_PT_rangearmor_export`: caixas Platforms / Package Info / Export, com dicas (Web e Android têm painéis
  próprios; campos vazios mantêm o padrão do RangeArmor Panel; o `.blend` precisa estar em `<projeto>/data/`).
- `properties_web.py`: caixas Package / Touch Controls / Validation / Export / Browser Test. O relatório da validação
  fica dentro da caixa Validation; "Pré-voo" e "Abrir após exportar" lado a lado.
- `properties_android.py`: caixas App / Build / Release Signing (só com tipo Release) / Tools / Build and Install.
  Versão e código da versão em linhas separadas (o label "Versão do app" ficava cortado).
- Traduções que as capturas revelaram erradas: o tipo de build aparecia como "Liberar" (`.mo` do Blender traduzindo
  "Release") e o runtime Web como "Em execução" (chave genérica "Runtime"). Os itens do enum viraram
  "Debug (testing)" / "Release (players)" e a propriedade `runtime_id` virou "Web runtime", sem mudar identificadores.
  "Product Name" e "Company Name" ganharam tradução. Tudo em `EXPORT_PANELS` de `translations_labels.py`.
- Teste: capturas dos três painéis em pt_BR, es e ru_RU sem traceback; `engine_i18n.py` 36 ok.

## 2026-09-25 - Aba Export Game no editor de Propriedades

- Nova aba `BCONTEXT_EXPORT = 17` (ícone EXPORT) logo depois de Cutscene, no grupo de cima do cabeçalho
  (`DNA_space_types.h`, `rna_space.c`, `buttons_context.c` usa o caminho de cena, `space_buttons.c` desenha o
  contexto `"export"`, `space_properties.py` inclui `'EXPORT'` em `top_context`).
- Os painéis Export (RangeArmor), Web (Range) e Android (Range) saíram da aba Scene e passaram a usar
  `bl_context = "export"`. Traduções da aba em `translations_ui.py`.
- Docs com o caminho antigo (`Properties > Scene > Web (Range)`) atualizados.

## 2026-09-25 - Game Settings > Audio e Scene > Units: labels e dicas

- Audio: "Speed of Sound (m/s)" e "Doppler Factor" no lugar de "Speed"/"Doppler", com dica de que o `LA_Launcher`
  lê esses valores da cena inicial. `audio3d_update` virou "Speaker Update Skip (frames)", com dica de que vale só
  para objetos Speaker e 0 = todo quadro.
- Units: o label do sistema de unidades dizia "Length:" e virou "Unit System:". No Game Engine aparece a dica de que
  as unidades só mudam a exibição no editor (o jogo sempre usa 1 unidade = 1 m) e um aviso quando há Unit Scale
  diferente de 1.
- Traduções pt_BR/es/ru em `translations_labels.py`.

## 2026-09-25 - Build: Ninja não rastreia headers (MSVC em português) e crash ao dar play

- Sintoma: depois de adicionar membros em `KX_GameObject.h` (billboard do LOD), dar play no editor e no RangeRuntime
  fechava a engine (`EXCEPTION_ACCESS_VIOLATION` em `KX_ShadowRenderer::Render`).
- Causa: `msvc_deps_prefix` em `build/CMakeFiles/rules.ninja` é `Observação: incluindo arquivo:`; a saída do MSVC chega
  em outra codificação, o prefixo não bate e o Ninja não registra nenhuma dependência de header. Só os `.cpp` editados
  foram recompilados; `KX_ShadowRenderer.obj` ficou com o layout antigo do `KX_GameObject`.
- Contorno aplicado: apagados os 307 `.obj` de `build/source/gameengine/**` e recompilado (329/329). Engine abre sem
  crash, cena com Sun e sombra roda 120 quadros no RangeRuntime, teste de LOD passa.
- Regra registrada em `AGENTS.md` e `docs/build-notes.md`. Correção definitiva pendente: reconfigurar com `VSLANG=1033`.
  Mudanças antigas em headers da parte C podem ter deixado `.obj` desatualizados; um clean rebuild resolve.

## 2026-09-25 - LOD: billboard restaura a rotação e nível Invisible sem Occlusion Culling

- `KX_GameObject::UpdateLod`: o nível com Billboard girava o objeto para a câmera e nunca devolvia a rotação ao voltar
  para um nível sem billboard. Novos membros `m_lodBillboardActive`/`m_lodBillboardOrientation` guardam a orientação
  ao entrar no billboard e a restauram ao sair.
- `KX_Scene::CalculateVisibleMeshes`: o nível "Invisible Mesh" só escondia o objeto com Occlusion Culling (DBVT)
  ligado. Nova `CullInvisibleLods` aplicada nos caminhos sem frustum culling e sem DBVT (não em shadow buffer).
- `OBJECT_OT_bake_lod_impostor`: grade do atlas agora usa colunas que dividem o número de ângulos (8 ângulos = 4x2,
  antes 3x3 com célula vazia).
- Teste no RangeRuntime (Occlusion Culling desligado): near/billboard/near/invisible/back com nível, `culled` e rotação
  corretos em cada etapa.

## 2026-09-25 - Game Settings (aba Scene): labels, Navigation Mesh separada e Python Console

- `properties_game.py`, `SCENE_PT_game_physics`: "Physics Engine" e "Solver" no lugar de "Engine"; boxes
  "Steps & Timing" (Game Rate / Per Frame, sempre visível), "Deactivation (Sleeping Objects)" e "Culling"
  (Render / Object Activity). Corrigido o ramo com física "None", que usava a propriedade inexistente `logic_step_max`.
- Obstacle Simulation com dica "Used by the Steering actuator to avoid obstacles" e labels "Simulation",
  "Level Height", "Show Debug Visualization" (é o RVO do atuador Steering, independente da navmesh).
- Navigation Mesh virou o painel próprio `SCENE_PT_game_navmesh` (fechado por padrão); removido
  `Scene.show_expanded_game_navmesh`.
- "Level of Detail - LOD" virou "Level of Detail", com dica de que os níveis ficam na aba Object.
- Python Console: checkbox "Enable Python Console" movido para dentro do box, junto das teclas e de uma dica
  (segurar as teclas durante o jogo abre o console do sistema; o jogo pausa enquanto ele está aberto).
- Traduções pt_BR/es/ru dos novos textos em `translations_labels.py` (`RENDER_PANELS`).

## 2026-09-25 - Aba Render: painéis reorganizados, FXAA configurável e addons padrão

- Seletor de engine (`RENDER_PT_render`) movido para `properties_render_engine.py`, registrado antes de
  `properties_game` para ficar no topo da aba Render.
- Player: Embedded e Standalone lado a lado num painel "Player". System e Game Exit Key lado a lado; cursor
  customizado recolhível. Dynamic Resolution foi para dentro do painel Display, ao lado das opções de tela.
- Attachments: slots vazios aparecem como "Empty", mostra o índice `bgl_DataTextures[n]` real, avisa quando há slots
  vazios antes (os índices dos materiais deixam de bater) e quando o SSR usa o Slot 0. `active_attachment_index`
  usa `GAME_ATTACHMENT_COUNT`.
- Animations: frame rate da animação e taxa de lógica lado a lado, com dica do "Restrict Animation Updates".
- Bake: dicas de que precisa de UV e imagem, e de que usa o shading do Blender Render. Easter egg "Make GTA 6" mantido.
- FXAA: `SCENEFXSettings` ganhou `fxaa_edge_threshold`, `fxaa_edge_threshold_min`, `fxaa_subpix` e
  `fxaa_search_steps` (padrões = valores antigos fixos no shader; versioning em `versioning_range.c`). Os shaders do
  viewport (`gpu_shader_fx_fxaa_frag.glsl`) e do jogo (`RAS_Fxaa2DFilter.glsl`, uniform `ge_FxaaParams`) leem esses
  valores; filtros criados por Python/atuador usam os padrões. Painel FXAA expansível em Post-Processing.
- Userpref padrão liga os addons Icon Viewer e Game Engine Scene Statistics (vale para userpref novo; um
  `userpref.blend` salvo mantém a escolha do usuário).

## 2026-09-25 - Build: correções para Android NDK e Cycles no player

- `source/CMakeLists.txt`: sem GLU no Android mesmo com perfil compat. `mallocn_intern.h`: sem `malloc_stats()` no
  bionic. `util_profiling.cpp`: `#include <chrono>`. `blenderplayer/CMakeLists.txt`: liga `bf_intern_cycles` quando
  `WITH_CYCLES` (o `bf_python` registra o módulo `_cycles`).
- `docs/build-dirs.md`: nomes oficiais dos diretórios `build*` (o Android oficial é o APK WebView; `build-android/`
  é o experimento NDK congelado). Referenciado em `AGENTS.md`, `build-notes.md` e `mobile-export-plan.md`.

## 2026-09-24 - Debug: crash ao passar o mouse na tabela de Profile

- Sintoma: com "Framerate and Profile" ativo, passar o mouse sobre as linhas da tabela de profile fechava a engine
  (crash em `ImGui::SetTooltip` chamado por `KX_DebugMode::RenderDebugProperties`).
- Causa: `profileTips` (`KX_DebugMode.h`) tinha 12 entradas, mas a tabela percorre `tc_numCategories` (23)
  categorias; o hover nas linhas 13+ lia fora do array. As 12 dicas também estavam fora de ordem em relação às categorias.
- Correção: `profileTips` reescrito com uma dica por categoria, na ordem do enum `tc_*`, e um `static_assert` em
  `KX_DebugMode.cpp` que quebra a compilação se alguém adicionar categoria sem dica.
- Vale para todos os alvos (desktop, Android, web), pois compartilham o mesmo `source`.

## 2026-09-24 - Veículo: motor em Nm, pedais, joystick, moto e gamepad só no ImGui de gameplay

- `vehicle_player_component.py` (projeto de teste, demo `Vehicle` e template do flowmenu, mantidos idênticos):
  torque em Nm; neutro (N) e ré (R) no câmbio; pedais acelerador/ré/freio com ré virtual; "Invert Direction";
  telemetria sempre publicada; "Throttle Time (s)" (rampa de pedal no teclado) e "Engine Inertia" (RPM sobe/desce
  com inércia, mais lento em neutro).
- Joystick no mesmo componente (seção Joystick): analógico esquerdo = direção, RT/LT = acelerar/ré, B = freio,
  X = freio de mão, LB/RB = marchas, A = empinar; índice e zona morta configuráveis.
- Seção Moto: checkbox "Motorcycle" com equilíbrio PD em torno do eixo à frente (inclina para dentro da curva conforme
  a velocidade), "Max Wheelie (deg)" (trava de empinar, padrão 45°) e "Wheelie Key" (Shift esquerdo) / botão A com
  "Wheelie Force" e "Wheelie Min Speed". Na moto a tecla de empinar tem prioridade sobre o freio de mão se coincidirem.
- `KX_Imgui_Impl_Inputs.cpp`/`KX_PythonImgui.cpp`: o gamepad só navega janelas ImGui criadas pelo Python
  (`imgui.begin`, gameplay); menus de debug nativos recebem os botões como soltos.
- `KX_VehiclePreset` ganhou bloco opcional `engine` (torque, RPM, câmbio, relações); `KX_VehicleDebugUI` ganhou aba
  Engine. Build de `RangeEngine`/`RangeRuntime` ok; validado no jogo pelo usuário.

## 2026-09-24 - Veículo: telemetria de marcha/RPM no HUD e no Vehicle Lab

- `vehicle_player_component.py` (projeto de teste, demo `Vehicle` e template do flowmenu): seções Motor, Freios,
  Direção, Câmbio, Controles e Telemetria; teclas configuráveis de troca (E/Q por padrão) e RPM de subida/descida do
  automático. "Publish Telemetry" grava `vehicle_gearbox`, `vehicle_gear`, `vehicle_rpm` e `vehicle_speed_kmh` no chassi;
  "Show HUD" mostra essas propriedades no debug (depois removido: a telemetria passou a ser sempre publicada). No manual a troca vale a qualquer velocidade.
- `KX_VehicleDebugUI.cpp`: aba Overview do Vehicle Lab mostra câmbio, marcha e RPM lidos dessas propriedades (ou dica
  para ligar a telemetria). Compilado; validação no jogo pendente com o usuário.

## 2026-09-24 - Reauditoria de bugs silenciosos

- Concluída a releitura dos 26 candidatos de `source/blender`: PHYS-001/002, GPU-002, PY-002, BLN-002 e BLN-004 foram descartados; a suspeita de cabeçalho AVI inválido após o primeiro frame também foi descartada.
- Fechadas quatro lacunas remanescentes em commits pequenos: falhas de I/O/finalização AVI, liberação de `AnimOverride`, limites da reconstrução de tracking e I/O parcial de `datatoc`.
- `RangeEngine` e `RangeRuntime` passaram no build isolado; a regressão ANIM/MOD/RND, uma exportação AVI RAW e a conversão real por `datatoc` passaram. GPU-001 requer teste manual em uma janela interativa já aberta; o smoke automatizado agora o registra como `SKIP` explícito.

## 2026-09-24 - Associações `.blend` e `.range` no Windows

- `RangeEngine.exe -R`/`-r` registra `.blend` para o editor e `.range` para o `RangeRuntime`; `-U`/`-u` remove somente os valores e ProgIDs da Range Engine. O registro tenta `HKLM` e recua para `HKCU` sem elevação.
- Validado sem abrir janela: `RangeEngine -r` e `-u` criaram/removeram no `HKCU` os ProgIDs, comandos e ícones esperados, e as associações anteriores foram restauradas. Falta o teste visual de duplo clique no Explorer.

## 2026-09-24 - Lacunas do catálogo pt_BR e espanhol

- Novo `range_web/translations_catalog.py`: 436 entradas pt_BR e 493 es já traduzidas nos `.po` do Blender 2.79, mas ausentes do MO instalado, passam a complementar os dicionários do editor. O russo não recebeu tradução em massa.
- Auditoria com a árvore-fonte carregada: pt_BR 1 279 → 1 030 e es 1 336 → 1 089. A diferença remanescente inclui identificadores RNA, ícones e textos técnicos/iguais ao inglês; `engine_i18n.py` passou para pt_BR, es e ru_RU em modo background.

## 2026-09-24 - Export Android: AAB para a Google Play

- `range_web/android.py`: opção `aab` do `android-export.json` (só no release). O mesmo Gradle roda
  `assembleRelease bundleRelease`; o `.aab` sai ao lado do APK e entra no `android-report.json`. A assinatura do AAB é
  conferida pelo `keytool -printcert -jarfile` e tem de ser a mesma do APK; um `.aab` antigo no destino é apagado quando
  a opção está desligada. O keytool em pt_BR quebra no `-printcert` (`MissingFormatArgumentException`), por isso roda com
  `-J-Duser.language=en`.
- Painel "Android (Range)": caixa "Also build AAB (Google Play)" no release; `package-android.py --aab`. Traduções
  pt/es/ru em `translations_android.py`.
- Verificado: First Person em release com chave de teste, APK 51,8 MiB e AAB 21,9 MiB com o mesmo certificado.
  `bundletool build-apks --connected-device` (1.18.3) gerou os splits do Find X3 Pro (download ~22 MB, `.wasm`/`.data`
  sem compressão no master); `install-apks` instalou e o jogo abriu e renderizou com o controle na tela.

## 2026-09-24 - Controle na tela: layout `fps` (stick de olhar e clique) e áudio pausado em segundo plano

- Relato do usuário no First Person 0.1.6: em segundo plano o jogo pausa e volta de onde estava, mas a música
  continuava. Causa: o Web Audio do SDL (`Module.SDL2.audioContext`) segue tocando com a página escondida. A página
  agora suspende o contexto no `visibilitychange` e retoma ao voltar (só o que ela mesma suspendeu; se o SDL chamar
  `resume()` com a página escondida, suspende de novo). Verificado no `verify-capabilities.cjs audio` (novo item:
  `suspended` escondida, `running` ao voltar).
- Pedido do usuário: segundo direcional à direita para olhar e botão de tiro. Novo alvo **`look`** no stick: a
  página acumula o giro em `Module.rangePad.look` (frações da janela, curva quadrática, 1,5 janela/s) e
  `GHOST_SystemSDL::processWebLook()` o consome a cada quadro, movendo o cursor virtual do Web como um arrastar de
  dedo (só com o cursor escondido). Botões do mouse no alvo tecla: `DEV_InputDevice::PollVirtualKeys` aceita
  `LEFTMOUSE`..`BUTTON7MOUSE` além das teclas, com origem separada do mouse físico (`ConvertButtonEvent` registra o
  estado físico).
- Layout **`fps`**: stick esquerdo W/A/S/D, stick direito olhar, botões espaço e clique esquerdo. No painel Web
  ("Primeira pessoa (WASD + olhar)", pt/es/ru), em `--touch-layout` e no `range_web/touch.py` (WEB-INPUT-001).
- Cena de teste `make_pad_project.py`: cursor escondido com `reCenter()`, logs `[pad] mouse LEFT down/up` e
  `[pad] look dx= dy=`. `verify-touch.cjs` ganhou a seção do `fps`: 30/30 no Edge headless. 124 testes puros OK;
  builds `build-web-release` e nativo (`RangeRuntime`, `RangeEngine`) com código 0.
- APK debug do First Person 0.1.7 (versionCode 3, `--touch-layout fps`) instalado no Find X3 Pro e aprovado pelo
  usuário (pausa da música, stick de olhar e botão de tiro).

## 2026-09-24 - Controle na tela aprovado no First Person (A1 concluído)

- APK debug do First Person (`com.anastaciogames.firstperson` 0.1.6, versionCode 2) com o layout `wasd` e o
  runtime release, instalado no Find X3 Pro; o usuário jogou e aprovou. Fecha o item 5 da T4 e o A1.
- Nota de uso: o layout `wasd` é um direcional que aperta teclas, não quatro botões W/A/S/D; o Espaço é o ␣.
- Docs: roadmap, `android-export-plan.md`, `android-touch-controls-plan.md` e `android-manual-tests.md`.

## 2026-09-24 - Addon Cutscene Shot Tool em inglês com tradução

- `addons/addon_editor_shot_tool.py` (`1.0.1` → `1.0.2`): rótulos, dicas, títulos dos grupos, nomes dos campos e
  mensagens passaram do português ao inglês; o português original virou tradução pt/es/ru (38 textos no bloco
  `MESSAGES` de `range_web/translations_labels.py`). Mensagens via `tip_()` com `%s`; a contagem do painel usa
  `iface_()` com `translate=False`. "Effects" e "Shake" não têm tradução no catálogo do Blender e entraram na tabela.
- A cópia em `tools/ProjetoCutscene/scripts/addon_shot_tool.py` (projeto de exemplo, versão 1.0.0) não mudou.
- Conferido no motor: o addon liga, "New Camera Shot" cria `CamShot_01` com 13 propriedades e a mensagem sai no
  idioma escolhido; rótulos traduzidos em pt/es/ru. `engine_i18n.py`, `engine_web_ui.py`, os 124 testes puros e
  `bugfix_regression/run_all.py` passam. Não conferido na janela real.

## 2026-09-24 - Operadores da Range com texto-fonte em inglês e tradução

- Mensagens e dicas que estavam escritas em português no código passaram ao inglês, como no painel Web, e o
  português original virou tradução (pt/es/ru no bloco `MESSAGES` de `range_web/translations_labels.py`):
  `flowmenu/operators/open_external_editor.py` (dica, item "System Default", três mensagens),
  `flowmenu/functions/create_component_wizard.py` (três mensagens), `flowmenu/custom_pt_physics.py` (dica do Set Drive
  Type e itens FWD/RWD/AWD) e `bl_ui/properties_particle.py` (três mensagens do Import Debug Values). As mensagens
  de `self.report` passam por `pgettext_tip`, porque o `report` não traduz sozinho.
- Com a tradução desligada (padrão de fábrica), o editor mostra esses textos em inglês; com pt ligado, o texto é o
  mesmo de antes.
- Conferido no motor: os quatro operadores registram com a dica em inglês e `pgettext_tip` devolve pt/es/ru.
  `engine_i18n.py`, `engine_web_ui.py` e os 124 testes puros seguem OK. Não conferido na janela real.
- Na mesma rodada, as 32 mensagens `self.report` que já estavam em inglês no flowmenu (`custom_pt_properties.py`,
  `component_reload_new.py`, `create_component.py`, `register_component.py`, `create_component_wizard.py`) e no
  painel de veículo passaram por `tip_()`, com moldes `%s` no lugar de concatenação/`format`; traduções pt/es/ru no
  mesmo bloco `MESSAGES` (48 textos no total, `%s` conferido entre as línguas). No motor, o operador de criar
  componente mostrou "Erro: Selecione um objeto com Game Physics!" em pt e o russo em ru. `bugfix_regression/run_all.py`
  também passa.
- Fica de fora: o addon opcional `addon_editor_shot_tool.py` (UI em português) e o código gerado para o jogo
  (template do `VehiclePlayerComponent`, que imprime no console do jogo).

## 2026-09-24 - Tradução dos textos de interface em C fora do RNA (scan estático)

- Novo `tools/tests/web_profile/i18n_scan_c.py` (roda no motor): lê os `.c/.cc/.cpp` de `source/source` (fora
  `makesrna`, já coberto pelo `i18n_audit.py`) e lista os literais de `IFACE_`, `TIP_`, `N_`, `CTX_IFACE_` e `CTX_N_`
  (junta literais adjacentes; resolve `BLT_I18NCONTEXT_*`) que o `pgettext` não traduz. 1 300 textos distintos; antes,
  131 sem tradução em pt_BR, 128 em es e 221 em ru_RU.
- Novo `range_web/translations_c.py` (pt_BR/es/ru, 78 textos), registrado junto do `translations_labels.py`
  (tradução existente vence): diálogo de fechar sem salvar e títulos das janelas da Range (`wm_window.c`), editor de
  drivers, logic bricks (Animation sensor, Skip dt), sockets de nós novos (Principled Hair/Volume, sprites), outliner.
- Depois: pt_BR 73, es 70 e ru_RU 163. Em pt/es restam só códigos (X:, RGB, Hex, Ctrl), nomes (Python, Range
  Engine), portas lógicas (And, Or, Xor) e palavras iguais nas duas línguas. Os 90 a mais do ru são lacunas do
  catálogo russo do Blender 2.79 (dicas de modal, Principled BSDF, mensagens de biblioteca), não textos da Range.
- `engine_i18n.py` confere um texto em C em pt/es/ru; `engine_web_ui.py` e os 124 testes puros seguem OK.
  Não conferido na janela real.

## 2026-09-24 - Tradução dos textos fixos dos layouts Python (scan estático)

- Novo `tools/tests/web_profile/i18n_scan_labels.py` (roda no motor): lê com `ast` os `.py` de
  `release/scripts/startup` e lista os textos literais passados a `label`, `operator`, `prop`, `menu` etc.
  (`text=` ou `label("...")`, respeitando `text_ctxt` e `translate=False`) que `pgettext_iface` não traduz. Cobre o que
  o `i18n_audit.py` (só RNA) não via. 2 378 textos distintos; antes, 895 sem tradução em pt_BR e 898 em es (ru não medido antes).
- Novo `range_web/translations_labels.py` (pt_BR/es/ru, 997 textos), registrado depois dos outros dicionários
  (`setdefault`: tradução já existente vence). Cobre sobretudo os painéis do game engine (Game, Física, Mundo,
  Input System, cutscene, componentes, menus da Range) e menus do Blender que o catálogo 2.79 não traduz. Textos
  que o catálogo traduz num idioma e não em outro ficam nas três línguas, para as tabelas manterem as mesmas chaves.
- Depois: pt_BR 72, es 74 e ru 30 sem tradução no scan, todos nomes próprios (Range Engine - Discord), códigos
  (X/Y/Z, FXAA, ORM, AWD/FWD/RWD) ou palavras iguais nas duas línguas (Sensor, Material). A auditoria RNA também
  cai um pouco (pt_BR 1 286 → 1 279, ru 1 958 → 1 940).
- `engine_i18n.py` confere um rótulo fixo em pt/es/ru; `engine_web_ui.py` e os 124 testes puros seguem OK.
  es/ru pedem revisão nativa. Não conferido na janela real do editor. Textos em C fora do RNA seguem sem scan.

## 2026-09-24 - Controle na tela: checklist do celular no navegador e no Find X3 Pro (A1, etapa T4)

- `tools/web/verify-touch.cjs` passou de 19 para 25 conferências, cobrindo no Edge headless os critérios do plano
  que antes só estavam na lista do celular: dois botões juntos (A+B, engine vê `buttons=[0, 1]`), dedo do stick
  arrastado até em cima do botão A (continua no stick e não aperta A), soltar fora do controle, `touchcancel` com
  stick e botão apertados, e página escondida (`visibilitychange`, troca de app) com o stick apertado. Tudo solta
  sem entrada presa.
- Mudança do plano: a cena de teste da T4 é a do pad (`make_pad_project.py`), que já registra eixos, botões,
  teclas e a ação do Input System, e sai no logcat `RangeWeb` no APK; o multitoque fica no `verify-touch.cjs`,
  sem modo novo no `verify-capabilities.cjs`.
- Roteiro do aparelho escrito no plano (T4). Itens 1 a 4 aprovados no Find X3 Pro pelo usuário: APK
  `com.anastaciogames.pad` da cena `pad`, layouts stick e `wasd`, logcat sem entrada presa (detalhes em
  `android-manual-tests.md`). Falta o First Person com `wasd` no aparelho.

## 2026-09-24 - Controle na tela: layout no painel Web e aviso de entrada sem toque (A1, etapa T3)

- Properties > Scene > Web (Range) ganhou **Controle na tela** (nenhum, stick + 2 botões, d-pad + 4 botões, dois
  sticks, stick como WASD + espaço, d-pad como setas + espaço/Enter) e **Modo do stick** (onde o dedo toca ou no
  canto). O Exportar Web passa `--touch-layout/--touch-stick` ao empacotador, que grava `touch_controls` no
  `manifest.json`. O painel Android mostra o mesmo campo: o APK embute o pacote Web, então a config não foi para o
  `android-export.json` (decisão registrada no plano).
- Nova regra WEB-INPUT-001 (`range_web/touch.py`, aviso, evidência potencial): sensor Keyboard com tecla que o
  layout não aperta, sensor Joystick com botão/stick que o layout não tem, ação do Input System sem nenhum binding
  alcançado (todas as entradas do binding precisam estar no layout; clique esquerdo e movimento do mouse contam,
  porque o toque fora dos controles vira mouse). Com controle desligado, um só aviso informativo. Não vê
  `logic.keyboard` lido em Python.
- Correção: os mapas do Input System (`KeyMapping/*.json`, lidos pelo motor ao lado do `.range`) não entravam no
  pacote Web; o export do editor agora os inclui. `make_pad_project.py` gera `KeyMapping/Pad.json` com a ação
  "Pular" (espaço ou botão A) e `verify-touch.cjs` confere as duas vias no navegador (19/19). Isso também fecha a
  pendência da T0 de conferir um binding `JOYSTICK` com o pad virtual.
- Traduções pt/es/ru do painel e das mensagens. "Stick", "Dynamic" e "Fixed" viraram "Stick mode", "Where the
  finger touches" e "In the corner": o catálogo do Blender traduz os primeiros ("Bastão", "Фикс") e vence o nosso.
- Testes: `test_range_web.py` +5 (teclas dos layouts conferidas contra o template, sensores, mapas, layout
  desligado), 124 puros OK; `engine_collect_bpy.py` (JSON no pacote, aviso com stick e sem aviso com wasd) e
  `engine_web_export.py` (layout do painel no manifest e na página) sem falhas; `engine_i18n`, `engine_web_ui` e
  `engine_android_export` sem falhas. Não testado: celular.

## 2026-09-24 - Controle na tela: alvo tecla para jogos que leem teclado (A1, etapa T2)

- O controle na tela também aperta teclas. Na página, stick e d-pad aceitam `keys` (cima, baixo, esquerda, direita;
  o stick vira tecla depois de meio curso, diagonal aperta duas) e o botão aceita `key`, com os nomes de
  `bge.events` (`WKEY`, `SPACEKEY`, …). O controle com alvo tecla não mexe no gamepad. Novos layouts: `wasd`
  (stick = W/A/S/D, botão = espaço) e `arrows` (d-pad = setas, espaço e Enter).
- `Module.rangePad.keys` leva os códigos de `bge.events` (tabela na página na ordem de `SCA_EnumInputs`, conferida
  contra o `bge.events` no teste). `DEV_InputDevice::PollVirtualKeys` lê por `EM_JS` a cada quadro, chamado em
  `LA_Launcher::EngineNextFrame` logo depois dos eventos do sistema. Teclado físico e toque ficam em estados
  separados e o evento só muda com o estado combinado: soltar o toque não solta W que o teclado segura, e vice-versa.
  No build nativo o poll não faz nada. Chega ao sensor Keyboard, a `logic.keyboard` e aos bindings `KEYBOARD` do
  Input System (mesma tabela de entradas).
- Removido o `printf("[web-input] ...")` de depuração que sobrou em `DEV_EventConsumer::HandleKeyEvent`.
- `TOUCH.layout` aceita também a lista de controles (para a config do projeto na T3).
- `verify-touch.cjs` 16/16 no Edge headless: as 10 de gamepad e, no `wasd`, códigos W=45/SPACE=8/UPARROW=72 iguais
  aos do `bge.events`, stick para cima + botão dão `keys [45,8]` sem eixo nem botão de gamepad, o jogo vê W e espaço
  apertados e soltos, W segurado no teclado (CDP) continua quando o toque solta e sobe quando o teclado solta. Cada
  layout abre numa aba nova: recarregar na mesma aba deixava o toque do CDP sem chegar à página. D-pad do `arrows`
  conferido à parte (diagonal = ↑ e →). Build Web e nativo sem erro. Aceite do usuário no Edge do PC (`wasd` com
  mouse e teclado físico). Não testado: celular, First Person com `wasd`.

## 2026-09-24 - Controle na tela: overlay com stick, d-pad e botões (A1, etapa T1)

- `package-web.py` desenha o controle na página (HTML/CSS, sem custo na cena) e escreve `Module.rangePad`, que a T0
  já entrega como gamepad 0. Cada controle segue um dedo (`pointerId` + pointer capture): mover e apertar ao mesmo
  tempo funciona, e arrastar para fora do controle não solta nem aciona outro. Toques fora dos controles seguem para
  o canvas (arrastar para olhar continua). Tudo solta em `blur`, `visibilitychange`, `pagehide`, giro da tela e
  `pointercancel`.
- Layouts: `stick` (stick esquerdo + A/B, padrão), `dpad` (d-pad de 8 direções nos botões DPAD do SDL + A/B/X/Y),
  `twin` (dois sticks, eixos 0-1 e 2-3). Stick dinâmico (nasce onde o dedo toca, na zona inferior da metade da
  tela) ou fixo; zona morta radial de 10 %. Tamanho por `vmin` e margens por `env(safe-area-inset-*)`
  (`viewport-fit=cover`).
- Aparece só em `pointer: coarse` (celular, WebView do APK) ou com `?touch=1`; `?touch=0`, `?touchlayout=` e
  `?touchstick=` para testar. Padrão do pacote por `--touch-layout` (`none` desliga) e `--touch-stick`; o editor ainda
  usa o padrão (seletor na T3). Com `?debug=1` o log mostra `[touch] axes ... | buttons ...`.
- `tools/web/verify-touch.cjs`: 10/10 no Edge headless com toque emulado pelo CDP — stick até a borda dá LX 1,
  botão A junto, engine vê os dois (`axes=[1.0, 0.0, …] buttons=[0]`) e o sensor A dispara; soltar só o A mantém o
  stick; soltar tudo zera; diagonal solta ao perder o foco; toque fora dos controles não mexe no pad. D-pad
  conferido à parte (diagonal cima-direita aperta UP+RIGHT, baixo só DOWN, soltar zera).
- Com o controle USB ligado no PC, `verify-pad.cjs` falha nas 3 checagens que esperam "sem gamepad" (o índice 0 é o
  físico); anotado no cabeçalho dele. Conferido pelo usuário no Edge do PC com `?touch=1`, usando o mouse como
  dedo: funciona. Não testado: celular (toque real, entalhe, WebView do APK).

## 2026-09-24 - Controle na tela: ponte do gamepad virtual (A1, etapa T0)

- Levantamento e caminho do A1 completo em [android-touch-controls-plan.md](android-touch-controls-plan.md): overlay
  HTML (Pointer Events) alimentando o input existente, com alvo gamepad ou tecla; estende o Range Input System em
  vez de criar sistema paralelo. O joystick virtual do SDL não está habilitado na porta Emscripten
  (`SDL_config_emscripten.h` sem `SDL_JOYSTICK_VIRTUAL`), por isso a ponte é da engine.
- `DEV_Joystick` lê `Module.rangePad` (`active`, `axes[6]` em -1..1 na ordem do SDL GameController, `buttons` em
  máscara de bits) a cada quadro, por `EM_JS` no molde do `logic.motion`. Com o pad ativo, o índice 0 existe mesmo
  sem controle físico (nome "Range Virtual Pad"); com controle físico no 0, os dois se somam (eixo: o mais empurrado
  vence; botão: qualquer um). Controle físico que chega com o pad sozinho abre na mesma instância. Pad desligado
  remove o índice 0 virtual. `SyncLiveState` usa o estado somado, então o sensor Joystick também dispara.
- Corrigido de passagem: `GetName()` com controle ausente construía `std::string` de ponteiro nulo;
  leitores de eixo/botão não chamam mais o SDL com controle nulo.
- `package-web.py` expõe `Module.rangePad` (inativo; o overlay vem na T1).
- Cena `tools/tests/web_profile/make_pad_project.py` e `tools/web/verify-pad.cjs` (escreve `Module.rangePad` pelo
  CDP): 7/7 no Edge headless com `build-web-release` — sem pad `joysticks[0]` vazio; pad ativo vira
  `joysticks[0]` com eixos (1, -0.5, …, 0.25) no Python; botão A em `activeButtons` e sensor Joystick down/up;
  pad desligado remove o gamepad.
- Controle USB real ("Standard Gamepad") no Edge do PC, com o usuário: sozinho, eixos/botões/sensor A funcionam;
  com o pad ligado (LX 0.5 + B), o eixo fica 0.5 com o físico solto e vira -1.0 quando empurrado ao fim, e os botões
  se somam (`[0, 1]`, `[1, 9]`); ao desligar o pad o eixo volta a 0 e o B solta na hora, e o físico segue
  funcionando sozinho (stick ±1, botões, sensor A). Aba minimizada pausa o jogo (sem leitura). Não testado:
  Input System (mesmo `DEV_Joystick`, sem teste próprio), celular.

## 2026-09-24 - Export Android: release assinado

- Build type Release liberado. Chave PKCS12 (RSA 4096, ~27 anos) criada pelo keytool do JDK: botão "Criar chave"
  no painel (padrão `~/RangeAndroidKeys/<applicationId>.jks`) ou `package-android.py --create-keystore`. Recusa
  caminho dentro de repositório git e nunca sobrescreve uma chave existente.
- `android-export.json` ganha `keystore` e `keyAlias`; a senha nunca é gravada. Vem de
  `RANGE_ANDROID_KEYSTORE_PASSWORD` (terminal, ou pedida por `getpass`) ou do campo "Senha da chave"
  (`WindowManager.range_android_password`, `SKIP_SAVE`, fora do `.blend`). O template lê chave, alias e senha
  do ambiente (`signingConfigs` só existe com `RANGE_ANDROID_KEYSTORE`), então nada fica no projeto temporário.
- Antes do Gradle, `keytool -list` confere senha e alias (erros claros em vez da exceção do Gradle). Depois,
  `apksigner verify --print-certs`; o relatório ganha `signing` com o SHA-256 do certificado.
- Catálogos es/ru do Android completados: `engine_i18n.py` falhava em "es/ru cobrem as mesmas chaves do pt_BR"
  desde o commit do A3/A4.
- Verificado: `test_android.py` (20 testes, com criação real de chave, senha errada, alias inexistente e recusa
  dentro do git), `engine_android_export.py` e `engine_i18n.py` sem falhas; release do First Person pelo terminal
  com chave temporária (APK assinado, senha ausente de `gradle.log`, JSON e relatório); debug continua igual.
  No aparelho (app de teste separado): release v1 instalado e v2 atualizado por cima com a mesma chave,
  `firstInstallTime` mantido; com a cena `web-save`, v3 `SAVED` e v4 por cima `LOADED` (save preservado).

## 2026-09-24 - Export Android pelo editor e pelo terminal (A3/A4, APK debug)

- Novo `range_web/android.py` (sem bpy): confere o pacote do export Web por `SHA256SUMS.txt`, copia
  `tools/android/webview-template` para `%TEMP%/range-android-build/` (sem `build/`, `.gradle/` nem o `www/` de teste),
  põe o jogo em `assets/www` (sem `serve.py`/`HOSTING.md`), aplica `applicationId`, nome, `versionName`/`versionCode`,
  ícone PNG (`mipmap-xxxhdpi`) e orientação (`fullUser`/`sensorLandscape`/`sensorPortrait`) e roda `assembleDebug`.
  Saída: APK, `android-export.json` usado, `android-report.json` (hashes, template, JDK/SDK) e `gradle.log`.
  O namespace Kotlin continua `com.anastaciogames.rangewebview`; só o `applicationId` muda.
- JDK/SDK: `JAVA_HOME`/`ANDROID_HOME`, depois Android Studio (registro do Windows e `%LOCALAPPDATA%\Android\Sdk`),
  depois as pastas do painel. Sem JDK, SDK, platform 37 ou build-tools: erro com o que instalar; nada é instalado.
- `adb`: instala por cima com `install -r` e abre o jogo; erros claros para aparelho ausente, não autorizado,
  assinatura diferente (não desinstala, para não apagar o save) e versão mais nova no aparelho.
- Painel "Android (Range)" (`bl_ui/properties_android.py`, `Scene.range_android`), abaixo do painel Web: campos,
  "Gerar APK" (exporta o Web antes se o pacote estiver ausente ou mais velho que o `.range`) e "Instalar no celular".
  Gradle e adb rodam numa thread com operador modal; em modo background, direto. Traduções em
  `range_web/translations_android.py`.
- `tools/web/package-android.py`: mesma lógica pelo terminal (`--web`, `--config` ou `--app-id/--name`, `--install`).
- Release assinado ainda bloqueado com mensagem ("use debug").
- Verificado: `test_android.py` (15 testes), `engine_android_export.py` no editor em background (APK gerado de uma cena
  vazia, sem celular "Instalar" cancela com mensagem) e APK do First Person pelo terminal (`aapt`: id
  `com.anastaciogames.firstperson`, nome e versão certos). Primeiro `assembleDebug` em ~8 s com o cache do Gradle.
- Aceite: APK do First Person gerado pelo painel e instalado no Find X3 Pro com "Instalar no celular"; aprovado
  pelo usuário. Correções do aceite: "Gerar APK" salva o arquivo modificado antes de exportar (antes recusava e o
  aviso sumia no topo) e o painel mostra o último erro/resultado abaixo dos botões. `engine_android_export.py` só
  chama "Instalar" com `RANGE_ANDROID_TEST_INSTALL=1` (tinha instalado o app de teste no celular ligado).

## 2026-09-24 - APK e Web: rotação em paisagem e retrato

- APK: `screenOrientation` passa de `sensorLandscape` para `fullUser` (as quatro direções, respeitando o bloqueio
  de rotação do sistema). No APK o `index.html` sempre ajusta o canvas à tela.
- `package-web.py`: `fitCanvas` usa uma proporção fixa do jogo, adotada quando o runtime cria a janela com a
  resolução do `.range` (MutationObserver em `width/height`). Antes media por `canvas.width/height`, que o SDL
  troca pelo tamanho CSS a cada resize: a imagem abria achatada em pé (960x540 x 640x480) e se deformava a cada giro.
  Vale também para a tela cheia no navegador.
- `GHOST_SystemSDL.cpp` (Web): no resize da janela o cursor virtual do mouse-look é reescalado para a nova
  janela. Ficava no centro antigo e a câmera do First Person virava um pouco a cada giro.
- Aprovado pelo usuário no Find X3 Pro com o First Person ("ficou muito bom").

## 2026-09-24 - APK: botão "Tela cheia" escondido dentro do app

- `MainActivity` acrescenta `RangeWebView/1` ao user agent do WebView. O `index.html` de `package-web.py` procura
  essa marca e não mostra o botão "Tela cheia" dentro do APK, que já abre imersivo. No navegador nada muda.
- Verificado no Edge headless com o user agent sobrescrito pelo CDP (botão visível sem a marca, oculto com ela).
  APK debug recompilado com o pacote `motion` e o runtime release (`build-web-release/bin`), instalado no
  Find X3 Pro: botão ausente e Home/retorno com a cena seguindo sem recarregar.
- Orientação: o giro de 180° em paisagem funciona com o `sensorLandscape` atual. Em pé a imagem não vira retrato,
  e o jogo continua só em paisagem por decisão do usuário. Um `OrientationEventListener` próprio foi testado e
  descartado: não era necessário.
- First Person no APK: o WebView do Android não tem pointer lock e rejeita o pedido do runtime (cursor oculto)
  com `UnknownError: If you see this error we have a bug...`, que a página mostrava como erro fatal. O
  `index.html` de `package-web.py` troca `Element.prototype.requestPointerLock` por um no-op só dentro do APK
  (marca `RangeWebView/`); no navegador nada muda. Jogo roda, áudio `running`, usuário confirmou.
- `AndroidManifest.xml`: `launchMode="singleTask"`. Tocar no ícone com o jogo aberto por `adb shell am start`
  criava uma segunda Activity por cima, com dois jogos rodando.
- Medida por CDP, jogo parado, 1200 frames: APK 50,3 e 59,9 fps médios em duas rodadas (p50 16,7 ms); Chrome do
  aparelho com o mesmo pacote 37,5 fps (p50 33,3 ms, uma rodada). Números preliminares
  ([android-manual-tests.md](android-manual-tests.md)).
- Música ausente no APK não era do WebView: o `First_Person.range` local é uma versão antiga sem o script da
  música. Com o `.range` publicado em `gh-pages` a saída de áudio mede pico 0,65 (antes 0); usuário ouviu.
- Save no APK: `web-save.range` grava (`SAVED`), o app é encerrado por `am force-stop` e a sessão seguinte lê
  (`LOADED`). O IndexedDB do WebView persiste entre execuções.
- Cuidado ao reempacotar para o APK: `build-web/bin` pode estar com runtime de depuração (SAFE_HEAP); usar
  `--runtime-dir build-web-release/bin`.
