// 3D View preview of the game's camera lens pass (RAS_CameraLens2DFilter.glsl) without the
// speed/motion blurs: fisheye, chromatic aberration, vignette and film grain, same order and
// math (gpu_shader_camera_lens_lib.glsl).
uniform sampler2D colorbuffer;
// x: chromatic, y: vignette, z: vignette radius, w: fisheye
uniform vec4 lens_params;
// x: grain strength, y: grain seed, zw: buffer size in pixels (no textureSize in GLSL 1.20)
uniform vec4 grain_params;
// Camera frame inside the buffer, in uv: x min, y min, width, height. The lens works in the
// frame's own coordinates, as in the game where the frame is the whole screen.
uniform vec4 lens_frame;

in vec4 uvcoord; // coordinates [0.0, 1.0]

void main()
{
	vec2 size = grain_params.zw * lens_frame.zw;
	float aspect = size.x / size.y;

	vec2 fuv = (uvcoord.xy - lens_frame.xy) / lens_frame.zw;
	bool in_frame = !camera_lens_outside(fuv);
	vec4 params = in_frame ? lens_params : vec4(0.0);

	vec2 uv = camera_lens_fisheye(fuv, aspect, params.w);
	vec2 v = uv - 0.5;
	vec2 suv = lens_frame.xy + uv * lens_frame.zw;

	vec4 direct = texture(colorbuffer, in_frame ? suv : uvcoord.xy);
	vec3 color = direct.rgb;
	if (params.x > 0.0) {
		vec2 shift = camera_lens_chroma_shift(v, params.x) * lens_frame.zw;
		color = vec3(texture(colorbuffer, suv + shift).r, direct.g, texture(colorbuffer, suv - shift).b);
	}

	color = camera_lens_vignette(color, v, params.y, params.z);
	color = camera_lens_grain(color, in_frame ? uv : uvcoord.xy, grain_params.x, grain_params.y);

	if (params.w != 0.0 && camera_lens_outside(uv)) {
		color = vec3(0.0);
	}

	gl_FragColor = vec4(color, direct.a);
}
