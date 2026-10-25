/* Screen Space Reflections, trace pass (Fase 3 of docs/plano-efeitos-render.md).
 *
 *  - ray march in screen space with the DDA of McGuire & Mara (2014): the reflected ray is
 *    clipped to the near plane, projected, and walked pixel by pixel (with a stride) in 2D while
 *    the view depth is interpolated in homogeneous space, so the steps are even on screen and
 *    there is no "ring" banding of the fixed view-space step;
 *  - per pixel and per frame jitter of the start (interleaved gradient noise), averaged by the
 *    temporal resolve (RAS_Temporal2DFilter.glsl with TEMPORAL_HIT_REPROJECT);
 *  - binary refinement of the hit, thickness proportional to the distance;
 *  - fades: screen edge at the hit, ray distance, rays going back to the camera, Schlick fresnel;
 *  - no hit: World color (horizon/zenith gradient by the world space direction).
 *
 * Output: rgb = reflection already weighted (fresnel * fades * spec), a = 1 / (1 + total ray
 * length camera -> surface -> hit) for the reprojection by the hit point (0 = sky, at infinity). */

#ifdef USE_CORE_PROFILE
in vec2 texCoordVarying;

uniform mat4 unfviewmat;
uniform mat4 unfprojmat;
  #define gl_ModelViewMatrix unfviewmat
  #define gl_ProjectionMatrix unfprojmat
  #define gl_ProjectionMatrixInverse inverse(unfprojmat)

out vec4 fragColor;
  #define gl_FragColor fragColor
#endif

uniform sampler2D bgl_RenderedTexture;
uniform sampler2D bgl_DataTextures[1];
uniform sampler2D bgl_DepthTexture;
uniform mat4 unfinvviewmat;
uniform int bgl_Frame;
uniform vec3 ge_RainSkyHorizon; // World horizon color
uniform vec3 ge_RainSkyZenith;  // World zenith color

uniform vec3 ge_ssrparams; // step_max, bias, max_distance

#define SSR_MAX_STEPS 128

vec2 unpackFloat2(float f) {
	return vec2(floor(f) / 255.0, fract(f));
}

vec3 decode_octa(vec2 e) {
	vec3 v = vec3(e.xy, 1.0 - abs(e.x) - abs(e.y));

	if (v.z < 0.0)
		v.xy = (1.0 - abs(v.yx)) * vec2((v.x >= 0.0) ? 1.0 : -1.0, (v.y >= 0.0) ? 1.0 : -1.0);

	return -(gl_ModelViewMatrix * vec4(normalize(v), 0.0)).xyz;
}

float ign(vec2 p, float frame)
{
	p += frame * 5.588238;
	return fract(52.9829189 * fract(dot(p, vec2(0.06711056, 0.00583715))));
}

/* GGX VNDF sampling (Heitz 2018, "Sampling the GGX Distribution of Visible Normals"). N faces the
 * camera, Ve is the direction to the camera, a = roughness^2. u.x is scaled by 0.8 to cut the far
 * tail of the lobe (rays that would mostly go into the surface or add fireflies). */
vec3 sampleGGXVNDF(vec3 N, vec3 Ve, float a, vec2 u)
{
	vec3 T = normalize(abs(N.z) < 0.99 ? cross(N, vec3(0.0, 0.0, 1.0)) : cross(N, vec3(1.0, 0.0, 0.0)));
	vec3 B = cross(N, T);
	vec3 v = vec3(dot(Ve, T), dot(Ve, B), dot(Ve, N));
	vec3 Vh = normalize(vec3(a * v.x, a * v.y, max(v.z, 0.0)));
	float lensq = dot(Vh.xy, Vh.xy);
	vec3 T1 = (lensq > 1e-7) ? vec3(-Vh.y, Vh.x, 0.0) * inversesqrt(lensq) : vec3(1.0, 0.0, 0.0);
	vec3 T2 = cross(Vh, T1);
	float r = sqrt(u.x * 0.8);
	float phi = 6.2831853 * u.y;
	float t1 = r * cos(phi);
	float t2 = r * sin(phi);
	float s = 0.5 * (1.0 + Vh.z);
	t2 = (1.0 - s) * sqrt(max(0.0, 1.0 - t1 * t1)) + s * t2;
	vec3 Nh = t1 * T1 + t2 * T2 + sqrt(max(0.0, 1.0 - t1 * t1 - t2 * t2)) * Vh;
	vec3 m = normalize(vec3(a * Nh.x, a * Nh.y, max(Nh.z, 1e-4)));
	return normalize(T * m.x + B * m.y + N * m.z);
}

mat4 invProj;

float viewZ(vec2 uv)
{
	float d = texture(bgl_DepthTexture, uv).x;
	vec4 v = invProj * vec4(uv * 2.0 - 1.0, d * 2.0 - 1.0, 1.0);
	return v.z / v.w;
}

vec3 worldColor(vec3 viewDir)
{
	vec3 w = normalize((unfinvviewmat * vec4(viewDir, 0.0)).xyz);
	return mix(ge_RainSkyHorizon, ge_RainSkyZenith, clamp(w.z, 0.0, 1.0));
}

