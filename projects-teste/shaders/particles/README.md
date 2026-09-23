# Exemplos de Fragment Shader para GPU Particles (Fase P)

Arquivos `.glsl` prontos para usar em `object.particles.fragmentShaderPath` (Python) ou no
campo "Fragment Shader File" do painel "Custom Shader (GLSL)" (`properties_particle.py`).

## Como usar

1. Copie/aponte o campo para um destes arquivos, ex.: `//shaders/particles/fire.glsl`
   (caminho relativo ao `.blend`, mesma convenção do campo `texture`).
2. Ligue o checkbox "Custom Fragment Shader" (`use_fragment_shader` / `gp.use_fragment_shader`).
3. Edite o `.glsl` com o jogo rodando (`RangeEngine`/`RangeRuntime`) — o motor faz poll do
   `mtime` do arquivo a cada ~0,5s e recompila sozinho. Se a compilação falhar, o shader anterior
   continua ativo e o erro aparece no console.

Também dá pra trocar em runtime via Python:

```python
obj.particles.fragmentShaderPath = "//shaders/particles/fire.glsl"
```

## Contrato do shader

Cada arquivo aqui é só o corpo (`void main() { ... }`); o motor já injeta este preâmbulo antes de
compilar (ver `drawFragmentPreamble` em `RAS_ParticleShaderCache.cpp`):

```glsl
#version 130
in vec2 v_uv;              // corner do quad da partícula, [-0.5, 0.5]
in float v_alpha;          // alpha atual (fade in/out por vida), 0..1
in float v_lifeFrac;       // fração de vida decorrida, 0 (nasceu) .. 1 (vai morrer)
out vec4 fragColor;        // obrigatório escrever
uniform vec4 u_color;      // cor inicial (RGBA) configurada no emissor
uniform vec4 u_endColor;   // cor final (RGBA), usada para interpolar por v_lifeFrac
uniform sampler2D u_texture;
uniform bool u_useTexture; // true se o emissor tem uma textura de sprite associada
uniform sampler2D u_colorCurveTex;
uniform bool u_useColorCurve; // true se o emissor usa curva de cor em vez de lerp linear
uniform float u_time;      // tempo de simulação acumulado do emissor (segundos), para animação
```

Regras:

- É obrigatório escrever `fragColor`; `discard` é permitido (útil pra máscaras não-redondas).
- Não declare `#version`, `in`/`out`/`uniform` de novo — já vêm do preâmbulo.
- Erro de compilação não derruba o efeito: o shader anterior (ou o padrão) continua rodando.

## Efeitos incluídos

| Arquivo | Efeito |
|---|---|
| `fire.glsl` | Chama: núcleo quente com ruído procedural e flicker via `u_time`, sem textura. |
| `smoke.glsl` | Fumaça suave: máscara elíptica difusa, ruído lento, alpha decrescente pela vida. |
| `sparkle.glsl` | Faísca/glitter: pontos piscando (hash + `u_time`), boa pra magia/impacto. |
| `dissolve.glsl` | Textura com dissolve por ruído conforme `v_lifeFrac` avança (borda queimada). |
| `rainbow_trail.glsl` | Rastro com matiz variando por `u_time` + `v_lifeFrac` (HSV → RGB), sem textura. |
| `tornado.glsl` | Funil/vórtice: listras radiais de poeira girando mais rápido perto do centro. |
| `wind.glsl` | Rajada de vento: listra horizontal fina e translúcida, com leve ondulação. |
| `aurora.glsl` | Aurora boreal: cortinas onduladas com matiz verde→violeta deslizando no tempo. |

Todos usam só matemática de shader (sem sampler extra além dos já fornecidos), então são
baratos e não competem por texture units.

Dica de emissor para `tornado.glsl`/`aurora.glsl`: funcionam melhor com sprites maiores/esticados
e emissão em cone ou ao longo de um eixo, não pontual — ajuste `size`/`endSize` e a geometria de
emissão do `object.particles` (ou o preset correspondente) pra combinar com a forma do efeito.
