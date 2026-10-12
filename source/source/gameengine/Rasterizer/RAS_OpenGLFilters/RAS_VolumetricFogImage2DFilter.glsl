/* Volumetric Fog at Half/Quarter resolution: composites the small fog buffer (in-scatter rgb,
 * transmittance a, from RAS_VolumetricFog2DFilter.glsl with VFOG_LOW_RES) onto the image. The 4
 * nearest fog texels are weighted by how close their depth is to this pixel's, so the fog of the
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
	/* Bottom-left of the 2x2 fog texels around this pixel and the bilinear weights. */
	vec2 p = texcoord * size - 0.5;
	vec2 base = floor(p);
	vec2 f = p - base;
	float z = vfogViewDepth(texcoord);

	vec4 sum = vec4(0.0);
	float wsum = 0.0;
	for (int i = 0; i < 4; i++) {
		vec2 o = vec2(mod(float(i), 2.0), floor(float(i) * 0.5));
		vec2 uv = (clamp(base + o, vec2(0.0), size - 1.0) + 0.5) / size;
		float bil = (o.x > 0.5 ? f.x : 1.0 - f.x) * (o.y > 0.5 ? f.y : 1.0 - f.y);
		/* The fog texel was computed with the depth at its center. */
		float zi = vfogViewDepth(uv);
		float w = bil * exp(-abs(zi - z) / max(z * 0.05, 1e-3)) + 1e-5 * bil;
		sum += texture(vfog_buffer, uv) * w;
		wsum += w;
	}
	vec4 fog = (wsum > 0.0) ? sum / wsum : texture(vfog_buffer, texcoord);
	gl_FragColor = vec4(direct.rgb * fog.a + fog.rgb, direct.a);
}
