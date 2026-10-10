#ifdef USE_CORE_PROFILE
  #define texture2D texture

in vec2 texCoordVarying;

uniform mat4 unfprojmat;
  #define gl_ProjectionMatrix unfprojmat

out vec4 fragColor;
  #define gl_FragColor fragColor
#endif

// Ambient Occlusion from 3D viewport as a Filter2D
// ported by Murilo Hilas
uniform vec4 ge_ssaoparams; // Samples, Strength, Distance, Attenuation
vec4 Color = vec4(0.0, 0.0, 0.0, 1.0);

//---------------------------------------------------------------------

uniform sampler2D bgl_RenderedTexture;
uniform sampler2D bgl_DepthTexture;
uniform float bgl_RenderedTextureWidth;
uniform float bgl_RenderedTextureHeight;

/* Core profile GLSL only allows constant expressions in global initializers, so anything
 * derived from a uniform, varying, or function call has to be assigned at runtime instead
 * of at declaration. These globals are populated once at the top of main(). */
vec4 uvcoordsvar;

float att;
/* ssao_params.x : pixel scale for the ssao radious */
/* ssao_params.y : factor for the ssao darkening */
vec4 ssao_params;

vec3 get_sample_params()
{
    vec3 sample_params;
    sample_params.x = ge_ssaoparams.x;
    /* multiplier so we tile the random texture on screen */
    sample_params.y = bgl_RenderedTextureWidth  / 64.0;
    sample_params.z = bgl_RenderedTextureHeight / 64.0;

    return sample_params;
}

vec3 ssao_sample_params;

mat4 projection;
mat4 invproj;

/* store the view space vectors for the corners of the view frustum here.
 * It helps to quickly reconstruct view space vectors by using uv coordinates,
 * see http://www.derschmale.com/2014/01/26/reconstructing-positions-from-the-depth-buffer */
vec4 viewvecs[3];
void getviewvecs(out vec4 viewvecs[3]) {
    vec4 tempVecs[3] = vec4[3](
        vec4(-1.0, -1.0, -1.0, 1.0),
        vec4(1.0, -1.0, -1.0, 1.0),
        vec4(-1.0, 1.0, -1.0, 1.0)
    );

    for (int i = 0; i < 3; i++) {
        tempVecs[i] = invproj * tempVecs[i];
        /* normalized trick see http://www.derschmale.com/2014/01/26/reconstructing-positions-from-the-depth-buffer */
        tempVecs[i] = tempVecs[i] * (1.0 / tempVecs[i].w);
        tempVecs[i] = tempVecs[i] * (1.0 / tempVecs[i].z);
        tempVecs[i].w = 1.0;
    }

    /* we need to store the differences */
    viewvecs[0] = tempVecs[0];
    viewvecs[1] = vec4(tempVecs[1].x - tempVecs[0].x, tempVecs[2].y - tempVecs[0].y, 0.0, 0.0);
    viewvecs[2] = tempVecs[2];
}

vec3 get_view_space_from_depth(in vec2 uvcoords, in vec3 viewvec_origin, in vec3 viewvec_diff, in float depth)
{
	float d = 2.0 * depth - 1.0;

	float zview = -projection[3][2] / (d + projection[2][2]);

	return zview * (viewvec_origin + vec3(uvcoords, 0.0) * viewvec_diff);
}

vec3 calculate_view_space_normal(in vec3 viewposition)
{
	vec3 normal = cross(normalize(dFdx(viewposition)),
	                    ssao_params.w * normalize(dFdy(viewposition)));
	return normalize(normal);
}

vec2 createJitter(vec2 xy)
{
    float jitter_x = fract(sin(dot(xy, vec2(12.9898, 78.233))) * 43758.5453) * 2.0 - 1.0;
    float jitter_y = fract(sin(dot(xy, vec2(98.2340, 34.982))) * 23452.9876) * 2.0 - 1.0;
    return normalize(vec2(jitter_x, jitter_y)) * (1.0 / ssao_sample_params.x);
}

vec2 spiralSampling(float x)
{
    float r = (x + 0.5) * (1.0 / float(ssao_sample_params.x));
    float phi = r * 7.357 * 2.0 * 3.14159265358979323846;
    return vec2(r * cos(phi), r * sin(phi));
}

float calculate_ssao_factor(float depth)
{
	/* take the normalized ray direction here */
    vec2 rotX = createJitter(gl_FragCoord.xy).rg;
	vec2 rotY = vec2(-rotX.y, rotX.x);

	/* occlusion is zero in full depth */
	if (depth == 1.0)
		return 0.0;

	vec3 position = get_view_space_from_depth(uvcoordsvar.xy, viewvecs[0].xyz, viewvecs[1].xyz, depth);
	vec3 normal = calculate_view_space_normal(position);

	/* find the offset in screen space by multiplying a point
	 * in camera space at the depth of the point by the projection matrix. */
	vec2 offset;
	float homcoord = projection[2][3] * position.z + projection[3][3];
	offset.x = projection[0][0] * ssao_params.x / homcoord;
	offset.y = projection[1][1] * ssao_params.x / homcoord;
	/* convert from -1.0...1.0 range to 0.0..1.0 for easy use with texture coordinates */
	offset *= 0.5;

	float factor = 0.0;
	int x;

	for (x = 0; x < int(ge_ssaoparams.x); x++) {
        vec2 dir_sample = spiralSampling((float(x) + 0.5) * ssao_sample_params.x);
		/* rotate with random direction to get jittered result */
		vec2 dir_jittered = vec2(dot(dir_sample, rotX), dot(dir_sample, rotY));

		vec2 uvcoords = uvcoordsvar.xy + dir_jittered * offset;

		if (uvcoords.x > 1.0 || uvcoords.x < 0.0 || uvcoords.y > 1.0 || uvcoords.y < 0.0)
			continue;

		float depth_new = texture2D(bgl_DepthTexture, uvcoords).r;
		if (depth_new != 1.0) {
			vec3 pos_new = get_view_space_from_depth(uvcoords, viewvecs[0].xyz, viewvecs[1].xyz, depth_new);
			vec3 dir = pos_new - position;
			float len = length(dir);
			float f = dot(dir, normal);

			/* use minor bias here to avoid self shadowing */
			if (f > 0.05 * len){
				factor += f * 1.0 / (len * (1.0 + len * len * ssao_params.z));
            }
		}
	}

	factor /= ssao_sample_params.x;

	return 1.0 - clamp(factor * ssao_params.y, 0.0, 1.0);
}

