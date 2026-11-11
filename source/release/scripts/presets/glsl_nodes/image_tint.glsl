// @name Image Tint
// @category Images
// @description Imagem com repetição, deslocamento e cor multiplicada.
// @output color
// @param tex: image
// @param tint: color = 1, 1, 1
// @param repeat: float(0.1, 16) = 1
// @param offset_x: float(-1, 1) = 0
// @param offset_y: float(-1, 1) = 0

vec4 node(vec2 uv)
{
    vec2 p = fract(uv * params.repeat + vec2(params.offset_x, params.offset_y));
    vec4 c = img_tex(p);
    return vec4(c.rgb * params.tint, c.a);
}
