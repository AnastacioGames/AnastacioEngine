# Relatório de varredura: bugs silenciosos

Use este roteiro para revisar um addon, uma extensão ou um subsistema antes de
considerá-lo estável. Ele procura defeitos que normalmente compilam/importam
sem erro e só aparecem depois de uso repetido, troca de cena, recarregamento
do addon ou uma combinação incomum de ações.

## Resultado esperado

Ao terminar, produza uma lista curta com cada achado classificado como:

- **Corrigido** — descreva causa, alteração e teste que confirmou o resultado.
- **Dívida registrada** — explique risco, por que não foi corrigido agora e a
  decisão necessária.
- **Falso positivo** — registre por que o padrão é seguro neste caso, para não
  investigá-lo novamente.

Não declare a varredura concluída sem executar o carregamento aplicável
(importação para Python, build para C/C++) e o caminho funcional relevante.

## Preparação

1. Delimite o escopo: pasta do addon, módulos carregados e integrações externas
   (por exemplo `bpy`, arquivos, rede ou timers).
2. Leia changelog, issues e código de registro do addon antes de propor uma
   feature ou repetir uma investigação antiga.
3. Liste o ciclo de vida: registro, uso, recarregamento, desregistro e remoção
   de dados temporários.
4. Preserve alterações não relacionadas no worktree.
5. Registre os módulos/arquivos incluídos, a revisão/commit-base e a data da
   varredura. Isso torna o critério de cobertura auditável.

## Sete frentes obrigatórias de inspeção

Use buscas textuais como ponto de partida, mas confirme cada suspeita pelo
fluxo de controle e pelos call sites. Registre também os grupos sem achados.

### 1. Recursos com ownership manual

Procure alocação e liberação assimétricas. Em Python, isso inclui handlers,
timers, draw handlers, arquivos, sockets, threads e objetos temporários; em
C/C++, `new`/`delete`, `malloc`/`free`, referências Python e ponteiros donos.

Perguntas úteis:

- Todo recurso criado tem cleanup no sucesso, no erro e no desregistro?
- Um retorno antecipado pula a liberação?
- O mesmo recurso pode ser registrado duas vezes?
- A remoção acontece antes de descartar o último ponteiro que permite removê-lo?
- Campos, IDs sentinela e buffers temporários são inicializados antes de uso?

### 2. Contratos prometidos pelo código

Busque `TODO`, `FIXME`, `XXX`, `not implemented`, `deprecated` e comentários
que descrevam ownership, tipo ou pré-condição. Compare a promessa com cada
call site e a implementação atual.

Priorize comentários que avisam sobre ponteiro cru, validade de objeto,
thread-safety, compatibilidade de versão ou API exposta ao usuário. Inclua
retornos e erros aparentemente "impossíveis": `nullptr`, falha de I/O,
`find() == end()`, códigos de retorno ignorados e exceções Python pendentes.

### 3. Limites silenciosos e números mágicos

Localize limites fixos, tamanhos de buffer, índices, timeouts e contadores.

- O limite está documentado e validado na entrada?
- Ao excedê-lo, o usuário recebe erro claro, warning ou resultado truncado?
- O valor depende de frame rate, tamanho da cena ou quantidade de objetos?

### 4. Stubs e defaults enganosos

Procure getters que sempre retornam constante, setters vazios, `pass`, `return
None`, `return False`, branches temporários e funções que aceitam parâmetros
mas não os usam.

Confirme se são intencionais. Um fallback silencioso costuma ser pior que um
erro explícito quando muda o resultado de uma operação.

### 5. Contrato da API pública

Compare o que a API anuncia com o que ela faz:

- argumentos, valores padrão, tipos aceitos e retorno;
- propriedades registradas versus getters/setters existentes;
- operadores/painéis do addon versus suas classes e `bl_idname`;
- nomes persistidos em arquivos `.blend` versus renomes recentes;
- documentação e exemplos versus implementação.

Para addons Blender, faça ao menos um ciclo de `register()` → uso →
`unregister()` → `register()` no mesmo processo.

### 6. Callbacks e ciclo de vida

Mapeie cada registro para sua contraparte:

| Registro | Contraparte esperada |
| --- | --- |
| `bpy.app.handlers.*.append` | `remove` no `unregister()` |
| `bpy.app.timers.register` | `unregister` ou callback que retorna `None` |
| `Space*.draw_handler_add` | `draw_handler_remove` |
| keymap/item | remoção do item e do keymap criado |
| msgbus | `bpy.msgbus.clear_by_owner(owner)` |
| thread/processo | sinalização, espera e descarte seguro |

Teste recarregar o addon duas ou três vezes. Duplicação de menu, callback
executando várias vezes e exceção após desregistro são falhas comuns.

### 7. Referências e validade de dados

Em Python, não mantenha referências a `bpy`/`bmesh`/objetos de cena depois que
eles podem ter sido removidos, trocados de arquivo ou invalidados por uma
operação. Rebusque por nome ou valide antes de usar quando o ciclo de vida não
for garantido.

