// @name Emission Pulse
// @category Shading
// @description Faz a superfície brilhar pulsando com o tempo. Ligue Emission e Albedo no material.
// @shading
// @param glow: color = 1, 0.35, 0.1
// @param strength: float(0, 10) = 2
// @param speed: float(0, 10) = 2

void node(inout Shade c)
{
    float pulse = 0.5 + 0.5 * sin(TIME * params.speed);
    // The material's Emit is a single value that multiplies Albedo: the glow color goes in Albedo.
    c.albedo.rgb = mix(c.albedo.rgb, params.glow, pulse);
    c.emission += vec3(params.strength * pulse);
}
