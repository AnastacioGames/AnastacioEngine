# Track Tool: leitura do dado cozido da pista no jogo (Python puro, sem bpy).
#
# Referência da semântica de Range.track (C++, F5): os dois precisam dar o mesmo resultado
# (tolerância 1 mm), conferido pelos vetores de tools/debug/track_tool/ref/.
# Contrato: docs/plano-track-tool.md, "Contrato entre módulos" -> bake.py / runtime.py.
#
# ---------------------------------------------------------------------------------------------
# Como o jogo lê o dado cozido (decisão de F4)
# ---------------------------------------------------------------------------------------------
# O jogo não tem bpy e nenhuma API de Range/bge.logic devolve o conteúdo de um Text. O que existe
# é o import de textos internos: KX_PythonInit.cpp (initGamePython) chama
# bpy_import_main_set(main), e o __import__ do builtins é trocado por blender_import
# (source/blender/python/generic/bpy_internal_import.c). Quando o import normal falha, ele procura
# no Main do jogo (e nos Mains do LibLoad, addImportMain) um Text chamado "<nome>.py" e executa.
# Só serve para ".py": um Text "TRACK_x.json" NÃO é importável.
#
# Por isso o bake grava dois Texts com o mesmo conteúdo:
#   - "TRACK_<nome>.json": o JSON v1 (canônico; o C++ de F5 lê direto do Main);
#   - "TRACK_<modulo>.py":  DATA = '...json...', importável no jogo (get() abaixo).
# <modulo> = nome com todo caractere fora de [A-Za-z0-9_] trocado por "_" (module_name()).
# get() usa builtins.__import__ (o gancho); importlib.import_module NÃO passa pelo gancho.
# No fim do jogo restorePySysObjects() devolve o sys.modules de antes, então o texto e este
# módulo são importados de novo a cada partida (o cache de get() não fica velho).
# No editor (bpy disponível, sem jogo rodando) get() lê o Text .json direto de bpy.data.
#
# Disponibilidade: o player põe 2.79/scripts/modules no sys.path (KX_PythonInit.cpp, "Standalone
# Python does not run bpy.utils startup"), então `import range_track.runtime` funciona rodando de
# build/bin. No jogo exportado por "Save As Runtime" sem "Copy Scripts" só vão anastacio_network e
# anastacio_video (addons/game_engine_save_as_runtime.py): range_track NÃO vai junto (o mesmo vale
# hoje para range_ui_runtime/range_args/range_locale). Até Range.track (C++) existir, o export
# precisa copiar scripts/modules/range_track (ou o jogo leva uma cópia deste arquivo).
#
# ---------------------------------------------------------------------------------------------
# Formato v1 (arrays planos, um item por amostra; metros, radianos; "esquerda" = +lateral)
# ---------------------------------------------------------------------------------------------
# version, name, length, cyclic, step, count
# s px py pz tx ty tz lx ly bank wl wr el er race   (floats)   surface (ints)   surfaces (nomes)
# - s cresce; s[0] = 0. Cíclica: as amostras cobrem [0, length) (sem repetir a primeira no fim) e
#   o último segmento vai da amostra count-1 até a 0, com s de s[count-1] até length.
#   Aberta: s[count-1] = length.
# - (lx, ly): lateral horizontal unitária, para a esquerda. (tx, ty, tz): tangente unitária 3D.
# - bank: + = cai para a esquerda (borda esquerda mais baixa). Superfície no deslocamento
#   lateral u: z = pz - u * tan(bank).
# - wl, wr: meia largura do asfalto (>= 0). el, er: borda externa da faixa BORDER (ou da última
#   faixa transitável), distância (>= 0) do centro. race: deslocamento lateral da linha ideal
#   (+ = esquerda), dentro de [-wr, wl].
#
# ---------------------------------------------------------------------------------------------
# Semântica (o C++ deve repetir passo a passo)
# ---------------------------------------------------------------------------------------------
# Segmento i: amostra i -> j = i + 1 (cíclica: o último vai para 0), ds = s[j] - s[i]
# (último da cíclica: length - s[i]).
#
# Interpolação por s (pointAt, tangentAt, bankAt, widthAt, racingLine, surfaceAt):
#   cíclica: s = s mod length (resto não negativo); aberta: s limitado a [0, length].
#   i = (último índice com s[i] <= s), limitado a [0, count-1]; aberta com i = count-1: t = 0.
#   t = (s - s[i]) / ds (0 se ds <= 0), limitado a [0, 1]; valor = a[i] + (a[j] - a[i]) * t.
#   tangentAt: tangente interpolada normalizada (3D). Lateral: (lx, ly) interpolada normalizada.
#   racingLine: P + race * L (XY) e z = pz - race * tan(bank), tudo interpolado em s.
#   surfaceAt: surfaces[surface[i]] (sem interpolar; "" se não houver nomes).
#
# project(pos) -> (s, side, dist):
#   1. Amostra mais próxima k pela métrica m = dx² + dy² + (2·dz)² (dz = z - pz[k]); empate: menor k.
#      A grade (células de CELL m em XY, anéis a partir da célula de pos) só acelera: para depois do
#      anel r quando melhor m <= (r·CELL)².
#   2. Candidatos: segmentos k-2, k-1, k, k+1 (cíclica: com volta; aberta: só os que existem,
#      0..count-2, sem repetir), nessa ordem.
#   3. Em cada segmento (XY): acha t com p - P(t) paralelo a L(t), onde P(t) = P0 + t·D e
#      L(t) = L0 + t·(L1 - L0) (laterais SEM normalizar). Com q = p - P0, dL = L1 - L0 e
#      cross(a, b) = a.x·b.y - a.y·b.x:
#         A = -cross(D, dL), B = cross(q, dL) - cross(D, L0), C = cross(q, L0);  A·t² + B·t + C = 0
#      Raízes: |A| < 1e-12 -> t = -C/B (nenhuma se |B| < 1e-12); senão disc = B² - 4AC, sem raiz se
#      disc < 0; com disc >= 0: Q = -(B + sgn(B)·sqrt(disc)) / 2 (sgn(0) = +1), raízes Q/A e C/Q
#      (essa só se Q != 0). Aceita raiz em [-1e-6, 1 + 1e-6]; se houver duas, a mais perto de t_o;
#      se nenhuma, t = t_o. t_o = q·D / |D|² (0 se |D|² < 1e-12). Por fim t limitado a [0, 1].
#   4. No t escolhido: C = P(t) (3D), Ln = L(t) normalizado, u = (p - C)·Ln (XY),
#      e² = |p - C - u·Ln|² (XY), zs = C.z - u·tan(bank(t)), dz = z - zs.
#      Nota: e² < 1e-12 (o ponto está na seção do segmento) -> (0, u² + (2·dz)²); senão (1, e²).
#      Fica o segmento de menor nota (comparação em ordem; empate: o primeiro da ordem).
#   5. s = s[i] + t·ds (cíclica: se s >= length, s -= length); side = +1 se u >= 0, senão -1;
#      dist = |u|.
#   Posição com só 2 componentes (x, y): dz = 0 nos passos 1 e 4.
#
# isOnRoad(pos): projeta (passos acima); aberta e e² > 0.25 (passou do começo/fim): False.
#   w = wl(s) se side = +1, senão wr(s). True se dist <= w e |dz| <= 3 (dz do passo 4;
#   sem z, ignora a altura).
#
# Retornos de ponto/vetor: mathutils.Vector quando existir (no jogo e no editor), senão tupla.

