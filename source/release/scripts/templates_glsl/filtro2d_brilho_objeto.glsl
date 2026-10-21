// 2D Filter: brilho que segue um objeto na tela
//
// Uso: atuador 2D Filter > Custom Filter > este texto. No painel do atuador, clique em
// "Create Missing Properties" e escolha o objeto em u_alvo. O brilho acompanha o objeto
// e some quando ele fica atras da camera.
// Erros de compilacao citam a linha deste texto.

uniform sampler2D bgl_RenderedTexture;
uniform vec2 bgl_Resolution;

uniform vec4 u_alvo;          // @object — x, y na tela (0-1), z distancia, w visivel
uniform float u_intensidade;  // @min 0 @max 4 @default 1.0
uniform float u_tamanho;      // @min 0.01 @max 1 @default 0.15 — raio na tela
uniform float u_vermelho;     // @min 0 @max 1 @default 1.0
uniform float u_verde;        // @min 0 @max 1 @default 0.7
uniform float u_azul;         // @min 0 @max 1 @default 0.2

in vec2 texCoordVarying;
out vec4 fragColor;

void main()
{
	vec4 color = texture(bgl_RenderedTexture, texCoordVarying);
	float aspect = bgl_Resolution.x / max(bgl_Resolution.y, 1.0);
	vec2 d = (texCoordVarying - u_alvo.xy) * vec2(aspect, 1.0);
	float raio = max(u_tamanho, 0.01);
	float glow = u_alvo.w * u_intensidade * exp(-dot(d, d) / (raio * raio));
	fragColor = vec4(color.rgb + vec3(u_vermelho, u_verde, u_azul) * glow, color.a);
}
