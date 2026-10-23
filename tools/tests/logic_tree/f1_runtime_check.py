# Confere o registro de f1_compile_test.py: cada contador soma quando a regra da árvore é verdadeira.
# Uso: python3 f1_runtime_check.py <f1.txt>
import sys

rows = [[int(v) for v in l.split()] for l in open(sys.argv[1]) if l.strip()]
rules = {  # coluna: regra da árvore
    4: ("Soma S = a", lambda a, b, c: a),
    5: ("Soma E = a and b", lambda a, b, c: a and b),
    6: ("Soma Ou = a or b", lambda a, b, c: a or b),
    7: ("Soma Mista = (a or b) and not c", lambda a, b, c: (a or b) and not c),
    8: ("Soma Duas = b or not a", lambda a, b, c: b or not a),
}
ok = True
for col, (name, f) in rules.items():
    got = [rows[i + 1][col] - rows[i][col] for i in range(len(rows) - 1)]
    exp = [int(bool(f(*r[1:4]))) for r in rows]
    best = min((sum(x != y for x, y in zip(got[k - 1:], exp)), k) for k in range(1, 5))
    print("%-36s atraso %d, %d diferentes de %d" % (name, best[1], best[0], len(got)))
    ok &= best[0] == 0
print("PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
