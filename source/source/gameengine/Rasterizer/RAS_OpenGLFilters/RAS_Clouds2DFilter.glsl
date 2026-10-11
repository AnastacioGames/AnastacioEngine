
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
uniform float ge_CloudsMask; // 1: Clouds, 2: Sky Layers (both can be on)
uniform vec4 ge_SkyLayersParams; // coverage, scale, speed, time
uniform vec3 ge_SkyLayersColor;

/* Volumetric Clouds (Stage 2 real raymarch). params1 = coverage, scale, speed, time;
 * params2 = altitude, thickness, density, detail_scale; params3 = silver_intensity,
 * quality (0 Low/1 Medium/2 High), shadow_enable, shadow_strength. */
uniform vec4 ge_VCloudsParams1;
uniform vec4 ge_VCloudsParams2;
uniform vec4 ge_VCloudsParams3;
uniform vec3 ge_VCloudsColor;
uniform vec3 ge_VCloudsSunDir;

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

/* World-space position of the pixel's scene geometry, reconstructed from the depth buffer
 * with the same inverse matrices as skyViewDirection -- used both as the camera's raymarch
 * occlusion distance (clouds behind terrain/mountains) and as the shading point for the
 * terrain cloud-shadow approximation below. */
vec3 worldPosFromDepth(vec2 uv, float depth)
{
	vec4 clip = vec4(uv * 2.0 - 1.0, depth * 2.0 - 1.0, 1.0);
	vec4 viewSpace = unfinvprojmat * clip;
	viewSpace /= viewSpace.w;
	return (unfinvviewmat * vec4(viewSpace.xyz, 1.0)).xyz;
}

/* ---- Volumetric Clouds (Stage 2): density field + raymarch ----
 * No baked 3D texture: the base shape reuses cloudFbm (already a 3D Perlin-ish FBM) and the
 * erosion detail is a cheap procedural Worley-style noise (cloudWorley below), both evaluated
 * directly at each raymarch sample's world position. This engine has no existing precedent for
 * generating/uploading a 3D texture (compute or slice-by-slice), so doing the density field
 * procedurally avoids inventing that infrastructure for a single effect -- see final report. */
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

/* wp in world units; altitude/thickness define the cloud slab on Z (Blender/UPBGE is Z-up). */
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

/* Mini-raymarch toward the sun (self-shadowing / light reaching the underside of the cloud). */
float cloudLightMarch(vec3 wp, vec3 sunDir, float coverage, float scale, float detailScale, float altitude, float thickness, float densityMul)
{
	float stepLen = max(thickness, 1.0) * 0.15;
	float dens = 0.0;
	vec3 p = wp;
	for (int i = 0; i < 6; i++) {
		p += sunDir * stepLen;
		dens += cloudDensityAt(p, coverage, scale, detailScale, altitude, thickness, densityMul);
	}
	return exp(-dens * stepLen * 0.25);
}

float henyeyGreenstein(float cosAngle, float g)
{
	float g2 = g * g;
	return (1.0 - g2) / (4.0 * 3.14159265 * pow(max(1.0 + g2 - 2.0 * g * cosAngle, 0.0001), 1.5));
}

/* Dual-lobe HG: broad forward+back scattering plus a tight near-forward lobe scaled by
 * silver_intensity for the bright rim around the sun (silver lining). */
float cloudPhase(float cosAngle, float silver)
{
	float forward = henyeyGreenstein(cosAngle, 0.75);
	float back = henyeyGreenstein(cosAngle, -0.2);
	float silverLobe = henyeyGreenstein(cosAngle, 0.99) * silver * 2.0;
	return max(forward, back) + silverLobe;
}

/* Interleaved gradient noise (Jorge Jimenez, SIGGRAPH 2014) to dither the raymarch start
 * offset per pixel instead of banding between coarse steps -- no extra texture needed. */
float interleavedGradientNoise(vec2 uv)
{
	vec3 magic = vec3(0.06711056, 0.00583715, 52.9829189);
	return fract(magic.z * fract(dot(uv, magic.xy)));
}

/* Two-phase raymarch (coarse empty-space skip to find the cloud entry point, then a detail
 * pass that accumulates light) through the horizontal cloud slab, stopping at maxDist (the
 * scene depth) so terrain/mountains correctly occlude the clouds behind them. Returns
 * (premultiplied color, alpha). */
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
			accumColor += transmittance * stepAbsorb * cloudColor * (0.35 + 1.3 * max(lit, 0.0));
			transmittance *= (1.0 - stepAbsorb);
		}
		t += detailStep;
	}

	return vec4(accumColor, clamp(1.0 - transmittance, 0.0, 1.0));
}

