"""Moto esportiva detalhada (estilo 600 cc). Frente em +X, origem no chao.

AnastacioEngine.exe -b --factory-startup --python tools/modelagem/criar_moto_esportiva.py -- saida.range relatorio.txt
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bmesh
from lowpoly_kit import *

scn = limpar_cena()
PINT = material_fino("ME_Pintura", (0.02, 0.12, 0.55), 0.9, 90)
BRANCO = material_fino("ME_Branco", (0.85, 0.86, 0.88), 0.8, 80)
PRETO = material_fino("ME_PretoFosco", (0.025, 0.025, 0.03), 0.25, 20)
CARB = material_fino("ME_Carbono", (0.05, 0.05, 0.06), 0.7, 120)
ALU = material_fino("ME_Aluminio", (0.55, 0.57, 0.6), 0.9, 60)
CROMO = material_fino("ME_Cromo", (0.8, 0.8, 0.82), 1.0, 160)
OURO = material_fino("ME_Dourado", (0.75, 0.5, 0.1), 0.9, 90)
TITAN = material_fino("ME_Titanio", (0.35, 0.33, 0.38), 0.9, 70)
BORR = material_fino("ME_Pneu", (0.035, 0.035, 0.035), 0.08, 10)
COURO = material_fino("ME_Banco", (0.04, 0.035, 0.035), 0.2, 15)
VERM = material_fino("ME_Vermelho", (0.75, 0.04, 0.03), 0.8, 80)
LENTE = material_fino("ME_Farol", (0.9, 0.95, 1.0), 1.0, 200)
LANT = material_fino("ME_Lanterna", (0.8, 0.02, 0.02), 1.0, 150, alpha=0.85)
VIDRO = material_fino("ME_Parabrisa", (0.15, 0.17, 0.2), 1.0, 200, alpha=0.35)
TELA = material_fino("ME_Painel", (0.05, 0.25, 0.35), 1.0, 100)

XT, XD = -0.70, 0.70          # eixos (entre-eixos 1.40)
RD, RT = 0.300, 0.315         # raio externo pneus 120/70-17 e 180/55-17
RARO = 0.216                  # aro 17"
CAB = Vector((0.47, 0.0, 0.84))   # caixa de direcao
moto = raiz("MotoEsp")


def peca(nome, mat, pai=moto, sub=0, auto=None, constroi=None):
    bm = bmesh.new()
    constroi(bm)
    o = objeto(nome, bm, mat, pai)
    if sub:
        aplicar_subsurf(o, sub)
    elif auto is not None:
        suavizar(o, auto)
    return o


# ---------------------------------------------------------------- rodas
def pneu_perfil(w):
    h = w / 2
    return [(RARO + 0.005, -h * 0.80), (RARO + 0.035, -h), (R_ - 0.03, -h * 0.98), (R_ - 0.008, -h * 0.70),
            (R_, -h * 0.30), (R_, h * 0.30), (R_ - 0.008, h * 0.70), (R_ - 0.03, h * 0.98),
            (RARO + 0.035, h), (RARO + 0.005, h * 0.80)]


def montar_roda(nome, centro, largura, raio_ext, pai, lado_coroa=None, discos=()):
    global R_
    R_ = raio_ext
    e = pivo(nome, pai, centro, raio_ext)
    o = peca(nome + "_Pneu", BORR, e, constroi=lambda bm: torneado(bm, pneu_perfil(largura), (0, 0, 0), 40))
    suavizar(o, 70)
    w = largura / 2 * 0.82

    def aro(bm):
        torneado(bm, [(RARO + 0.012, -w), (RARO + 0.012, w), (RARO - 0.012, w * 0.9), (RARO - 0.02, 0),
                      (RARO - 0.012, -w * 0.9)], (0, 0, 0), 40)
        torneado(bm, [(0.055, -w * 0.9), (0.055, w * 0.9), (0.02, w * 0.9), (0.02, -w * 0.9)], (0, 0, 0), 20)
        for k in range(5):  # 5 raios duplos
            a = 2 * math.pi * k / 5
            for d in (-0.13, 0.13):
                b = a + d
                tubo(bm, (0.05 * math.cos(a), 0, 0.05 * math.sin(a)),
                     ((RARO - 0.015) * math.cos(b), 0, (RARO - 0.015) * math.sin(b)), 0.022)
    suavizar(peca(nome + "_Aro", PRETO, e, constroi=aro), 35)
    for y, rd in discos:
        def disco(bm, y=y, rd=rd):
            torneado(bm, [(rd, y - 0.0025), (rd, y + 0.0025), (rd - 0.035, y + 0.0025), (rd - 0.035, y - 0.0025)], (0, 0, 0), 48)
            torneado(bm, [(rd - 0.035, y - 0.003), (rd - 0.035, y + 0.003), (0.06, y + 0.003), (0.06, y - 0.003)], (0, 0, 0), 12)
        suavizar(peca(nome + "_Disco%d" % (1 if y > 0 else 0), CROMO, e, constroi=disco), 30)
    if lado_coroa is not None:
        def coroa(bm):
            n = 44
            for side in (-0.004, 0.004):
                pass
            vs1, vs2 = [], []
            for i in range(n * 2):
                a = math.pi * i / n
                r = 0.118 if i % 2 == 0 else 0.108
                vs1.append(bm.verts.new((r * math.cos(a), lado_coroa - 0.004, r * math.sin(a))))
                vs2.append(bm.verts.new((r * math.cos(a), lado_coroa + 0.004, r * math.sin(a))))
            m = len(vs1)
            for i in range(m):
                j = (i + 1) % m
                bm.faces.new((vs1[i], vs1[j], vs2[j], vs2[i]))
            bm.faces.new(vs1); bm.faces.new(list(reversed(vs2)))
        suavizar(peca(nome + "_Coroa", ALU, e, constroi=coroa), 20)
    return e


montar_roda("ME_RodaTras", (XT, 0, RT), 0.18, RT, moto, lado_coroa=-0.085, discos=[(0.075, 0.11)])

# ---------------------------------------------------------------- direcao (pivo inclinado no eixo do garfo)
eixo_garfo = (Vector((XD, 0, RD)) - CAB).normalized()
dire = pivo("ME_Direcao", moto, CAB, 0.15)
dire.rotation_euler = (0, -math.atan2(eixo_garfo.x, -eixo_garfo.z), 0)
frente = []
rd_e = montar_roda("ME_RodaDiant", (XD, 0, RD), 0.12, RD, None, discos=[(0.072, 0.16), (-0.072, 0.16)])
frente.append(rd_e)

topo = CAB + Vector((0, 0, 0.06)) - eixo_garfo * 0.0
for y in (-0.10, 0.10):
    a = Vector((topo.x, y, topo.z)) - eixo_garfo * 0.02
    m = Vector((XD, y, RD)) - eixo_garfo * 0.28
    b = Vector((XD, y, RD))
    frente.append(peca("ME_GarfoSup%d" % (y > 0), OURO, None, auto=40,
                       constroi=lambda bm, a=a, m=m: tubo(bm, a, m, 0.058)))
    frente.append(peca("ME_GarfoInf%d" % (y > 0), PRETO, None, auto=40,
                       constroi=lambda bm, m=m, b=b: tubo(bm, m - eixo_garfo * 0.03, b + eixo_garfo * 0.03, 0.046)))
    # pinca radial
    frente.append(peca("ME_Pinca%d" % (y > 0), OURO, None, sub=2,
                       constroi=lambda bm, y=y: caixa(bm, (XD - 0.10, y * 0.83, RD + 0.12), (0.11, 0.035, 0.05), ("Y", 35))))


def mesas(bm):
    for dz in (0.0, -0.13):
        c = topo - eixo_garfo * dz
        caixa(bm, (c.x, 0, c.z), (0.07, 0.27, 0.025))
frente.append(peca("ME_Mesas", ALU, None, sub=1, constroi=mesas))


def paralama(bm):
    torneado(bm, [(RD + 0.035, -0.065), (RD + 0.05, -0.05), (RD + 0.055, 0), (RD + 0.05, 0.05), (RD + 0.035, 0.065)],
             (0, 0, 0), 16, fechado=False, a0=math.radians(15), a1=math.radians(150))
o = peca("ME_ParalamaD", PINT, None, constroi=paralama)
o.location = (XD, 0, RD)
aplicar_subsurf(o, 1)
frente.append(o)


def guidao(bm):
    for s in (-1, 1):
        a = Vector((topo.x, s * 0.10, topo.z - 0.02))
        b = Vector((topo.x - 0.04, s * 0.30, topo.z - 0.06))
        tubo(bm, a, b, 0.024)
frente.append(peca("ME_Guidao", ALU, None, auto=40, constroi=guidao))
for s in (-1, 1):
    frente.append(peca("ME_Manopla%d" % (s > 0), PRETO, None, sub=1, constroi=lambda bm, s=s: tubo(
        bm, (topo.x - 0.03, s * 0.24, topo.z - 0.045), (topo.x - 0.045, s * 0.34, topo.z - 0.065), 0.034)))
    frente.append(peca("ME_Manete%d" % (s > 0), ALU, None, auto=30, constroi=lambda bm, s=s: tubo(
        bm, (topo.x + 0.01, s * 0.22, topo.z - 0.03), (topo.x + 0.04, s * 0.36, topo.z - 0.06), 0.012)))
frente.append(peca("ME_Reservatorio", PRETO, None, sub=1, constroi=lambda bm: caixa(
    bm, (topo.x - 0.02, 0.2, topo.z + 0.02), (0.04, 0.04, 0.035))))
for o in frente:
    prender(o, dire)

# ---------------------------------------------------------------- carenagem e carroceria (loft + subdivisao)
peca("ME_Tanque", PINT, sub=2, constroi=lambda bm: loft(bm, [
    (0.40, 0.11, 0.05, 0.93, 0.7), (0.32, 0.17, 0.09, 0.95, 0.7), (0.18, 0.205, 0.11, 0.97, 0.65),
    (0.02, 0.20, 0.10, 0.96, 0.65), (-0.10, 0.16, 0.08, 0.92, 0.7), (-0.17, 0.11, 0.05, 0.88, 0.8)]))
peca("ME_Banco", COURO, sub=2, constroi=lambda bm: loft(bm, [
    (-0.14, 0.10, 0.03, 0.885, 0.6), (-0.25, 0.135, 0.04, 0.89, 0.5), (-0.42, 0.12, 0.04, 0.905, 0.5),
    (-0.52, 0.085, 0.035, 0.93, 0.6)]))
peca("ME_Rabeta", PINT, sub=2, constroi=lambda bm: loft(bm, [
    (-0.22, 0.14, 0.07, 0.83, 0.6), (-0.45, 0.13, 0.08, 0.86, 0.6), (-0.70, 0.10, 0.075, 0.93, 0.6),
    (-0.92, 0.06, 0.05, 0.99, 0.7), (-1.00, 0.035, 0.03, 1.0, 0.8)]))
peca("ME_RabetaFaixa", BRANCO, sub=2, constroi=lambda bm: loft(bm, [
    (-0.50, 0.128, 0.03, 0.88, 0.6), (-0.70, 0.103, 0.03, 0.92, 0.6), (-0.88, 0.07, 0.025, 0.97, 0.7)]))
peca("ME_Bico", PINT, sub=2, constroi=lambda bm: loft(bm, [
    (0.99, 0.05, 0.035, 0.86, 0.8), (0.93, 0.15, 0.09, 0.87, 0.7), (0.80, 0.22, 0.14, 0.86, 0.65),
    (0.64, 0.25, 0.17, 0.83, 0.6), (0.52, 0.25, 0.16, 0.80, 0.6)]))
peca("ME_CarenagemLat", PINT, sub=2, constroi=lambda bm: loft(bm, [
    (0.60, 0.245, 0.14, 0.66, 0.55), (0.42, 0.25, 0.15, 0.60, 0.5), (0.20, 0.23, 0.13, 0.52, 0.5),
    (0.02, 0.19, 0.08, 0.50, 0.6)]))
peca("ME_Quilha", PRETO, sub=2, constroi=lambda bm: loft(bm, [
    (0.42, 0.17, 0.06, 0.32, 0.5), (0.20, 0.19, 0.07, 0.28, 0.5), (-0.05, 0.16, 0.06, 0.26, 0.5),
    (-0.15, 0.09, 0.04, 0.27, 0.7)]))
peca("ME_ParalamaT", CARB, sub=1, constroi=lambda bm: torneado(
    bm, [(RT + 0.03, -0.075), (RT + 0.045, -0.06), (RT + 0.05, 0), (RT + 0.045, 0.06), (RT + 0.03, 0.075)],
    (XT, 0, RT), 12, fechado=False, a0=math.radians(20), a1=math.radians(95)))


def parabrisa(bm):
    lin, col = 5, 7
    vs = []
    for i in range(lin):
        t = i / float(lin - 1)
        x = 0.90 - 0.22 * t
        z = 0.95 + 0.17 * t
        w = 0.17 - 0.06 * t
        row = []
        for j in range(col):
            u = j / float(col - 1) * 2 - 1
            row.append(bm.verts.new((x - 0.05 * u * u, u * w, z - 0.03 * u * u)))
        vs.append(row)
    for i in range(lin - 1):
        for j in range(col - 1):
            bm.faces.new((vs[i][j], vs[i][j + 1], vs[i + 1][j + 1], vs[i + 1][j]))
o = peca("ME_Parabrisa", VIDRO, constroi=parabrisa)
aplicar_subsurf(o, 1)
for s in (-1, 1):
    peca("ME_Farol%d" % (s > 0), LENTE, sub=2, constroi=lambda bm, s=s: loft(bm, [
        (0.985, 0.025, 0.015, 0.86, 0.6, s * 0.06), (0.955, 0.045, 0.025, 0.865, 0.6, s * 0.085)]))
    peca("ME_Retrovisor%d" % (s > 0), PINT, sub=2, constroi=lambda bm, s=s: caixa(
        bm, (0.70, s * 0.30, 1.0), (0.06, 0.12, 0.05)))
    peca("ME_RetroHaste%d" % (s > 0), PRETO, auto=40, constroi=lambda bm, s=s: tubo(
        bm, (0.72, s * 0.21, 0.94), (0.70, s * 0.27, 0.99), 0.015))
    peca("ME_Seta%d" % (s > 0), OURO, sub=1, constroi=lambda bm, s=s: caixa(
        bm, (-0.98, s * 0.09, 0.90), (0.05, 0.02, 0.02)))
peca("ME_Painel", TELA, sub=1, constroi=lambda bm: caixa(bm, (0.62, 0, 1.02), (0.05, 0.16, 0.10), ("Y", -55)))
peca("ME_Lanterna", LANT, sub=1, constroi=lambda bm: caixa(bm, (-1.0, 0, 0.99), (0.03, 0.08, 0.03)))
peca("ME_Placa", PRETO, auto=40, constroi=lambda bm: (
    tubo(bm, (-0.95, 0, 0.92), (-1.05, 0, 0.70), 0.02), caixa(bm, (-1.06, 0, 0.66), (0.01, 0.18, 0.12), ("Y", 20))))

# ---------------------------------------------------------------- quadro, balanca, suspensao
for s in (-1, 1):
    peca("ME_Longarina%d" % (s > 0), ALU, sub=1, constroi=lambda bm, s=s: loft(bm, [
        (0.50, 0.035, 0.05, 0.82, 0.4, s * 0.06), (0.32, 0.03, 0.06, 0.80, 0.4, s * 0.15),
        (0.10, 0.03, 0.06, 0.76, 0.4, s * 0.18), (-0.04, 0.03, 0.08, 0.62, 0.4, s * 0.17),
        (-0.08, 0.03, 0.08, 0.48, 0.4, s * 0.15)], n=12))
    peca("ME_Balanca%d" % (s > 0), ALU, sub=1, constroi=lambda bm, s=s: loft(bm, [
        (-0.05, 0.025, 0.06, 0.46, 0.4, s * 0.13), (-0.35, 0.025, 0.055, 0.40, 0.4, s * 0.12),
        (XT - 0.02, 0.02, 0.035, RT, 0.4, s * 0.115)], n=12))
    peca("ME_Pedaleira%d" % (s > 0), ALU, auto=40, constroi=lambda bm, s=s: (
        tubo(bm, (-0.12, s * 0.17, 0.42), (-0.20, s * 0.17, 0.36), 0.03),
        tubo(bm, (-0.20, s * 0.17, 0.36), (-0.20, s * 0.25, 0.36), 0.022)))
peca("ME_SubQuadro", PRETO, auto=40, constroi=lambda bm: [
    tubo(bm, (-0.05, s * 0.12, 0.70), (-0.85, s * 0.06, 0.92), 0.025) for s in (-1, 1)])
peca("ME_Eixos", ALU, auto=40, constroi=lambda bm: (
    cilindro(bm, (XT, 0, RT), 0.025, 0.30, 'Y', 12), cilindro(bm, (-0.05, 0, 0.46), 0.03, 0.32, 'Y', 12)))
amort_b, amort_t = Vector((-0.18, 0, 0.42)), Vector((-0.10, 0, 0.72))
peca("ME_AmortCorpo", PRETO, auto=40, constroi=lambda bm: tubo(bm, amort_b, amort_t, 0.04))
ax = (amort_t - amort_b)
mola = []
for i in range(9 * 12 + 1):
    t = i / float(9 * 12)
    a = 2 * math.pi * 9 * t
    c = amort_b + ax * (0.15 + 0.7 * t)
    mola.append(c + Vector((0.035 * math.cos(a), 0.035 * math.sin(a), 0)))
tubo_curva("ME_Mola", mola, 0.007, VERM, moto, ordem=2, res=1)

# ---------------------------------------------------------------- motor 4 cilindros
peca("ME_Carter", ALU, sub=1, constroi=lambda bm: caixa(bm, (0.08, 0, 0.42), (0.40, 0.30, 0.22)))
peca("ME_Bloco", PRETO, auto=30, constroi=lambda bm: [
    caixa(bm, (0.26, 0, 0.60 + 0.02 * k), (0.15, 0.32 - 0.01 * (k % 2), 0.012), ("Y", -30)) for k in range(7)] + [
    caixa(bm, (0.24, 0, 0.62), (0.12, 0.28, 0.20), ("Y", -30))])
peca("ME_Cabecote", PINT, sub=1, constroi=lambda bm: caixa(bm, (0.33, 0, 0.76), (0.17, 0.30, 0.08), ("Y", -30)))
peca("ME_Radiador", PRETO, auto=30, constroi=lambda bm: [caixa(bm, (0.47, 0, 0.62), (0.04, 0.38, 0.28), ("Y", -15))] + [
    caixa(bm, (0.495, 0, 0.50 + 0.025 * k), (0.01, 0.37, 0.006), ("Y", -15)) for k in range(10)])
peca("ME_TampaEmbreagem", ALU, auto=30, constroi=lambda bm: torneado(
    bm, [(0.10, 0.15), (0.10, 0.17), (0.085, 0.19), (0.03, 0.195), (0.0, 0.195), (0.0, 0.15)], (0.0, 0, 0.42), 28))
peca("ME_TampaAlternador", ALU, auto=30, constroi=lambda bm: torneado(
    bm, [(0.08, -0.15), (0.08, -0.17), (0.065, -0.185), (0.0, -0.185), (0.0, -0.15)], (0.10, 0, 0.44), 28))
peca("ME_Pinhao", ALU, auto=30, constroi=lambda bm: cilindro(bm, (0.02, -0.085, 0.40), 0.045, 0.015, 'Y', 16))

# corrente: pinhao (0.02, 0.40, r .045) -> coroa (XT, RT, r .113)
cad = []
pa, ra = Vector((0.02, -0.085, 0.40)), 0.05
pb, rb = Vector((XT, -0.085, RT)), 0.118
for k in range(9):
    a = math.radians(-90 + 180 * k / 8.0)
    cad.append(pa + Vector((ra * math.cos(a), 0, ra * math.sin(a))))
for k in range(13):
    a = math.radians(90 + 180 * k / 12.0)
    cad.append(pb + Vector((rb * math.cos(a), 0, rb * math.sin(a))))
tubo_curva("ME_Corrente", cad, 0.008, PRETO, moto, ordem=3, ciclico=True, res=6)

# escapamento 4-em-1
for i, y in enumerate((-0.11, -0.04, 0.04, 0.11)):
    tubo_curva("ME_Coletor%d" % i, [(0.40, y, 0.70), (0.47, y, 0.55), (0.42, y * 0.8, 0.30), (0.25, y * 0.4, 0.20),
                                   (0.05, 0.0, 0.19)], 0.019, TITAN, moto, ordem=3)
tubo_curva("ME_EscapeMeio", [(0.05, 0, 0.19), (-0.15, 0.05, 0.22), (-0.35, 0.15, 0.32)], 0.03, TITAN, moto)
peca("ME_Ponteira", TITAN, auto=30, constroi=lambda bm: loft(bm, [
    (-0.33, 0.045, 0.045, 0.32, 0.9, 0.16), (-0.42, 0.055, 0.065, 0.36, 0.7, 0.17),
    (-0.68, 0.05, 0.06, 0.47, 0.7, 0.18), (-0.72, 0.042, 0.05, 0.49, 0.8, 0.18)], n=20))
peca("ME_PonteiraBoca", CARB, auto=30, constroi=lambda bm: loft(bm, [
    (-0.72, 0.042, 0.05, 0.49, 0.8, 0.18), (-0.75, 0.035, 0.042, 0.50, 0.8, 0.18)], n=20))
peca("ME_Cavalete", PRETO, auto=40, constroi=lambda bm: tubo(bm, (-0.05, -0.17, 0.33), (-0.25, -0.33, 0.02), 0.022))

luz_e_camera((0.0, 0, 0.55), 3.4)
saida, rel = sys.argv[sys.argv.index('--') + 1:][:2]
bpy.ops.wm.save_as_mainfile(filepath=saida)
relatorio(rel)
with open(rel, "a") as f:
    f.write("TRIS %d\n" % sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in scn.objects if o.type == 'MESH'))
