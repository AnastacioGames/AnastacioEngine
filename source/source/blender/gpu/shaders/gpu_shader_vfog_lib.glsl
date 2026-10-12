/* Volumetric Fog, shared by the game filter (RAS_VolumetricFog2DFilter.glsl) and the 3D View
 * pass (gpu_shader_fx_vfog_frag.glsl): both prepend their own inputs and call vfogApply().
 *
 * vfog_data layout (vec4):
 *  0 density, base height, height falloff, max distance
 *  1 noise scale, noise amount, drift offset (time * speed), anisotropy
 *  2 fog color rgb, quality (0 Low analytic, 1 Medium, 2 High)
 *  3 sun direction (toward the sun) xyz, has sun
 *  4 sun color * intensity rgb, -
 *  5 ambient color rgb, -
 *  6 lamp count, volume count, lamp intensity, only inside volumes
 *  7 density of volumes 0-3
 *  8 volume edge, shaft intensity, sun shadow bias, has sun shadow (vfog_shadow2)
 *  9 wind offset xy (world units), smoke time, pusher count
 *  10 shape of volumes 0-3 (0 box, 1 sphere)
 *  11 edge of volumes 0-3
 *  12 + 4i lamp i: position xyz, falloff distance
 *  13 + 4i color * energy rgb, shadow slot (-1 none, 0/1 -> vfog_shadow0/1)
 *  14 + 4i spot direction xyz (where it points), cos of half cone (-2 = Point)
 *  15 + 4i cos where the spot edge blend ends, shadow bias, -, -
 *  44 + i volume i color rgb, has color (0 = fog color)
 *  48 + i volume i: smoke rise speed x (m/s; 0 = normal volume), fire temperature y (0..1)
 *  52 + i pusher i (fog_push): position xyz, radius
 * vfog_mats: 0-3 world -> volume local space (unit box/sphere), 4-5 world -> Spot shadow map,
 * 6 world -> Sun shadow map. */

#define VFOG_MAX_LIGHTS 8
#define VFOG_VOLUME_COLOR (12 + 4 * VFOG_MAX_LIGHTS)
#define VFOG_VOLUME_SMOKE (VFOG_VOLUME_COLOR + 4)
#define VFOG_PUSHER (VFOG_VOLUME_SMOKE + 4)

uniform vec4 vfog_data[VFOG_PUSHER + 4];
uniform mat4 vfog_mats[7];
uniform sampler2DShadow vfog_shadow0;
uniform sampler2DShadow vfog_shadow1;
uniform sampler2DShadow vfog_shadow2;

float vfogHash(vec3 p)
{
	p = fract(p * 0.3183099 + 0.1);
	p *= 17.0;
	return fract(p.x * p.y * p.z * (p.x + p.y + p.z));
}

float vfogNoise(vec3 p)
{
	vec3 i = floor(p);
	vec3 f = fract(p);
	vec3 u = f * f * (3.0 - 2.0 * f);
	return mix(mix(mix(vfogHash(i), vfogHash(i + vec3(1.0, 0.0, 0.0)), u.x),
	               mix(vfogHash(i + vec3(0.0, 1.0, 0.0)), vfogHash(i + vec3(1.0, 1.0, 0.0)), u.x), u.y),
	           mix(mix(vfogHash(i + vec3(0.0, 0.0, 1.0)), vfogHash(i + vec3(1.0, 0.0, 1.0)), u.x),
	               mix(vfogHash(i + vec3(0.0, 1.0, 1.0)), vfogHash(i + vec3(1.0, 1.0, 1.0)), u.x), u.y),
	           u.z);
}

/* Patchy multiplier around 1: 1 - amount .. 1 + amount. */
float vfogPatches(vec3 p)
{
	float amount = vfog_data[1].y;
	if (amount <= 0.001) {
		return 1.0;
	}
	vec3 q = (p - vec3(vfog_data[9].xy, 0.0)) * vfog_data[1].x +
	         vec3(vfog_data[1].z, vfog_data[1].z * 0.6, vfog_data[1].z * 0.15);
	float n = vfogNoise(q) * 0.65 + vfogNoise(q * 2.03 + 17.0) * 0.35;
	if (vfog_data[2].w > 1.5) {
		n = n * 0.8 + vfogNoise(q * 4.1 + 41.0) * 0.2;
	}
	return max(0.0, 1.0 + (n * 2.0 - 1.0) * 2.0 * amount);
}

/* Fog Volume i at p: 0 outside .. its density inside, the soft edge eroded by noise so it does
 * not look like a box/ball. */
