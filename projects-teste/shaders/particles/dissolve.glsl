// Fase P — exemplo: sprite com textura dissolvendo por ruído conforme a vida avança.
// Precisa que o emissor tenha uma textura configurada (u_useTexture). Sem textura, cai pra
// máscara redonda padrão dissolvendo do mesmo jeito. Ver README.md para o contrato.

float hash21(vec2 p) {
	p = fract(p * vec2(123.34, 456.21));
	p += dot(p, p + 45.32);
	return fract(p.x * p.y);
}

float noise(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	f = f * f * (3.0 - 2.0 * f);
	float a = hash21(i);
	float b = hash21(i + vec2(1.0, 0.0));
	float c = hash21(i + vec2(0.0, 1.0));
	float d = hash21(i + vec2(1.0, 1.0));
	return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}

void main() {
	vec2 uv = v_uv + 0.5;
	vec4 baseColor = mix(u_color, u_endColor, v_lifeFrac);

	vec3 rgb;
	float baseMask;
	if (u_useTexture) {
		vec4 texColor = texture2D(u_texture, uv);
		rgb = baseColor.rgb * texColor.rgb;
		baseMask = texColor.a;
	} else {
		float d = length(v_uv) * 2.0;
		baseMask = smoothstep(1.0, 0.0, d);
		rgb = baseColor.rgb;
	}

	// Limiar de dissolve sobe com v_lifeFrac; ruído em coordenada de tela (uv) fixa por
	// partícula gera a "queima" irregular em vez de um fade uniforme.
	float grain = noise(uv * 18.0);
	float dissolveMask = step(v_lifeFrac, grain);

	// Borda brilhante logo antes de sumir (estilo "queimando").
	float edge = smoothstep(0.0, 0.12, grain - v_lifeFrac);
	vec3 edgeGlow = mix(vec3(1.6, 0.9, 0.3), vec3(0.0), edge);

	float alpha = baseMask * dissolveMask * v_alpha * baseColor.a;
	if (alpha <= 0.001) {
		discard;
	}
	fragColor = vec4(rgb + edgeGlow * (1.0 - edge) * dissolveMask, alpha);
}
