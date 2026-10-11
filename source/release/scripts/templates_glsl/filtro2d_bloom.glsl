// 2D Filter: bloom em um passe
//
// Uso: atuador 2D Filter > Custom Filter > este texto. Pass >= 0.
// Ajustes por propriedades de jogo com o nome do uniform ou filter.setUniform(nome, valor).
// Valor 0 usa o padrao do shader. Erros de compilacao citam a linha deste texto.
// Com "Mipmap" ligado no atuador o brilho fica mais largo e suave (usa niveis menores).

uniform sampler2D bgl_RenderedTexture;
uniform vec2 bgl_Resolution;

uniform float u_threshold;  // brilho minimo que espalha (padrao 0.8)
uniform float u_intensity;  // forca (padrao 0.6)
uniform float u_radius;     // raio em pixels (padrao 12)

in vec2 texCoordVarying;
out vec4 fragColor;

const int SAMPLES = 24;

vec3 bright(vec2 uv, float lod, float threshold)
{
	vec3 c = textureLod(bgl_RenderedTexture, uv, lod).rgb;
	float luma = dot(c, vec3(0.2126, 0.7152, 0.0722));
	return c * smoothstep(threshold, threshold + 0.25, luma);
}

void main()
{
	vec2 uv = texCoordVarying;
	vec4 color = texture(bgl_RenderedTexture, uv);

	float threshold = u_threshold > 0.0 ? u_threshold : 0.8;
	float intensity = u_intensity > 0.0 ? u_intensity : 0.6;
	float radius = u_radius > 0.0 ? u_radius : 12.0;
	vec2 texel = 1.0 / bgl_Resolution;

	vec3 glow = vec3(0.0);
	float weightSum = 0.0;
	for (int i = 0; i < SAMPLES; ++i) {
		// Disco com angulo dourado: amostras espalhadas sem padrao visivel.
		float t = (float(i) + 0.5) / float(SAMPLES);
		float a = float(i) * 2.399963;
		vec2 offset = vec2(cos(a), sin(a)) * sqrt(t) * radius * texel;
		float w = 1.0 - t;
		glow += bright(uv + offset, 2.0 * t, threshold) * w;
		weightSum += w;
	}

	fragColor = vec4(color.rgb + glow / weightSum * intensity, color.a);
}
