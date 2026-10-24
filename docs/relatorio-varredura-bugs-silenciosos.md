# Relatório de varredura: bugs silenciosos (`source/source/blender`)

Roteiro reutilizável: [checklist-varredura-bugs-silenciosos.md](checklist-varredura-bugs-silenciosos.md).
Histórico detalhado de cada rodada: `docs/changelog-arquivo.md` (2026-09-03 e 2026-09-24).

## Estado

- Rodada de 2026-09-03 nos 25 subdiretórios, reauditada em 2026-09-24.
- 26 itens: 20 corrigidos, 6 descartados. Nenhuma dívida sem decisão.
- Regressão automática: `tools/tests/bugfix_regression/run_all.py` (ANIM-001, MOD-001, RND-001).
- A pasta `python` (129 arquivos) teve só triagem; não conta como auditada por completo.
- A varredura de `source/source/gameengine/` (2026-09-02) está no histórico Git e no changelog.

## Aberto

### GPU-001 — `GPU_texture_convert_pixels()` com `int` de tamanho

- **Local:** `source/source/blender/gpu/intern/gpu_texture.c:80-92, 196`.
- **Correção feita:** a função recebe `size_t length` e usa `size_t` no laço; o call site 2D passa
  `(size_t)w * (size_t)h`. O call site 3D está em `#if 0` (ver GPU-002).
- **Falta:** teste manual numa sessão interativa já aberta. Em `--background` não há contexto GL, e
  `gl_load()` chamado cedo via `--python` bloqueia. `bpy.data.images.new(float_buffer=True)` não materializa
  dados nesta base, então o teste antigo não valia; o script agora pula o caso.
- Overflow real (textura com mais de 2^31 pixels) segue fora de automação segura.

## Corrigidos

- PHYS-001 — `cp_bfmatrix` sem checar destino: descartado (tamanhos iguais por construção); assert defensivo
  adicionado em 2026-09-03.
- AVI-001 — AVI ignorava erro de `fwrite`/`fseek`/`fclose`: corrigido em 2026-09-03, completado em 2026-09-24.
- ANIM-001 — keying set com `array_index` fora do intervalo: corrigido em 2026-09-03, coberto pela regressão.
- ANIM-002 — preview do pose library não revertia constraints no ESC: corrigido em 2026-09-03. Só testável à mão
  (operador modal); registrado como validação impraticável, não como trabalho aberto.
- ANIM-003 — `bezt_remap_times()` com intervalo nulo gerava NaN: corrigido em 2026-09-03 (build OK; cena real
  não testada).
- RND-001 — voxel data `.bvox` com overflow e vazamento no erro: corrigido em 2026-09-03, coberto pela regressão.
- PY-001 — `Py_DECREF` duplo em `mathutils.noise.voronoi()`: corrigido em 2026-09-03 (build OK; sem teste em
  Python debug/ASan).
- BLN-001 — `strcpy` no identificador de socket: corrigido em 2026-09-03.
- BLN-003 — `adt->overrides` não lido nem liberado: corrigido em 2026-09-03, ownership em 2026-09-24. Nada na
  base cria overrides; validado por inspeção e build.
- MESH-001 — `crazyspace` com polígono de menos de 3 loops: corrigido em 2026-09-03.
- MESH-002 — `UVProject` com face de zero loops: corrigido em 2026-09-03.
- MOD-001 — bind do Mesh Deform com produto sem limite: corrigido em 2026-09-03, coberto pela regressão.
- MEDIA-001 — intervalo de frames da reconstrução sem validação: corrigido em 2026-09-03, completado em
  2026-09-24.
- MEDIA-002 — extensão de proxy além de `FILE_MAX`: corrigido em 2026-09-03.
- BPROP-001 — `BKE_bproperty_set()` com `strcpy`: corrigido em 2026-09-03.
- BPROP-002 — nome inicial de propriedade com `strcpy`: corrigido em 2026-09-03 (preventivo).
- BL-001 — cópia de arquivo ignorava falha de escrita: corrigido em 2026-09-03.
- FONT-001 — `fseek`/`ftell` sem checagem na leitura de fonte: corrigido em 2026-09-03.
- BLT-001 — `msgfmt` ignorava erro de escrita: corrigido em 2026-09-03; build não validado (alvo `msgfmt`
  ausente no grafo Ninja).
- DATATOC-001 — `datatoc` com seek/tamanho inválido: corrigido em 2026-09-03, completado e testado em
  2026-09-24.

## Descartados

- PHYS-002 — tamanho do bake de fluido: descartado, as duas expressões são iguais.
- GPU-002 — textura 3D com `#if 0`: descartado, `type` é sempre `GL_FLOAT`.
- PY-002 — `Py_DECREF(sub)` em `bgl.c`: descartado, é a referência temporária correta.
- BLN-002 — `malloc(100)+strcpy`: descartado, código morto em `#if 0`.
- BLN-004 — cache do modificador Collision: descartado, a leitura já reseta tudo.
- Cabeçalho AVI de stream inválido após o 1º frame: descartado em 2026-09-24, o 1º frame o regrava.
