#if defined(ANAGLYPH) || defined(STIPPLE)
uniform sampler2D lefteyetex;
uniform sampler2D righteyetex;
#else
uniform sampler2D colortex;
#  ifdef DEPTH
uniform sampler2D depthtex;
#  endif
#endif

#ifdef LENS_DISTORT
uniform float lensk;
uniform float lensaspect;

/* Side by side: each half is one eye. Pre-distorts (barrel) so the lens pincushion cancels out.
 * Returns the source coordinate, or a negative x when it falls outside the eye's half. */
vec2 lens_source(vec2 co)
{
	float cx = (co.x < 0.5) ? 0.25 : 0.75;
	vec2 n = vec2((co.x - cx) * lensaspect, co.y - 0.5) * 2.0;
	n *= 1.0 + lensk * dot(n, n);
	vec2 s = vec2(cx + n.x / lensaspect * 0.5, 0.5 + n.y * 0.5);
	if (abs(s.x - cx) > 0.25 || abs(s.y - 0.5) > 0.5) {
		return vec2(-1.0, -1.0);
	}
	return s;
}
#endif

#ifdef STIPPLE
#define STIPPLE_COLUMN 0
#define STIPPLE_ROW 1

uniform int stippleid;
#endif

#if __VERSION__ >= 130

in vec2 texCoordVarying;
layout(location = 0) out vec4 fragColor;

void main(void)
{
	vec2 co = texCoordVarying;
#ifdef STIPPLE
	if (stippleid == STIPPLE_ROW) {
		int result = int(mod(gl_FragCoord.y, 2.0));
		if (result != 0) {
			fragColor = texture(lefteyetex, co);
		}
		else {
			fragColor = texture(righteyetex, co);
		}
	}
	else if (stippleid == STIPPLE_COLUMN) {
		int result = int(mod(gl_FragCoord.x, 2.0));
		if (result == 0) {
			fragColor = texture(lefteyetex, co);
		}
		else {
			fragColor = texture(righteyetex, co);
		}
	}
#elif defined(LENS_DISTORT)
	vec2 ls = lens_source(co);
	fragColor = (ls.x < 0.0) ? vec4(0.0, 0.0, 0.0, 1.0) : texture(colortex, ls);
#elif defined(ANAGLYPH)
	fragColor = vec4(texture(lefteyetex, co).r, texture(righteyetex, co).gb, 1.0);
#else
	fragColor = texture(colortex, co);
#  ifdef DEPTH
	gl_FragDepth = texture(depthtex, co).x;
#  endif
#endif
}

#else

void main()
{
	vec2 co = gl_TexCoord[0].xy;
#ifdef STIPPLE
	if (stippleid == STIPPLE_ROW) {
		int result = int(mod(gl_FragCoord.y, 2.0));
		if (result != 0) {
			gl_FragData[0] = texture2D(lefteyetex, co);
		}
		else {
			gl_FragData[0] = texture2D(righteyetex, co);
		}
	}
	else if (stippleid == STIPPLE_COLUMN) {
		int result = int(mod(gl_FragCoord.x, 2.0));
		if (result == 0) {
			gl_FragData[0] = texture2D(lefteyetex, co);
		}
		else {
			gl_FragData[0] = texture2D(righteyetex, co);
		}
	}
#elif defined(LENS_DISTORT)
	vec2 ls = lens_source(co);
	gl_FragData[0] = (ls.x < 0.0) ? vec4(0.0, 0.0, 0.0, 1.0) : texture2D(colortex, ls);
#elif defined(ANAGLYPH)
	gl_FragData[0] = vec4(texture2D(lefteyetex, co).r, texture2D(righteyetex, co).gb, 1.0);
#else
	gl_FragData[0] = texture2D(colortex, co);
#  ifdef DEPTH
	gl_FragDepth = texture2D(depthtex, co).x;
#  endif
#endif
}

#endif
