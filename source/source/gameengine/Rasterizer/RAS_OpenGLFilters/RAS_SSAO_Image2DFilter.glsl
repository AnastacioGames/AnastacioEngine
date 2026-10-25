/* Ambient Occlusion, composite pass (desktop). The GTAO visibility is traced at half resolution
 * into ssao_buffer (RAS_SSAO2DFilter.glsl with SSAO_TRACE); here a 4x4 bilateral filter over the
 * half resolution texels removes the per pixel noise of the trace without spilling the
 * occlusion across depth edges, then the multi-bounce fit uses the full resolution albedo. */

#ifdef USE_CORE_PROFILE
in vec2 texCoordVarying;

out vec4 fragColor;
  #define gl_FragColor fragColor
#endif

uniform sampler2D bgl_RenderedTexture;
uniform sampler2D bgl_DepthTexture;
uniform sampler2D ssao_buffer;

uniform mat4 unfprojmat;
uniform vec4 ge_ssaoparams; // Samples, Strength, Distance, Attenuation

/* Distance to the camera along the view axis (positive), from the depth buffer. */
float viewDepth(float depth)
{
	return unfprojmat[3][2] / (depth * 2.0 - 1.0 + unfprojmat[2][2]);
}

void main()
{
#ifdef USE_CORE_PROFILE
	vec2 texcoord = texCoordVarying;
#else
	vec2 texcoord = gl_TexCoord[0].st;
#endif
	vec4 color = texture(bgl_RenderedTexture, texcoord);
	float depth = texture(bgl_DepthTexture, texcoord).r;
	if (depth >= 1.0) {
		gl_FragColor = color;
		return;
	}

	vec2 size = vec2(textureSize(ssao_buffer, 0));
	float z = abs(viewDepth(depth));
	/* Depth tolerance grows with the distance (depth buffer precision, slanted floors). */
	float zTol = max(z * 0.1, 1e-3);

	/* 4x4 half resolution texels around this pixel (8x8 full resolution pixels, the period of the
	 * trace noise), tent weights times how close each texel's depth is to this pixel's. */
	vec2 p = texcoord * size - 0.5;
	vec2 base = floor(p) - 1.0;
	float sum = 0.0;
	float wsum = 0.0;
	for (int y = 0; y < 4; y++) {
		for (int x = 0; x < 4; x++) {
			vec2 t = base + vec2(float(x), float(y));
			vec2 d = abs(t - p);
			vec2 tent = max(vec2(2.0) - d, vec2(0.0));
			float sp = tent.x * tent.y;
			vec2 uv = (clamp(t, vec2(0.0), size - 1.0) + 0.5) / size;
			/* The trace texel used the depth at its center. */
			float zi = abs(viewDepth(texture(bgl_DepthTexture, uv).r));
			float w = sp * exp(-abs(zi - z) / zTol) + 1e-4 * sp;
			sum += texture(ssao_buffer, uv).r * w;
			wsum += w;
		}
	}
	float visibility = (wsum > 0.0) ? sum / wsum : texture(ssao_buffer, texcoord).r;

	/* multi-bounce fit (Jimenez 2016): bright surfaces get light back from the occluders around them */
	vec3 albedo = clamp(color.rgb, 0.0, 1.0);
	vec3 a = 2.0404 * albedo - 0.3324;
	vec3 b = -4.7951 * albedo + 0.6417;
	vec3 c = 2.7552 * albedo + 0.6903;
	vec3 bounce = max(vec3(visibility), ((visibility * a + b) * visibility + c) * visibility);
	visibility = dot(bounce, vec3(0.2126, 0.7152, 0.0722));

	gl_FragColor = vec4(color.rgb * pow(visibility, ge_ssaoparams.y), color.a);
}