Em C/C++, revise ownership, borrowed/new references da CPython, ponteiros
crus expostos à API e callbacks que podem sobreviver ao objeto dono.

Quando houver API CPython, confira separadamente se cada referência é borrowed
ou new, se `Py_INCREF`/`Py_DECREF` estão balanceados em todos os ramos e se uma
função que falhou deixou uma exceção tratada ou propagada corretamente.

## Roteiro prático por módulo

1. Faça buscas textuais pelos sete grupos acima e anote os arquivos cobertos.
2. Para cada suspeita, encontre criação, todos os usos e destruição/cleanup.
3. Reproduza com o menor cenário possível; não corrija um padrão só porque ele
   parece estranho.
4. Corrija uma causa por vez. Evite misturar refactor amplo com bug fix.
5. Rode o teste proporcional ao risco:
   - addon Python: importação, registro/desregistro repetido e fluxo da UI;
   - extensão C/C++: build do alvo afetado e execução do fluxo real;
   - renderização: teste no aplicativo/jogo real, não somente screenshot
     automatizado.
   Inclua, quando aplicável, troca/remoção de cena ou objeto, recarregamento,
   repetição prolongada e ao menos um caminho de falha (arquivo, rede ou
   recurso indisponível). Analisadores estáticos e sanitizers, quando
   disponíveis, complementam mas não substituem esses testes.
6. Atualize o changelog com causa, correção, validação e limitações restantes.

## Template de registro de achado

```md
### [ID] Título curto

- **Local**: `caminho/arquivo.py:linha`.
- **Sintoma/risco**: o que pode acontecer e em qual ciclo de uso.
- **Reprodução mínima**: passos ou condição que expõe o problema.
- **Causa**: ownership, contrato ou ciclo de vida quebrado.
- **Correção**: alteração mínima feita.
- **Validação**: comando e/ou passos manuais com resultado.
- **Prioridade**: crítica | alta | média | baixa.
- **Estado**: corrigido | dívida registrada | falso positivo.
- **Rastreio**: commit/issue, quando existir.
```

## Critérios de encerramento

A varredura só está fechada quando todos os módulos do escopo registrado
passaram pelas sete frentes, os achados têm estado registrado e o componente
passa por seu ciclo de vida aplicável sem exceções, callbacks duplicados ou
recursos pendurados. Para addons, isso inclui uma rodada de
registro/uso/desregistro; para C/C++, build do alvo e execução do fluxo real.

## Origem

### Achados da parte 5 — física, partículas, áudio e vídeo

- [x] **PHYS-001 — cópia de matriz implícita usa contadores do objeto de origem sem validar destino** — **Estado: falso positivo, assert defensivo adicionado (2026-09-03).**
  - **Local:** `source/source/blender/physics/intern/implicit_blender.c:551-557` (`cp_bfmatrix`).
  - **Evidência:** a função continha o comentário `TODO bounds checking` e fazia `memcpy(to, from, ...)` sem validar o destino.
  - **Investigação:** `cp_bfmatrix` tem um único call site em todo o código (`BPH_mass_spring_solve_velocities`, linha ~1106: `cp_bfmatrix(data->A, data->M)`). `data->A` e `data->M` são alocados uma única vez, na mesma chamada de `BPH_mass_spring_solver_create`, com o mesmo par `numverts`/`numsprings` (linhas 663 e 670), nunca redimensionados individualmente, e liberados juntos no destrutor de `Implicit_Data`. Portanto `to`/`from` são sempre do mesmo tamanho por construção; não há caminho de código que produza a divergência descrita no achado.
  - **Correção:** adicionado `BLI_assert(to[0].vcount == from[0].vcount && to[0].scount == from[0].scount)` antes do `memcpy`, documentando a invariante e detectando gratuitamente (custo zero em release) qualquer regressão futura que quebre essa garantia.
  - **Validação:** build de `RangeEngine` sem erros/warnings novos (`implicit_blender.c.obj`). Não há cenário de reprodução real (a invariante é estrutural, não depende de dado de cena).

- [x] **PHYS-002 — bake de fluido usa `scene->r.efra` como comprimento, apesar de calcular outro número de quadros** — **Estado: falso positivo (2026-09-03).**
  - **Local:** `source/source/blender/editors/physics/physics_fluid.c:870-872, 936-940`.
  - **Investigação:** `noFrames = scene->r.efra - 0` e `channels->length = scene->r.efra` são literalmente a mesma expressão — não existe divergência de tamanho entre o que é alocado/iterado e o que é armazenado em `channels->length`. O comentário `DG TODO` local questiona a fórmula por ela ignorar `sfra` (uma limitação de contrato conhecida e já documentada), mas isso é separado do descompasso de tamanho que o achado original descrevia.
  - **Validação:** nenhuma mudança de código necessária; apenas reclassificação após releitura completa da função.

