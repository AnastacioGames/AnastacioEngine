// color buffer
uniform sampler2D colorbuffer;

// jitter texture for ssao
uniform sampler2D jitter_tex;

// concentric sample texture for ssao
uniform sampler1D ssao_concentric_tex;

// depth buffer
uniform sampler2D depthbuffer;
// coordinates on framebuffer in normalized (0.0-1.0) uv space
in vec4 uvcoord;

/* ssao_params.x : pixel scale for the ssao radious */
/* ssao_params.y : factor for the ssao darkening */
uniform vec4 ssao_params;
uniform vec3 ssao_sample_params;
uniform vec4 ssao_color;

/* store the view space vectors for the corners of the view frustum here.
 * It helps to quickly reconstruct view space vectors by using uv coordinates,
 * see http://www.derschmale.com/2014/01/26/reconstructing-positions-from-the-depth-buffer */
uniform vec4 viewvecs[3];

vec3 calculate_view_space_normal(in vec3 viewposition)
{
	vec3 normal = cross(normalize(dFdx(viewposition)),
	                    ssao_params.w * normalize(dFdy(viewposition)));
	return normalize(normal);
}

float calculate_ssao_factor(float depth)
{
	/* take the normalized ray direction here */
	vec2 rotX = texture2DLod(jitter_tex, uvcoord.xy * ssao_sample_params.yz, 0).rg;
	vec2 rotY = vec2(-rotX.y, rotX.x);

	/* occlusion is zero in full depth */
	if (depth == 1.0)
		return 0.0;

	vec3 position = get_view_space_from_depth(uvcoord.xy, viewvecs[0].xyz, viewvecs[1].xyz, depth);
	vec3 normal = calculate_view_space_normal(position);

	/* find the offset in screen space by multiplying a point
	 * in camera space at the depth of the point by the projection matrix. */
	vec2 offset;
	float homcoord = gl_ProjectionMatrix[2][3] * position.z + gl_ProjectionMatrix[3][3];
	offset.x = gl_ProjectionMatrix[0][0] * ssao_params.x / homcoord;
	offset.y = gl_ProjectionMatrix[1][1] * ssao_params.x / homcoord;
	/* convert from -1.0...1.0 range to 0.0..1.0 for easy use with texture coordinates */
	offset *= 0.5;

	float factor = 0.0;
	int x;
	int num_samples = int(ssao_sample_params.x);

	for (x = 0; x < num_samples; x++) {
		vec2 dir_sample = texture1D(ssao_concentric_tex, (float(x) + 0.5) / ssao_sample_params.x).rg;

		/* rotate with random direction to get jittered result */
		vec2 dir_jittered = vec2(dot(dir_sample, rotX), dot(dir_sample, rotY));

		vec2 uvcoords = uvcoord.xy + dir_jittered * offset;

		if (uvcoords.x > 1.0 || uvcoords.x < 0.0 || uvcoords.y > 1.0 || uvcoords.y < 0.0)
			continue;

		float depth_new = texture2D(depthbuffer, uvcoords).r;
		if (depth_new != 1.0) {
			vec3 pos_new = get_view_space_from_depth(uvcoords, viewvecs[0].xyz, viewvecs[1].xyz, depth_new);
			vec3 dir = pos_new - position;
			float len = length(dir);
			float f = dot(dir, normal);

			/* use minor bias here to avoid self shadowing */
			if (f > 0.05 * len)
				factor += f * 1.0 / (len * (1.0 + len * len * ssao_params.z));
		}
	}

	factor /= ssao_sample_params.x;

	return 1.0 - clamp(factor * ssao_params.y, 0.0, 1.0);
}

/* Ground Truth AO, same as the game (RAS_SSAO2DFilter.glsl, Jimenez 2016 after XeGTAO) so the
 * viewport preview matches the P player: visible arc between the two horizons of each slice,
 * multi-bounce by the albedo, then pow(visibility, factor). The old estimator above stayed for
 * reference but skipped bright pixels (the "lumina" term), which hid AO on PBR materials. */
#define GTAO_PI 3.14159265358979323846

vec3 view_position(vec2 uv)
{
	return get_view_space_from_depth(uv, viewvecs[0].xyz, viewvecs[1].xyz, texture2D(depthbuffer, uv).r);
}

vec3 gtao_normal(vec3 p, vec2 uv, vec2 texel)
{
	vec3 r = view_position(uv + vec2(texel.x, 0.0)) - p;
	vec3 l = p - view_position(uv - vec2(texel.x, 0.0));
	vec3 t = view_position(uv + vec2(0.0, texel.y)) - p;
	vec3 b = p - view_position(uv - vec2(0.0, texel.y));
	vec3 dx = abs(r.z) < abs(l.z) ? r : l;
	vec3 dy = abs(t.z) < abs(b.z) ? t : b;
	return normalize(cross(dx, dy)) * sign(ssao_params.w);
}

