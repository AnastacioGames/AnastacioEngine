"""Gera as miniaturas da faixa de presets das outras árvores do Node Editor
(Shader, Logic Tree, UI Tree). Só ilustram o preset.

Uso: python tools/debug/gerar_miniaturas_presets.py
Saída: source/release/scripts/startup/node_effects/<arvore>_<id>.png (256x256)
"""
import os
import numpy as np
from PIL import Image, ImageDraw

from gerar_miniaturas_efeitos import S, SS, OUT, blur, luma, grade_uv


def fundo(c1=(0.10, 0.11, 0.16), c2=(0.24, 0.27, 0.36)):
    y = np.linspace(0, 1, S, dtype=np.float32)[:, None, None]
    return np.broadcast_to(np.array(c2) * (1 - y) + np.array(c1) * y, (S, S, 3)).astype(np.float32)


LUZ = np.array([-0.5, 0.6, 0.62])
LUZ = LUZ / np.linalg.norm(LUZ)


def esfera(raio=0.78):
    """x, y, z da normal, máscara suave e N.L de uma esfera no centro."""
    u, v = grade_uv()
    u, v = u / raio, -v / raio
    r2 = u * u + v * v
    m = np.clip((1 - r2) * 60, 0, 1)
    z = np.sqrt(np.clip(1 - r2, 0, 1))
    ndl = np.clip(u * LUZ[0] + v * LUZ[1] + z * LUZ[2], 0, 1)
    return u, v, z, m, ndl


def comp(f, img, m):
    return f * (1 - m[..., None]) + img * m[..., None]


def brilho(ndl_spec, z, u, v, p=40):
    h = LUZ + np.array([0, 0, 1.0])
    h = h / np.linalg.norm(h)
    return np.clip(u * h[0] + v * h[1] + z * h[2], 0, 1) ** p


def sh_fur():
    f = fundo()
    rng = np.random.default_rng(2)
    u, v, z, m, ndl = esfera(0.70)
    # pelos: máscara com borda serrilhada e fios em ruído alongado
    uu, vv = grade_uv()
    ang = np.arctan2(vv, uu)
    r = np.sqrt(uu * uu + vv * vv)
    borda = 0.70 + 0.07 * np.abs(np.sin(ang * 45 + rng.random() * 3)) * (0.5 + 0.5 * np.sin(ang * 13))
    mm = np.clip((borda - r) * 80, 0, 1)
    fios = luma(blur(rng.random((S, S, 3)).astype(np.float32), 0.7))
    fios = (fios - fios.min()) / (fios.max() - fios.min())
    raiz, ponta = np.array([0.35, 0.20, 0.10]), np.array([1.0, 0.85, 0.60])
    t = np.clip(r / 0.75, 0, 1) * 0.6 + fios * 0.5
    base = raiz + (ponta - raiz) * np.clip(t, 0, 1)[..., None]
    sombra = np.clip(ndl + 0.15 * (1 - z), 0, 1)
    img = base * (0.30 + 0.85 * sombra[..., None])
    return comp(f, img, mm)


def sh_grass():
    n = S * SS
    f = (fundo((0.55, 0.75, 0.95), (0.80, 0.90, 1.0)) * 255).astype(np.uint8)
    im = Image.fromarray(f).resize((n, n))
    d = ImageDraw.Draw(im)
    d.rectangle([0, n * 0.80, n, n], fill=(70, 50, 30))
    rng = np.random.default_rng(5)
    for _ in range(260):
        bx = rng.random() * n
        h = n * (0.30 + 0.35 * rng.random())
        lean = (rng.random() - 0.5) * n * 0.18
        g = rng.random()
        cor = (int(40 + 60 * g), int(120 + 90 * g), int(30 + 30 * g))
        base_y = n * (0.82 + 0.15 * rng.random())
        w = n * 0.012
        d.polygon([(bx - w, base_y), (bx + w, base_y), (bx + lean, base_y - h)], fill=cor)
    return np.asarray(im.resize((S, S), Image.LANCZOS)).astype(np.float32) / 255


def sh_toon_rim():
    f = fundo()
    u, v, z, m, ndl = esfera()
    faixa = np.where(ndl > 0.6, 1.0, np.where(ndl > 0.2, 0.68, 0.40))
    img = np.array([0.95, 0.42, 0.32]) * faixa[..., None]
    rim = np.clip((0.32 - z) * 8, 0, 1)
    img = img + np.array([1.0, 0.95, 0.75]) * rim[..., None] * 0.9
    img = img + (brilho(None, z, u, v, 80) > 0.5)[..., None] * 0.4
    return comp(f, img, m)


