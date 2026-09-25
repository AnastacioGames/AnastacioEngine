# Relatório de varredura — Cycles

Data: 2026-09-25
Estado: CYC-001 a CYC-011 corrigidos e validados por compilação. Permanecem apenas validações funcionais direcionadas e a cobertura das variantes desativadas.

## Escopo e método

- Base examinada: `ab4883d5` (25/09/2026). O diretório principal possui 639 arquivos e 156.091 linhas em `source/intern/cycles/`.
- Cobertura por tipo: 130 `.cpp`, 359 `.h`, 26 `.cl`, 3 `.cu`, 88 `.osl`, 9 `.py`, 22 `.txt` e 2 `.cmake`.
- Foram incluídos os pontos de integração diretos: CMake de Cycles, bridge `_cycles`, addon Python instalado, editor/player e RNA de resolução de render.
- Varreduras mecânicas: marcadores TODO/FIXME/XXX/HACK (174 ocorrências), padrões de I/O/alocação, parse de todos os 9 Python e análise estática sobre 110 unidades C++ presentes no banco de compilação atual. Cada alerta foi lido no contexto antes de entrar abaixo.
- Configuração auditada: `WITH_CYCLES=ON`, `WITH_OPENSUBDIV=ON`, `WITH_CYCLES_LOGGING=ON`; CUDA, OpenCL, OSL e rede estão desligados neste build. Arquivos dessas variantes receberam somente leitura/análise estática, não execução.

## Achados para corrigir

| ID | Prioridade | Local | Condição / efeito |
| --- | --- | --- | --- |
| CYC-001 | Corrigido | `source/intern/cycles/util/util_path.cpp:690` | `path_write_binary()` agora retorna `false` se `fwrite()` não gravar todos os bytes ou se `fclose()` falhar no flush. Os chamadores de cache OpenCL já respeitam esse retorno. |
| CYC-002 | Corrigido | `source/intern/cycles/util/util_ies.cpp:117` | Contagens de tilt e dos eixos IES agora permanecem em `long` até serem validadas. O parser rejeita eixos nulos/negativos, mais de 4.096 ângulos por eixo e mais de 1.048.576 amostras antes de `reserve()`/`resize()`; o limite também deixa margem para os espelhamentos do processamento. |
| CYC-003 | Corrigido | `source/intern/cycles/render/buffers.cpp`, `render/tile.cpp` e `blender/blender_session.cpp` | Produtos de largura × altura (e passes) são promovidos para `size_t`, `uint64_t` ou `int64_t` antes da multiplicação. Isso elimina overflow de `int` para dimensões aceitas pela RNA, inclusive 65.536², em alocação, cópia, progresso e pixels de tile. |
| CYC-004 | Corrigido | `source/intern/cycles/util/util_path.cpp:592,716` | `path_read_binary()` trata o sentinela `(size_t)-1` de `path_file_size()` e leitura parcial como falha, limpa o vetor e retorna `false`; não repassa `SIZE_MAX` a `vector::resize()`. |
| CYC-005 | Corrigido | `source/intern/cycles/util/util_ies.cpp:48` e `source/intern/cycles/render/light.cpp:1008` | O limite de CYC-002 mantém uma IES individual representável em `int`; o empacotamento de todas as IES agora soma em `size_t` e confirma que tabela + dados cabem em `INT_MAX`, pois os offsets vão ao kernel como `int`. Se não couber, envia tabela com offsets `-1`, em vez de truncar a soma ou o offset. |
| CYC-006 | Corrigido | `source/intern/cycles/device/opencl/opencl_util.cpp:447` | A API Python interna `_cycles.opencl_compile()` passava diretamente um vetor externo a seis acessos por índice e a `std::stoi()`. Argumentos ausentes, texto não numérico ou índice negativo podiam causar acesso inválido/exceção no processo de compilação em segundo plano. Agora exige exatamente seis argumentos e aceita somente índice decimal não negativo representável em `int`. |
| CYC-007 | Corrigido | `source/intern/cycles/device/opencl/opencl_split.cpp:1000` | `OpenCLDevice::mem_copy_from()` multiplicava `elem * y * w` e `elem * w * h` como `int` antes de convertê-los para `size_t`. Em buffers grandes, o overflow podia transformar offset/tamanho em valores incorretos na leitura do buffer OpenCL. As multiplicações agora começam em `size_t`. |
| CYC-008 | Corrigido | `source/intern/cycles/device/device_cuda.cpp:561` | `CUDADevice::load_kernels()` reaproveitava `result` para o módulo de filtro: se o cubin de render falhasse e o de filtro carregasse, retornava `true` e chamava `reserve_local_memory()` com `cuModule = 0`. Ali `cuModuleGetFunction()` falhava e o código seguia com `CUfunction` e `num_threads_per_block` não inicializados até `cuLaunchKernel()`. Agora cada módulo tem seu resultado, a carga só tem sucesso com os dois, e `reserve_local_memory()` retorna antes de configurar/lançar o kernel se a busca da função ou o cálculo de ocupação falhar. |
| CYC-009 | Corrigido | `source/intern/cycles/device/device_cuda.cpp:972` | Mesmo padrão de CYC-007 no CUDA: `mem_copy_from()` calculava `elem * y * w` e `elem * w * h` em `int`. Com buffer de 2 GiB ou mais (ex.: 8192 × 8192 com 8 floats por pixel), o valor negativo virava `size_t` enorme; `cuMemcpyDtoH()` falhava e a render era perdida, ou o `memset` do ramo só-host escrevia fora do buffer. As multiplicações agora começam em `size_t`. |
| CYC-010 | Corrigido | `source/intern/cycles/device/opencl/opencl_util.cpp:395` | A serialização do comando Python de compilação externa usava strings brutas e um suposto escape de apóstrofo que não continha barra invertida em C++. Nomes de dispositivo ou caminhos com apóstrofo quebravam `--python-expr`. Agora usa literal Python comum e escapa barras, apóstrofos e quebras de linha. |
| CYC-011 | Corrigido | `source/intern/cycles/util/util_ies.cpp:83` | `IESTextParser` construía um `vector<char>` sem terminador, porém chamava `strstr`/`strtod` e acessava `data[0]` como string C. Um IES sem quebra de linha final podia ler além do fim. Agora o buffer recebe `\\0` antes do parse. |