import bisect
import math

try:  # opcional: no jogo e no editor existe; com o Python do sistema não
    from mathutils import Vector as _Vec
except ImportError:  # pragma: no cover - depende do ambiente
    _Vec = tuple

FORMAT_VERSION = 1
TEXT_PREFIX = "TRACK_"
CELL = 10.0          # tamanho da célula da grade (m), só desempenho
Z_WEIGHT = 2.0       # peso da altura na escolha da amostra/segmento (pontes e cruzamentos)
HEIGHT_TOL = 3.0     # isOnRoad: altura plausível em relação à superfície (m)
_ROOT_EPS = 1e-6

ARRAYS = ("s", "px", "py", "pz", "tx", "ty", "tz", "lx", "ly",
          "bank", "wl", "wr", "el", "er", "race")


def text_name(name):
    """Nome do Text canônico (JSON) da pista."""
    return "%s%s.json" % (TEXT_PREFIX, name)


def module_name(name):
    """Nome do módulo do Text importável ("TRACK_<nome>.py" sem o .py)."""
    return TEXT_PREFIX + "".join(c if (c.isalnum() and c.isascii()) or c == "_" else "_" for c in name)


class Track:
    """Pista cozida (formato v1). Use Track.from_json(texto) ou get(nome)."""

    def __init__(self, data):
        n = len(data["s"])
        if n < 1:
            raise ValueError("track has no samples")
        if "count" in data and int(data["count"]) != n:
            raise ValueError("'count' (%d) differs from the size of 's' (%d)" % (data["count"], n))
        self.version = int(data.get("version", 1))
        self.name = data.get("name", "")
        self.cyclic = bool(data.get("cyclic", False))
        self.step = float(data.get("step", 1.0))
        self.count = n
        for key in ARRAYS:
            arr = data.get(key)
            if arr is None:
                arr = [0.0] * n
                if key == "lx":  # sem lateral: perpendicular à tangente
                    arr = [-float(v) for v in data.get("ty", [0.0] * n)]
                elif key == "ly":
                    arr = [float(v) for v in data.get("tx", [1.0] * n)]
            elif len(arr) != n:
                raise ValueError("'%s' has %d items, expected %d" % (key, len(arr), n))
            setattr(self, "_" + key, tuple(float(v) for v in arr))
        surf = data.get("surface")
        self._surface = tuple(int(v) for v in surf) if surf and len(surf) == n else (0,) * n
        self.surfaces = tuple(data.get("surfaces", ()))
        self.length = float(data.get("length", self._s[-1]))
        if self.length <= 0.0:
            self.length = self._s[-1]
        self._nseg = n if self.cyclic else n - 1
        self._build_segments()
        self._build_grid()

    @classmethod
    def from_json(cls, text):
        import json
        return cls(json.loads(text))

    # ------------------------------------------------------------------ preparo

    def _segment_end(self, i):
        j = i + 1
        if j < self.count:
            return j, self._s[j] - self._s[i]
        return 0, self.length - self._s[i]

    def _build_segments(self):
        """Constantes por segmento para project(): só desempenho (mesmas contas dos passos 3-4)."""
        px, py, pz, lx, ly, bank = self._px, self._py, self._pz, self._lx, self._ly, self._bank
        segs = []
        for i in range(self._nseg):
            j, _ds = self._segment_end(i)
            Dx = px[j] - px[i]
            Dy = py[j] - py[i]
            dLx = lx[j] - lx[i]
            dLy = ly[j] - ly[i]
            dd = Dx * Dx + Dy * Dy
            segs.append((px[i], py[i], Dx, Dy, lx[i], ly[i], dLx, dLy,
                         -(Dx * dLy - Dy * dLx),           # A
                         Dx * ly[i] - Dy * lx[i],          # cross(D, L0)
                         dd >= 1e-12, dd,
                         pz[i], pz[j] - pz[i], bank[i], bank[j] - bank[i]))
        self._segs = tuple(segs)

    def _build_grid(self):
        """Células de CELL m em XY. _near[c]: amostras da célula c e das 8 vizinhas (anéis 0-1)."""
        px, py = self._px, self._py
        self._gx0 = min(px)
        self._gy0 = min(py)
        nx = self._nx = int((max(px) - self._gx0) / CELL) + 1
        ny = self._ny = int((max(py) - self._gy0) / CELL) + 1
        cells = {}
        for k in range(self.count):
            cx = int((px[k] - self._gx0) / CELL)
            cy = int((py[k] - self._gy0) / CELL)
            cells.setdefault(cy * nx + cx, []).append(k)
        self._cells = {c: tuple(v) for c, v in cells.items()}
        near = {}
        for c, items in cells.items():
            cy, cx = divmod(c, nx)
            for gy in range(cy - 1, cy + 2):
                for gx in range(cx - 1, cx + 2):
                    if 0 <= gx < nx and 0 <= gy < ny:
                        near.setdefault(gy * nx + gx, []).extend(items)
        self._near = {c: tuple(sorted(v)) for c, v in near.items()}

    # ------------------------------------------------------------- projeção

    def _nearest_sample(self, x, y, z):
        """Passo 1: amostra de menor m = dx² + dy² + (2·dz)² (empate: menor índice)."""
        px, py, pz = self._px, self._py, self._pz
        nx, ny = self._nx, self._ny
        cx = int(math.floor((x - self._gx0) / CELL))
        cy = int(math.floor((y - self._gy0) / CELL))
        best = float("inf")
        bk = -1
        zz = 0.0 if z is None else z
        wz = 0.0 if z is None else 4.0
        if 0 <= cx < nx and 0 <= cy < ny:
            # anéis 0 e 1 juntos (caso comum: carro na pista); _near está em ordem de índice
            items = self._near.get(cy * nx + cx, ())
            if z is None:
                for k in items:
                    dx = px[k] - x
                    dy = py[k] - y
                    m = dx * dx + dy * dy
                    if m < best:
                        best = m
                        bk = k
            else:
                for k in items:
                    dx = px[k] - x
                    dy = py[k] - y
                    dz = pz[k] - z
                    m = dx * dx + dy * dy + 4.0 * dz * dz
                    if m < best:
                        best = m
                        bk = k
            if bk >= 0 and best <= CELL * CELL:
                return bk
            r = 2
        else:
            r = max(0, -cx, cx - (nx - 1), -cy, cy - (ny - 1))
        cells = self._cells
        while True:
            # anel r recortado pela grade
            ring = []
            x0 = max(cx - r, 0)
            x1 = min(cx + r, nx - 1)
            if x0 <= x1:
                if 0 <= cy - r < ny:
                    ring.extend(range((cy - r) * nx + x0, (cy - r) * nx + x1 + 1))
                if r > 0 and 0 <= cy + r < ny:
                    ring.extend(range((cy + r) * nx + x0, (cy + r) * nx + x1 + 1))
            y0 = max(cy - r + 1, 0)
            y1 = min(cy + r - 1, ny - 1)
            if r > 0 and y0 <= y1:
                if 0 <= cx - r < nx:
                    ring.extend(gy * nx + cx - r for gy in range(y0, y1 + 1))
                if 0 <= cx + r < nx:
                    ring.extend(gy * nx + cx + r for gy in range(y0, y1 + 1))
            for c in ring:
                items = cells.get(c)
                if not items:
                    continue
                for k in items:
                    dx = px[k] - x
                    dy = py[k] - y
                    dz = pz[k] - zz
                    m = dx * dx + dy * dy + wz * dz * dz
                    if m <= best and (m < best or k < bk):
                        best = m
                        bk = k
            bound = r * CELL
            if bk >= 0 and best <= bound * bound:
                break
            if cx - r <= 0 and cx + r >= nx - 1 and cy - r <= 0 and cy + r >= ny - 1:
                break
            r += 1
        return bk

    def _solve(self, i, x, y, z):
        """Passos 3 e 4 da semântica no segmento i: (nota, t, u, e2, dz); nota = (0|1, valor)."""
        (x0, y0, Dx, Dy, L0x, L0y, dLx, dLy, A, cDL0, dd_ok, dd,
         z0, dz0, b0, db) = self._segs[i]
        qx = x - x0
        qy = y - y0
        t_o = (qx * Dx + qy * Dy) / dd if dd_ok else 0.0
        B = (qx * dLy - qy * dLx) - cDL0
        C = qx * L0y - qy * L0x
        t = None
        if -1e-12 < A < 1e-12:
            if not -1e-12 < B < 1e-12:
                r1 = -C / B
                if -_ROOT_EPS <= r1 <= 1.0 + _ROOT_EPS:
                    t = r1
        else:
            disc = B * B - 4.0 * A * C
            if disc >= 0.0:
                sq = math.sqrt(disc)
                Q = -0.5 * (B + sq) if B >= 0.0 else -0.5 * (B - sq)
                r1 = Q / A
                if -_ROOT_EPS <= r1 <= 1.0 + _ROOT_EPS:
                    t = r1
                if Q != 0.0:
                    r2 = C / Q
                    if -_ROOT_EPS <= r2 <= 1.0 + _ROOT_EPS and (t is None or abs(r2 - t_o) < abs(t - t_o)):
                        t = r2
        if t is None:
            t = t_o
        if t < 0.0:
            t = 0.0
        elif t > 1.0:
            t = 1.0
        Lx = L0x + dLx * t
        Ly = L0y + dLy * t
        ll = math.sqrt(Lx * Lx + Ly * Ly)
        if ll > 1e-12:
            Lx /= ll
            Ly /= ll
        ox = qx - Dx * t
        oy = qy - Dy * t
        u = ox * Lx + oy * Ly
        ex = ox - u * Lx
        ey = oy - u * Ly
        e2 = ex * ex + ey * ey
        if z is None:
            dz = 0.0
        else:
            dz = z - (z0 + dz0 * t - u * math.tan(b0 + db * t))
        if e2 < 1e-12:
            return (0, u * u + 4.0 * dz * dz), t, u, e2, dz
        return (1, e2), t, u, e2, dz

    def _project(self, pos):
        x = float(pos[0])
        y = float(pos[1])
        z = float(pos[2]) if len(pos) > 2 else None
        n = self.count
        if n == 1:
            return 0.0, 0, 0.0, 0.0, 0.0, 0.0
        k = self._nearest_sample(x, y, z)
        if self.cyclic:
            if n >= 4:
                segs = ((k - 2) % n, (k - 1) % n, k, (k + 1) % n)
            else:
                segs = []
                for i in (k - 2, k - 1, k, k + 1):
                    i %= n
                    if i not in segs:
                        segs.append(i)
        else:
            segs = [i for i in (k - 2, k - 1, k, k + 1) if 0 <= i <= n - 2]
        best = None
        solve = self._solve
        for i in segs:
            r = solve(i, x, y, z)
            if best is None or r[0] < best[0]:
                best = r
                bi = i
        _note, t, u, e2, dz = best
        _j, ds = self._segment_end(bi)
        s = self._s[bi] + t * ds
        if self.cyclic and s >= self.length:
            s -= self.length
        return s, bi, t, u, e2, dz

    def project(self, pos):
        """pos (x, y, z) -> (s, side, dist): metros percorridos, +1 esquerda / -1 direita e
        distância lateral até o centro (>= 0)."""
        s, _i, _t, u, _e2, _dz = self._project(pos)
        return s, (1 if u >= 0.0 else -1), abs(u)

    def isOnRoad(self, pos):
        """True se pos está sobre o asfalto (dentro de wl/wr) e a até 3 m da superfície."""
        s, _i, _t, u, e2, dz = self._project(pos)
        if not self.cyclic and e2 > 0.25:
            return False
        wl, wr = self.widthAt(s)
        w = wl if u >= 0.0 else wr
        if abs(u) > w:
            return False
        return len(pos) <= 2 or abs(dz) <= HEIGHT_TOL

    # ----------------------------------------------------------- interpolação

    def _locate(self, s):
        ss = self._s
        n = self.count
        s = float(s)
        if self.cyclic and self.length > 0.0:
            s %= self.length
        else:
            if s < ss[0]:
                s = ss[0]
            elif s > ss[-1]:
                s = ss[-1]
        i = bisect.bisect_right(ss, s) - 1
        if i < 0:
            i = 0
        elif i > n - 1:
            i = n - 1
        if i == n - 1 and not self.cyclic:
            return i, i, 0.0
        j, ds = self._segment_end(i)
        t = (s - ss[i]) / ds if ds > 0.0 else 0.0
        if t < 0.0:
            t = 0.0
        elif t > 1.0:
            t = 1.0
        return i, j, t

    def _lateral(self, i, j, t):
        lx = self._lx[i] + (self._lx[j] - self._lx[i]) * t
        ly = self._ly[i] + (self._ly[j] - self._ly[i]) * t
        ll = math.sqrt(lx * lx + ly * ly)
        if ll > 1e-12:
            return lx / ll, ly / ll
        return lx, ly

    def pointAt(self, s):
        """Centro da pista em s."""
        i, j, t = self._locate(s)
        px, py, pz = self._px, self._py, self._pz
        return _Vec((px[i] + (px[j] - px[i]) * t,
                     py[i] + (py[j] - py[i]) * t,
                     pz[i] + (pz[j] - pz[i]) * t))

    def tangentAt(self, s):
        """Tangente unitária 3D em s (sentido de s crescente)."""
        i, j, t = self._locate(s)
        tx, ty, tz = self._tx, self._ty, self._tz
        vx = tx[i] + (tx[j] - tx[i]) * t
        vy = ty[i] + (ty[j] - ty[i]) * t
        vz = tz[i] + (tz[j] - tz[i]) * t
        ll = math.sqrt(vx * vx + vy * vy + vz * vz)
        if ll > 1e-12:
            vx /= ll
            vy /= ll
            vz /= ll
        return _Vec((vx, vy, vz))

    def bankAt(self, s):
        """Inclinação lateral em radianos (+ = cai para a esquerda)."""
        i, j, t = self._locate(s)
        b = self._bank
        return b[i] + (b[j] - b[i]) * t

    def widthAt(self, s):
        """(esquerda, direita): meia largura do asfalto em s."""
        i, j, t = self._locate(s)
        wl, wr = self._wl, self._wr
        return (wl[i] + (wl[j] - wl[i]) * t, wr[i] + (wr[j] - wr[i]) * t)

    def racingLine(self, s):
        """Ponto da linha ideal em s (sobre a superfície inclinada)."""
        i, j, t = self._locate(s)
        px, py, pz, race, bank = self._px, self._py, self._pz, self._race, self._bank
        off = race[i] + (race[j] - race[i]) * t
        lx, ly = self._lateral(i, j, t)
        b = bank[i] + (bank[j] - bank[i]) * t
        return _Vec((px[i] + (px[j] - px[i]) * t + off * lx,
                     py[i] + (py[j] - py[i]) * t + off * ly,
                     pz[i] + (pz[j] - pz[i]) * t - off * math.tan(b)))

    def lateralAt(self, s):
        """Lateral horizontal unitária (para a esquerda) em s: (x, y, 0)."""
        i, j, t = self._locate(s)
        lx, ly = self._lateral(i, j, t)
        return _Vec((lx, ly, 0.0))

    def edgeAt(self, s):
        """(esquerda, direita): borda externa da faixa BORDER (el, er) interpolada em s."""
        i, j, t = self._locate(s)
        el, er = self._el, self._er
        return (el[i] + (el[j] - el[i]) * t, er[i] + (er[j] - er[i]) * t)

    def surfaceAt(self, s):
        """Nome do piso na amostra que começa o trecho de s ("" se a pista não tem pisos)."""
        i, _j, _t = self._locate(s)
        idx = self._surface[i]
        if 0 <= idx < len(self.surfaces):
            return self.surfaces[idx]
        return ""

    def __repr__(self):
        return "<Track %r length=%.1f cyclic=%s count=%d>" % (self.name, self.length, self.cyclic, self.count)