def sh_toon_outline():
    f = fundo((0.82, 0.84, 0.80), (0.96, 0.96, 0.93))
    u, v, z, m, ndl = esfera(0.72)
    _u, _v, _z, contorno, _n = esfera(0.80)
    faixa = np.where(ndl > 0.45, 1.0, 0.62)
    img = np.array([0.35, 0.65, 0.95]) * faixa[..., None]
    img = img + (brilho(None, z, u, v, 80) > 0.5)[..., None] * 0.5
    out = comp(f, np.zeros_like(f) + 0.06, contorno)
    return comp(out, img, m)


def sh_dissolve():
    f = fundo()
    u, v, z, m, ndl = esfera()
    rng = np.random.default_rng(9)
    n = luma(blur(rng.random((S, S, 3)).astype(np.float32), 6))
    n = (n - n.min()) / (n.max() - n.min())
    corte = np.quantile(n[m > 0.5], 0.45)
    vivo = n > corte
    borda = (n > corte - 0.05) & ~vivo
    img = np.array([0.70, 0.72, 0.80]) * (0.25 + 0.8 * ndl[..., None])
    img = img + brilho(None, z, u, v)[..., None] * 0.6
    img[borda] = (1.0, 0.6, 0.15)
    out = comp(f, img, m * (vivo | borda))
    glow = np.where((borda & (m > 0))[..., None], np.array([1.0, 0.45, 0.05]), 0.0).astype(np.float32)
    return out + blur(glow, 5) * 1.2


def sh_water():
    f = fundo((0.55, 0.72, 0.92), (0.95, 0.85, 0.75))
    y, x = np.mgrid[0:S, 0:S].astype(np.float32)
    hor = S * 0.36
    t = np.clip((y - hor) / (S - hor), 0, 1)
    k = 1 + t * 3  # ondas maiores perto da câmera
    onda = np.sin(x / (6 * k) + y / (2.5 * k)) * 0.6 + np.sin(x / (3.5 * k) - y / (2 * k)) * 0.4
    perto, longe = np.array([0.03, 0.22, 0.40]), np.array([0.45, 0.70, 0.85])
    agua = longe * (1 - t[..., None]) + perto * t[..., None]
    agua = agua + onda[..., None] * 0.06 + (onda[..., None] > 0.75) * (0.35 * (1 - t[..., None] * 0.5))
    return np.where((y > hor)[..., None], agua, f)


def sh_wind_leaves():
    n = S * SS
    f = (fundo((0.55, 0.78, 0.95), (0.85, 0.93, 1.0)) * 255).astype(np.uint8)
    im = Image.fromarray(f).resize((n, n))
    d = ImageDraw.Draw(im)
    d.line([(n * 0.55, n), (n * 0.50, n * 0.45)], fill=(90, 60, 35), width=int(n * 0.05))
    rng = np.random.default_rng(3)
    for _ in range(90):
        cx, cy = n * (0.25 + 0.55 * rng.random()), n * (0.12 + 0.42 * rng.random())
        a = rng.random() * np.pi
        w, h = n * 0.06, n * 0.025
        pts = [(cx + np.cos(t) * w * np.cos(a) - np.sin(t) * h * np.sin(a),
                cy + np.cos(t) * w * np.sin(a) + np.sin(t) * h * np.cos(a))
               for t in np.linspace(0, 2 * np.pi, 16)]
        g = int(110 + 110 * rng.random())
        d.polygon(pts, fill=(int(g * 0.35), g, int(g * 0.3)))
    for k in range(3):
        y0 = n * (0.20 + k * 0.17)
        d.arc([n * 0.02, y0, n * 0.26, y0 + n * 0.10], 200, 340, fill=(255, 255, 255), width=int(n * 0.012))
    return np.asarray(im.resize((S, S), Image.LANCZOS)).astype(np.float32) / 255


