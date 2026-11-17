// @name Box Impostor
// @category Impostor
// @description Impostor de Caixa: desenha o objeto assado em 6 vistas (Bake Box Impostor) num card virado para a câmera, com volume por parallax. Ligue o nó Billboard (Lock Axis 0) no Vertex Offset.
// @output color
// @surface
// @param color: image
// @param data: image
// @param extent: float(0.0001, 10000) = 1
// @param steps: int(1, 32) = 32
// @param box_mode: int(0, 1) = 0
// @param box_x: float(0.0001, 10000) = 1
// @param box_y: float(0.0001, 10000) = 1
// @param box_z: float(0.0001, 10000) = 1

// docs/plano-imposter-caixa.md. Atlas 3x2 do bake (anastacio_box_impostor.py): vista k na coluna
// k % 3, linha k / 3; 0 +X, 1 -X, 2 +Y, 3 -Y, 4 +Z, 5 -Z. "data": RGB = normal, A = profundidade a
// partir da face (0..1 da aresta do cubo; 1 = nada). O card fica no centro do cubo, com os eixos do
// objeto, então surface().position e .view já estão no espaço do bake (metros, -extent..extent).
//
// Só as 3 vistas voltadas para a câmera (uma por eixo, pelo sinal do raio). A "sombra" de cada uma
// (tudo atrás da primeira superfície vista daquela face) vai até o fundo da caixa, então até uma
// orelha fina é grossa para o raio; as vistas de trás a deixariam fina e os passos a pulariam. O raio
// do olho marcha pela caixa e o primeiro ponto dentro das 3 é o acerto; a cor vem das vistas que viram
// aquele ponto (profundidade igual à assada), pesadas pelo quanto encaram a câmera. Sem acerto:
// discard (o mesmo do Alpha Clip, sem precisar de socket de alpha).

void imp_axes(int k, out vec3 n, out vec3 u, out vec3 v)
{
    if (k == 0)      { n = vec3( 1.0, 0.0, 0.0); u = vec3( 0.0, 1.0, 0.0); v = vec3(0.0, 0.0, 1.0); }
    else if (k == 1) { n = vec3(-1.0, 0.0, 0.0); u = vec3( 0.0,-1.0, 0.0); v = vec3(0.0, 0.0, 1.0); }
    else if (k == 2) { n = vec3( 0.0, 1.0, 0.0); u = vec3(-1.0, 0.0, 0.0); v = vec3(0.0, 0.0, 1.0); }
    else if (k == 3) { n = vec3( 0.0,-1.0, 0.0); u = vec3( 1.0, 0.0, 0.0); v = vec3(0.0, 0.0, 1.0); }
    else if (k == 4) { n = vec3( 0.0, 0.0, 1.0); u = vec3( 1.0, 0.0, 0.0); v = vec3(0.0, 1.0, 0.0); }
    else             { n = vec3( 0.0, 0.0,-1.0); u = vec3( 1.0, 0.0, 0.0); v = vec3(0.0,-1.0, 0.0); }
}

// Atlas UV of point p (meters, cube center at 0) in view k, clamped half a texel inside the cell so
// linear filtering never reads the neighbour view; depth = how far p is behind the face (0..1).
vec2 imp_uv(int k, vec3 p, float ext, float margin, out float depth)
{
    vec3 n, u, v;
    imp_axes(k, n, u, v);
    vec2 c = clamp(vec2(dot(p, u), dot(p, v)) / ext * 0.5 + 0.5, vec2(margin), vec2(1.0 - margin));
    depth = (ext - dot(p, n)) / (2.0 * ext);
    float col = float(k - (k / 3) * 3);
    float row = float(k / 3);
    return (vec2(col, row) + c) / vec2(3.0, 2.0);
}

// Stored depth at the nearest texel: filtering would blend a near surface with "nothing" (1.0) or
// with a far one at every silhouette and cut cracks in the shape.
float imp_depth(vec2 st)
{
    vec2 size = res();
    return img_data_lod((floor(st * size) + 0.5) / size, 0.0).a;
}

// Inside: behind the first surface of the 3 views kx, ky, kz (alpha 1 = that view sees nothing).
bool imp_inside(vec3 p, float ext, float margin, float eps, ivec3 views)
{
    for (int i = 0; i < 3; i++) {
        int k = (i == 0) ? views.x : (i == 1) ? views.y : views.z;
        float d;
        vec2 st = imp_uv(k, p, ext, margin, d);
        float stored = imp_depth(st);
        if (stored > 0.996 || d < stored - eps) {
            return false;
        }
    }
    return true;
}

vec3 imp_srgb_to_linear(vec3 c)
{
    return mix(c / 12.92, pow((c + 0.055) / 1.055, vec3(2.4)), step(vec3(0.04045), c));
}