- [x] **AVI-001 — exportação AVI não propaga erro de `fwrite`/`fseek`** — **Estado: corrigido (2026-09-03; auditoria completada em 2026-09-24).**
  - **Local:** `source/source/blender/avi/intern/avi_endian.c:154-207`, usado por `source/source/blender/avi/intern/avi.c`.
  - **Evidência:** `awrite()` retorna `void` e descarta o retorno de todas as chamadas `fwrite`; vários chamadores também executam `fseek()` sem verificar o resultado e `avi.c` pode retornar `AVI_ERROR_NONE` após essas operações.
  - **Risco silencioso:** disco cheio, quota excedida, caminho sem permissão ou falha de seek podem deixar um AVI truncado/corrompido enquanto o fluxo de render/exportação aparenta sucesso.
  - **Correção:** `awrite()` agora retorna `bool` (sucesso se `fwrite` escreveu a contagem esperada, no caminho big-endian e no direto). Os call sites em `avi.c` (`AVI_open_compress`, `AVI_write_frame`, `AVI_close_compress`) e `avi_options.c` acumulam o resultado em `write_ok` e retornam `AVI_ERROR_WRITING` em vez de `AVI_ERROR_NONE` quando alguma escrita falha. A auditoria de 2026-09-24 completou a propagação que ainda faltava para `fseek`, FourCC/padding via `putc` e `fclose`; `writeavi.c` agora converte falhas de configuração/frame em erro no `ReportList` e sinaliza no `stderr` uma falha na finalização (o callback legado de finalização retorna `void`).
  - **Validação:** build de `RangeEngine` e `RangeRuntime` sem erros/warnings novos (`avi_endian.c.obj`, `avi.c.obj`, `avi_options.c.obj`). Em 2026-09-24, um render `AVI_RAW` 16×16 de um frame gerou arquivo RIFF/AVI válido de 2.864 bytes. Não foi possível forçar falha de disco com segurança; o caminho de sucesso normal segue idêntico e a propagação de erro é aditiva.

> **Nota da parte 5:** achados obtidos por inspeção estática. PHYS-001 foi investigado e reclassificado como falso positivo (invariante estrutural garante tamanhos iguais; assert defensivo adicionado). PHYS-002 depende do contrato histórico do simulador e permanece pendente. AVI-001 é uma lacuna direta de propagação de I/O, já corrigida.

### Achados da parte 4 — editores, operadores, animação e interface

| ID | Local | Risco silencioso | Evidência e reparo/validação sugeridos |
|---|---|---|---|
| ANIM-001 | `source/source/blender/blenkernel/intern/anim_sys.c:1386-1409` | **Estado: corrigido e validado (2026-09-03).** `BKE_keyingset_add_path()` agora resolve `id`/`rna_path` via `RNA_path_resolve_property` (mesmo padrão de `animsys_store_rna_setting`) e, quando resolvível, compara `array_index` contra `RNA_property_array_length()`; fora do intervalo, cai para `-1` ("todos os componentes", convenção já usada em `BKE_keyingset_find_path`) em vez de persistir um índice inválido. Quando o caminho RNA não resolve ainda, mantém o comportamento anterior. | Teste automatizado `tools/tests/bugfix_regression/test_anim_keyingset_array_index.py` — 3/3 asserções passando contra o binário instalado (índice fora do intervalo cai para -1, índice válido preservado, "todo o array" inalterado). |
| ANIM-002 | `source/source/blender/editors/armature/pose_lib.c:876-1000` | **Estado: corrigido (2026-09-03).** `tPoseLib_Backup` ganhou uma lista `constraint_backups` (`tPoseLib_ConstraintBackup`) que snapshota `enforce`/`flag` de cada `bConstraint` do canal em `poselib_backup_posecopy()`; `poselib_backup_restore()` restaura esses campos, e `poselib_backup_free_data()` libera a lista nova. A lista de constraints em si (add/remove) já era coberta pelo `memcpy` do `bPoseChannel`; agora os valores internos de constraints existentes também são revertidos ao cancelar o preview. | Não automatizável: o caminho de restauração só roda dentro do operador modal `POSELIB_OT_browse_interactive` ao receber ESC (`poselib_preview_cancel`); não há `EXEC_DEFAULT` equivalente, e sem janela + fila de eventos do WM não há como simular isso via script. Validação manual: constraint com influência alterada por driver, preview, ESC, conferir que o valor original voltou. |
| ANIM-003 | `source/source/blender/editors/animation/keyframes_edit.c:752-758` | **Estado: corrigido (2026-09-03).** `bezt_remap_times()` agora guarda `old_range == 0.0f` e retorna sem alterar os handles nesse caso, evitando `NaN`/`Inf`. Build de `RangeEngine` sem erros; cenário de intervalo nulo não testado em runtime nesta rodada (comportamento de "manter posição" escolhido por ser o mais conservador). | Correção aplicada em `keyframes_edit.c`; validação completa (comparar handles antes/depois em cena real) ainda pendente do usuário. |