def sh_triplanar():
    # cubo em vista isométrica com o mesmo xadrez nas três faces, sem costura
    n = S * SS
    f = (fundo() * 255).astype(np.uint8)
    im = Image.fromarray(f).resize((n, n))
    d = ImageDraw.Draw(im)
    c = (n * 0.5, n * 0.45)
    a = n * 0.30
    ex = (a * 0.866, a * 0.5)  # eixo x
    ey = (-a * 0.866, a * 0.5)  # eixo y
    ez = (0, -a)  # eixo z
    baixo = (0, a)

    def p(o, u, v):
        return (c[0] + o[0] + u[0] + v[0], c[1] + o[1] + u[1] + v[1])

    dx = (ez[0] + ex[0], ez[1] + ex[1])  # bordas da frente do topo
    dy = (ez[0] + ey[0], ez[1] + ey[1])
    faces = (((0, 0), ex, ey, 1.0, ez), ((0, 0), dx, baixo, 0.75, None), ((0, 0), dy, baixo, 0.55, None))
    k = 4
    for base, eu, ev, luz, off in faces:
        o = off if off else (0, 0)
        for i in range(k):
            for j in range(k):
                cor = (240, 170, 60) if (i + j) % 2 == 0 else (90, 55, 25)
                cor = tuple(int(x * luz) for x in cor)
                q = []
                for (di, dj) in ((0, 0), (1, 0), (1, 1), (0, 1)):
                    u = (eu[0] * (i + di) / k, eu[1] * (i + di) / k)
                    v = (ev[0] * (j + dj) / k, ev[1] * (j + dj) / k)
                    q.append(p(o, u, v))
                d.polygon(q, fill=cor)
    return np.asarray(im.resize((S, S), Image.LANCZOS)).astype(np.float32) / 255


def sh_hologram():
    f = fundo((0.01, 0.02, 0.05), (0.04, 0.07, 0.13))
    u, v, z, m, ndl = esfera()
    y = np.mgrid[0:S, 0:S][0]
    linhas = (np.sin(y * 0.55) > 0.2).astype(np.float32)
    rim = np.clip((0.65 - z) * 2.2, 0, 1)
    a = (0.12 + 0.35 * linhas + rim) * m
    cor = np.array([0.25, 0.90, 1.0])
    return f + cor * a[..., None] + blur(cor * (rim * m)[..., None], 7) * 0.7


def icone(desenho, c1=(0.12, 0.14, 0.21), c2=(0.27, 0.31, 0.44)):
    n = S * SS
    f = (fundo(c1, c2) * 255).astype(np.uint8)
    im = Image.fromarray(f).resize((n, n))
    desenho(ImageDraw.Draw(im), n)
    return np.asarray(im.resize((S, S), Image.LANCZOS)).astype(np.float32) / 255


def boneco(d, n, x, y, s=1.0, cor=(255, 205, 80)):
    r = n * 0.06 * s
    d.ellipse([x - r, y - r, x + r, y + r], fill=cor)
    d.rounded_rectangle([x - r * 1.1, y + r * 1.25, x + r * 1.1, y + r * 4], r * 0.6, fill=cor)


def tecla(d, n, x, y, txt):
    d.rounded_rectangle([n * (x - .09), n * (y - .09), n * (x + .09), n * (y + .09)], n * .03,
                        fill=(235, 238, 245), outline=(150, 155, 170), width=int(n * .008))
    d.text((n * x, n * y), txt, fill=(40, 45, 60), font_size=int(n * .1), anchor="mm")


def lg_walk(d, n):
    for k, x, y in (("W", .5, .2), ("A", .29, .41), ("S", .5, .41), ("D", .71, .41)):
        tecla(d, n, x, y, k)
    boneco(d, n, n * .5, n * .66, 0.85)


def lg_jump(d, n):
    d.rectangle([0, n * .86, n, n], fill=(70, 160, 80))
    d.arc([n * .12, n * .22, n * .88, n * 1.3], 200, 340, fill=(255, 255, 255), width=int(n * .014))
    boneco(d, n, n * .5, n * .17, 0.85)


def lg_collect(d, n):
    for x, y, s in ((.5, .44, .22), (.18, .22, .08), (.82, .28, .1), (.8, .74, .07), (.2, .72, .06)):
        d.ellipse([n * (x - s), n * (y - s), n * (x + s), n * (y + s)], fill=(250, 200, 40),
                  outline=(190, 130, 20), width=int(n * .015))
    d.text((n * .5, n * .44), "$", fill=(170, 110, 15), font_size=int(n * .24), anchor="mm")
    d.text((n * .5, n * .82), "+10", fill=(255, 255, 255), font_size=int(n * .12), anchor="mm")


def lg_health(d, n):
    x, y, r = n * .5, n * .36, n * .15
    cor = (230, 50, 65)
    d.ellipse([x - 2 * r, y - r, x, y + r], fill=cor)
    d.ellipse([x, y - r, x + 2 * r, y + r], fill=cor)
    d.polygon([(x - 1.93 * r, y + r * .35), (x + 1.93 * r, y + r * .35), (x, y + r * 2.5)], fill=cor)
    d.rounded_rectangle([n * .12, n * .8, n * .88, n * .89], n * .03, fill=(60, 30, 35))
    d.rounded_rectangle([n * .12, n * .8, n * .58, n * .89], n * .03, fill=(90, 220, 90))


