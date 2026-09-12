// coordinates on framebuffer in normalized (0.0-1.0) uv space
in vec4 uvcoord;

// color buffer
uniform sampler2D colorbuffer;

// jitter texture
uniform sampler2D jitter_tex;

// depth buffer
uniform sampler2D depthbuffer;

uniform vec4 ssr_params; // step_max, max_dist, roughness, bias

/* store the view space vectors for the corners of the view frustum here.
 * It helps to quickly reconstruct view space vectors by using uv coordinates,
 * see http://www.derschmale.com/2014/01/26/reconstructing-positions-from-the-depth-buffer */
uniform vec4 viewvecs[3];

vec3 calculate_view_space_normal(in vec3 viewposition)
{
	vec3 normal = cross(normalize(dFdx(viewposition)),
	                    //ssr_extra_params.y * normalize(dFdy(viewposition)));
						normalize(dFdy(viewposition)));
	return normalize(normal);
}

vec3 calculate_ssr_factor() {
	float roughness = ssr_params.z; // strength [0.0, 1.0]

	int num_samples = int(ssr_params.x);

	float depth = texture(depthbuffer, uvcoord.xy).x;

	vec3 position = get_view_space_from_depth(uvcoord.xy, viewvecs[0].xyz, viewvecs[1].xyz, depth);
	vec3 normal = calculate_view_space_normal(position);

	vec4 camera_space_pos = gl_ProjectionMatrixInverse * vec4(uvcoord.xy * 2.0 - 1.0, depth, 1.0);
	vec3 pixel_position = camera_space_pos.xyz / camera_space_pos.w;

	vec2 uv = camera_space_pos.xy / length(camera_space_pos);

	vec2 rotX = texture(jitter_tex, uv * 43543.0).xy;
	vec3 noise = vec3(rotX.y, rotX.x, rotX.x - rotX.y);

	vec3 view_dir = normalize(pixel_position);
	vec3 reflect_dir = reflect(view_dir, normal);

	if (roughness > 0.05) {
		reflect_dir += noise * roughness * roughness;
	}

	vec3 col = vec3(0.0);

	float stepSize = ssr_params.y / num_samples;

	vec3 ray_pos = pixel_position;
	vec3 one_step = reflect_dir * stepSize;

	for (int i = 0; i < num_samples; i++) {
		ray_pos += one_step;

		vec4 clip_pos = gl_ProjectionMatrix * vec4(ray_pos, 1.0);
		vec2 screen_pos = clip_pos.xy / clip_pos.w * 0.5 + 0.5;

		if (screen_pos.x < 0.0 || screen_pos.x > 1.0 || screen_pos.y < 0.0 || screen_pos.y > 1.0) {
			break;
		}

		float scene_depth = texture(depthbuffer, screen_pos).x;

		vec4 projected_pos = gl_ProjectionMatrixInverse * vec4(screen_pos * 2.0 - 1.0, scene_depth, 1.0);
		vec3 scene_position = projected_pos.xyz / projected_pos.w;

		if (length(scene_position) < length(ray_pos)) {
			if(abs(ray_pos.z - scene_position.z) < stepSize * ssr_params.w) {
				col = texture(colorbuffer, screen_pos).rgb;
			}

			break;
		}

		if (length(ray_pos) > ssr_params.y) {
			break;
		}
	}

	float fresnel = pow(1.0 - max(0.0, dot(normal, view_dir)), 2.0);

	depth = 1.0 - step(1.0, depth);

	return col * fresnel * depth * (1.0 - roughness) * 0.25;
}

void main() {
	vec3 color = texture(colorbuffer, uvcoord.xy).rgb;

	vec3 final_color = calculate_ssr_factor();

	gl_FragColor.rgb = color + final_color;
	gl_FragColor.a = 1.0;
}
