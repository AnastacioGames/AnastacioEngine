
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
uniform vec4 ge_RainParams3; // density, ripple radius, minimum upward normal, splash distance
uniform vec4 ge_RainParams4; // use splash, splash size, splash rate, splash intensity
uniform vec4 ge_RainLightning; // flash, bolt, bolt screen position
uniform float ge_RainStreakWidth; // Classic streak width, 1 = 2 px at 1080p
uniform float ge_RainRippleNormal; // ripple normal strength, 1 = default
uniform vec4 ge_RainParams5; // ripple size, ripple rate, splash normal, splash minimum upward normal
uniform sampler2D ge_RainMask; // KX_RainSurfaceMask: R = 1 ripples + 2 splash, G = view depth
uniform vec3 ge_RainMaskFlags; // x: ripples only on marked objects, y: same for splash, z: puddles
uniform vec4 ge_RainPuddle1; // use puddles, amount, size (m), darkness
uniform vec4 ge_RainPuddle2; // reflection, distance, minimum upward normal, use SSR
uniform vec3 ge_RainSkyHorizon; // World horizon/zenith: what the puddles reflect
uniform vec3 ge_RainSkyZenith;
uniform vec3 ge_RainColor;
uniform float ge_RainStyle; // 0 = Classic (screen-space streaks), 1 = Volumetric (world-space streaks)

vec2 texcoord;

/* Classic streaks: thin anti-aliased lines measured in pixels, so they stay fine at any
 * resolution. Each column of cells scrolls down at its own speed and every cell holds at
 * most one drop with a short fading tail, so no streak ever spans the whole screen. */
float rainLineHash(vec2 p)
{
	return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453);
}

float rainLines(vec2 uv, vec2 res, float cellsX, float cellsY, float speed, float widthPx, float wind, float time, float seed)
{
	vec2 p = uv;
	p.x += p.y * wind * 0.4;
	float col = floor(p.x * cellsX);
	float hc = rainLineHash(vec2(col, seed));
	/* Wrapped scroll: rows are random, so the wrap is invisible and fract() keeps its precision. */
	float y = p.y * cellsY + mod(time * speed * cellsY * (0.8 + 0.4 * hc), 4096.0) + hc * 37.0;
	float row = floor(y);
	float f = fract(y);
	float h1 = rainLineHash(vec2(col + seed, row));
	float h2 = rainLineHash(vec2(row, col - seed));
	float h3 = rainLineHash(vec2(col + row, seed * 1.7));
	if (h3 < 0.3) {
		return 0.0;
	}
	float len = 0.2 + 0.45 * h2;
	if (f > len) {
		return 0.0;
	}
	float dx = abs(fract(p.x * cellsX) - (0.15 + 0.7 * h1)) * res.x / cellsX;
	/* Coverage of a line narrower than one pixel is its width. */
	float w = max(widthPx, 1.0);
	float line = clamp(0.5 * w + 0.5 - dx, 0.0, 1.0) * min(widthPx, 1.0);
	/* Head at the bottom, tail fading upward. */
	float tail = smoothstep(0.0, 0.03, f) * (1.0 - f / len);
	return line * tail * (0.5 + 0.5 * h3);
}

/* Three layers for depth: a few slightly wider, faster drops up close and many finer,
 * slower ones behind. widthScale 1 = 2 px at 1080p. */
