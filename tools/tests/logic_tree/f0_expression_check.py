# Lê o resultado de f0_expression_scene.py e compara os caminhos tick a tick.
# Uso: python3 f0_expression_check.py <resultado.txt>
import sys

rows = []
for line in open(sys.argv[1]):
    if line.startswith("#") or not line.strip():
        continue
    rows.append([int(v) for v in line.split()])

# colunas: tick a b c ca ce_and co ce_or cx
deltas = {}
for col, name in ((4, "ca"), (5, "ce_and"), (6, "co"), (7, "ce_or"), (8, "cx")):
    deltas[name] = [rows[i + 1][col] - rows[i][col] for i in range(len(rows) - 1)]

ok = True
for native, expr in (("ca", "ce_and"), ("co", "ce_or")):
    diff = [i for i, (x, y) in enumerate(zip(deltas[native], deltas[expr])) if x != y]
    print("%s x %s: %d ticks, %d diferentes, soma %d x %d" % (
        native, expr, len(deltas[native]), len(diff), sum(deltas[native]), sum(deltas[expr])))
    ok &= not diff

expected = [int((r[1] or r[2]) and not r[3]) for r in rows]
best = None
for k in range(1, 5):  # atraso entre gravar as propriedades e o actuator somar
    got = deltas["cx"][k - 1:]
    exp = expected[:len(got)]
    bad = sum(1 for x, y in zip(got, exp) if x != y)
    if best is None or bad < best[1]:
        best = (k, bad, len(got), sum(exp))
print("cx x esperado (A or B) and not C: atraso %d ticks, %d de %d diferentes, %d positivos esperados" % best)
ok &= best[1] == 0
print("PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
