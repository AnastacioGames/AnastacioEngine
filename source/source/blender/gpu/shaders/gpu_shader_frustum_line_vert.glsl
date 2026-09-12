#if __VERSION__ < 130
  #define in attribute
  #define flat
  #define out varying
#endif

#ifdef USE_CORE_PROFILE
uniform mat4 unfviewprojmat;
#endif

in vec3 pos;
in mat4 mat;
in vec4 color;

flat out vec4 finalColor;

void main()
{
#ifdef USE_CORE_PROFILE
	gl_Position = unfviewprojmat * mat * vec4(pos, 1.0);
#else
	gl_Position = gl_ModelViewProjectionMatrix * mat * vec4(pos, 1.0);
#endif
	finalColor = color;
}
