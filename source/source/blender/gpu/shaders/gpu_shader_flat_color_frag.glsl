#if __VERSION__ < 130
  #define flat
  #define in varying
#endif

flat in vec4 finalColor;

#ifdef USE_CORE_PROFILE
out vec4 fragColor;
#endif

void main()
{
#ifdef USE_CORE_PROFILE
	fragColor = finalColor;
#else
	gl_FragData[0] = finalColor;
#endif
}
