#!/usr/bin/env python3
"""Aplica no SDL2 do Emscripten a remocao do gate de timestamp do gamepad.

A porta SDL2 do emsdk (SDL-release-2.32.10, src/joystick/emscripten/SDL_sysjoystick.c) so processa
botoes/eixos quando Gamepad.timestamp muda. Em varios navegadores/SOs o timestamp nao avanca de forma
confiavel e o soltar do D-pad se perde (entrada presa em ACTIVE). O patch compara os valores direto a
cada chamada. O cache do emsdk fica fora do repo, entao este script e a fonte versionada da correcao.

Uso: python tools/web/patch-sdl2-gamepad.py [--emsdk D:/emsdk] [--check]
  Idempotente. Apos aplicar, apaga libSDL2*.a do cache para o proximo build do runtime recompilar a porta.
  --check apenas informa o estado (retorna 0 se aplicado, 1 se falta aplicar).
"""
import argparse
import os
import sys
from pathlib import Path

REL = Path("upstream/emscripten/cache/ports/sdl2/SDL-release-2.32.10/src/joystick/emscripten/SDL_sysjoystick.c")
LIB_DIR = Path("upstream/emscripten/cache/sysroot/lib")
MARKER = "Range: gamepad timestamp gate removed"
CR, LF = chr(13), chr(10)
CRLF = CR + LF

OLD = "            if (gamepadState.timestamp == 0 || gamepadState.timestamp != item->timestamp) {" + LF
NEW = ("            /* " + MARKER + ". Some browser/OS combinations never advance Gamepad.timestamp" + LF +
       "             * reliably, which froze the last polled state (input stuck ACTIVE after release)." + LF +
       "             * Button/axis values are diffed directly on every call; the per-element comparisons" + LF +
       "             * below already avoid redundant events. */" + LF +
       "            {" + LF)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--emsdk", default=os.environ.get("EMSDK", "D:/emsdk"))
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    emsdk = Path(args.emsdk)
    src = emsdk / REL
    if not src.is_file():
        print(f"erro: {src} nao existe. Compile o runtime Web uma vez (baixa a porta sdl2) e rode de novo.")
        return 2
    text = src.read_bytes().decode("utf-8")
    eol = CRLF if CRLF in text else LF
    text = text.replace(CRLF, LF)

    if MARKER in text:
        print("SDL2 gamepad: patch ja aplicado.")
        return 0
    if args.check:
        print("SDL2 gamepad: patch NAO aplicado.")
        return 1
    if OLD not in text:
        print("erro: trecho original nao encontrado (versao do SDL2 mudou, ou arquivo editado a mao).")
        print("Restaure a porta (apague cache/ports/sdl2 e rebuild) e rode de novo.")
        return 2

    out = text.replace(OLD, NEW, 1).replace(LF, eol)
    src.write_bytes(out.encode("utf-8"))
    removed = []
    for lib in (emsdk / LIB_DIR).rglob("libSDL2*.a"):
        lib.unlink()
        removed.append(lib.name)
    print("SDL2 gamepad: patch aplicado." + (f" Removido {', '.join(removed)} (sera recompilada)." if removed else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
