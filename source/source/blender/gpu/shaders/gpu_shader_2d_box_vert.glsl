#if __VERSION__ < 130
  #define in attribute
  #define flat
  #define out varying
#endif

#ifdef USE_CORE_PROFILE
/* No fixed-function matrix stack under core profile, so the 2D screen-space
 * orthographic projection that would have come from glOrtho() (see
 * RAS_OpenGLDebugDraw::Flush) is uploaded explicitly here instead. */
uniform mat4 unforthomat;
#endif

in vec2 pos;
in vec4 trans;
in vec4 color;

flat out vec4 finalColor;

void main()
{
#ifdef USE_CORE_PROFILE
	gl_Position = unforthomat * vec4(pos * trans.zw + trans.xy, 0.0, 1.0);
#else
	gl_Position = gl_ProjectionMatrix * gl_ModelViewMatrix * vec4(pos * trans.zw + trans.xy, 0.0, 1.0);
#endif
	finalColor = color;
}
