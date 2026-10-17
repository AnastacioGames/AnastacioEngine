#!/usr/bin/env bash
# Gera a cena do guia multiplayer e roda host + cliente (127.0.0.1) em background, cada um com TEMP e pasta proprios.
# Uso (Git Bash): tools/debug/cenas/docs_guias/rodar_guia_multiplayer.sh <pasta de saida (Windows)>
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../../../.." && pwd)"
OUT="$1"
PORT="${GUIA_NET_PORT:-$((20000 + RANDOM % 20000))}"
mkdir -p "$OUT/gen" "$OUT/host" "$OUT/client"
"$ROOT/build/bin/AnastacioEngine.exe" -b --factory-startup --python "$HERE/criar_cena_guia_multiplayer.py" -- "$OUT/gen" > "$OUT/gen.log" 2>&1
grep -q "GUIA salvo" "$OUT/gen.log" || { echo "falhou gerar (veja $OUT/gen.log)"; exit 1; }
for r in host client; do cp "$OUT"/gen/*.range "$OUT"/gen/*.py "$OUT/$r/"; done
cd "$ROOT/build/bin" || exit 1
TEMP="$OUT/host" TMP="$OUT/host" GUIA_NET_ROLE=host GUIA_NET_PORT=$PORT timeout 60 ./AnastacioRuntime.exe -w 320 240 "$OUT/host/guia_multiplayer.range" > "$OUT/host/stdout.txt" 2>&1 &
sleep 1
TEMP="$OUT/client" TMP="$OUT/client" GUIA_NET_ROLE=client GUIA_NET_PORT=$PORT timeout 60 ./AnastacioRuntime.exe -w 320 240 "$OUT/client/guia_multiplayer.range" > "$OUT/client/stdout.txt" 2>&1 &
wait
for r in host client; do echo "== $r"; cat "$OUT/$r/guia_multiplayer_$r.txt"; grep -A8 Traceback "$OUT/$r/range_runtime.log.txt"; done
