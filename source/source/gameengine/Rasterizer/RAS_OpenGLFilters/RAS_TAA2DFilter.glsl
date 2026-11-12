/* Temporal anti-aliasing (docs/plano-taa.md, etapa 1). Full resolution, after Tonemap and
 * before FXAA / camera lens. The scene is drawn with a sub-pixel jitter that changes every
 * frame (Halton 2,3); this pass blends the jittered frame into the history it keeps
 * (RAS_2DFilterManager copies the output of this pass after it runs).
 *
 *  - reprojection by the depth (closest depth of the 3x3, sharper silhouettes) with the
 *    view-projection the history was drawn with; both jitters removed from the motion;
 *  - history read with a 5 tap Catmull-Rom, so it does not blur over the frames;
 *  - history clipped to the variance box of the 3x3 current texels in YCoCg (no ghosting);
 *  - more weight to the current frame when the pixel moves;
 *  - luma weighted blend (less flicker on small bright details);
 *  - optional sharpen of the current sample (ge_TAAParams.y).
 *
 * Etapa 2: with TAA_VELOCITY_SLOT (RAS_2DFilterManager::EnsureTaaFilter), opaque object
 * materials write where each pixel was last frame (world offset, alpha 1 = valid) into that
 * attachment; it is added to the world position before the reprojection, so a car seen from
 * behind stays sharp. Pixels without it (sky, transparent, instanced, batched, skinned shape)
 * keep the camera only reprojection.
 *
 * Etapa 3 (docs/plano-opensource.md item 3, proof of concept, RANGE_TAAU): with ge_TAAUpscale.zw
 * set, this pass is the last one and draws at the window size from the reduced render. Each window
 * pixel gathers the 3x3 jittered render texels around it, weighted by their distance to it
 * (the jitter moves them over the frames), and blends into a window size history. Ideas from
 * AMD FSR 2 (MIT): reconstruction weighted by the sample distance, closest depth for the motion. */

#ifdef USE_CORE_PROFILE
in vec2 texCoordVarying;

out vec4 fragColor;
  #define gl_FragColor fragColor
#endif

uniform sampler2D bgl_RenderedTexture;
uniform sampler2D bgl_DepthTexture;
uniform sampler2D ge_TAAHistory;
uniform mat4 ge_TAAHistoryViewProj;
/// xy: jitter of this frame, zw: jitter of the history, in pixels.
uniform vec4 ge_TAAJitter;
/// x: history valid, y: sharpen, z: weight of the current frame when still, w: when moving.
uniform vec4 ge_TAAParams;

uniform mat4 unfinvviewmat;
uniform mat4 unfinvprojmat;

#ifdef TAA_VELOCITY_SLOT
uniform sampler2D bgl_DataTextures[7];
/// 1 when the motion attachment exists in this frame buffer.
uniform float ge_TAAVelocity;
#endif

/// Temporal upscaling: xy render (input) size, zw window (output) size; zw zero when off.
uniform vec4 ge_TAAUpscale;

vec3 RGBToYCoCg(vec3 c)
{
	return vec3(0.25 * c.r + 0.5 * c.g + 0.25 * c.b,
	            0.5 * c.r - 0.5 * c.b,
	            -0.25 * c.r + 0.5 * c.g - 0.25 * c.b);
}

vec3 YCoCgToRGB(vec3 c)
{
	return vec3(c.x + c.y - c.z, c.x + c.z, c.x - c.y - c.z);
}

vec3 FetchYCoCg(ivec2 texel, ivec2 size)
{
	return RGBToYCoCg(texelFetch(bgl_RenderedTexture, clamp(texel, ivec2(0), size - 1), 0).rgb);
}

