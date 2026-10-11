# Nós de vertex, geometry e GLSL Script

Como deformar a malha, criar camadas (pelo, contorno) e escrever GLSL próprio dentro do material, sem material
custom em Python. Estado e pendências em [roadmap.md](roadmap.md); detalhes técnicos na entrada de 2026-10-10 do
[changelog.md](changelog.md).

## Vertex Offset

O Material Output (e o Output antigo) tem a entrada **Vertex Offset** (vetor). Os nós ligados a ela rodam no
vertex shader e deslocam o vértice antes da projeção. Eles podem ler posição, normal, UV e tempo. Um nó usado só
ali não entra no fragment.

Nós da categoria **Vertex**: Vertex Offset, Wind e Wave.

## Geometry

Nós da categoria **Geometry**:

- **Fur Shells**: repete a malha em camadas ao longo da normal. Saídas Layer e Alpha para recortar os fios.
  Length e Layers são lidos ao gerar o shader; mudar esses valores recompila. **Direction** (vetor) e
  **Direction Strength** (0-1, padrão 0) deixam o pelo "penteado" numa direção (vento, direção custom etc.):
  com Direction Strength 0 (padrão) o comportamento é idêntico ao de antes, só a normal; conforme sobe até 1,
  cada shell mistura `normalize(mix(normal, Direction, Direction Strength))` em vez de usar só a normal. Os dois
  sockets também são lidos ao gerar o shader (mesma regra de Length/Layers).
- **Outline**: casco invertido. Precisa de backface culling ligado no material.
- **Shell Layer**: índice da camada atual, para variar cor ou alpha por camada.

Em **Input** há também **Camera Distance**, útil para reduzir o efeito longe da câmera.

O estágio geometry precisa de geometry shader na GPU. Na Web e em GLES ele é ignorado: o material desenha sem o
estágio e o console avisa uma vez.

## Campo Geometry (código à mão)

Em Material > Shading > Shader Sources há a linha **Geometry:**, ao lado de Vertex e Fragment (`script_geom` no
Python). O Text define `void geometry()`. As varyings do material são repassadas sozinhas; use os helpers:

| Helper | Função |
|---|---|
| `geom_copy` | copia as varyings de um vértice de entrada |
| `geom_emit` | copia e emite um vértice de entrada |
| `geom_emit_offset` | emite o vértice deslocado |
| `geom_set_position` | define a posição do vértice a emitir |
| `geom_position`, `geom_normal` | leem posição e normal de um vértice de entrada |
| `TIME` | tempo do jogo |

`layout(... max_vertices = N) out;` é opcional (padrão 3). Quanto maior o N, mais caro.

### Modo livre: `void main()`

Se o Text define `void main()` no lugar de `void geometry()`, o geometry shader é o do usuário, como escrito,
com os próprios `layout(...) in;` e `layout(...) out;` (sem eles valem `triangles` e `triangle_strip` com
`max_vertices = 3`). A engine só acrescenta antes do código as entradas, as saídas e os helpers da tabela acima.

| Disponível | O que é |
|---|---|
| `vs_varposition[i]`, `vs_varnormal[i]` | posição e normal do vértice `i`, em view space |
| `vs_var0[i]`, `vs_var1[i]`, ... | atributos que os nós do material usam (UV, cor de vértice, tangente), na ordem em que aparecem no código gerado |
| `vs_<nome>[i]` | cada `out`/`varying` declarado no Text do campo Vertex |
| `gl_in[i].gl_Position` | posição já projetada |
| `varposition`, `varnormal`, `var0`, `<nome>` | as saídas: mesmo nome, sem o `vs_`. Tudo que o fragment lê precisa ser escrito em cada vértice emitido; `geom_copy(i)` escreve todas de uma vez |
| `GEOM_PROJECTION` | matriz de projeção, para posições novas (`geom_set_position` já a usa) |
| `TIME` | tempo do jogo |

A malha chega sempre em triângulos. Show Generated Code mostra a lista exata de `vs_*` do material no `.geom`.

## Nó GLSL Script

Categoria **Script**. O nó aponta para um Text com uma função `main`. Os parâmetros viram os sockets: `float`/`int`,
`vec2`/`vec3` e `vec4`; parâmetro `out` vira saída. O nó roda no fragment ou no vertex conforme onde for ligado.
Editar o Text atualiza os sockets e recompila. Um erro de compilação aponta a linha do Text.

### Erro de compilação no nó (2026-10-11)

