
#ifdef USE_CORE_PROFILE
in vec2 texCoordVarying;

out vec4 fragColor;
  #define gl_FragColor fragColor
#endif

uniform sampler2D bgl_RenderedTexture;
uniform vec4 ge_BloomParams; // intensity, threshold, width, height

vec2 texcoord;

void main() {
#ifdef USE_CORE_PROFILE
	texcoord = texCoordVarying;
#else
	texcoord = gl_TexCoord[0].st;
#endif

	vec3 color = texture(bgl_RenderedTexture, texcoord).rgb;
	vec3 result = max(color - ge_BloomParams.y, 0.0) * ge_BloomParams.x;

	gl_FragColor = vec4(result, 1.0);
}
