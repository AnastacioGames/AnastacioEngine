
#ifdef USE_CORE_PROFILE
in vec2 texCoordVarying;

out vec4 fragColor;
  #define gl_FragColor fragColor
#endif

uniform sampler2D bgl_RenderedTexture;
uniform sampler2D bgl_DepthTexture;

uniform vec2 ge_LightScatterSunPos;
uniform vec4 ge_LightScatterParams; // step_max, step_size, threshold, intensity

vec3 saturation(vec3 col) {
	const vec3 W = vec3(0.2125, 0.7154, 0.0721);

	vec3 intensity = vec3(dot(col, W));

	return mix(intensity, col, 0.5);
}

vec2 uvcoord;

void main() {
#ifdef USE_CORE_PROFILE
	uvcoord = texCoordVarying;
#else
	uvcoord = gl_TexCoord[0].xy;
#endif

	vec2 delta = (uvcoord - ge_LightScatterSunPos) * ge_LightScatterParams.y;

	/* Each sample is masked by the depth at its own position (sky = 1 lets light through,
	 * geometry blocks it), so shafts appear between occluders, not only on sky pixels.
	 * The decay is per ray fraction and the sum is normalized, so the brightness doesn't
	 * depend on the step count (scaled to match the old look at the default 32 steps). */
	const float DECAY_TOTAL = 0.194; // 0.95^32: old falloff along the full ray at 32 steps
	const float REFERENCE_SUM = 15.3; // sum of 0.95^i, i = 1..32
	int steps = max(1, int(ge_LightScatterParams.x));
	float invSteps = 1.0 / float(steps);

	vec3 result = vec3(0.0);
	float weightSum = 0.0;

	for (int i = 0; i < steps; i++) {
		float t = float(i) * invSteps;
		vec2 offset = uvcoord - delta * t;

		float sky = step(1.0, texture(bgl_DepthTexture, offset).x);
		vec3 color = texture(bgl_RenderedTexture, offset).rgb - ge_LightScatterParams.z;

		float w = pow(DECAY_TOTAL, (float(i) + 1.0) * invSteps);
		weightSum += w;
		result += max(vec3(0.0), color * sky) * w;
	}
	result *= REFERENCE_SUM / max(weightSum, 1e-4);

	// Sun distance from the screen center in aspect corrected units (y = 1).
	vec2 size = vec2(textureSize(bgl_RenderedTexture, 0));
	vec2 sunFromCenter = (ge_LightScatterSunPos - vec2(0.5)) * vec2(size.x / max(size.y, 1.0), 1.0);
	float ocluder = max(0.0, 1.0 - length(sunFromCenter));

	gl_FragColor = vec4(saturation(result) * ocluder * ge_LightScatterParams.w, 1.0);
}
