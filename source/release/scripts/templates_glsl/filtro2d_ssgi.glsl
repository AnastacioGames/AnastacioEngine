// 2D Filter: SSGI simples (luz indireta de um rebatimento em espaco de tela)
//
// Uso: atuador 2D Filter > Custom Filter > este texto. Pass >= 0.
// Ajustes por propriedades de jogo com o nome do uniform ou filter.setUniform(nome, valor).
// Valor 0 usa o padrao do shader. Erros de compilacao citam a linha deste texto.
//
// Cada pixel junta a cor dos vizinhos que estao "na frente" da sua normal. Para reduzir o
// ruido, o resultado e misturado com o quadro anterior reprojetado (bgl_PreviousTexture +
// bgl_PreviousViewProjectionMatrix), como num TAA. bgl_PreviousTexture so e alocada porque
// este shader a usa; filtros que nao a usam nao pagam nada.

uniform sampler2D bgl_RenderedTexture;
uniform sampler2D bgl_DepthTexture;
uniform sampler2D bgl_PreviousTexture;
uniform vec2 bgl_Resolution;
uniform float bgl_Time;
uniform mat4 bgl_ProjectionMatrix;
uniform mat4 bgl_InverseProjectionMatrix;
uniform mat4 bgl_InverseViewMatrix;
uniform mat4 bgl_PreviousViewProjectionMatrix;

uniform float u_radius;     // raio em unidades do mundo (padrao 2.0)
uniform float u_intensity;  // forca da luz indireta (padrao 1.0)
uniform float u_temporal;   // 0..0.95, peso do quadro anterior (padrao 0.8)

in vec2 texCoordVarying;
out vec4 fragColor;

const int SAMPLES = 12;

vec3 viewPosition(vec2 uv)
{
	float depth = texture(bgl_DepthTexture, uv).r;
	vec4 p = bgl_InverseProjectionMatrix * vec4(vec3(uv, depth) * 2.0 - 1.0, 1.0);
	return p.xyz / p.w;
}

float hash(vec2 p)
{
	return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453);
}

void main()
{
	vec2 uv = texCoordVarying;
	vec4 color = texture(bgl_RenderedTexture, uv);
	if (texture(bgl_DepthTexture, uv).r >= 1.0) {
		fragColor = color;
		return;
	}

	float radius = u_radius > 0.0 ? u_radius : 2.0;
	float intensity = u_intensity > 0.0 ? u_intensity : 1.0;
	float temporal = u_temporal > 0.0 ? min(u_temporal, 0.95) : 0.8;

	vec3 pos = viewPosition(uv);
	vec3 normal = normalize(cross(dFdx(pos), dFdy(pos)));

	// Raio do disco em pixels para o raio em mundo, na profundidade deste pixel.
	float pixelRadius = radius * bgl_ProjectionMatrix[1][1] / max(-pos.z, 0.1) * 0.5;
	float angle = (hash(gl_FragCoord.xy) + fract(bgl_Time * 7.0)) * 6.2831853;

	vec3 indirect = vec3(0.0);
	float weightSum = 0.0;
	for (int i = 0; i < SAMPLES; ++i) {
		float t = (float(i) + 0.5) / float(SAMPLES);
		float a = angle + float(i) * 2.399963;
		vec2 sampleUv = uv + vec2(cos(a), sin(a)) * pixelRadius * sqrt(t);
		if (any(lessThan(sampleUv, vec2(0.0))) || any(greaterThan(sampleUv, vec2(1.0)))) {
			continue;
		}
		vec3 toSample = viewPosition(sampleUv) - pos;
		float dist = length(toSample);
		vec3 dir = toSample / max(dist, 1e-4);
		// Vizinho na frente da normal, perto o bastante.
		float w = max(dot(normal, dir), 0.0) * (1.0 - smoothstep(0.0, radius, dist));
		indirect += texture(bgl_RenderedTexture, sampleUv).rgb * w;
		weightSum += 1.0;
	}
	indirect = weightSum > 0.0 ? indirect / weightSum : vec3(0.0);

	vec3 result = color.rgb + indirect * color.rgb * intensity;

	// Reprojecao para o quadro anterior.
	vec4 world = bgl_InverseViewMatrix * vec4(pos, 1.0);
	vec4 prevClip = bgl_PreviousViewProjectionMatrix * world;
	vec2 prevUv = prevClip.xy / prevClip.w * 0.5 + 0.5;
	if (all(greaterThanEqual(prevUv, vec2(0.0))) && all(lessThanEqual(prevUv, vec2(1.0)))) {
		vec3 previous = texture(bgl_PreviousTexture, prevUv).rgb;
		result = mix(result, previous, temporal);
	}

	fragColor = vec4(result, color.a);
}
