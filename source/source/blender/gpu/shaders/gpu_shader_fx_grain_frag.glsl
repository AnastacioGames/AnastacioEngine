// Film Grain, same noise as the in-game camera lens pass (RAS_CameraLens2DFilter.glsl).
uniform sampler2D colorbuffer;
// x: strength, y: seed
uniform vec4 grain_params;

in vec4 uvcoord; // coordinates [0.0, 1.0]

void main()
{
	vec2 uv = uvcoord.xy;
	vec4 direct = texture(colorbuffer, uv);
	vec3 color = direct.rgb;

	// Stronger on the mid tones.
	vec2 seed = uv + vec2(grain_params.y * 0.05, grain_params.y * 0.03);
	float n = fract(sin(dot(seed, vec2(12.9898, 78.233))) * 43758.5453) - 0.5;
	float luma = dot(color, vec3(0.299, 0.587, 0.114));
	float lumaMask = 1.0 - pow(abs(luma - 0.5) * 2.0, 2.0);
	color += n * grain_params.x * (0.5 + 0.5 * lumaMask);

	gl_FragColor = vec4(color, direct.a);
}
