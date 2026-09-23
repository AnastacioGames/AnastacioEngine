uniform sampler2D bgl_RenderedTexture;

#if __VERSION__ >= 130

in vec2 texCoordVarying;
layout(location = 0) out vec4 fragColor;

void main(void)
{
	vec4 texcolor = texture(bgl_RenderedTexture, texCoordVarying);
	fragColor.rgb = 1.0 - texcolor.rgb;
	fragColor.a = texcolor.a;
}

#else

void main(void)
{
	vec4 texcolor = texture2D(bgl_RenderedTexture, gl_TexCoord[0].st);
	gl_FragColor.rgb = 1.0 - texcolor.rgb;
	gl_FragColor.a = texcolor.a;
}

#endif
