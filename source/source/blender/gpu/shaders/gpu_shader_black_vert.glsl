#ifdef USE_CORE_PROFILE
layout(location = 0) in vec3 att_Position;
uniform mat4 unfviewmat;
uniform mat4 unfobmat;
uniform mat4 unfprojmat;
#define gl_Vertex vec4(att_Position, 1.0)
#define gl_ModelViewMatrix (unfviewmat * unfobmat)
#define gl_ProjectionMatrix unfprojmat
#endif

#ifdef USE_INSTANCING
in mat3 ininstmatrix;
in vec3 ininstposition;
#endif

void main()
{
#ifdef USE_INSTANCING
	mat4 instmat = mat4(vec4(ininstmatrix[0], ininstposition.x),
						vec4(ininstmatrix[1], ininstposition.y),
						vec4(ininstmatrix[2], ininstposition.z),
						vec4(0.0, 0.0, 0.0, 1.0));

	gl_Position = gl_ProjectionMatrix * gl_ModelViewMatrix * (gl_Vertex * instmat);
#else
	gl_Position = gl_ProjectionMatrix * gl_ModelViewMatrix * gl_Vertex;
#endif
}