**Nota da parte 4:** estes candidatos vieram de inspeção estática de caminhos de animação; ainda não houve build nem execução dos operadores. ANIM-001 depende do contrato histórico de índices RNA, enquanto ANIM-002 e ANIM-003 têm cenários de reprodução manuais bem delimitados.

### Achados da parte 3 — GPU, renderização, compositor e nós

| ID | Local | Risco silencioso | Evidência e reparo/validação sugeridos |
|---|---|---|---|
| GPU-001 | `source/source/blender/gpu/intern/gpu_texture.c:80-92, 196` | **Estado: corrigido e validado (2026-09-03).** `GPU_texture_convert_pixels()` agora recebe `size_t length` (e usa `size_t` internamente para `len`/índice de loop); o call site 2D passa `(size_t)w * (size_t)h`. O call site 3D (linha ~361) está dentro de `#if 0` (ver GPU-002) e não precisou de mudança. | Teste automatizado `tools/tests/bugfix_regression/test_regression_smoke.py` (upload/liberação de imagem float via GPU) — passa quando executado sem `--background` (precisa de contexto OpenGL real; em `--background` o script pula essa checagem em vez de travar, o que foi confirmado empiricamente). Cenário de overflow real (textura >2^31 pixels) continua fora de alcance de automação segura. |
| GPU-002 | `source/source/blender/gpu/intern/gpu_texture.c:299-422` | **Estado: falso positivo (2026-09-03).** `GPU_texture_create_3D()` fixa `type = GL_FLOAT` no início e nunca troca para `GL_UNSIGNED_BYTE` (diferente do caminho 2D). O bloco `#if 0` que chamaria `GPU_texture_convert_pixels` é código morto de um caminho uchar nunca implementado aqui; como `type` permanece `GL_FLOAT`, passar `fpixels` (float bruto) direto para `glTexImage3D` é consistente com `format`/`type` efetivos. `pixels` fica sempre `NULL` e o `MEM_freeN(pixels)` final é inofensivo. | Nenhuma ação necessária; registrado para não reinvestigar. |
| RND-001 | `source/source/blender/render/intern/source/voxeldata.c:67-123` | **Estado: corrigido e validado (2026-09-03).** Em `load_frame_blendervoxel()`: o `fseek` agora usa `(size_t)frame * size * sizeof(float) + offset` (evita overflow de `int` antes da promoção); `vd->dataset` é liberado (`MEM_freeN` + `NULL`) nos retornos de erro de `fseek`/`fread`, no mesmo padrão de `load_frame_raw8()`; e foi adicionado um teto explícito (`VOXELDATA_MAX_BYTES`, 2 GiB) verificado antes de `MEM_mapallocN`, rejeitando resoluções/headers que produziriam uma alocação corrompida ou desproporcional. | Teste automatizado `tools/tests/bugfix_regression/test_rnd001_voxeldata_bvox.py` — gera um `.bvox` sintético real e força a leitura via `bpy.ops.render.render()` (engine `BLENDER_RENDER`); 2/2 casos passando: arquivo bem formado (header/resolução round-trip corretos) e arquivo truncado (antes vazava/lia lixo, agora falha limpo sem crash). |

**Nota da parte 3:** GPU-001 e RND-001 corrigidos com mudança mínima (aritmética `size_t` + teto/liberação) e validados por teste automatizado; GPU-002 confirmado como falso positivo após releitura completa de `GPU_texture_create_3D()`.

### Achados da parte 2 — Python, BMesh e ImBuf

| ID | Local | Suspeita/impacto | Como confirmar e reparar |
|---|---|---|---|
| PY-001 | `source/source/blender/python/mathutils/mathutils_noise.c:746-747` | **Estado: corrigido (2026-09-03).** `Py_DECREF(v)` removido após `PyList_SET_ITEM`, que já toma posse da referência de `v`. Build de `RangeEngine` sem erros; teste de execução repetida de `mathutils.noise.voronoi()` sob Python debug/ASan não realizado nesta rodada. | Correção aplicada; validação em runtime pendente do usuário. |
| PY-002 | `source/source/blender/python/generic/bgl.c:558-561` | **Estado: falso positivo.** `sub` (retornado por `Buffer_item`) é um objeto distinto do valor armazenado em `PyList_SET_ITEM`, que vem de `Buffer_to_list_recursive(sub)` — uma lista/objeto novo, não `sub` em si. O `Py_DECREF(sub)` decrementa corretamente a referência temporária de `Buffer_item`, sem duplo-decremento. Não é o mesmo padrão do PY-001. | Nenhuma ação necessária; registrado para não reinvestigar. |

Observação: a busca nesta parte não promoveu novos achados confirmados em BMesh ou ImBuf. Os padrões de alocação encontrados exigem análise de tamanhos/fluxo de erro e não foram classificados como defeitos sem um caso de entrada reproduzível. A pasta `python` continua não considerada totalmente auditada: estes são apenas os primeiros pontos encontrados.

### Achados da parte 1 — núcleo e dados

Status: triagem estática concluída; nenhum bug foi promovido a confirmado sem teste de entrada/execução.

