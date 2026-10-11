/* Volumetric Fog in the 3D View, mirrors RAS_VolumetricFog2DFilter.glsl: the fog itself is
 * gpu_shader_vfog_lib.glsl, passed as this shader's library code. */

in vec4 uvcoord; // coordinates [0.0, 1.0]

uniform sampler2D colorbuffer; // color buffer
uniform sampler2D depthbuffer; // depth buffer
uniform float vfog_frame;

void main()
{
	vec2 texcoord = uvcoord.xy;
	vec4 direct = texture(colorbuffer, texcoord);
	float depth = texture(depthbuffer, texcoord).x;

	vec4 clip = vec4(texcoord * 2.0 - 1.0, depth * 2.0 - 1.0, 1.0);
	vec4 viewPos = gl_ProjectionMatrixInverse * clip;
	viewPos /= viewPos.w;
	vec3 camPos = (gl_ModelViewMatrixInverse * vec4(0.0, 0.0, 0.0, 1.0)).xyz;
	vec3 worldPos = (gl_ModelViewMatrixInverse * vec4(viewPos.xyz, 1.0)).xyz;
	vec3 ray = worldPos - camPos;
	float dist = length(ray);
	vec3 rd = ray / max(dist, 1e-6);
	if (depth >= 0.9999) {
		dist = 1e9;
	}

	gl_FragColor = vec4(vfogApply(direct.rgb, camPos, rd, dist, gl_FragCoord.xy, vfog_frame), direct.a);
}