/* Cheap terrain shadow: marches the SAME procedural density field from the terrain pixel
 * toward the sun through the cloud slab (8-16 steps, density only, no phase function) --
 * an approximation kept entirely inside this post-process filter (it already has depth and
 * the inverse matrices needed to reconstruct world position) instead of injecting a cloud
 * shadow map/matrix into the generic material shader's light loop, see final report. */
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

	float depth = texture(bgl_DepthTexture, texcoord).x;
	bool vcloudsOn = mod(floor(ge_CloudsMask / 4.0), 2.0) > 0.5 && ge_VCloudsParams1.x > 0.001;
	if (depth < 0.9999) {
		/* Near geometry (terrain/mountains): Clouds and Sky Layers never paint over it, only
		 * the Volumetric Clouds terrain-shadow approximation can darken it. */
		vec3 color = direct.rgb;
		if (vcloudsOn && ge_VCloudsParams3.z > 0.5 && ge_VCloudsParams3.w > 0.001) {
			vec3 worldPos = worldPosFromDepth(texcoord, depth);
			float shadow = cloudTerrainShadow(worldPos, normalize(ge_VCloudsSunDir), ge_VCloudsParams1, ge_VCloudsParams2);
			color *= mix(1.0, shadow, clamp(ge_VCloudsParams3.w, 0.0, 1.0));
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

	float coverage = ge_CloudsParams.x;
	if (mod(ge_CloudsMask, 2.0) > 0.5 && coverage > 0.001) {
		float scale = max(0.0001, ge_CloudsParams.y);
		vec3 p = viewDir * scale * 4.0 + vec3(ge_CloudsParams.w * ge_CloudsParams.z, 0.0, 0.0);
		float density = cloudFbm(p);
		float mask = smoothstep(1.0 - coverage, 1.0 - coverage + 0.25, density) * horizonFade;
		color = mix(color, ge_CloudsColor, mask);
	}

	if (ge_CloudsMask > 1.5 && ge_SkyLayersParams.x > 0.001) {
		vec2 layered = layeredClouds(viewDir, ge_SkyLayersParams.x, max(0.0001, ge_SkyLayersParams.y), ge_SkyLayersParams.z, ge_SkyLayersParams.w);
		color = mix(color, ge_SkyLayersColor * layered.y, layered.x * horizonFade);
	}

	/* Volumetric Clouds, Stage 2: bit 2 of the mask (value 4). Real two-phase raymarch
	 * through a world-space cloud slab, occluded by the scene depth (far-plane here, since
	 * near geometry already returned above), with self-shadow and silver lining. */
	vec3 sunDirForDisc = vec3(0.0);
	bool haveSunDir = false;
	if (vcloudsOn) {
		vec3 camPos = (unfinvviewmat * vec4(0.0, 0.0, 0.0, 1.0)).xyz;
		/* Sky pixel: nothing occludes the ray before the far plane. A huge-but-finite distance
		 * keeps the slab intersection math well-conditioned (this is after the depth<0.9999
		 * early-return, so every pixel here is background/far-plane). */
		float maxDist = 1e5;
		vec3 sunDir = normalize(ge_VCloudsSunDir);
		sunDirForDisc = sunDir;
		haveSunDir = true;
		vec4 raymarch = volumetricCloudsRaymarch(camPos, viewDir, maxDist, sunDir,
		                                          ge_VCloudsParams1, ge_VCloudsParams2, ge_VCloudsParams3,
		                                          ge_VCloudsColor, texcoord * vec2(1920.0, 1080.0));
		color = mix(color, raymarch.rgb / max(raymarch.a, 0.0001), raymarch.a * horizonFade);
	}

	/* Visible sun disc + glow, drawn on top of the cloud layer so it reads as light behind
	 * them instead of a gap. The legacy sky-blend background can render very dark, so this
	 * is drawn unconditionally (not multiplied by horizonFade) wherever the sun direction is
	 * known, to keep the sky readable regardless of that separate issue. */
	if (haveSunDir) {
		float cosSun = dot(viewDir, sunDirForDisc);
		float sunAngle = acos(clamp(cosSun, -1.0, 1.0));
		/* Angle-based falloff (not pow(cos, N)) so the glow stays visible across a wide margin
		 * of camera/sun placement instead of needing near pixel-perfect alignment. */
		float disc = 1.0 - smoothstep(0.012, 0.022, sunAngle);
		float core = exp(-(sunAngle * sunAngle) / (2.0 * 0.07 * 0.07)) * 0.9;
		float haze = exp(-(sunAngle * sunAngle) / (2.0 * 0.32 * 0.32)) * 0.35;
		vec3 sunTint = vec3(1.0, 0.92, 0.75);
		color += sunTint * (core + haze);
		color = mix(color, sunTint, disc);
	}

	gl_FragColor = vec4(color, direct.a);
}
