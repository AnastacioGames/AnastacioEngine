"""Desenha o joystick dos ícones GAME e LOGIC no estilo Blender 5 (traço fino monocromático).

O Blender 5.0 não tem ícone de jogo, então o atlas desse estilo usava a silhueta da Range. As
imagens vão para tools/blender5_icons/extra; rode depois o build_blender5_icon_atlas.py.

Uso: python tools/icons/make_game_icon.py
"""
import os

from PIL import Image, ImageDraw

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
EXTRA = os.path.join(ROOT, "tools", "blender5_icons", "extra")
SS = 8
WHITE = (255, 255, 255, 255)


def joystick(size):
    n = size * SS
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    def p(x, y):
        return (x * n / 16.0, y * n / 16.0)

    w = max(1, int(round(1.0 * n / 16.0)))
    # Base em perspectiva leve, haste e bola.
    d.rounded_rectangle([p(1.5, 10.0), p(14.5, 14.5)], radius=int(1.6 * n / 16), outline=WHITE, width=w)
    d.line([p(1.5, 12.0), p(14.5, 12.0)], fill=WHITE, width=w)
    d.line([p(8.0, 5.8), p(8.0, 11.0)], fill=WHITE, width=w)
    d.ellipse([p(8.0 - 0.9, 11.0 - 0.6), p(8.0 + 0.9, 11.0 + 0.6)], outline=WHITE, width=w)
    d.ellipse([p(5.6, 1.4), p(10.4, 6.2)], outline=WHITE, width=w)
    # Botão.
    d.ellipse([p(10.9, 8.3), p(13.3, 9.9)], outline=WHITE, width=w)
    return img.resize((size, size), Image.LANCZOS)


def main():
    os.makedirs(EXTRA, exist_ok=True)
    for name in ("game", "logic"):
        for size in (16, 32):
            joystick(size).save(os.path.join(EXTRA, "%s_%d.png" % (name, size)))
    print("GAME/LOGIC em", EXTRA)


if __name__ == "__main__":
    main()
