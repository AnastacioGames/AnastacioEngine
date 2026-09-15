/**
FXAA 3.11-style edge-search antialiasing, adapted from the public reference
implementation described in NVIDIA's FXAA whitepaper (Timothy Lottes) and the
widely reused simplified GLSL port (e.g. Simon Rodriguez, "Implementing FXAA").
Replaces the previous 4-corner luma-only pass with proper edge detection,
orientation, and directional edge-length search for sharper diagonals.
*/

#define FXAA_EDGE_THRESHOLD_MIN 0.0312
#define FXAA_EDGE_THRESHOLD 0.125
#define FXAA_SUBPIX_TRIM_SCALE 1.0
#define FXAA_SEARCH_STEPS 10

// color buffer
uniform sampler2D colorbuffer;
uniform vec2 viewport_size; // Width, Height

// coordinates on framebuffer in normalized (0.0-1.0) uv space
in vec4 uvcoord;

#if __VERSION__ >= 130
layout(location = 0) out vec4 fragColor;
#define FINAL_COLOR fragColor
#define TEXTURE_LOD textureLod
#else
#define FINAL_COLOR gl_FragColor
#define TEXTURE_LOD texture2DLod
#endif

float rgb2luma(vec3 rgb)
{
	return dot(rgb, vec3(0.299, 0.587, 0.114));
}

