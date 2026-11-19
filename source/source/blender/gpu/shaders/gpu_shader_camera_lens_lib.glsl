// Camera lens effects shared by the game (RAS_CameraLens2DFilter.glsl) and the 3D View preview
// (gpu_shader_fx_camera_lens_frag.glsl): fisheye, chromatic aberration, vignette and film grain.
// Math only, no texture reads, so both pipelines keep their own sampling and pass order.

// Fisheye (barrel, > 0) / pincushion (< 0) distortion of the screen uv.
vec2 camera_lens_fisheye(vec2 uv, float aspect, float fisheye)
{
	if (fisheye == 0.0) {
		return uv;
	}
	vec2 v = uv - 0.5;
	vec2 va = v * vec2(aspect, 1.0);
	float r2 = dot(va, va);
	return 0.5 + v * (1.0 - fisheye * 0.5 + fisheye * r2);
}

// Offset of the red channel (blue gets the opposite) for chromatic aberration; v = uv - 0.5.
vec2 camera_lens_chroma_shift(vec2 v, float chroma)
{
	return v * length(v) * chroma * 0.02;
}

// Darkened corners; v = uv - 0.5.
vec3 camera_lens_vignette(vec3 color, vec2 v, float strength, float radius)
{
	if (strength <= 0.0) {
		return color;
	}
	// 0 at the center, 1 at the corners.
	float d = length(v * 2.0) * 0.7071;
	float shade = smoothstep(radius, radius - 0.5, d);
	return color * mix(1.0, shade, strength);
}

// Film grain, stronger on the mid tones.
vec3 camera_lens_grain(vec3 color, vec2 uv, float strength, float seed)
{
	if (strength <= 0.0) {
		return color;
	}
	vec2 s = uv + vec2(seed * 0.05, seed * 0.03);
	float n = fract(sin(dot(s, vec2(12.9898, 78.233))) * 43758.5453) - 0.5;
	float luma = dot(color, vec3(0.299, 0.587, 0.114));
	float lumaMask = 1.0 - pow(abs(luma - 0.5) * 2.0, 2.0);
	return color + n * strength * (0.5 + 0.5 * lumaMask);
}

// Outside the distorted frame (fisheye) the image is black.
bool camera_lens_outside(vec2 uv)
{
	return uv.x < 0.0 || uv.x > 1.0 || uv.y < 0.0 || uv.y > 1.0;
}
