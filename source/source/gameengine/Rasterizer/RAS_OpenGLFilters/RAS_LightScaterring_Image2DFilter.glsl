
#ifdef USE_CORE_PROFILE
in vec2 texCoordVarying;

out vec4 fragColor;
  #define gl_FragColor fragColor
#endif

uniform sampler2D bgl_RenderedTexture;
uniform sampler2D bgl_LightScatter;

vec2 texcoord;

void main() {
#ifdef USE_CORE_PROFILE
	texcoord = texCoordVarying;
#else
	texcoord = gl_TexCoord[0].st;
#endif

	vec3 image = texture(bgl_RenderedTexture, texcoord).rgb;
	vec3 scatter = texture(bgl_LightScatter,  texcoord).rgb;

	gl_FragColor.rgb = image + scatter;
}
