// @name Triplanar
// @category Images
// @description Projeta a imagem pelos três eixos do objeto, sem precisar de UV. Bom para pedra, terra e paredes.
// @surface
// @param tex: image
// @param scale: float(0.01, 100) = 1

vec4 node(vec2 uv)
{
    return triplanar_tex(params.scale);
}
