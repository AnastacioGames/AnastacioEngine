// @name Sharpen
// @category Images
// @description Realça os detalhes da imagem ligada em src (lê os vizinhos com in_src em outra UV).
// @output color
// @input src: color = 1, 1, 1
// @param amount: float(0, 4) = 1
// @param texel: float(0.0001, 0.02) = 0.002

vec4 node(vec2 uv)
{
    vec2 d = vec2(params.texel, 0.0);
    vec4 c = in_src(uv);
    vec4 around = in_src(uv + d.xy) + in_src(uv - d.xy) + in_src(uv + d.yx) + in_src(uv - d.yx);
    return vec4(max(c.rgb + (c.rgb * 4.0 - around.rgb) * params.amount, 0.0), c.a);
}