/* 5 tap Catmull-Rom (bilinear taps at the right offsets, corners dropped). */
vec3 SampleHistory(vec2 uv, vec2 texSize)
{
	vec2 samplePos = uv * texSize;
	vec2 tc1 = floor(samplePos - 0.5) + 0.5;
	vec2 f = samplePos - tc1;
	vec2 w0 = f * (-0.5 + f * (1.0 - 0.5 * f));
	vec2 w1 = 1.0 + f * f * (-2.5 + 1.5 * f);
	vec2 w2 = f * (0.5 + f * (2.0 - 1.5 * f));
	vec2 w3 = f * f * (-0.5 + 0.5 * f);
	vec2 w12 = w1 + w2;
	vec2 tc0 = (tc1 - 1.0) / texSize;
	vec2 tc3 = (tc1 + 2.0) / texSize;
	vec2 tc12 = (tc1 + w2 / w12) / texSize;

	vec3 result = texture(ge_TAAHistory, vec2(tc12.x, tc0.y)).rgb * (w12.x * w0.y) +
	              texture(ge_TAAHistory, vec2(tc0.x, tc12.y)).rgb * (w0.x * w12.y) +
	              texture(ge_TAAHistory, tc12).rgb * (w12.x * w12.y) +
	              texture(ge_TAAHistory, vec2(tc3.x, tc12.y)).rgb * (w3.x * w12.y) +
	              texture(ge_TAAHistory, vec2(tc12.x, tc3.y)).rgb * (w12.x * w3.y);
	float weight = w12.x * w0.y + w0.x * w12.y + w12.x * w12.y + w3.x * w12.y + w12.x * w3.y;
	return max(result / weight, vec3(0.0));
}

/* Clip the history toward the box center instead of clamping each channel: keeps its hue. */
vec3 ClipToBox(vec3 history, vec3 boxMin, vec3 boxMax)
{
	vec3 center = 0.5 * (boxMax + boxMin);
	vec3 extents = 0.5 * (boxMax - boxMin) + 1e-5;
	vec3 offset = history - center;
	vec3 ratio = abs(offset / extents);
	float m = max(ratio.x, max(ratio.y, ratio.z));
	return (m > 1.0) ? center + offset / m : history;
}

/* World position of a render texel at the given depth (this frame's jittered projection), moved
 * to where it was last frame by the motion attachment when there is one. */
vec4 WorldOfTexel(ivec2 texel, float depth, vec2 texSize, ivec2 size)
{
	vec2 depthUV = (vec2(texel) + 0.5) / texSize;
	vec4 view = unfinvprojmat * vec4(depthUV * 2.0 - 1.0, depth * 2.0 - 1.0, 1.0);
	view /= view.w;
	vec4 world = unfinvviewmat * view;
#ifdef TAA_VELOCITY_SLOT
	if (ge_TAAVelocity > 0.5) {
		vec4 offset = texelFetch(bgl_DataTextures[TAA_VELOCITY_SLOT - 1], clamp(texel, ivec2(0), size - 1), 0);
		if (offset.a > 0.01) {
			world.xyz += offset.xyz / offset.a;
		}
	}
#endif
	return world;
}