float vfogVolume(int i, vec3 p)
{
	vec3 l = (vfog_mats[i] * vec4(p, 1.0)).xyz;
	float inside = (vfog_data[10][i] > 0.5) ? 1.0 - length(l) : 1.0 - max(max(abs(l.x), abs(l.y)), abs(l.z));
	float edge = max(vfog_data[11][i], 0.001);
	float smoke = vfog_data[VFOG_VOLUME_SMOKE + i].x;
	float fire = vfog_data[VFOG_VOLUME_SMOKE + i].y;
	if (inside <= 0.0) {
		return 0.0;
	}
	/* Smoke and fire are local plumes in their own Z axis (-1 bottom .. 1 top): a column narrow at
	 * the bottom that opens upward and sways, cut into round billows by rising noise (a threshold
	 * on it, as clouds), thinning out at the top. */
	if (smoke > 0.001 || fire > 0.001) {
		float rise = max(smoke, (fire > 0.001) ? 1.5 : 0.0);
		float time = vfog_data[9].z;
		float h = clamp(l.z * 0.5 + 0.5, 0.0, 1.0);
		vec2 sway = vec2(vfogNoise(vec3(l.z * 1.3 - time * 0.35, 3.0, 7.0)),
		                 vfogNoise(vec3(l.z * 1.3 - time * 0.35, 11.0, 5.0))) - 0.5;
		vec2 xy = l.xy - sway * 0.5 * h;
		/* Smoke opens upward; a flame is a tongue that narrows upward. */
		float radius = (smoke > 0.001 && fire <= 0.001) ? mix(0.42, 0.95, sqrt(h)) : mix(0.85, 0.25, h);
		float column = 1.0 - length(xy) / radius;
		vec3 q = vec3(l.xy * 4.0, l.z * 3.0 - rise * time * 0.8);
		float n = vfogNoise(q) * 0.55 + vfogNoise(q * 2.07 + 17.0) * 0.3 + vfogNoise(q * 4.3 + 41.0) * 0.15;
		float billow = column + 0.12 + (n - 0.5) * (0.6 + 0.6 * h);
		float shape = smoothstep(0.0, 0.18, billow) * smoothstep(-1.0, -0.85, l.z) *
		              (1.0 - smoothstep(0.35, 1.0, l.z));
		return min(shape, clamp(inside * 6.0, 0.0, 1.0)) * vfog_data[7][i];
	}
	if (inside < edge && edge > 0.01) {
		vec3 q = (p - vec3(vfog_data[9].xy, 0.0)) * max(vfog_data[1].x, 0.0001) * 2.5 + vfog_data[1].z * 0.5;
		inside -= edge * 0.7 * vfogNoise(q);
	}
	return clamp(inside / edge, 0.0, 1.0) * vfog_data[7][i];
}

bool vfogIsPlume(int i)
{
	return vfog_data[VFOG_VOLUME_SMOKE + i].x > 0.001 || vfog_data[VFOG_VOLUME_SMOKE + i].y > 0.001;
}

/* Medium/High march the smoke/fire plumes on their own (more samples, self shadow); the main
 * march then leaves them out. */
bool vfogSkipPlumes = false;

float vfogVolumeFactor(vec3 p)
{
	float f = 0.0;
	int count = int(vfog_data[6].y);
	for (int i = 0; i < 4; i++) {
		if (i >= count) {
			break;
		}
		float localDensity = (vfog_data[VFOG_VOLUME_SMOKE + i].x > 0.001 ||
		                      vfog_data[VFOG_VOLUME_SMOKE + i].y > 0.001) ? 0.5 : vfog_data[0].x;
		f = max(f, vfogVolume(i, p) * localDensity);
	}
	return f;
}

float vfogPush(vec3 p);

/* Approximation of black-body flame colors, from dark red through orange to yellow-white. */
vec3 vfogFireColor(float temperature)
{
	temperature = clamp(temperature, 0.0, 1.0);
	if (temperature < 0.5) {
		return mix(vec3(0.35, 0.005, 0.0), vec3(1.0, 0.16, 0.005), temperature * 2.0);
	}
	return mix(vec3(1.0, 0.16, 0.005), vec3(1.0, 0.95, 0.62), (temperature - 0.5) * 2.0);
}

