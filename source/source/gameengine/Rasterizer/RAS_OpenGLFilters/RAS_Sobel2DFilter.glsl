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

	vec4 horizEdge = samples[2] + (2.0*samples[5]) + samples[8] -
	        (samples[0] + (2.0*samples[3]) + samples[6]);

	vec4 vertEdge = samples[0] + (2.0*samples[1]) + samples[2] -
	        (samples[6] + (2.0*samples[7]) + samples[8]);

	fragColor.rgb = sqrt((horizEdge.rgb * horizEdge.rgb) +
	                        (vertEdge.rgb * vertEdge.rgb));
	fragColor.a = 1.0;
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

	vec4 horizEdge = samples[2] + (2.0*samples[5]) + samples[8] -
	        (samples[0] + (2.0*samples[3]) + samples[6]);

	vec4 vertEdge = samples[0] + (2.0*samples[1]) + samples[2] -
	        (samples[6] + (2.0*samples[7]) + samples[8]);

	gl_FragColor.rgb = sqrt((horizEdge.rgb * horizEdge.rgb) +
	                        (vertEdge.rgb * vertEdge.rgb));
	gl_FragColor.a = 1.0;
}

#endif