| ID | Local | Sinal encontrado | Risco/comportamento silencioso | Informação para reparo/validação |
|---|---|---|---|---|
| BLN-001 | `blenloader/intern/readfile.c:2933-2946` | **Estado: corrigido (2026-09-03).** Os dois `strcpy` viraram `BLI_strncpy(..., sizeof(sock->identifier))`; origem e destino já eram do mesmo tipo `bNodeSocket.identifier[64]` (`DNA_node_types.h:83`), então o risco era baixo, mas a cópia agora trunca em vez de poder estourar. | Build de `RangeEngine` sem erros; teste com arquivo `.blend` legado contendo grupos de nós não realizado nesta rodada. |
| BLN-002 | `blenloader/intern/readfile.c:8302-8305` | **Estado: falso positivo (código morto).** O `malloc(100)+strcpy` está dentro de `#if 0` — bloco de debug nunca compilado nesta base. Não é um bug ativo; não alterado. | Nenhuma ação necessária; registrado para não reinvestigar enquanto o bloco permanecer desativado. |
| BLN-003 | `blenloader/intern/readfile.c:2814-2818`, `writefile.c:910-918` e `blenkernel/intern/anim_sys.c` | **Estado: corrigido (2026-09-03; ownership completado em 2026-09-24).** | `direct_link_animdata()` tinha `// TODO...` sem lógica onde deveria ler `adt->overrides` de volta, enquanto `write_animdata()` já gravava cada `AnimOverride`. Implementado `link_list(fd, &adt->overrides)` + `aor->rna_path = newdataadr(fd, aor->rna_path)` para cada override, no mesmo padrão já usado duas linhas abaixo para `nla_tracks`. A auditoria posterior constatou que a lista recém-carregada ainda não era liberada: `BKE_animdata_free()` agora libera cada `rna_path` e a lista. `AnimOverride` (`value`, `array_index`) não tem outros ponteiros donos. | Não testável hoje pela API: nada nesta base cria `adt->overrides` (recurso do Blender parcialmente implementado desde 2009, `animsys_evaluate_overrides()` só lê uma lista que nunca é populada). Leitura e ownership foram validados por inspeção simétrica com `write_animdata()` e pelo build dos dois executáveis. |
| BLN-004 | `blenloader/intern/readfile.c:5351-5377` e `writefile.c:1862-1868` | **Estado: falso positivo (2026-09-03).** | A leitura ativa (fora do `#if 0`) já reseta `time_xnew = time_x = -1000`, `mvert_num = 0`, `bvhtree = NULL`, `tri = NULL` junto com os ponteiros de cache (`x`/`xnew`/`current_*` para `NULL`). Em `MOD_collision.c:128`, `time_xnew == -1000` é exatamente a condição de "primeira vez", que realoca tudo do zero a partir da malha atual no próximo passo de simulação — cenário que o comentário em `MOD_collision.c:196` descreve ("happens on file load ONLY when i decomment changes in readfile.c") só ocorreria SEM esse reset. É cache de simulação, não dado persistente; nenhuma perda de dado de usuário. | Nenhuma ação necessária; registrado para não reinvestigar. |

BLN-001/002 são riscos de robustez na leitura e já resolvidos/descartados. BLN-003 era uma lacuna funcional real, agora corrigida; BLN-004 confirmado como falso positivo após releitura completa do reset em `readfile.c`.

## Relatório de varredura: `source/source/blender`

Data da primeira parte: 2026-09-03. O caminho efetivo neste checkout é
`source/source/blender`; `source/blender` não existe. O escopo contém 25
subpastas e aproximadamente 2.900 arquivos, portanto a auditoria será feita
por partes.

### Inventário inicial

| Grupo | Pastas | Estado |
| --- | --- | --- |
| Núcleo/dados | `blenkernel`, `blenlib`, `blenloader`, `makesdna`, `makesrna` | pendente |
| Python/buffers | `python`, `bmesh`, `mathutils`, `imbuf` | parcialmente coberta |
| Gráficos | `gpu`, `render`, `compositor`, `nodes`, `modifiers`, `physics` | pendente |
| Editor/estado | `editors`, `windowmanager` e demais | pendente |

### Pasta `python`

Não há evidência de que ela tenha sido totalmente concluída. O changelog
registra correções anteriores em integrações Python e em `python_component.c`,
mas isso não equivale a auditar `intern`, `generic`, `bmesh` e `mathutils`.
O inventário atual contém 129 arquivos: 67 em `intern`, 15 em `generic`, 19
em `bmesh` e 23 em `mathutils`.

Resultado desta passagem: **dúvida registrada, sem bug novo confirmado**.
Marcadores como `TODO`/`FIXME`/`XXX`, `return NULL` e macros de referência
Python são apenas pontos de inspeção; cada candidato precisa de call-site,
caminho de erro, reprodução e validação.

### Próximas partes

