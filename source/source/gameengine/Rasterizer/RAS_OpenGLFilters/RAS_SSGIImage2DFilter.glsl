/* Edge-aware spatial reconstruction and linear-light composition. */
#ifdef USE_CORE_PROFILE
#define texture2D texture
in vec2 texCoordVarying;
out vec4 fragColor;
#define gl_FragColor fragColor
#endif
uniform sampler2D bgl_RenderedTexture;
uniform sampler2D bgl_DepthTexture;
uniform sampler2D bgl_DataTextures[7];
uniform sampler2D ge_SSGIBuffer;
uniform mat4 unfinvprojmat;
uniform float bgl_RenderedTextureWidth;
uniform float bgl_RenderedTextureHeight;
uniform vec4 ge_SSGIParams[2];
uniform vec4 ge_SSGIDisplay;

vec3 position_at(vec2 uv)
{
    float depth = texture2D(bgl_DepthTexture, uv).r;
    vec4 p = unfinvprojmat * vec4(uv * 2.0 - 1.0, depth * 2.0 - 1.0, 1.0);
    return p.xyz / p.w;
}
float display_channel(float c)
{
    c = max(c * exp2(ge_SSGIDisplay.x), 0.0);
    float contrast = ge_SSGIDisplay.z;
    float d;
    if (contrast > 0.0) {
        float s0 = 10.0 / 16.5;
        float s = clamp((log2(max(c, 1e-10) / 0.18) + 10.0) / 16.5, 0.0, 1.0);
        float b = contrast * (1.0 - s0) / s0;
        d = s < s0 ? 0.5 * pow(s / s0, contrast) : 1.0 - 0.5 * pow((1.0 - s) / (1.0 - s0), b);
    }
    else d = c < 0.0031308 ? 12.92 * c : 1.055 * pow(c, 1.0 / 2.4) - 0.055;
    return ge_SSGIDisplay.y > 0.0 ? pow(max(d, 0.0), 1.0 / ge_SSGIDisplay.y) : d;
}
void main()
{
#ifdef USE_CORE_PROFILE
    vec2 uv = texCoordVarying;
#else
    vec2 uv = gl_TexCoord[0].xy;
#endif
    vec4 scene = texture2D(bgl_RenderedTexture, uv);
    gl_FragColor = scene;
    vec4 geom = texture2D(bgl_DataTextures[SSGI_SLOT], uv);
    vec4 albedo = texture2D(bgl_DataTextures[SSGI_SLOT + 1], uv);
    if (geom.a < 0.99 || albedo.a < 0.99 || dot(albedo.rgb, albedo.rgb) < 1e-8 ||
        texture2D(bgl_DepthTexture, uv).r >= 0.999999) return;
    vec3 p = position_at(uv);
    vec3 n = normalize(geom.xyz * 2.0 - 1.0);
    vec2 size = vec2(bgl_RenderedTextureWidth, bgl_RenderedTextureHeight);
    vec2 low_size = max(floor(size / ge_SSGIParams[1].z), vec2(1.0));
    vec2 center = floor(uv * low_size);
    vec3 sum = vec3(0.0);
    float total = 0.0;
    for (int y = -1; y <= 1; ++y) for (int x = -1; x <= 1; ++x) {
        vec2 tap = (center + vec2(float(x), float(y)) + 0.5) / low_size;
        if (any(lessThan(tap, vec2(0.0))) || any(greaterThan(tap, vec2(1.0)))) continue;
        vec4 gi = texture2D(ge_SSGIBuffer, tap);
        vec2 full_tap = (floor(tap * size) + 0.5) / size;
        vec4 tap_n = texture2D(bgl_DataTextures[SSGI_SLOT], full_tap);
        if (gi.a < 0.99 || tap_n.a < 0.99) continue;
        vec3 delta = position_at(full_tap) - p;
        float normal_weight = pow(max(dot(n, normalize(tap_n.xyz * 2.0 - 1.0)), 0.0), 32.0);
        float plane_weight = exp(-abs(dot(delta, n)) / max(ge_SSGIParams[0].z, 0.002));
        float spatial_weight = exp(-0.5 * float(x * x + y * y));
        float weight = normal_weight * plane_weight * spatial_weight;
        sum += gi.rgb * weight;
        total += weight;
    }
    vec3 indirect = sum / max(total, 1e-6) * albedo.rgb * ge_SSGIParams[0].y;
    if (dot(indirect, indirect) < 1e-12) return;
    vec3 linear_scene = texture2D(bgl_DataTextures[SSGI_SLOT + 3], uv).rgb;
    vec3 result = max(linear_scene + indirect, vec3(0.0));
    if (ge_SSGIDisplay.w > 0.5) result = vec3(display_channel(result.r), display_channel(result.g), display_channel(result.b));
    gl_FragColor = vec4(result, scene.a);
}
