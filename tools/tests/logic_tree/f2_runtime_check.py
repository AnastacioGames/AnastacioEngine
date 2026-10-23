# Confere o registro de f2_compile_test.py (linhas: tick, máscara de estado, pos, ticks, voltas).
# Uso: python3 f2_runtime_check.py <f2.txt>
import sys

rows = [[int(v) for v in l.split()] for l in open(sys.argv[1]) if l.strip()]
ok = True


def check(name, cond, detail=""):
    global ok
    ok &= bool(cond)
    print("%s %s %s" % ("PASS" if cond else "FAIL", name, detail))


masks = {r[1] for r in rows}
check("só um Frame ativo por vez (máscara 1 ou 2)", masks <= {1, 2}, str(masks))
phases, start = [], 0
for i in range(1, len(rows)):
    if rows[i][1] != rows[i - 1][1]:
        phases.append((rows[start][1], i - start))
        start = i
full = phases[1:]  # a primeira fase começa antes do registro
check("troca de estado pelo Then da Espera (0,5 s = ~30 ticks)",
      len(full) >= 4 and all(25 <= n <= 36 for _, n in full), str(phases))
bad = [i for i in range(2, len(rows)) if rows[i][1] == rows[i - 1][1] == rows[i - 2][1]
       and rows[i][2] - rows[i - 1][2] != (1 if rows[i][1] == 1 else -1)]
check("pos sobe em Indo e desce em Voltando", not bad, str(bad[:5]))
check("nó fora de Frame roda todo tick", all(rows[i][3] - rows[i - 1][3] == 1 for i in range(1, len(rows))))
ups = sum(1 for i in range(1, len(rows)) if rows[i - 1][1] == 1 and rows[i][1] == 2)
check("Then soma uma volta a cada ida", rows[-1][4] == ups, "%d voltas, %d idas" % (rows[-1][4], ups))
print("PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
