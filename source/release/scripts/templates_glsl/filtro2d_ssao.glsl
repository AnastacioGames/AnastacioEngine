// 2D Filter: SSAO (ambient occlusion em espaco de tela)
//
// Uso: atuador 2D Filter > Custom Filter > este texto. Pass >= 0.
// Ajustes: crie propriedades de jogo com o mesmo nome dos uniforms u_* no objeto do atuador
// (ex.: u_radius = 0.5) ou, pelo Python, filter.setUniform("u_radius", 0.5).
// Valor 0 usa o padrao do shader. Erros de compilacao citam a linha deste texto.
//
// Entradas da engine (so as usadas pelo shader custam alguma coisa):
//   bgl_RenderedTexture, bgl_DepthTexture, bgl_Resolution, bgl_ProjectionMatrix,
//   bgl_InverseProjectionMatrix. Veja docs/2d-filters.md.

uniform sampler2D bgl_RenderedTexture;
uniform sampler2D bgl_DepthTexture;
uniform vec2 bgl_Resolution;
uniform mat4 bgl_ProjectionMatrix;
uniform mat4 bgl_InverseProjectionMatrix;

uniform float u_radius;     // @min 0 @max 10 @default 0.5 — raio em unidades do mundo
uniform float u_intensity;  // @min 0 @max 3 @default 1.0 — forca

in vec2 texCoordVarying;
out vec4 fragColor;

const int SAMPLES = 16;

// Posicao em espaco de camera a partir da profundidade.
vec3 viewPosition(vec2 uv)
{
	float depth = texture(bgl_DepthTexture, uv).r;
	vec4 p = bgl_InverseProjectionMatrix * vec4(vec3(uv, depth) * 2.0 - 1.0, 1.0);
	return p.xyz / p.w;
}

// Normal reconstruida da profundidade (sem buffer extra).
vec3 viewNormal(vec3 pos)
{
	return normalize(cross(dFdx(pos), dFdy(pos)));
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
		fragColor = color; // ceu
		return;
	}

	float radius = u_radius > 0.0 ? u_radius : 0.5;
	float intensity = u_intensity > 0.0 ? u_intensity : 1.0;

	vec3 pos = viewPosition(uv);
	vec3 normal = viewNormal(pos);
	float angle = hash(gl_FragCoord.xy) * 6.2831853;

	float occlusion = 0.0;
	for (int i = 0; i < SAMPLES; ++i) {
		// Espiral no hemisferio da normal.
		float t = (float(i) + 0.5) / float(SAMPLES);
		float a = angle + float(i) * 2.399963;
		vec3 dir = vec3(cos(a) * sqrt(1.0 - t), sin(a) * sqrt(1.0 - t), sqrt(t));
		vec3 tangent = normalize(cross(normal, abs(normal.z) < 0.9 ? vec3(0.0, 0.0, 1.0) : vec3(1.0, 0.0, 0.0)));
		vec3 bitangent = cross(normal, tangent);
		vec3 samplePos = pos + (tangent * dir.x + bitangent * dir.y + normal * dir.z) * radius * t;

		vec4 clip = bgl_ProjectionMatrix * vec4(samplePos, 1.0);
		vec2 sampleUv = clip.xy / clip.w * 0.5 + 0.5;
		float sceneZ = viewPosition(sampleUv).z;
		float range = smoothstep(0.0, 1.0, radius / abs(pos.z - sceneZ));
		occlusion += (sceneZ >= samplePos.z + 0.02 ? 1.0 : 0.0) * range;
	}
	float ao = 1.0 - occlusion / float(SAMPLES) * intensity;

	fragColor = vec4(color.rgb * clamp(ao, 0.0, 1.0), color.a);
}
