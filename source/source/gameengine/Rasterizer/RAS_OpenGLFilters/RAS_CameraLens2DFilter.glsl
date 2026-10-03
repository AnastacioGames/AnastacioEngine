#ifdef USE_CORE_PROFILE
in vec2 texCoordVarying;

out vec4 fragColor;
  #define gl_FragColor fragColor
#endif

// Camera FX, pass B: speed blur (radial, centered on the focus), directional blur (camera turn),
// chromatic aberration and vignette / fisheye, in a single pass. Values from KX_Camera::UpdateGameFX.
uniform sampler2D bgl_RenderedTexture;
uniform sampler2D bgl_DepthTexture;
uniform float bgl_RenderedTextureWidth;
uniform float bgl_RenderedTextureHeight;

// [0] focus distance, focus range, near, far
// [1] max blur (px), rings, cat eye strength, perspective
// [2] speed blur, focus x, focus y (bottom-up), protect
// [3] turn x, turn y (screen fraction), unused, unused
// [4] chromatic, vignette, vignette radius, fisheye
// [5] blades, grain strength, grain seed, unused
uniform vec4 ge_CameraFX[6];

float linearDepth(vec2 uv)
{
	float d = texture(bgl_DepthTexture, uv).r;
	float n = ge_CameraFX[0].z;
	float f = ge_CameraFX[0].w;
	if (ge_CameraFX[1].w > 0.5) {
		return n * f / (f - d * (f - n));
	}
	return n + d * (f - n);
}

vec3 fetchColor(vec2 uv, vec2 chromaShift)
{
	if (ge_CameraFX[4].x <= 0.0) {
		return texture(bgl_RenderedTexture, uv).rgb;
	}
	return vec3(texture(bgl_RenderedTexture, uv + chromaShift).r,
	            texture(bgl_RenderedTexture, uv).g,
	            texture(bgl_RenderedTexture, uv - chromaShift).b);
}

void main()
{
#ifdef USE_CORE_PROFILE
	vec2 uv = texCoordVarying;
#else
	vec2 uv = gl_TexCoord[0].st;
#endif
	float aspect = bgl_RenderedTextureWidth / bgl_RenderedTextureHeight;

	// Fisheye (barrel) / pincushion distortion.
	float fisheye = ge_CameraFX[4].w;
	vec2 v = uv - 0.5;
	if (fisheye != 0.0) {
		vec2 va = v * vec2(aspect, 1.0);
		float r2 = dot(va, va);
		uv = 0.5 + v * (1.0 - fisheye * 0.5 + fisheye * r2);
		v = uv - 0.5;
	}

	float chroma = ge_CameraFX[4].x;
	vec2 chromaShift = v * length(v) * chroma * 0.02;

	float speed = ge_CameraFX[2].x;
	vec2 turn = ge_CameraFX[3].xy;
	bool blur = speed > 0.0 || dot(turn, turn) > 1e-8;

	// Keep the focus band sharp so the target (car) is not smeared with the scenery.
	float blurMask = 1.0;
	if (blur && ge_CameraFX[2].w > 0.5) {
		float z = linearDepth(uv);
		float halfRange = max(ge_CameraFX[0].y * 0.5, 0.25);
		blurMask = smoothstep(halfRange, halfRange * 2.0 + 0.5, abs(z - ge_CameraFX[0].x));
	}

	vec3 color;
	if (blur && blurMask > 0.0) {
		vec2 focus = ge_CameraFX[2].yz;
		// Radial streaks grow away from the focus point.
		vec2 radial = (uv - focus) * speed * 0.12;
		vec2 dir = turn;
		const int SAMPLES = 12;
		vec3 sum = vec3(0.0);
		float weight = 0.0;
		for (int i = 0; i < SAMPLES; ++i) {
			float t = float(i) / float(SAMPLES - 1);
			vec2 offset = (-radial * t + dir * (t - 0.5)) * blurMask;
			float w = 1.0 - t * 0.5;
			sum += fetchColor(uv + offset, chromaShift) * w;
			weight += w;
		}
		color = sum / weight;
	}
	else {
		color = fetchColor(uv, chromaShift);
	}

	// Vignette.
	float vignette = ge_CameraFX[4].y;
	if (vignette > 0.0) {
		float radius = ge_CameraFX[4].z;
		// 0 at the center, 1 at the corners.
		float d = length(v * 2.0) * 0.7071;
		float shade = smoothstep(radius, radius - 0.5, d);
		color *= mix(1.0, shade, vignette);
	}

	// Film grain, stronger on the mid tones.
	float grain = ge_CameraFX[5].y;
	if (grain > 0.0) {
		vec2 seed = uv + vec2(ge_CameraFX[5].z * 0.05, ge_CameraFX[5].z * 0.03);
		float n = fract(sin(dot(seed, vec2(12.9898, 78.233))) * 43758.5453) - 0.5;
		float luma = dot(color, vec3(0.299, 0.587, 0.114));
		float lumaMask = 1.0 - pow(abs(luma - 0.5) * 2.0, 2.0);
		color += n * grain * (0.5 + 0.5 * lumaMask);
	}

	// Outside the distorted frame.
	if (fisheye != 0.0 && (uv.x < 0.0 || uv.x > 1.0 || uv.y < 0.0 || uv.y > 1.0)) {
		color = vec3(0.0);
	}

	gl_FragColor = vec4(color, 1.0);
}
