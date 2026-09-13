// Fase P — exemplo: aurora boreal, sem textura.
// Pensado para um sprite grande e esticado (ex.: plane bem largo/alto por partícula) formando
// cortinas de luz onduladas que mudam de cor com o tempo, em vez de um efeito pontual. Várias
// partículas empilhadas/deslocadas em X dão o efeito de múltiplas cortinas. Ver README.md.

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

vec3 hsv2rgb(vec3 c) {
	vec4 k = vec4(1.0, 2.0 / 3.0, 1.0 / 3.0, 3.0);
	vec3 p = abs(fract(c.xxx + k.xyz) * 6.0 - k.www);
	return c.z * mix(k.xxx, clamp(p - k.xxx, 0.0, 1.0), c.y);
}

void main() {
	vec2 uv = v_uv + 0.5; // 0..1, uv.y = 0 embaixo, 1 em cima

	// Ondulação horizontal que serpenteia com a altura (uv.y) e o tempo -- é isso que dá o
	// aspecto de "cortina" balançando, em vez de uma faixa reta.
	float wave = sin(uv.y * 5.0 + u_time * 0.6) * 0.12
	           + sin(uv.y * 11.0 - u_time * 0.9) * 0.05;
	float distFromCenter = abs(uv.x - 0.5 - wave);

	// Cortina mais larga/difusa no topo, mais fina embaixo (base da aurora).
	float width = mix(0.06, 0.22, uv.y);
	float mask = smoothstep(width, 0.0, distFromCenter);

	// Desvanece nas bordas verticais do sprite pra emendar melhor com partículas vizinhas.
	mask *= smoothstep(0.0, 0.15, uv.y) * smoothstep(1.0, 0.75, uv.y);

	// Textura fina de "cortina" (ruído esticado verticalmente) por cima da máscara.
	float shimmer = noise(vec2(uv.x * 30.0, uv.y * 4.0 - u_time * 0.5));
	mask *= 0.6 + 0.4 * shimmer;

	// Matiz desliza lentamente entre verde e violeta/azul, típico de aurora, modulado pela
	// altura (base mais verde, topo mais violeta) e por v_lifeFrac (usa u_color/u_endColor
	// como âncoras de matiz via mix simples de RGB, sem depender de HSV do usuário).
	float hue = 0.33 + 0.25 * sin(u_time * 0.15 + uv.y * 1.5);
	vec3 auroraColor = hsv2rgb(vec3(hue, 0.75, 1.0));
	vec3 rgb = mix(auroraColor, mix(u_color.rgb, u_endColor.rgb, v_lifeFrac), 0.25);

	float alpha = mask * v_alpha * u_color.a;
	if (alpha <= 0.001) {
		discard;
	}
	fragColor = vec4(rgb, alpha);
}