Quando a compilação do material falha por causa de um GLSL Script, o nó aparece com o cabeçalho/corpo em
vermelho no editor (mesmo visual de `NODE_MUTED`/incompatibilidade de engine), e o mouse sobre o nó mostra
um tooltip com a mensagem crua do compilador. Mecanismo:

- `codegen_print_scripts` (`gpu_codegen.c`) usa `#line 1 <id>` (em vez de `#line 1`) antes do código de
  cada GLSL Script, onde `<id>` é `GPUScriptCode->id + 1`; isso é o "source string number" do GLSL, que a
  maioria dos drivers imprime como prefixo do log de erro (`"<id>:<linha>"` ou `"<id>(<linha>)"`). Depois do
  código do nó, volta pra `#line 1 0` (0 = sem nó, código gerado/material) para não confundir o próximo bloco.
- `gpu_material_construct_end` (`gpu_material.c`), quando `GPU_generate_pass` falha, lê
  `GPU_shader_get_last_error()` (log cru do último compile/link, capturado em `shader_print_errors` em
  `gpu_shader.c`) e usa `gpu_shader_error_find_node` pra achar, pelo prefixo `<id>`, qual `GPUScriptCode`
  (e portanto qual `bNode->name`) é o dono; guarda a mensagem e o nome do nó em `GPUMaterial->error_log`/
  `error_node_name`.
- `GPU_material_node_error(Material *ma, node_name, &mensagem)` (`GPU_material.h`) procura nas listas
  `ma->gpumaterial`/`gpumaterialinstancing`/`gpumaterialskinning` (as mesmas do `GPU_material_script_uniform_set`)
  um erro cujo nó seja esse — funciona porque essas listas vivem no `Material` real, não na cópia localizada
  da `bNodeTree` usada durante a geração do passe (`bNode->name` sobrevive à localização, ver `ntreeLocalize`).
- `node_draw.c` ganhou `node_shader_error_badge()`, no mesmo padrão de `node_engine_badge()`: se
  `snode->id` for um `Material` (`GS(snode->id->name) == ID_MA`) e `GPU_material_node_error` achar esse nó,
  o cabeçalho pinta `TH_REDALERT` (como `NODE_MUTED`) e ganha um selo com ícone de erro cujo tooltip é a
  mensagem do compilador; aplicado em `node_draw_basis` (nó aberto) e `node_draw_hidden` (nó colapsado).
- Custo: só roda quando o editor desenha um nó dentro de um material com erro (um `STREQ` por material
  compilado do objeto); nenhuma checagem nova no loop de jogo/runtime.
- Limite conhecido: a mensagem de erro depende do formato do driver reconhecer o segundo argumento do
  `#line` (padrão GLSL desde 1.10; NVIDIA/Mesa/ANGLE testados de olho no código, não visualmente — ver nota
  abaixo); se o driver não imprimir o `<id>` no formato esperado, o nó não é identificado e o erro só aparece
  no console (comportamento anterior), sem regressão.
- **Não validado visualmente**: este ambiente não tem display/GPU para abrir o editor e ver o nó vermelho
  nem o tooltip; só a compilação do engine foi conferida.

```glsl
void main(vec3 color, float amount, out vec3 result)
{
	result = mix(color, vec3(1.0, 0.0, 0.0), amount);
}
```

### Funções auxiliares

O Text pode ter outras funções, constantes, structs e `#define` além do `main`, nos dois estágios. Cada nó
recebe nomes próprios na compilação, então dois scripts do mesmo material podem declarar `float noise(vec3 p)`
ou `const float SCALE` sem conflito, e um helper pode ter o nome de uma função da biblioteca do material. O
erro de compilação continua apontando a linha do Text. Variáveis globais declaradas com `in`, `out` ou
`varying` não são renomeadas.

### Uniforms `u_`

Um uniform cujo nome começa com `u_` vira mais uma entrada do nó:

```glsl
uniform float u_speed;   // @min 0 @max 2 @default 0.5
uniform vec4 u_color;    // @default 1 0.5 0 1

float pulse(float t) { return 0.5 + 0.5 * sin(t * u_speed); }

void main(out vec4 Color)
{
	Color = u_color * pulse(TIME);
}
```

- Tipos: `float`, `int`, `vec2`, `vec3` e `vec4`, um uniform por linha.
- O comentário no fim da linha é opcional. `@min` e `@max` juntos transformam o campo em slider; `@default`
  vale quando a entrada é criada (um número, ou um por componente).
