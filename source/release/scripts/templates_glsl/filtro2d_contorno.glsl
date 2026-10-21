// 2D Filter: contorno (outline) por profundidade e normal
//
// Uso: atuador 2D Filter > Custom Filter > este texto. Pass >= 0.
// Ajustes por propriedades de jogo com o nome do uniform ou filter.setUniform(nome, valor).
// Ex.: filter.setUniform("u_color", (1.0, 0.5, 0.0)). Valor 0 usa o padrao do shader.
// Erros de compilacao citam a linha deste texto.

uniform sampler2D bgl_RenderedTexture;
uniform sampler2D bgl_DepthTexture;
uniform vec2 bgl_Resolution;
uniform mat4 bgl_InverseProjectionMatrix;

uniform vec3 u_color;        // cor da linha (padrao preto)
uniform float u_thickness;   // @min 0 @max 8 @default 1.0 — espessura em pixels
uniform float u_depthEdge;   // @min 0 @max 1 @default 0.05 — sensibilidade a profundidade
uniform float u_normalEdge;  // @min 0 @max 1 @default 0.4 — sensibilidade a normal

in vec2 texCoordVarying;
out vec4 fragColor;

vec3 viewPosition(vec2 uv)
{
	float depth = texture(bgl_DepthTexture, uv).r;
	vec4 p = bgl_InverseProjectionMatrix * vec4(vec3(uv, depth) * 2.0 - 1.0, 1.0);
	return p.xyz / p.w;
}

vec3 viewNormal(vec2 uv, vec2 texel)
{
	vec3 p = viewPosition(uv);
	vec3 px = viewPosition(uv + vec2(texel.x, 0.0)) - p;
	vec3 py = viewPosition(uv + vec2(0.0, texel.y)) - p;
	return normalize(cross(px, py));
}

void main()
{
	vec2 uv = texCoordVarying;
	vec4 color = texture(bgl_RenderedTexture, uv);

	float thickness = u_thickness > 0.0 ? u_thickness : 1.0;
	float depthEdge = u_depthEdge > 0.0 ? u_depthEdge : 0.05;
	float normalEdge = u_normalEdge > 0.0 ? u_normalEdge : 0.4;
	vec2 texel = thickness / bgl_Resolution;

	// O ceu (profundidade 1) nao tem posicao: so a silhueta contra ele conta.
	bool centerSky = texture(bgl_DepthTexture, uv).r >= 1.0;
	float centerZ = -viewPosition(uv).z;
	vec3 centerN = viewNormal(uv, 1.0 / bgl_Resolution);

	float edge = 0.0;
	vec2 offsets[4] = vec2[](vec2(1.0, 0.0), vec2(-1.0, 0.0), vec2(0.0, 1.0), vec2(0.0, -1.0));
	for (int i = 0; i < 4; ++i) {
		vec2 sampleUv = uv + offsets[i] * texel;
		bool sampleSky = texture(bgl_DepthTexture, sampleUv).r >= 1.0;
		if (centerSky || sampleSky) {
			edge = max(edge, (centerSky != sampleSky) ? 1.0 : 0.0);
			continue;
		}
		float z = -viewPosition(sampleUv).z;
		vec3 n = viewNormal(sampleUv, 1.0 / bgl_Resolution);
		edge = max(edge, step(depthEdge * centerZ, abs(z - centerZ)));
		edge = max(edge, step(normalEdge, 1.0 - dot(n, centerN)));
	}

	fragColor = vec4(mix(color.rgb, u_color, edge), color.a);
}