#ifndef GL_ES
/* Ground Truth AO (Jimenez et al. 2016, after Intel XeGTAO, MIT): integrates the visible arc between the
 * two horizons of each screen slice against the cosine lobe of the normal. Desktop only; GLSL ES (Web,
 * Android) keeps the cheaper spiral SSAO above. */
#define GTAO_PI 3.14159265358979323846

vec3 view_position(vec2 uv)
{
	return get_view_space_from_depth(uv, viewvecs[0].xyz, viewvecs[1].xyz, texture2D(bgl_DepthTexture, uv).r);
}

/* normal from the neighbour with the smaller depth step on each axis, so silhouettes do not smear */
vec3 gtao_normal(vec3 p, vec2 uv, vec2 texel)
{
	vec3 r = view_position(uv + vec2(texel.x, 0.0)) - p;
	vec3 l = p - view_position(uv - vec2(texel.x, 0.0));
	vec3 t = view_position(uv + vec2(0.0, texel.y)) - p;
	vec3 b = p - view_position(uv - vec2(0.0, texel.y));
	vec3 dx = abs(r.z) < abs(l.z) ? r : l;
	vec3 dy = abs(t.z) < abs(b.z) ? t : b;
	return normalize(cross(dx, dy));
}

float gtao_visibility(float depth, vec3 albedo)
{
	if (depth == 1.0)
		return 1.0;

	vec2 texel = vec2(1.0 / bgl_RenderedTextureWidth, 1.0 / bgl_RenderedTextureHeight);
	vec3 p = get_view_space_from_depth(uvcoordsvar.xy, viewvecs[0].xyz, viewvecs[1].xyz, depth);
	vec3 n = gtao_normal(p, uvcoordsvar.xy, texel);
	vec3 v = normalize(-p);

	float radius = ge_ssaoparams.z;
	/* view space radius to uv: projection scale over the distance to the camera */
	vec2 screen_radius = 0.5 * radius * vec2(projection[0][0], projection[1][1]) / max(-p.z, 1e-4);
	if (screen_radius.x < texel.x)
		return 1.0;

	int total = max(int(ge_ssaoparams.x), 4);
	int slices = total >= 16 ? 4 : 2;
	int steps = max(total / (slices * 2), 2);
	/* the far 60% of the radius fades out, so occluders do not pop in at the radius edge */
	float falloff_range = 0.6 * radius;
	float falloff_mul = -1.0 / falloff_range;
	float falloff_add = (radius - falloff_range) / falloff_range + 1.0;

	/* interleaved gradient noise: the per pixel rotation and step jitter average out over 4x4 pixels */
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
			/* quadratic distribution: more samples close to the pixel, where contact shadows live */
			vec2 offset = t * t * screen_radius * omega + omega * texel;
			for (int side = 0; side < 2; side++) {
				vec2 uv = uvcoordsvar.xy + (side == 0 ? offset : -offset);
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

	/* multi-bounce fit (Jimenez 2016): bright surfaces get light back from the occluders around them */
	vec3 a = 2.0404 * albedo - 0.3324;
	vec3 b = -4.7951 * albedo + 0.6417;
	vec3 c = 2.7552 * albedo + 0.6903;
	vec3 bounce = max(vec3(visibility), ((visibility * a + b) * visibility + c) * visibility);
	visibility = dot(bounce, vec3(0.2126, 0.7152, 0.0722));

	return pow(visibility, ge_ssaoparams.y);
}
#endif

void main()
{
#ifdef USE_CORE_PROFILE
    uvcoordsvar = vec4(texCoordVarying, 0.0, 1.0);
#else
    uvcoordsvar = gl_TexCoord[0];
#endif

    att = ge_ssaoparams.w / (ge_ssaoparams.z * ge_ssaoparams.z);
    ssao_params = vec4(ge_ssaoparams.z, ge_ssaoparams.y, att, 1.0);
    ssao_sample_params = get_sample_params();
    projection = gl_ProjectionMatrix;
    invproj = inverse(projection);

    getviewvecs(viewvecs);

	float depth = texture(bgl_DepthTexture, uvcoordsvar.xy).x;
    vec3 scene_col = texture(bgl_RenderedTexture, uvcoordsvar.xy).rgb;

#ifndef GL_ES
	gl_FragColor = vec4(scene_col * gtao_visibility(depth, clamp(scene_col, 0.0, 1.0)), 1.0);
	return;
#endif
	float ao = calculate_ssao_factor(depth);
//	float lumina = dot(scene_col, vec3(0.299, 0.587, 0.114));
	float lumina = pow(dot(scene_col, scene_col), 4.0);

	vec3 final_color = mix(vec3(0.0), scene_col, clamp(ao + lumina + step(1.0, depth), 0.0, 1.0));

    gl_FragColor = vec4(final_color, 1.0);
}