# --------------------------------------------------------------------------- leitura no jogo

_cache = {}


def _read_text(name):
    """Texto JSON da pista: Text importável (jogo) ou bpy.data.texts (editor)."""
    try:
        import bpy
        texts = bpy.data.texts
    except Exception:  # no jogo não há bpy (ou ele não tem data)
        texts = None
    if texts is not None:
        txt = texts.get(text_name(name))
        if txt is not None:
            return txt.as_string()
    import builtins
    try:
        mod = builtins.__import__(module_name(name))
    except ImportError:
        return None
    return getattr(mod, "DATA", None)


def get(name):
    """Track da pista `name` (nome do traçado), cozida pelo Track Tool. None se não existe."""
    if name.startswith(TEXT_PREFIX) and name.endswith(".json"):
        name = name[len(TEXT_PREFIX):-len(".json")]
    text = _read_text(name)
    if text is None:
        return None
    cached = _cache.get(name)
    if cached is not None and (cached[0] is text or cached[0] == text):
        return cached[1]
    track = Track.from_json(text)
    _cache[name] = (text, track)
    return track


def fromJson(text, name=""):
    """Track a partir de um texto JSON v1 (igual a Range.track.fromJson)."""
    track = Track.from_json(text)
    if name and not track.name:
        track.name = name
    return track


def reload():
    """Esquece as pistas em cache; o próximo get() lê o Text de novo."""
    _cache.clear()


def clear_cache():
    _cache.clear()