def lg_door(d, n):
    d.rectangle([n * .38, n * .14, n * .78, n * .92], fill=(150, 95, 50), outline=(80, 50, 25), width=int(n * .02))
    d.ellipse([n * .67, n * .52, n * .72, n * .57], fill=(240, 200, 60))
    w = int(n * .028)
    d.ellipse([n * .06, n * .58, n * .2, n * .72], outline=(250, 210, 60), width=w)
    d.line([(n * .2, n * .65), (n * .34, n * .65)], fill=(250, 210, 60), width=w)
    d.line([(n * .3, n * .65), (n * .3, n * .72)], fill=(250, 210, 60), width=w)


def lg_platform(d, n):
    d.rounded_rectangle([n * .3, n * .52, n * .7, n * .62], n * .02, fill=(180, 190, 210))
    w = int(n * .016)
    for s in (-1, 1):
        x0 = n * .5 + s * n * .33
        d.line([(n * .5 + s * n * .2, n * .75), (x0, n * .75)], fill=(255, 255, 255), width=w)
        d.polygon([(x0 + s * n * .05, n * .75), (x0, n * .71), (x0, n * .79)], fill=(255, 255, 255))
    boneco(d, n, n * .5, n * .26, 0.65)


def ui_menu(d, n):
    d.text((n * .5, n * .14), "MY GAME", fill=(255, 215, 110), font_size=int(n * .11), anchor="mm")
    for i, t in enumerate(("Play", "Options", "Quit")):
        y = n * (.32 + i * .19)
        d.rounded_rectangle([n * .22, y, n * .78, y + n * .13], n * .04,
                            fill=(90, 140, 235) if i == 0 else (62, 72, 100))
        d.text((n * .5, y + n * .065), t, fill=(255, 255, 255), font_size=int(n * .075), anchor="mm")


def ui_hud(d, n):
    d.rectangle([0, 0, n, n * .62], fill=(95, 160, 210))
    d.rectangle([0, n * .62, n, n], fill=(80, 145, 70))
    d.rounded_rectangle([n * .05, n * .05, n * .48, n * .12], n * .03, fill=(45, 20, 28))
    d.rounded_rectangle([n * .05, n * .05, n * .34, n * .12], n * .03, fill=(235, 60, 60))
    d.ellipse([n * .62, n * .62, n * .95, n * .95], fill=(25, 25, 35), outline=(220, 220, 220), width=int(n * .01))
    d.line([(n * .785, n * .785), (n * .88, n * .68)], fill=(255, 90, 60), width=int(n * .016))
    for i, t in enumerate(("A", "B")):
        x = n * (.08 + i * .15)
        d.ellipse([x, n * .8, x + n * .12, n * .92], fill=(250, 250, 250))
        d.text((x + n * .06, n * .86), t, fill=(30, 30, 30), font_size=int(n * .07), anchor="mm")
    d.rectangle([n * .84, n * .05, n * .865, n * .14], fill=(255, 255, 255))
    d.rectangle([n * .895, n * .05, n * .92, n * .14], fill=(255, 255, 255))


PRESETS = {
    "shader_fur": sh_fur, "shader_grass": sh_grass, "shader_toon_rim": sh_toon_rim,
    "shader_toon_outline": sh_toon_outline, "shader_dissolve": sh_dissolve,
    "shader_water_waves": sh_water, "shader_wind_leaves": sh_wind_leaves,
    "shader_triplanar": sh_triplanar, "shader_hologram": sh_hologram,
    "logic_walk": lambda: icone(lg_walk), "logic_jump": lambda: icone(lg_jump),
    "logic_collect": lambda: icone(lg_collect), "logic_health": lambda: icone(lg_health),
    "logic_door": lambda: icone(lg_door), "logic_platform": lambda: icone(lg_platform),
    "ui_menu": lambda: icone(ui_menu, (0.07, 0.05, 0.15), (0.26, 0.15, 0.36)),
    "ui_hud": lambda: icone(ui_hud),
}


def main():
    for nome, f in PRESETS.items():
        img = np.clip(f(), 0, 1)
        Image.fromarray((img * 255 + 0.5).astype(np.uint8)).save(os.path.join(OUT, nome + ".png"))
        print("ok", nome)


if __name__ == "__main__":
    main()