- O valor é editado no próprio nó ou em Material > Node Shader > **Script Uniforms**, e é salvo no `.range`.
  Como é um socket, também pode ser ligado a outro nó.
- Entrada sem ligação é um uniform de verdade, enviado a cada desenho. Entrada ligada recebe o valor do outro
  nó e deixa de ser alterável pelo jogo.
- No jogo: `material.setScriptUniform("u_speed", 1.5)` e `material.getScriptUniform("u_speed")`
  (`KX_BlenderMaterial`, por exemplo `obj.meshes[0].materials[0]`). Aceita um número ou uma sequência de até 4.
  Não recompila o shader. Vale para todos os nós GLSL Script do material com esse nome; o retorno é `False`
  quando o material não tem o uniform. O valor volta ao do nó quando o jogo termina.
- Uniform sem o prefixo `u_` compila, mas ninguém o preenche.

### TIME

`TIME` (tempo do jogo, em segundos) pode ser usado no script sem ligar um nó Time.

## Presets

Add > Presets cria grupos de nós editáveis (`node.shader_preset_add`): Fur, Grass, Toon + Rim, Toon Outline,
Dissolve, Water Waves, Wind Leaves, Triplanar e Hologram. Water Waves e Wind Leaves ligam o Offset ao Vertex
Offset sozinhos. Os presets com Alpha põem o material em Alpha Clip.

Dentro do grupo (Tab) os nós ficam em frames coloridos com um rótulo que explica cada parte: Inputs, Vertex,
Geometry, Colour e Output.

- **Wind Leaves**: o nó Wind balança a malha acima da altura Anchor; a cor varia em manchas.
- **Triplanar**: uma textura por eixo, misturada pela direção da face. Não precisa de UV. Troque os três Checker
  por Image Texture para projetar uma imagem.
- **Hologram**: linhas que correm pela altura do objeto e borda clara. Gap vai de -1 (sólido) a 1 (vazio).

Presets com Alpha (Fur, Grass, Dissolve) também se ligam sozinhos: Color vai para a cor do shader que está na
saída e o Alpha entra como recorte (Mix Shader entre um Transparent BSDF e esse shader). Se a saída já tem um
Mix Shader, nada é religado.

O Fur Shells espalha os fios pelo mapa UV. Em malha sem UV ele usa as coordenadas geradas (Generated),
projetadas pelo eixo principal de cada face.

## Bloom e SSR pelo World node graph

No Shader Editor, com o cabeçalho em modo **World**, categoria **Output**, há dois nós além do World Output:

- **Bloom**: `Enable` (bool), `Threshold` (0 a 1, padrão 0.75) e `Intensity` (0 a 10, padrão 2.0).
- **Screen Space Reflections**: `Enable` (bool), `Max Steps` (0 a 1024, padrão 16), `Lod` (1 a 8, padrão 1),
  `Bias` (0 a 10, padrão 3.0) e `Max Distance` (0 a 1000, padrão 100.0).

Os ranges e os padrões são os mesmos de `GPUBLOOMSettings`/`GPUSSRSettings` (Scene > Scene FX, `rna_scene.c`) e
dos métodos Python `changeBloomValues`/`changeSSRValues` do `KX_2DFilterManager`.

**O que esses nós são, de verdade**: um jeito de ligar os mesmos filtros Filter2D de Bloom e SSR que já
existem e já funcionam (`RAS_2DFilterData::BuildInFilters.useBloom/useSSR` e companhia, shaders em
`RAS_OpenGLFilters/RAS_Bloom2DFilter*.glsl` e `RAS_SSR2DFilter.glsl`/`RAS_SSR_Blur2DFilter.glsl`). Não é um
Bloom/SSR novo, e nenhum `.glsl` desses filtros foi tocado. Os dois nós (`node_shader_world_fx.c`) não têm
saída nem função de GPU codegen — eles nunca ligam no World Output nem entram na compilação do material do
céu; são só um cartão de valores. `KX_Scene` (`KX_Scene.cpp`) lê o `World.nodetree` na conversão da cena (igual
Clouds/Rain lêem `World.cloud_coverage`/`World.rain_intensity` direto do DNA) e, se achar um nó Bloom e/ou SSR,
usa os valores dele por cima do que Scene > Scene FX (`scenefx_settings`) já tinha configurado; sem o nó, o
Scene FX de sempre continua decidindo, sem mudança de comportamento.

