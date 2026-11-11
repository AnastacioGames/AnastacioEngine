// @name Mesh Wear
// @category Mesh Maps
// @description Escurece as cavidades pelo AO e clareia as quinas pela curvatura (mapas assados da malha).
// @output color
// @input base: color = 0.6, 0.6, 0.6
// @param ao: meshmap(ao)
// @param curvature: meshmap(curvature)
// @param ao_strength: float(0, 1) = 1
// @param edge_color: color = 1, 0.95, 0.85
// @param edge_strength: float(0, 4) = 1.5

vec4 node(vec2 uv)
{
    vec4 c = in_base(uv);
    float occ = mix(1.0, mesh_ao(uv), params.ao_strength);
    float edge = clamp((mesh_curvature(uv) - 0.5) * 2.0 * params.edge_strength, 0.0, 1.0);
    return vec4(mix(c.rgb * occ, params.edge_color, edge), c.a);
}