/* Fire emission at p from volume i. Its hotter turbulent core is kept below the smoke plume. */
vec3 vfogFireEmission(int i, vec3 p)
{
	float temperature = vfog_data[VFOG_VOLUME_SMOKE + i].y;
	if (temperature <= 0.001) {
		return vec3(0.0);
	}
	vec3 l = (vfog_mats[i] * vec4(p, 1.0)).xyz;
	float rise = max(vfog_data[VFOG_VOLUME_SMOKE + i].x, 1.5);
	vec3 q = l * max(vfog_data[1].x, 0.0001) * 4.0;
	q.z -= rise * vfog_data[9].z;
	float turbulence = vfogNoise(q) * 0.65 + vfogNoise(q * 2.17 + 23.0) * 0.35;
	float lower = 1.0 - smoothstep(-0.55, 0.45, l.z);
	float heat = temperature * lower * (0.3 + 0.7 * turbulence);
	return vfogFireColor(heat) * (2.0 + 8.0 * heat);
}

/* Top of the fog for the ray interval: Layer = base + its waves, else base + 6 falloffs (under
 * 0.25% of the base density). The haze up to the clouds is added in closed form by vfogScatter. */
float vfogTop()
{
	float top = (vfog_data[4].w > 0.5) ? vfog_data[0].y + vfog_data[0].z * 1.5
	                                   : vfog_data[0].y + vfog_data[0].z * 6.0;
	return top;
}

/* Haze between the fog and the clouds: a small fraction of the density, fading out just under
 * the cloud base. */
float vfogHaze(float z)
{
	float clouds = vfog_data[5].w;
	if (clouds <= 0.0) {
		return 0.0;
	}
	/* Thin whatever the fog density: long rays cross hundreds of meters of it. */
	return min(vfog_data[0].x * 0.02, 0.0015) * (1.0 - smoothstep(clouds * 0.6, clouds, z));
}

/* Height fog density at p (no volumes): exponential above the base, or the Layer, dense up to a
 * top that waves with the noise by about one falloff (fills the valleys like a sea of fog). */
float vfogHeightDensity(vec3 p)
{
	float d;
	if (vfog_data[4].w > 0.5) {
		vec2 q = (p.xy - vfog_data[9].xy) * vfog_data[1].x * 0.35 + vfog_data[1].z * 0.3;
		float wave = vfogNoise(vec3(q, 0.0)) * 0.65 + vfogNoise(vec3(q * 2.3, 7.0)) * 0.35;
		float top = vfog_data[0].y + (wave - 0.5) * 2.0 * vfog_data[0].z;
		float soft = 0.25 + vfog_data[0].z * 0.3;
		d = vfog_data[0].x * (1.0 - smoothstep(top - soft, top + soft, p.z));
	}
	else {
		d = vfog_data[0].x * exp(-max(p.z - vfog_data[0].y, 0.0) / vfog_data[0].z);
	}
	return d;
}

/* Extinction coefficient at p (before the noise) and the fog color there: the height fog and the
 * volumes, each volume with its own tint, mixed by how much each contributes. */
float vfogDensityColor(vec3 p, out vec3 color, out vec3 emission)
{
	float d = 0.0;
	color = vfog_data[2].rgb;
	emission = vec3(0.0);
	if (vfog_data[6].w < 0.5) {
		d = vfogHeightDensity(p);
	}
	int count = int(vfog_data[6].y);
	if (count > 0) {
		vec3 sum = color * d;
		float weight = d;
		float f = 0.0;
		for (int i = 0; i < 4; i++) {
			if (i >= count) {
				break;
			}
			if (vfogSkipPlumes && vfogIsPlume(i)) {
				continue;
			}
		float localDensity = (vfog_data[VFOG_VOLUME_SMOKE + i].x > 0.001 ||
		                      vfog_data[VFOG_VOLUME_SMOKE + i].y > 0.001) ? 0.5 : vfog_data[0].x;
		float v = vfogVolume(i, p) * localDensity;
			if (v > 0.0) {
				vec4 tint = vfog_data[VFOG_VOLUME_COLOR + i];
				sum += ((tint.w > 0.5) ? tint.rgb : vfog_data[2].rgb) * v;
				weight += v;
				f = max(f, v);
				emission += vfogFireEmission(i, p);
			}
		}
		/* Overlapping volumes: the densest sets the density (as before), the color is their mix. */
		if (weight > 1e-6) {
			color = sum / weight;
		}
		d += f;
	}
	if (vfog_data[9].w > 0.5 && d > 0.0) {
		float push = vfogPush(p);
		d *= push;
		emission *= push;
	}
	return d;
}

/* Fog left at p by the pushers: 0 at their center .. 1 out of their radius, the rim wobbling with
 * the noise so the hole does not look like a ball. */
float vfogPush(vec3 p)
{
	float k = 1.0;
	int count = int(vfog_data[9].w);
	for (int i = 0; i < 4; i++) {
		if (i >= count) {
			break;
		}
		vec4 push = vfog_data[VFOG_PUSHER + i];
		float x = length(p - push.xyz) / max(push.w, 0.01);
		if (x < 1.0) {
			x += (vfogNoise(p * 1.7 + vfog_data[1].z) - 0.5) * 0.3;
			k *= smoothstep(0.35, 1.0, x);
		}
	}
	return k;
}

