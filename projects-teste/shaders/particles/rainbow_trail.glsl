// Fase P — exemplo: rastro com matiz variando no tempo (arco-íris), sem textura.
// u_color/u_endColor são ignorados de propósito aqui (o efeito É a cor); troque o HSV base
// se quiser tingir o efeito em vez de cores puras. Ver README.md para o contrato.

vec3 hsv2rgb(vec3 c) {
	vec4 k = vec4(1.0, 2.0 / 3.0, 1.0 / 3.0, 3.0);
	vec3 p = abs(fract(c.xxx + k.xyz) * 6.0 - k.www);
	return c.z * mix(k.xxx, clamp(p - k.xxx, 0.0, 1.0), c.y);
}

void main() {
	float d = length(v_uv) * 2.0;
	float mask = smoothstep(1.0, 0.0, d);

	// Matiz avança com o tempo global e também varia um pouco por idade da partícula,
	// pra dar um degradê ao longo do rastro em vez de tudo na mesma cor.
	float hue = fract(u_time * 0.25 + v_lifeFrac * 0.4);
	vec3 rgb = hsv2rgb(vec3(hue, 0.85, 1.0));

	float alpha = mask * v_alpha * (1.0 - v_lifeFrac);
	if (alpha <= 0.001) {
		discard;
	}
	fragColor = vec4(rgb, alpha);
}
