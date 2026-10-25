#ifdef USE_CORE_PROFILE
in vec2 texCoordVarying;

out vec4 fragColor;
  #define gl_FragColor fragColor
#endif

#ifndef BLOOM_LOD
#define BLOOM_LOD 2
#endif

/* Level 0 reads the bright pass; level N reads level N-1 (progressive chain, downsampled by the
 * bilinear fetch). The step is one texel of this level's own resolution. */
uniform sampler2D bgl_RenderedBloomB;
uniform vec4 ge_BloomParams; // intensity, threshold, width, height

vec2 texcoord;

/* 11-tap gaussian folded into 6 bilinear taps (center + 5 pairs sampled between texels),
 * so every texel of the level contributes: no gaps between samples. */
const float w0 = 0.198596;
const float wl[6] = float[](0.175713, 0.121703, 0.065984, 0.028002, 0.0093, 0.0);

void main() {
#ifdef USE_CORE_PROFILE
	texcoord = texCoordVarying;
#else
	texcoord = gl_TexCoord[0].st;
#endif

	vec2 texel = float(BLOOM_LOD) / ge_BloomParams.zw; // texel of this level (target) resolution

	vec3 result = texture(bgl_RenderedBloomB, texcoord).rgb * w0;
	for (int i = 0; i < 5; i += 2) {
		float wa = wl[i];
		float wb = wl[i + 1];
		float w = wa + wb;
		float o = (float(i + 1) * wa + float(i + 2) * wb) / w;
		vec2 offset = vec2(texel.x * o, 0.0);
		result += (texture(bgl_RenderedBloomB, texcoord + offset).rgb + texture(bgl_RenderedBloomB, texcoord - offset).rgb) * w;
	}

	gl_FragColor = vec4(result, 1.0);
}
