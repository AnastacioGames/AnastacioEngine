// Fase P — exemplo: faísca/glitter piscando, sem textura.
// Cada partícula pisca em instantes pseudo-aleatórios diferentes (hash por v_lifeFrac),
// dando aparência de brilho/magia em vez de um sprite liso. Ver README.md para o contrato.

float hash11(float p) {
	p = fract(p * 0.1031);
	p *= p + 33.33;
	p *= p + p;
	return fract(p);
}

void main() {
	float d = length(v_uv) * 2.0;
	float mask = smoothstep(1.0, 0.0, d);

	// Fase de piscada única por partícula (baseada em quando ela nasceu via v_lifeFrac
	// acumulado com u_time), pra não sincronizar todas as faíscas juntas.
	float seed = hash11(v_lifeFrac * 97.0 + u_time * 0.001);
	float blink = 0.5 + 0.5 * sin(u_time * (8.0 + seed * 12.0) + seed * 6.2831);
	blink = pow(max(blink, 0.0), 3.0);

	vec3 rgb = mix(u_color.rgb, u_endColor.rgb, v_lifeFrac) * (1.0 + blink * 2.0);
	float alpha = mask * v_alpha * (0.25 + blink * 0.75);

	if (alpha <= 0.001) {
		discard;
	}
	fragColor = vec4(rgb, alpha);
}
