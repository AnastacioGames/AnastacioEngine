// @name Checker Tint
// @category Patterns
// @description Xadrez com duas cores e opção de inverter.
// @output color
// @input tint: color = 1, 1, 1
// @param color_a: color = 0.9, 0.9, 0.9
// @param color_b: color = 0.1, 0.1, 0.1
// @param scale: float(1, 64) = 8
// @param invert: bool = false

vec4 node(vec2 uv)
{
    vec2 c = floor(uv * params.scale);
    bool odd = mod(c.x + c.y, 2.0) > 0.5;
    if (params.invert) odd = !odd;
    vec3 col = odd ? params.color_a : params.color_b;
    return vec4(col, 1.0) * in_tint(uv);
}
