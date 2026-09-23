
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

uniform vec4 ge_RainParams1; // intensity, speed, wind, darken
uniform vec4 ge_RainParams2; // ripple intensity, time, use droplets, use ripple
uniform vec4 ge_RainParams3; // density, ripple radius, minimum upward normal, unused
uniform vec3 ge_RainColor;
uniform float ge_RainStyle; // 0 = Classic (screen-space streaks), 1 = Volumetric (world-space streaks)

vec2 texcoord;

/* Streaks: screen-space value-noise layers (base: RainFX.py rainLayer/hash/valueNoise). */
float rainHash(vec2 p)
{
	return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453123);
}

float rainValueNoise(vec2 p)
{
	vec2 i = floor(p);
	vec2 f = fract(p);
	float a = rainHash(i);
	float b = rainHash(i + vec2(1.0, 0.0));
	float c = rainHash(i + vec2(0.0, 1.0));
	float d = rainHash(i + vec2(1.0, 1.0));
	vec2 u = f * f * (3.0 - 2.0 * f);
	return mix(a, b, u.x) + (c - a) * u.y * (1.0 - u.x) + (d - b) * u.x * u.y;
}

float rainLayer(vec2 uv, float scale, float speed, float sharpness, float wind, float time)
{
	vec2 p = uv;
	p.x += p.y * wind * 0.4;
	p *= vec2(scale * 0.6, scale * 0.06);
	p.y += time * speed;
	float n = rainValueNoise(p);
	return pow(clamp(n, 0.0, 1.0), sharpness);
}

/* Puddle ripples: world-space cellular rings sampled from reconstructed depth
 * (base: Rain.glsl createHash/getRainRipples3D), reconstructed with this engine's
 * real view/projection uniforms instead of legacy fixed-function matrices. */
vec3 rainCellHash(vec3 position)
{
	return fract(
		sin(vec3(
			dot(position, vec3(1.0, 57.0, 113.0)),
			dot(position, vec3(57.0, 113.0, 1.0)),
			dot(position, vec3(113.0, 1.0, 57.0))))
		* 43758.5453);
}

float rainRipples3D(vec3 coord, float time)
{
	vec3 i = floor(coord);
	vec3 f = fract(coord);
	float rippleEffect = 0.0;

	for (int z = -1; z <= 1; z++) {
		for (int y = -1; y <= 1; y++) {
			for (int x = -1; x <= 1; x++) {
				vec3 neighbor = vec3(float(x), float(y), float(z));
				vec3 randomVector = rainCellHash(i + neighbor);
				vec3 difference = neighbor - f + randomVector;

				float dist = length(difference);
				float dropTime = fract(time * 2.0 + randomVector.x);

				float distToRing1 = abs(dist - dropTime);
				float distToRing2 = abs(dist - dropTime + 0.12);

				float ring1 = smoothstep(0.09, 0.0, distToRing1);
				float ring2 = smoothstep(0.09, 0.0, distToRing2);

				float fade = 1.0 - smoothstep(0.3, 0.95, dropTime);
				float totalRing = (ring1 + ring2 * 0.4) * fade;

				rippleEffect = max(rippleEffect, totalRing);
			}
		}
	}
	return rippleEffect;
}

vec3 getWorldPositionFromDepth(vec2 uv, float depthValue)
{
	vec4 ndcPosition = vec4(uv * 2.0 - 1.0, depthValue * 2.0 - 1.0, 1.0);

	vec4 viewSpacePosition = unfinvprojmat * ndcPosition;
	viewSpacePosition /= viewSpacePosition.w;

	vec4 worldSpacePosition = unfinvviewmat * viewSpacePosition;

	return worldSpacePosition.xyz;
}

/* "Volumetric" rain style: world-space streaks marched along the view ray (base:
 * user-provided rain shader's getSingleRainLayer). Reuses this file's own
 * rainCellHash/getWorldPositionFromDepth instead of duplicating them, and is called
 * from a single wrapper (rainVolumetricStreaks below) instead of 3 separate top-level
 * calls -- but still samples 3 real, independently-hashed layers: collapsing them into
 * one continuous sample (an earlier version of this function) reads as much sparser
 * rain, since it's the 3 overlapping noise fields that make it look dense. */
float rainStreakLayer(vec3 p, float layerScale, float speedMod, float seed, float time)
{
	vec3 p_scaled = p * layerScale * 4.5;
	p_scaled.z += time * 500.0 * speedMod;

	vec3 cell = floor(p_scaled);
	vec3 f = fract(p_scaled);
	vec3 h = rainCellHash(cell + seed);

	vec2 center = h.xy * 0.8 + 0.1;
	float horizontalDist = length(f.xy - center);

	float streak = smoothstep(0.15, 0.0, horizontalDist);
	float verticalMask = smoothstep(0.0, 0.15, f.z) * smoothstep(1.0, 0.5, f.z);

	return streak * verticalMask * h.z;
}

