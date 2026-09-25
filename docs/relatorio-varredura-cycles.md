# Relatório de varredura — Cycles

Data: 2026-09-25
Estado: CYC-001 a CYC-005 corrigidos e validados por compilação. Permanecem apenas validações funcionais direcionadas e a cobertura das variantes desativadas.

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

### Validação funcional ainda recomendada

- CYC-001: teste com writer injetado/volume sem espaço; esperar `false` e nenhuma entrada de cache aceita como completa.
- CYC-002: corpus IES com contagem negativa, zero, enorme e produto acima do limite; esperar rejeição limpa, sem alocação desproporcional.
- CYC-005: corpus com muitas tabelas IES válidas; confirmar que o excedente resulta em offsets `-1`, sem truncamento.
- CYC-003: teste unitário para dimensões no limite da RNA e para produtos acima de `INT_MAX`; confirmar que a falha seguinte é somente por limite real de memória, não por overflow.
- CYC-004: simular remoção ou troca de arquivo entre abrir e consultar tamanho; confirmar `false` com vetor vazio.

## Observações estranhas ou limitações (não promovidas a defeito ativo)

| Local | Observação | Avaliação |
| --- | --- | --- |
| `util/util_image_impl.h:129-170` | A função pública de resize aloca a saída para `scale_factor > 1`, mas o ramo de upscale só tem `TODO` e deixa os pixels sem preencher. O único chamador atual (`render/image.cpp:668`) inicia em 1 e só reduz a escala, portanto esse ramo não é alcançado no fluxo atual. | Corrigir antes de reutilizar a API para upscale; não há regressão ativa demonstrada. |
| `render/mesh_subdivision.cpp:562` | A subdivisão de `ATTR_ELEMENT_VERTEX_MOTION` está explicitamente sem implementação. | Lacuna funcional para motion blur + subdivisão, dependente do caminho de cena; requer teste de render específico antes de priorizar. |
| `render/mesh_subdivision.cpp:260` | Interpolação FVar de atributos de canto está marcada como pendente. | Lacuna conhecida de atributos/subdivisão, não evidência de corrupção nesta varredura. |
| `device/device_network.cpp` | Há TODOs de espera ocupada e liberação em erro de rede. | Variante não compilada (`WITH_CYCLES_NETWORK=OFF`); manter no backlog de configuração de rede. |
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
- `ninja bf_intern_cycles`, no ambiente MSVC configurado: sucesso (`ninja: no work to do`).
- Binário instalado `build/bin/RangeEngine.exe`: addon Cycles já estava habilitado pelas preferências locais. A tentativa de registrá-lo novamente falhou corretamente com `register_class(... already registered ...)`; não é falha de inicialização.
- No processo isolado, a sequência `cycles.unregister(); cycles.register(); cycles.unregister()` terminou com os três marcos de sucesso e saída normal.
- A análise estática não cobriu compilação real de CUDA/OpenCL/OSL porque essas opções estão desabilitadas no build auditado. Três TUs AVX2 também não puderam ser analisadas pelo frontend clang-tidy por intrínseca MSVC `__lzcnt32`; o alvo Ninja permaneceu válido.

## Próximas prioridades sugeridas

1. Cobrir as variantes CUDA/OpenCL/OSL/rede em build separado antes de habilitá-las para usuários.
2. Adicionar corpus automatizado para entradas IES e corridas de I/O, se a infraestrutura de testes de Cycles for ativada neste fork.
