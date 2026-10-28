#!/bin/bash
# Testa o pacote Linux de uma release extraído numa pasta limpa (nunca a pasta de build).
# Uso, na raiz do repo, depois do container-build-22.04.sh:
#   bash tools/linux/testar-release.sh 0.6.1
# Variáveis: PKG_TAR (padrão build-linux/dist/AnastacioEngine-<versao>-linux-x86_64.tar.xz),
#            WORK (padrão /tmp/anastacio-release-<versao>).
# Os testes que precisam de janela rodam com DISPLAY ou xvfb-run; sem os dois, são pulados e listados.
# Resultado em $WORK/resultado.txt; sai com 1 se algo falhou.
set -uo pipefail
version="${1:?uso: testar-release.sh <versao>}"
repo="$(cd "$(dirname "$0")/../.." && pwd)"
pkg="AnastacioEngine-$version-linux-x86_64"
tar_file="${PKG_TAR:-$repo/build-linux/dist/$pkg.tar.xz}"
work="${WORK:-/tmp/anastacio-release-$version}"
log="$work/resultado.txt"
failed=0

rm -rf "$work"; mkdir -p "$work/out"
: > "$log"
ok()   { echo "OK    $*" | tee -a "$log"; }
fail() { echo "FALHA $*" | tee -a "$log"; failed=1; }
skip() { echo "PULO  $*" | tee -a "$log"; }

tar -xJf "$tar_file" -C "$work" || { fail "extrair $tar_file"; exit 1; }
root="$work/$pkg"
editor="$root/AnastacioEngine"
runtime="$root/AnastacioRuntime"
sha256sum "$tar_file" | tee -a "$log"

# 1. Bibliotecas: nada "not found" nos executáveis e nas .so do pacote. As .so de lib/ não têm RPATH próprio
# (acham as vizinhas pelo RPATH do executável), então são checadas com lib/ no LD_LIBRARY_PATH.
missing=$( { for f in "$editor" "$runtime"; do
        [ -f "$f" ] && ldd "$f" 2>/dev/null | grep "not found" | sed "s|^|$(basename "$f"): |"
    done
    for f in "$root"/lib/*.so* "$root"/libae_*.so; do
        [ -f "$f" ] && LD_LIBRARY_PATH="$root/lib:$root" ldd "$f" 2>/dev/null | grep "not found" | sed "s|^|$(basename "$f"): |"
    done; } | sort -u)
# Som, OpenGL e X11 vêm do sistema do usuário (o pacote não leva); sem eles é só aviso.
system_libs='lib(asound|pulse|OpenGL|GL|GLX|EGL|X[a-z0-9]*|xcb[a-z0-9-]*|wayland[a-z-]*)\.so'
sys_missing=$(echo "$missing" | grep -E "=> *not found" | grep -E "	$system_libs" )
missing=$(echo "$missing" | grep -v -E "	$system_libs" | grep . )
[ -n "$sys_missing" ] && echo "AVISO bibliotecas do sistema ausentes nesta máquina: $sys_missing" | tee -a "$log"
[ -z "$missing" ] && ok "ldd sem bibliotecas faltando" || fail "ldd: $missing"

# 2. Arquivos que já faltaram em releases anteriores.
for p in 2.79/python/bin/python3.11 2.79/datafiles/colormanagement/config.ocio web/android-template \
         2.79/datafiles/sounds/effects/trovao1.wav 2.79/scripts/modules/anastacio_network; do
    [ -e "$root/$p" ] && ok "tem $p" || fail "falta $p"
done
[ -e "$root/RangeEngine" ] || [ -e "$root/RangeRuntime" ] && fail "nome antigo RangeEngine/RangeRuntime no pacote"

# 3. Editor em background: versão certa e Python 3.11 do pacote.
"$editor" -b --factory-startup --python-expr \
    "import bpy, sys; open('$work/out/versao.txt','w').write(sys.version.split()[0] + ' ' + sys.prefix)" \
    > "$work/out/editor_b.log" 2>&1
grep -q "^3\.11" "$work/out/versao.txt" 2>/dev/null && grep -q "$root" "$work/out/versao.txt" \
    && ok "editor -b com Python $(cat "$work/out/versao.txt")" || fail "editor -b (ver out/editor_b.log)"
grep -aq "AnastacioEngine $version\|$version" "$editor" && ok "binário com a versão $version" \
    || fail "binário não tem a string $version"

# 4. Testes headless de tools/test_*.py (os mesmos da 0.5.3).
run_test() {  # nome, args extras...
    local name="$1"; shift
    if (cd "$work/out" && "$@") > "$work/out/$name.log" 2>&1; then ok "$name"; else fail "$name (ver out/$name.log)"; fi
}
base=("$editor" -b --factory-startup --python-exit-code 1 --python)
for t in test_baked_ao_smoke test_baked_static_smoke test_material_atlas test_material_classic_and_categories \
         test_material_to_pbr_uv test_object_render_categories test_texture_preview_layout; do
    run_test "$t" "${base[@]}" "$repo/tools/$t.py"
done
run_test test_material_atlas_integration "${base[@]}" "$repo/tools/test_material_atlas_integration.py"
run_test test_weather_sounds_auto "${base[@]}" "$repo/tools/test_weather_sounds_auto.py" -- "$work/out/sons"
for t in test_logic_convert_bricks2_codegen test_logic_convert_f5_codegen test_logic_convert_f6_codegen \
         test_logic_convert_f7_codegen; do
    run_test "$t" env GEN_OUT="$work/out/$t" "${base[@]}" "$repo/tools/$t.py"
done

# 5. Runtime: cena mínima roda 60 frames com o Python do pacote e sai sozinha.
"$editor" -b --factory-startup --python "$repo/tools/linux/release_smoke_scene.py" -- \
    "$work/out/smoke.range" "$work/out/smoke.txt" > "$work/out/smoke_scene.log" 2>&1
display=()
if [ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]; then display=(); elif command -v xvfb-run >/dev/null; then display=(xvfb-run -a); fi
if [ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ] || [ ${#display[@]} -gt 0 ]; then
    (cd "$work" && timeout 60 "${display[@]}" "$runtime" --server "$work/out/smoke.range") > "$work/out/smoke_run.log" 2>&1
    grep -q "^ok 60 3\.11" "$work/out/smoke.txt" 2>/dev/null && ok "runtime --server rodou 60 frames" \
        || fail "runtime --server (ver out/smoke_run.log)"
    run_test test_material_atlas_modal "${display[@]}" "$editor" --factory-startup --python-exit-code 1 \
        --python "$repo/tools/test_material_atlas_modal.py" -- --case cancel
else
    skip "runtime --server e test_material_atlas_modal (sem DISPLAY nem xvfb-run)"
fi

echo "---" | tee -a "$log"
[ $failed -eq 0 ] && echo "TUDO OK ($log)" || echo "HÁ FALHAS ($log)"
exit $failed