float rainClassicStreaks(vec2 uv, vec2 res, float density, float speed, float wind, float widthScale, float time)
{
	float px = widthScale * 2.0 * res.y / 1080.0;
	float s = rainLines(uv, res, 45.0 * density, 5.0, speed * 1.6, px * 1.6, wind, time, 3.1) * 0.9;
	s += rainLines(uv, res, 90.0 * density, 8.0, speed * 1.2, px, wind * 0.8, time, 7.7) * 0.7;
	s += rainLines(uv, res, 160.0 * density, 13.0, speed * 0.9, px * 0.7, wind * 0.7, time, 12.9) * 0.5;
	return s;
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

/* Ripple water height: each cell drops once per cycle; the wave is a damped sine
 * inside an expanding ring (crest + trough), so its gradient reads as a bump normal. */
float rainRippleHeight(vec2 p, float time, float rate)
{
	vec2 i = floor(p);
	vec2 f = fract(p);
	float h = 0.0;

	for (int y = -1; y <= 1; y++) {
		for (int x = -1; x <= 1; x++) {
			vec2 n = vec2(float(x), float(y));
			vec3 r = rainCellHash(vec3(i + n, 0.0));
			float dist = length(n - f + r.xy);
			float t = fract(time * rate + r.z);
			float x0 = dist - t * 1.1;
			float wave = sin(x0 * 55.0) * exp(-x0 * x0 * 180.0);
			h += wave * (1.0 - t) * (1.0 - t);
		}
	}
	return h;
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

/* Splash: drops bouncing up where the rain hits upward-facing surfaces, edges included.
 * For each pixel, look a few pixels below for a surface cell (the drops rise above it),
 * then draw a crown + drops in a parabola for the 2x2 nearest cells of a world-space grid. */
#define SPLASH_SEARCH_STEPS 10
#define SPLASH_DROPS 8
#define SPLASH_GRAVITY 9.8

float splashCell;
float splashRate;
float splashHeight;
float splashRadius;
float splashDrop;
float splashTime;
float splashMinUp;
/* Splash > Only in Puddles: drops only where the puddle water is. */
bool splashInPuddles;
vec2 splashRes;

vec3 splashHash(vec3 p)
{
	return fract(sin(vec3(dot(p, vec3(127.1, 311.7, 74.7)),
	                      dot(p, vec3(269.5, 183.3, 246.1)),
	                      dot(p, vec3(113.5, 271.9, 124.6)))) * 43758.5453);
}

float splashDepthAt(vec2 uv)
{
	return texture(bgl_DepthTexture, uv).x;
}

vec3 splashViewPos(vec2 uv, float d)
{
	vec4 v = unfinvprojmat * vec4(uv * 2.0 - 1.0, d * 2.0 - 1.0, 1.0);
	return v.xyz / v.w;
}

vec3 splashWorldPos(vec2 uv, float d)
{
	return (unfinvviewmat * vec4(splashViewPos(uv, d), 1.0)).xyz;
}

/* xy = screen uv, z = distance along the view axis. */
vec3 splashProject(vec3 w)
{
	vec4 c = unfprojmat * (unfviewmat * vec4(w, 1.0));
	return vec3(c.xy / c.w * 0.5 + 0.5, c.w);
}

/* Puddle screen-space reflection: marches the reflected ray in world space, projecting each
 * step against the depth buffer, and refines the first crossing. rgb = scene color,
 * a = confidence (0 = left the screen, went behind an object or hit the sky). */
vec4 puddleSSR(sampler2D colorTex, vec3 origin, vec3 dir, float maxDist)
{
	float t = 0.05;
	float prevT = 0.0;
	for (int i = 0; i < 32; i++) {
		vec3 s = splashProject(origin + dir * t);
		if (s.z <= 0.0 || s.x < 0.0 || s.y < 0.0 || s.x > 1.0 || s.y > 1.0) {
			break;
		}
		float d = texture(bgl_DepthTexture, s.xy).x;
		if (s.z > -splashViewPos(s.xy, d).z) {
			float a = prevT;
			float b = t;
			for (int j = 0; j < 5; j++) {
				float m = (a + b) * 0.5;
				vec3 sm = splashProject(origin + dir * m);
				if (sm.z > -splashViewPos(sm.xy, texture(bgl_DepthTexture, sm.xy).x).z) {
					b = m;
				}
				else {
					a = m;
				}
			}
			s = splashProject(origin + dir * b);
			d = texture(bgl_DepthTexture, s.xy).x;
			/* Too far behind the surface found: the ray passed behind an object. */
			if (d >= 0.9999 || s.z + splashViewPos(s.xy, d).z > max(0.3, b * 0.1)) {
				break;
			}
			vec2 edge = smoothstep(vec2(0.0), vec2(0.08), s.xy) * smoothstep(vec2(0.0), vec2(0.08), 1.0 - s.xy);
			return vec4(texture(colorTex, s.xy).rgb, clamp(edge.x * edge.y * (1.0 - b / maxDist), 0.0, 1.0));
		}
		prevT = t;
		t += 0.1 + t * 0.15;
		if (t > maxDist) {
			break;
		}
	}
	return vec4(0.0);
}

/* Neighbour on the side that stays on the same surface (avoids the silhouette). */
vec3 splashNeighbour(vec2 uv, vec2 dir, vec3 wp)
{
	vec3 a = splashWorldPos(uv + dir, splashDepthAt(uv + dir));
	vec3 b = splashWorldPos(uv - dir, splashDepthAt(uv - dir));
	return distance(a, wp) < distance(b, wp) ? a - wp : wp - b;
}

float splashOne(vec3 cell, float surfZ, vec2 uv, float sceneZ)
{
	vec3 h = splashHash(cell);
	float V = sqrt(2.0 * SPLASH_GRAVITY * splashHeight);
	float life = 2.2 * V / SPLASH_GRAVITY;
	float age = fract(splashTime * splashRate + h.x) / splashRate;
	if (age > life) {
		return 0.0;
	}

	vec3 C = vec3((cell.xy + 0.2 + 0.6 * h.yz) * splashCell, surfZ);
	vec3 s0 = splashProject(C);
	if (s0.z <= 0.0) {
		return 0.0;
	}
	/* Only on the real surface: near an edge the center may fall in the air. */
	vec2 cuv = s0.xy;
	if (any(lessThan(cuv, vec2(0.0))) || any(greaterThan(cuv, vec2(1.0)))) {
		return 0.0;
	}
	float cd = splashDepthAt(cuv);
	if (cd >= 0.9999 || distance(splashWorldPos(cuv, cd), C) > 0.02 + 0.004 * s0.z) {
		return 0.0;
	}
	/* Hidden behind something closer. */
	if (sceneZ < s0.z - 0.08) {
		return 0.0;
	}

	/* World axes on screen (pixels per meter); the splash is tiny, so affine is enough. */
	const float e = 0.05;
	vec2 ax = (splashProject(C + vec3(e, 0.0, 0.0)).xy - s0.xy) / e * splashRes;
	vec2 ay = (splashProject(C + vec3(0.0, e, 0.0)).xy - s0.xy) / e * splashRes;
	vec2 az = (splashProject(C + vec3(0.0, 0.0, e)).xy - s0.xy) / e * splashRes;
	vec2 p = (uv - s0.xy) * splashRes;
	float ppm = length(az);
	float u = age / life;
	float a = 0.0;

	/* Crown: thin wall of water that opens and rises right after the impact. */
	if (u < 0.45) {
		float det = ax.x * ay.y - ax.y * ay.x;
		if (abs(det) > 1e-3) {
			mat2 inv = mat2(ay.y, -ax.y, -ay.x, ax.x) / det;
			float k = u / 0.45;
			float rc = splashRadius * (0.15 + 0.55 * k);
			float hc = splashHeight * 0.45 * sin(3.1416 * k);
			float w = max(splashDrop * 0.6, 1.2 / ppm);
			for (int j = 0; j < 4; ++j) {
				float z = hc * float(j) / 3.0;
				vec2 local = inv * (p - az * z);
				float ring = 1.0 - smoothstep(0.0, w, abs(length(local) - rc));
				a = max(a, ring * (0.9 - 0.4 * float(j) / 3.0) * (1.0 - k * 0.5));
			}
		}
	}

	/* Drops thrown up and out, falling back with gravity. */
	for (int n = 0; n < SPLASH_DROPS; ++n) {
		float fn = float(n);
		float r1 = fract(h.x * 37.13 + fn * 0.618);
		float r2 = fract(h.y * 91.71 + fn * 0.371);
		float ang = 6.2832 * (fn / float(SPLASH_DROPS) + 0.12 * r1 + h.z);
		float vs = V * (0.55 + 0.45 * r2);
		float z = vs * age - 0.5 * SPLASH_GRAVITY * age * age;
		if (z < 0.0) {
			continue;
		}
		float rr = splashRadius * (0.3 + 0.9 * u) * (0.7 + 0.6 * r1);
		vec2 sp = ax * cos(ang) * rr + ay * sin(ang) * rr + az * z;
		float rad = max(splashDrop * (1.0 - 0.4 * u) * (0.6 + 0.8 * r2) * ppm, 0.8);
		float d = length(p - sp);
		a = max(a, 1.0 - smoothstep(rad * 0.4, rad + 0.75, d));
	}
	return a;
}

/* Only objects with ripples_effect/splash_effect: the mask holds the marked surface (bit) and
 * its view depth, so a surface counts only where it is the one the scene shows. */
bool rainMaskBit(float flags, float bit)
{
	return mod(floor(flags / bit + 0.001), 2.0) > 0.5;
}

bool rainMarked(vec2 uv, float bit, float viewZ)
{
	vec2 m = texture(ge_RainMask, uv).xy;
	if (!rainMaskBit(m.x, bit)) {
		return false;
	}
	return abs(m.y - viewZ) < 0.02 + 0.01 * viewZ;
}

float puddleWaterAt(vec3 wp, float nz, vec2 uv, float viewZ, vec3 camPos);

/* Returns the splash coverage (0..1) for this pixel. */
float rainSplash(vec2 uv, float size, float rate, float maxDist, float minUp, float time)
{
	splashMinUp = minUp;
	splashRes = vec2(textureSize(bgl_DepthTexture, 0));
	vec2 texel = 1.0 / splashRes;
	splashCell = 0.1 * max(size, 1.0);
	splashRate = rate;
	splashHeight = 0.035 * size;
	splashRadius = 0.03 * size;
	splashDrop = 0.0035 * size;
	splashTime = time;
	/* Pixels per meter at 0.8 m from the camera: the search must cover the tallest splash. */
	float ppm = unfprojmat[1][1] * splashRes.y * 0.5 / 0.8;
	float searchPx = min((splashHeight * 1.1 + splashDrop) * ppm, 72.0);

	float d0 = splashDepthAt(uv);
	float sceneZ = d0 >= 0.9999 ? 1e9 : -splashViewPos(uv, d0).z;
	vec3 camPos = unfinvviewmat[3].xyz;

	float acc = 0.0;
	vec3 lastBase = vec3(1e9);
	for (int k = 0; k < SPLASH_SEARCH_STEPS; ++k) {
		vec2 suv = uv - vec2(0.0, float(k) * searchPx / float(SPLASH_SEARCH_STEPS - 1) * texel.y);
		if (suv.y < 0.0) {
			break;
		}
		/* Cheap reject first: an unmarked spot skips the depth and normal work. */
		if (ge_RainMaskFlags.y > 0.5 && !rainMaskBit(texture(ge_RainMask, suv).x, 2.0)) {
			continue;
		}
		float ds = splashDepthAt(suv);
		if (ds >= 0.9999) {
			continue;
		}
		vec3 wp = splashWorldPos(suv, ds);
		if (distance(wp, camPos) > maxDist) {
			continue;
		}
		if (ge_RainMaskFlags.y > 0.5 && !rainMarked(suv, 2.0, -splashViewPos(suv, ds).z)) {
			continue;
		}
		vec3 n = normalize(cross(splashNeighbour(suv, vec2(texel.x, 0.0), wp), splashNeighbour(suv, vec2(0.0, texel.y), wp)));
		if (dot(n, camPos - wp) < 0.0) {
			n = -n;
		}
		if (n.z < splashMinUp) {
			continue;
		}
		if (splashInPuddles && puddleWaterAt(wp, n.z, suv, -splashViewPos(suv, ds).z, camPos) < 0.5) {
			continue;
		}
		/* The two nearest cells on each axis, so a crown is not cut at a cell border. */
		vec3 b = vec3(floor(wp.xy / splashCell - 0.5), floor(wp.z / 0.25));
		if (all(equal(b, lastBase))) {
			continue;
		}
		lastBase = b;
		for (int i = 0; i < 2; ++i) {
			for (int j = 0; j < 2; ++j) {
				acc = max(acc, splashOne(b + vec3(float(i), float(j), 0.0), wp.z, uv, sceneZ));
			}
		}
	}
	return acc;
}

/* Lightning flash: the whole scene gets brighter and colder, the sky much more, and the
 * sky around the bolt even more. x = flash, y = bolt brightness, zw = bolt on screen (uv). */
/* Puddles: smooth value noise in world XY, so the puddles stay on the ground. */
float puddleNoise(vec2 p)
{
	vec2 i = floor(p);
	vec2 f = fract(p);
	vec2 u = f * f * (3.0 - 2.0 * f);
	float a = rainCellHash(vec3(i, 7.0)).x;
	float b = rainCellHash(vec3(i + vec2(1.0, 0.0), 7.0)).x;
	float c = rainCellHash(vec3(i + vec2(0.0, 1.0), 7.0)).x;
	float d = rainCellHash(vec3(i + vec2(1.0, 1.0), 7.0)).x;
	return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}

/* Large blobs plus finer octaves for irregular borders, about 0..1. */
float puddleField(vec2 p)
{
	return puddleNoise(p) * 0.6 + puddleNoise(p * 2.07 + 17.3) * 0.28 + puddleNoise(p * 4.31 + 3.9) * 0.12;
}

/* Puddle water (0..1) at a surface point, same rules as the puddle pass without the edge
 * antialiasing: used by Splash > Only in Puddles for the spot where the drop lands. */
float puddleWaterAt(vec3 wp, float nz, vec2 uv, float viewZ, vec3 camPos)
{
	if (nz < ge_RainPuddle2.z || distance(wp, camPos) > ge_RainPuddle2.y) {
		return 0.0;
	}
	if (ge_RainMaskFlags.z > 0.5 && !rainMarked(uv, 4.0, viewZ)) {
		return 0.0;
	}
	float threshold = mix(0.82, 0.22, ge_RainPuddle1.y);
	return smoothstep(threshold, threshold + 0.03, puddleField(wp.xy / max(ge_RainPuddle1.z, 0.05)));
}

vec3 rainLightning(vec3 col, vec2 uv, float depth, vec2 res, vec4 lightning)
{
	float sky = step(0.9999, depth);
	float halo = lightning.y * exp(-length((uv - lightning.zw) * vec2(res.x / res.y, 1.0)) * 5.0);
	vec3 tint = vec3(0.75, 0.82, 1.0);
	return col * (1.0 + lightning.x * 1.2) + tint * (lightning.x * (0.04 + 0.3 * sky) + halo * 0.35 * sky);
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
	/* 0 = values never set (old filter data): the ones the shader had fixed. */
	float rippleSize = ge_RainParams5.x > 0.0 ? ge_RainParams5.x : 1.0;
	float rippleRate = ge_RainParams5.y > 0.0 ? ge_RainParams5.y : 0.8;

	/* Puddles stay after the rain stops (Intensity 0); they dry with Amount. */
	if (intensity <= 0.001 && ge_RainLightning.x <= 0.001 && !(ge_RainPuddle1.x > 0.5 && ge_RainPuddle1.y > 0.001)) {
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
			streaks = rainClassicStreaks(texcoord, vec2(textureSize(bgl_RenderedTexture, 0)), density, speed, wind, ge_RainStreakWidth, time);
		}

		finalColor += ge_RainColor * streaks * intensity;
	}

	bool rippleOn = useRipple && rippleIntensity > 0.001;
	bool puddlesOn = ge_RainPuddle1.x > 0.5 && ge_RainPuddle1.y > 0.001;
	/* Only in Puddles: Puddle1.x = 1 + 1 (ripples) + 2 (splash); both can be on together. */
	float puddleOnly = ge_RainPuddle1.x > 0.5 ? floor(ge_RainPuddle1.x - 0.5) : 0.0;
	bool ripplePuddleOnly = mod(puddleOnly, 2.0) > 0.5;
	splashInPuddles = puddleOnly > 1.5;
	if (rippleOn || puddlesOn) {
		/* Surface under the pixel, shared by puddles and ripples. Derivatives stay outside the
		 * per-pixel branches below. */
		float depth = texture(bgl_DepthTexture, texcoord).x;
		bool isBackground = depth >= 0.9999;
		vec3 worldPos = getWorldPositionFromDepth(texcoord, depth);
		vec3 camPos = (unfinvviewmat * vec4(0.0, 0.0, 0.0, 1.0)).xyz;
		vec3 normal = normalize(cross(dFdx(worldPos), dFdy(worldPos)));
		/* Derivative orientation is screen-dependent. Point it at the camera so
		 * undersides remain down-facing and cannot receive puddle ripples. */
		if (dot(normal, camPos - worldPos) < 0.0) {
			normal = -normal;
		}
		float camDist = length(worldPos - camPos);
		float viewZ = -splashViewPos(texcoord, depth).z;
		vec3 V = normalize(camPos - worldPos);

		/* Puddles: wet darker ground with standing water reflecting the sky. Computed before
		 * the ripples, which can be limited to the puddle water. */
		/* Puddle field and its derivative before the per-pixel branch: fwidth inside it is undefined.
		 * puddlesOn is uniform, so the pixels of a quad always run this together. */
		float field = 0.0;
		float aa = 0.008;
		if (puddlesOn) {
			field = puddleField(worldPos.xy / max(ge_RainPuddle1.z, 0.05));
			aa = max(fwidth(field) * 1.5, 0.008);
		}
		float puddleDist = ge_RainPuddle2.y;
		bool puddleHere = puddlesOn && !isBackground && camDist <= puddleDist && normal.z >= ge_RainPuddle2.z &&
		    (ge_RainMaskFlags.z < 0.5 || rainMarked(texcoord, 4.0, viewZ));
		float water = 0.0;
		float wet = 0.0;
		if (puddleHere) {
			/* Amount 0 -> nothing above the threshold, 1 -> almost everything. */
			float threshold = mix(0.82, 0.22, ge_RainPuddle1.y);
			water = smoothstep(threshold, threshold + aa + 0.02, field);
			wet = smoothstep(threshold - 0.14, threshold, field);
			float fade = 1.0 - smoothstep(puddleDist * 0.75, puddleDist, camDist);
			water *= fade;
			wet *= fade;
		}

		/* Ripples: height -> gradient -> perturbed Z-up normal, like a material normal map
		 * projected from above in world XY (no mesh UV needed). Blender/Range uses Z as the
		 * world-up axis. */
		bool rippleHere = false;
		float puddleWater = 0.0;
		vec3 N = vec3(0.0, 0.0, 1.0);
		float amount = 0.0;
		if (rippleOn && !isBackground && camDist <= rippleRadius && normal.z >= rippleMinUp &&
		    (!ripplePuddleOnly || water > 0.001) &&
		    (ge_RainMaskFlags.x < 0.5 || rainMarked(texcoord, 1.0, viewZ)))
		{
			rippleHere = true;
			vec2 p = worldPos.xy * 6.0 / rippleSize;
			const float e = 0.02;
			float h = rainRippleHeight(p, time, rippleRate);
			vec2 grad = vec2(rainRippleHeight(p + vec2(e, 0.0), time, rippleRate) - h,
			                 rainRippleHeight(p + vec2(0.0, e), time, rippleRate) - h) / e;
			N = normalize(vec3(-grad * 0.075 * ge_RainRippleNormal, 1.0));
			float fadeOut = 1.0 - smoothstep(rippleRadius * 0.7, rippleRadius, camDist);
			amount = rippleIntensity * 2.5 * fadeOut * (ripplePuddleOnly ? water : 1.0);
		}

		if (puddleHere) {
			float darkness = ge_RainPuddle1.w;
			finalColor *= 1.0 - darkness * (0.3 * wet + 0.55 * water);

			/* The ripples only bend the reflection direction; the fresnel uses the flat water
			 * surface, otherwise every ring edge turns into a full sky-colored line. */
			vec3 Nw = rippleHere ? N : vec3(0.0, 0.0, 1.0);
			puddleWater = water * clamp(ge_RainPuddle2.x, 0.0, 1.0);
			vec3 R = reflect(-V, Nw);
			float skyT = sqrt(clamp(R.z, 0.0, 1.0));
			vec3 sky = mix(ge_RainSkyHorizon, ge_RainSkyZenith, skyT);
			sky = mix(sky, vec3(dot(sky, vec3(0.299, 0.587, 0.114))) * 0.85, darken);
			/* Optional SSR: the visible scene where the ray finds it, the sky elsewhere. */
			if (ge_RainPuddle2.w > 0.5 && water > 0.001) {
				vec4 ssr = puddleSSR(bgl_RenderedTexture, worldPos + vec3(0.0, 0.0, 0.02), R, puddleDist);
				vec3 ssrCol = mix(ssr.rgb, vec3(dot(ssr.rgb, vec3(0.299, 0.587, 0.114))) * 0.85, darken);
				sky = mix(sky, ssrCol, ssr.a);
			}
			float fres = mix(0.2, 1.0, pow(1.0 - max(V.z, 0.0), 4.0));
			finalColor = mix(finalColor, sky, clamp(water * fres * ge_RainPuddle2.x, 0.0, 1.0));

			vec3 H = normalize(normalize(vec3(0.3, 0.2, 1.0)) + V);
			finalColor += vec3(pow(max(dot(Nw, H), 0.0), 200.0)) * water * ge_RainPuddle2.x * 0.6;
		}

		if (rippleHere) {
			/* Refraction: shift what is under the water by the normal slope. */
			vec3 refr = texture(bgl_RenderedTexture, texcoord + N.xy * 0.012 * amount).rgb;
			float refrLuma = dot(refr, vec3(0.299, 0.587, 0.114));
			/* Inside a puddle the reflection already shows the waves: keep only part of the
			 * refraction, which was added on top of the sky and doubled the rings. */
			finalColor += (mix(refr, vec3(refrLuma) * 0.85, darken) - overcast) * (1.0 - 0.75 * puddleWater);

			/* Highlight + fresnel from the bent normal, only where there is a wave. */
			vec3 H = normalize(normalize(vec3(0.3, 0.2, 1.0)) + V);
			float spec = pow(max(dot(N, H), 0.0), 120.0);
			float fres = pow(1.0 - max(dot(N, V), 0.0), 5.0);
			float slope = clamp((1.0 - N.z) * 40.0, 0.0, 1.0);
			finalColor += vec3(spec * 0.8 + fres * 0.25 * (1.0 - puddleWater)) * slope * amount * 0.4;
		}
	}

	if (ge_RainParams4.x > 0.5 && ge_RainParams4.w > 0.001) {
		float splash = rainSplash(texcoord, ge_RainParams4.y, ge_RainParams4.z, ge_RainParams3.w, ge_RainParams5.w, time) * ge_RainParams4.w * 0.85;
		if (splash > 0.0) {
			/* Water: slightly refracts what is behind it and catches the sky light. */
			vec2 texel = 1.0 / vec2(textureSize(bgl_DepthTexture, 0));
			/* Splash Normal: how much the drop bends what is behind it and catches the sky (1 = default). */
			float splashNormal = ge_RainParams5.z;
			vec3 behind = texture(bgl_RenderedTexture, texcoord + vec2(0.0, 2.0 * splashNormal) * texel).rgb;
			vec3 water = behind * (1.0 - 0.45 * min(splashNormal, 2.0)) + vec3(0.78, 0.85, 0.95) * 0.6 * splashNormal;
			finalColor = mix(finalColor, water, clamp(splash, 0.0, 1.0));
		}
	}

	if (ge_RainLightning.x > 0.001) {
		finalColor = rainLightning(finalColor, texcoord, texture(bgl_DepthTexture, texcoord).x, vec2(textureSize(bgl_RenderedTexture, 0)), ge_RainLightning);
	}

	gl_FragColor = vec4(finalColor, direct.a);
}
