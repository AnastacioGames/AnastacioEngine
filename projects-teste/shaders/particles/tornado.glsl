// Fase P — exemplo: partícula de tornado/funil, sem textura.
// Pensado para partículas emitidas em espiral ao redor de um eixo vertical (emissor com
// velocidade tangencial/cone); o shader cuida da aparência: névoa volumétrica em camadas (FBM)
// girando em torno do funil, com luz âmbar de contorno de um lado (efeito "golden hour" contra
// o funil escuro), como no relatório de referência. Ver README.md.

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
float fbm(vec2 p) {
	float v = 0.0;
	float amp = 0.5;
	for (int i = 0; i < 4; i++) {
		v += amp * noise(p);
		p *= 2.02;
		amp *= 0.55;
	}
	return v;
}

void main() {
	vec2 uv = v_uv; // -0.5..0.5
	float d = length(uv) * 2.0;

	// Ângulo do fragmento dentro do sprite, girando com u_time -- mais rápido perto do
	// centro (1/d) pra dar sensação de sucção/vórtice.
	float spin = 3.0 + 5.0 / max(d, 0.12);
	float ang = atan(uv.y, uv.x) + u_time * spin;

	// Densidade volumétrica em camadas (FBM) em vez de uma senoide simples -- lê como poeira
	// espessa girando, não como listras planas.
	vec2 bandCoord = vec2(ang * 1.6, d * 3.0 - u_time * 0.4);
	float density = fbm(bandCoord + fbm(bandCoord * 1.7) * 0.6);
	float bands = smoothstep(0.25, 0.85, density);
	float grain = hash21(vec2(v_lifeFrac * 53.0, floor(ang * 6.0)));
	float dust = mix(bands, grain, 0.3);

	float mask = smoothstep(1.0, 0.0, d) * (0.3 + 0.7 * dust);

	// Núcleo escuro (carvão) com contorno âmbar de um lado, simulando sol de golden-hour
	// rasgando a tempestade e iluminando a borda do vórtice em rotação.
	vec3 darkCore = vec3(0.05, 0.05, 0.06);
	vec3 amberRim = vec3(1.0, 0.6, 0.25);
	float rim = smoothstep(0.35, 1.0, d) * clamp(dot(normalize(uv + vec2(1e-4)), vec2(0.75, 0.4)), 0.0, 1.0);
	vec3 stormColor = mix(u_color.rgb, u_endColor.rgb, v_lifeFrac);
	vec3 rgb = mix(mix(darkCore, stormColor, 0.6), amberRim, rim * 0.6);

	float alpha = mask * v_alpha * u_color.a;

	if (alpha <= 0.001) {
		discard;
	}
	fragColor = vec4(rgb, alpha);
}
