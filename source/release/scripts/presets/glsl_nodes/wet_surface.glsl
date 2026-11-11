// @name Wet Surface
// @category Shading
// @description Superfície molhada: escurece a cor e deixa mais lisa. Ligue entre os valores e o material.
// @shading
// @param wetness: float(0, 1) = 0.7
// @param puddle_roughness: float(0, 1) = 0.05

void node(inout Shade c)
{
    float w = params.wetness;
    c.albedo.rgb *= mix(1.0, 0.45, w);
    c.roughness = mix(c.roughness, params.puddle_roughness, w);
}
