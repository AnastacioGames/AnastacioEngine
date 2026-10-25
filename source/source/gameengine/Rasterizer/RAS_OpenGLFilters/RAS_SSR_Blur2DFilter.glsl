/* Screen Space Reflections, composite pass: blurs the (temporally resolved) SSR buffer by the
 * roughness of the surface and adds it to the image. Golden angle disk whose radius grows with
 * roughness^2; samples from surfaces of a very different roughness (or the sky) are rejected so
 * the glossy floor does not bleed onto a matte wall next to it. Samples across a depth or normal
 * edge (silhouette of a sphere over the floor) are rejected too: the half resolution buffer would
 * otherwise mix both reflections into a dotted rim. */

#ifdef USE_CORE_PROFILE
in vec2 texCoordVarying;

out vec4 fragColor;
  #define gl_FragColor fragColor
#endif

uniform sampler2D ssr_buffer;
uniform sampler2D bgl_DataTextures[1];
uniform sampler2D bgl_RenderedTexture;
uniform sampler2D bgl_DepthTexture;

#define SSR_BLUR_SAMPLES 16

vec2 unpackFloat2(float f) {
	return vec2(floor(f) / 255.0, fract(f));
}

void main() {
	vec2 texcoord;
#ifdef USE_CORE_PROFILE
	texcoord = texCoordVarying;
#else
	texcoord = gl_TexCoord[0].st;
#endif

	vec3 image = texture(bgl_RenderedTexture, texcoord).rgb;
	if (texture(bgl_DepthTexture, texcoord).x >= 1.0) {
		gl_FragColor = vec4(image, 1.0);
		return;
	}

	vec4 Gbuff0 = texture(bgl_DataTextures[0], texcoord);
	vec2 rough_metal = unpackFloat2(Gbuff0.b);
	float rough = rough_metal.x;
	float a = rough * rough;

	float depthC = texture(bgl_DepthTexture, texcoord).x;
	/* 1 - depth is ~ proportional to 1 / z, so its relative difference is the relative depth gap. */
	float invZC = max(1.0 - depthC, 1e-7);

	vec3 result = texture(ssr_buffer, texcoord).rgb;
	/* Minimum 1.5 texel radius even on mirrors: single-texel hit/miss disagreements (one ray hits,
	 * the neighbour misses) are softened instead of showing as streaks. */
	float radius = max(a * 24.0, 1.5);
	{
		vec2 texel = 1.0 / vec2(textureSize(ssr_buffer, 0));
		float n = 1.0;
		for (int i = 0; i < SSR_BLUR_SAMPLES; i++) {
			float fi = float(i) + 0.5;
			float r = sqrt(fi / float(SSR_BLUR_SAMPLES)) * radius;
			float ang = fi * 2.39996323;
			vec2 uv = texcoord + vec2(cos(ang), sin(ang)) * r * texel;
			vec4 g = texture(bgl_DataTextures[0], uv);
			vec2 rm = unpackFloat2(g.b);
			float w = 1.0 - smoothstep(0.1, 0.3, abs(rm.x - rough));
			float du = texture(bgl_DepthTexture, uv).x;
			w *= step(du, 0.99999);
			w *= 1.0 - smoothstep(0.01, 0.03, abs(du - depthC) / invZC);
			w *= 1.0 - smoothstep(0.1, 0.3, length(g.rg - Gbuff0.rg));
			result += texture(ssr_buffer, uv).rgb * w;
			n += w;
		}
		result /= n;
	}
	result = min(result, vec3(4.0));

	if (rough_metal.y < 0.1) {
		gl_FragColor = vec4(image + result, 1.0);
	}
	else {
		gl_FragColor = vec4(mix(image, image * result * 2.0, clamp(length(result), 0.0, 1.0)), 1.0);
	}
}
