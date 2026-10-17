"""Pipeline de atlas de texto bitmap editável por IA.

Cada glifo é um PNG separado com tamanho de célula fixo, então editar uma
letra nunca move as outras. O atlas final é montado pelo código do caractere.

Uso:
  python tools/text_atlas.py init  PASTA --font arial.ttf [--size 48] [--chars ascii+latin1]
  python tools/text_atlas.py build PASTA      # glyphs/*.png|*.svg -> atlas.png + atlas.json
  python tools/text_atlas.py preview PASTA [--text "Olá, Mundo!"]
  python tools/text_atlas.py sheet PASTA      # glifos -> sheet.png (editar/IA) + sheet_guia.png
  python tools/text_atlas.py unsheet PASTA [editada.png]   # folha -> glyphs/ (depois rode build)
  python tools/text_atlas_style.py PASTA --style madeira   # estilo pronto como ponto de partida

Layout da PASTA:
  manifest.json          cell, baseline, line_height, padding, glyphs{hex: {advance}}
  glyphs/0041_A.png      um arquivo por glifo, exatamente cell x cell, RGBA
  glyphs/E000_coin.svg   SVG também vale (precisa de cairosvg); vence o PNG do mesmo código
  atlas.png / atlas.json gerados por build (não editar à mão)
  preview.png            folha de prova gerada por build/preview
"""

import argparse
import json
import math
import os
import re
import sys

from PIL import Image, ImageDraw, ImageFont

CHARSETS = {
    "ascii": [chr(c) for c in range(0x20, 0x7F)],
    "latin1": [chr(c) for c in range(0xA0, 0x100)],
}
GLYPH_RE = re.compile(r"^([0-9A-Fa-f]{4,6})(?:_.*)?\.(png|svg)$")
SAFE_NAME = re.compile(r"[A-Za-z0-9]")


def parse_chars(spec):
    chars = []
    for part in spec.split("+"):
        if part in CHARSETS:
            chars += CHARSETS[part]
        else:
            chars += list(part)
    seen = set()
    return [c for c in chars if not (c in seen or seen.add(c))]


def glyph_filename(code, ext="png"):
    ch = chr(code)
    suffix = ch if SAFE_NAME.match(ch) else ""
    return "%04X%s.%s" % (code, "_" + suffix if suffix else "", ext)


def load_manifest(folder):
    with open(os.path.join(folder, "manifest.json"), encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)


