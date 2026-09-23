uniform sampler2D bgl_RenderedTexture;

#if __VERSION__ >= 130

in vec2 texCoordVarying;
layout(location = 0) out vec4 fragColor;

void main(void)
{
	vec4 texcolor = texture(bgl_RenderedTexture, texCoordVarying);
	float gray = dot(texcolor.rgb, vec3(0.299, 0.587, 0.114));
	fragColor = vec4(gray, gray, gray, texcolor.a);
}

#else

void main(void)
{
	vec4 texcolor = texture2D(bgl_RenderedTexture, gl_TexCoord[0].st);
	float gray = dot(texcolor.rgb, vec3(0.299, 0.587, 0.114));
	gl_FragColor = vec4(gray, gray, gray, texcolor.a);
}

#endif
