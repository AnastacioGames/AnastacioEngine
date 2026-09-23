// Fase P — exemplo: fogo procedural, sem textura.
// Núcleo quente que fica mais fraco e "esfumaçado" perto do fim da vida, com flicker
// via ruído hash barato animado por u_time. Ver README.md para o contrato de variáveis.

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
	vec2 uv = v_uv + 0.5; // 0..1
	// Achata o disco pra parecer uma chama subindo em vez de uma bola redonda.
	vec2 flameUv = vec2(uv.x, uv.y * 0.8 + 0.1);
	float d = length((flameUv - 0.5) * vec2(2.2, 1.6));

	float flicker = noise(vec2(uv.x * 6.0, uv.y * 6.0 - u_time * 4.0));
	float mask = smoothstep(1.0, 0.15, d + flicker * 0.25);

	vec3 hot = mix(u_color.rgb, u_endColor.rgb, v_lifeFrac);
	// Núcleo mais claro/amarelado perto da base (uv.y baixo), pontas mais escuras.
	vec3 rgb = mix(hot * 1.6, hot * 0.4, uv.y);

	float alpha = mask * v_alpha * (1.0 - v_lifeFrac * 0.6);
	if (alpha <= 0.001) {
		discard;
	}
	fragColor = vec4(rgb, alpha);
}
