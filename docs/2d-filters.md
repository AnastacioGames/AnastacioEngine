# Filtros 2D custom (GLSL)

Referência para quem escreve efeitos de tela (SSAO, SSGI, SSR, TAA, bloom, contorno) com o atuador
**2D Filter > Custom Filter** ou com `scene.filterManager.addFilter(...)`.

Modelos prontos: no Text Editor, **Templates > 2D Filters (GLSL)** (`release/scripts/templates_glsl/`):
SSAO, SSGI simples (com reprojeção temporal), bloom em um passe e contorno por profundidade/normal.

## Esqueleto

```glsl
uniform sampler2D bgl_RenderedTexture;
in vec2 texCoordVarying;     // UV da tela, 0..1
out vec4 fragColor;

void main()
{
	fragColor = texture(bgl_RenderedTexture, texCoordVarying);
}
```

Não escreva `#version`: a engine põe a versão do contexto (descartada com aviso se estiver no texto).

## Entradas da engine

Só o que o shader declara e usa é ligado; o resto não custa nada (o driver remove uniforms não usados e a
engine testa a localização uma vez ao compilar).

| Nome | Tipo | Conteúdo |
| --- | --- | --- |
| `bgl_RenderedTexture` | `sampler2D` | Cor da tela (saída do filtro anterior). |
| `bgl_DepthTexture` | `sampler2D` | Profundidade não linear 0..1 (1 = céu). |
| `bgl_DataTextures[n]` | `sampler2D[]` | Cores extras quando o offscreen tem mais slots (`filter.addOffScreen`). |
| `bgl_PreviousTexture` | `sampler2D` | Imagem final do quadro anterior (RGBA16F). Só é alocada e copiada quando algum filtro ativo a usa. Não existe no build Web. |
| `bgl_Resolution` | `vec2` | Largura e altura da tela em pixels. |
| `bgl_RenderedTextureWidth` / `Height` | `float` | O mesmo, nomes antigos. |
| `bgl_Time` | `float` | Segundos de jogo (tempo de quadro da engine, não desacelera com Time Scale). |
| `bgl_Frame` | `int` | Contador de quadros do gerenciador de filtros. |
| `bgl_ViewMatrix` / `bgl_InverseViewMatrix` | `mat4` | Mundo -> câmera e inversa. |
| `bgl_ProjectionMatrix` / `bgl_InverseProjectionMatrix` | `mat4` | Câmera -> clip e inversa (invertidas na CPU uma vez por quadro). |
| `bgl_PreviousViewProjectionMatrix` | `mat4` | Projeção × view do quadro anterior, para reprojeção (TAA, acumulação temporal). |
| `bgl_TextureCoordinateOffset[9]` | `vec2[]` | Vizinhança 3x3 em UV (legado). |

`unfviewmat`, `unfprojmat`, `unfinvviewmat` e `unfinvprojmat` continuam valendo (nomes antigos dos
filtros embutidos).

Unidades de textura: 0-7 ficam para `filter.setTexture`/`setCubeMap`; 8 profundidade; 9 cor; 10-16 dados;
`bgl_PreviousTexture` usa a 17 (ou a 7 em GPUs com 16 unidades ou menos).

### Posição e normal a partir da profundidade

Não há buffer de normais: reconstrua da profundidade (barato e sem memória extra).

```glsl
vec3 viewPosition(vec2 uv)
{
	float depth = texture(bgl_DepthTexture, uv).r;
	vec4 p = bgl_InverseProjectionMatrix * vec4(vec3(uv, depth) * 2.0 - 1.0, 1.0);
	return p.xyz / p.w;
}
vec3 normal = normalize(cross(dFdx(pos), dFdy(pos)));   // espaço de câmera
```

Posição no mundo: `bgl_InverseViewMatrix * vec4(viewPos, 1.0)`. UV no quadro anterior:
`clip = bgl_PreviousViewProjectionMatrix * world; uv = clip.xy / clip.w * 0.5 + 0.5`.

## Uniforms do usuário (`u_*`)

- **Propriedades de jogo:** toda propriedade Float/Int do objeto do atuador com o mesmo nome de um uniform
  é enviada a cada quadro (use Float para uniform `float`). É o jeito de ajustar pelo painel de lógica.
