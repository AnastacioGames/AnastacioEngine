// @name Box Blur
// @category Images
// @description Desfoca a imagem ligada em src lendo-a em 9 pontos (in_src em outra UV).
// @output color
// @input src: color = 1, 1, 1
// @param radius: float(0, 0.05) = 0.01

vec4 node(vec2 uv)
{
    vec4 sum = vec4(0.0);
    for (int y = -1; y <= 1; y++) {
        for (int x = -1; x <= 1; x++) {
            sum += in_src(uv + vec2(float(x), float(y)) * params.radius);
        }
    }
    return sum / 9.0;
}
