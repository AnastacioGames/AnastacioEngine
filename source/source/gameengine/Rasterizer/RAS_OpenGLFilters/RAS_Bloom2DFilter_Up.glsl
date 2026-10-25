#ifdef USE_CORE_PROFILE
in vec2 texCoordVarying;

out vec4 fragColor;
  #define gl_FragColor fragColor
#endif

/* Bloom, dual filter upsample: 8 bilinear taps (tent) of the smaller level, plus this level's own
 * downsample (Unreal/COD style accumulation, so every level adds its width to the glow). */
uniform sampler2D bgl_BloomSource; // smaller level (up chain)
uniform sampler2D bgl_BloomAdd;    // downsample of this level

vec3 bloomUpsample(sampler2D tex, vec2 uv)
{
	vec2 h = 1.0 / vec2(textureSize(tex, 0));
	vec3 sum = texture(tex, uv + vec2(-2.0 * h.x, 0.0)).rgb;
	sum += texture(tex, uv + vec2(2.0 * h.x, 0.0)).rgb;
	sum += texture(tex, uv + vec2(0.0, -2.0 * h.y)).rgb;
	sum += texture(tex, uv + vec2(0.0, 2.0 * h.y)).rgb;
	sum += texture(tex, uv + vec2(-h.x, -h.y)).rgb * 2.0;
	sum += texture(tex, uv + vec2(h.x, -h.y)).rgb * 2.0;
	sum += texture(tex, uv + vec2(-h.x, h.y)).rgb * 2.0;
	sum += texture(tex, uv + vec2(h.x, h.y)).rgb * 2.0;
	return sum / 12.0;
}

void main()
{
#ifdef USE_CORE_PROFILE
	vec2 uv = texCoordVarying;
#else
	vec2 uv = gl_TexCoord[0].st;
#endif
	gl_FragColor = vec4(bloomUpsample(bgl_BloomSource, uv) + texture(bgl_BloomAdd, uv).rgb, 1.0);
}