float gtao_visibility(float depth, vec3 albedo)
{
	if (depth == 1.0)
		return 1.0;

	vec2 texel = 1.0 / vec2(textureSize(depthbuffer, 0));
	vec3 p = get_view_space_from_depth(uvcoord.xy, viewvecs[0].xyz, viewvecs[1].xyz, depth);
	vec3 n = gtao_normal(p, uvcoord.xy, texel);
	vec3 v = normalize(-p);
	if (dot(n, v) < 0.0)
		n = -n;

	float radius = ssao_params.x;
	vec2 screen_radius = 0.5 * radius * vec2(gl_ProjectionMatrix[0][0], gl_ProjectionMatrix[1][1]) / max(-p.z, 1e-4);
	if (screen_radius.x < texel.x)
		return 1.0;

	int total = max(int(ssao_sample_params.x), 4);
	int slices = total >= 16 ? 4 : 2;
	int steps = max(total / (slices * 2), 2);
	float falloff_range = 0.6 * radius;
	float falloff_mul = -1.0 / falloff_range;
	float falloff_add = (radius - falloff_range) / falloff_range + 1.0;

	float noise_slice = fract(52.9829189 * fract(dot(gl_FragCoord.xy, vec2(0.06711056, 0.00583715))));
	float noise_step = fract(noise_slice + 0.61803398875);

	float visibility = 0.0;
	for (int s = 0; s < slices; s++) {
		float phi = (float(s) + noise_slice) * GTAO_PI / float(slices);
		vec2 omega = vec2(cos(phi), sin(phi));
		vec3 dir = vec3(omega, 0.0);
		vec3 ortho = dir - dot(dir, v) * v;
		vec3 axis = normalize(cross(ortho, v));
		vec3 proj_n = n - axis * dot(n, axis);
		float proj_len = length(proj_n);
		float cos_n = clamp(dot(proj_n, v) / max(proj_len, 1e-4), 0.0, 1.0);
		float angle_n = sign(dot(ortho, proj_n)) * acos(cos_n);

		float low0 = cos(angle_n + 0.5 * GTAO_PI);
		float low1 = cos(angle_n - 0.5 * GTAO_PI);
		float horizon0 = low0;
		float horizon1 = low1;
		for (int j = 0; j < steps; j++) {
			float t = (float(j) + noise_step) / float(steps);
			vec2 offset = t * t * screen_radius * omega + omega * texel;
			for (int side = 0; side < 2; side++) {
				vec2 uv = uvcoord.xy + (side == 0 ? offset : -offset);
				if (uv.x > 1.0 || uv.x < 0.0 || uv.y > 1.0 || uv.y < 0.0)
					continue;
				vec3 delta = view_position(uv) - p;
				float dist = length(delta);
				float weight = clamp(dist * falloff_mul + falloff_add, 0.0, 1.0);
				float h = dot(delta, v) / max(dist, 1e-4);
				if (side == 0)
					horizon0 = max(horizon0, mix(low0, h, weight));
				else
					horizon1 = max(horizon1, mix(low1, h, weight));
			}
		}
		float h0 = -acos(clamp(horizon1, -1.0, 1.0));
		float h1 = acos(clamp(horizon0, -1.0, 1.0));
		h0 = angle_n + max(h0 - angle_n, -0.5 * GTAO_PI);
		h1 = angle_n + min(h1 - angle_n, 0.5 * GTAO_PI);
		float sin_n = sin(angle_n);
		float arc0 = (cos_n + 2.0 * h0 * sin_n - cos(2.0 * h0 - angle_n)) * 0.25;
		float arc1 = (cos_n + 2.0 * h1 * sin_n - cos(2.0 * h1 - angle_n)) * 0.25;
		visibility += proj_len * (arc0 + arc1);
	}
	visibility = clamp(visibility / float(slices), 0.0, 1.0);

	vec3 a = 2.0404 * albedo - 0.3324;
	vec3 b = -4.7951 * albedo + 0.6417;
	vec3 c = 2.7552 * albedo + 0.6903;
	vec3 bounce = max(vec3(visibility), ((visibility * a + b) * visibility + c) * visibility);
	visibility = dot(bounce, vec3(0.2126, 0.7152, 0.0722));

	return pow(visibility, ssao_params.y);
}

void main()
{
	float depth = texture2D(depthbuffer, uvcoord.xy).x;
	vec3 scene_col = texture2D(colorbuffer, uvcoord.xy).rgb;

	gl_FragColor = vec4(scene_col * gtao_visibility(depth, clamp(scene_col, 0.0, 1.0)), 1.0);
}
