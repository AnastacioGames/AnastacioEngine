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
#  if __VERSION__ >= 130
#    define TEXTURE texture
#  else
#    define TEXTURE texture2D
#  endif
uniform float lensk;
uniform float lensaspect;
uniform float vignette; /* comfort vignette 0..1, closes the edges of each eye */
uniform float lensca; /* chromatic aberration correction: red/blue radial scale offset, 0 = off */

/* Brightness kept at this point of the eye: the dark ring grows toward the center with the vignette. */
float lens_vignette(vec2 co)
{
	if (vignette <= 0.0) {
		return 1.0;
	}
	float cx = (co.x < 0.5) ? 0.25 : 0.75;
	float r = length(vec2((co.x - cx) * lensaspect, co.y - 0.5) * 2.0);
	float inner = mix(1.2, 0.25, vignette);
	return 1.0 - smoothstep(inner, inner + 0.45, r);
}

/* Side by side: each half is one eye. Pre-distorts (barrel) so the lens pincushion cancels out.
 * Returns the source coordinate, or a negative x when it falls outside the eye's half. */
vec2 lens_source(vec2 co, float scale)
{
	float cx = (co.x < 0.5) ? 0.25 : 0.75;
	vec2 n = vec2((co.x - cx) * lensaspect, co.y - 0.5) * 2.0;
	n *= (1.0 + lensk * dot(n, n)) * scale;
	vec2 s = vec2(cx + n.x / lensaspect * 0.5, 0.5 + n.y * 0.5);
	if (abs(s.x - cx) > 0.25 || abs(s.y - 0.5) > 0.5) {
		return vec2(-1.0, -1.0);
	}
	return s;
}

/* The lens bends blue more than red: sample red slightly inside and blue slightly outside so the
 * colored fringes at the edges cancel out. */
vec4 lens_color(vec2 co)
{
	vec2 g = lens_source(co, 1.0);
	if (g.x < 0.0) {
		return vec4(0.0, 0.0, 0.0, 1.0);
	}
	vec4 color = TEXTURE(colortex, g);
	if (lensca > 0.0) {
		vec2 r = lens_source(co, 1.0 - lensca);
		vec2 b = lens_source(co, 1.0 + lensca);
		color.r = (r.x < 0.0) ? 0.0 : TEXTURE(colortex, r).r;
		color.b = (b.x < 0.0) ? 0.0 : TEXTURE(colortex, b).b;
	}
	color.rgb *= lens_vignette(co);
	return color;
}
#endif

#if defined(FSR_RCAS) && __VERSION__ >= 130
/* AMD FidelityFX Super Resolution 1, RCAS (robust contrast adaptive sharpening), MIT license.
 * Runs on the full size EASU output. */
uniform vec4 fsrviewport; /* output x, y, width, height in pixels */
uniform float fsrsharp; /* exp2(-stops), 1.0 = strongest */

vec4 rcas_color(void)
{
	ivec2 size = textureSize(colortex, 0);
	ivec2 p = ivec2(gl_FragCoord.xy - fsrviewport.xy);
	vec3 b = texelFetch(colortex, clamp(p + ivec2(0, 1), ivec2(0), size - 1), 0).rgb;
	vec3 d = texelFetch(colortex, clamp(p + ivec2(-1, 0), ivec2(0), size - 1), 0).rgb;
	vec4 e4 = texelFetch(colortex, clamp(p, ivec2(0), size - 1), 0);
	vec3 e = e4.rgb;
	vec3 f = texelFetch(colortex, clamp(p + ivec2(1, 0), ivec2(0), size - 1), 0).rgb;
	vec3 h = texelFetch(colortex, clamp(p + ivec2(0, -1), ivec2(0), size - 1), 0).rgb;

	vec3 mn4 = min(min(b, d), min(f, h));
	vec3 mx4 = max(max(b, d), max(f, h));
	vec3 hitMin = min(mn4, e) / (4.0 * mx4 + 1e-5);
	vec3 hitMax = (1.0 - max(mx4, e)) / (4.0 * mn4 - 4.0 - 1e-5);
	vec3 lobeRGB = max(-hitMin, hitMax);
	float lobe = max(-0.1875, min(max(lobeRGB.r, max(lobeRGB.g, lobeRGB.b)), 0.0)) * fsrsharp;
	vec3 c = (lobe * (b + d + f + h) + e) / (4.0 * lobe + 1.0);
	return vec4(clamp(c, 0.0, 1.0), e4.a);
}
#endif

#if defined(FSR_EASU) && __VERSION__ >= 130
/* AMD FidelityFX Super Resolution 1, EASU (edge adaptive upscale), MIT license, ported to plain
 * texelFetch (12 taps, no textureGather) so it also runs on GLSL ES 3.00 (Web). */
uniform vec4 fsrviewport; /* output x, y, width, height in pixels */

vec3 easu_fetch(ivec2 p, ivec2 size)
{
	return texelFetch(colortex, clamp(p, ivec2(0), size - 1), 0).rgb;
}

float easu_luma(vec3 c)
{
	return c.b * 0.5 + (c.r * 0.5 + c.g);
}

void easu_set(inout vec2 dir, inout float len, float w, float lA, float lB, float lC, float lD, float lE)
{
	float dc = lD - lC;
	float cb = lC - lB;
	float lenX = max(abs(dc), abs(cb));
	lenX = (lenX > 0.0) ? 1.0 / lenX : 0.0;
	float dirX = lD - lB;
	dir.x += dirX * w;
	lenX = clamp(abs(dirX) * lenX, 0.0, 1.0);
	len += lenX * lenX * w;

	float ec = lE - lC;
	float ca = lC - lA;
	float lenY = max(abs(ec), abs(ca));
	lenY = (lenY > 0.0) ? 1.0 / lenY : 0.0;
	float dirY = lE - lA;
	dir.y += dirY * w;
	lenY = clamp(abs(dirY) * lenY, 0.0, 1.0);
	len += lenY * lenY * w;
}

