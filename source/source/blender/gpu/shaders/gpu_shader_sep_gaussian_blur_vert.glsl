#if __VERSION__ >= 130

layout(location = 0) in vec2 pos;
layout(location = 1) in vec2 uv;
out vec2 texCoordVarying;

void main()
{
	gl_Position = vec4(pos, 0.0, 1.0);
#ifndef USE_CORE_PROFILE
	gl_TexCoord[0] = vec4(uv, 0.0, 1.0);
#endif
	texCoordVarying = uv;
}

#else

void main()
{
	gl_Position = gl_Vertex;
	gl_TexCoord[0] = gl_MultiTexCoord0;
}

#endif
