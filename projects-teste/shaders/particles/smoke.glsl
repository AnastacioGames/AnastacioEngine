// Fase P — exemplo: fumaça suave, sem textura.
// Máscara elíptica difusa com ruído lento (ao contrário do fire.glsl, que anima rápido) e
// alpha caindo por toda a vida da partícula. Ver README.md para o contrato de variáveis.

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
	float d = length(v_uv) * 2.0;
	float drift = noise(v_uv * 3.0 + u_time * 0.15) - 0.5;
	float mask = smoothstep(1.0, 0.0, d + drift * 0.35);

	vec3 rgb = mix(u_color.rgb, u_endColor.rgb, v_lifeFrac);
	// Fumaça fica mais transparente e maior/mais dispersa perto do fim da vida.
	float fadeByLife = (1.0 - v_lifeFrac) * 0.7;
	float alpha = mask * v_alpha * fadeByLife * u_color.a;

	if (alpha <= 0.001) {
		discard;
	}
	fragColor = vec4(rgb, alpha);
}
