// Velocidade cenografica: funciona com camera e carro totalmente parados.
uniform sampler2D bgl_RenderedTexture;
uniform float u_strength;
uniform float bgl_Time;
uniform vec2 bgl_Resolution;
in vec2 texCoordVarying;
out vec4 fragColor;

float subjectMask(vec2 uv)
{
    float d = length((uv - vec2(0.82, 0.28)) / vec2(0.25, 0.36));
    return 1.0 - smoothstep(0.82, 1.12, d);
}

void main()
{
    vec2 uv = texCoordVarying;
    vec4 original = texture(bgl_RenderedTexture, uv);
    vec2 radial = uv - vec2(0.32, 0.52);
    float amount = smoothstep(0.08, 0.48, length(radial));
    amount *= 1.0 - subjectMask(uv);
    vec4 sum = original;
    float weights = 1.0;
    for (int i = 1; i <= 16; ++i) {
        float t = float(i) / 16.0;
        vec2 sampleUV = clamp(uv - radial * u_strength * t, vec2(0.0), vec2(1.0));
        float weight = (1.0 - 0.5 * t) * (1.0 - subjectMask(sampleUV));
        sum += texture(bgl_RenderedTexture, sampleUV) * weight;
        weights += weight;
    }
    vec4 result = mix(original, sum / weights, amount * 0.92);

    // Filetes alongados correndo do ponto de fuga para as bordas.
    // Mascara protege o piloto tambem das linhas, sem exigir movimento real.
    vec2 p = radial * vec2(bgl_Resolution.x / bgl_Resolution.y, 1.0);
    float radius = length(p);
    float lane = (atan(p.y, p.x) + 3.14159265) * (94.0 / 6.2831853);
    float seed = fract(sin(floor(lane) * 127.1 + 4.7) * 43758.5453);
    float thin = exp(-pow((fract(lane) - 0.5) / 0.024, 2.0));
    float phase = fract(radius * 1.45 - bgl_Time * 0.85 + seed * 4.0);
    float segment = smoothstep(0.20, 0.27, phase) * (1.0 - smoothstep(0.51, 0.67, phase));
    float edge = smoothstep(0.28, 0.78, radius);
    float streak = thin * segment * edge * step(0.68, seed);
    streak *= (1.0 - subjectMask(uv)) * clamp(u_strength * 10.0, 0.0, 1.0);
    result.rgb += vec3(0.48, 0.70, 0.95) * streak * 0.23;
    fragColor = result;
}