/* Fraction of the optical depth over [t0, t1] that the pushers leave (Low, no raymarch): the part
 * of the ray inside each pusher counts about 70% less. */
float vfogPushAnalytic(vec3 ro, vec3 rd, float t0, float t1)
{
	float k = 1.0;
	int count = int(vfog_data[9].w);
	float len = max(t1 - t0, 1e-3);
	for (int i = 0; i < 4; i++) {
		if (i >= count) {
			break;
		}
		vec4 push = vfog_data[VFOG_PUSHER + i];
		float tc = dot(push.xyz - ro, rd);
		vec3 c = ro + rd * tc - push.xyz;
		float h2 = dot(c, c);
		float r2 = push.w * push.w;
		if (h2 < r2) {
			float w = sqrt(r2 - h2);
			float chord = max(0.0, min(t1, tc + w) - max(t0, tc - w));
			k *= 1.0 - 0.7 * min(chord / len, 1.0);
		}
	}
	return k;
}

float vfogDensityBase(vec3 p)
{
	vec3 color;
	vec3 emission;
	return vfogDensityColor(p, color, emission);
}

float vfogPhase(float cosTheta, float g)
{
	float g2 = g * g;
	return (1.0 - g2) / (12.566371 * pow(max(1.0 + g2 - 2.0 * g * cosTheta, 1e-4), 1.5));
}

/* Ray interval [t0, t1] inside the unit box of volume i, empty when t0 >= t1. */
vec2 vfogVolumeInterval(int i, vec3 ro, vec3 rd)
{
	vec3 o = (vfog_mats[i] * vec4(ro, 1.0)).xyz;
	vec3 d = (vfog_mats[i] * vec4(rd, 0.0)).xyz;
	if (vfog_data[10][i] > 0.5) {
		float a = dot(d, d);
		float b = dot(o, d);
		float c = dot(o, o) - 1.0;
		float h = b * b - a * c;
		if (h < 0.0 || a < 1e-8) {
			return vec2(1.0, 0.0);
		}
		h = sqrt(h);
		return vec2((-b - h) / a, (-b + h) / a);
	}
	vec3 inv = 1.0 / (abs(d) + 1e-6) * sign(d + 1e-12);
	vec3 a = (-1.0 - o) * inv;
	vec3 b = (1.0 - o) * inv;
	vec3 lo = min(a, b);
	vec3 hi = max(a, b);
	return vec2(max(max(lo.x, lo.y), lo.z), min(min(hi.x, hi.y), hi.z));
}

/* Part of the ray [0, dist] where there can be fog: below the top of the height fog and
 * inside the volumes. Returns (start, end), start >= end when there is none. */
vec2 vfogInterval(vec3 ro, vec3 rd, float dist)
{
	float t0 = dist;
	float t1 = 0.0;
	if (vfog_data[6].w < 0.5) {
		float top = vfogTop();
		if (ro.z <= top) {
			t0 = 0.0;
			t1 = (rd.z > 1e-4) ? min(dist, (top - ro.z) / rd.z) : dist;
		}
		else if (rd.z < -1e-4) {
			t0 = (top - ro.z) / rd.z;
			t1 = dist;
		}
	}
	int count = int(vfog_data[6].y);
	for (int i = 0; i < 4; i++) {
		if (i >= count) {
			break;
		}
		vec2 v = vfogVolumeInterval(i, ro, rd);
		if (v.x < v.y && v.y > 0.0) {
			t0 = min(t0, max(v.x, 0.0));
			t1 = max(t1, min(v.y, dist));
		}
	}
	return vec2(max(t0, 0.0), min(t1, dist));
}

float vfogSpot(int i, vec3 toPoint)
{
	vec4 spot = vfog_data[14 + 4 * i];
	if (spot.w < -1.5) {
		return 1.0;
	}
	float c = dot(normalize(toPoint), spot.xyz);
	return smoothstep(spot.w, max(vfog_data[15 + 4 * i].x, spot.w + 1e-4), c);
}

/* Lamp light reaching p (no shadow), already with the lamp's color and energy. */
vec3 vfogLamp(int i, vec3 p, out vec3 toPoint)
{
	vec4 pos = vfog_data[12 + 4 * i];
	toPoint = p - pos.xyz;
	float d2 = dot(toPoint, toPoint);
	float r = max(pos.w, 0.01);
	float x = d2 / (r * r);
	float window = clamp(1.0 - x * x, 0.0, 1.0);
	float att = window * window / (1.0 + 16.0 * x);
	return vfog_data[13 + 4 * i].rgb * att * vfogSpot(i, toPoint);
}

