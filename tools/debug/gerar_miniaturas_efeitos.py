"""Gera as miniaturas da faixa de efeitos do Compositing (Node Editor).

Desenha uma paisagem (céu de fim de tarde, sol, montanhas, mar, ilha com
palmeira) e aplica uma imitação de cada efeito com numpy. As miniaturas só
ilustram o efeito; o resultado real vem dos nós.

Uso: python tools/debug/gerar_miniaturas_efeitos.py
Saída: source/release/scripts/startup/node_effects/<id>.png (256x256)
"""
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

S = 256
SS = 3  # supersampling do desenho
OUT = os.path.join(os.path.dirname(__file__), "..", "..", "source", "release", "scripts",
                   "startup", "node_effects")
SUN = (0.66, 0.30)  # posição do sol (x, y) em 0..1


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def paisagem():
    n = S * SS
    im = Image.new("RGB", (n, n))
    d = ImageDraw.Draw(im)
    horizonte = int(n * 0.62)
    # céu: azul em cima, laranja/rosa perto do horizonte
    topo, meio, baixo = (38, 52, 120), (196, 92, 140), (255, 170, 90)
    for y in range(horizonte):
        t = y / horizonte
        c = lerp(topo, meio, t / 0.6) if t < 0.6 else lerp(meio, baixo, (t - 0.6) / 0.4)
        d.line([(0, y), (n, y)], fill=c)
    # sol com halo
    sx, sy, r = SUN[0] * n, SUN[1] * n, n * 0.075
    halo = Image.new("L", (n, n), 0)
    ImageDraw.Draw(halo).ellipse([sx - r * 2.2, sy - r * 2.2, sx + r * 2.2, sy + r * 2.2], fill=110)
    halo = halo.filter(ImageFilter.GaussianBlur(n * 0.04))
    im = Image.composite(Image.new("RGB", (n, n), (255, 225, 150)), im, halo)
    d = ImageDraw.Draw(im)
    d.ellipse([sx - r, sy - r, sx + r, sy + r], fill=(255, 246, 210))
    # montanhas em duas camadas
    rng = np.random.default_rng(7)
    for base, amp, col, seed in ((0.50, 0.16, (110, 62, 120), 3), (0.57, 0.10, (64, 38, 86), 11)):
        xs = np.linspace(0, n, 40)
        rs = np.random.default_rng(seed)
        ys = n * base - n * amp * np.abs(np.sin(xs / n * 7 + seed)) * (0.6 + 0.4 * rs.random(40))
        d.polygon([(0, horizonte)] + list(zip(xs, ys)) + [(n, horizonte)], fill=col)
    # mar com reflexo do sol
    for y in range(horizonte, n):
        t = (y - horizonte) / (n - horizonte)
        d.line([(0, y), (n, y)], fill=lerp((200, 110, 120), (30, 40, 90), t))
    for i in range(14):
        y = horizonte + 4 * SS + i * (n - horizonte) / 15
        w = n * (0.10 - i * 0.004) * (0.7 + 0.6 * rng.random())
        d.rectangle([sx - w, y, sx + w, y + 2 * SS], fill=(255, 210, 140))
    # ilha com palmeira (silhueta) à esquerda
    ix, iy = n * 0.24, horizonte + n * 0.05
    d.ellipse([ix - n * 0.17, iy - n * 0.035, ix + n * 0.17, iy + n * 0.035], fill=(28, 18, 40))
    pts = [(ix - n * 0.02 + n * 0.03 * (k / 10) ** 2, iy - n * 0.36 * k / 10) for k in range(11)]
    d.line(pts, fill=(28, 18, 40), width=int(n * 0.016))
    tx, ty = pts[-1]
    for ang in (-160, -130, -95, -55, -20, 10):
        a = np.radians(ang)
        ex, ey = tx + np.cos(a) * n * 0.13, ty + np.sin(a) * n * 0.05 + n * 0.05
        mx, my = (tx + ex) / 2, min(ty, ey) - n * 0.025
        d.line([(tx, ty), (mx, my), (ex, ey)], fill=(28, 18, 40), width=int(n * 0.014), joint="curve")
    im = im.resize((S, S), Image.LANCZOS)
    return np.asarray(im).astype(np.float32) / 255.0


def blur(a, r):
    im = Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8))
    return np.asarray(im.filter(ImageFilter.GaussianBlur(r))).astype(np.float32) / 255.0


def luma(a):
    return a @ np.array([0.299, 0.587, 0.114], np.float32)


def grade_uv():
    y, x = np.mgrid[0:S, 0:S].astype(np.float32)
    return (x + 0.5) / S * 2 - 1, (y + 0.5) / S * 2 - 1