### Validação funcional ainda recomendada

- CYC-001: teste com writer injetado/volume sem espaço; esperar `false` e nenhuma entrada de cache aceita como completa.
- CYC-002: corpus IES com contagem negativa, zero, enorme e produto acima do limite; esperar rejeição limpa, sem alocação desproporcional.
- CYC-005: corpus com muitas tabelas IES válidas; confirmar que o excedente resulta em offsets `-1`, sem truncamento.
- CYC-003: teste unitário para dimensões no limite da RNA e para produtos acima de `INT_MAX`; confirmar que a falha seguinte é somente por limite real de memória, não por overflow.
- CYC-004: simular remoção ou troca de arquivo entre abrir e consultar tamanho; confirmar `false` com vetor vazio.
- CYC-006: com um build `WITH_CYCLES_DEVICE_OPENCL=ON`, chamar `_cycles.opencl_compile()` com zero, cinco, sete, índice negativo e índice não numérico; esperar `False`, sem encerrar o processo.
- CYC-007: com OpenCL habilitado, copiar uma região cuja multiplicação de dimensões exceda `INT_MAX`; confirmar offset e tamanho corretos ou falha limpa por limite real do driver.
- CYC-008: com CUDA habilitado, corromper ou remover só o cubin de render mantendo o de filtro; esperar falha de carga com mensagem, sem lançamento de kernel.
- CYC-009: com CUDA habilitado, render cuja cópia de buffer ultrapasse 2 GiB; confirmar a leitura completa ou falha limpa por limite real de memória.
- CYC-010: com OpenCL habilitado, executar compilação separada usando caminho/nome com barra invertida, apóstrofo e quebra de linha; confirmar que o processo recebe os valores originais e não produz erro de sintaxe Python.

## Observações estranhas ou limitações (não promovidas a defeito ativo)

