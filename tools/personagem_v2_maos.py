import json, sys
from PIL import Image, ImageDraw
data = json.load(open(sys.argv[1])); out = sys.argv[2]
cores = {"Thumb":(230,25,75),"Index":(60,180,75),"Middle":(67,99,216),"Ring":(245,130,49),"Pinky":(145,30,180)}
W = 500; PAD = 20
img = Image.new("RGB", (2 * W, 2 * W), "white"); dr = ImageDraw.Draw(img)
for col, side in enumerate(("Left", "Right")):
    d = data[side]; v = d["verts"]
    # só a mão: 22 cm a partir da ponta
    tipx = min(p[0] for p in v) if side == "Left" else max(p[0] for p in v)
    v = [p for p in v if abs(p[0] - tipx) < 0.16]
    for row, (i, j, nome) in enumerate(((0, 1, "cima X,Y (frente = cima)"), (0, 2, "frente X,Z"))):
        lo = [min(p[k] for p in v) for k in (i, j)]; hi = [max(p[k] for p in v) for k in (i, j)]
        s = (W - 2 * PAD) / max(hi[0] - lo[0], hi[1] - lo[1])
        ox, oy = col * W + PAD, row * W + PAD
        P = lambda p: (ox + (p[i] - lo[0]) * s, oy + (W - 2 * PAD) - (p[j] - lo[1]) * s)
        for p in v:
            x, y = P(p); dr.ellipse((x-1.5, y-1.5, x+1.5, y+1.5), fill=(120, 120, 120))
        for n, (h, t) in d["bones"].items():
            c = next((c for k, c in cores.items() if k in n), (0, 0, 0))
            dr.line([P(h), P(t)], fill=c, width=3)
            x, y = P(h); dr.ellipse((x-3, y-3, x+3, y+3), fill=c)
        dr.text((ox, oy - 15), "%s - %s" % (side, nome), fill="black")
        dr.rectangle((col*W, row*W, col*W+W-1, row*W+W-1), outline=(200,200,200))
img.save(out)
