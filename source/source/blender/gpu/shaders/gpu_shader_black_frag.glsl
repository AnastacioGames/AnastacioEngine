#if __VERSION__ >= 130

layout(location = 0) out vec4 fragColor;

void main()
{
	fragColor = vec4(0.0, 0.0, 0.0, 1.0);
}

#else

void main()
{
	gl_FragData[0] = vec4(0.0, 0.0, 0.0, 1.0);
}

#endif
