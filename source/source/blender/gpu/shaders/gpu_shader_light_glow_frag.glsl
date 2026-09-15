#if __VERSION__ < 130
  #define flat
  #define in varying
#endif

in vec2 localPos;
flat in vec4 finalColor;

#ifdef USE_CORE_PROFILE
out vec4 fragColor;
#endif

void main()
{
	/* Simple radial glow falloff, generated procedurally so the light impostor doesn't need
	 * an external texture asset -- soft center, fading smoothly to transparent at the quad edge. */
	float dist = length(localPos) * 2.0; /* localPos in [-0.5, 0.5] -> dist in [0, ~1.41] */
	float glow = 1.0 - smoothstep(0.0, 1.0, dist);
	glow *= glow;

	vec4 outColor = vec4(finalColor.rgb, finalColor.a * glow);

#ifdef USE_CORE_PROFILE
	fragColor = outColor;
#else
	gl_FragData[0] = outColor;
#endif
}