vec4 AAPostFX(sampler2D tex, vec2 rcpRes, vec2 uv)
{
	vec4 texelCenter = TEXTURE_LOD(tex, uv, 0.0);
	vec3 colorCenter = texelCenter.rgb;
	float lumaCenter = rgb2luma(colorCenter);

	float lumaDown = rgb2luma(TEXTURE_LOD(tex, uv + vec2(0.0, -1.0) * rcpRes, 0.0).rgb);
	float lumaUp = rgb2luma(TEXTURE_LOD(tex, uv + vec2(0.0, 1.0) * rcpRes, 0.0).rgb);
	float lumaLeft = rgb2luma(TEXTURE_LOD(tex, uv + vec2(-1.0, 0.0) * rcpRes, 0.0).rgb);
	float lumaRight = rgb2luma(TEXTURE_LOD(tex, uv + vec2(1.0, 0.0) * rcpRes, 0.0).rgb);

	float lumaMin = min(lumaCenter, min(min(lumaDown, lumaUp), min(lumaLeft, lumaRight)));
	float lumaMax = max(lumaCenter, max(max(lumaDown, lumaUp), max(lumaLeft, lumaRight)));
	float lumaRange = lumaMax - lumaMin;

	if (lumaRange < max(FXAA_EDGE_THRESHOLD_MIN, lumaMax * FXAA_EDGE_THRESHOLD)) {
		return texelCenter;
	}

	float lumaDownLeft = rgb2luma(TEXTURE_LOD(tex, uv + vec2(-1.0, -1.0) * rcpRes, 0.0).rgb);
	float lumaUpRight = rgb2luma(TEXTURE_LOD(tex, uv + vec2(1.0, 1.0) * rcpRes, 0.0).rgb);
	float lumaUpLeft = rgb2luma(TEXTURE_LOD(tex, uv + vec2(-1.0, 1.0) * rcpRes, 0.0).rgb);
	float lumaDownRight = rgb2luma(TEXTURE_LOD(tex, uv + vec2(1.0, -1.0) * rcpRes, 0.0).rgb);

	float lumaDownUp = lumaDown + lumaUp;
	float lumaLeftRight = lumaLeft + lumaRight;

	float lumaLeftCorners = lumaDownLeft + lumaUpLeft;
	float lumaDownCorners = lumaDownLeft + lumaDownRight;
	float lumaRightCorners = lumaDownRight + lumaUpRight;
	float lumaUpCorners = lumaUpRight + lumaUpLeft;

	float edgeHorizontal = abs(-2.0 * lumaLeft + lumaLeftCorners) +
	                        abs(-2.0 * lumaCenter + lumaDownUp) * 2.0 +
	                        abs(-2.0 * lumaRight + lumaRightCorners);
	float edgeVertical = abs(-2.0 * lumaUp + lumaUpCorners) +
	                      abs(-2.0 * lumaCenter + lumaLeftRight) * 2.0 +
	                      abs(-2.0 * lumaDown + lumaDownCorners);

	bool isHorizontal = (edgeHorizontal >= edgeVertical);

	float luma1 = isHorizontal ? lumaDown : lumaLeft;
	float luma2 = isHorizontal ? lumaUp : lumaRight;
	float gradient1 = luma1 - lumaCenter;
	float gradient2 = luma2 - lumaCenter;

	bool is1Steepest = abs(gradient1) >= abs(gradient2);
	float gradientScaled = 0.25 * max(abs(gradient1), abs(gradient2));

	float stepLength = isHorizontal ? rcpRes.y : rcpRes.x;
	float lumaLocalAverage = 0.0;

	if (is1Steepest) {
		stepLength = -stepLength;
		lumaLocalAverage = 0.5 * (luma1 + lumaCenter);
	}
	else {
		lumaLocalAverage = 0.5 * (luma2 + lumaCenter);
	}

	vec2 currentUv = uv;
	if (isHorizontal) {
		currentUv.y += stepLength * 0.5;
	}
	else {
		currentUv.x += stepLength * 0.5;
	}

	vec2 offset = isHorizontal ? vec2(rcpRes.x, 0.0) : vec2(0.0, rcpRes.y);

	vec2 uv1 = currentUv - offset;
	vec2 uv2 = currentUv + offset;

	float lumaEnd1 = rgb2luma(TEXTURE_LOD(tex, uv1, 0.0).rgb) - lumaLocalAverage;
	float lumaEnd2 = rgb2luma(TEXTURE_LOD(tex, uv2, 0.0).rgb) - lumaLocalAverage;

	bool reached1 = abs(lumaEnd1) >= gradientScaled;
	bool reached2 = abs(lumaEnd2) >= gradientScaled;
	bool reachedBoth = reached1 && reached2;

	if (!reached1) { uv1 -= offset; }
	if (!reached2) { uv2 += offset; }

	if (!reachedBoth) {
		for (int i = 2; i < FXAA_SEARCH_STEPS; i++) {
			if (!reached1) {
				lumaEnd1 = rgb2luma(TEXTURE_LOD(tex, uv1, 0.0).rgb) - lumaLocalAverage;
			}
			if (!reached2) {
				lumaEnd2 = rgb2luma(TEXTURE_LOD(tex, uv2, 0.0).rgb) - lumaLocalAverage;
			}
			reached1 = abs(lumaEnd1) >= gradientScaled;
			reached2 = abs(lumaEnd2) >= gradientScaled;
			reachedBoth = reached1 && reached2;

			if (!reached1) { uv1 -= offset; }
			if (!reached2) { uv2 += offset; }

			if (reachedBoth) { break; }
		}
	}

	float distance1 = isHorizontal ? (uv.x - uv1.x) : (uv.y - uv1.y);
	float distance2 = isHorizontal ? (uv2.x - uv.x) : (uv2.y - uv.y);

	bool isDirection1 = distance1 < distance2;
	float distanceFinal = min(distance1, distance2);
	float edgeThickness = distance1 + distance2;

	float pixelOffset = -distanceFinal / edgeThickness + 0.5;

	bool isLumaCenterSmaller = lumaCenter < lumaLocalAverage;
	bool correctVariation = ((isDirection1 ? lumaEnd1 : lumaEnd2) < 0.0) != isLumaCenterSmaller;

	float finalOffset = correctVariation ? pixelOffset : 0.0;

	float lumaAverage = (1.0 / 12.0) * (2.0 * (lumaDownUp + lumaLeftRight) + lumaLeftCorners + lumaRightCorners);
	float subPixelOffset1 = clamp(abs(lumaAverage - lumaCenter) / lumaRange, 0.0, 1.0);
	float subPixelOffset2 = (-2.0 * subPixelOffset1 + 3.0) * subPixelOffset1 * subPixelOffset1;
	float subPixelOffsetFinal = subPixelOffset2 * subPixelOffset2 * FXAA_SUBPIX_TRIM_SCALE;

	finalOffset = max(finalOffset, subPixelOffsetFinal);

	vec2 finalUv = uv;
	if (isHorizontal) {
		finalUv.y += finalOffset * stepLength;
	}
	else {
		finalUv.x += finalOffset * stepLength;
	}

	return TEXTURE_LOD(tex, finalUv, 0.0);
}

void main()
{
	vec2 uv = uvcoord.xy;
	vec2 rcpRes = 1.0 / vec2(viewport_size.x, viewport_size.y);

	FINAL_COLOR = AAPostFX(colorbuffer, rcpRes, uv);
}
