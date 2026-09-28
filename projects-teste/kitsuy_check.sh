#!/usr/bin/env bash
# Valida no Linux as correcoes dos bugs do Kitsuy (2026-09-28): crash de setHalfAnimations,
# rodas do carro sem "Use Frame Rate" e folhagem Hashed sem MSAA. Gera as cenas com o editor
# e roda cada uma no runtime. Ver docs/changelog.md, entradas de 2026-09-28.
#
# Uso: bash projects-teste/kitsuy_check.sh [RangeEngine] [RangeRuntime]
# Para comparar GPUs, rode de novo com o prefixo do offload, ex.:
#   DRI_PRIME=1 bash projects-teste/kitsuy_check.sh                       (Mesa: AMD/Intel)
#   __NV_PRIME_RENDER_OFFLOAD=1 __GLX_VENDOR_LIBRARY_NAME=nvidia bash ...  (NVIDIA)
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
ENGINE="${1:-$ROOT/build-linux-editor/bin/RangeEngine}"
RUNTIME="${2:-$ROOT/build-linux/bin/RangeRuntime}"
WIN="-w 800 450 10 10"
for exe in "$ENGINE" "$RUNTIME"; do
	[ -x "$exe" ] || { echo "nao achei $exe (passe o caminho como argumento)"; exit 1; }
done
ENGINE="$(cd "$(dirname "$ENGINE")" && pwd)/$(basename "$ENGINE")"
RUNTIME="$(cd "$(dirname "$RUNTIME")" && pwd)/$(basename "$RUNTIME")"

run() {  # run <arquivo.range>; imprime o codigo de saida (11 = segfault)
	(cd "$(dirname "$1")" && timeout 180 "$RUNTIME" $WIN "$(basename "$1")" >/dev/null 2>&1)
	echo "  saida=$?"
}

echo "== GPU"
command -v glxinfo >/dev/null && glxinfo -B | grep -E "OpenGL renderer|OpenGL core profile version" | sed 's/^/  /'

echo "== 1. setHalfAnimations + IK + skinning CPU (esperado: OK frames=600, saida=0)"
D="$HERE/halfanim_crash"
"$ENGINE" -b --python "$D/gen_halfanim_crash.py" >/dev/null 2>&1
cp "$D/halfanim_crash.blend" "$D/halfanim_crash.range"
rm -f "$D/halfanim_log.txt"
run "$D/halfanim_crash.range"
tail -n 1 "$D/halfanim_log.txt" 2>/dev/null | sed 's/^/  /'

echo "== 2. Carro com/sem Use Frame Rate (esperado: maxErr=0.0000 em todos)"
D="$HERE/car_framerate"
for cfg in "1 1" "1 0" "3 1" "3 0" "com 1" "com 0"; do
	set -- $cfg
	if [ "$1" = com ]; then name="car_com_fr$2"; args="1 $2 $D/$name.blend 0.5 -0.3"
	else name="car_s$1_fr$2"; args="$1 $2 $D/$name.blend"; fi
	"$ENGINE" -b --python "$D/gen_car_framerate.py" -- $args >/dev/null 2>&1
	cp "$D/$name.blend" "$D/$name.range"
	rm -f "$D/${name}_log.txt"
	echo "  $name:$(run "$D/$name.range") $(grep RESULT "$D/${name}_log.txt" 2>/dev/null)"
done

echo "== 3. Folhagem Hashed (esperado: aa>=2 e degrade nos PNGs, nao bloco branco)"
D="$HERE/foliage_aa"
"$ENGINE" -b --python "$D/gen_foliage_aa.py" >/dev/null 2>&1
for f in menu level level_aa0; do cp "$D/$f.blend" "$D/$f.range"; done
for f in level level_aa0 menu; do
	rm -f "$D/foliage_log.txt" "$D/level_shot.png"
	echo "  $f:$(run "$D/$f.range") $(cat "$D/foliage_log.txt" 2>/dev/null | tr '\n' ' ')"
	[ -f "$D/level_shot.png" ] && mv "$D/level_shot.png" "$D/shot_$f.png"
done
echo "  screenshots: $D/shot_*.png"