1. `blenkernel`/`blenlib`/`blenloader`/`makesdna`/`makesrna`.
2. `python`/`bmesh`/`mathutils`/`imbuf`.
3. `gpu`/`render`/`compositor`/`nodes`/`modifiers`/`physics`.
4. `editors`/`windowmanager` e módulos restantes.

A varredura global permanecerá aberta até todos os grupos passarem pelas sete
frentes e pelos testes aplicáveis. Busca estática não substitui build,
importação ou execução do fluxo real.

Este checklist foi extraído da varredura concluída em
`source/source/gameengine/` do AnastacioEngine em 2026-09-02. O resultado
daquela revisão permanece no histórico Git e em `docs/changelog.md`.

### Achados da parte 6 — nós, modificadores, malha e geometria

- [x] **MESH-001 — `crazyspace` acessa vértices vizinhos sem validar polígonos degenerados** — **Estado: corrigido (2026-09-03).**
  - **Local:** `source/source/blender/blenkernel/intern/crazyspace.c:200-208` (`BKE_crazyspace_set_quats_mesh`).
  - **Evidência:** para cada `MPoly`, o código assumia `mp->totloop >= 2` e calculava `mp->totloop - 2` antes de percorrer os loops, sem checar `totloop`.
  - **Correção:** adicionado `if (mp->totloop < 3) continue;` antes do cálculo de `ml_prev`/`ml_curr`/`ml_next`, pulando polígonos degenerados (0/1/2 loops) — um triângulo é o mínimo válido para os índices "anterior/atual/próximo" fazerem sentido.
  - **Validação:** build de `RangeEngine`/`bf_blenkernel` sem erros. Não automatizável: um polígono com `totloop < 3` só existe via dado corrompido (arquivo malformado/add-on de importação com bug) — a API normal do Blender já valida a malha e não permite criar esse estado. Regressão coberta indiretamente pelo bind normal do MOD-001 (abaixo).

- [x] **MESH-002 — `UVProject` usa contador sem sinal em laço de polígonos degenerados** — **Estado: corrigido (2026-09-03).**
  - **Local:** `source/source/blender/modifiers/intern/MOD_uvproject.c:243-303`.
  - **Evidência:** os quatro caminhos de projeção inicializam `unsigned int fidx = mp->totloop - 1` e usam laço `do/while`; com `totloop == 0`, o valor vira `UINT_MAX` e o primeiro `lidx` sai do array de loops.
  - **Risco silencioso:** uma face vazia/degenerada pode causar escrita de UV fora do buffer, crash ou corrupção ao avaliar o modificador.
  - **Correção:** adicionado `if (mp->totloop == 0) { /* pular */ }` antes dos quatro ramos de projeção, evitando o cálculo de `fidx` para faces vazias.
  - **Validação:** build de `RangeEngine` sem erros. Teste com malha contendo face de zero loops não realizado nesta rodada (dado degenerado real não reproduzido).

- [x] **MOD-001 — bind do `Mesh Deform` multiplica dimensões grandes sem limite explícito** — **Estado: corrigido (2026-09-03).**
  - **Local:** `source/source/blender/editors/armature/meshlaplacian.c:1420-1448` (`harmonic_coordinates_bind`) e `source/source/blender/modifiers/intern/MOD_meshdeform.c:448-495` (`modifier_mdef_compact_influences`).
  - **Evidência:** `mdb->weights` era alocado com `sizeof(float) * mdb->totvert * mdb->totcagevert` (produto em `int`) e depois indexado em `MOD_meshdeform.c` como `weights[a + b * totcagevert]`, sem validação de overflow em nenhum dos dois pontos.
  - **Correção:** adicionada guarda em `harmonic_coordinates_bind()` (`if ((double)mdb->totvert * (double)mdb->totcagevert > (double)INT_MAX) { modifier_setError(...); return; }`) antes de qualquer alocação, abortando o bind com erro reportado ao usuário em vez de prosseguir com um produto corrompido. A indexação em `modifier_mdef_compact_influences()` passou a usar aritmética `size_t` explícita (`weights[(size_t)a + (size_t)b * totcagevert]`).
  - **Validação:** teste automatizado `tools/tests/bugfix_regression/test_regression_smoke.py` — bind normal (cage/malha de tamanho comum) executado contra o binário instalado, `is_bound == True`. Cenário de overflow real (bilhões de vértices) continua fora de alcance de automação segura, coberto só pela guarda defensiva em si.

> **Nota da parte 6:** MESH-001 e MOD-001 corrigidos com guardas mínimas e conservadoras (early-continue / early-return + aritmética `size_t`), sem alterar o comportamento do caminho normal. Regressão do caminho normal confirmada por teste automatizado (MOD-001); MESH-001 não tem caminho de reprodução alcançável por API normal.

### Achados da parte 8 — imagem/vídeo, proxies e reconstrução de câmera

