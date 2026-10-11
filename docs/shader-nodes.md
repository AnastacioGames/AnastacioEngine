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
  Length e Layers são lidos ao gerar o shader; mudar esses valores recompila.
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

## Nó GLSL Script

Categoria **Script**. O nó aponta para um Text com uma função `main`. Os parâmetros viram os sockets: `float`/`int`,
`vec2`/`vec3` e `vec4`; parâmetro `out` vira saída. O nó roda no fragment ou no vertex conforme onde for ligado.
Editar o Text atualiza os sockets e recompila. Um erro de compilação aponta a linha do Text.

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

## Ver o código gerado

Material > Node Shader > **Show Generated Code** (também no cabeçalho do Node Editor, ícone de texto) grava o
GLSL final do material em três Texts: `<material>_generated.vert`, `.geom` e `.frag`. Os Text Editors abertos
passam a mostrá-los, o fragment primeiro. São cópias para leitura: editar não muda o material; clique de novo
para atualizar. No fragment, o código dos nós fica no fim, depois das funções da biblioteca. Em Python:
`gpu.export_shader(scene, material)` devolve `vertex`, `fragment` e `geometry`.

O botão precisa do shader compilado; com erro de compilação ele avisa e não gera os Texts.

## Sombras e cache

- Material que move vértices (Vertex Offset, Fur Shells, Outline ou código do usuário) faz sombra com o próprio
  shader.
- Materiais sem esses recursos geram o mesmo código de antes. O cache de shaders e o `.cooked` recompilam uma vez
  após a atualização.

## Cena de teste

`tools/debug/cenas/criar_cena_shader_nodes.py` gera uma cena com água (Water Waves), esfera com Fur, macaco com
Toon Outline, cubo com GLSL Script e cubo com o campo Geometry.

`tools/debug/cenas/criar_cena_glsl_script_uniforms.py` testa o GLSL Script: dois scripts com helpers de mesmo
nome no mesmo material, uniforms `u_` trocados pelo Python do jogo e script no Vertex Offset com `TIME`.