float vfogShadow(int i, vec3 p)
{
	float slot = vfog_data[13 + 4 * i].w;
	if (slot < -0.5) {
		return 1.0;
	}
	int m = (slot < 0.5) ? 4 : 5;
	vec4 sc = vfog_mats[m] * vec4(p, 1.0);
	if (sc.w <= 0.0) {
		return 1.0;
	}
	sc.z -= vfog_data[15 + 4 * i].y * sc.w;
	vec3 uvz = sc.xyz / sc.w;
	if (any(lessThan(uvz.xy, vec2(0.0))) || any(greaterThan(uvz.xy, vec2(1.0)))) {
		return 1.0;
	}
	return (slot < 0.5) ? texture(vfog_shadow0, uvz) : texture(vfog_shadow1, uvz);
}

/* Sun light reaching p through the Sun's shadow map (sun shafts), 1 without one. */
float vfogSunShadow(vec3 p)
{
	if (vfog_data[8].w < 0.5) {
		return 1.0;
	}
	vec4 sc = vfog_mats[6] * vec4(p, 1.0);
	vec3 uvz = sc.xyz / sc.w;
	if (any(lessThan(uvz, vec3(0.0))) || any(greaterThan(uvz, vec3(1.0)))) {
		return 1.0;
	}
	uvz.z -= vfog_data[8].z;
	return texture(vfog_shadow2, uvz);
}

/* Narrows [a, b] to the part of the ray inside a Spot's cone (apex at the lamp), so the lamp march
 * spends its samples where the cone is instead of all over the lamp's reach. */
vec2 vfogConeInterval(int i, vec3 ro, vec3 rd, float a, float b)
{
	vec4 spot = vfog_data[14 + 4 * i];
	if (spot.w < -1.5) {
		return vec2(a, b);
	}
	vec3 co = ro - vfog_data[12 + 4 * i].xyz;
	float c2 = spot.w * spot.w;
	float da = dot(rd, spot.xyz);
	float oa = dot(co, spot.xyz);
	float A = da * da - c2;
	float B = 2.0 * (da * oa - c2 * dot(rd, co));
	float C = oa * oa - c2 * dot(co, co);
	float t1 = b;
	float t2 = b;
	float disc = B * B - 4.0 * A * C;
	if (abs(A) > 1e-6 && disc > 0.0) {
		float q = sqrt(disc);
		t1 = (-B - q) / (2.0 * A);
		t2 = (-B + q) / (2.0 * A);
		if (t1 > t2) {
			float tmp = t1;
			t1 = t2;
			t2 = tmp;
		}
	}
	/* The roots split the ray in up to 3 pieces: keep the span of the ones inside the cone. */
	float lo = b;
	float hi = a;
	float cuts[4];
	cuts[0] = a;
	cuts[1] = clamp(t1, a, b);
	cuts[2] = clamp(t2, a, b);
	cuts[3] = b;
	for (int k = 0; k < 3; k++) {
		if (cuts[k + 1] - cuts[k] < 1e-4) {
			continue;
		}
		vec3 m = co + rd * (0.5 * (cuts[k] + cuts[k + 1]));
		float md = dot(m, spot.xyz);
		if (md > 0.0 && md * md >= c2 * dot(m, m)) {
			lo = min(lo, cuts[k]);
			hi = max(hi, cuts[k + 1]);
		}
	}
	return vec2(lo, hi);
}

/* Interleaved gradient noise: per pixel step jitter, different each frame. */
float vfogJitter(vec2 fragCoord, float frame)
{
	vec2 p = fragCoord + vec2(5.588238, 5.588238) * mod(frame, 64.0);
	return fract(52.9829189 * fract(dot(p, vec2(0.06711056, 0.00583715))));
}

/* Analytic single scattering of a point lamp along the ray (inverse square, homogeneous medium
 * at the density of the closest point): integral of a^2 / (a^2 + h^2 + s^2) over the part of the
 * ray inside the lamp's reach. */
