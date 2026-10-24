"""Moto street simples low poly (~150 cc). Frente em +X.

AnastacioEngine.exe -b --factory-startup --python tools/modelagem/criar_moto.py -- saida.range relatorio.txt
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bmesh
from lowpoly_kit import *

scn = limpar_cena()
VERM = material("Moto_Pintura", (0.75, 0.05, 0.05), 0.6)
PRETO = material("Moto_Preto", (0.03, 0.03, 0.03))
METAL = material("Moto_Metal", (0.65, 0.65, 0.68), 0.8)
BORR = material("Moto_Borracha", (0.06, 0.06, 0.06), 0.1)
BANCO = material("Moto_Banco", (0.12, 0.08, 0.06), 0.2)
FAROL = material("Moto_Farol", (1.0, 0.95, 0.7), 1.0)

R = 0.30                     # raio das rodas
XT, XD = -0.66, 0.66         # eixo traseiro / dianteiro (entre-eixos 1.32)
moto = raiz("Moto")

roda("Moto_RodaTras", moto, (XT, 0, R), R, 0.12, BORR, METAL)
# direcao: pivo na coluna; garfo, roda dianteira, guidao e farol giram juntos
col_base, col_topo = Vector((0.42, 0, 0.62)), Vector((0.30, 0, 0.98))
dire = pivo("Moto_Direcao", moto, col_topo, 0.15)
garfo_eixo = Vector((XD, 0, R))
roda("Moto_RodaDiant", dire, garfo_eixo - col_topo, R, 0.10, BORR, METAL)

bm = bmesh.new()
for y in (-0.08, 0.08):
    tubo(bm, Vector((XD, y, R)) - col_topo, Vector((0.30, y, 0.95)) - col_topo, 0.04)
tubo(bm, Vector((0.30, -0.08, 0.95)) - col_topo, Vector((0.30, 0.08, 0.95)) - col_topo, 0.05)
objeto("Moto_Garfo", bm, METAL, dire)

bm = bmesh.new()
tubo(bm, (-0.04, -0.37, 0.12), (-0.04, 0.37, 0.12), 0.025)
for y in (-0.33, 0.33):
    caixa(bm, (-0.04, y, 0.12), (0.04, 0.12, 0.04), ("X", 90))
objeto("Moto_Guidao", bm, PRETO, dire)

bm = bmesh.new(); cilindro(bm, (0.14, 0, -0.02), 0.09, 0.08, 'X', 16)
objeto("Moto_Farol", bm, FAROL, dire)
bm = bmesh.new(); caixa(bm, (Vector((XD, 0, R + 0.33)) - col_topo), (0.30, 0.13, 0.03))
objeto("Moto_Paralama_D", bm, VERM, dire)

# quadro
bm = bmesh.new()
tubo(bm, col_topo, (-0.30, 0, 0.78), 0.05)        # espinha
tubo(bm, col_base, (0.05, 0, 0.30), 0.05)         # berco
tubo(bm, (0.05, 0, 0.30), (-0.25, 0, 0.30), 0.05)
for y in (-0.09, 0.09):
    tubo(bm, (-0.15, y, 0.40), (XT, y, R), 0.04)   # balanca
    tubo(bm, (-0.30, y, 0.78), (XT + 0.05, y, R + 0.1), 0.03)  # amortecedor
objeto("Moto_Quadro", bm, PRETO, moto)

# tanque e tampa lateral pela silhueta lateral
bm = bmesh.new()
perfil_extrudado(bm, [(0.30, 0.92), (0.20, 1.02), (-0.15, 1.00), (-0.25, 0.86), (0.25, 0.80)], 0.30)
perfil_extrudado(bm, [(-0.25, 0.80), (-0.25, 0.55), (-0.50, 0.60), (-0.55, 0.78)], 0.24)
objeto("Moto_Tanque", bm, VERM, moto)
bm = bmesh.new()
perfil_extrudado(bm, [(-0.15, 0.92), (-0.25, 0.86), (-0.55, 0.80), (-0.85, 0.84), (-0.85, 0.88), (-0.55, 0.90), (-0.25, 0.95)], 0.26)
objeto("Moto_Banco", bm, BANCO, moto)
bm = bmesh.new(); caixa(bm, (XT - 0.10, 0, R + 0.36), (0.38, 0.15, 0.03), ("Y", -20))
objeto("Moto_Paralama_T", bm, VERM, moto)
bm = bmesh.new(); caixa(bm, (-0.98, 0, 0.82), (0.04, 0.12, 0.05))
objeto("Moto_Lanterna", bm, material("Moto_Lanterna", (0.9, 0.05, 0.0), 1.0), moto)

# motor, escapamento, pedaleiras
bm = bmesh.new()
caixa(bm, (-0.05, 0, 0.42), (0.36, 0.26, 0.26))
caixa(bm, (0.08, 0, 0.62), (0.18, 0.20, 0.18), ("Y", -20))
cilindro(bm, (-0.05, 0.15, 0.40), 0.11, 0.05, 'Y', 16)
objeto("Moto_Motor", bm, METAL, moto)
bm = bmesh.new()
tubo(bm, (0.12, -0.10, 0.55), (0.10, -0.16, 0.25), 0.04)
tubo(bm, (0.10, -0.16, 0.25), (-0.40, -0.16, 0.25), 0.04)
cilindro(bm, (-0.62, -0.17, 0.33), 0.06, 0.40, 'X', 12)
objeto("Moto_Escape", bm, METAL, moto)
bm = bmesh.new()
for y in (-0.22, 0.22):
    caixa(bm, (-0.05, y, 0.30), (0.10, 0.12, 0.025))
objeto("Moto_Pedaleiras", bm, PRETO, moto)

luz_e_camera((0, 0, 0.55), 3.2)
saida, rel = sys.argv[sys.argv.index('--') + 1:][:2]
bpy.ops.wm.save_as_mainfile(filepath=saida)
relatorio(rel)
