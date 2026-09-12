uniform sampler2D bgl_RenderedTexture;
uniform vec2 bgl_TextureCoordinateOffset[9];

#if __VERSION__ >= 130

in vec2 texCoordVarying;
layout(location = 0) out vec4 fragColor;

void main(void)
{
	vec4 samples[9];

	for (int i = 0; i < 9; i++)
	{
		samples[i] = texture(bgl_RenderedTexture,
		                      texCoordVarying + bgl_TextureCoordinateOffset[i]);
	}

	fragColor = (samples[4] * 9.0) -
	        (samples[0] + samples[1] + samples[2] +
	         samples[3] + samples[5] +
	         samples[6] + samples[7] + samples[8]);
}

#else

void main(void)
{
	vec4 samples[9];

	for (int i = 0; i < 9; i++)
	{
		samples[i] = texture2D(bgl_RenderedTexture,
		                      gl_TexCoord[0].st + bgl_TextureCoordinateOffset[i]);
	}

	gl_FragColor = (samples[4] * 9.0) -
	        (samples[0] + samples[1] + samples[2] +
	         samples[3] + samples[5] +
	         samples[6] + samples[7] + samples[8]);
}

#endif