| Local | Observação | Avaliação |
| --- | --- | --- |
| `util/util_image_impl.h:129-170` | A função pública de resize aloca a saída para `scale_factor > 1`, mas o ramo de upscale só tem `TODO` e deixa os pixels sem preencher. O único chamador atual (`render/image.cpp:668`) inicia em 1 e só reduz a escala, portanto esse ramo não é alcançado no fluxo atual. | Corrigir antes de reutilizar a API para upscale; não há regressão ativa demonstrada. |
| `render/mesh_subdivision.cpp:562` | A subdivisão de `ATTR_ELEMENT_VERTEX_MOTION` está explicitamente sem implementação. | Lacuna funcional para motion blur + subdivisão, dependente do caminho de cena; requer teste de render específico antes de priorizar. |
| `render/mesh_subdivision.cpp:260` | Interpolação FVar de atributos de canto está marcada como pendente. | Lacuna conhecida de atributos/subdivisão, não evidência de corrupção nesta varredura. |
| `device/device_network.cpp`, `device/device_network.h` | **Device de rede não suportado e inseguro.** Três defeitos confirmados por leitura: (1) não compila com `WITH_CYCLES_NETWORK=ON`: `device_network.cpp:533` tem `(void*)? ...` (erro de sintaxe) e `:502` atribui `device_ptr` (inteiro) a `void*`; (2) se o cliente cai sem enviar `stop`, `DeviceServer::listen()` (`:333`) e `task_release_tile()` (`:718`) não consultam `have_error()` e ficam em laço a 100% de CPU, sem aceitar nova conexão; (3) quando `RPCReceive` falha no cabeçalho/dados, `archive` fica nulo, mas os chamadores seguem com `rcv.read()` (ex.: `NetworkDevice::load_kernels`, `:195`) e desreferenciam nulo. Além disso, o protocolo não tem autenticação, aceita cabeçalho de até 4 GiB e valida ponteiros vindos do par só com `assert`: qualquer host da rede local que conecte na porta 5120 derruba o servidor. | Manter `WITH_CYCLES_NETWORK=OFF` e não oferecer a usuários. Correções pontuais dos três defeitos não resolvem a segurança do protocolo; reativar exige redesenho (autenticação, limites e validação de mensagens). O Cycles upstream removeu esse device em versões posteriores. |
| `device/device_cuda.cpp:397-407`, `kernel/kernels/cuda/kernel_config.h:86-88`, `CYCLES_CUDA_BINARIES_ARCH` | CUDA parado na geração de 2019: `kernel_config.h` só conhece arquiteturas até 7.x e dá `#error` para sm_80+ (RTX 30/40/50); a lista de binários pré-compilados termina em sm_75; `compile_check_compiler()` trata CUDA 10.1 como a única versão suportada, e o CUDA 12+ já não gera sm_3x (padrão da lista). Mesmo ligando CUDA, GPUs NVIDIA atuais ficam sem kernel. | Backlog de portabilidade, não correção pontual: adicionar perfis de registradores/launch bounds para 8.x/9.x, atualizar a lista de arquiteturas e a versão de CUDA esperada, e validar com toolkit NVIDIA e GPU real. |
| `kernel/osl/osl_services.cpp:388,1260-1281` | `get_array_attribute()` e as três operações de point cloud retornam imediatamente “não suportado” (`false`/`0`). | Limitação deliberada do backend OSL herdado. Ao reativar OSL, documentar que shaders que dependam desses recursos não funcionam; implementar exige backend de atributos/point cloud, não um patch pontual. |
| `blender/addon/__init__.py:127-166` | `unregister()` não chama `engine.exit()` nem retira o callback `atexit`; o callback é desduplicado no próximo `register()`. | A sequência isolada desregistrar→registrar→desregistrar passou. Tratar como assimetria de ciclo de vida a monitorar, não como falha confirmada. |

## Alertas analisados e não promovidos

- A análise estática sinalizou acessos de atributos de motion normal em `blender_mesh.cpp`. A criação de `ATTR_STD_MOTION_VERTEX_NORMAL` é condicionada à existência do atributo normal, preservando a invariável usada nas cópias; não foi confirmado acesso nulo.
- O alerta sobre `subd_attributes.add()` e UV em `blender_mesh.cpp` é coberto por `AttributeSet::add()`: o conjunto está associado a `subd_mesh` e redimensiona o atributo antes da escrita.
- `memcmp` de `Transform` e `DecomposedTransform` não foi promovido: ambos são blocos compactos de `float4` no layout atual. O alerta é conservador sobre padding.
- `BVHReference::operator=` usa `memcpy`, mas seus campos atuais são escalares e `BoundBox`; ficou como código antigo a simplificar, sem defeito observável demonstrado.
- Os `except` nus de `addon/osl.py` ficam em caminho OSL, que está desligado. Eles são pouco diagnósticos, mas não entraram como defeito confirmado; preferir exceções específicas quando OSL for reativado.

