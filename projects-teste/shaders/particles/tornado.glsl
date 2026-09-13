// Fase P — exemplo: partícula de tornado/funil, sem textura.
// Pensado para partículas emitidas em espiral ao redor de um eixo vertical (emissor com
// velocidade tangencial/cone); o shader só cuida da aparência: listras rotativas de poeira
// esticadas radialmente, que ficam mais finas e rápidas perto do centro. Ver README.md.

float hash21(vec2 p) {
	p = fract(p * vec2(123.34, 456.21));
	p += dot(p, p + 45.32);
	return fract(p.x * p.y);
}

void main() {
	vec2 uv = v_uv; // -0.5..0.5
	float d = length(uv) * 2.0;

	// Ângulo do fragmento dentro do sprite, girando com u_time -- mais rápido perto do
	// centro (1/d) pra dar sensação de sucção/vórtice.
	float ang = atan(uv.y, uv.x) + u_time * (3.0 + 4.0 / max(d, 0.15));
	// Listras radiais de poeira (bandas no ângulo), moduladas por ruído por partícula.
	float bands = sin(ang * 6.0) * 0.5 + 0.5;
	float grain = hash21(vec2(v_lifeFrac * 53.0, floor(ang * 6.0)));
	float dust = mix(bands, grain, 0.4);

	float mask = smoothstep(1.0, 0.0, d) * (0.35 + 0.65 * dust);

	vec3 rgb = mix(u_color.rgb, u_endColor.rgb, v_lifeFrac);
	float alpha = mask * v_alpha * u_color.a;

	if (alpha <= 0.001) {
		discard;
	}
	fragColor = vec4(rgb, alpha);
}
