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
    float jitter_x = fract(sin(dot(xy, vec2(12.9898, 78.233))) * 43758.5453)*2-1;
    float jitter_y = fract(sin(dot(xy, vec2(98.2340, 34.982))) * 23452.9876)*2-1;
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

	for (x = 0; x < ge_ssaoparams.x; x++) {
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

	float ao = calculate_ssao_factor(depth);
//	float lumina = dot(scene_col, vec3(0.299, 0.587, 0.114));
	float lumina = pow(dot(scene_col, scene_col), 4.0);

	vec3 final_color = mix(vec3(0.0), scene_col, clamp(ao + lumina + step(1.0, depth), 0.0, 1.0));

    gl_FragColor = vec4(final_color, 1.0);
}
