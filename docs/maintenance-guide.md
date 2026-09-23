# Guia de manutenção — "o que mais preciso tocar?"

> Objetivo: para os tipos de mudança mais comuns nesta engine, listar a cadeia completa de arquivos/camadas
> que historicamente precisam ser tocados juntos — não é teoria, é extraído de episódios reais já
> documentados em `docs/changelog.md` (GPU Skinning, menu ImGui, migração de core profile, CSM, Z-prepass).
> Cada padrão abaixo é **[precedente confirmado no changelog]** — já aconteceu nesta engine pelo menos uma
> vez e está detalhado lá com data. Use isto para não esquecer uma camada; use o changelog para o "porquê"
> e o passo a passo completo de cada caso.
>
> Ver também: `docs/architecture.md` (mapa de módulos) e `docs/build-notes.md` (como compilar).

---

## 1. Adicionar/mudar uma propriedade de material ou objeto com checkbox na UI

**Gatilho**: "quero uma opção nova tipo `use_gpu_skinning` / `use_occlude_culling`, com checkbox no painel."

**Cadeia (nesta ordem de dependência)**:
1. `DNA_material_types.h` / `DNA_armature_types.h` / `DNA_object_types.h` — novo bit/enum no struct
   (ex.: `MA_SKINNING` em `shade_flag`, `ARM_VDEF_BGE_GPU`).
2. `source/blender/makesrna/intern/rna_material.c` / `rna_armature.c` / `rna_object.c` — registra a
   propriedade RNA (ex.: `use_gpu_skinning`).
3. Painel Python da UI (`properties_material.py`, `properties_game.py`) **— e qualquer addon/panel próprio
   que sobrescreva o painel stock** (ex.: `Range_Components_Label/custom_pt_physics.py` sombreia
   `properties_game.py` — se existir um panel customizado equivalente, editar os dois).
4. Consumo em `BL_BlenderDataConversion.cpp` — lê a flag na conversão de cena (ex.: `SetOccluder()`,
   `HasArmatureDeformer`).
5. Shader, se afetar render (ex.: bloco `#ifdef USE_SKINNING` em `gpu_shader_vertex.glsl`).

**Cuidado conhecido**: uma propriedade pode existir em RNA/Python por muito tempo sem nunca ganhar
`col.prop(...)` na UI — sempre confirmar que o checkbox está de fato exposto (aconteceu com
`use_gpu_skinning` até a Fase G, ver relatório).

---

## 2. Expor uma função/módulo novo na API Python do jogo (`Range.*`)

**Gatilho**: "quero `Range.algumacoisa.funcao()` chamável de script Python de jogo."

**Cadeia**:
1. Implementação em C++ (`Ketsji/...`, ex.: `KX_PythonImgui.h/.cpp`, ou função nova em `KX_PythonInit.cpp`).
2. Tabela `PyMethodDef` + registro em `initRANGE()`/`KX_PythonInit.cpp` (`sys.modules['Range.xxx']`).
3. **Adicionar o nome do módulo no shim de validação de componentes do editor**,
   `source/blender/blenkernel/intern/python_component.c` (`load_component()`) — sem isso, `import Range.xxx`
   falha só dentro do editor com "No module named X" genérico, mesmo funcionando no jogo real.

**Cuidados conhecidos (bugs reais já corrigidos)**:
- Nunca referenciar atributos `Range.*` em **escopo de módulo** num script de componente — o shim do
  editor liga `Range.events` etc. a um stub quase vazio; só acessar dentro de função é seguro.
- A rotina de limpeza do shim (`FINISH`) precisa remover **todo** módulo fake injetado de `sys.modules` e
  purgar o cache de `scripts.*` a cada `load_component()` — senão "Reload All Components" deixa imports
  presos a bindings fake que crasham de forma intermitente só no Play (bug real, corrigido 2026-08-25, ver
  changelog).

---

## 3. Mudança de shader que precisa sobreviver a compat E core profile

**Gatilho**: "preciso mudar um shader e ele roda tanto em `build/` (compat) quanto `build_core/` (core,
`WITH_GL_PROFILE_CORE_RANGERUNTIME`)."

**Padrão**:
- Ramificar com `#if __VERSION__ >= 130` ou `#ifdef WITH_GL_PROFILE_CORE`, mantendo o corpo legado
  (`gl_Vertex`, `gl_TexCoord`, `texture2D`, `gl_FragColor`) intacto no `#else`.
- Matrizes (`gl_ModelViewMatrix` etc.) viram uniforms (`unfviewmat`/`unfobmat`/`unfprojmat`/`unfnormalmat`)
  vindos do C++ (`GPU_material_bind()`, ou upload manual via `RAS_Rasterizer` para shaders "builtin" que não
  passam por `GPU_material`).
- Testar num build isolado e descartável (`build_core_test/`, opção
  `WITH_GL_PROFILE_CORE_RASTERIZER_TEST`), escopado **por arquivo**
  (`set_source_files_properties(... COMPILE_DEFINITIONS "WITH_GL_PROFILE_CORE")`), nunca por *target* —
  escopar por target puxa código fixed-function do editor que não deveria mudar.
- **Nunca** ligar `WITH_GL_PROFILE_CORE`/`COMPAT` globalmente — `editors/` e `bf_rna` são
  permanentemente compat-only (callbacks RNA chamam funções `ED_*` do editor diretamente).

**Cuidados conhecidos**:
- GLSL core proíbe inicializadores de array estilo C e inicializadores não-constantes de global/`const`
  local (achado repetidamente em `RAS_OpenGLFilters/*.glsl`).
- Desenho em immediate-mode (`glBegin`/`glEnd`, ex.: blur VSM em `gpu_framebuffer.c`) precisa de reescrita
  completa para VBO/VAO, não dá para só trocar o texto do shader.

