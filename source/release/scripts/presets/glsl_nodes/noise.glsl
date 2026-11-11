// @name Noise
// @category Generators
// @description Ruído fractal: suave, valor, turbulência ou cristas.
// @output gray
// @input mask: gray = 1
// @param style: enum(Perlin, Value, Turbulence, Ridged) = Perlin
// @param scale: float(1, 64) = 6
// @param octaves: int(1, 8) = 5
// @param roughness: float(0, 1) = 0.5
// @param seed: int(0, 1000) = 0

float hash(vec2 p)
{
    return fract(sin(dot(p, vec2(127.1, 311.7)) + float(params.seed) * 17.13) * 43758.5453);
}

float value_noise(vec2 p)
{
    vec2 i = floor(p);
    vec2 f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), u.x),
               mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), u.x), u.y);
}

float grad_noise(vec2 p)
{
    vec2 i = floor(p);
    vec2 f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    float a = dot(vec2(hash(i), hash(i + 7.0)) * 2.0 - 1.0, f);
    float b = dot(vec2(hash(i + vec2(1.0, 0.0)), hash(i + vec2(8.0, 7.0))) * 2.0 - 1.0, f - vec2(1.0, 0.0));
    float c = dot(vec2(hash(i + vec2(0.0, 1.0)), hash(i + vec2(7.0, 8.0))) * 2.0 - 1.0, f - vec2(0.0, 1.0));
    float d = dot(vec2(hash(i + vec2(1.0, 1.0)), hash(i + vec2(8.0, 8.0))) * 2.0 - 1.0, f - vec2(1.0, 1.0));
    return mix(mix(a, b, u.x), mix(c, d, u.x), u.y) * 0.5 + 0.5;
}

vec4 node(vec2 uv)
{
    vec2 p = uv * params.scale;
    float sum = 0.0, amp = 1.0, total = 0.0;
    for (int o = 0; o < 8; o++) {
        if (o >= params.octaves) break;
        float n = (params.style == 1) ? value_noise(p) : grad_noise(p);
        if (params.style == 2) n = abs(n * 2.0 - 1.0);
        if (params.style == 3) n = 1.0 - abs(n * 2.0 - 1.0);
        sum += n * amp;
        total += amp;
        amp *= params.roughness;
        p *= 2.0;
    }
    return vec4(sum / total * in_mask(uv));
}
