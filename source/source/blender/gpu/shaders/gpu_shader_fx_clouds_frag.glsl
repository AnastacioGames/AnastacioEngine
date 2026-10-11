
in vec4 uvcoord; // coordinates [0.0, 1.0]

uniform sampler2D colorbuffer; // color buffer
uniform sampler2D depthbuffer; // depth buffer

uniform vec4 clouds_params; // coverage, scale, speed, time
uniform vec3 clouds_color;
uniform float clouds_mask; // bits: 1 Clouds, 2 Sky Layers, 4 Volumetric Clouds (any combination)
uniform vec4 sky_layers_params; // coverage, scale, speed, time
uniform vec3 sky_layers_color;
uniform vec3 clouds_quality; // Clouds octaves, Sky Layers octaves, Sky Layers relief

/* Volumetric Clouds (Stage 2 real raymarch), mirrors RAS_Clouds2DFilter.glsl. */
uniform vec4 vclouds_params1; // coverage, scale, speed, time
uniform vec4 vclouds_params2; // altitude, thickness, density, detail_scale
uniform vec4 vclouds_params3; // silver_intensity, quality, shadow_enable, shadow_strength
uniform vec3 vclouds_color;
uniform vec3 vclouds_sundir;

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

/* cloudFbm with a chosen octave count (Detail, 1-8). Normalized to the 5-octave range so the
 * coverage reads the same at any Detail; 5 octaves gives exactly cloudFbm. */
