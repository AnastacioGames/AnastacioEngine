/* Anastacio native SSGI. Cosine-weighted hemisphere rays, first visible depth intersection.
 * Only direct diffuse radiance is sampled: no display colors, specular or baked GI feedback.
 * SSGI_SLOT is supplied by the manager so sampler indices remain compile-time constants. */
#ifdef USE_CORE_PROFILE
#define texture2D texture
in vec2 texCoordVarying;
out vec4 fragColor;
#define gl_FragColor fragColor
#endif
uniform sampler2D bgl_DepthTexture;
uniform sampler2D bgl_DataTextures[7];
uniform mat4 unfprojmat;
uniform mat4 unfinvprojmat;
uniform float bgl_RenderedTextureWidth;
uniform float bgl_RenderedTextureHeight;
uniform vec4 ge_SSGIParams[2]; // radius, strength, thickness, rays; steps, slot, divisor, reserved

vec3 position_at(vec2 uv, float depth)
{
    vec4 p = unfinvprojmat * vec4(uv * 2.0 - 1.0, depth * 2.0 - 1.0, 1.0);
    return p.xyz / p.w;
}

void main()
{
#ifdef USE_CORE_PROFILE
    vec2 uv = texCoordVarying;
#else
    vec2 uv = gl_TexCoord[0].xy;
#endif
    vec2 size = vec2(bgl_RenderedTextureWidth, bgl_RenderedTextureHeight);
    uv = (floor(uv * size) + 0.5) / size;
    float depth = texture2D(bgl_DepthTexture, uv).r;
    vec4 geom = texture2D(bgl_DataTextures[SSGI_SLOT], uv);
    vec4 albedo = texture2D(bgl_DataTextures[SSGI_SLOT + 1], uv);
    gl_FragColor = vec4(0.0);
    if (depth >= 0.999999 || geom.a < 0.99 || albedo.a < 0.99 ||
        dot(albedo.rgb, albedo.rgb) < 1e-8) return;

    vec3 p = position_at(uv, depth);
    vec3 n = normalize(geom.xyz * 2.0 - 1.0);
    vec3 tangent = normalize(cross(abs(n.z) < 0.9 ? vec3(0.0, 0.0, 1.0) : vec3(0.0, 1.0, 0.0), n));
    vec3 bitangent = cross(n, tangent);
    float radius = ge_SSGIParams[0].x;
    float thickness = ge_SSGIParams[0].z;
    int rays = int(ge_SSGIParams[0].w);
    int steps = int(ge_SSGIParams[1].x);
    /* Static interleaved rotation: avoids temporal flicker without a history buffer. */
    float noise = fract(52.9829189 * fract(dot(gl_FragCoord.xy, vec2(0.06711056, 0.00583715))));
    vec3 sum = vec3(0.0);
    for (int r = 0; r < 16; ++r) {
        if (r >= rays) break;
        float u = (float(r) + 0.5) / float(rays);
        float angle = 6.28318530718 * fract(float(r) * 0.61803398875 + noise);
        vec3 dir = tangent * (sqrt(u) * cos(angle)) + bitangent * (sqrt(u) * sin(angle)) + n * sqrt(1.0 - u);
        float bias = max(0.002, thickness * 0.1);
        vec3 origin = p + n * bias;
        float previous_t = 0.0;
        for (int j = 0; j < 32; ++j) {
            if (j >= steps) break;
            float fraction = (float(j) + 1.0) / float(steps);
            float t = radius * fraction * fraction;
            vec3 q = origin + dir * t;
            vec4 clip = unfprojmat * vec4(q, 1.0);
            if (clip.w <= 0.0) break;
            vec3 ndc = clip.xyz / clip.w;
            vec2 sample_uv = ndc.xy * 0.5 + 0.5;
            if (any(lessThan(sample_uv, vec2(0.0))) || any(greaterThan(sample_uv, vec2(1.0))) || abs(ndc.z) > 1.0) break;
            sample_uv = (floor(sample_uv * size) + 0.5) / size;
            float d = texture2D(bgl_DepthTexture, sample_uv).r;
            if (d < 0.999999) {
                vec3 hit = position_at(sample_uv, d);
                float gap = hit.z - q.z;
                /* A sampled foreground surface terminates the ray; it is not a transparent hole.
                 * The thickness cap prevents reaching unrelated geometry behind silhouettes. */
                if (gap >= 0.0) {
                    float tolerance = thickness + (t - previous_t) * abs(dir.z);
                    if (gap <= tolerance && length(hit - p) > bias * 2.0 && length(hit - p) <= radius) {
                        vec4 hit_n = texture2D(bgl_DataTextures[SSGI_SLOT], sample_uv);
                        vec3 hit_normal = hit_n.xyz * 2.0 - 1.0;
                        if (hit_n.a >= 0.99 && dot(hit_normal, -dir) > 0.0) {
                            vec3 radiance = texture2D(bgl_DataTextures[SSGI_SLOT + 2], sample_uv).rgb;
                            float edge = min(min(sample_uv.x, sample_uv.y), min(1.0 - sample_uv.x, 1.0 - sample_uv.y));
                            sum += max(radiance, vec3(0.0)) * smoothstep(0.0, 0.05, edge);
                        }
                    }
                    break;
                }
            }
            previous_t = t;
        }
    }
    /* Cosine distribution includes the receiver cosine/pdf. Division uses ALL rays, including misses. */
    gl_FragColor = vec4(sum / float(rays), 1.0);
}
