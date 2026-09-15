// Fase P — exemplo: rajada de vento, sem textura.
// Sprite esticado numa listra horizontal translúcida em vez de um disco -- parece uma
// "linha de corrente" de ar em movimento. Combina bem com emissores de velocidade alta e
// pouca gravidade. Ver README.md para o contrato de variáveis.

void main() {
	vec2 uv = v_uv; // -0.5..0.5

	// Leve ondulação vertical ao longo do comprimento, animada por u_time, pra não parecer
	// uma barra estática -- desloca o centro da listra em Y conforme x e o tempo.
	float wobble = sin(uv.x * 18.0 + u_time * 10.0) * 0.04;

	// Achata bastante no eixo Y pra virar uma linha horizontal, e afina as pontas em X
	// (em vez de retângulo com bordas duras) pra parecer uma rajada, não uma barra.
	float lengthMask = smoothstep(0.5, 0.15, abs(uv.x));
	float thicknessMask = smoothstep(0.5, 0.0, abs(uv.y - wobble) * 6.0);
	float mask = lengthMask * thicknessMask;

	vec3 rgb = mix(u_color.rgb, u_endColor.rgb, v_lifeFrac);
	// Vento é sutil: mais transparente que a maioria dos outros efeitos, e some rápido no
	// fim da vida (rajada passando, não uma nuvem parada).
	float alpha = mask * v_alpha * u_color.a * (1.0 - v_lifeFrac * v_lifeFrac) * 0.6;

	if (alpha <= 0.001) {
		discard;
	}
	fragColor = vec4(rgb, alpha);
}
