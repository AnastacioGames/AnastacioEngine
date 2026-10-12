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
 *  9 wind offset xy (world units), smoke time, -
 *  10 shape of volumes 0-3 (0 box, 1 sphere)
 *  11 edge of volumes 0-3
 *  12 + 4i lamp i: position xyz, falloff distance
 *  13 + 4i color * energy rgb, shadow slot (-1 none, 0/1 -> vfog_shadow0/1)
 *  14 + 4i spot direction xyz (where it points), cos of half cone (-2 = Point)
 *  15 + 4i cos where the spot edge blend ends, shadow bias, -, -
 *  44 + i volume i color rgb, has color (0 = fog color)
 *  48 + i volume i smoke rise speed (m/s; 0 = normal volume)
 * vfog_mats: 0-3 world -> volume local space (unit box/sphere), 4-5 world -> Spot shadow map,
 * 6 world -> Sun shadow map. */

#define VFOG_MAX_LIGHTS 8
#define VFOG_VOLUME_COLOR (12 + 4 * VFOG_MAX_LIGHTS)
#define VFOG_VOLUME_SMOKE (VFOG_VOLUME_COLOR + 4)

uniform vec4 vfog_data[VFOG_VOLUME_SMOKE + 4];
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
	if (inside <= 0.0) {
		return 0.0;
	}
	/* A smoke volume is a local plume: its noise rises in its own Z axis and fades out at the top. */
	if (smoke > 0.001) {
		vec3 q = l * max(vfog_data[1].x, 0.0001) * 2.5;
		q.z -= smoke * vfog_data[9].z;
		inside -= edge * 0.7 * vfogNoise(q);
		return clamp(inside / edge, 0.0, 1.0) *
		       (0.45 + 0.55 * vfogNoise(q * 2.03 + 17.0)) *
		       (1.0 - smoothstep(-0.25, 1.0, l.z)) * vfog_data[7][i];
	}
	if (inside < edge && edge > 0.01) {
		vec3 q = (p - vec3(vfog_data[9].xy, 0.0)) * max(vfog_data[1].x, 0.0001) * 2.5 + vfog_data[1].z * 0.5;
		inside -= edge * 0.7 * vfogNoise(q);
	}
	return clamp(inside / edge, 0.0, 1.0) * vfog_data[7][i];
}

float vfogVolumeFactor(vec3 p)
{
	float f = 0.0;
	int count = int(vfog_data[6].y);
	for (int i = 0; i < 4; i++) {
		if (i >= count) {
			break;
		}
		f = max(f, vfogVolume(i, p));
	}
	return f;
}

/* Extinction coefficient at p (before the noise) and the fog color there: the height fog and the
 * volumes, each volume with its own tint, mixed by how much each contributes. */
float vfogDensityColor(vec3 p, out vec3 color)
{
	float d = 0.0;
	color = vfog_data[2].rgb;
	if (vfog_data[6].w < 0.5) {
		d = vfog_data[0].x * exp(-max(p.z - vfog_data[0].y, 0.0) / vfog_data[0].z);
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
			float v = vfogVolume(i, p) * vfog_data[0].x;
			if (v > 0.0) {
				vec4 tint = vfog_data[VFOG_VOLUME_COLOR + i];
				sum += ((tint.w > 0.5) ? tint.rgb : vfog_data[2].rgb) * v;
				weight += v;
				f = max(f, v);
			}
		}
		/* Overlapping volumes: the densest sets the density (as before), the color is their mix. */
		if (weight > 1e-6) {
			color = sum / weight;
		}
		d += f;
	}
	return d;
}

float vfogDensityBase(vec3 p)
{
	vec3 color;
	return vfogDensityColor(p, color);
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
		/* Above base + 6 falloffs the fog is under 0.25% of the base density. */
		float top = vfog_data[0].y + vfog_data[0].z * 6.0;
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
vec3 vfogApply(vec3 color, vec3 ro, vec3 rd, float dist, vec2 fragCoord, float frame)
{
	dist = min(dist, vfog_data[0].w);
	vec2 seg = vfogInterval(ro, rd, dist);
	if (seg.x >= seg.y || vfog_data[0].x <= 0.0) {
		return color;
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
		if (vfog_data[6].w < 0.5) {
			float f = vfog_data[0].z;
			float za = max(pa.z - vfog_data[0].y, 0.0);
			float dz = rd.z * len;
			float e = (abs(dz) > 1e-3) ? f * (1.0 - exp(-dz / f)) / dz : 1.0;
			tau = vfog_data[0].x * exp(-za / f) * len * clamp(e, 0.0, 50.0);
		}
		if (vfog_data[6].y > 0.5) {
			tau += vfog_data[0].x * vfogVolumeFactor(ro + rd * (seg.x + len * 0.5)) * len;
		}
		tau *= vfogPatches(ro + rd * (seg.x + min(len, 30.0) * 0.5));
		float T = exp(-tau);
		if (vfog_data[6].y > 0.5) {
			vfogDensityColor(ro + rd * (seg.x + len * 0.5), fogColor);
		}
		vec3 inscatter = (sunLight + ambient) * fogColor * (1.0 - T);
		if (lampCount > 0) {
			float sigma = tau / max(len, 1e-3);
			for (int i = 0; i < VFOG_MAX_LIGHTS; i++) {
				if (i >= lampCount) {
					break;
				}
				inscatter += vfogLampAnalytic(i, ro, rd, seg.x, seg.y, sigma) * fogColor * lampIntensity *
				             (1.0 / 12.566371) * mix(1.0, T, 0.5);
			}
		}
		return color * T + inscatter;
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
	for (int s = 0; s < 24; s++) {
		if (s >= steps) {
			break;
		}
		vec3 p = ro + rd * t;
		vec3 col;
		float sigma = vfogDensityColor(p, col);
		if (sigma > 1e-5) {
			sigma *= vfogPatches(p);
			float stepT = exp(-sigma * ds);
			L += T * (sunLight * vfogSunShadow(p) + ambient) * col * (1.0 - stepT);
			T *= stepT;
		}
		Tsteps[s + 1] = T;
		t += ds;
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
				float sigma = vfogDensityColor(p, col);
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
	return color * T + L;
}