## Verificações executadas

- CYC-001: `util_path.cpp` recompilado explicitamente e `lib/cycles_util.lib` relinkada com sucesso no ambiente MSVC. `git diff --check` passou. O alvo agregado `bf_intern_cycles` não possuía dependência pendente depois desse relink.
- CYC-002: limites revisados contra as expansões de `process_type_b()`/`process_type_c()`; `util_ies.cpp` recompilado e `lib/cycles_util.lib` relinkada com sucesso no ambiente MSVC.
- CYC-005: `light.cpp` recompilado e `lib/cycles_render.lib` relinkada com sucesso no ambiente MSVC.
- CYC-003/CYC-004: `buffers.cpp`, `tile.cpp`, `blender_session.cpp` e `util_path.cpp` compilados no MSVC. A revisão posterior confirmou os quatro objetos atualizados (`ninja: no work to do`); não houve render de 65.536², pois exigiria memória inviável.
- CYC-006/CYC-007/CYC-010: build isolado `build_opencl_validate/` configurado com `WITH_CYCLES_DEVICE_OPENCL=ON`; `device_opencl.cpp`, `opencl_util.cpp` e `opencl_split.cpp` foram compilados com `-DWITH_OPENCL`. A RX 6800M e a Radeon integrada expõem OpenCL 2.1 e são aceitas pelo backend. O link do alvo completo parou nos objetos CPU SSE/AVX por `Permission denied`, fora do backend OpenCL; por isso as chamadas Python, a cópia maior que 2 GiB e a compilação externa com caracteres especiais permanecem testes funcionais pendentes.
- CYC-008/CYC-009: build separado `build_cuda/` (cache copiado de `build/` com `WITH_CYCLES_DEVICE_CUDA=ON`, `WITH_CUDA_DYNLOAD=ON`, `WITH_CYCLES_CUDA_BINARIES=OFF`), sem tocar no `build/` compartilhado. `ninja cycles_device extern_cuew` compilou `device_cuda.cpp` com `-DWITH_CUDA -DWITH_CUDA_DYNLOAD` (via cuew, sem toolkit NVIDIA) sem avisos e linkou `lib/cycles_device.lib`. Não houve execução: não há GPU/toolkit CUDA configurado nesta máquina e os kernels `.cu` não foram compilados.
- CYC-011: `util_ies.cpp` recompilado e `cycles_util_ies_test` executado com 13/13 casos, inclusive IES válido sem quebra de linha final.
- Kernels `.cu` (`kernel.cu`, `kernel_split.cu`, `filter.cu`): assinaturas conferidas contra os argumentos que `device_cuda.cpp` passa em cada `cuLaunchKernel()`; contagem, ordem e tipos batem.
- `ninja bf_intern_cycles`, no ambiente MSVC configurado: sucesso (`ninja: no work to do`).
- Binário instalado `build/bin/RangeEngine.exe`: addon Cycles já estava habilitado pelas preferências locais. A tentativa de registrá-lo novamente falhou corretamente com `register_class(... already registered ...)`; não é falha de inicialização.
- No processo isolado, a sequência `cycles.unregister(); cycles.register(); cycles.unregister()` terminou com os três marcos de sucesso e saída normal.
- A análise estática não cobriu compilação real de CUDA/OpenCL/OSL porque essas opções estão desabilitadas no build auditado. Três TUs AVX2 também não puderam ser analisadas pelo frontend clang-tidy por intrínseca MSVC `__lzcnt32`; o alvo Ninja permaneceu válido.

## Próximas prioridades sugeridas

1. Cobrir as variantes CUDA/OpenCL/OSL em build separado antes de habilitá-las para usuários. A rede fica fora: não suportada/insegura (ver observações).
2. Portar CUDA para arquiteturas e toolkits atuais (sm_80+, CUDA 12+) antes de qualquer oferta de render em GPU NVIDIA.
3. Adicionar corpus automatizado para entradas IES e corridas de I/O, se a infraestrutura de testes de Cycles for ativada neste fork.