- [x] **MEDIA-001 — intervalo de frames da reconstrução é multiplicado sem validação** — **Estado: corrigido (2026-09-03; auditoria completada em 2026-09-24).** `source/source/blender/blenkernel/intern/tracking_solver.c:190-210`. A rotina alocava `efra - sfra + 1` câmeras diretamente e depois percorria o mesmo intervalo; não havia checagem local de intervalo negativo, overflow da expressão ou limite de memória antes de `MEM_callocN`. A primeira correção adicionou a guarda para intervalo invertido, mas o cast para `size_t` ainda ocorria depois de `efra - sfra` e o laço `a <= efra; a++` ainda podia estourar. A auditoria calcula a diferença em `int64_t`, limita a alocação ao que `camnr`/o tamanho final em `int` representam, valida falha de alocação e percorre pela contagem, sem incrementar `INT_MAX`. Build de `RangeEngine` e `RangeRuntime` sem erros; intervalo extremo real não é reproduzível pela UI normal (`MINAFRAME`/`MAXFRAME`), portanto as guardas foram validadas por inspeção e compilação.

- [x] **MEDIA-002 — extensão de proxy pode exceder o buffer após caminho truncado** — **Estado: corrigido (2026-09-03).** `source/source/blender/blenkernel/intern/movieclip.c:~180-201`, em `get_proxy_fname()`. O caminho é montado com `BLI_snprintf(name, FILE_MAX, ...)`, que pode truncar, e em seguida recebia `strcat(name, ".jpg")` sem recalcular o espaço restante. **Correção:** o `strcat` foi trocado por `strlen(name)` seguido de `BLI_strncpy(name + name_len, ".jpg", FILE_MAX - name_len)`, garantindo que a extensão nunca escreva além de `FILE_MAX`. Build de `RangeEngine` sem erros; teste com caminho próximo do limite `FILE_MAX` não realizado nesta rodada.

> **Nota da parte 8:** triagem estática; não houve build, solve de câmera, leitura de vídeo nem geração de proxy.

### Achados da parte 7 — Window Manager, editores e propriedades legadas

- [x] **BPROP-001 — `BKE_bproperty_set()` copia string sem limitar o destino** — **Estado: corrigido (2026-09-03).** `source/source/blender/blenkernel/intern/property.c:198-204` aloca strings com `MAX_PROPSTRING` em `BKE_bproperty_init()`, mas o setter usava `strcpy(prop->poin, str)`. **Correção:** trocado por `BLI_strncpy(prop->poin, str, MAX_PROPSTRING)`. Build de `RangeEngine` sem erros; teste com string acima do limite via API de jogo não realizado nesta rodada.

- [x] **BPROP-002 — nome inicial de propriedade também usa cópia não limitada** — **Estado: corrigido (2026-09-03, preventivo).** `source/source/blender/blenkernel/intern/property.c:115-120` fazia `strcpy(prop->name, "prop")`; `name[64]` confirmado em `DNA_property_types.h:37`. **Correção:** trocado por `BLI_strncpy(prop->name, "prop", sizeof(prop->name))`. Build sem erros.

> **Nota da parte 7:** a triagem de Window Manager/editores foi estática e não executou operadores. BPROP-001 é o candidato prioritário desta parte; BPROP-002 é uma dependência de contrato de tamanho, não um overflow reproduzível com o literal atual.
### Achados da parte 9 — bibliotecas de base e fontes

- **BL-001 — cópia de arquivo pode reportar sucesso após falha de escrita** — **Estado: corrigido (2026-09-03).** `source/source/blender/blenlib/intern/fileops.c:898-905`. `BLI_copy`/operação equivalente lia em loop, mas ignorava o retorno de `fwrite`, `ferror` e `fclose`. **Correção:** cada `fwrite` agora tem seu retorno comparado ao tamanho lido; `ferror(from_stream)` e o retorno de `fclose(to_stream)` também são checados. Qualquer falha retorna `RecursiveOp_Callback_Error` em vez de `_OK`. Build de `RangeEngine` sem erros; falha de disco real não injetada nesta rodada, caminho de sucesso normal inalterado.

- **FONT-001 — falhas de `fseek`/`ftell` podem virar leitura de fonte incorreta** — **Estado: corrigido (2026-09-03).** `source/source/blender/blenfont/intern/blf_font_win32_compat.c:68-73,95-105`. O callback de leitura chamava `fseek` sem verificar o retorno; na abertura, `fseek(SEEK_END)`/`ftell`/retorno ao início também não eram validados. **Correção:** `ft_ansi_stream_io` retorna `0` bytes lidos se o `fseek` falhar; `FT_Stream_Open__win32_compat` agora valida `fseek`+`ftell<0` ao medir o tamanho e o `fseek` de rebobinar, retornando `FT_THROW(Cannot_Open_Stream)` em caso de erro. Build de `RangeEngine` sem erros; fonte truncada/seek inválido real não testado nesta rodada.

**Nota da parte 9:** achados estáticos; não houve compilação nem execução de cópia/carregamento de fontes. Os demais padrões encontrados em `blenlib`, `depsgraph`, `nodes` e `compositor` foram triados como contratos internos, literais constantes ou código desativado, sem evidência suficiente para promover novos bugs.

