#ifdef USE_CORE_PROFILE
in vec2 texCoordVarying;

out vec4 fragColor;
  #define gl_FragColor fragColor
#endif

/* Bloom, dual filter (Kawase/Bjorge, SIGGRAPH 2015) downsample: 5 bilinear taps (center x4 and
 * the 4 diagonals one source texel away) cover a 4x4 footprint of the level above. The first level
 * (BLOOM_PREFILTER) reads the scene and keeps only what is above the threshold. */
#ifdef BLOOM_PREFILTER
uniform sampler2D bgl_RenderedTexture;
  #define BLOOM_SOURCE bgl_RenderedTexture
#else
uniform sampler2D bgl_BloomSource;
  #define BLOOM_SOURCE bgl_BloomSource
#endif
uniform vec4 ge_BloomParams; // intensity, threshold, width, height

vec3 bloomTap(vec2 uv)
{
	vec3 c = texture(BLOOM_SOURCE, uv).rgb;
#ifdef BLOOM_PREFILTER
	c = max(c - ge_BloomParams.y, 0.0) * ge_BloomParams.x;
#endif
	return c;
}

void main()
{
#ifdef USE_CORE_PROFILE
	vec2 uv = texCoordVarying;
#else
	vec2 uv = gl_TexCoord[0].st;
#endif
	vec2 t = 1.0 / vec2(textureSize(BLOOM_SOURCE, 0));
	vec3 sum = bloomTap(uv) * 4.0;
	sum += bloomTap(uv + vec2(-t.x, -t.y));
	sum += bloomTap(uv + vec2(t.x, -t.y));
	sum += bloomTap(uv + vec2(-t.x, t.y));
	sum += bloomTap(uv + vec2(t.x, t.y));
	gl_FragColor = vec4(sum * 0.125, 1.0);
}