Os valores são lidos uma vez, na montagem da cena — igual ao próprio Scene FX hoje (que também não é relido
quadro a quadro). Para mudar Bloom/SSR com o jogo já rodando, o caminho continua sendo
`changeBloomValues`/`changeSSRValues` via Python (API existente, sem mudança); o nó só decide o estado inicial.

SSR lê roughness/metallic do G-buffer PBR, então funciona sem nenhum nó extra em qualquer material
Principled. Um material com GLSL Script que não escreve esses canais do G-buffer não reflete corretamente —
isso é uma limitação do próprio filtro SSR, não deste node.

Reflexo planar por objeto (espelho/água real) já existe separado, pelo `KX_PlanarMap`
(`KX_PlanarMap.h`/`.cpp`), amarrado a uma Image/EnvMap no objeto; ele não tem nó dedicado no shader-nodes
ainda — fica para uma próxima etapa.

**Validado sem GPU/display**: além da compilação, `AnastacioEngine.exe -b --python` confirmou que os dois
nós existem em `bpy.types` com os sockets/nomes certos e que um World com eles salva normalmente num `.range`;
`AnastacioRuntime.exe` rodou essa cena por 15 s sem crash (ou seja, `KX_Scene` lendo os nós na conversão não
quebra nada). **Falta** a conferência visual (Bloom/SSR realmente aparecendo na tela) — este ambiente não tem
display/GPU para isso.

## Ver o código gerado

Material > Node Shader > **Show Generated Code** (também no cabeçalho do Node Editor, ícone de texto) grava o
GLSL final do material em três Texts: `<material>_generated.vert`, `.geom` e `.frag`. Os Text Editors abertos
passam a mostrá-los, o fragment primeiro. São cópias para leitura: editar não muda o material; clique de novo
para atualizar. No fragment, o código dos nós fica no fim, depois das funções da biblioteca. Em Python:
`gpu.export_shader(scene, material)` devolve `vertex`, `fragment` e `geometry`.

O botão precisa do shader compilado; com erro de compilação ele avisa e não gera os Texts.

## Billboard, Strands, Explode (fase 3)

Três nós novos em `node_shader_stage_nodes.c`, completando os pendentes da fase 3 (ver `docs/roadmap.md`).

**Billboard** (categoria Vertex, `SH_NODE_BILLBOARD`): entradas `Lock Axis` (0/1, padrão 1) e `Scale`;
saída `Offset` pro Vertex Offset do Material Output, igual Wind/Wave. Implementado em
`node_billboard` (`gpu_shader_material.glsl`): assume que a malha foi desenhada no plano local XZ
(X = largura, Z = altura) em volta da origem — convenção comum de quad de sprite/grama — e troca X/Z
pelas direções direita/cima da câmera, lidas de `GPU_INVERSE_VIEW_MATRIX`/`GPU_INVERSE_OBJECT_MATRIX`
(mesmos builtins que `node_shader_bump.c`/`node_shader_damage.c` já usam). Com `Lock Axis` ligado
(padrão) o billboard é cilíndrico: o eixo local +Z fica fixo (bom pra grama/árvores, não capota) e só
gira pra encarar a câmera; desligado é esférico (sempre de frente total, bom pra partícula/ícone).
Não precisou de nenhuma mudança em `gpu_codegen.c`/`gpu_material.c` — é só um nó de vertex como os outros.

**Strands** (categoria Geometry, `SH_NODE_STRANDS`): entradas `Density` (1-32), `Length`, `Curvature`;
saída `Tip Factor` (0 na base, 1 na ponta). Liga o estágio de geometria via
`GPU_material_strands(mat, density, length, curvature)` (novo em `gpu_material.c`/`GPU_material.h`,
mesmo padrão de `GPU_material_shells`). Em `gpu_codegen.c`, `code_generate_geometry_stage` ganhou um
modo `use_strands`: um invocation por strand (`GL_VERSION >= 400`) ou um loop de `Density` iterações no
fallback, cada um emitindo UM triângulo fino (3 vértices: base-esquerda, base-direita, ponta) a partir
de um ponto pseudo-aleatório do triângulo de entrada (coordenada baricêntrica por hash de
`gl_InvocationID`/`gl_PrimitiveIDIn`), com LOD por distância da câmera (`length(base)` em view space,
que tem a câmera na origem — strands somem progressivamente depois de ~20 unidades, fator fixo
`0.05`, ainda não exposto como socket). **Decisão de escopo**: em vez de criar uma varying nova pro Tip
Factor, Strands reaproveita o canal `varshelllayer`/`node_shell_layer` que Fur Shells e Outline já
usam (0 nas duas bases, 1 na ponta) — por isso não há uma segunda saída "Strand Index" separada, só
`Tip Factor`; Strands e Shells/Outline são estágios de geometria mutuamente exclusivos no mesmo
material (prioridade: Shells/Outline > Strands > Explode > `geomcode` do usuário, decidida em
`GPU_generate_pass`). Custo documentado: `max_vertices` do GS é `Density * 3`; o GLSL do triângulo
inteiro é copiado do vértice 0 (`geom_copy(0)`) pros três vértices do strand, então atributos como UV
variam pouco dentro da fita — aceitável pra grama simples, não pra strand com textura própria ao longo
do comprimento.