float rainVolumetricStreaks(vec3 camPos, vec3 viewDir, float sceneDepth, float time)
{
	float rain = 0.0;

	if (sceneDepth > 1.5) {
		rain += rainStreakLayer(camPos + viewDir * 1.5, 0.6, 1.2, 12.34, time) * 0.1;
	}
	if (sceneDepth > 4.0) {
		rain += rainStreakLayer(camPos + viewDir * 4.0, 1.2, 1.0, 56.78, time) * 0.3;
	}
	if (sceneDepth > 10.0) {
		rain += rainStreakLayer(camPos + viewDir * 10.0, 2.2, 0.8, 91.01, time) * 0.8;
	}

	return rain;
}

void main()
{
#ifdef USE_CORE_PROFILE
	texcoord = texCoordVarying;
#else
	texcoord = gl_TexCoord[0].st;
#endif

	vec4 direct = texture(bgl_RenderedTexture, texcoord);

	float intensity = ge_RainParams1.x;
	float speed = ge_RainParams1.y;
	float wind = ge_RainParams1.z;
	float darken = ge_RainParams1.w;
	float rippleIntensity = ge_RainParams2.x;
	float time = ge_RainParams2.y;
	bool useDroplets = ge_RainParams2.z > 0.5;
	bool useRipple = ge_RainParams2.w > 0.5;
	/* Files saved before the density field was added have zero in that slot.
	 * Keep them visually compatible with the original Classic rain instead of
	 * multiplying every layer by zero. */
	float density = max(ge_RainParams3.x, 0.25);
	float rippleRadius = ge_RainParams3.y;
	float rippleMinUp = ge_RainParams3.z;

	if (intensity <= 0.001) {
		gl_FragColor = direct;
		return;
	}

	/* Ceu nublado: escurece e dessatura levemente a cena inteira. */
	float luma = dot(direct.rgb, vec3(0.299, 0.587, 0.114));
	vec3 overcast = mix(direct.rgb, vec3(luma) * 0.85, darken);

	vec3 finalColor = overcast;

	if (useDroplets) {
		float streaks;

		if (ge_RainStyle > 0.5) {
			/* Volumetric: streaks marched in world space along the view ray, so they
			 * get real depth/parallax instead of sliding with screen-space UV. */
			float depth = texture(bgl_DepthTexture, texcoord).x;
			vec3 camPos = (unfinvviewmat * vec4(0.0, 0.0, 0.0, 1.0)).xyz;
			vec3 worldPos = getWorldPositionFromDepth(texcoord, depth);
			vec3 viewDir = normalize(worldPos - camPos);
			float sceneDepth = length(worldPos - camPos);

			streaks = rainVolumetricStreaks(camPos, viewDir, sceneDepth, time * speed);
		}
		else {
			/* Classic: two screen-space layers for a sense of parallax -- a few thick,
			 * fast, sharply-defined streaks up close, and many thin, slower, softer
			 * ones further back. */
			/* The former 12/30 power masks retained only exceptionally bright noise
			 * samples, so Classic could look entirely dry at ordinary resolutions.
			 * These narrower, lower-power layers keep individual streaks visible. */
			streaks = rainLayer(texcoord, 15.0 * density, speed * 1.3, 6.0, wind, time) * 0.75;

			streaks += rainLayer(texcoord + vec2(3.7, 1.3), 55.0 * density, speed * 0.6, 12.0, wind * 0.7, time) * 0.50;
			streaks += rainLayer(texcoord + vec2(9.1, 5.2), 80.0 * density, speed * 0.5, 14.0, wind * 0.7, time) * 0.35;
		}

		finalColor += ge_RainColor * streaks * intensity;
	}

	if (useRipple && rippleIntensity > 0.001) {
		float depth = texture(bgl_DepthTexture, texcoord).x;
		float isBackground = step(0.9999, depth);

		if (isBackground < 0.5) {
			vec3 worldPos = getWorldPositionFromDepth(texcoord, depth);
			vec3 camPos = (unfinvviewmat * vec4(0.0, 0.0, 0.0, 1.0)).xyz;
			vec3 normal = normalize(cross(dFdx(worldPos), dFdy(worldPos)));
			/* Derivative orientation is screen-dependent. Point it at the camera so
			 * undersides remain down-facing and cannot receive puddle ripples. */
			if (dot(normal, camPos - worldPos) < 0.0) {
				normal = -normal;
			}
			/* Blender/Range uses Z as the world-up axis. Testing Y here rejects
			 * horizontal floors and lets some vertical faces through. */
			if (length(worldPos - camPos) <= rippleRadius && normal.z >= rippleMinUp) {
				float rippleNoise = rainRipples3D(worldPos * 6.0, time);
				finalColor += vec3(rippleNoise * rippleIntensity * 0.15);
			}
		}
	}

	gl_FragColor = vec4(finalColor, direct.a);
}