def cmd_init(args):
    font = ImageFont.truetype(args.font, args.size)
    ascent, descent = font.getmetrics()
    pad = args.padding
    cell = int(math.ceil(max(ascent + descent, args.size))) + pad * 2
    baseline = pad + ascent
    gdir = os.path.join(args.folder, "glyphs")
    os.makedirs(gdir, exist_ok=True)
    glyphs = {}
    for ch in parse_chars(args.chars):
        code = ord(ch)
        advance = font.getlength(ch)
        img = Image.new("RGBA", (cell, cell), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        # Origem x = padding; o texto pisa na linha de base.
        draw.text((pad, baseline), ch, font=font, fill=(255, 255, 255, 255), anchor="ls")
        if ch != " ":
            path = os.path.join(gdir, glyph_filename(code))
            if os.path.exists(path) and not args.force:
                pass  # preserva edições já feitas
            else:
                img.save(path)
        glyphs["%04X" % code] = {"char": ch, "advance": round(advance, 2)}
    manifest = {
        "version": 1,
        "font": os.path.basename(args.font),
        "size": args.size,
        "cell": cell,
        "padding": pad,
        "baseline": baseline,
        "line_height": ascent + descent,
        "glyphs": glyphs,
    }
    save_json(os.path.join(args.folder, "manifest.json"), manifest)
    print("init: %d glifos, célula %dpx, em %s" % (len(glyphs), cell, args.folder))


def load_glyph_image(path, cell):
    if path.lower().endswith(".svg"):
        try:
            import cairosvg
        except ImportError:
            sys.exit("SVG requer 'pip install cairosvg': %s" % path)
        import io
        png = cairosvg.svg2png(url=path, output_width=cell, output_height=cell)
        img = Image.open(io.BytesIO(png))
    else:
        img = Image.open(path)
    img = img.convert("RGBA")
    if img.size != (cell, cell):
        sys.exit("%s tem %dx%d; precisa ser %dx%d (célula fixa)" % (
            os.path.basename(path), img.size[0], img.size[1], cell, cell))
    return img


def collect_glyph_files(folder):
    files = {}
    gdir = os.path.join(folder, "glyphs")
    for name in sorted(os.listdir(gdir)) if os.path.isdir(gdir) else []:
        m = GLYPH_RE.match(name)
        if not m:
            continue
        code = int(m.group(1), 16)
        # SVG vence PNG do mesmo código.
        if code in files and files[code].endswith(".svg"):
            continue
        files[code] = os.path.join(gdir, name)
    return files


def cmd_build(args):
    man = load_manifest(args.folder)
    cell, pad = man["cell"], man["padding"]
    files = collect_glyph_files(args.folder)
    codes = sorted(set(int(k, 16) for k in man["glyphs"]) | set(files))
    cols = max(1, int(math.ceil(math.sqrt(len(codes)))))
    rows = int(math.ceil(len(codes) / cols))
    w = 1 << int(math.ceil(math.log2(cols * cell)))
    h = 1 << int(math.ceil(math.log2(max(1, rows * cell))))
    atlas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    out = []
    for i, code in enumerate(codes):
        key = "%04X" % code
        info = man["glyphs"].get(key, {})
        x, y = (i % cols) * cell, (i // cols) * cell
        if code in files:
            atlas.paste(bleed_edges(load_glyph_image(files[code], cell)), (x, y))
        advance = info.get("advance", cell - pad * 2)
        out.append({
            "code": code,
            # UV com origem embaixo (OpenGL); a célula inteira, inclusive padding.
            "u0": x / w, "v0": 1.0 - (y + cell) / h,
            "u1": (x + cell) / w, "v1": 1.0 - y / h,
            "advance": advance,
        })
    atlas.save(os.path.join(args.folder, "atlas.png"))
    save_json(os.path.join(args.folder, "atlas.json"), {
        "version": 1, "size": man["size"], "width": w, "height": h, "cell": cell, "padding": pad,
        "baseline": man["baseline"], "line_height": man["line_height"],
        "glyphs": out,
    })
    print("build: %d glifos -> atlas %dx%d" % (len(out), w, h))
    render_preview(args.folder, args.text)


def render_preview(folder, text):
    man = load_manifest(folder)
    data = json.load(open(os.path.join(folder, "atlas.json"), encoding="utf-8"))
    atlas = Image.open(os.path.join(folder, "atlas.png")).convert("RGBA")
    cell, pad, w, h = data["cell"], data["padding"], data["width"], data["height"]
    by_code = {g["code"]: g for g in data["glyphs"]}

    def crop(g):
        x0, y1 = round(g["u0"] * w), round((1 - g["v0"]) * h)
        return atlas.crop((x0, y1 - cell, x0 + cell, y1))

    # Linha 1..N: frase de teste; abaixo: todos os glifos com código.
    lines = text.split("\\n")
    lh = data["line_height"]
    width = max(400, int(max(sum(by_code.get(ord(c), {"advance": cell})["advance"]
                                for c in ln) for ln in lines)) + cell)
    cols = max(1, width // (cell + 4))
    sheet_rows = int(math.ceil(len(by_code) / cols))
    img = Image.new("RGBA", (width, int(lh * len(lines)) + pad * 2 + 8 +
                             sheet_rows * (cell + 14)), (40, 40, 48, 255))
    draw = ImageDraw.Draw(img)
    for li, ln in enumerate(lines):
        pen = 0.0
        top = int(li * lh)
        for c in ln:
            g = by_code.get(ord(c))
            if g is None:
                draw.rectangle((pen, top, pen + cell * 0.5, top + cell), outline=(255, 0, 0, 255))
                pen += cell * 0.5
                continue
            img.alpha_composite(crop(g), (int(round(pen)), top))
            pen += g["advance"]
    y0 = int(lh * len(lines)) + pad * 2 + 8
    for i, code in enumerate(sorted(by_code)):
        x, y = (i % cols) * (cell + 4), y0 + (i // cols) * (cell + 14)
        draw.rectangle((x, y, x + cell - 1, y + cell - 1), outline=(90, 90, 110, 255))
        bl = y + data["baseline"]
        draw.line((x, bl, x + cell - 1, bl), fill=(0, 140, 255, 120))
        img.alpha_composite(crop(by_code[code]), (x, y))
        draw.text((x, y + cell), "%04X" % code, fill=(160, 160, 170, 255))
    img.save(os.path.join(folder, "preview.png"))
    print("preview:", os.path.join(folder, "preview.png"))


SHEET_COLS = 16


def sheet_layout(folder):
    man = load_manifest(folder)
    codes = sorted(int(k, 16) for k in man["glyphs"] if int(k, 16) != 0x20)
    cell = man["cell"]
    rows = int(math.ceil(len(codes) / SHEET_COLS))
    return man, codes, cell, (SHEET_COLS * cell, rows * cell)


def cmd_sheet(args):
    """Junta os glifos numa folha única (para IA/editor) + folha-guia com grade."""
    man, codes, cell, size = sheet_layout(args.folder)
    files = collect_glyph_files(args.folder)
    sheet = Image.new("RGBA", size, (0, 0, 0, 0))
    guide = Image.new("RGBA", size, (40, 40, 48, 255))
    draw = ImageDraw.Draw(guide)
    for i, code in enumerate(codes):
        x, y = (i % SHEET_COLS) * cell, (i // SHEET_COLS) * cell
        if code in files:
            sheet.alpha_composite(load_glyph_image(files[code], cell), (x, y))
        draw.rectangle((x, y, x + cell - 1, y + cell - 1), outline=(90, 90, 110, 255))
        draw.line((x, y + man["baseline"], x + cell - 1, y + man["baseline"]), fill=(0, 140, 255, 255))
        draw.text((x + 2, y + 1), "%04X %s" % (code, chr(code)), fill=(160, 160, 170, 255))
    guide.alpha_composite(sheet)
    sheet.save(os.path.join(args.folder, "sheet.png"))
    guide.save(os.path.join(args.folder, "sheet_guia.png"))
    print("sheet: %dx%d, %d glifos, %d colunas de %dpx" % (size[0], size[1], len(codes), SHEET_COLS, cell))


def remove_background(img, tol):
    """Imagem sem alpha (comum vindo de IA): a cor do canto vira transparente."""
    if img.getchannel("A").getextrema()[0] < 255:
        return img
    # "Color to alpha" (como no GIMP): cada pixel é tratado como mistura
    # cor*a + fundo*(1-a); acha o menor alpha que explica a cor e remove o fundo
    # da mistura. Assim sombras/bordas suaves não ficam com halo da cor do fundo.
    # Só vale na faixa da borda: o miolo da letra (longe do fundo) fica opaco,
    # senão cores claras viram semitransparentes (laranja sobre branco ~70%).
    from PIL import ImageFilter
    bg = img.getpixel((0, 0))[:3]
    px = img.load()
    w, h = img.size
    far = Image.new("L", img.size, 0)
    fpx = far.load()
    for y in range(h):
        for x in range(w):
            r, g, b, _ = px[x, y]
            if max(abs(r - bg[0]), abs(g - bg[1]), abs(b - bg[2])) > tol:
                fpx[x, y] = 255
    core = far.filter(ImageFilter.MinFilter(5)).load()
    for y in range(h):
        for x in range(w):
            r, g, b, _ = px[x, y]
            if core[x, y]:
                px[x, y] = (r, g, b, 255)
                continue
            a = 0.0
            for c, k in zip((r, g, b), bg):
                if c > k:
                    a = max(a, (c - k) / (255.0 - k) if k < 255 else 0.0)
                elif c < k:
                    a = max(a, (k - c) / float(k) if k > 0 else 0.0)
            if a * 255 <= tol * 0.25:
                px[x, y] = (0, 0, 0, 0)
                continue
            fg = [int(round(min(255, max(0, (c - k) / a + k)))) for c, k in zip((r, g, b), bg)]
            px[x, y] = (fg[0], fg[1], fg[2], int(round(a * 255)))
    return img


def bleed_edges(img, passes=4):
    """Pixels transparentes herdam a cor do vizinho opaco, para o filtro linear
    da textura não puxar preto/branco para a borda da letra."""
    from PIL import ImageFilter
    rgb = img.convert("RGB")
    alpha = img.getchannel("A")
    solid_mask = alpha.point(lambda v: 255 if v > 0 else 0)
    for _ in range(passes):
        grown = rgb.filter(ImageFilter.MaxFilter(3))
        grown_mask = solid_mask.filter(ImageFilter.MaxFilter(3))
        rgb = Image.composite(rgb, grown, solid_mask)
        solid_mask = grown_mask
    out = rgb.convert("RGBA")
    out.putalpha(alpha)
    return out


def cmd_unsheet(args):
    """Corta a folha editada de volta em glyphs/ (cada célula volta ao seu código)."""
    man, codes, cell, size = sheet_layout(args.folder)
    path = args.image or os.path.join(args.folder, "sheet.png")
    img = Image.open(path).convert("RGBA")
    if img.size != size:
        print("aviso: %s tem %dx%d, redimensionando para %dx%d" % (
            os.path.basename(path), img.size[0], img.size[1], size[0], size[1]))
        img = img.resize(size, Image.LANCZOS)
    img = remove_background(img, args.tolerance)
    gdir = os.path.join(args.folder, "glyphs")
    for i, code in enumerate(codes):
        x, y = (i % SHEET_COLS) * cell, (i // SHEET_COLS) * cell
        img.crop((x, y, x + cell, y + cell)).save(os.path.join(gdir, glyph_filename(code)))
    print("unsheet: %d glifos atualizados a partir de %s" % (len(codes), path))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("init")
    p.add_argument("folder")
    p.add_argument("--font", required=True)
    p.add_argument("--size", type=int, default=48)
    p.add_argument("--padding", type=int, default=4)
    p.add_argument("--chars", default="ascii+latin1")
    p.add_argument("--force", action="store_true", help="sobrescreve glifos já editados")
    p.set_defaults(func=cmd_init)
    for name, fn in (("build", cmd_build), ("preview", None)):
        p = sub.add_parser(name)
        p.add_argument("folder")
        p.add_argument("--text", default="Olá, Mundo! Ação: 123\\nÁÉÍÓÚ ãõç @#$%")
        p.set_defaults(func=fn or (lambda a: render_preview(a.folder, a.text)))
    p = sub.add_parser("sheet", help="folha única para editar (sheet.png + sheet_guia.png)")
    p.add_argument("folder")
    p.set_defaults(func=cmd_sheet)
    p = sub.add_parser("unsheet", help="corta a folha editada de volta em glyphs/")
    p.add_argument("folder")
    p.add_argument("image", nargs="?", help="folha editada (padrão: PASTA/sheet.png)")
    p.add_argument("--tolerance", type=int, default=24, help="tolerância do fundo sem alpha")
    p.set_defaults(func=cmd_unsheet)
    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
