/* Shared temporal resolve (Fase 2 of docs/plano-efeitos-render.md). Runs on the low resolution
 * buffer of an effect (Volumetric Fog, SSGI...), right after the pass that traced it, into its own
 * off screen of the same size; the manager then keeps that output as the history of the next
 * frame (RAS_2DFilterManager::RenderTemporalResolve).
 *
 *  - reconstruct the world position of the texel from the scene depth (inverse view/projection);
 *  - reproject it with the view-projection the history was drawn with;
 *  - reject it off screen or on disocclusion (relative linear depth difference > TEMPORAL_DEPTH_TOL);
 *  - clamp the history to the min/max of the 3x3 current texels (no ghosting on moving lights);
 *  - blend with TEMPORAL_ALPHA (weight of the current frame).
 *
 * Defines given by the effect: TEMPORAL_ALPHA (default 0.1), TEMPORAL_DEPTH_TOL (0.03). */

#ifndef TEMPORAL_ALPHA
#define TEMPORAL_ALPHA 0.1
#endif
#ifndef TEMPORAL_DEPTH_TOL
#define TEMPORAL_DEPTH_TOL 0.03
#endif

#ifdef USE_CORE_PROFILE
in vec2 texCoordVarying;

out vec4 fragColor;
  #define gl_FragColor fragColor
#endif

uniform sampler2D bgl_DepthTexture;
/// Current (noisy) effect buffer, same size as this pass' off screen.
uniform sampler2D ge_TemporalCurrent;
uniform sampler2D ge_TemporalHistory;
uniform sampler2D ge_TemporalHistoryDepth;
uniform float ge_TemporalHistoryValid;
uniform mat4 ge_TemporalHistoryViewProj;

uniform mat4 unfinvviewmat;
uniform mat4 unfinvprojmat;

float temporalLinearDepth(float depth)
{
	vec4 v = unfinvprojmat * vec4(0.0, 0.0, depth * 2.0 - 1.0, 1.0);
	return -v.z / v.w;
}

void main()
{
	ivec2 size = textureSize(ge_TemporalCurrent, 0);
	ivec2 texel = ivec2(gl_FragCoord.xy);
	vec2 uv = (vec2(texel) + 0.5) / vec2(size);

	vec4 current = texelFetch(ge_TemporalCurrent, texel, 0);
	if (ge_TemporalHistoryValid < 0.5) {
		gl_FragColor = current;
		return;
	}

	/* 3x3 neighborhood box of the current buffer. */
	vec4 nmin = current;
	vec4 nmax = current;
	for (int y = -1; y <= 1; y++) {
		for (int x = -1; x <= 1; x++) {
			if (x == 0 && y == 0) {
				continue;
			}
			ivec2 t = clamp(texel + ivec2(x, y), ivec2(0), size - 1);
			vec4 c = texelFetch(ge_TemporalCurrent, t, 0);
			nmin = min(nmin, c);
			nmax = max(nmax, c);
		}
	}

	/* The effect traced this texel with the depth at its center (same as the image passes). */
	float depth = texture(bgl_DepthTexture, uv).x;
	vec4 view = unfinvprojmat * vec4(uv * 2.0 - 1.0, depth * 2.0 - 1.0, 1.0);
	view /= view.w;
	vec4 world = unfinvviewmat * view;
	vec4 prevClip = ge_TemporalHistoryViewProj * world;
	if (prevClip.w <= 0.0) {
		gl_FragColor = current;
		return;
	}
	vec3 prevNdc = prevClip.xyz / prevClip.w;
	vec2 prevUv = prevNdc.xy * 0.5 + 0.5;
	if (any(lessThan(prevUv, vec2(0.0))) || any(greaterThan(prevUv, vec2(1.0)))) {
		gl_FragColor = current;
		return;
	}

	/* Disocclusion: what the history saw there must be the same surface (sky stays sky). */
	float histDepth = texture(ge_TemporalHistoryDepth, prevUv).x;
	if (depth < 1.0 || histDepth < 1.0) {
		float expected = temporalLinearDepth(clamp(prevNdc.z * 0.5 + 0.5, 0.0, 1.0));
		float seen = temporalLinearDepth(histDepth);
		if (abs(seen - expected) > TEMPORAL_DEPTH_TOL * max(expected, 1e-3)) {
			gl_FragColor = current;
			return;
		}
	}

#ifdef TEMPORAL_HIT_REPROJECT
	/* SSR: the reflection moves with the reflected (virtual) point, not with the surface. The
	 * effect stores a = 1 / (1 + camera -> surface -> hit length), 0 for the sky (infinity); the
	 * virtual point lies on the view ray of the texel at that distance. */
	{
		vec3 dirView = normalize(view.xyz);
		vec4 virt = (current.a > 1e-4) ? vec4(dirView * (1.0 / current.a - 1.0), 1.0) : vec4(dirView, 0.0);
		vec4 vClip = ge_TemporalHistoryViewProj * (unfinvviewmat * virt);
		if (vClip.w > 0.0) {
			vec2 vUv = vClip.xy / vClip.w * 0.5 + 0.5;
			if (all(greaterThanEqual(vUv, vec2(0.0))) && all(lessThanEqual(vUv, vec2(1.0)))) {
				prevUv = vUv;
			}
		}
	}
#endif
	vec4 history = clamp(texture(ge_TemporalHistory, prevUv), nmin, nmax);
	gl_FragColor = mix(history, current, TEMPORAL_ALPHA);
#ifdef TEMPORAL_HIT_REPROJECT
	gl_FragColor.a = current.a;
#endif
}
