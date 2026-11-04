# Track Tool: cozimento do dado de jogo (formato v1).
#
# Contrato: docs/plano-track-tool.md, "bake.py e runtime.py". O formato e a forma de leitura no
# jogo estão descritos no topo de runtime.py.
#
# bake(track_obj) grava dois Texts com o mesmo JSON:
#   - "TRACK_<nome>.json"  (canônico; lido pelo Range.track em C++ e por runtime.get no editor);
#   - "TRACK_<modulo>.py"  com DATA = '<json>' (importável no jogo: runtime.get).
# build_data()/to_json() são Python puro (testes e vetores de referência sem bpy).

import math

from . import racing
from . import runtime

ROUND = 4  # floats arredondados a 1e-4


def _r(v):
    v = round(float(v), ROUND)
    return 0.0 if v == 0.0 else v  # sem "-0.0"


def build_data(name, cyclic, length, step, s, pos, tan, lat, bank, wl, wr, el=None, er=None,
               surface=None, race=None, margin=racing.MARGIN):
    """Dict do formato v1. pos/tan: sequências (x, y, z); lat: (x, y[, z]) horizontal à esquerda.
    surface: por amostra, nome (str) ou índice; race: None = calcula (racing.racing_line).
    Cíclica: se a última amostra repete a primeira (s = length), ela é descartada."""
    n = len(s)
    if cyclic and n > 1 and (s[-1] >= length - 1e-6 or
                             math.dist(tuple(pos[-1])[:3], tuple(pos[0])[:3]) < 1e-6):
        n -= 1
    lx = []
    ly = []
    for i in range(n):
        x, y = float(lat[i][0]), float(lat[i][1])
        ll = math.hypot(x, y)
        if ll > 1e-12:
            x, y = x / ll, y / ll
        lx.append(x)
        ly.append(y)
    tx, ty, tz = [], [], []
    for i in range(n):
        x, y, z = (float(v) for v in tuple(tan[i])[:3])
        ll = math.sqrt(x * x + y * y + z * z)
        if ll > 1e-12:
            x, y, z = x / ll, y / ll, z / ll
        tx.append(x)
        ty.append(y)
        tz.append(z)
    px = [float(pos[i][0]) for i in range(n)]
    py = [float(pos[i][1]) for i in range(n)]
    pz = [float(pos[i][2]) for i in range(n)]
    wl = [max(0.0, float(v)) for v in wl[:n]]
    wr = [max(0.0, float(v)) for v in wr[:n]]
    el = [max(float(v), 0.0) for v in el[:n]] if el is not None else list(wl)
    er = [max(float(v), 0.0) for v in er[:n]] if er is not None else list(wr)
    if race is None:
        race = racing.racing_line(px, py, lx, ly, wl, wr, cyclic, margin)
    race = list(race[:n])

    names = []
    idx = []
    for i in range(n):
        v = surface[i] if surface is not None else ""
        if isinstance(v, int):
            idx.append(v)
            continue
        v = str(v or "")
        if v not in names:
            names.append(v)
        idx.append(names.index(v))
    if names == [""]:
        names = []
        idx = [0] * n

    data = {
        "version": runtime.FORMAT_VERSION,
        "name": name,
        "length": _r(length),
        "cyclic": bool(cyclic),
        "step": _r(step),
        "count": n,
    }
    for key, arr in (("s", s), ("px", px), ("py", py), ("pz", pz), ("tx", tx), ("ty", ty),
                     ("tz", tz), ("lx", lx), ("ly", ly), ("bank", bank), ("wl", wl), ("wr", wr),
                     ("el", el), ("er", er), ("race", race)):
        data[key] = [_r(arr[i]) for i in range(n)]
    data["surface"] = idx
    data["surfaces"] = names
    return data


def to_json(data):
    """JSON com uma chave por linha (legível no Text Editor e fácil de comparar)."""
    import json
    head = ("version", "name", "length", "cyclic", "step", "count")
    lines = []
    for key in head:
        lines.append("%s: %s" % (json.dumps(key), json.dumps(data[key])))
    for key in runtime.ARRAYS + ("surface", "surfaces"):
        if key in data:
            lines.append("%s: %s" % (json.dumps(key), json.dumps(data[key], separators=(",", ":"))))
    return "{\n" + ",\n".join(lines) + "\n}\n"


def to_module(text):
    """Conteúdo do Text importável: DATA = '<json>' (um literal por linha do JSON)."""
    out = ["# Gerado pelo Track Tool (Bake Track Data). Não edite: refaça o bake.",
           "# Lido por range_track.runtime.get(); o mesmo JSON está no Text .json.",
           "DATA = ("]
    for line in text.splitlines(True):
        out.append("    %r" % line)
    out.append(")")
    return "\n".join(out) + "\n"


def from_frames(frames, edges=None, name=None, race=None):
    """Dict v1 a partir de Frames (frames.py) e Edges (layout.py)."""
    n = frames.count
    el = er = None
    if edges is not None:
        el = []
        er = []
        for i in range(n):
            el.append(edges.outer(i, 1, 'BORDER')[0])
            er.append(edges.outer(i, -1, 'BORDER')[0])
    return build_data(name or frames.name, frames.cyclic, frames.length, frames.step,
                      frames.s, frames.pos, frames.tan, frames.lat, frames.bank,
                      frames.wl, frames.wr, el, er, frames.surface, race)


def _write_text(bpy, name, body):
    txt = bpy.data.texts.get(name)
    if txt is None:
        txt = bpy.data.texts.new(name)
    txt.clear()
    txt.write(body)
    txt.use_fake_user = True
    return txt


def bake(track_obj, frames=None, edges=None):
    """Cozinha o dado de jogo do traçado. Retorna o nome do Text JSON ("TRACK_<nome>.json")."""
    import bpy
    from . import frames as frames_mod
    from . import layout
    from . import props

    settings = track_obj.range_track
    if frames is None:
        frames = frames_mod.sample(track_obj, settings)
    if edges is None:
        profile = props.track_profile(track_obj)
        edges = layout.band_edges(frames, profile, settings)
    data = from_frames(frames, edges, track_obj.name)
    text = to_json(data)
    json_name = runtime.text_name(track_obj.name)
    py_name = runtime.module_name(track_obj.name) + ".py"
    if len(json_name) > 63 or len(py_name) > 63:
        raise ValueError("nome do traçado longo demais para o Text (máx. 52 caracteres): %s"
                         % track_obj.name)
    _write_text(bpy, json_name, text)
    _write_text(bpy, py_name, to_module(text))
    runtime.clear_cache()
    return json_name