void UpscaleMain()
{
	ivec2 size = textureSize(bgl_RenderedTexture, 0);
	vec2 inSize = vec2(size);
	vec2 outSize = ge_TAAUpscale.zw;
	vec2 uv = gl_FragCoord.xy / outSize;
	/* Where this window pixel falls among the render texels: texel k (center k + 0.5) holds the
	 * scene at k + 0.5 - jitter, so the jittered position is the plain one plus the jitter. */
	vec2 inPos = uv * inSize + ge_TAAJitter.xy;
	ivec2 base = ivec2(floor(inPos));

	vec3 sum = vec3(0.0);
	float weightSum = 0.0;
	float weightMax = 0.0;
	vec3 m1 = vec3(0.0);
	vec3 m2 = vec3(0.0);
	vec3 boxMin = vec3(1e9);
	vec3 boxMax = vec3(-1e9);
	float closestDepth = 1.0;
	ivec2 closestTexel = clamp(base, ivec2(0), size - 1);
	float alpha0;
	for (int y = -1; y <= 1; y++) {
		for (int x = -1; x <= 1; x++) {
			ivec2 texel = base + ivec2(x, y);
			ivec2 inside = clamp(texel, ivec2(0), size - 1);
			vec3 c = FetchYCoCg(texel, size);
			/* Gaussian close to a Blackman-Harris of radius 1 window pixel: measured in window
			 * pixels, so a render texel only counts near where it lands (the jitter moves it over
			 * the frames and the history fills the rest). */
			vec2 d = (vec2(texel) + 0.5 - inPos) * (outSize / inSize);
			float w = exp(-2.29 * dot(d, d));
			sum += c * w;
			weightSum += w;
			weightMax = max(weightMax, w);
			m1 += c;
			m2 += c * c;
			boxMin = min(boxMin, c);
			boxMax = max(boxMax, c);
			float depth = texelFetch(bgl_DepthTexture, inside, 0).x;
			if (depth < closestDepth) {
				closestDepth = depth;
				closestTexel = inside;
			}
		}
	}
	alpha0 = texelFetch(bgl_RenderedTexture, clamp(base, ivec2(0), size - 1), 0).a;
	vec3 current = sum / max(weightSum, 1e-5);

	if (ge_TAAParams.x < 0.5) {
		gl_FragColor = vec4(YCoCgToRGB(current), alpha0);
		return;
	}

	vec4 prevClip = ge_TAAHistoryViewProj * WorldOfTexel(closestTexel, closestDepth, inSize, size);
	if (prevClip.w <= 0.0) {
		gl_FragColor = vec4(YCoCgToRGB(current), alpha0);
		return;
	}
	/* Motion in render texels without the jitters, then the same fraction of the window. */
	vec2 prevPixel = (prevClip.xy / prevClip.w * 0.5 + 0.5) * inSize - ge_TAAJitter.zw;
	vec2 curPixel = (vec2(closestTexel) + 0.5) - ge_TAAJitter.xy;
	vec2 motion = (prevPixel - curPixel) / inSize;
	vec2 prevUV = uv + motion;
	if (any(lessThan(prevUV, vec2(0.0))) || any(greaterThan(prevUV, vec2(1.0)))) {
		gl_FragColor = vec4(YCoCgToRGB(current), alpha0);
		return;
	}

	vec3 history = RGBToYCoCg(SampleHistory(prevUV, outSize));
	vec3 mean = m1 / 9.0;
	vec3 sigma = sqrt(max(m2 / 9.0 - mean * mean, vec3(0.0)));
	history = ClipToBox(history, max(boxMin, mean - sigma), min(boxMax, mean + sigma));

	/* A render sample landing right on this window pixel counts fully; one half a texel away
	 * counts about a third: the history fills the window pixels between the samples. */
	float speed = clamp(length(motion * outSize) / 4.0, 0.0, 1.0);
	float alpha = mix(ge_TAAParams.z, ge_TAAParams.w, speed) * weightMax;

	float wCurrent = alpha / (1.0 + current.x);
	float wHistory = (1.0 - alpha) / (1.0 + history.x);
	vec3 result = (current * wCurrent + history * wHistory) / max(wCurrent + wHistory, 1e-5);
	gl_FragColor = vec4(max(YCoCgToRGB(result), vec3(0.0)), alpha0);
}

