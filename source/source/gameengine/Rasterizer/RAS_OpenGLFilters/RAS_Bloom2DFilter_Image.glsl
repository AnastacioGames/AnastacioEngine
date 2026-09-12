
#ifdef USE_CORE_PROFILE
in vec2 texCoordVarying;

out vec4 fragColor;
  #define gl_FragColor fragColor
#endif

uniform sampler2D bgl_RenderedTexture;

uniform sampler2D bgl_RenderedBloomI0;
uniform sampler2D bgl_RenderedBloomI1;
uniform sampler2D bgl_RenderedBloomI2;
uniform sampler2D bgl_RenderedBloomB;

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

	result += texture(bgl_RenderedBloomI0, texcoord).rgb;
	result += texture(bgl_RenderedBloomI1, texcoord).rgb;
	result += texture(bgl_RenderedBloomI2, texcoord).rgb;

	result += texture(bgl_RenderedBloomB, texcoord).rgb;

	result = clamp(saturation(result), 0.0, 1.0);

	gl_FragColor = vec4(mixScreen(image, result), 1.0);
}