vec3 vfogLampAnalytic(int i, vec3 ro, vec3 rd, float t0, float t1, float sigmaAt)
{
	vec4 pos = vfog_data[12 + 4 * i];
	float r = max(pos.w, 0.01);
	float tc = dot(pos.xyz - ro, rd);
	vec3 closest = ro + rd * tc;
	float h2 = dot(closest - pos.xyz, closest - pos.xyz);
	if (h2 >= r * r) {
		return vec3(0.0);
	}
	float w = sqrt(r * r - h2);
	float s0 = max(t0, tc - w) - tc;
	float s1 = min(t1, tc + w) - tc;
	if (s1 <= s0) {
		return vec3(0.0);
	}
	float a2 = r * r / 16.0;
	float H = sqrt(a2 + h2);
	float integral = a2 / H * (atan(s1 / H) - atan(s0 / H));
	vec3 mid = ro + rd * clamp(tc, t0, t1);
	vec3 toPoint = mid - pos.xyz;
	float spot = vfogSpot(i, toPoint);
	return vfog_data[13 + 4 * i].rgb * integral * spot * sigmaAt;
}

/* Applies the fog to a pixel: ro camera, rd normalized view ray, dist distance to the scene
 * (the max distance for the sky). */
vec4 vfogScatter(vec3 ro, vec3 rd, float dist, vec2 fragCoord, float frame);

vec3 vfogApply(vec3 color, vec3 ro, vec3 rd, float dist, vec2 fragCoord, float frame)
{
	vec4 fog = vfogScatter(ro, rd, dist, fragCoord, frame);
	return color * fog.a + fog.rgb;
}

vec4 vfogScatterFog(vec3 ro, vec3 rd, float dist, vec2 fragCoord, float frame);

/* The fog along the ray alone: in-scatter rgb, transmittance a (the scene color is multiplied by
 * a and the in-scatter added; the Half/Quarter resolution game pass stores this). The thin haze
 * up to the clouds is in closed form, in front of the fog (it is far thinner). */
vec4 vfogScatter(vec3 ro, vec3 rd, float dist, vec2 fragCoord, float frame)
{
	vec4 fog = vfogScatterFog(ro, rd, dist, fragCoord, frame);
	float clouds = vfog_data[5].w;
	if (clouds <= 0.0) {
		return fog;
	}
	/* Length of the ray under the cloud base, the haze density at its middle height. */
	float len = min(dist, vfog_data[0].w);
	if (rd.z > 1e-4) {
		len = min(len, max(clouds - ro.z, 0.0) / rd.z);
	}
	else if (ro.z > clouds) {
		len = (rd.z < -1e-4) ? max(len - (ro.z - clouds) / -rd.z, 0.0) : 0.0;
	}
	float tau = vfogHaze(ro.z + rd.z * len * 0.5) * len;
	float T = exp(-tau);
	vec3 light = vfog_data[5].rgb;
	if (vfog_data[3].w > 0.5) {
		light += vfog_data[4].rgb * vfogPhase(dot(rd, vfog_data[3].xyz), vfog_data[1].w) * 12.566371;
	}
	return vec4(light * vfog_data[2].rgb * (1.0 - T) + fog.rgb * T, fog.a * T);
}