**Explode** (categoria Geometry, `SH_NODE_EXPLODE`): entrada `Factor`; saída `Amount` (passthrough de
Factor, pra encadear em outro nó, ex. sumir com o alfa conforme explode). Liga
`GPU_material_explode(mat, factor)` (novo, mesmo arquivo). Modo `use_explode` em
`code_generate_geometry_stage`: um único invocation, sem loop — cada triângulo de entrada sai inteiro
(`geom_copy(i)` nos 3 vértices) deslocado por uma direção que mistura a normal da face com um vetor
aleatório por triângulo (hash de `gl_PrimitiveIDIn`), pra os triângulos não voarem todos exatamente
juntos. `max_vertices = 3`. Não tem noção de velocidade/tempo própria — se quiser animar a explosão,
o `Factor` precisa variar no tempo por fora (ex. ligado a um Math com `TIME`, ou trocado via Python);
não há integração com física/destruição real, é puro efeito visual de geometria.

Os três foram adicionados em `BKE_node.h` (`SH_NODE_BILLBOARD` 1015, `SH_NODE_STRANDS` 1016,
`SH_NODE_EXPLODE` 1017), `node.c` (registro + lista de nós compatíveis com os dois sistemas de
shading), `NOD_static_types.h`, `NOD_shader.h` e no menu Add (`nodeitems_builtins.py`, categorias
Vertex/Geometry, tanto a lista antiga quanto a nova).

**Validado sem GPU/display** com `tools/debug/cenas/criar_cena_billboard_strands_explode.py`: os três
tipos existem em `bpy.types` com os sockets certos (`CHECK BILLBOARD_INPUTS` etc.), dá pra criar e
ligar no Material Output/BSDF e salvar num `.range`. Diferente dos nós de Bloom/SSR anteriores, este
ambiente **tinha** GL disponível para o `AnastacioRuntime.exe`: a cena rodou 65 quadros sem crash e
tirou um `shot.png` (câmera fixa olhando pros três objetos) — então o geometry shader de Strands e
Explode realmente compilou e rodou nessa máquina, não só "não quebrou a conversão". **Falta** a
inspeção visual do `shot.png` por alguém (confirmar que a grama parece grama, que o cubo do Explode
abriu as faces, que o billboard girou certo) — isso não foi feito aqui.

## Sombras e cache

- Material que move vértices (Vertex Offset, Fur Shells, Outline, Billboard ou código do usuário) faz sombra
  com o próprio shader. Strands e Explode também mudam a geometria no mesmo sentido (via geometry stage).
- Materiais sem esses recursos geram o mesmo código de antes. O cache de shaders e o `.cooked` recompilam uma vez
  após a atualização.

## Cena de teste

`tools/debug/cenas/criar_cena_shader_nodes.py` gera uma cena com água (Water Waves), esfera com Fur, macaco com
Toon Outline, cubo com GLSL Script e cubo com o campo Geometry.

`tools/debug/cenas/criar_cena_geometry_livre.py` compara os modos do campo Geometry: `void geometry()`,
`void main()` com layout próprio e `void main()` sem layout.

`tools/debug/cenas/criar_cena_glsl_script_uniforms.py` testa o GLSL Script: dois scripts com helpers de mesmo
nome no mesmo material, uniforms `u_` trocados pelo Python do jogo e script no Vertex Offset com `TIME`.

`tools/debug/cenas/criar_cena_billboard_strands_explode.py` cria um plano com Billboard, um plano com Strands
(ligado no Base Color pra inspecionar o Tip Factor) e um cubo com Explode (ligado no Metallic); salva o
`.range` e roda alguns quadros no Runtime tirando um `shot.png`.
