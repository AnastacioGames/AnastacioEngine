
in vec4 uvcoord; // coordinates [0.0, 1.0]

uniform sampler2D colorbuffer; // color buffer
uniform sampler2D depthbuffer; // depth buffer

uniform vec4 clouds_params; // coverage, scale, speed, time
uniform vec3 clouds_color;
uniform float clouds_mask; // 1: Clouds, 2: Sky Layers (both can be on)
uniform vec4 sky_layers_params; // coverage, scale, speed, time
uniform vec3 sky_layers_color;

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

/* Sky Layers (adapted from a node sky material): the view ray hits a flat sky plane, two value-noise
 * layers drift over it at different scale and speed and their difference is the cloud; a small offset sample
 * toward a fixed light direction gives the relief. Returns (alpha, shade). */
float skyHash2(vec2 p)
{
	return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453123);
}

float skyNoise2(vec2 p)
{
	vec2 i = floor(p);
	vec2 f = fract(p);
	vec2 u = f * f * (3.0 - 2.0 * f);
	float a = skyHash2(i);
	float b = skyHash2(i + vec2(1.0, 0.0));
	float c = skyHash2(i + vec2(0.0, 1.0));
	float d = skyHash2(i + vec2(1.0, 1.0));
	return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}

float skyFbm2(vec2 p)
{
	float sum = 0.0;
	float amp = 0.5;
	for (int i = 0; i < 5; i++) {
		sum += skyNoise2(p) * amp;
		p = p * 2.03 + vec2(1.7, 9.2);
		amp *= 0.5;
	}
	return sum;
}

vec2 layeredClouds(vec3 viewDir, float coverage, float scale, float speed, float time)
{
	float up = max(viewDir.z, 0.02);
	vec2 base = viewDir.xy / up * scale * 0.5;
	float t = time * speed;
	vec2 pA = base + vec2(t * 0.5);
	vec2 pB = (base + vec2(t)) * 0.5;
	float a = skyFbm2(pA);
	float b = skyFbm2(pB);
	float alpha = clamp((a - b) * coverage * 20.0 * up, 0.0, 1.0);
	float lit = skyFbm2(pA + vec2(0.06, 0.04));
	float shade = clamp(0.8 + (a - lit) * 6.0, 0.45, 1.2);
	return vec2(alpha, shade);
}

void main()
{
	vec2 texcoord = uvcoord.xy;
	vec4 direct = texture(colorbuffer, texcoord);

	float depth = texture(depthbuffer, texcoord).x;
	if (depth < 0.9999) {
		/* Only background/sky pixels (far-plane depth), never over near geometry. */
		gl_FragColor = direct;
		return;
	}

	/* World is Z-up (Blender/UPBGE convention) -- viewDir.z is elevation. */
	vec3 viewDir = skyViewDirection(texcoord);
	/* Clouds only belong above the horizon -- fade them out toward and below it instead of a hard cut, since the
	 * depth test above can't tell an infinite ground plane's background fill from real sky. */
	float horizonFade = smoothstep(-0.02, 0.18, viewDir.z);
	vec3 color = direct.rgb;

	float coverage = clouds_params.x;
	if (mod(clouds_mask, 2.0) > 0.5 && coverage > 0.001) {
		float scale = max(0.0001, clouds_params.y);
		vec3 p = viewDir * scale * 4.0 + vec3(clouds_params.w * clouds_params.z, 0.0, 0.0);
		float density = cloudFbm(p);
		float mask = smoothstep(1.0 - coverage, 1.0 - coverage + 0.25, density) * horizonFade;
		color = mix(color, clouds_color, mask);
	}

	if (clouds_mask > 1.5 && sky_layers_params.x > 0.001) {
		vec2 layered = layeredClouds(viewDir, sky_layers_params.x, max(0.0001, sky_layers_params.y), sky_layers_params.z, sky_layers_params.w);
		color = mix(color, sky_layers_color * layered.y, layered.x * horizonFade);
	}

	gl_FragColor = vec4(color, direct.a);
}
