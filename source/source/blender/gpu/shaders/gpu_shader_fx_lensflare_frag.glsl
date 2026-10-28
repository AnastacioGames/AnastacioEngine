
in vec4 uvcoord; // coordinates [0.0, 1.0]

uniform sampler2D colorbuffer; // color buffer
uniform sampler2D depthbuffer; // depth buffer

uniform vec3 sunpos; // world-space sun direction (same convention as light scatter fx)
uniform vec4 flare_params; // scale, intensity, time, quality (0 High, 1 Medium, 2 Low)
uniform vec2 viewport_size;

float lensNoise(float n)
{
	return fract(sin(n));
}

float lensNoise(vec2 co)
{
	return fract(sin(dot(co.xy, vec2(12.9898, 78.233))) * 43758.5453);
}

/* quality: 0 High, 1 Medium (no small ghosts), 2 Low (glow and the big ghosts only, no noise). */
vec3 lensflare(vec2 uv, vec2 pos, float sunscale, float timer, float quality)
{
	vec2 main = uv - pos;
	vec2 uvd = uv * length(uv);

	if (quality > 1.5) {
		float g0 = 1.8 / (length(main) / sunscale + 1.0);
		vec2 d2 = uvd + 0.8 * pos, d22 = uvd + 0.85 * pos, d23 = uvd + 0.9 * pos;
		vec3 ghost = vec3(0.25 / (1.0 + 32.0 * dot(d2, d2)), 0.23 / (1.0 + 32.0 * dot(d22, d22)),
		                  0.21 / (1.0 + 32.0 * dot(d23, d23)));
		return ghost + vec3(g0);
	}

	float ang = atan(main.y, main.x);
	float dist = length(main);
	dist = pow(dist, 0.1);
	float n = lensNoise(vec2((ang - timer / 9.0) * 16.0, dist * 32.0));

	float f0 = 1.0 / (length(uv - pos) / sunscale + 1.0);
	f0 = f0 + f0 * (sin((ang + timer / 18.0 + lensNoise(abs(ang) + n / 2.0) * 2.0) * 12.0) * 0.1 + dist * 0.1 + 0.8);

	float f2 = max(1.0 / (1.0 + 32.0 * pow(length(uvd + 0.8 * pos), 2.0)), 0.0) * 0.25;
	float f22 = max(1.0 / (1.0 + 32.0 * pow(length(uvd + 0.85 * pos), 2.0)), 0.0) * 0.23;
	float f23 = max(1.0 / (1.0 + 32.0 * pow(length(uvd + 0.9 * pos), 2.0)), 0.0) * 0.21;

	vec2 uvx = mix(uv, uvd, -0.5);

	float f4 = max(0.01 - pow(length(uvx + 0.4 * pos), 2.4), 0.0) * 6.0;
	float f42 = max(0.01 - pow(length(uvx + 0.45 * pos), 2.4), 0.0) * 5.0;
	float f43 = max(0.01 - pow(length(uvx + 0.5 * pos), 2.4), 0.0) * 3.0;

	vec3 c = vec3(f0);
	c.r += f2 + f4;
	c.g += f22 + f42;
	c.b += f23 + f43;
	if (quality > 0.5) {
		return c;
	}

	uvx = mix(uv, uvd, -0.4);

	float f5 = max(0.01 - pow(length(uvx + 0.2 * pos), 5.5), 0.0) * 2.0;
	float f52 = max(0.01 - pow(length(uvx + 0.4 * pos), 5.5), 0.0) * 2.0;
	float f53 = max(0.01 - pow(length(uvx + 0.6 * pos), 5.5), 0.0) * 2.0;

	uvx = mix(uv, uvd, -0.5);

	float f6 = max(0.01 - pow(length(uvx - 0.3 * pos), 1.6), 0.0) * 6.0;
	float f62 = max(0.01 - pow(length(uvx - 0.325 * pos), 1.6), 0.0) * 3.0;
	float f63 = max(0.01 - pow(length(uvx - 0.35 * pos), 1.6), 0.0) * 5.0;

	c.r += f5 + f6;
	c.g += f52 + f62;
	c.b += f53 + f63;

	return c;
}

void main()
{
	vec3 image = texture(colorbuffer, uvcoord.xy).rgb;

	/* Same convention as the light scatter fx: sunpos is a world-space direction,
	 * projected here to find where the sun sits on screen this frame. */
	vec3 cam_space = (gl_ModelViewMatrix * vec4(sunpos, 0.0)).xyz;
	vec4 clip_space = gl_ProjectionMatrix * vec4(cam_space, 0.0);

	/* clip_space.w <= 0 means the sun is behind or parallel to the view plane:
	 * keep the flare fully hidden instead of letting the divide fold it back
	 * onto a bogus on-screen position. */
	float visibility = step(1e-5, clip_space.w);

	vec2 sunScreenPos = (clip_space.xy / max(clip_space.w, 1e-5)) * 0.5 + 0.5;

	visibility *= step(0.0, sunScreenPos.x) * step(sunScreenPos.x, 1.0);
	visibility *= step(0.0, sunScreenPos.y) * step(sunScreenPos.y, 1.0);

	/* Cheap sun occlusion: depth-compare at the sun's own screen position instead
	 * of a CPU rayCast, same trick as the game engine's lens flare filter. Uses the
	 * same tolerant smoothstep as RAS_LensFlare2DFilter.glsl: an exact step(1.0, ...)
	 * against the background depth is too strict here (viewport depth precision/
	 * resolve leaves it just under 1.0), which was hiding the flare outside Play. */
	float sunDepth = texture(depthbuffer, clamp(sunScreenPos, 0.0, 1.0)).x;
	visibility *= smoothstep(0.995, 1.0, sunDepth);

	/* Sun hidden or off screen: same branch for every pixel, skip the flare math. */
	if (visibility <= 0.0) {
		gl_FragColor = vec4(image, 1.0);
		return;
	}

	float xconv = viewport_size.x / viewport_size.y;
	vec2 pos = vec2((sunScreenPos.x - 0.5) * xconv, sunScreenPos.y - 0.5);
	vec2 uv = vec2((uvcoord.x - 0.5) * xconv, uvcoord.y - 0.5);

	vec3 lens = lensflare(uv, pos, flare_params.x * 0.02, flare_params.z, flare_params.w);

	gl_FragColor = vec4(image + lens * flare_params.y * visibility, 1.0);
}
