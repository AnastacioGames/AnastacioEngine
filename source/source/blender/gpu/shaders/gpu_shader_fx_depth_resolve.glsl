uniform sampler2D depthbuffer;

#if __VERSION__ >= 130

in vec4 uvcoordsvar;

void main(void)
{
	float depth = texture(depthbuffer, uvcoordsvar.xy).r;

	/* XRay background, discard */
	if (depth >= 1.0) {
		discard;
	}

	gl_FragDepth = depth;
}

#else

varying vec4 uvcoordsvar;

void main(void)
{
	float depth = texture2D(depthbuffer, uvcoordsvar.xy).r;

	/* XRay background, discard */
	if (depth >= 1.0) {
		discard;
	}

	gl_FragDepth = depth;
}

#endif