- **Python:** `filter.activeUniforms` lista `(nome, tipo, tamanho)` dos uniforms que o programa usa;
  `filter.setUniform("u_tint", (1, 0.5, 0))` descobre o tipo no shader (float, vec2-4, int, ivec2-4, bool,
  mat3, mat4 e arrays) e guarda o valor, que é reenviado após recompilar. Nome inexistente dá `KeyError`;
  quantidade errada de valores, `ValueError`. Os `setUniform1f`... antigos continuam funcionando, mas se perdem
  numa recompilação.

### Painel Smart no atuador Custom Filter

No **Logic Editor**, escolha **Actuator > 2D Filter > Custom Filter** e selecione um Text GLSL. O painel lê os
uniforms de topo `float`, `int` e `bool` que não começam com `bgl_`; ele não muda o runtime nem cria property
enquanto desenha. Cada campo controla a Game Property do **mesmo objeto do atuador**, que continua sendo o
transporte usado pelo filtro em jogo.

```glsl
uniform float u_radius; // @min 0 @max 20 @default 2.0
uniform int u_mode;     // @choice Linear=2, Smooth=7, Step=12 @default 7
uniform bool u_enabled; // @default 1
```

- Uma property existente, com o tipo certo, é editada pelo painel. `float` com `@min` e `@max` usa slider;
  `int` continua campo numérico e `bool`, checkbox.
- Se faltar a property, o botão **+** cria apenas aquele campo. **Create Missing Properties** cria todos os
  campos ausentes com o tipo e `@default` do shader; sem default usa zero, ou a primeira opção de Choice.
- `@choice` vale para `float` e `int`. O menu grava o valor declarado, não a posição da opção. Valores antigos
  fora da lista permanecem e o painel mostra `Valor fora das opções: n`.
- Se a property tiver outro tipo, o painel mostra o aviso e não a converte. Vetores, matrizes e samplers são
  identificados como não editáveis nesta primeira versão; continue usando `filter.setUniform()` para eles.
- A anotação fica no comentário final da própria declaração. Choice segue as regras do GLSL Script: no máximo
  32 opções, rótulos e valores únicos, valores inteiros representáveis exatamente e `@default` presente na lista.
  Anotação inválida volta ao campo numérico comum e não impede a compilação do shader.

Os quatro modelos em **Text Editor > Templates > 2D Filters (GLSL)** já trazem defaults e faixas úteis para
Bloom, SSAO, SSGI e contorno. Eles preservam a compatibilidade com cenas anteriores: nenhuma property é criada
automaticamente e o valor zero ainda ativa o fallback que cada shader já possuía.

## Erros e recompilação

- Erro de compilação de um filtro custom sai no console com o nome do Text (ou `addFilter(n)`) e as linhas
  **do texto** (ex.: `ERROR: 0:3: 'x' : undeclared identifier` = linha 3). O mesmo log fica em
  `filter.compileLog` (vazio quando compilou).
- **Texto externo:** se o Text do atuador aponta para um arquivo `.glsl` em disco (Text > Open sem
  "Internal"), a engine confere o arquivo duas vezes por segundo durante o jogo e recompila ao salvar. Edite
  num editor externo e veja o resultado sem reiniciar. Se a nova versão não compilar, a anterior continua na
  tela e o erro vai para o console/`compileLog`.
- **Python:** `filter.recompile()` relê o arquivo externo (ou recompila a fonte atual);
  `filter.recompile(fonte)` compila outra fonte. Retorna `True`/`False`. `filter.sourceName` e
  `filter.sourcePath` dizem de onde veio o filtro.

```python
import bge
f = bge.logic.getCurrentScene().filterManager.getFilter(0)
if not f.recompile(open("meu_ssao.glsl").read()):
    print(f.compileLog)
print(f.activeUniforms)
f.setUniform("u_radius", 0.8)
```

## Teste

`tools/debug/cenas/criar_cena_filtro2d.py` gera uma cena que exercita linha do erro, recompilação,
recarga do texto externo, `activeUniforms`/`setUniform` e compila todos os modelos.