def amostra(a, u, v):
    # u, v em -1..1; bilinear com borda presa
    x = np.clip((u + 1) * 0.5 * S - 0.5, 0, S - 1)
    y = np.clip((v + 1) * 0.5 * S - 0.5, 0, S - 1)
    x0, y0 = np.floor(x).astype(int), np.floor(y).astype(int)
    x1, y1 = np.minimum(x0 + 1, S - 1), np.minimum(y0 + 1, S - 1)
    fx, fy = (x - x0)[..., None], (y - y0)[..., None]
    top = a[y0, x0] * (1 - fx) + a[y0, x1] * fx
    bot = a[y1, x0] * (1 - fx) + a[y1, x1] * fx
    return top * (1 - fy) + bot * fy


def vignette(a):
    u, v = grade_uv()
    m = np.clip(1.25 - (u * u + v * v) * 0.62, 0, 1) ** 1.6
    return a * m[..., None]


def chromatic(a):
    u, v = grade_uv()
    out = a.copy()
    for ch, k in ((0, 1.045), (2, 0.955)):
        out[..., ch] = amostra(a, u * k, v * k)[..., ch]
    return out


def fisheye(a):
    u, v = grade_uv()
    r2 = u * u + v * v
    k = 0.72 + 0.20 * r2
    return amostra(a, u * k, v * k)


def film_grain(a):
    rng = np.random.default_rng(1)
    g = rng.normal(0, 0.06, (S, S)).astype(np.float32)
    base = a * 0.85 + luma(a)[..., None] * 0.15
    return base + g[..., None]


def sepia(a):
    l = luma(a)[..., None]
    escuro, claro = np.array([0.18, 0.10, 0.05]), np.array([1.0, 0.86, 0.62])
    return escuro + (claro - escuro) * l ** 0.9


def split_toning(a):
    l = luma(a)[..., None]
    sombra, luz = np.array([0.0, 0.10, 0.28]), np.array([0.22, 0.10, -0.08])
    return a * 0.85 + sombra * (1 - l) ** 2 + luz * l ** 2


def tune(a):
    l = luma(a)[..., None]
    a = l + (a - l) * 1.55
    return (a - 0.5) * 1.25 + 0.5


def bloom(a):
    claro = np.clip(a - 0.62, 0, 1) * 2.4
    return a + blur(claro, 10) * 1.1 + blur(claro, 3) * 0.5


def sun_beams(a):
    claro = np.clip(a - 0.62, 0, 1) * 3.0
    cu, cv = SUN[0] * 2 - 1, SUN[1] * 2 - 1
    u, v = grade_uv()
    acc = np.zeros_like(a)
    n = 40
    for i in range(n):
        t = 1 - i / n * 0.55
        acc += amostra(claro, cu + (u - cu) * t, cv + (v - cv) * t) * (1 - i / n)
    return a + acc / n * 3.5


def pixel_art(a):
    im = Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8))
    im = im.resize((S // 8, S // 8), Image.BOX)
    return np.asarray(im.resize((S, S), Image.NEAREST)).astype(np.float32) / 255.0


def outline(a):
    l = luma(blur(a, 0.6))
    gx = np.abs(np.roll(l, -1, 1) - np.roll(l, 1, 1))
    gy = np.abs(np.roll(l, -1, 0) - np.roll(l, 1, 0))
    e = np.clip((gx + gy) * 6 - 0.25, 0, 1)
    e[0], e[-1], e[:, 0], e[:, -1] = 0, 0, 0, 0
    return a * (1 - e[..., None])


def motion(a):
    u, v = grade_uv()
    acc = np.zeros_like(a)
    n = 24
    for i in range(n):
        k = 1 - i / n * 0.16
        acc += amostra(a, u * k, v * k)
    return acc / n


EFEITOS = {
    "vignette": vignette, "chromatic": chromatic, "fisheye": fisheye, "film_grain": film_grain,
    "sepia": sepia, "split_toning": split_toning, "tune": tune, "bloom": bloom,
    "sun_beams": sun_beams, "pixel_art": pixel_art, "outline": outline, "motion": motion,
}


def main():
    base = paisagem()
    # a base fica um pouco apagada para o Tune Image mostrar diferença
    l = luma(base)[..., None]
    base = l + (base - l) * 0.85
    os.makedirs(OUT, exist_ok=True)
    for nome, f in EFEITOS.items():
        img = np.clip(f(base), 0, 1)
        Image.fromarray((img * 255 + 0.5).astype(np.uint8)).save(os.path.join(OUT, nome + ".png"))
        print("ok", nome)


if __name__ == "__main__":
    main()
