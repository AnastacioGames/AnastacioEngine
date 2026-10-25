
#ifdef USE_CORE_PROFILE
in vec2 texCoordVarying;

out vec4 fragColor;
  #define gl_FragColor fragColor
#endif

uniform sampler2D bgl_RenderedTexture;

/* Dual filter bloom (KX_2DFilterManager::EnsureBloomFilters): levels 1/2 .. 1/16 downsampled,
 * the 1/16 and 1/8 ones accumulated up to bgl_BloomUp (1/8); this pass upsamples it with a tent
 * and adds the 1/4 and 1/2 downsamples, the same 4 widths the old gaussian chain summed. */
uniform sampler2D bgl_BloomUp; // 1/8, up chain
uniform sampler2D bgl_BloomI1; // 1/4 downsample
uniform sampler2D bgl_BloomI0; // 1/2 downsample (prefiltered)

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

/* 4 diagonal bilinear taps half a texel away: a 3x3 tent, hides the blocks of the 1/4 level. */
vec3 bloomSoft(sampler2D tex, vec2 uv)
{
	vec2 h = 0.5 / vec2(textureSize(tex, 0));
	return 0.25 * (texture(tex, uv + vec2(-h.x, -h.y)).rgb + texture(tex, uv + vec2(h.x, -h.y)).rgb +
	               texture(tex, uv + vec2(-h.x, h.y)).rgb + texture(tex, uv + vec2(h.x, h.y)).rgb);
}

vec2 texcoord;

vec3 saturation(vec3 col) {
	const vec3 W = vec3(0.2125, 0.7154, 0.0721);

	vec3 intensity = vec3(dot(col, W));

	return mix(intensity, col, 0.7);
}

vec3 mixScreen(vec3 base, vec3 blend) {
	return 1.0 - (1.0 - base) * (1.0 - blend);
}

void main() {
#ifdef USE_CORE_PROFILE
	texcoord = texCoordVarying;
#else
	texcoord = gl_TexCoord[0].st;
#endif

	vec3 image = texture(bgl_RenderedTexture, texcoord).rgb;

	vec3 result = vec3(0.0);

	result += bloomUpsample(bgl_BloomUp, texcoord);
	result += bloomSoft(bgl_BloomI1, texcoord);
	result += texture(bgl_BloomI0, texcoord).rgb;

	result = clamp(saturation(result), 0.0, 1.0);

	gl_FragColor = vec4(mixScreen(image, result), 1.0);
}
