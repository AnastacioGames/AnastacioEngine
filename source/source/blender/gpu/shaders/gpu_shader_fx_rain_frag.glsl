
in vec4 uvcoord; // coordinates [0.0, 1.0]

uniform sampler2D colorbuffer; // color buffer
uniform sampler2D depthbuffer; // depth buffer

uniform vec4 rain_params1; // intensity, speed, wind, darken
uniform vec4 rain_params2; // ripple intensity, time, use droplets, use ripple
uniform vec4 rain_params3; // density, ripple radius, minimum upward normal, splash distance
uniform vec4 rain_params4; // use splash, splash size, splash rate, splash intensity
uniform vec4 rain_lightning; // flash, bolt, bolt screen position
uniform float rain_streak_width; // Classic streak width, 1 = 2 px at 1080p
uniform float rain_ripple_normal; // ripple normal strength, 1 = default
uniform vec3 rain_color;
uniform float rain_style; // 0 = Classic (screen-space streaks), 1 = Volumetric (world-space streaks)

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

/* Puddle ripples: world-space cellular rings, same convention as RAS_Rain2DFilter.glsl,
 * reconstructed here with the fixed-function gl_*MatrixInverse builtins instead of the
 * game engine's own view/proj uniforms, since this compositor is compat-profile. */
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
float rainRippleHeight(vec2 p, float time)
{
	vec2 i = floor(p);
	vec2 f = fract(p);
	float h = 0.0;

	for (int y = -1; y <= 1; y++) {
		for (int x = -1; x <= 1; x++) {
			vec2 n = vec2(float(x), float(y));
			vec3 r = rainCellHash(vec3(i + n, 0.0));
			float dist = length(n - f + r.xy);
			float t = fract(time * 0.8 + r.z);
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

	vec4 viewSpacePosition = gl_ProjectionMatrixInverse * ndcPosition;
	viewSpacePosition /= viewSpacePosition.w;

	vec4 worldSpacePosition = gl_ModelViewMatrixInverse * viewSpacePosition;

	return worldSpacePosition.xyz;
}

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

/* The splash below is shared with RAS_Rain2DFilter.glsl, which names the matrices and
 * textures after the game engine; this compositor is compat-profile. */
#define unfprojmat gl_ProjectionMatrix
#define unfviewmat gl_ModelViewMatrix
#define unfinvprojmat gl_ProjectionMatrixInverse
#define unfinvviewmat gl_ModelViewMatrixInverse
#define bgl_DepthTexture depthbuffer

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
	vec2 texcoord = uvcoord.xy;
	vec4 direct = texture(colorbuffer, texcoord);

	float intensity = rain_params1.x;
	float speed = rain_params1.y;
	float wind = rain_params1.z;
	float darken = rain_params1.w;
	float rippleIntensity = rain_params2.x;
	float time = rain_params2.y;
	bool useDroplets = rain_params2.z > 0.5;
	bool useRipple = rain_params2.w > 0.5;
	float density = max(rain_params3.x, 0.25);
	float rippleRadius = rain_params3.y;
	float rippleMinUp = rain_params3.z;

	if (intensity <= 0.001 && rain_lightning.x <= 0.001) {
		gl_FragColor = direct;
		return;
	}

	float luma = dot(direct.rgb, vec3(0.299, 0.587, 0.114));
	vec3 overcast = mix(direct.rgb, vec3(luma) * 0.85, darken);

	vec3 finalColor = overcast;

	if (useDroplets) {
		float streaks;

		if (rain_style > 0.5) {
			float depth = texture(depthbuffer, texcoord).x;
			vec3 camPos = (gl_ModelViewMatrixInverse * vec4(0.0, 0.0, 0.0, 1.0)).xyz;
			vec3 worldPos = getWorldPositionFromDepth(texcoord, depth);
			vec3 viewDir = normalize(worldPos - camPos);
			float sceneDepth = length(worldPos - camPos);

			streaks = rainVolumetricStreaks(camPos, viewDir, sceneDepth, time * speed);
		}
		else {
			streaks = rainClassicStreaks(texcoord, vec2(textureSize(colorbuffer, 0)), density, speed, wind, rain_streak_width, time);
		}

		finalColor += rain_color * streaks * intensity;
	}

	if (useRipple && rippleIntensity > 0.001) {
		float depth = texture(depthbuffer, texcoord).x;
		float isBackground = step(0.9999, depth);

		if (isBackground < 0.5) {
			vec3 worldPos = getWorldPositionFromDepth(texcoord, depth);
			vec3 camPos = (gl_ModelViewMatrixInverse * vec4(0.0, 0.0, 0.0, 1.0)).xyz;
			vec3 normal = normalize(cross(dFdx(worldPos), dFdy(worldPos)));
			if (dot(normal, camPos - worldPos) < 0.0) {
				normal = -normal;
			}
			if (length(worldPos - camPos) <= rippleRadius && normal.z >= rippleMinUp) {
				/* Height -> gradient -> perturbed Z-up normal, like a material normal map
				 * projected from above in world XY (no mesh UV needed). */
				vec2 p = worldPos.xy * 6.0;
				const float e = 0.02;
				float h = rainRippleHeight(p, time);
				vec2 grad = vec2(rainRippleHeight(p + vec2(e, 0.0), time) - h,
				                 rainRippleHeight(p + vec2(0.0, e), time) - h) / e;
				vec3 N = normalize(vec3(-grad * 0.075 * rain_ripple_normal, 1.0));
				float fadeOut = 1.0 - smoothstep(rippleRadius * 0.7, rippleRadius, length(worldPos - camPos));
				float amount = rippleIntensity * 2.5 * fadeOut;

				/* Refraction: shift what is under the water by the normal slope. */
				vec3 refr = texture(colorbuffer, texcoord + N.xy * 0.012 * amount).rgb;
				float refrLuma = dot(refr, vec3(0.299, 0.587, 0.114));
				finalColor += mix(refr, vec3(refrLuma) * 0.85, darken) - overcast;

				/* Highlight + fresnel from the bent normal, only where there is a wave. */
				vec3 V = normalize(camPos - worldPos);
				vec3 H = normalize(normalize(vec3(0.3, 0.2, 1.0)) + V);
				float spec = pow(max(dot(N, H), 0.0), 120.0);
				float fres = pow(1.0 - max(dot(N, V), 0.0), 5.0);
				float slope = clamp((1.0 - N.z) * 40.0, 0.0, 1.0);
				finalColor += vec3(spec * 0.8 + fres * 0.25) * slope * amount * 0.4;
			}
		}
	}

	if (rain_params4.x > 0.5 && rain_params4.w > 0.001) {
		float splash = rainSplash(texcoord, rain_params4.y, rain_params4.z, rain_params3.w, time) * rain_params4.w * 0.85;
		if (splash > 0.0) {
			vec2 texel = 1.0 / vec2(textureSize(depthbuffer, 0));
			vec3 behind = texture(colorbuffer, texcoord + vec2(0.0, 2.0) * texel).rgb;
			vec3 water = behind * 0.55 + vec3(0.78, 0.85, 0.95) * 0.6;
			finalColor = mix(finalColor, water, clamp(splash, 0.0, 1.0));
		}
	}

	if (rain_lightning.x > 0.001) {
		finalColor = rainLightning(finalColor, texcoord, texture(depthbuffer, texcoord).x, vec2(textureSize(colorbuffer, 0)), rain_lightning);
	}

	gl_FragColor = vec4(finalColor, direct.a);
}
