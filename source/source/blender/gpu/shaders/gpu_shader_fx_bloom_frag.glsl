in vec4 uvcoord; // coordinates [0.0, 1.0]

uniform sampler2D colorbuffer;  // color buffer
uniform vec4 bloom_params;      // intensity (x), threshold (y)

vec3 getCol(vec2 coord) {
	return max(texture(colorbuffer, coord).rgb - bloom_params.y, 0.0);
}

//const float weights[5] = float[](0.227027, 0.1945946, 0.1216216, 0.054054, 0.016216);
const float weights[9] = float[](0.204164, 0.190238, 0.152221, 0.102059, 0.057051, 0.027710, 0.011257, 0.004041, 0.001309);

vec3 saturation(vec3 col) {
	const vec3 W = vec3(0.2125, 0.7154, 0.0721);

	vec3 intensity = vec3(dot(col, W));

	return mix(intensity, col, 0.7);
}

vec3 mixScreen(vec3 base, vec3 blend) {
	return 1.0 - (1.0 - base) * (1.0 - blend);
}

/* The game bloom (RAS_Bloom2DFilter_*.glsl) sums 4 widths of blur (1/2 .. 1/16 resolution); here a
 * narrow and a wide gaussian, each weighted 2x, give about the same energy and spread so the
 * viewport preview matches the P player. The wide one skips every other tap, so its weights are scaled up (sum ~2). */
vec3 getBloom() {
	vec2 size = vec2(textureSize(colorbuffer, 0));
	vec2 narrow = 3.0 / size;
	vec2 wide = 12.0 / size;

	vec3 result = vec3(0.0);

	for (int x = -8; x <= 8; ++x) {
		for (int y = -8; y <= 8; ++y) {
			result += getCol(uvcoord.xy + vec2(x, y) * narrow).rgb * weights[abs(y)] * weights[abs(x)] * 2.0;
		}
	}
	for (int x = -8; x <= 8; x += 2) {
		for (int y = -8; y <= 8; y += 2) {
			result += getCol(uvcoord.xy + vec2(x, y) * wide).rgb * weights[abs(y)] * weights[abs(x)] * 5.0;
		}
	}

	return result;
}

#if __VERSION__ >= 130
layout(location = 0) out vec4 fragColor;
#define FINAL_COLOR fragColor
#else
#define FINAL_COLOR gl_FragColor
#endif

void main() {
	vec3 image = texture(colorbuffer, uvcoord.xy).rgb;
	vec3 bloom = getBloom() * bloom_params.x;

	bloom = clamp(saturation(bloom), 0.0, 1.0);

	FINAL_COLOR = vec4(mixScreen(image, bloom), 1.0);
}