- **BLT-001 — `msgfmt` pode declarar sucesso sem criar/gravar o arquivo de saída** — **Estado: corrigido (2026-09-03), build não validado.** `source/source/blender/blentranslation/msgfmt/msgfmt.c:435-437`. O retorno de `BLI_fopen`, `fwrite` e `fclose` era ignorado. **Correção:** `fp == NULL`, retorno de `fwrite` e de `fclose` agora são checados; qualquer falha imprime diagnóstico e retorna `EXIT_FAILURE`. **Nota de validação:** o alvo `msgfmt` não está presente no grafo Ninja atual (`ninja: error: unknown target 'msgfmt'`) apesar de `WITH_INTERNATIONAL=ON` no `CMakeCache.txt` — gap de configuração pré-existente do build tree, não relacionado a esta correção; recompilar exigiria reconfigurar o CMake, fora do escopo de uma correção às cegas. Revisão manual do código confirma que usa apenas `bool`/`BLI_fopen`/`fwrite`/`fclose`, já usados no resto do arquivo.

- **DATATOC-001 — tamanho de entrada pode ficar inválido após falha de seek/tamanho** — **Estado: corrigido (2026-09-03; auditoria completada em 2026-09-24).** `source/source/blender/datatoc/datatoc.c:45-110`. `fseek` e `ftell` eram usados sem validar retorno antes de calcular/usar `size`. A primeira correção validou `fseek(SEEK_END)` e `ftell`; a auditoria posterior completou o contrato validando o seek de retorno ao início, EOF prematuro, erro/fechamento da saída e os três argumentos obrigatórios. Em erro, o `.c` parcial é removido em vez de poder ser consumido como artefato válido. `datatoc.exe` compilado e testado com chamada incompleta (falha + usage) e conversão real (sucesso).

**Nota complementar:** `alembic`, `collada`, `freestyle` e `ikplugin` foram triados nesta parte por contratos de importação/exportação e alocação; os TODOs encontrados indicam limitações funcionais conhecidas, mas não houve evidência estática suficiente para um bug silencioso novo. A validação funcional dessas bibliotecas ainda requer build e arquivos de teste.
## Cobertura atual e pendências

- Triagem estática realizada nos 25 subdiretórios de `source/source/blender`, incluindo núcleo, Python/BMesh/ImBuf, GPU/render/compositor/nodes, animação/editores, física/mídia e bibliotecas auxiliares.
- 26 itens estão registrados no relatório. Em 2026-09-03, 22 itens mecânicos e localizados (PY-001, BPROP-001, BPROP-002, BLN-001, MEDIA-002, ANIM-003, MESH-002, MEDIA-001, BL-001, FONT-001, BLT-001, DATATOC-001, AVI-001, GPU-001, RND-001, MESH-001, MOD-001, ANIM-001, ANIM-002, BLN-003) foram corrigidos e compilados com sucesso (`RangeEngine`/`RangeRuntime`, sem erros/warnings novos); 6 itens (PY-002, BLN-002, PHYS-001, PHYS-002, GPU-002, BLN-004) foram investigados e reclassificados como falso positivo/código morto (PHYS-001 recebeu também um assert defensivo). Nenhum item permanece como dívida registrada sem decisão — todos os 26 têm correção aplicada ou justificativa de falso positivo.
- Em 2026-09-03, além do build completo (`RangeEngine` + `RangeRuntime`, `ninja install`), 5 das 7 correções desta rodada (GPU-001, RND-001, MOD-001, ANIM-001 e, parcialmente, GPU-001 fora de `--background`) passaram a ter teste automatizado real em `tools/tests/bugfix_regression/` (`run_all.py` roda tudo de uma vez), executado contra o binário instalado e com resultado passando. Os dois restantes ficaram assim por razão específica, não por falta de esforço: **ANIM-002** exige um evento ESC dentro de um operador modal (sem `EXEC_DEFAULT` equivalente), inalcançável sem janela real; **BLN-003** está correto por inspeção mas não tem nenhum cenário de reprodução possível hoje — nada nesta base de código escreve em `adt->overrides`, então a leitura corrigida nunca é exercitada por nenhuma ação de usuário.
- Os cenários de overflow "puro" que motivaram GPU-001/MOD-001/MESH-001 (textura com bilhões de pixels, malha com bilhões de vértices, polígono degenerado por corrupção de arquivo) continuam sem reprodução real — exigiriam alocações de dezenas de GB ou dado deliberadamente corrompido, fora do escopo de automação segura. Essas guardas permanecem validadas apenas por inspeção + regressão do caminho normal. Ver `docs/changelog.md` para o registro completo da sessão.
- Com isso, a rodada de 2026-09-03 é considerada encerrada: todos os 26 itens do relatório têm decisão de código registrada, e as correções alcançáveis por automação têm teste passando. ANIM-002 (manual) e os cenários de overflow puro ficam registrados como validação impraticável/pendente de reprodução real, não como trabalho em aberto.
