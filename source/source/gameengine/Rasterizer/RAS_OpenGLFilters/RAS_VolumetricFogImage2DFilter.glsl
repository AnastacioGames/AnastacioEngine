/* Volumetric Fog: composites the fog buffer (Full/Half/Quarter resolution; in-scatter rgb,
 * transmittance a, from RAS_VolumetricFog2DFilter.glsl with VFOG_LOW_RES) onto the image. The
 * nearby fog texels are weighted by how close their depth is to this pixel's, so the fog of the
 * sky does not bleed onto the edges of the objects in front of it (and the other way around). */

#ifdef USE_CORE_PROFILE
in vec2 texCoordVarying;

out vec4 fragColor;
  #define gl_FragColor fragColor
#endif

uniform sampler2D bgl_RenderedTexture;
uniform sampler2D bgl_DepthTexture;
uniform sampler2D vfog_buffer;

uniform mat4 unfinvprojmat;

float vfogViewDepth(vec2 uv)
{
	float depth = texture(bgl_DepthTexture, uv).x;
	vec4 v = unfinvprojmat * vec4(uv * 2.0 - 1.0, depth * 2.0 - 1.0, 1.0);
	return -v.z / v.w;
}

void main()
{
#ifdef USE_CORE_PROFILE
	vec2 texcoord = texCoordVarying;
#else
	vec2 texcoord = gl_TexCoord[0].st;
#endif
	vec4 direct = texture(bgl_RenderedTexture, texcoord);
	vec2 size = vec2(textureSize(vfog_buffer, 0));
	/* 3x3 fog texels around the nearest one, tent weights (radius 1.5 texels) times how close
	 * their depth is to this pixel's: also a small bilateral blur that smooths out the per pixel
	 * raymarch jitter (the IGN stipple), without spilling the fog across depth edges. */
	vec2 p = texcoord * size - 0.5;
	vec2 c = floor(p + 0.5);
	float z = vfogViewDepth(texcoord);
	float zTol = max(z * 0.05, 1e-3);

	vec4 sum = vec4(0.0);
	float wsum = 0.0;
	for (int y = -1; y <= 1; y++) {
		for (int x = -1; x <= 1; x++) {
			vec2 t = c + vec2(float(x), float(y));
			vec2 d = abs(t - p);
			vec2 tent = max(vec2(1.5) - d, vec2(0.0));
			float sp = tent.x * tent.y;
			vec2 uv = (clamp(t, vec2(0.0), size - 1.0) + 0.5) / size;
			/* The fog texel was computed with the depth at its center. */
			float zi = vfogViewDepth(uv);
			float w = sp * exp(-abs(zi - z) / zTol) + 1e-5 * sp;
			sum += texture(vfog_buffer, uv) * w;
			wsum += w;
		}
	}
	vec4 fog = (wsum > 0.0) ? sum / wsum : texture(vfog_buffer, texcoord);
	gl_FragColor = vec4(direct.rgb * fog.a + fog.rgb, direct.a);
}