float cloudFbmDetail(vec3 p, float octaves)
{
	float sum = 0.0;
	float amp = 0.5;
	for (int i = 0; i < 8; i++) {
		if (float(i) >= octaves) {
			break;
		}
		sum += cloudNoise(p) * amp;
		p *= 2.0;
		amp *= 0.5;
	}
	return sum * 0.96875 / (1.0 - 2.0 * amp);
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

vec3 worldPosFromDepth(vec2 uv, float depth)
{
	vec4 clip = vec4(uv * 2.0 - 1.0, depth * 2.0 - 1.0, 1.0);
	vec4 viewSpace = gl_ProjectionMatrixInverse * clip;
	viewSpace /= viewSpace.w;
	return (gl_ModelViewMatrixInverse * vec4(viewSpace.xyz, 1.0)).xyz;
}

/* ---- Volumetric Clouds (Stage 2): density field + raymarch ----
 * Mirrors RAS_Clouds2DFilter.glsl -- see that file for the rationale on using a procedural
 * density field (cloudFbm + cloudWorley sampled per raymarch sample) instead of a baked 3D
 * texture. */
float worleyHash3(vec3 p)
{
	p = fract(p * vec3(0.1031, 0.1030, 0.0973));
	p += dot(p, p.yxz + 33.33);
	return fract((p.x + p.y) * p.z);
}

float cloudWorley(vec3 p)
{
	vec3 cell = floor(p);
	float minDist = 1.0;
	for (int dz = 0; dz <= 1; dz++) {
		for (int dy = 0; dy <= 1; dy++) {
			for (int dx = 0; dx <= 1; dx++) {
				vec3 neighbor = cell + vec3(float(dx), float(dy), float(dz));
				vec3 pt = neighbor + vec3(worleyHash3(neighbor), worleyHash3(neighbor + 7.1), worleyHash3(neighbor + 13.7));
				minDist = min(minDist, length(pt - p));
			}
		}
	}
	return 1.0 - clamp(minDist, 0.0, 1.0);
}

float cloudDensityAt(vec3 wp, float coverage, float scale, float detailScale, float altitude, float thickness, float densityMul)
{
	float hf = clamp((wp.z - altitude) / max(thickness, 1.0), 0.0, 1.0);
	float heightGrad = smoothstep(0.0, 0.2, hf) * smoothstep(1.0, 0.65, hf);
	if (heightGrad <= 0.001) {
		return 0.0;
	}
	float base = cloudFbm(wp * scale);
	float shape = smoothstep(1.0 - coverage, 1.0, base + heightGrad * 0.15);
	if (shape <= 0.001) {
		return 0.0;
	}
	float detail = cloudWorley(wp * detailScale);
	float density = clamp(shape - detail * 0.35 * shape, 0.0, 1.0);
	return density * heightGrad * densityMul;
}

float cloudLightMarch(vec3 wp, vec3 sunDir, float coverage, float scale, float detailScale, float altitude, float thickness, float densityMul)
{
	float stepLen = max(thickness, 1.0) * 0.15;
	float dens = 0.0;
	vec3 p = wp;
	for (int i = 0; i < 6; i++) {
		p += sunDir * stepLen;
		dens += cloudDensityAt(p, coverage, scale, detailScale, altitude, thickness, densityMul);
	}
	return exp(-dens * stepLen * 0.5);
}

float henyeyGreenstein(float cosAngle, float g)
{
	float g2 = g * g;
	return (1.0 - g2) / (4.0 * 3.14159265 * pow(max(1.0 + g2 - 2.0 * g * cosAngle, 0.0001), 1.5));
}

float cloudPhase(float cosAngle, float silver)
{
	float forward = henyeyGreenstein(cosAngle, 0.75);
	float back = henyeyGreenstein(cosAngle, -0.2);
	/* Narrower, hotter forward lobe than the base scattering -- this is the thin bright rim
	 * RDR2-style clouds show around the sun, not a broad glow. */
	float silverLobe = henyeyGreenstein(cosAngle, 0.996) * silver * 4.0;
	return max(forward, back) + silverLobe;
}

float interleavedGradientNoise(vec2 uv)
{
	vec3 magic = vec3(0.06711056, 0.00583715, 52.9829189);
	return fract(magic.z * fract(dot(uv, magic.xy)));
}

vec4 volumetricCloudsRaymarch(vec3 camPos, vec3 rayDir, float maxDist, vec3 sunDir, vec4 p1, vec4 p2, vec4 p3, vec3 cloudColor, vec2 ditherUV)
{
	float coverage = p1.x;
	float scale = max(0.0001, p1.y) * 0.02;
	float altitude = p2.x;
	float thickness = max(1.0, p2.y);
	float densityMul = max(0.0001, p2.z);
	float detailScale = max(0.0001, p2.w) * 0.08;
	float silver = p3.x;
	int quality = int(p3.y + 0.5);

	int coarseSteps = (quality <= 0) ? 24 : ((quality == 1) ? 48 : 64);
	int detailSteps = (quality <= 0) ? 12 : ((quality == 1) ? 24 : 48);

	float top = altitude + thickness;
	float t0, t1;
	if (abs(rayDir.z) < 0.0001) {
		if (camPos.z < altitude || camPos.z > top) {
			return vec4(0.0);
		}
		t0 = 0.0;
		t1 = maxDist;
	}
	else {
		float ta = (altitude - camPos.z) / rayDir.z;
		float tb = (top - camPos.z) / rayDir.z;
		t0 = max(0.0, min(ta, tb));
		t1 = max(ta, tb);
	}
	if (t1 <= t0 || t0 >= maxDist) {
		return vec4(0.0);
	}
	t1 = min(t1, maxDist);

	float dither = interleavedGradientNoise(ditherUV);
	float coarseStep = (t1 - t0) / float(coarseSteps);
	float t = t0 + coarseStep * dither;

	bool inCloud = false;
	float enteredT = t0;
	for (int i = 0; i < 64; i++) {
		if (i >= coarseSteps || t > t1) {
			break;
		}
		vec3 p = camPos + rayDir * t;
		if (cloudDensityAt(p, coverage, scale, detailScale, altitude, thickness, densityMul) > 0.01) {
			inCloud = true;
			enteredT = t;
			break;
		}
		t += coarseStep;
	}

	if (!inCloud) {
		return vec4(0.0);
	}

	float cosAngle = dot(rayDir, sunDir);
	float phase = cloudPhase(cosAngle, silver);

	float transmittance = 1.0;
	vec3 accumColor = vec3(0.0);
	float detailStep = max(t1 - enteredT, 0.001) / float(detailSteps);
	t = enteredT + detailStep * dither;
	for (int i = 0; i < 64; i++) {
		if (i >= detailSteps || transmittance < 0.01 || t > t1) {
			break;
		}
		vec3 p = camPos + rayDir * t;
		float d = cloudDensityAt(p, coverage, scale, detailScale, altitude, thickness, densityMul);
		if (d > 0.001) {
			float lightT = cloudLightMarch(p, sunDir, coverage, scale, detailScale, altitude, thickness, densityMul);
			float powder = 1.0 - exp(-d * 3.0);
			float lit = lightT * mix(1.0, powder, 0.5) * phase;
			float stepAbsorb = clamp(d * detailStep * 0.08, 0.0, 1.0);
			/* Shadowed cloud reads as cool/grey ambient; sun-facing cloud bleaches toward white
			 * instead of just scaling the base tint, matching the punchy lit-vs-shadow look of
			 * RDR2 clouds rather than a flat grey puff. */
			vec3 ambientColor = cloudColor * vec3(0.72, 0.8, 0.95);
			vec3 litColor = mix(cloudColor, vec3(1.0), clamp(lit * 0.5, 0.0, 1.0));
			vec3 sampleColor = ambientColor * 0.18 + litColor * max(lit, 0.0);
			accumColor += transmittance * stepAbsorb * sampleColor;
			transmittance *= (1.0 - stepAbsorb);
		}
		t += detailStep;
	}

	return vec4(accumColor, clamp(1.0 - transmittance, 0.0, 1.0));
}

float cloudTerrainShadow(vec3 worldPos, vec3 sunDir, vec4 p1, vec4 p2)
{
	if (sunDir.z <= 0.001) {
		return 1.0;
	}
	float coverage = p1.x;
	float scale = max(0.0001, p1.y) * 0.02;
	float altitude = p2.x;
	float thickness = max(1.0, p2.y);
	float densityMul = max(0.0001, p2.z);
	float detailScale = max(0.0001, p2.w) * 0.08;

	float top = altitude + thickness;
	float tBottom = (altitude - worldPos.z) / sunDir.z;
	float tTop = (top - worldPos.z) / sunDir.z;
	float t0 = max(0.0, min(tBottom, tTop));
	float t1 = max(tBottom, tTop);
	if (t1 <= t0) {
		return 1.0;
	}

	const int steps = 12;
	float stepLen = (t1 - t0) / float(steps);
	float dens = 0.0;
	for (int i = 0; i < steps; i++) {
		float t = t0 + stepLen * (float(i) + 0.5);
		vec3 p = worldPos + sunDir * t;
		dens += cloudDensityAt(p, coverage, scale, detailScale, altitude, thickness, densityMul);
	}
	return exp(-dens * stepLen * 0.6);
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

/* Octaves = Detail (1-8), normalized to the 5-octave range; 5 gives the original look. */
float skyFbm2(vec2 p, float octaves)
{
	float sum = 0.0;
	float amp = 0.5;
	for (int i = 0; i < 8; i++) {
		if (float(i) >= octaves) {
			break;
		}
		sum += skyNoise2(p) * amp;
		p = p * 2.03 + vec2(1.7, 9.2);
		amp *= 0.5;
	}
	return sum * 0.96875 / (1.0 - 2.0 * amp);
}

/* relief 0 skips the offset sample (one noise pass less) and leaves the layers flat. */
vec2 layeredClouds(vec3 viewDir, float coverage, float scale, float speed, float time, float octaves, float relief)
{
	float up = max(viewDir.z, 0.02);
	vec2 base = viewDir.xy / up * scale * 0.5;
	float t = time * speed;
	vec2 pA = base + vec2(t * 0.5);
	vec2 pB = (base + vec2(t)) * 0.5;
	float a = skyFbm2(pA, octaves);
	float b = skyFbm2(pB, octaves);
	float alpha = clamp((a - b) * coverage * 20.0 * up, 0.0, 1.0);
	float shade = 0.8;
	if (relief > 0.001) {
		float lit = skyFbm2(pA + vec2(0.06, 0.04), octaves);
		shade = clamp(0.8 + (a - lit) * 6.0 * relief, 0.45, 1.2);
	}
	return vec2(alpha, shade);
}

void main()
{
	vec2 texcoord = uvcoord.xy;
	vec4 direct = texture(colorbuffer, texcoord);

	float depth = texture(depthbuffer, texcoord).x;
	bool vcloudsOn = mod(floor(clouds_mask / 4.0), 2.0) > 0.5 && vclouds_params1.x > 0.001;
	if (depth < 0.9999) {
		/* Near geometry: Clouds and Sky Layers never paint over it, only the Volumetric
		 * Clouds terrain-shadow approximation can darken it. */
		vec3 color = direct.rgb;
		if (vcloudsOn && vclouds_params3.z > 0.5 && vclouds_params3.w > 0.001) {
			vec3 worldPos = worldPosFromDepth(texcoord, depth);
			float shadow = cloudTerrainShadow(worldPos, normalize(vclouds_sundir), vclouds_params1, vclouds_params2);
			color *= mix(1.0, shadow, clamp(vclouds_params3.w, 0.0, 1.0));
		}
		gl_FragColor = vec4(color, direct.a);
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
		float density = cloudFbmDetail(p, clouds_quality.x);
		float mask = smoothstep(1.0 - coverage, 1.0 - coverage + 0.25, density) * horizonFade;
		color = mix(color, clouds_color, mask);
	}

	if (mod(floor(clouds_mask / 2.0), 2.0) > 0.5 && sky_layers_params.x > 0.001) {
		vec2 layered = layeredClouds(viewDir, sky_layers_params.x, max(0.0001, sky_layers_params.y), sky_layers_params.z, sky_layers_params.w,
		                               clouds_quality.y, clouds_quality.z);
		color = mix(color, sky_layers_color * layered.y, layered.x * horizonFade);
	}

	/* Volumetric Clouds, Stage 2: real two-phase raymarch through a world-space cloud slab. */
	if (vcloudsOn) {
		vec3 camPos = (gl_ModelViewMatrixInverse * vec4(0.0, 0.0, 0.0, 1.0)).xyz;
		float maxDist = 1e5;
		vec4 raymarch = volumetricCloudsRaymarch(camPos, viewDir, maxDist, normalize(vclouds_sundir),
		                                          vclouds_params1, vclouds_params2, vclouds_params3,
		                                          vclouds_color, texcoord * vec2(1920.0, 1080.0));
		color = mix(color, raymarch.rgb / max(raymarch.a, 0.0001), raymarch.a * horizonFade);
	}

	gl_FragColor = vec4(color, direct.a);
}
