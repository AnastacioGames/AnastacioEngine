
in vec4 uvcoord; // coordinates [0.0, 1.0]

uniform sampler2D colorbuffer; // color buffer
uniform sampler2D depthbuffer; // depth buffer

uniform vec4 rain_params1; // intensity, speed, wind, darken
uniform vec4 rain_params2; // ripple intensity, time, use droplets, use ripple
uniform vec4 rain_params3; // density, ripple radius, minimum upward normal, unused
uniform vec3 rain_color;
uniform float rain_style; // 0 = Classic (screen-space streaks), 1 = Volumetric (world-space streaks)

/* Streaks: screen-space value-noise layers, same convention as RAS_Rain2DFilter.glsl. */
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

	if (intensity <= 0.001) {
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
			streaks = rainLayer(texcoord, 15.0 * density, speed * 1.3, 6.0, wind, time) * 0.75;

			streaks += rainLayer(texcoord + vec2(3.7, 1.3), 55.0 * density, speed * 0.6, 12.0, wind * 0.7, time) * 0.50;
			streaks += rainLayer(texcoord + vec2(9.1, 5.2), 80.0 * density, speed * 0.5, 14.0, wind * 0.7, time) * 0.35;
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
				float rippleNoise = rainRipples3D(worldPos * 6.0, time);
				finalColor += vec3(rippleNoise * rippleIntensity * 0.15);
			}
		}
	}

	gl_FragColor = vec4(finalColor, direct.a);
}
