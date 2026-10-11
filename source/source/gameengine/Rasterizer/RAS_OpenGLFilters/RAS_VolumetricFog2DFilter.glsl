/* Volumetric Fog (World > Weather). The fog itself is gpu_shader_vfog_lib.glsl, prepended to this
 * text by KX_2DFilterManager::EnsureVFogFilters and shared with the 3D View pass. */

#ifdef USE_CORE_PROFILE
in vec2 texCoordVarying;

out vec4 fragColor;
  #define gl_FragColor fragColor
#endif

uniform sampler2D bgl_RenderedTexture;
uniform sampler2D bgl_DepthTexture;

uniform mat4 unfinvviewmat;
uniform mat4 unfinvprojmat;
uniform int bgl_Frame;

void main()
{
#ifdef USE_CORE_PROFILE
	vec2 texcoord = texCoordVarying;
#else
	vec2 texcoord = gl_TexCoord[0].st;
#endif
	vec4 direct = texture(bgl_RenderedTexture, texcoord);
	float depth = texture(bgl_DepthTexture, texcoord).x;

	vec4 clip = vec4(texcoord * 2.0 - 1.0, depth * 2.0 - 1.0, 1.0);
	vec4 viewPos = unfinvprojmat * clip;
	viewPos /= viewPos.w;
	vec3 camPos = (unfinvviewmat * vec4(0.0, 0.0, 0.0, 1.0)).xyz;
	vec3 worldPos = (unfinvviewmat * vec4(viewPos.xyz, 1.0)).xyz;
	vec3 ray = worldPos - camPos;
	float dist = length(ray);
	vec3 rd = ray / max(dist, 1e-6);
	if (depth >= 0.9999) {
		dist = 1e9;
	}

	gl_FragColor = vec4(vfogApply(direct.rgb, camPos, rd, dist, gl_FragCoord.xy, float(bgl_Frame)), direct.a);
}
