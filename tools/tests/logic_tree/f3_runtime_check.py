# Confere f3.txt (tick, máscara de estado, y da plataforma): vai e volta trocando de estado.
# Uso: python3 f3_runtime_check.py <f3.txt>
import sys

rows = [l.split() for l in open(sys.argv[1]) if l.strip()]
rows = [(int(a), int(b), float(c)) for a, b, c in rows]
bad = [r[0] for i, r in enumerate(rows[2:], 2)
       if r[1] == rows[i - 1][1] == rows[i - 2][1]
       and abs((r[2] - rows[i - 1][2]) - (0.03 if r[1] == 1 else -0.03)) > 1e-3]
switches = sum(1 for i in range(1, len(rows)) if rows[i][1] != rows[i - 1][1])
ys = [r[2] for r in rows]
print("trocas de estado: %d, y entre %.2f e %.2f, ticks fora do passo: %s" % (
    switches, min(ys), max(ys), bad[:5]))
ok = switches >= 4 and not bad and max(ys) > 0.5
print("PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