---

## 4. Mudar um struct DNA

**Gatilho**: qualquer edição em `DNA_*.h` (ex.: `DNA_armature_types.h`, `DNA_material_types.h`).

**Regra obrigatória**: rebuild limpo (`ninja -t clean` + rebuild completo), **nunca incremental**.

**Porquê**: o Ninja não rastreia `DNA_*.h` como dependência do `dna.c`/`dna_type_offsets.h` gerados
(codegen via custom-command, sem depfile) — então `readfile.c`/`writefile.c` compilam contra uma tabela de
offsets de struct desatualizada, causando corrupção de heap (`STATUS_HEAP_CORRUPTION`,
`EXCEPTION_ACCESS_VIOLATION`) que só aparece depois, de forma aparentemente aleatória.

**Regra geral relacionada**: o mesmo tipo de staleness já apareceu com headers amplamente incluídos que não
são DNA (ex.: `RAS_Rasterizer.h`) — depois de tocar em qualquer header muito incluído, prefira rebuild limpo
antes de investigar um crash "esquisito" que não bate com a mudança feita.

---

## 5. Outras regras cruzadas

- **Filtros 2D do jogo vs. pipeline multi-pass nativo do editor são sistemas separados**: `RAS_OpenGLFilters/*.glsl`
  (`Filter2DToggle`/`addFilter`) é uma coisa; Bloom/SSR/SSAO/LightScatter nativos
  (`scene.scenefx_settings`) são outra, com arquivos próprios. Não assumir que migrar um cobre o outro
  (erro cometido e corrigido duas vezes no changelog).
- **Shaders de viewport do editor** (`gpu_shader_fx_*`, usados por `view3d_draw.c`) **nunca são compilados
  pelo `RangeRuntime`** — não entram em esforços de migração de core profile do jogo.
- **Manter `RangeEngine.exe` (editor) e `RangeRuntime.exe` (player) em paridade**: toda mudança de
  C++/shader deveria ser compilada e smoke-testada nos dois.
- **Malhas compartilhadas entre Objects**: a conversão de dados Blender→Ketsji faz cache de mesh por
  `Mesh*` compartilhado entre Objects — dado por-objeto que dependa da ordem de vertex groups (ex.: índices
  de bone) quebra se dois Objects compartilharem a mesma malha com vertex groups em ordem diferente. Vale
  como alerta para qualquer dado novo por-objeto que for pendurado na conversão de mesh compartilhada.

---

## 6. Como validar uma mudança antes de considerar terminada

**Regra**: nenhuma mudança em C++/shader/DNA está pronta só porque compilou. A engine tem dois builds e dois
executáveis que historicamente divergem (ver item 3 e item 5 acima) — validar significa cobrir ambos.

**Checklist mínimo**:
1. **Compilar os dois builds relevantes**: `build/` (compat) e, se a mudança toca shader/rasterizador/GPU,
   também `build_core/` (`WITH_GL_PROFILE_CORE_RANGERUNTIME`). Mudança em `DNA_*.h` ou em header muito
   incluído exige rebuild limpo nos dois (`ninja -t clean` + rebuild), nunca incremental — ver item 4.
2. **Rodar os dois executáveis**: `RangeEngine.exe` (editor) e `RangeRuntime.exe` (player standalone). Uma
   mudança que só é testada no editor pode esconder regressão que só aparece no Play/player (aconteceu com o
   bug de "Reload All Components", ver changelog 2026-08-25).
3. **Testar na cena real do usuário, não em screenshot automatizado por script de câmera** — captura
   scriptada já se mostrou pouco confiável aqui para bugs visuais (ver `[[feedback_test_in_real_game]]`).
   Pedir para o usuário rodar o jogo real e descrever/printar o que vê.
4. **Se a mudança afeta performance**: rodar `benchmark_component.py` (`Range.types.KX_PythonComponent`,
   ver changelog 2026-08-23) na cena de benchmark e comparar as categorias do profiler (`Physics`,
   `MainRender`, `Animations` etc.) contra o relatório anterior mais próximo, não só "parece mais rápido".
5. **Se a mudança toca shader**: confirmar que não há inicializador de array/`const` não-constante em GLSL
   core (erro comum, ver item 3) e que o shader ainda compila nos dois profiles antes de declarar concluído.

**Por que isso vira regra**: praticamente todo bug grande já registrado no changelog (crash de heap por DNA
desatualizado, regressão de performance do GPU Skinning, bug de fumaça em core profile, "Reload All
Components" travando só no Play) só apareceu **depois** de um "compilou, deu certo" prematuro — cada um exigiu
voltar e testar a combinação certa de build + executável + cena real para ser pego.

---

## 7. Criar um `KX_PythonComponent`

- Use `OrderedDict` em `args` para preservar a ordem dos campos.
- Prefira rótulos legíveis e agrupe seções com `C_Header /Nome da seção/ÍCONE`; declare `C_Icons` no topo
  quando o componente usar ícones próprios.
- Use `mathutils.Vector` e `Color` como tipos dos campos, em vez de decompor valores em vários floats. Este
  fork aceita `Color((r, g, b, a))` com quatro componentes (`CPROP_TYPE_COL4` em `python_component.c`).
- Consulte um componente atual em `projects-teste/scripts/` antes de copiar padrões antigos.

---

## Como usar este guia

Antes de começar uma mudança que se pareça com um dos gatilhos acima, siga a cadeia como checklist. Se a
mudança não se encaixa em nenhum padrão listado, ela é provavelmente nova o suficiente para merecer entrada
própria em `docs/changelog.md` depois — e, se o padrão se repetir, vale adicionar aqui.
