
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

/* Splash: drops bouncing up where the rain hits upward-facing surfaces, edges included.
 * For each pixel, look a few pixels below for a surface cell (the drops rise above it),
 * then draw a crown + drops in a parabola for the 2x2 nearest cells of a world-space grid. */
#define SPLASH_SEARCH_STEPS 10
#define SPLASH_DROPS 8
#define SPLASH_MIN_UP 0.7
#define SPLASH_GRAVITY 9.8

float splashCell;
float splashRate;
float splashHeight;
float splashRadius;
float splashDrop;
float splashTime;
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

/* Returns the splash coverage (0..1) for this pixel. */
float rainSplash(vec2 uv, float size, float rate, float maxDist, float time)
{
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
		float ds = splashDepthAt(suv);
		if (ds >= 0.9999) {
			continue;
		}
		vec3 wp = splashWorldPos(suv, ds);
		if (distance(wp, camPos) > maxDist) {
			continue;
		}
		vec3 n = normalize(cross(splashNeighbour(suv, vec2(texel.x, 0.0), wp), splashNeighbour(suv, vec2(0.0, texel.y), wp)));
		if (dot(n, camPos - wp) < 0.0) {
			n = -n;
		}
		if (n.z < SPLASH_MIN_UP) {
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

	if (intensity <= 0.001 && ge_RainLightning.x <= 0.001) {
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

	if (ge_RainParams4.x > 0.5 && ge_RainParams4.w > 0.001) {
		float splash = rainSplash(texcoord, ge_RainParams4.y, ge_RainParams4.z, ge_RainParams3.w, time) * ge_RainParams4.w * 0.85;
		if (splash > 0.0) {
			/* Water: slightly refracts what is behind it and catches the sky light. */
			vec2 texel = 1.0 / vec2(textureSize(bgl_DepthTexture, 0));
			vec3 behind = texture(bgl_RenderedTexture, texcoord + vec2(0.0, 2.0) * texel).rgb;
			vec3 water = behind * 0.55 + vec3(0.78, 0.85, 0.95) * 0.6;
			finalColor = mix(finalColor, water, clamp(splash, 0.0, 1.0));
		}
	}

	if (ge_RainLightning.x > 0.001) {
		finalColor = rainLightning(finalColor, texcoord, texture(bgl_DepthTexture, texcoord).x, vec2(textureSize(bgl_RenderedTexture, 0)), ge_RainLightning);
	}

	gl_FragColor = vec4(finalColor, direct.a);
}
