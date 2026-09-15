
in vec4 uvcoord; // coordinates [0.0, 1.0]

uniform sampler2D colorbuffer; // color buffer

// depth buffer
uniform sampler2D depthbuffer;

uniform vec3 sunpos; // screen sun position -> sun orientation
uniform vec4 scatter_params; // Intensity, Threshold, stepSize, stepMax

vec3 saturation(vec3 col) {
	const vec3 W = vec3(0.2125, 0.7154, 0.0721);

	vec3 intensity = vec3(dot(col, W));

	return mix(intensity, col, 0.5);
}

void main() {
	vec3 cam_space = (gl_ModelViewMatrix * vec4(sunpos, 0.0)).xyz;
	vec4 clip_space = gl_ProjectionMatrix * vec4(cam_space, 0.0);
	vec2 view_pos = (clip_space.xy / clip_space.w) * 0.5 + 0.5;

	float depth = texture(depthbuffer, uvcoord.xy).x;
	depth = step(1.0, depth);

	vec2 delta = (uvcoord.xy - view_pos) * scatter_params.z;

	vec3 result = vec3(0.0);
	float weights = 1.0;

	for (int i = 0; i < int(scatter_params.w); i++) {
		vec2 offset = uvcoord.xy - delta * (float(i) / scatter_params.w);

		vec3 color = texture(colorbuffer, offset).rgb - scatter_params.y;

		weights *= 0.95;
		result += max(vec3(0.0), color * depth) * weights;
	}

	vec4 view = inverse(gl_ProjectionMatrix) * vec4(uvcoord.xy * 2.0 - 1.0, 0.0, 1.0);
	view /= view.w;

	vec4 world = inverse(gl_ModelViewMatrix) * view;
	world.xyz /= world.w;

	float occluder = clamp(1.0 - dot(world.xyz, sunpos), 0.0, 1.0);

	vec3 image = texture(colorbuffer, uvcoord.xy).rgb;

	gl_FragColor = vec4(image + saturation(result) * occluder * scatter_params.x, 1.0);
}