void easu_tap(inout vec3 aC, inout float aW, vec2 off, vec2 dir, vec2 len2, float lob, float clp, vec3 c)
{
	vec2 v = vec2(off.x * dir.x + off.y * dir.y, off.x * (-dir.y) + off.y * dir.x) * len2;
	float d2 = min(v.x * v.x + v.y * v.y, clp);
	float wB = 2.0 / 5.0 * d2 - 1.0;
	float wA = lob * d2 - 1.0;
	wB *= wB;
	wA *= wA;
	wB = 25.0 / 16.0 * wB - (25.0 / 16.0 - 1.0);
	float w = wB * wA;
	aC += c * w;
	aW += w;
}

vec4 easu_color(void)
{
	ivec2 size = textureSize(colortex, 0);
	vec2 scale = vec2(size) / fsrviewport.zw;
	vec2 pp = (gl_FragCoord.xy - fsrviewport.xy) * scale - 0.5;
	vec2 fp = floor(pp);
	pp -= fp;
	ivec2 p = ivec2(fp);

	vec3 b = easu_fetch(p + ivec2(0, -1), size);
	vec3 c = easu_fetch(p + ivec2(1, -1), size);
	vec3 e = easu_fetch(p + ivec2(-1, 0), size);
	vec3 f = easu_fetch(p, size);
	vec3 g = easu_fetch(p + ivec2(1, 0), size);
	vec3 h = easu_fetch(p + ivec2(2, 0), size);
	vec3 i = easu_fetch(p + ivec2(-1, 1), size);
	vec3 j = easu_fetch(p + ivec2(0, 1), size);
	vec3 k = easu_fetch(p + ivec2(1, 1), size);
	vec3 l = easu_fetch(p + ivec2(2, 1), size);
	vec3 n = easu_fetch(p + ivec2(0, 2), size);
	vec3 o = easu_fetch(p + ivec2(1, 2), size);

	float bL = easu_luma(b), cL = easu_luma(c), eL = easu_luma(e), fL = easu_luma(f);
	float gL = easu_luma(g), hL = easu_luma(h), iL = easu_luma(i), jL = easu_luma(j);
	float kL = easu_luma(k), lL = easu_luma(l), nL = easu_luma(n), oL = easu_luma(o);

	vec2 dir = vec2(0.0);
	float len = 0.0;
	easu_set(dir, len, (1.0 - pp.x) * (1.0 - pp.y), bL, eL, fL, gL, jL);
	easu_set(dir, len, pp.x * (1.0 - pp.y), cL, fL, gL, hL, kL);
	easu_set(dir, len, (1.0 - pp.x) * pp.y, fL, iL, jL, kL, nL);
	easu_set(dir, len, pp.x * pp.y, gL, jL, kL, lL, oL);

	float dirR = dot(dir, dir);
	bool zro = dirR < 1.0 / 32768.0;
	dirR = zro ? 1.0 : inversesqrt(dirR);
	dir.x = zro ? 1.0 : dir.x;
	dir *= dirR;
	len = len * 0.5;
	len *= len;
	float stretch = dot(dir, dir) / max(abs(dir.x), abs(dir.y));
	vec2 len2 = vec2(1.0 + (stretch - 1.0) * len, 1.0 - 0.5 * len);
	float lob = 0.5 + ((1.0 / 4.0 - 0.04) - 0.5) * len;
	float clp = 1.0 / lob;

	vec3 mn = min(min(f, g), min(j, k));
	vec3 mx = max(max(f, g), max(j, k));

	vec3 aC = vec3(0.0);
	float aW = 0.0;
	easu_tap(aC, aW, vec2(0.0, -1.0) - pp, dir, len2, lob, clp, b);
	easu_tap(aC, aW, vec2(1.0, -1.0) - pp, dir, len2, lob, clp, c);
	easu_tap(aC, aW, vec2(-1.0, 1.0) - pp, dir, len2, lob, clp, i);
	easu_tap(aC, aW, vec2(0.0, 1.0) - pp, dir, len2, lob, clp, j);
	easu_tap(aC, aW, vec2(0.0, 0.0) - pp, dir, len2, lob, clp, f);
	easu_tap(aC, aW, vec2(-1.0, 0.0) - pp, dir, len2, lob, clp, e);
	easu_tap(aC, aW, vec2(1.0, 1.0) - pp, dir, len2, lob, clp, k);
	easu_tap(aC, aW, vec2(2.0, 1.0) - pp, dir, len2, lob, clp, l);
	easu_tap(aC, aW, vec2(2.0, 0.0) - pp, dir, len2, lob, clp, h);
	easu_tap(aC, aW, vec2(1.0, 0.0) - pp, dir, len2, lob, clp, g);
	easu_tap(aC, aW, vec2(1.0, 2.0) - pp, dir, len2, lob, clp, o);
	easu_tap(aC, aW, vec2(0.0, 2.0) - pp, dir, len2, lob, clp, n);

	return vec4(min(mx, max(mn, aC / aW)), 1.0);
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
#elif defined(FSR_EASU)
	fragColor = easu_color();
#elif defined(FSR_RCAS)
	fragColor = rcas_color();
#elif defined(LENS_DISTORT)
	fragColor = lens_color(co);
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
	gl_FragData[0] = lens_color(co);
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
