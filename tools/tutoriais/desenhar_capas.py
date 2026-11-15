"""Desenha as capas (miniatura.png) dos tutoriais: ilustrações simples e planas da aula.

    python tools/tutoriais/desenhar_capas.py [nome_do_tutorial ...]

Sem nomes, desenha todas as que estão em CAPAS.  Cada capa é 640x360, desenhada em 4x e reduzida
(bordas suaves).  Estilo: fundo claro com uma cor por aula, o cubo dourado da engine e poucos
elementos que contam o que se aprende.
"""
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

RAIZ = Path(__file__).resolve().parents[2]
PASTA = RAIZ / "source/release/scripts/tutoriais"
W, H, K = 640, 360, 4  # tamanho final e supersampling

DOURADO = ((255, 214, 120), (232, 172, 60), (186, 128, 30))  # topo, frente-esquerda, frente-direita
TINTA = (40, 44, 56)
BRANCO = (255, 255, 255)
VERMELHO, VERDE, AZUL = (226, 86, 86), (98, 184, 110), (72, 136, 220)


class Tela:
    def __init__(self, fundo, fundo2=None):
        self.img = Image.new("RGB", (W * K, H * K), fundo)
        self.d = ImageDraw.Draw(self.img)
        if fundo2:  # degradê vertical suave
            for y in range(H * K):
                t = y / (H * K)
                cor = tuple(int(a + (b - a) * t) for a, b in zip(fundo, fundo2))
                self.d.line([(0, y), (W * K, y)], fill=cor)

    def p(self, pts):
        return [(x * K, y * K) for x, y in pts]

    def poli(self, pts, cor, contorno=None, largura=0):
        self.d.polygon(self.p(pts), fill=cor)
        if contorno:
            self.linha(pts + [pts[0]], contorno, largura)

    def linha(self, pts, cor, largura=3):
        self.d.line(self.p(pts), fill=cor, width=int(largura * K), joint="curve")
        r = largura * K / 2
        for x, y in self.p(pts):  # pontas redondas
            self.d.ellipse([x - r, y - r, x + r, y + r], fill=cor)

    def ret(self, x0, y0, x1, y1, cor, raio=0, contorno=None, largura=0):
        self.d.rounded_rectangle([x0 * K, y0 * K, x1 * K, y1 * K], radius=raio * K, fill=cor,
                                 outline=contorno, width=int(largura * K))

    def circulo(self, cx, cy, r, cor, contorno=None, largura=0):
        self.d.ellipse([(cx - r) * K, (cy - r) * K, (cx + r) * K, (cy + r) * K], fill=cor,
                       outline=contorno, width=int(largura * K))

    def arco(self, cx, cy, r, a0, a1, cor, largura=4):
        self.d.arc([(cx - r) * K, (cy - r) * K, (cx + r) * K, (cy + r) * K], a0, a1, fill=cor,
                   width=int(largura * K))

    def seta(self, x0, y0, x1, y1, cor, largura=6, ponta=16):
        a = math.atan2(y1 - y0, x1 - x0)
        bx, by = x1 - ponta * 0.8 * math.cos(a), y1 - ponta * 0.8 * math.sin(a)
        self.linha([(x0, y0), (bx, by)], cor, largura)
        esq = (x1 - ponta * math.cos(a - 0.5), y1 - ponta * math.sin(a - 0.5))
        dir_ = (x1 - ponta * math.cos(a + 0.5), y1 - ponta * math.sin(a + 0.5))
        self.poli([(x1, y1), esq, dir_], cor)

    def grade(self, quad, n, c1, c2):
        """Divide um quadrilátero em n x n casas alternando duas cores (xadrez)."""
        a, b, c, d = quad
        def pt(u, v):
            x0, y0 = a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u
            x1, y1 = d[0] + (c[0] - d[0]) * u, d[1] + (c[1] - d[1]) * u
            return (x0 + (x1 - x0) * v, y0 + (y1 - y0) * v)
        for i in range(n):
            for j in range(n):
                q = [pt(i / n, j / n), pt((i + 1) / n, j / n), pt((i + 1) / n, (j + 1) / n), pt(i / n, (j + 1) / n)]
                self.poli(q, c1 if (i + j) % 2 else c2)

    def camada(self):
        c = Tela.__new__(Tela)
        c.img = Image.new("RGBA", self.img.size, (0, 0, 0, 0))
        c.d = ImageDraw.Draw(c.img)
        return c

    def juntar(self, c, opac=1.0, blur=0):
        img = c.img.filter(ImageFilter.GaussianBlur(blur * K)) if blur else c.img
        if opac < 1:
            img.putalpha(img.getchannel("A").point(lambda v: int(v * opac)))
        self.img.paste(img, (0, 0), img)

    def curva(self, p0, p1, p2, p3, n=40):
        pts = []
        for i in range(n + 1):
            u = i / n
            pts.append(tuple((1 - u) ** 3 * a + 3 * (1 - u) ** 2 * u * b + 3 * (1 - u) * u * u * c + u ** 3 * d
                             for a, b, c, d in zip(p0, p1, p2, p3)))
        return pts

    def estrela(self, cx, cy, r, cor):
        pts = []
        for i in range(10):
            a = math.radians(-90 + i * 36)
            rr = r if i % 2 == 0 else r * 0.45
            pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
        self.poli(pts, cor)

    def nuvem(self, cx, cy, s, cor):
        for dx, dy, r in ((-0.9, 0.15, 0.55), (-0.3, -0.25, 0.75), (0.45, -0.1, 0.65), (1.0, 0.2, 0.45)):
            self.circulo(cx + dx * s, cy + dy * s, r * s, cor)
        self.ret(cx - 1.3 * s, cy + 0.1 * s, cx + 1.35 * s, cy + 0.65 * s, cor, 0.3 * s)

    def texto(self, x, y, w, cor, n=1, gap=14, alt=6):
        """Linhas de texto estilizadas (barras arredondadas)."""
        for i in range(n):
            ww = w * (0.65 if i == n - 1 and n > 1 else 1)
            self.ret(x, y + i * gap, x + ww, y + i * gap + alt, cor, alt / 2)

    def no(self, x, y, w, h, cor, entradas=1, saidas=1):
        """Nó de editor: cabeçalho colorido, corpo e soquetes."""
        self.ret(x + 3, y + 4, x + w + 3, y + h + 4, (150, 150, 160), 8)
        self.ret(x, y, x + w, y + h, (70, 76, 92), 8)
        self.ret(x, y, x + w, y + 20, cor, 8)
        self.ret(x, y + 12, x + w, y + 20, cor)
        self.texto(x + 10, y + 32, w - 30, (140, 148, 168), max(1, (h - 36) // 16))
        for i in range(entradas):
            self.circulo(x, y + 34 + i * 16, 5, (230, 200, 90), TINTA, 1.5)
        for i in range(saidas):
            self.circulo(x + w, y + 34 + i * 16, 5, (230, 200, 90), TINTA, 1.5)

    def cubo(self, cx, cy, s, cores=DOURADO, contorno=TINTA, girar=0.0, xadrez=0):
        """Cubo isométrico com o centro da face de cima em (cx, cy - s/2)."""
        def v(ang, raio=s):
            return (cx + raio * math.cos(ang), cy + raio * 0.5 * math.sin(ang))
        a = math.radians(girar)
        topo = [v(a + math.radians(d)) for d in (-90, 0, 90, 180)]
        topo = [(x, y - s * 0.5) for x, y in topo]
        baixo = [(x, y + s) for x, y in topo]
        # faces visíveis: as duas que ficam para a frente (maior y médio)
        faces = []
        for i in range(4):
            j = (i + 1) % 4
            faces.append(([topo[i], topo[j], baixo[j], baixo[i]], (topo[i][1] + topo[j][1]) / 2, (topo[i][0] + topo[j][0]) / 2))
        faces.sort(key=lambda f: f[1])
        for quad, _, mx in faces[2:]:
            cor = cores[1] if mx < cx else cores[2]
            self.poli(quad, cor)
            if xadrez:
                self.grade(quad, xadrez, cor, tuple(int(v * 0.45) for v in cor))
            self.linha(quad + [quad[0]], contorno, 3)
        self.poli(topo, cores[0])
        if xadrez:
            self.grade(topo, xadrez, cores[0], tuple(int(v * 0.55) for v in cores[0]))
        self.linha(topo + [topo[0]], contorno, 3)

    def sombra(self, cx, cy, rx, ry, cor):
        self.d.ellipse([(cx - rx) * K, (cy - ry) * K, (cx + rx) * K, (cy + ry) * K], fill=cor)

    def chao(self, cx, cy, s, cor, contorno=None):
        self.poli([(cx, cy - s * 0.5), (cx + s, cy), (cx, cy + s * 0.5), (cx - s, cy)], cor, contorno, 3)

    def salvar(self, caminho):
        self.img.resize((W, H), Image.LANCZOS).save(caminho)


# ---------------------------------------------------------------- capas

def basico_interface(t):
    t = Tela((226, 236, 250), (200, 216, 240))
    # Janela do editor: barra do topo, Outliner à esquerda, Properties à direita, 3D View e área de baixo.
    t.ret(70, 40, 570, 320, (52, 58, 72), 14)
    t.ret(70, 40, 570, 66, (38, 42, 54), 14)
    t.ret(70, 56, 570, 66, (38, 42, 54))
    for i, c in enumerate(((236, 96, 90), (240, 190, 70), (110, 200, 120))):
        t.circulo(90 + i * 18, 53, 5, c)
    t.ret(80, 76, 180, 230, (70, 78, 96), 6)            # Outliner
    for i in range(5):
        t.ret(90, 88 + i * 24, 90 + (80 if i % 2 == 0 else 60), 100 + i * 24, (120, 130, 152), 4)
    t.ret(460, 76, 560, 310, (70, 78, 96), 6)           # Properties
    for i in range(7):
        t.ret(470, 88 + i * 30, 550, 104 + i * 30, (120, 130, 152), 4)
    t.ret(190, 76, 450, 230, (150, 176, 214), 6)        # 3D View
    t.chao(320, 196, 90, (205, 214, 228))
    t.cubo(320, 160, 34)
    t.ret(80, 240, 450, 310, (70, 78, 96), 6)           # área de baixo (Logic Editor)
    for i, c in enumerate(((240, 160, 70), (110, 170, 230), (130, 200, 130))):
        t.ret(92 + i * 120, 254, 92 + i * 120 + 100, 296, c, 6)
    # Cursor apontando para o Outliner
    t.poli([(150, 108), (150, 136), (157, 129), (163, 142), (168, 140), (162, 127), (172, 127)], BRANCO, TINTA, 2)
    return t


def basico_transformar(t):
    t = Tela((255, 240, 214), (250, 222, 180))
    t.sombra(320, 268, 120, 30, (230, 200, 150))
    t.cubo(320, 160, 70, girar=20)
    # G: seta para cima; R: arco girando; S: setas nos cantos
    t.seta(320, 112, 320, 40, AZUL, 7, 22)
    t.arco(320, 210, 150, 200, 250, VERMELHO, 7)
    t.seta(196, 155, 206, 132, VERMELHO, 7, 20)
    t.seta(420, 230, 470, 262, VERDE, 7, 20)
    t.seta(220, 230, 170, 262, VERDE, 7, 20)
    for x, y, letra, cor in ((372, 52, "G", AZUL), (150, 120, "R", VERMELHO), (494, 236, "S", VERDE)):
        t.circulo(x, y, 20, cor)
        _letra(t, x, y, letra)
    return t


def basico_primeiro_jogo(t):
    t = Tela((214, 240, 226), (176, 222, 200))
    t.chao(320, 280, 220, (120, 190, 150), (80, 150, 110))
    t.sombra(320, 280, 50, 14, (90, 160, 120))
    t.cubo(320, 96, 46, girar=25)
    for i, x in enumerate((282, 320, 358)):  # linhas de queda
        t.linha([(x, 30 - i % 2 * 8), (x, 52 - i % 2 * 8)], (90, 150, 120), 4)
    t.seta(320, 168, 320, 236, (60, 120, 90), 6, 18)
    # Botão P (jogar)
    t.ret(470, 40, 590, 92, BRANCO, 12, (60, 120, 90), 3)
    t.poli([(498, 52), (498, 80), (520, 66)], (60, 120, 90))
    _letra(t, 556, 66, "P", (60, 120, 90))
    return t


def _letra(t, x, y, letra, cor=BRANCO):
    """Letra desenhada com traços (sem depender de fonte instalada)."""
    s = 9
    tracos = {
        "G": [[(x + s * .7, y - s * .7), (x - s * .1, y - s), (x - s * .8, y - s * .4), (x - s * .8, y + s * .4),
               (x - s * .1, y + s), (x + s * .7, y + s * .6), (x + s * .7, y + s * .1), (x + s * .1, y + s * .1)]],
        "R": [[(x - s * .6, y + s), (x - s * .6, y - s), (x + s * .3, y - s), (x + s * .7, y - s * .5),
               (x + s * .3, y), (x - s * .6, y)], [(x + s * .05, y), (x + s * .7, y + s)]],
        "S": [[(x + s * .7, y - s * .7), (x, y - s), (x - s * .7, y - s * .5), (x - s * .4, y - s * .05),
               (x + s * .4, y + s * .05), (x + s * .7, y + s * .5), (x, y + s), (x - s * .7, y + s * .7)]],
        "P": [[(x - s * .6, y + s), (x - s * .6, y - s), (x + s * .3, y - s), (x + s * .7, y - s * .5),
               (x + s * .3, y), (x - s * .6, y)]],
    }
    for traco in tracos[letra]:
        t.linha(traco, cor, 3.2)


CINZA = (70, 76, 92)
ROXO = (150, 110, 210)
CIANO = (80, 200, 220)
LARANJA = (240, 150, 60)


def _tela(t, x0, y0, x1, y1, fundo=(150, 176, 214)):
    """Monitor/janela de jogo: moldura escura e área de imagem."""
    t.ret(x0, y0, x1, y1, (52, 58, 72), 12)
    t.ret(x0 + 10, y0 + 10, x1 - 10, y1 - 10, fundo, 6)


def _play(t, cx, cy, r, cor=BRANCO, fundo=None):
    if fundo:
        t.circulo(cx, cy, r, fundo)
    t.poli([(cx - r * .35, cy - r * .5), (cx - r * .35, cy + r * .5), (cx + r * .55, cy)], cor)


def _pessoa(t, x, y, pose, cor=TINTA):
    """Bonequinho em traço; y é o chão."""
    if pose == "pe":
        t.circulo(x, y - 118, 15, cor)
        t.linha([(x, y - 100), (x, y - 50)], cor, 9)
        t.linha([(x - 20, y), (x, y - 50), (x + 20, y)], cor, 9)
        t.linha([(x - 24, y - 70), (x, y - 92), (x + 24, y - 70)], cor, 9)
    elif pose == "corre":
        t.circulo(x + 12, y - 112, 15, cor)
        t.linha([(x + 6, y - 94), (x - 4, y - 48)], cor, 9)
        t.linha([(x - 34, y - 20), (x - 4, y - 48), (x + 18, y - 22), (x + 10, y)], cor, 9)
        t.linha([(x - 26, y - 64), (x + 4, y - 86), (x + 32, y - 70)], cor, 9)
    elif pose == "abaixa":
        t.circulo(x + 6, y - 78, 15, cor)
        t.linha([(x, y - 60), (x - 10, y - 30)], cor, 9)
        t.linha([(x - 10, y - 30), (x + 18, y - 22), (x + 14, y)], cor, 9)
        t.linha([(x - 10, y - 30), (x - 26, y)], cor, 9)
        t.linha([(x + 2, y - 52), (x + 28, y - 40)], cor, 9)
    else:  # rasteja
        t.circulo(x + 50, y - 26, 14, cor)
        t.linha([(x + 34, y - 18), (x - 20, y - 12), (x - 50, y - 4)], cor, 9)
        t.linha([(x + 30, y - 16), (x + 58, y - 2)], cor, 9)


def _esfera(t, cx, cy, r, lados, cor, aneis):
    pts = [(cx + r * math.cos(2 * math.pi * i / lados), cy + r * math.sin(2 * math.pi * i / lados)) for i in range(lados)]
    t.poli(pts, cor, TINTA, 3)
    for k in range(1, aneis):
        d = -r + 2 * r * k / aneis
        w = math.sqrt(max(r * r - d * d, 0))
        t.linha([(cx - w, cy + d), (cx + w, cy + d)], TINTA, 1.6)
        t.linha([(cx + d, cy - w), (cx + d, cy + w)], TINTA, 1.6)


def _casa(t, x, base, w, h, parede, telhado):
    t.ret(x, base - h, x + w, base, parede, 3, TINTA, 3)
    t.poli([(x - 10, base - h), (x + w / 2, base - h - w * 0.45), (x + w + 10, base - h)], telhado, TINTA, 3)
    t.ret(x + w * 0.38, base - h * 0.55, x + w * 0.62, base, (120, 80, 50), 2, TINTA, 2)
    t.ret(x + w * 0.1, base - h * 0.75, x + w * 0.3, base - h * 0.5, (190, 225, 250), 2, TINTA, 2)
    t.ret(x + w * 0.7, base - h * 0.75, x + w * 0.9, base - h * 0.5, (190, 225, 250), 2, TINTA, 2)


def camera_foco(t):
    t = Tela((222, 232, 246), (196, 210, 236))
    fundo = t.camada()
    for x, y, r, c in ((90, 90, 50, (170, 190, 230)), (540, 80, 60, (240, 200, 160)), (470, 290, 44, (180, 220, 190)),
                       (150, 280, 40, (230, 180, 200)), (600, 220, 36, (200, 180, 240))):
        fundo.circulo(x, y, r, c)
    t.juntar(fundo, 1.0, 10)
    t.sombra(330, 262, 70, 16, (170, 180, 205))
    t.cubo(330, 170, 56, girar=15)
    for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):  # cantoneiras do foco
        x, y = 330 + sx * 100, 175 + sy * 95
        t.linha([(x, y - sy * 24), (x, y), (x - sx * 24, y)], AZUL, 6)
    t.ret(40, 150, 120, 205, (52, 58, 72), 10)  # câmera
    t.circulo(120, 177, 18, (52, 58, 72))
    t.circulo(121, 177, 10, (120, 170, 230))
    t.ret(56, 138, 82, 150, (52, 58, 72), 4)
    return t


def casas_brasileiras(t):
    t = Tela((206, 232, 250), (240, 246, 252))
    t.circulo(560, 70, 32, (255, 214, 120))
    t.ret(0, 270, 640, 360, (150, 150, 158))
    t.ret(0, 262, 640, 274, (210, 200, 180))
    for x in range(20, 640, 70):
        t.ret(x, 312, x + 36, 318, (240, 240, 240), 3)
    for x, w, h, p, tl in ((50, 120, 90, (250, 210, 120), (200, 90, 60)), (196, 110, 120, (140, 200, 170), (180, 80, 60)),
                           (330, 130, 80, (240, 150, 160), (190, 100, 70)), (486, 110, 105, (150, 190, 240), (200, 90, 60))):
        _casa(t, x, 264, w, h, p, tl)
    return t


def ceu_entardecer(t):
    t = Tela((60, 50, 110), (250, 160, 110))
    for x, y, r in ((80, 50, 6), (180, 30, 4), (300, 60, 5), (420, 26, 6), (560, 50, 4), (610, 100, 5), (40, 120, 4)):
        t.estrela(x, y, r * 1.6, (255, 240, 200))
    t.circulo(320, 290, 80, (255, 200, 110))
    t.nuvem(150, 170, 34, (250, 190, 170))
    t.nuvem(500, 150, 40, (240, 170, 160))
    t.ret(0, 280, 640, 360, (90, 60, 90))
    t.cubo(470, 240, 30, cores=((120, 90, 120), (90, 60, 100), (70, 46, 80)))
    return t


def chuva_nevoa(t):
    t = Tela((150, 166, 190), (200, 210, 222))
    t.ret(0, 280, 640, 360, (120, 136, 150))
    t.sombra(320, 280, 70, 14, (100, 114, 128))
    t.cubo(320, 190, 52)
    for i in range(46):  # gotas
        x, y = (i * 137) % 640, (i * 71) % 300 + 20
        t.linha([(x, y), (x - 8, y + 22)], (230, 240, 255), 3)
    nev = t.camada()
    for y in (230, 260, 300):
        nev.ret(-40, y, 680, y + 46, (240, 244, 250), 23)
    t.juntar(nev, 0.6, 8)
    t.nuvem(170, 60, 50, (110, 124, 146))
    t.nuvem(470, 50, 56, (120, 134, 156))
    return t


def compositing_efeitos(t):
    t = Tela((236, 226, 250), (214, 200, 240))
    _tela(t, 100, 40, 540, 300, (150, 176, 214))
    t.chao(320, 230, 120, (205, 214, 228))
    t.cubo(320, 180, 52)
    box = (320 * K, 50 * K, 530 * K, 290 * K)  # metade direita vira pixel art
    pedaco = t.img.crop(box)
    pedaco = pedaco.resize((pedaco.width // 40, pedaco.height // 40), Image.NEAREST).resize(pedaco.size, Image.NEAREST)
    t.img.paste(pedaco, box[:2])
    vin = t.camada()  # vinheta
    vin.ret(110, 50, 530, 290, (20, 20, 40), 6)
    vin.ret(170, 90, 470, 250, (0, 0, 0, 0), 90)
    t.juntar(vin, 0.35, 18)
    t.linha([(320, 46), (320, 294)], BRANCO, 3)
    for i, c in enumerate((LARANJA, ROXO, CIANO)):
        t.circulo(260 + i * 60, 326, 14, c, TINTA, 2)
    return t


def cutscene_abertura(t):
    t = Tela((40, 40, 52), (20, 20, 28))
    t.ret(0, 70, 640, 290, (150, 176, 214))
    t.chao(320, 250, 140, (205, 214, 228))
    t.cubo(320, 190, 50)
    fade = t.camada()
    for i in range(30):
        fade.ret(i * 8, 70, i * 8 + 8, 290, (0, 0, 0, int(230 * (1 - i / 30))))
    t.juntar(fade)
    t.ret(0, 0, 640, 70, (10, 10, 14))
    t.ret(0, 290, 640, 360, (10, 10, 14))
    for x in range(20, 640, 50):  # furos de filme
        t.ret(x, 24, x + 26, 44, (60, 60, 72), 4)
        t.ret(x, 316, x + 26, 336, (60, 60, 72), 4)
    _play(t, 520, 120, 26, BRANCO, LARANJA)
    return t


def decimate_hq(t):
    t = Tela((226, 244, 236), (196, 230, 214))
    _esfera(t, 170, 180, 100, 48, (255, 214, 120), 14)
    t.seta(296, 180, 360, 180, (60, 140, 100), 9, 24)
    _esfera(t, 470, 180, 100, 8, (255, 214, 120), 3)
    return t


def destruicao_bomba(t):
    t = Tela((250, 232, 214), (244, 206, 180))
    t.ret(0, 300, 640, 360, (200, 170, 140))
    buraco = ((2, 3), (3, 3), (3, 4), (4, 4), (2, 4))
    for linha in range(6):  # parede de tijolos com buraco
        for col in range(5):
            if (linha, col) in buraco:
                continue
            x = 60 + col * 52 + (26 if linha % 2 else 0)
            y = 300 - (linha + 1) * 32
            t.ret(x, y, x + 48, y + 28, (200, 110, 80), 3, (130, 70, 50), 2)
    for x, y, a in ((360, 120, 20), (400, 170, -15), (430, 100, 35), (380, 220, 10), (460, 150, -30)):
        q = [(x + 14 * math.cos(math.radians(a + d)), y + 10 * math.sin(math.radians(a + d))) for d in (0, 90, 180, 270)]
        t.poli(q, (200, 110, 80), (130, 70, 50), 2)
    t.circulo(530, 250, 44, (52, 58, 72))
    t.ret(516, 196, 544, 212, (90, 96, 110), 3)
    t.linha(t.curva((530, 198), (540, 170), (570, 180), (580, 150)), (150, 120, 90), 4)
    t.estrela(584, 144, 22, (255, 200, 60))
    t.estrela(584, 144, 11, (255, 250, 220))
    return t


def exportar_desktop(t):
    t = Tela((224, 236, 250), (200, 218, 244))
    _tela(t, 150, 40, 490, 260)
    t.chao(320, 200, 90, (205, 214, 228))
    t.cubo(320, 160, 40)
    t.ret(290, 260, 350, 290, (52, 58, 72))
    t.ret(240, 288, 400, 302, (52, 58, 72), 6)
    t.circulo(70, 150, 44, BRANCO, AZUL, 4)  # selo de janelas
    for x0, y0 in ((48, 128), (72, 128), (48, 152), (72, 152)):
        t.ret(x0, y0, x0 + 20, y0 + 20, AZUL, 2)
    t.circulo(570, 150, 44, BRANCO, TINTA, 4)  # selo de terminal
    t.linha([(548, 136), (562, 150), (548, 164)], TINTA, 5)
    t.linha([(568, 166), (592, 166)], TINTA, 5)
    return t


def exportar_web(t):
    t = Tela((230, 240, 252), (206, 226, 248))
    t.ret(70, 50, 430, 300, BRANCO, 12, (52, 58, 72), 4)  # navegador
    t.ret(70, 50, 430, 82, (52, 58, 72), 12)
    t.ret(70, 70, 430, 82, (52, 58, 72))
    t.ret(130, 60, 400, 74, (120, 130, 152), 7)
    for i, c in enumerate(((236, 96, 90), (240, 190, 70), (110, 200, 120))):
        t.circulo(88 + i * 14, 66, 4, c)
    t.ret(84, 92, 416, 286, (150, 176, 214), 6)
    t.chao(250, 240, 90, (205, 214, 228))
    t.cubo(250, 200, 40)
    t.ret(450, 110, 570, 330, (52, 58, 72), 18)  # celular
    t.ret(460, 128, 560, 312, (150, 176, 214), 8)
    t.cubo(510, 210, 22)
    t.circulo(482, 290, 10, BRANCO)
    t.circulo(540, 290, 10, BRANCO)
    t.circulo(560, 60, 30, BRANCO, AZUL, 4)  # globo
    t.linha([(530, 60), (590, 60)], AZUL, 3)
    t.d.ellipse([548 * K, 30 * K, 572 * K, 90 * K], outline=AZUL, width=3 * K)
    return t


def glsl_node(t):
    t = Tela((232, 236, 248), (206, 214, 236))
    t.no(40, 70, 160, 110, (110, 170, 120), 0, 1)
    t.grade([(70, 130), (170, 130), (170, 170), (70, 170)], 5, (240, 240, 240), (60, 64, 80))
    t.no(250, 110, 150, 90, (200, 110, 80), 1, 1)
    t.linha(t.curva((200, 104), (230, 104), (220, 144), (250, 144)), (230, 200, 90), 4)
    t.linha(t.curva((400, 144), (430, 144), (420, 180), (450, 180)), (230, 200, 90), 4)
    t.sombra(530, 280, 70, 14, (180, 186, 210))
    t.cubo(530, 200, 52, cores=((245, 245, 245), (220, 220, 225), (190, 190, 200)), xadrez=4)
    return t


def lod_automatico(t):
    t = Tela((236, 240, 226), (214, 226, 196))
    t.ret(0, 270, 640, 360, (180, 200, 150))
    for cx, cy, r, lados, an in ((130, 190, 80, 40, 10), (330, 210, 56, 12, 4), (480, 226, 36, 6, 2), (580, 238, 22, 4, 1)):
        _esfera(t, cx, cy, r, lados, (255, 214, 120), an)
    t.seta(80, 320, 600, 320, (110, 130, 90), 5, 18)
    return t


def logica_andar(t):
    t = Tela((228, 236, 250), (204, 216, 240))
    for i, (cor, x) in enumerate((((200, 120, 220), 40), ((120, 170, 230), 210), ((240, 160, 70), 380))):
        t.no(x, 60, 140, 100, cor, 1 if i else 0, 1 if i < 2 else 0)
    t.linha([(180, 94), (210, 94)], (230, 200, 90), 4)
    t.linha([(350, 94), (380, 94)], (230, 200, 90), 4)
    t.chao(260, 290, 140, (205, 214, 228))
    t.cubo(240, 250, 36)
    t.seta(310, 260, 420, 260, AZUL, 8, 22)
    t.ret(470, 220, 540, 290, BRANCO, 10, TINTA, 3)  # tecla
    t.seta(488, 255, 522, 255, TINTA, 6, 16)
    return t


def logica_arvore_andar(t):
    t = Tela((230, 244, 240), (200, 230, 222))
    t.no(40, 50, 130, 80, (110, 170, 120), 0, 1)
    t.no(40, 160, 130, 80, (110, 170, 120), 0, 1)
    t.no(250, 100, 130, 96, (120, 170, 230), 2, 1)
    t.no(460, 110, 130, 80, (240, 160, 70), 1, 0)
    t.linha(t.curva((170, 84), (220, 84), (200, 134), (250, 134)), (230, 200, 90), 4)
    t.linha(t.curva((170, 194), (220, 194), (200, 150), (250, 150)), (230, 200, 90), 4)
    t.linha(t.curva((380, 134), (420, 134), (420, 144), (460, 144)), (230, 200, 90), 4)
    t.cubo(280, 280, 26)
    t.seta(330, 290, 430, 290, AZUL, 7, 20)
    return t


def material_atlas_paleta(t):
    t = Tela((250, 238, 226), (244, 220, 200))
    cores = [(226, 86, 86), (240, 150, 60), (255, 214, 120), (98, 184, 110), (72, 136, 220), (150, 110, 210),
             (80, 200, 220), (240, 150, 190), (120, 90, 70)]
    t.ret(60, 80, 260, 280, BRANCO, 10, TINTA, 3)
    for i, c in enumerate(cores):
        x, y = 74 + (i % 3) * 62, 94 + (i // 3) * 62
        t.ret(x, y, x + 56, y + 56, c, 4)
    t.seta(290, 180, 350, 180, TINTA, 7, 20)
    for (cx, cy), i in zip(((430, 120), (540, 140), (470, 250), (580, 260)), (0, 4, 3, 5)):
        c = cores[i]
        t.cubo(cx, cy, 30, cores=(tuple(min(255, v + 40) for v in c), c, tuple(int(v * .75) for v in c)))
    return t


def microfone_pular(t):
    t = Tela((240, 230, 250), (222, 206, 244))
    t.ret(90, 90, 150, 200, (52, 58, 72), 30)
    t.arco(120, 170, 46, 0, 180, (52, 58, 72), 6)
    t.linha([(120, 216), (120, 250)], (52, 58, 72), 6)
    t.linha([(94, 252), (146, 252)], (52, 58, 72), 6)
    for r in (40, 64, 88):
        t.arco(160, 150, r, -40, 40, ROXO, 6)
    t.chao(420, 300, 120, (210, 196, 236))
    t.sombra(420, 300, 46, 12, (190, 176, 220))
    t.cubo(420, 150, 46)
    t.seta(530, 250, 530, 110, ROXO, 8, 24)
    return t


def mind_map_barra(t):
    t = Tela((246, 242, 226), (236, 228, 200))
    centro = (320, 180)
    ramos = ((120, 80, (226, 86, 86)), (110, 270, (98, 184, 110)), (320, 50, (72, 136, 220)),
             (520, 80, (150, 110, 210)), (530, 270, (240, 150, 60)), (320, 310, (80, 200, 220)))
    for x, y, c in ramos:
        t.linha(t.curva(centro, ((centro[0] + x) / 2, centro[1]), ((centro[0] + x) / 2, y), (x, y)), c, 5)
    for x, y, c in ramos:
        t.ret(x - 56, y - 22, x + 56, y + 22, BRANCO, 22, c, 4)
        t.texto(x - 34, y - 3, 68, c)
    t.ret(250, 150, 390, 210, (255, 214, 120), 30, TINTA, 4)
    t.cubo(320, 174, 14)
    return t


def minimap_radar(t):
    t = Tela((214, 236, 222), (180, 216, 196))
    _tela(t, 60, 40, 580, 320, (120, 180, 140))
    t.linha(t.curva((70, 260), (220, 120), (360, 300), (570, 140)), (200, 190, 160), 26)
    t.cubo(260, 190, 30)
    t.circulo(480, 110, 62, (30, 40, 50), BRANCO, 4)  # mini mapa
    t.linha(t.curva((428, 136), (450, 90), (500, 150), (532, 90)), (200, 190, 160), 6)
    t.poli([(470, 122), (480, 98), (490, 122), (480, 116)], (255, 214, 120))
    for x, y, c in ((510, 130, VERMELHO), (450, 84, VERMELHO), (514, 80, AZUL)):
        t.circulo(x, y, 6, c)
    return t


def occlusion_culling(t):
    t = Tela((232, 236, 246), (210, 216, 236))
    t.circulo(80, 180, 34, BRANCO, TINTA, 4)  # olho
    t.circulo(92, 180, 14, TINTA)
    for a in (-18, 0, 18):
        t.linha([(120, 180), (290, 180 + a * 5)], (150, 160, 190), 3)
    t.ret(290, 60, 330, 300, (200, 110, 80), 4, TINTA, 3)  # parede
    for i in range(1, 8):
        t.linha([(290, 60 + i * 30), (330, 60 + i * 30)], (130, 70, 50), 2)
    fantasma = t.camada()
    for cx, cy in ((430, 130), (510, 200), (420, 260)):
        fantasma.cubo(cx, cy, 30, contorno=(120, 120, 140))
    t.juntar(fantasma, 0.25)
    t.linha([(560, 70), (600, 110)], VERMELHO, 6)
    t.linha([(600, 70), (560, 110)], VERMELHO, 6)
    return t


def performance_medir(t):
    t = Tela((236, 246, 232), (214, 234, 206))
    t.arco(200, 230, 120, 180, 360, (220, 226, 220), 26)
    t.arco(200, 230, 120, 180, 240, (98, 184, 110), 26)
    t.arco(200, 230, 120, 240, 300, (240, 190, 70), 26)
    t.arco(200, 230, 120, 300, 360, (226, 86, 86), 26)
    t.linha([(200, 230), (130, 150)], TINTA, 8)
    t.circulo(200, 230, 14, TINTA)
    t.ret(380, 60, 600, 290, BRANCO, 10, TINTA, 3)
    for i, h in enumerate((80, 140, 110, 180, 60)):
        t.ret(400 + i * 40, 270 - h, 430 + i * 40, 270, AZUL if h < 150 else VERMELHO, 4)
    return t


def personagem_postura(t):
    t = Tela((246, 234, 222), (236, 214, 196))
    t.ret(0, 290, 640, 360, (210, 180, 150))
    t.ret(470, 230, 600, 244, (150, 120, 90), 4)  # obstáculo baixo para rastejar
    t.ret(476, 244, 486, 290, (150, 120, 90))
    t.ret(584, 244, 594, 290, (150, 120, 90))
    for x, pose in ((90, "pe"), (230, "corre"), (370, "abaixa"), (520, "rasteja")):
        _pessoa(t, x, 290, pose, (70, 80, 110))
    return t


def probe_volume_luz(t):
    t = Tela((246, 240, 224), (236, 226, 196))
    t.poli([(120, 260), (320, 330), (520, 260), (320, 190)], (240, 200, 120), TINTA, 3)  # chão
    t.poli([(120, 260), (120, 110), (320, 40), (320, 190)], (226, 120, 100), TINTA, 3)  # paredes
    t.poli([(320, 190), (320, 40), (520, 110), (520, 260)], (230, 230, 236), TINTA, 3)
    luz = t.camada()
    luz.circulo(300, 220, 120, (255, 220, 160))
    t.juntar(luz, 0.45, 26)
    t.cubo(320, 210, 34, cores=((255, 214, 120), (240, 150, 100), (200, 140, 60)))
    for x, y in ((200, 170), (260, 140), (380, 150), (440, 190), (320, 270)):
        t.circulo(x, y, 6, BRANCO, TINTA, 2)  # sondas
    t.seta(580, 20, 470, 230, (255, 190, 60), 6, 18)
    t.seta(470, 230, 380, 190, (255, 190, 60), 5, 16)
    return t


def rec_play_gravar(t):
    t = Tela((250, 228, 230), (244, 204, 210))
    pts = t.curva((90, 290), (180, 80), (380, 320), (540, 110))
    for i in range(0, len(pts) - 1, 2):
        t.linha([pts[i], pts[i + 1]], (200, 120, 130), 4)
    for i, u in enumerate((10, 22)):
        x, y = pts[u]
        fantasma = t.camada()
        fantasma.cubo(x, y - 10, 24)
        t.juntar(fantasma, 0.35 + i * 0.2)
    t.cubo(540, 100, 30)
    t.ret(40, 30, 160, 76, BRANCO, 23, TINTA, 3)
    t.circulo(70, 53, 12, (226, 60, 60))
    t.texto(92, 50, 50, TINTA)
    return t


def screencast_gravar(t):
    t = Tela((246, 230, 232), (236, 210, 214))
    _tela(t, 90, 40, 550, 290)
    t.chao(320, 230, 110, (205, 214, 228))
    t.cubo(320, 180, 46)
    t.ret(110, 60, 200, 92, (40, 44, 56), 16)
    t.circulo(130, 76, 9, (226, 60, 60))
    t.texto(146, 73, 40, BRANCO)
    t.ret(290, 290, 350, 316, (52, 58, 72))
    _play(t, 520, 280, 40, BRANCO, (226, 86, 86))
    return t


def shader_preset(t):
    t = Tela((236, 232, 250), (214, 208, 240))
    t.cubo(140, 160, 54, cores=((255, 220, 120), (255, 170, 60), (220, 110, 40)), contorno=(20, 20, 20))  # toon
    holo = t.camada()
    holo.cubo(320, 160, 54, cores=((140, 240, 255), (80, 200, 240), (50, 150, 220)), contorno=(30, 120, 200))
    t.juntar(holo, 0.6)
    for y in range(110, 270, 12):
        t.linha([(266, y), (374, y)], (200, 250, 255), 1.5)
    t.cubo(500, 160, 54, cores=((140, 200, 240), (60, 130, 210), (40, 100, 180)), contorno=(30, 70, 140))  # água
    for i in range(3):
        t.arco(500, 132 + i * 4, 30 + i * 10, 200, 340, (220, 240, 255), 3)
    for x, c in ((140, LARANJA), (320, CIANO), (500, AZUL)):
        t.ret(x - 50, 300, x + 50, 320, c, 10)
    return t


def smart_wizard_girador(t):
    t = Tela((244, 236, 214), (236, 222, 186))
    t.sombra(380, 280, 80, 18, (220, 200, 160))
    t.cubo(380, 170, 60, girar=30)
    t.arco(380, 200, 130, 200, 340, VERMELHO, 7)
    t.seta(500, 158, 508, 178, VERMELHO, 7, 20)
    t.linha([(80, 300), (200, 140)], (90, 70, 60), 10)  # varinha
    t.linha([(185, 160), (200, 140)], BRANCO, 10)
    for x, y, r in ((214, 110, 18), (250, 140, 10), (180, 90, 8), (236, 74, 12)):
        t.estrela(x, y, r, (255, 190, 60))
    return t


def som_world_sound(t):
    t = Tela((230, 244, 250), (200, 230, 244))
    t.poli([(70, 150), (110, 150), (170, 100), (170, 260), (110, 210), (70, 210)], (52, 58, 72))
    for r in (40, 70, 100):
        t.arco(180, 180, r, -45, 45, AZUL, 7)
    for x, y, c in ((380, 170, ROXO), (470, 250, LARANJA), (540, 140, VERDE)):  # notas
        t.circulo(x, y, 16, c)
        t.linha([(x + 14, y), (x + 14, y - 70)], c, 6)
        t.linha([(x + 14, y - 70), (x + 44, y - 56)], c, 6)
    return t


def sombra_realista(t):
    t = Tela((246, 242, 232), (232, 226, 210))
    t.circulo(90, 70, 36, (255, 210, 100))
    t.ret(0, 230, 640, 360, (220, 214, 200))
    longe = t.camada()
    longe.poli([(250, 250), (330, 250), (600, 330), (460, 350)], (90, 84, 76))
    perto = t.camada()
    perto.poli([(250, 250), (330, 250), (360, 270), (290, 280)], (90, 84, 76))
    t.juntar(longe, 0.45, 10)
    t.juntar(perto, 0.5, 1)
    t.cubo(290, 160, 50)
    return t


def ssgi_luz(t):
    t = Tela((240, 240, 240), (222, 222, 226))
    t.poli([(60, 40), (240, 100), (240, 300), (60, 340)], (220, 70, 70))
    t.poli([(580, 40), (400, 100), (400, 300), (580, 340)], (70, 180, 90))
    t.poli([(240, 300), (400, 300), (580, 340), (60, 340)], (210, 206, 200))
    brilho = t.camada()
    brilho.circulo(250, 220, 80, (240, 90, 90))
    brilho.circulo(390, 220, 80, (90, 200, 110))
    t.juntar(brilho, 0.5, 30)
    t.cubo(320, 210, 46, cores=((250, 240, 230), (250, 170, 160), (170, 220, 170)))
    return t


def texto_caixa_dialogo(t):
    t = Tela((236, 230, 250), (216, 206, 240))
    t.cubo(150, 100, 46)
    t.ret(60, 210, 580, 330, BRANCO, 16, TINTA, 4)
    t.poli([(130, 214), (150, 186), (170, 214)], BRANCO)
    t.linha([(130, 212), (150, 186), (170, 212)], TINTA, 4)
    t.texto(90, 236, 440, (110, 116, 140), 3, 22, 10)
    t.poli([(540, 304), (560, 304), (550, 318)], ROXO)
    return t


def track_pista(t):
    t = Tela((214, 238, 214), (180, 220, 180))
    pts = t.curva((40, 330), (200, -40), (420, 420), (610, 60))
    t.linha(pts, (240, 240, 240), 60)
    t.linha(pts, (110, 110, 118), 48)
    for i in range(0, len(pts) - 1, 4):
        t.linha([pts[i], pts[i + 1]], BRANCO, 4)
    t.linha([(40, 330), (200, 20)], (200, 160, 60), 2)
    t.linha([(420, 360), (610, 60)], (200, 160, 60), 2)
    for x, y in ((40, 330), (200, 20), (610, 60)):
        t.circulo(x, y, 10, (255, 214, 120), TINTA, 3)
    return t


def ui_tree_hud(t):
    t = Tela((224, 236, 250), (196, 214, 240))
    _tela(t, 40, 30, 600, 330, (150, 176, 214))
    t.chao(320, 250, 120, (205, 214, 228))
    t.cubo(320, 200, 40)
    t.ret(70, 60, 260, 84, (40, 44, 56), 12)  # barra de vida
    t.ret(74, 64, 200, 80, (226, 86, 86), 8)
    t.arco(520, 290, 50, 180, 360, BRANCO, 10)  # velocímetro
    t.linha([(520, 290), (550, 258)], (226, 86, 86), 6)
    for i, c in enumerate((AZUL, VERDE)):
        t.circulo(90 + i * 60, 280, 22, c, BRANCO, 3)
    t.ret(420, 60, 570, 90, (40, 44, 56), 10)
    t.texto(436, 72, 100, BRANCO)
    return t


def ui_tree_menu(t):
    t = Tela((246, 232, 216), (236, 212, 186))
    t.ret(180, 30, 460, 330, (52, 58, 72), 16)
    t.ret(220, 56, 420, 76, (255, 214, 120), 10)
    for i in range(3):
        y = 110 + i * 70
        t.ret(220, y, 420, y + 50, (255, 214, 120) if i == 0 else (90, 98, 118), 12)
        if i == 0:
            _play(t, 250, y + 25, 20, TINTA)
            t.texto(276, y + 21, 100, TINTA, 1, alt=8)
        else:
            t.texto(250, y + 21, 120, (170, 178, 196), 1, alt=8)
    t.poli([(400, 150), (400, 178), (407, 171), (413, 184), (418, 182), (412, 169), (422, 169)], BRANCO, TINTA, 2)
    return t


def veiculo_carro(t):
    t = Tela((226, 238, 250), (206, 222, 244))
    t.ret(0, 280, 640, 360, (120, 120, 128))
    for x in range(20, 640, 80):
        t.ret(x, 316, x + 40, 322, BRANCO, 3)
    t.poli([(150, 250), (150, 200), (230, 196), (280, 140), (420, 140), (470, 196), (520, 206), (520, 250)],
           (226, 86, 86), TINTA, 4)
    t.poli([(296, 154), (340, 154), (340, 194), (260, 196)], (190, 225, 250), TINTA, 3)
    t.poli([(356, 154), (410, 154), (446, 196), (356, 194)], (190, 225, 250), TINTA, 3)
    for x in (220, 450):
        t.circulo(x, 256, 34, (40, 44, 56))
        t.circulo(x, 256, 14, (200, 200, 210))
    for y in (180, 210, 240):
        t.linha([(70, y), (120, y)], (150, 166, 190), 4)
    return t


def video_player(t):
    t = Tela((250, 230, 220), (244, 206, 190))
    _tela(t, 130, 50, 510, 280, (60, 120, 180))
    t.circulo(220, 130, 30, (255, 214, 120))
    t.poli([(140, 270), (270, 160), (360, 260), (420, 200), (500, 270)], (60, 160, 110))
    _play(t, 320, 165, 46, BRANCO, (226, 86, 86))
    t.ret(150, 300, 490, 310, (220, 180, 160), 5)
    t.ret(150, 300, 290, 310, (226, 86, 86), 5)
    return t


CAPAS = {f.__name__: f for f in [basico_interface, basico_transformar, basico_primeiro_jogo] + [
    camera_foco, casas_brasileiras, ceu_entardecer, chuva_nevoa, compositing_efeitos, cutscene_abertura, decimate_hq,
    destruicao_bomba, exportar_desktop, exportar_web, glsl_node, lod_automatico, logica_andar, logica_arvore_andar,
    material_atlas_paleta, microfone_pular, mind_map_barra, minimap_radar, occlusion_culling, performance_medir,
    personagem_postura, probe_volume_luz, rec_play_gravar, screencast_gravar, shader_preset, smart_wizard_girador,
    som_world_sound, sombra_realista, ssgi_luz, texto_caixa_dialogo, track_pista, ui_tree_hud, ui_tree_menu,
    veiculo_carro, video_player]}


def main():
    nomes = sys.argv[1:] or list(CAPAS)
    for nome in nomes:
        CAPAS[nome](None).salvar(PASTA / nome / "miniatura.png")
        print("ok:", nome)


if __name__ == "__main__":
    main()
