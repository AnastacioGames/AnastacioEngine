#ifdef USE_CORE_PROFILE
in vec2 texCoordVarying;

out vec4 fragColor;
  #define gl_FragColor fragColor
#endif

// Camera FX, pass A: bokeh depth of field around the camera focus (KX_Camera::UpdateGameFX).
uniform sampler2D bgl_RenderedTexture;
uniform sampler2D bgl_DepthTexture;
uniform float bgl_RenderedTextureWidth;
uniform float bgl_RenderedTextureHeight;

// [0] focus distance, focus range, near, far
// [1] max blur (px), rings, cat eye strength (0 = off), perspective
// [2] speed blur, focus x, focus y, protect
// [3] turn x, turn y, directional blur on, unused
// [4] chromatic, vignette, vignette radius, fisheye
// [5] blades, unused, unused, unused
uniform vec4 ge_CameraFX[6];

float linearDepth(vec2 uv)
{
	float d = texture(bgl_DepthTexture, uv).r;
	float n = ge_CameraFX[0].z;
	float f = ge_CameraFX[0].w;
	if (ge_CameraFX[1].w > 0.5) {
		return n * f / (f - d * (f - n));
	}
	return n + d * (f - n);
}

// 0 = sharp, 1 = full blur.
float circleOfConfusion(float z)
{
	float focus = ge_CameraFX[0].x;
	float halfRange = ge_CameraFX[0].y * 0.5;
	float away = max(abs(z - focus) - halfRange, 0.0);
	// Grows with the distance relative to the focus, like a real lens.
	return clamp(away / max(focus * 0.5, 0.5), 0.0, 1.0);
}

// Radius scale of a polygonal aperture at angle a (circle when blades < 3).
float bladeShape(float a)
{
	float blades = ge_CameraFX[5].x;
	if (blades < 3.0) {
		return 1.0;
	}
	float seg = 6.2831853 / blades;
	float x = mod(a, seg) - seg * 0.5;
	return cos(seg * 0.5) / cos(x);
}

void main()
{
#ifdef USE_CORE_PROFILE
	vec2 uv = texCoordVarying;
#else
	vec2 uv = gl_TexCoord[0].st;
#endif
	vec4 center = texture(bgl_RenderedTexture, uv);

	float coc = circleOfConfusion(linearDepth(uv));
	float maxRadius = ge_CameraFX[1].x;
	float radius = coc * maxRadius;
	if (radius < 0.5) {
		gl_FragColor = center;
		return;
	}

	vec2 texel = vec2(1.0 / bgl_RenderedTextureWidth, 1.0 / bgl_RenderedTextureHeight);
	float aspect = bgl_RenderedTextureWidth / bgl_RenderedTextureHeight;
	// Cat eye: the aperture is clipped by a disc pushed toward the frame center.
	vec2 fromCenter = (uv - 0.5) * vec2(aspect, 1.0);
	float catEye = ge_CameraFX[1].z;

	int rings = int(ge_CameraFX[1].y);
	vec3 sum = center.rgb;
	float weight = 1.0;

	for (int ring = 1; ring <= 5; ++ring) {
		if (ring > rings) {
			break;
		}
		float ringFrac = float(ring) / float(rings);
		int count = ring * 6;
		for (int i = 0; i < 30; ++i) {
			if (i >= count) {
				break;
			}
			float a = 6.2831853 * (float(i) + 0.5 * float(ring)) / float(count);
			vec2 dir = vec2(cos(a), sin(a)) * ringFrac * bladeShape(a);
			if (catEye > 0.0 && length(dir + fromCenter * catEye * 2.0) > 1.0) {
				continue;
			}
			vec2 suv = uv + dir * radius * texel;
			float scoc = circleOfConfusion(linearDepth(suv)) * maxRadius;
			// A sample only spreads over this pixel if its own blur reaches it,
			// so sharp foreground edges do not bleed into the background.
			float w = clamp(scoc - ringFrac * radius + 1.0, 0.0, 1.0);
			vec3 c = texture(bgl_RenderedTexture, suv).rgb;
			// Bright samples weigh more: bokeh highlights.
			w *= 1.0 + dot(c, vec3(0.3, 0.59, 0.11)) * 2.0;
			sum += c * w;
			weight += w;
		}
	}

	gl_FragColor = vec4(sum / weight, center.a);
}
