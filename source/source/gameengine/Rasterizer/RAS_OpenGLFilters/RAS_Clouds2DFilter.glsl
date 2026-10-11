
#ifdef USE_CORE_PROFILE
in vec2 texCoordVarying;

out vec4 fragColor;
  #define gl_FragColor fragColor
#endif

uniform sampler2D bgl_RenderedTexture;
uniform sampler2D bgl_DepthTexture;

uniform mat4 unfviewmat;
uniform mat4 unfprojmat;
uniform mat4 unfinvviewmat;
uniform mat4 unfinvprojmat;

uniform vec4 ge_CloudsParams; // coverage, scale, speed, time
uniform vec3 ge_CloudsColor;
uniform float ge_CloudsStyle; // World.cloud_style: 0 Procedural, 1 Layered Sky

vec2 texcoord;

float cloudHash(vec3 p)
{
	return fract(sin(dot(p, vec3(127.1, 311.7, 74.7))) * 43758.5453123);
}

/* Trilinear value noise sampled directly on the view direction (a point on the unit
 * sphere) instead of unwrapped lon/lat -- lon wraps at +-pi, which would otherwise show
 * up as a hard seam running down the sky where the wraparound jumps the noise input. */
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

/* World-space view ray direction for this pixel, same trick used by the atmospheric
 * sky/stars shader (world_stars() in gpu_shader_material.glsl) -- sampling noise by this
 * direction instead of raw screen texcoord anchors the cloud pattern to the sky, so it
 * doesn't slide sideways when the camera only rotates. */
vec3 skyViewDirection(vec2 uv)
{
	vec4 clip = vec4(uv * 2.0 - 1.0, 1.0, 1.0);
	vec4 viewSpace = unfinvprojmat * clip;
	viewSpace /= viewSpace.w;
	return normalize((unfinvviewmat * vec4(viewSpace.xyz, 0.0)).xyz);
}

/* Layered Sky style (adapted from a node sky material): the view ray hits a flat sky plane, two value-noise
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
#ifdef USE_CORE_PROFILE
	texcoord = texCoordVarying;
#else
	texcoord = gl_TexCoord[0].st;
#endif

	vec4 direct = texture(bgl_RenderedTexture, texcoord);

	float coverage = ge_CloudsParams.x;
	float scale = max(0.0001, ge_CloudsParams.y);
	float speed = ge_CloudsParams.z;
	float time = ge_CloudsParams.w;

	if (coverage <= 0.001) {
		gl_FragColor = direct;
		return;
	}

	/* Only draw over background/sky pixels (far-plane depth), same depth-mask
	 * trick already used by the rain puddles -- never over near geometry. */
	float depth = texture(bgl_DepthTexture, texcoord).x;
	float isSky = step(0.9999, depth);

	if (isSky < 0.5) {
		gl_FragColor = direct;
		return;
	}

	/* World is Z-up (Blender/UPBGE convention) -- viewDir.z is elevation. */
	vec3 viewDir = skyViewDirection(texcoord);

	if (ge_CloudsStyle > 0.5) {
		vec2 layered = layeredClouds(viewDir, coverage, scale, speed, time);
		float alpha = layered.x * smoothstep(-0.02, 0.18, viewDir.z);
		gl_FragColor = vec4(mix(direct.rgb, ge_CloudsColor * layered.y, alpha), direct.a);
		return;
	}

	vec3 p = viewDir * scale * 4.0 + vec3(time * speed, 0.0, 0.0);
	float density = cloudFbm(p);
	float mask = smoothstep(1.0 - coverage, 1.0 - coverage + 0.25, density);

	/* Clouds only belong above the horizon -- fade them out toward and below it instead of
	 * a hard cut, since the "isSky" depth test above can't tell an infinite ground plane's
	 * background fill from real sky. */
	float horizonFade = smoothstep(-0.02, 0.18, viewDir.z);
	mask *= horizonFade;

	vec3 finalColor = mix(direct.rgb, ge_CloudsColor, mask);

	gl_FragColor = vec4(finalColor, direct.a);
}