vec4 vfogScatterFog(vec3 ro, vec3 rd, float dist, vec2 fragCoord, float frame)
{
	dist = min(dist, vfog_data[0].w);
	vec2 seg = vfogInterval(ro, rd, dist);
	if (seg.x >= seg.y || (vfog_data[0].x <= 0.0 && vfog_data[6].y < 0.5)) {
		return vec4(0.0, 0.0, 0.0, 1.0);
	}
	float quality = vfog_data[2].w;
	vec3 fogColor = vfog_data[2].rgb;
	float g = vfog_data[1].w;
	int lampCount = int(vfog_data[6].x);
	float lampIntensity = vfog_data[6].z;
	vec3 sunLight = vec3(0.0);
	if (vfog_data[3].w > 0.5) {
		sunLight = vfog_data[4].rgb * vfogPhase(dot(rd, vfog_data[3].xyz), g) * 12.566371;
	}
	vec3 ambient = vfog_data[5].rgb;

	if (quality < 0.5) {
		/* Low: no raymarch. Optical depth of the exponential height fog in closed form, plus
		 * the volumes with the density at the middle of their stretch; lamps analytic. */
		float len = seg.y - seg.x;
		vec3 pa = ro + rd * seg.x;
		float tau = 0.0;
		if (vfog_data[6].w < 0.5 && vfog_data[4].w > 0.5) {
			/* Layer: the length of the ray under its (flat) top, plus the haze. */
			float zb = (ro + rd * seg.y).z;
			float lo = min(pa.z, zb);
			float hi = max(pa.z, zb);
			float under = (hi - lo > 1e-3) ? clamp((vfog_data[0].y - lo) / (hi - lo), 0.0, 1.0)
			                               : step(lo, vfog_data[0].y);
			tau = vfog_data[0].x * len * under;
		}
		else if (vfog_data[6].w < 0.5) {
			float f = vfog_data[0].z;
			float za = max(pa.z - vfog_data[0].y, 0.0);
			float dz = rd.z * len;
			float e = (abs(dz) > 1e-3) ? f * (1.0 - exp(-dz / f)) / dz : 1.0;
			tau = vfog_data[0].x * exp(-za / f) * len * clamp(e, 0.0, 50.0);
		}
		if (vfog_data[6].y > 0.5) {
			tau += vfogVolumeFactor(ro + rd * (seg.x + len * 0.5)) * len;
		}
		tau *= vfogPatches(ro + rd * (seg.x + min(len, 30.0) * 0.5));
		if (vfog_data[9].w > 0.5) {
			tau *= vfogPushAnalytic(ro, rd, seg.x, seg.y);
		}
		float T = exp(-tau);
		vec3 emission = vec3(0.0);
		if (vfog_data[6].y > 0.5) {
			vfogDensityColor(ro + rd * (seg.x + len * 0.5), fogColor, emission);
		}
		vec3 inscatter = (sunLight + ambient) * fogColor * (1.0 - T);
		inscatter += emission * (1.0 - T);
		if (lampCount > 0) {
			float sigma = tau / max(len, 1e-3);
			for (int i = 0; i < VFOG_MAX_LIGHTS; i++) {
				if (i >= lampCount) {
					break;
				}
				vec3 mid = ro + rd * (0.5 * (seg.x + seg.y));
				vec3 toPoint = mid - vfog_data[12 + 4 * i].xyz;
				float phase = vfogPhase(dot(rd, normalize(toPoint)), g * 0.5) * 12.566371;
				inscatter += vfogLampAnalytic(i, ro, rd, seg.x, seg.y, sigma) * fogColor * lampIntensity *
				             phase * mix(1.0, T, 0.5);
			}
		}
		return vec4(inscatter, T);
	}

	/* Medium/High: raymarch with per pixel jitter for the sun, sky and transmittance, keeping the
	 * transmittance at every step; then each lamp marches only the part of the ray inside its
	 * reach, so a narrow Spot cone gets all its samples instead of 1-2 of the main march. */
	int steps = (quality > 1.5) ? 24 : 12;
	float ds = (seg.y - seg.x) / float(steps);
	float jitter = vfogJitter(fragCoord, frame);
	float t = seg.x + ds * jitter;
	float T = 1.0;
	vec3 L = vec3(0.0);
	float Tsteps[25];
	Tsteps[0] = 1.0;
	for (int s = 1; s < 25; s++) {
		Tsteps[s] = 0.0;
	}
	vfogSkipPlumes = true;
	for (int s = 0; s < 24; s++) {
		if (s >= steps) {
			break;
		}
		vec3 p = ro + rd * t;
		vec3 col;
		vec3 emission;
		float sigma = vfogDensityColor(p, col, emission);
		if (sigma > 1e-5) {
			sigma *= vfogPatches(p);
			float stepT = exp(-sigma * ds);
			L += T * (sunLight * vfogSunShadow(p) + ambient) * col * (1.0 - stepT);
			L += T * emission * sigma * ds;
			T *= stepT;
		}
		Tsteps[s + 1] = T;
		t += ds;
		if (T < 0.01) {
			break;
		}
	}
	vfogSkipPlumes = false;

	/* Smoke/fire plumes always, and a small local volume that can fall between the 12 Medium
	 * samples (its ray interval shorter than six regular steps), are marched on their own. */
	int volumeCount = int(vfog_data[6].y);
	int plumeSteps = (quality > 1.5) ? 16 : 10;
	for (int i = 0; i < 4; i++) {
		if (i >= volumeCount) {
			break;
		}
		bool plume = vfogIsPlume(i);
		vec2 vseg = vfogVolumeInterval(i, ro, rd);
		float a = max(seg.x, vseg.x);
		float b = min(seg.y, vseg.y);
		if (b <= a || (!plume && (b - a) >= 6.0 * ds)) {
			continue;
		}
		float vk = clamp((a - seg.x) / max(ds, 1e-4), 0.0, float(steps));
		int vk0 = int(floor(vk));
		int vk1 = min(vk0 + 1, steps);
		float Tv = mix(Tsteps[vk0], Tsteps[vk1], fract(vk));
		if (Tv < 0.01) {
			continue;
		}
		int vsteps = plume ? plumeSteps : 6;
		float vds = (b - a) / float(vsteps);
		float vt = a + vds * fract(jitter + 0.381966 * float(i + 1));
		vec4 tint = vfog_data[VFOG_VOLUME_COLOR + i];
		vec3 volColor = (tint.w > 0.5) ? tint.rgb : vfog_data[2].rgb;
		float localDensity = plume ? 0.5 : vfog_data[0].x;
		/* Self shadow of a plume: two taps toward the sun, about a third and the whole of the volume
		 * radius away, so the billows get a lit and a shaded side. */
		vec3 sunDir = vfog_data[3].xyz;
		float radius = 1.0 / max(length((vfog_mats[i] * vec4(sunDir, 0.0)).xyz), 1e-4);
		float Tin = Tv;
		for (int s = 0; s < 16; s++) {
			if (s >= vsteps) {
				break;
			}
			vec3 p = ro + rd * vt;
			float sigma = vfogVolume(i, p) * localDensity;
			if (!plume) {
				sigma *= vfogPatches(p);
			}
			vec3 emission = vfogFireEmission(i, p);
			if (vfog_data[9].w > 0.5) {
				float push = vfogPush(p);
				sigma *= push;
				emission *= push;
			}
			if (sigma > 1e-5) {
				float stepT = exp(-sigma * vds);
				vec3 sun = sunLight * vfogSunShadow(p);
				vec3 amb = ambient;
				if (plume) {
					float occ = vfogVolume(i, p + sunDir * radius * 0.35) * 0.35 +
					            vfogVolume(i, p + sunDir * radius) * 0.65;
					sun *= exp(-occ * localDensity * radius * 1.6);
					/* Thick inner parts see less of the sky too. */
					amb *= mix(1.0, 0.75, clamp(occ, 0.0, 1.0));
					/* A little light of its own so a night plume is not a black hole in the sky. */
					amb += vfog_data[2].rgb * 0.15;
				}
				L += Tv * (sun + amb) * volColor * (1.0 - stepT);
				/* Plume fire: bounded by its own color instead of summing over a dense core. */
				L += Tv * emission * (plume ? (1.0 - stepT) * 0.07 : sigma * vds);
				Tv *= stepT;
			}
			vt += vds;
		}
		/* What the plume hides of the scene behind it. */
		if (plume && Tin > 1e-4) {
			T *= Tv / Tin;
		}
	}

	int lampSteps = (quality > 1.5) ? 16 : 8;
	float shaftIntensity = vfog_data[8].y;
	for (int i = 0; i < VFOG_MAX_LIGHTS; i++) {
		if (i >= lampCount) {
			break;
		}
		vec4 pos = vfog_data[12 + 4 * i];
		float r = max(pos.w, 0.01);
		float tc = dot(pos.xyz - ro, rd);
		vec3 closest = ro + rd * tc;
		float h2 = dot(closest - pos.xyz, closest - pos.xyz);
		if (h2 >= r * r) {
			continue;
		}
		float w = sqrt(r * r - h2);
		float a = max(seg.x, tc - w);
		float b = min(seg.y, tc + w);
		if (b <= a) {
			continue;
		}
		float entryK = clamp((a - seg.x) / max(ds, 1e-4), 0.0, float(steps));
		int entryK0 = int(floor(entryK));
		int entryK1 = min(entryK0 + 1, steps);
		float entryT = mix(Tsteps[entryK0], Tsteps[entryK1], fract(entryK));
		if (entryT < 0.01) {
			continue;
		}
		vec2 cone = vfogConeInterval(i, ro, rd, a, b);
		a = cone.x;
		b = cone.y;
		if (b <= a) {
			continue;
		}
		float lds = (b - a) / float(lampSteps);
		float lt = a + lds * fract(jitter + 0.618034 * float(i + 1));
		float phaseG = g * 0.5;
		float shaft = (vfog_data[13 + 4 * i].w > -0.5) ? shaftIntensity : 1.0;
		vec3 acc = vec3(0.0);
		for (int s = 0; s < 16; s++) {
			if (s >= lampSteps) {
				break;
			}
			vec3 p = ro + rd * lt;
			vec3 toPoint;
			vec3 lamp = vfogLamp(i, p, toPoint);
			if (dot(lamp, lamp) > 1e-8) {
				vec3 col;
				vec3 emission;
				float sigma = vfogDensityColor(p, col, emission);
				if (sigma > 1e-5) {
					sigma *= vfogPatches(p);
					float k = clamp((lt - seg.x) / max(ds, 1e-4), 0.0, float(steps));
					int k0 = int(floor(k));
					int k1 = min(k0 + 1, steps);
					float Tl = mix(Tsteps[k0], Tsteps[k1], fract(k));
					float phase = vfogPhase(dot(rd, normalize(toPoint)), phaseG) * 12.566371;
					acc += Tl * lamp * col * phase * vfogShadow(i, p) * sigma * lds;
				}
			}
			lt += lds;
		}
		L += acc * shaft * lampIntensity;
	}
	return vec4(L, T);
}
