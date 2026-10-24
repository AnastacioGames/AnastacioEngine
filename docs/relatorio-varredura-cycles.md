# Relatório de varredura — Cycles

Data: 2026-09-25. Base `ab4883d5`, 639 arquivos em `source/intern/cycles/`.
Detalhes de cada correção e teste: `docs/changelog-arquivo.md` (2026-09-25 e 2026-09-26).

## Estado

CYC-001 a CYC-012 corrigidos e compilados. CUDA portado para GPUs atuais (8.x a 12.x, CUDA 13) e validado na
RTX 5060 no Linux e no Windows em 2026-09-26. OpenCL validado no Windows (RX 6800M). Testes CPU de regressão
cobrem CYC-001 a CYC-005 e CYC-011.

## Corrigidos

- CYC-001 — `path_write_binary()` ignorava falha de `fwrite`/`fclose`: corrigido em 2026-09-25.
- CYC-002 — contagens IES sem limite antes de `resize()`: corrigido em 2026-09-25.
- CYC-003 — largura × altura em `int` (buffers, tiles, sessão): corrigido em 2026-09-25.
- CYC-004 — `path_read_binary()` repassava `SIZE_MAX`: corrigido em 2026-09-25.
- CYC-005 — soma/offset das tabelas IES em `int`: corrigido em 2026-09-25.
- CYC-006 — `_cycles.opencl_compile()` sem validar argumentos: corrigido e testado (zero args, índice texto).
- CYC-007 — `mem_copy_from()` OpenCL multiplicava em `int`: corrigido em 2026-09-25.
- CYC-008 — CUDA aceitava carga com só o cubin de filtro: corrigido em 2026-09-25.
- CYC-009 — `mem_copy_from()` CUDA multiplicava em `int`: corrigido em 2026-09-25.
- CYC-010 — escape errado no comando Python de compilação OpenCL: corrigido em 2026-09-25.
- CYC-011 — parser IES sem terminador `\0`: corrigido, `cycles_util_ies_test` 13/13.
- CYC-012 — upscale de `util_image_resize_pixels()` deixava a saída vazia: corrigido em 2026-09-25.

## Aberto: validações funcionais pendentes

Fora do alcance em CPU/memória comum ou sem infraestrutura de teste:

- CYC-001: writer injetado/disco cheio; esperar `false` e nenhum cache aceito como completo.
- CYC-002/CYC-005: corpus IES com contagens inválidas e com muitas tabelas válidas (offsets `-1`, sem truncar).
- CYC-003: dimensões no limite da RNA e produtos acima de `INT_MAX`; a falha deve ser só por memória real.
- CYC-004: trocar/remover o arquivo entre abrir e medir; esperar `false` com vetor vazio.
- CYC-006: ampliar para cinco, sete argumentos e índice negativo, quando houver suíte do binding.
- CYC-007: cópia OpenCL acima de 2 GiB; offset/tamanho corretos ou falha limpa.
- CYC-008: com CUDA, remover só o cubin de render; esperar falha com mensagem, sem lançar kernel.
- CYC-009: com CUDA, cópia de buffer acima de 2 GiB.
- CYC-010: compilação OpenCL separada com caminho/nome contendo barra, apóstrofo e quebra de linha.
- OpenCL no Linux: sem máquina Linux com GPU AMD (o WSL não serve). Já está no roadmap (Linux x86_64).
- Corpus automatizado de IES e corridas de I/O, se a infraestrutura de testes de Cycles for ativada.

## Limitações conhecidas (não são defeito ativo)

| Local | Observação | Decisão |
| --- | --- | --- |
| `device/device_network.cpp`, `.h` | Device de rede não compila com `WITH_CYCLES_NETWORK=ON` (`:533` erro de sintaxe, `:502` tipo), entra em laço a 100% de CPU se o cliente cai, desreferencia `archive` nulo após falha de `RPCReceive`, sem autenticação e com cabeçalho de até 4 GiB. | Manter `WITH_CYCLES_NETWORK=OFF`. Reativar exige redesenho do protocolo. O upstream removeu esse device. |
| `kernel/osl/osl_services.cpp:388,1260-1281` | `get_array_attribute()` e point cloud retornam "não suportado". | Limitação do OSL herdado. OSL segue inviável (exige OSL 1.9 com LLVM antigo). |
| `render/mesh_subdivision.cpp:562` | Subdivisão de `ATTR_ELEMENT_VERTEX_MOTION` sem implementação. | Lacuna de motion blur + subdivisão; testar antes de priorizar. |
| `render/mesh_subdivision.cpp:260` | Interpolação FVar de atributos de canto pendente. | Lacuna conhecida, sem corrupção. |
| `blender/addon/__init__.py:127-166` | `unregister()` não chama `engine.exit()` nem tira o `atexit`. | Desregistrar→registrar→desregistrar passou; monitorar. |
| `addon/osl.py` | `except` nus. | Trocar por exceções específicas se OSL voltar. |

## Alertas descartados

- Motion normal em `blender_mesh.cpp`: descartado, o atributo só existe se a normal existir.
- `subd_attributes.add()` com UV: descartado, `AttributeSet::add()` redimensiona antes de escrever.
- `memcmp` de `Transform`/`DecomposedTransform`: descartado, blocos compactos de `float4`.
- `BVHReference::operator=` com `memcpy`: descartado, campos escalares; só código antigo.