void main()
{
	if (ge_TAAUpscale.z > 0.5) {
		UpscaleMain();
		return;
	}
	ivec2 size = textureSize(bgl_RenderedTexture, 0);
	ivec2 texel = ivec2(gl_FragCoord.xy);
	vec2 texSize = vec2(size);
	vec2 uv = (vec2(texel) + 0.5) / texSize;

	vec4 currentFull = texelFetch(bgl_RenderedTexture, texel, 0);
	vec3 current = RGBToYCoCg(currentFull.rgb);

	/* 3x3 neighborhood: moments for the variance box, cross average for the sharpen and the
	 * closest depth for the reprojection. */
	vec3 m1 = vec3(0.0);
	vec3 m2 = vec3(0.0);
	vec3 boxMin = current;
	vec3 boxMax = current;
	vec3 crossSum = vec3(0.0);
	float closestDepth = 1.0;
	ivec2 closestOffset = ivec2(0);
	for (int y = -1; y <= 1; y++) {
		for (int x = -1; x <= 1; x++) {
			ivec2 offset = ivec2(x, y);
			vec3 c = (x == 0 && y == 0) ? current : FetchYCoCg(texel + offset, size);
			m1 += c;
			m2 += c * c;
			boxMin = min(boxMin, c);
			boxMax = max(boxMax, c);
			if ((x == 0) != (y == 0)) {
				crossSum += c;
			}
			float d = texelFetch(bgl_DepthTexture, clamp(texel + offset, ivec2(0), size - 1), 0).x;
			if (d < closestDepth) {
				closestDepth = d;
				closestOffset = offset;
			}
		}
	}

	float sharpen = ge_TAAParams.y;
	if (sharpen > 0.0) {
		current = current + (current - crossSum * 0.25) * sharpen;
		current.x = max(current.x, 0.0);
	}

	if (ge_TAAParams.x < 0.5) {
		gl_FragColor = vec4(YCoCgToRGB(current), currentFull.a);
		return;
	}

	/* World position of the closest texel, drawn with this frame's (jittered) projection. */
	vec2 depthUV = (vec2(texel + closestOffset) + 0.5) / texSize;
	vec4 view = unfinvprojmat * vec4(depthUV * 2.0 - 1.0, closestDepth * 2.0 - 1.0, 1.0);
	view /= view.w;
	vec4 world = unfinvviewmat * view;
#ifdef TAA_VELOCITY_SLOT
	if (ge_TAAVelocity > 0.5) {
		/* MSAA resolve averages valid and empty samples: divide by the coverage. */
		vec4 offset = texelFetch(bgl_DataTextures[TAA_VELOCITY_SLOT - 1], clamp(texel + closestOffset, ivec2(0), size - 1), 0);
		if (offset.a > 0.01) {
			world.xyz += offset.xyz / offset.a;
		}
	}
#endif
	vec4 prevClip = ge_TAAHistoryViewProj * world;
	if (prevClip.w <= 0.0) {
		gl_FragColor = vec4(YCoCgToRGB(current), currentFull.a);
		return;
	}
	/* Motion without the jitters: positions on screen as if both frames had none. */
	vec2 prevPixel = (prevClip.xy / prevClip.w * 0.5 + 0.5) * texSize - ge_TAAJitter.zw;
	vec2 curPixel = depthUV * texSize - ge_TAAJitter.xy;
	vec2 motion = prevPixel - curPixel;
	vec2 prevUV = uv + motion / texSize;
	if (any(lessThan(prevUV, vec2(0.0))) || any(greaterThan(prevUV, vec2(1.0)))) {
		gl_FragColor = vec4(YCoCgToRGB(current), currentFull.a);
		return;
	}

	vec3 history = RGBToYCoCg(SampleHistory(prevUV, texSize));

	/* Variance box (gamma 1), inside the min/max box. */
	vec3 mean = m1 / 9.0;
	vec3 sigma = sqrt(max(m2 / 9.0 - mean * mean, vec3(0.0)));
	vec3 vMin = max(boxMin, mean - sigma);
	vec3 vMax = min(boxMax, mean + sigma);
	history = ClipToBox(history, vMin, vMax);

	/* Still pixels converge (weight z), moving ones keep closer to the current frame (w). */
	float speed = clamp(length(motion) / 4.0, 0.0, 1.0);
	float alpha = mix(ge_TAAParams.z, ge_TAAParams.w, speed);

	float wCurrent = alpha / (1.0 + current.x);
	float wHistory = (1.0 - alpha) / (1.0 + history.x);
	vec3 result = (current * wCurrent + history * wHistory) / max(wCurrent + wHistory, 1e-5);

	gl_FragColor = vec4(max(YCoCgToRGB(result), vec3(0.0)), currentFull.a);
}