void main() {
	vec2 texcoord;
#ifdef USE_CORE_PROFILE
	texcoord = texCoordVarying;
#else
	texcoord = gl_TexCoord[0].st;
#endif
	invProj = gl_ProjectionMatrixInverse;

	float depth = texture(bgl_DepthTexture, texcoord).x;
	if (depth >= 1.0) {
		gl_FragColor = vec4(0.0);
		return;
	}

	vec4 csp = invProj * vec4(texcoord * 2.0 - 1.0, depth * 2.0 - 1.0, 1.0);
	vec3 P = csp.xyz / csp.w;

	vec4 Gbuff0 = texture(bgl_DataTextures[0], texcoord);
	vec3 N = decode_octa(Gbuff0.rg);
	vec2 rough_metal = unpackFloat2(Gbuff0.b);
	vec2 diff_spec = unpackFloat2(Gbuff0.a);
	float rough = rough_metal.x;

	vec3 V = normalize(P);
	vec2 fullSize = vec2(textureSize(bgl_DepthTexture, 0));
	vec2 pix = texcoord * fullSize;
	float frame = float(bgl_Frame % 64);
	float jitter = ign(pix, frame);

	/* The G-buffer normal sign is not guaranteed to face the camera: orient it by the view. */
	float nSign = (dot(N, V) < 0.0) ? 1.0 : -1.0;
	vec3 Nf = N * nSign;

	/* Rough surfaces: one GGX microfacet normal per pixel and frame, sampled from the distribution of
	 * visible normals (Heitz 2018), averaged by the temporal resolve and the roughness blur. */
	vec3 Nr = Nf;
	if (rough > 0.02) {
		Nr = sampleGGXVNDF(Nf, -V, rough * rough,
		                   vec2(ign(pix + 41.0, frame + 7.0), ign(pix + 17.0, frame + 3.0)));
	}
	vec3 R = normalize(reflect(V, Nr));
	/* At grazing angles (silhouette of a sphere) the rough jitter can send the ray into the surface,
	 * which then "hits" its own darker side: fall back to the mirror direction there. */
	if (dot(R, Nf) < 0.02) {
		R = normalize(reflect(V, N));
	}

	/* Schlick fresnel: F0 0.04 (dielectric, scaled by spec) up to 1 (metal). */
	float NdV = clamp(abs(dot(N, V)), 0.0, 1.0);
	float F0 = mix(0.04 * 2.0 * diff_spec.y, 1.0, rough_metal.y);
	float fresnel = F0 + (1.0 - F0) * pow(1.0 - NdV, 5.0);
	/* Rough reflections lose energy to the blur, not to a hard cut. */
	float weight = fresnel * (1.0 - 0.5 * rough * rough);

	vec3 fallback = worldColor(R);

	/* --- McGuire DDA ------------------------------------------------------------------------ */
	float maxDist = max(ge_ssrparams.z, 0.1);
	float near = 0.0;
	{
		vec4 n = invProj * vec4(0.0, 0.0, -1.0, 1.0);
		near = n.z / n.w; // negative
	}
	/* Lift the origin off the surface by its normal, proportional to the distance, so a ray almost
	 * tangent to a curved surface does not start inside its depth. */
	P += Nf * (0.002 * -P.z + 0.005);
	float rayLen = ((P.z + R.z * maxDist) > near) ? (near - 0.001 - P.z) / R.z : maxDist;
	vec3 Pend = P + R * rayLen;

	vec4 H0 = gl_ProjectionMatrix * vec4(P, 1.0);
	vec4 H1 = gl_ProjectionMatrix * vec4(Pend, 1.0);
	float k0 = 1.0 / H0.w, k1 = 1.0 / H1.w;
	vec3 Q0 = P * k0, Q1 = Pend * k1;
	vec2 S0 = (H0.xy * k0 * 0.5 + 0.5) * fullSize;
	vec2 S1 = (H1.xy * k1 * 0.5 + 0.5) * fullSize;

	/* Clip the 2D segment to the screen so the stride is spent on visible pixels. */
	{
		vec2 dS = S1 - S0;
		float t = 1.0;
		if (S1.x > fullSize.x) t = min(t, (fullSize.x - S0.x) / dS.x);
		if (S1.x < 0.0) t = min(t, -S0.x / dS.x);
		if (S1.y > fullSize.y) t = min(t, (fullSize.y - S0.y) / dS.y);
		if (S1.y < 0.0) t = min(t, -S0.y / dS.y);
		t = clamp(t, 0.0, 1.0);
		S1 = mix(S0, S1, t);
		Q1 = mix(Q0, Q1, t);
		k1 = mix(k0, k1, t);
	}
	S1 += vec2((dot(S1 - S0, S1 - S0) < 0.0001) ? 0.01 : 0.0);
	vec2 delta = S1 - S0;
	bool permute = false;
	if (abs(delta.x) < abs(delta.y)) {
		permute = true;
		delta = delta.yx;
		S0 = S0.yx;
		S1 = S1.yx;
	}
	float stepDir = sign(delta.x);
	float invdx = stepDir / delta.x;
	vec3 dQ = (Q1 - Q0) * invdx;
	float dk = (k1 - k0) * invdx;
	vec2 dS = vec2(stepDir, delta.y * invdx);

	int steps = clamp(int(ge_ssrparams.x), 8, SSR_MAX_STEPS);
	float stride = max(1.0, abs(delta.x) / float(steps));
	dS *= stride;
	dQ *= stride;
	dk *= stride;

	/* Start one pixel off the surface plus the jitter (no self hit, no rings). */
	float start = (1.0 + jitter * stride) / stride;
	vec2 S = S0 + dS * start;
	vec3 Q = Q0 + dQ * start;
	float k = k0 + dk * start;

	float prevZ = P.z;
	bool hit = false;
	float confidence = 0.0;
	vec2 hitUV = vec2(0.0);
	vec3 hitPos = vec3(0.0);
	float thickBias = max(ge_ssrparams.y, 1.0);

	for (int i = 0; i < SSR_MAX_STEPS; i++) {
		if (i >= steps) {
			break;
		}
		float zA = prevZ;
		float zB = (Q.z + dQ.z * 0.5) / (k + dk * 0.5);
		prevZ = zB;
		vec2 sp = permute ? S.yx : S;
		vec2 uv = sp / fullSize;
		if (any(lessThan(uv, vec2(0.0))) || any(greaterThan(uv, vec2(1.0)))) {
			break;
		}
		float zMin = min(zA, zB), zMax = max(zA, zB);
		float sceneZ = viewZ(uv);
		float thickness = (0.02 * -sceneZ + 0.05) * thickBias + 0.5 * abs(zB - zA);
		bool cand = zMin < sceneZ && zMax > sceneZ - thickness && texture(bgl_DepthTexture, uv).x < 1.0;
		/* Surfaces seen from behind by the ray (the floor itself at grazing angles) are not a hit:
		 * keep marching instead of stopping on them. */
		if (cand && dot(decode_octa(texture(bgl_DataTextures[0], uv).rg), R) * nSign > 0.0) {
			cand = false;
		}
		if (cand) {
			/* Binary refinement between the previous step and this one. */
			vec2 a = S - dS, b = S;
			vec3 qa = Q - dQ, qb = Q;
			float ka = k - dk, kb = k;
			for (int r = 0; r < 5; r++) {
				vec2 m = 0.5 * (a + b);
				vec3 qm = 0.5 * (qa + qb);
				float km = 0.5 * (ka + kb);
				float zm = qm.z / km;
				vec2 muv = (permute ? m.yx : m) / fullSize;
				if (zm < viewZ(muv)) { b = m; qb = qm; kb = km; }
				else { a = m; qa = qm; ka = km; }
			}
			vec2 rUV = (permute ? b.yx : b) / fullSize;
			vec3 rPos = qb / kb;
			/* Depth gap at the refined point: a ray passing behind an object (gap larger than the
			 * thickness) is not a hit; keep marching, it may end on the sky fallback. */
			float gap = abs(viewZ(rUV) - rPos.z);
			float tRef = (0.02 * -rPos.z + 0.05) * thickBias;
			/* A hit a few pixels from the start of a near tangent ray is the surface itself
			 * (convex silhouette): not a reflection, keep marching. */
			float startPx = length((rUV - texcoord) * fullSize);
			bool selfHit = startPx < 3.0 && dot(R, Nf) < 0.25;
			if (gap < tRef && !selfHit) {
				hitUV = rUV;
				hitPos = rPos;
				confidence = 1.0 - smoothstep(0.5, 1.0, gap / tRef);
				hit = true;
				break;
			}
		}
		S += dS;
		Q += dQ;
		k += dk;
	}

	/* The World fallback only on glossy surfaces (rough ones would just get brighter). */
	fallback *= (1.0 - rough) * (1.0 - rough);
	vec3 col = fallback;
	float encDist = 0.0;
	if (hit) {
		/* Back faces of the hit (ray hits something facing away) are not visible in a mirror. */
		vec3 hitN = decode_octa(texture(bgl_DataTextures[0], hitUV).rg);
		float facing = smoothstep(-0.05, 0.15, dot(hitN * nSign, -R));
		vec2 e = smoothstep(vec2(0.0), vec2(0.08), hitUV) * smoothstep(vec2(0.0), vec2(0.08), 1.0 - hitUV);
		float travel = length(hitPos - P);
		float fade = confidence * e.x * e.y * facing * (1.0 - smoothstep(0.7, 1.0, travel / maxDist));
		/* Rays going back toward the camera have no reliable screen data. */
		fade *= 1.0 - smoothstep(0.4, 0.9, R.z);
		vec3 hitCol = min(texture(bgl_RenderedTexture, hitUV).rgb, vec3(16.0));
		col = mix(fallback, hitCol, fade);
		encDist = (fade > 0.5) ? 1.0 / (1.0 + length(P) + travel) : 0.0;
	}

	vec3 result = col * weight * ((rough_metal.y < 0.1) ? diff_spec.y : 1.0);
	gl_FragColor = vec4(result, encDist);
}