vec4 node(vec2 uv)
{
    Surface s = surface(uv);
    float ext = max(params.extent, 1e-4);
    vec3 p = s.position;
    vec3 dir = s.view;
    float margin = 0.5 / max(res().y * 0.5, 1.0);
    float eps = 1.0 / 255.0;

    // Line (not ray) against the cube: the card is in the middle of the cube, so the half between
    // the card and the camera starts at a negative t.
    vec3 d = vec3(abs(dir.x) < 1e-6 ? 1e-6 : dir.x, abs(dir.y) < 1e-6 ? 1e-6 : dir.y,
                  abs(dir.z) < 1e-6 ? 1e-6 : dir.z);
    vec3 t0 = (vec3(-ext) - p) / d;
    vec3 t1 = (vec3(ext) - p) / d;
    vec3 tn = min(t0, t1);
    vec3 tf = max(t0, t1);
    float t_in = max(max(tn.x, tn.y), tn.z);
    float t_out = min(min(tf.x, tf.y), tf.z);
    if (t_in >= t_out) {
        discard;
    }

    // The view on the camera's side of each axis.
    ivec3 views = ivec3(dir.x < 0.0 ? 0 : 1, dir.y < 0.0 ? 2 : 3, dir.z < 0.0 ? 4 : 5);
    // Box mode (objects that fill their bounding box: crates, buildings): the entry point on the box
    // (half sizes box_x/y/z, centered like the cube) is already the surface; one read from the view of
    // the face the ray enters through.
    if (params.box_mode != 0) {
        vec3 h = min(vec3(params.box_x, params.box_y, params.box_z), vec3(ext));
        vec3 b0 = (-h - p) / d;
        vec3 b1 = (h - p) / d;
        vec3 bn = min(b0, b1);
        vec3 bf = max(b0, b1);
        float b_in = max(max(bn.x, bn.y), bn.z);
        if (b_in >= min(min(bf.x, bf.y), bf.z)) {
            discard;
        }
        vec3 q = p + dir * b_in;
        int k = (bn.x >= bn.y && bn.x >= bn.z) ? views.x : (bn.y >= bn.z) ? views.y : views.z;
        float dq;
        vec4 c = img_color_lod(imp_uv(k, q, ext, margin, dq), 0.0);
        if (c.a < 0.5) {
            discard;
        }
        return vec4(imp_srgb_to_linear(clamp(c.rgb, 0.0, 1.0)), 1.0);
    }

    int n_steps = clamp(params.steps, 1, 32);
    float dt = (t_out - t_in) / float(n_steps);
    float t_prev = t_in;
    float t_hit = -1e20;
    bool hit = false;
    for (int i = 0; i <= 32; i++) {
        if (i > n_steps) {
            break;
        }
        float t = t_in + dt * float(i);
        if (imp_inside(p + dir * t, ext, margin, eps, views)) {
            // Refine between the last outside sample and this one.
            float a = t_prev, b = t;
            if (i > 0) {
                for (int j = 0; j < 5; j++) {
                    float m = 0.5 * (a + b);
                    if (imp_inside(p + dir * m, ext, margin, eps, views)) b = m; else a = m;
                }
            }
            t_hit = b;
            hit = true;
            break;
        }
        t_prev = t;
    }
    if (!hit) {
        discard;
    }

    // Color: the views whose stored surface is at this point (smallest depth error), weighted by how
    // much they face the camera and by their alpha (no dark fringe from the transparent background).
    vec3 q = p + dir * t_hit;
    float err[3];
    float e_min = 1e20;
    for (int i = 0; i < 3; i++) {
        int k = (i == 0) ? views.x : (i == 1) ? views.y : views.z;
        float dq;
        vec2 st = imp_uv(k, q, ext, margin, dq);
        err[i] = abs(dq - imp_depth(st));
        e_min = min(e_min, err[i]);
    }
    vec3 sum = vec3(0.0);
    float wsum = 0.0;
    for (int i = 0; i < 3; i++) {
        int k = (i == 0) ? views.x : (i == 1) ? views.y : views.z;
        vec3 n, u, v;
        imp_axes(k, n, u, v);
        float dq;
        vec2 st = imp_uv(k, q, ext, margin, dq);
        vec4 c = img_color_lod(st, 0.0);
        float w = (0.05 + max(dot(n, -dir), 0.0)) * max(0.0, 1.0 - (err[i] - e_min) / 0.02);
        sum += c.rgb * w;
        wsum += w;
    }
    return vec4(imp_srgb_to_linear(clamp(sum / max(wsum, 1e-6), 0.0, 1.0)), 1.0);
}
