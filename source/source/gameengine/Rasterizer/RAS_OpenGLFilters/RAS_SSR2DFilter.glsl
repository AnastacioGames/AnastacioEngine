
#ifdef USE_CORE_PROFILE
in vec2 texCoordVarying;

uniform mat4 unfviewmat;
uniform mat4 unfprojmat;
  #define gl_ModelViewMatrix unfviewmat
  #define gl_ProjectionMatrix unfprojmat
  #define gl_ProjectionMatrixInverse inverse(unfprojmat)

out vec4 fragColor;
  #define gl_FragColor fragColor
#endif

uniform sampler2D bgl_RenderedTexture;
uniform sampler2D bgl_DataTextures[1];
uniform sampler2D bgl_DepthTexture;

uniform vec3 ge_ssrparams; // step_max, bias, max_distance

vec3 rand3D(vec3 pos) {
	pos = vec3(
		dot(pos, vec3(12.1, 78.7, 45.7)),
		dot(pos, vec3(93.5, 67.3, 12.1)),
		dot(pos, vec3(54.5, 98.9, 12.6))
	);

	return fract(sin(pos) * 43758.5453123) - 0.5;
}

vec2 unpackFloat2(float f) {
	return vec2(floor(f) / 255.0, fract(f));
}

vec3 decode_octa(vec2 e) {
	vec3 v = vec3(e.xy, 1.0 - abs(e.x) - abs(e.y));

	if (v.z < 0.0)
		v.xy = (1.0 - abs(v.yx)) * vec2((v.x >= 0.0) ? 1.0 : -1.0, (v.y >= 0.0) ? 1.0 : -1.0);

	return -(gl_ModelViewMatrix * vec4(normalize(v), 0.0)).xyz;
}

vec2 texcoord;

void main() {
#ifdef USE_CORE_PROFILE
	texcoord = texCoordVarying;
#else
	texcoord = gl_TexCoord[0].st;
#endif

	float stepSize = ge_ssrparams.z / ge_ssrparams.x;

	float depth = texture(bgl_DepthTexture, texcoord).x;

	vec4 camera_space_pos = gl_ProjectionMatrixInverse * vec4(texcoord * 2.0 - 1.0, depth, 1.0);
	vec3 pixel_position = camera_space_pos.xyz / camera_space_pos.w;

	vec4 Gbuff0 = texture(bgl_DataTextures[0], texcoord).rgba;
	vec3 normal = decode_octa(Gbuff0.rg);
	vec2 rough_metal = unpackFloat2(Gbuff0.b);
	vec2 diff_spec = unpackFloat2(Gbuff0.a);

	vec3 noise = rand3D(pixel_position) * 0.25;

	vec3 view_dir = normalize(pixel_position);
	vec3 reflect_dir = reflect(view_dir, normal);

	if (rough_metal.x > 0.05) {
		reflect_dir += noise * rough_metal.x * rough_metal.x;
	}

	vec3 ray_pos = pixel_position;
	vec3 one_step = reflect_dir * stepSize;

	vec3 col = vec3(0.0);

	for (int i = 0; i < int(ge_ssrparams.x); i++) {
		ray_pos += one_step;

		vec4 clip_pos = gl_ProjectionMatrix * vec4(ray_pos, 1.0);
		vec2 screen_pos = clip_pos.xy / clip_pos.w * 0.5 + 0.5;

		if (screen_pos.x < 0.0 || screen_pos.x > 1.0 || screen_pos.y < 0.0 || screen_pos.y > 1.0) {
			break;
		}

		float scene_depth = texture(bgl_DepthTexture, screen_pos).x;

		vec4 projected_pos = gl_ProjectionMatrixInverse * vec4(screen_pos * 2.0 - 1.0, scene_depth, 1.0);
		vec3 scene_position = projected_pos.xyz / projected_pos.w;

		if (length(scene_position) < length(ray_pos)) {
			if(abs(ray_pos.z - scene_position.z) < stepSize * ge_ssrparams.y) {
				col = texture(bgl_RenderedTexture, screen_pos).rgb;
			}

			break;
		}

		if (length(ray_pos) > ge_ssrparams.z) {
			break;
		}
	}

	depth = 1.0 - step(1.0, depth);

	float fresnel = pow(1.0 - max(0.0, dot(-normal, view_dir)), 2.0);
	float factor = fresnel * (1.0 - rough_metal.x);

	gl_FragColor.rgb = col * depth * factor * ((rough_metal.y < 0.1) ? diff_spec.y : 1.0);
	gl_FragColor.a = 1.0;
}
