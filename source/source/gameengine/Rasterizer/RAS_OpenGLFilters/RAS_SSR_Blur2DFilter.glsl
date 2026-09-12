
#ifdef USE_CORE_PROFILE
in vec2 texCoordVarying;

out vec4 fragColor;
  #define gl_FragColor fragColor
#endif

uniform sampler2D ssr_buffer;
uniform sampler2D bgl_DataTextures[1];
uniform sampler2D bgl_RenderedTexture;

const float Pi = 6.28318530718;
const float Directions = 9.0;
const float Quality = 3.0;

vec2 unpackFloat2(float f) {
	return vec2(floor(f) / 255.0, fract(f));
}

vec2 texcoord;

void main() {
#ifdef USE_CORE_PROFILE
	texcoord = texCoordVarying;
#else
	texcoord = gl_TexCoord[0].st;
#endif

	vec4 Gbuff0 = texture(bgl_DataTextures[0], texcoord).rgba;

	vec2 rough_metal = unpackFloat2(Gbuff0.b);
	rough_metal.x *= rough_metal.x;

	vec2 pixel = (rough_metal.x * 16.0) / textureSize(ssr_buffer, 0);

	vec3 result = texture(ssr_buffer, texcoord).rgb;

	for( float d = 0.0; d < Pi; d += Pi/Directions) {
		for(float i = 1.0/Quality; i <= 1.0; i += 1.0/Quality) {
			vec2 offset = vec2(cos(d), sin(d)) * pixel * i;

			result += texture(ssr_buffer, texcoord + offset).rgb;
		}
	}

	result /= Quality * Directions - 15.0;

	vec3 image = texture(bgl_RenderedTexture, texcoord).rgb;

	if (rough_metal.y < 0.1) {
		gl_FragColor.rgb = image + result;
	} else {
		gl_FragColor.rgb = mix(image, image * result * 2.0, length(result));
	}
}
