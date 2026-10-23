# Confere f5.txt (ticks da cena Watch, n e hit da cena Main): a Main pausou quando "Bate" disparou.
# Uso: python3 f5_runtime_check.py <f5.txt>
import sys

ticks, n, hit = map(int, open(sys.argv[1]).read().split())
print("ticks da Watch: %d, n da Main: %d, hit: %d" % (ticks, n, hit))
ok = hit == 1 and 15 <= n <= 30 and ticks >= 90
print("PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
