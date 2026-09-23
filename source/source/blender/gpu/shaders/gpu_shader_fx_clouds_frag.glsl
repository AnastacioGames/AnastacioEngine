
in vec4 uvcoord; // coordinates [0.0, 1.0]

uniform sampler2D colorbuffer; // color buffer
uniform sampler2D depthbuffer; // depth buffer

uniform vec4 clouds_params; // coverage, scale, speed, time
uniform vec3 clouds_color;

float cloudHash(vec3 p)
{
	return fract(sin(dot(p, vec3(127.1, 311.7, 74.7))) * 43758.5453123);
}

float cloudNoise(vec3 p)
{
	vec3 i = floor(p);
	vec3 f = fract(p);
	vec3 u = f * f * (3.0 - 2.0 * f);

	float a000 = cloudHash(i + vec3(0.0, 0.0, 0.0));
	float a100 = cloudHash(i + vec3(1.0, 0.0, 0.0));
	float a010 = cloudHash(i + vec3(0.0, 1.0, 0.0));
	float a110 = cloudHash(i + vec3(1.0, 1.0, 0.0));
	float a001 = cloudHash(i + vec3(0.0, 0.0, 1.0));
	float a101 = cloudHash(i + vec3(1.0, 0.0, 1.0));
	float a011 = cloudHash(i + vec3(0.0, 1.0, 1.0));
	float a111 = cloudHash(i + vec3(1.0, 1.0, 1.0));

	float x00 = mix(a000, a100, u.x);
	float x10 = mix(a010, a110, u.x);
	float x01 = mix(a001, a101, u.x);
	float x11 = mix(a011, a111, u.x);
	float y0 = mix(x00, x10, u.y);
	float y1 = mix(x01, x11, u.y);
	return mix(y0, y1, u.z);
}

float cloudFbm(vec3 p)
{
	float sum = 0.0;
	float amp = 0.5;
	for (int i = 0; i < 5; i++) {
		sum += cloudNoise(p) * amp;
		p *= 2.0;
		amp *= 0.5;
	}
	return sum;
}

/* World-space view ray direction for this pixel, reconstructed with the fixed-function
 * gl_*MatrixInverse builtins instead of the game engine's own view/proj uniforms, since
 * this compositor is compat-profile (same trick as gpu_shader_fx_rain_frag.glsl). */
vec3 skyViewDirection(vec2 uv)
{
	vec4 clip = vec4(uv * 2.0 - 1.0, 1.0, 1.0);
	vec4 viewSpace = gl_ProjectionMatrixInverse * clip;
	viewSpace /= viewSpace.w;
	return normalize((gl_ModelViewMatrixInverse * vec4(viewSpace.xyz, 0.0)).xyz);
}

void main()
{
	vec2 texcoord = uvcoord.xy;
	vec4 direct = texture(colorbuffer, texcoord);

	float coverage = clouds_params.x;
	float scale = max(0.0001, clouds_params.y);
	float speed = clouds_params.z;
	float time = clouds_params.w;

	if (coverage <= 0.001) {
		gl_FragColor = direct;
		return;
	}

	float depth = texture(depthbuffer, texcoord).x;
	float isSky = step(0.9999, depth);

	if (isSky < 0.5) {
		gl_FragColor = direct;
		return;
	}

	vec3 viewDir = skyViewDirection(texcoord);

	vec3 p = viewDir * scale * 4.0 + vec3(time * speed, 0.0, 0.0);
	float density = cloudFbm(p);
	float mask = smoothstep(1.0 - coverage, 1.0 - coverage + 0.25, density);

	float horizonFade = smoothstep(-0.02, 0.18, viewDir.z);
	mask *= horizonFade;

	vec3 finalColor = mix(direct.rgb, clouds_color, mask);

	gl_FragColor = vec4(finalColor, direct.a);
}
