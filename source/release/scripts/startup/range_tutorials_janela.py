"""Janela de Tutoriais: Help > Tutorials > Tutorials Window.

Uma janela grande por cima do editor (desenhada pela engine depois das áreas, como o cartão dos
tutoriais), dividida em: topo (título e progresso), categorias à esquerda, cartões no meio e
detalhes do tutorial escolhido à direita.  O operador modal segura os eventos enquanto ela está
aberta; Esc ou o X fecham.  A lista, o progresso e o idioma vêm de range_tutorials.
"""
import math
import os
import re

import bgl
import blf
import bpy
from bpy.types import Operator

import range_tutorials as rt

# Cores do tema atual (o escuro do protótipo); _aplicar_tema troca estes nomes pelos de TEMAS.
FUNDO = (0.086, 0.098, 0.122)
PAINEL = (0.114, 0.129, 0.161)
LATERAL = (0.098, 0.110, 0.137)
BORDA = (0.165, 0.184, 0.220)
TEXTO = (0.902, 0.910, 0.925)
TEXTO_2 = (0.639, 0.663, 0.706)
TEXTO_3 = (0.541, 0.569, 0.612)
DOURADO = (0.910, 0.710, 0.290)
VERDE = (0.435, 0.812, 0.592)
ESCURO = (0.055, 0.063, 0.078)
MINIATURAS = ((0.169, 0.227, 0.333), (0.227, 0.169, 0.290), (0.141, 0.263, 0.227),
              (0.290, 0.208, 0.141), (0.169, 0.267, 0.314), (0.263, 0.157, 0.227))

TEXTOS = {
    "titulo": {"pt": "Tutoriais", "en": "Tutorials", "es": "Tutoriales"},
    "sub": {"pt": "Aprenda a Anastacio Engine passo a passo, dentro do próprio editor.",
            "en": "Learn the Anastacio Engine step by step, right inside the editor.",
            "es": "Aprende Anastacio Engine paso a paso, dentro del propio editor."},
    "progresso": {"pt": "Seu progresso", "en": "Your progress", "es": "Tu progreso"},
    "de": {"pt": "de", "en": "of", "es": "de"},
    "categorias": {"pt": "CATEGORIAS", "en": "CATEGORIES", "es": "CATEGORÍAS"},
    "todos": {"pt": "Todos", "en": "All", "es": "Todos"},
    "passos": {"pt": "passos", "en": "steps", "es": "pasos"},
    "novo": {"pt": "Novo", "en": "New", "es": "Nuevo"},
    "concluido": {"pt": "Concluído", "en": "Completed", "es": "Completado"},
    "passo": {"pt": "Passo", "en": "Step", "es": "Paso"},
    "comecar": {"pt": "Começar tutorial", "en": "Start tutorial", "es": "Empezar tutorial"},
    "continuar": {"pt": "Continuar do passo %d", "en": "Continue from step %d", "es": "Continuar desde el paso %d"},
    "refazer": {"pt": "Refazer tutorial", "en": "Do it again", "es": "Rehacer tutorial"},
    "inicio": {"pt": "Recomeçar do início", "en": "Restart from the beginning", "es": "Empezar desde el inicio"},
    "dica": {"pt": "Dica: o tutorial avança sozinho quando você faz o que o passo pede.  Esc fecha esta janela.",
             "en": "Tip: the tutorial moves on by itself when you do what the step asks.  Esc closes this window.",
             "es": "Consejo: el tutorial avanza solo cuando haces lo que pide el paso.  Esc cierra esta ventana."},
    "vazio": {"pt": "Nenhum tutorial instalado.", "en": "No tutorials installed.", "es": "Ningún tutorial instalado."},
}

# Temas da janela: fundos, textos e o destaque.  O texto escuro sobre o destaque (ESCURO) não muda.
TEMAS = {
    "escuro": {"FUNDO": FUNDO, "PAINEL": PAINEL, "LATERAL": LATERAL, "BORDA": BORDA, "TEXTO": TEXTO,
               "TEXTO_2": TEXTO_2, "TEXTO_3": TEXTO_3, "DOURADO": DOURADO, "VERDE": VERDE},
    "claro": {"FUNDO": (0.957, 0.953, 0.937), "PAINEL": (1.0, 1.0, 1.0), "LATERAL": (0.925, 0.918, 0.898),
              "BORDA": (0.835, 0.824, 0.796), "TEXTO": (0.110, 0.110, 0.122), "TEXTO_2": (0.290, 0.290, 0.310),
              "TEXTO_3": (0.400, 0.400, 0.420), "DOURADO": (0.851, 0.600, 0.110), "VERDE": (0.435, 0.812, 0.592)},
    "azul": {"FUNDO": (0.059, 0.090, 0.165), "PAINEL": (0.082, 0.122, 0.212), "LATERAL": (0.067, 0.102, 0.184),
             "BORDA": (0.141, 0.200, 0.318), "TEXTO": (0.906, 0.933, 0.976), "TEXTO_2": (0.643, 0.706, 0.808),
             "TEXTO_3": (0.533, 0.596, 0.702), "DOURADO": (0.369, 0.682, 0.961), "VERDE": (0.435, 0.812, 0.592)},
}
NOMES_TEMA = {"escuro": {"pt": "Escuro", "en": "Dark", "es": "Oscuro"},
              "claro": {"pt": "Claro", "en": "Light", "es": "Claro"},
              "azul": {"pt": "Azul", "en": "Blue", "es": "Azul"}}
_tema = {}


def _arquivo_tema():
    return os.path.join(bpy.utils.user_resource('CONFIG', create=True), "range_tutorials_tema.txt")


def _aplicar_tema(nome=None, gravar=False):
    """Troca as cores da janela; sem nome, o tema guardado (ou o claro)."""
    if nome is None:
        try:
            with open(_arquivo_tema(), encoding="utf-8") as f:
                nome = f.read().strip()
        except OSError:
            nome = ""
    nome = nome if nome in TEMAS else "claro"
    globals().update(TEMAS[nome])
    _tema["nome"] = nome
    if gravar:
        try:
            with open(_arquivo_tema(), "w", encoding="utf-8") as f:
                f.write(nome)
        except OSError:
            pass  # sem pasta de configuração: vale só nesta sessão


janela = {}  # vazio = fechada


def _t(chave):
    return rt._txt(TEXTOS[chave])


# ---------------------------------------------------------------- dados

def _dados():
    """(categorias [(nome, [itens])], progresso); item = (pasta, título, subcategoria, passos, categoria inteira)."""
    grupos = {}
    for nome, titulo, categoria, total in rt.tutoriais():
        partes = categoria.split("/") if categoria else ["-"]
        grupos.setdefault(partes[0], []).append((nome, titulo, " / ".join(partes[1:]), total, " / ".join(partes)))
    for itens in grupos.values():
        itens.sort(key=_ordem)
    ordem = sorted(grupos, key=lambda c: (c != "Basics", c.lower()))
    # Em "Todos", o cartão mostra a categoria inteira no lugar da subcategoria.
    todos = [(n, t, completa, total, completa) for c in ordem for n, t, _, total, completa in grupos[c]]
    todos.sort(key=_ordem)
    return [(_t("todos"), todos)] + [(c, grupos[c]) for c in ordem], rt._progresso()


def _ordem(item):
    """Pelo número do título ("2. Mover..." antes de "15. Rec Play..."), depois pelo nome."""
    numero = re.match(r"\s*(\d+)", item[1])
    return (int(numero.group(1)) if numero else 10 ** 6, item[1].lower())


def _estado_item(progresso, nome, total):
    """("feito"|"andando"|"novo", passo atual 1..total)."""
    p = progresso.get(nome, {})
    if p.get("feito"):
        return "feito", total
    if p.get("passo", 0) > 0:
        return "andando", p["passo"] + 1
    return "novo", 1


def _resumo(nome):
    try:
        return rt._txt(rt._ler_roteiro(nome).get("resumo"))
    except (OSError, ValueError):
        return ""


# ---------------------------------------------------------------- desenho básico

def _ret(x0, y0, x1, y1, cor, alfa=1.0, raio=0.0):
    bgl.glColor4f(cor[0], cor[1], cor[2], alfa)
    raio = min(raio, (x1 - x0) / 2, (y1 - y0) / 2)
    if raio <= 0.5:
        bgl.glRectf(x0, y0, x1, y1)
        return
    bgl.glBegin(bgl.GL_POLYGON)
    for cx, cy, a0 in ((x1 - raio, y1 - raio, 0), (x0 + raio, y1 - raio, 90),
                       (x0 + raio, y0 + raio, 180), (x1 - raio, y0 + raio, 270)):
        for i in range(7):
            a = math.radians(a0 + 15 * i)
            bgl.glVertex2f(cx + raio * math.cos(a), cy + raio * math.sin(a))
    bgl.glEnd()


def _moldura(x0, y0, x1, y1, cor, raio, espessura):
    _ret(x0, y0, x1, y1, cor, raio=raio)
    _ret(x0 + espessura, y0 + espessura, x1 - espessura, y1 - espessura, PAINEL, raio=max(0.0, raio - espessura))


def _txt(x, y, texto, cor=TEXTO, tamanho=14):
    e = rt._escala()
    blf.size(0, int(tamanho * e), 72)
    bgl.glColor4f(cor[0], cor[1], cor[2], 1.0)
    blf.position(0, x, y, 0)
    blf.draw(0, texto)


def _largura(texto, tamanho):
    blf.size(0, int(tamanho * rt._escala()), 72)
    return blf.dimensions(0, texto)[0]


def _cortar(texto, largura, tamanho):
    if _largura(texto, tamanho) <= largura:
        return texto
    while texto and _largura(texto + "...", tamanho) > largura:
        texto = texto[:-1]
    return texto.rstrip() + "..."


def _quebrar(texto, largura, tamanho):
    blf.size(0, int(tamanho * rt._escala()), 72)
    return rt._quebrar(texto, largura) if texto else []


def _recortar(x0, y0, x1, y1):
    bgl.glEnable(bgl.GL_SCISSOR_TEST)
    bgl.glScissor(int(x0), int(y0), max(0, int(x1 - x0)), max(0, int(y1 - y0)))


def _dentro(r, x, y):
    return r[0] <= x <= r[2] and r[1] <= y <= r[3]


def _icone_cubo(cx, cy, r, cor):
    bgl.glColor4f(cor[0], cor[1], cor[2], 1.0)
    bgl.glLineWidth(max(1.0, 2.0 * rt._escala()))
    pontos = [(cx + r * math.cos(math.radians(30 + 60 * i)), cy + r * math.sin(math.radians(30 + 60 * i)))
              for i in range(6)]
    bgl.glBegin(bgl.GL_LINE_LOOP)
    for p in pontos:
        bgl.glVertex2f(*p)
    bgl.glEnd()
    bgl.glBegin(bgl.GL_LINES)
    for i in (1, 3, 5):  # topo, esquerda-baixo, direita-baixo até o centro
        bgl.glVertex2f(cx, cy)
        bgl.glVertex2f(*pontos[i])
    bgl.glEnd()
    bgl.glLineWidth(1.0)


_sem_imagem = set()  # caminhos que não carregaram (não tenta de novo a cada desenho)


def _imagem(x0, y0, x1, y1, caminho=None, cobrir=False):
    """Desenha um PNG (o cubo dourado do logo, por padrão); False sem o arquivo.
    cobrir: preenche o retângulo cortando as sobras, como object-fit: cover."""
    caminho = caminho or os.path.join(rt.PASTA, "cubo.png")
    nome = "range_tutoriais_%08x" % (hash(caminho) & 0xffffffff)
    img = bpy.data.images.get(nome)
    if img is None:
        if caminho in _sem_imagem or not os.path.isfile(caminho):
            return False
        try:
            img = bpy.data.images.load(caminho)
        except RuntimeError:
            _sem_imagem.add(caminho)
            return False
        img.name = nome
    if img.gl_load(filter=bgl.GL_LINEAR, mag=bgl.GL_LINEAR):
        _sem_imagem.add(caminho)
        return False
    u0, v0, u1, v1 = 0.0, 0.0, 1.0, 1.0
    w, h = img.size
    if cobrir and w and h and x1 > x0 and y1 > y0:
        caixa, foto = (x1 - x0) / (y1 - y0), w / h
        if foto > caixa:
            u0 = (1 - caixa / foto) / 2
            u1 = 1 - u0
        else:
            v0 = (1 - foto / caixa) / 2
            v1 = 1 - v0
    bgl.glEnable(bgl.GL_TEXTURE_2D)
    bgl.glBindTexture(bgl.GL_TEXTURE_2D, img.bindcode[0])
    bgl.glColor4f(1.0, 1.0, 1.0, 1.0)
    bgl.glBegin(bgl.GL_QUADS)
    for (u, v), (x, y) in zip(((u0, v0), (u1, v0), (u1, v1), (u0, v1)), ((x0, y0), (x1, y0), (x1, y1), (x0, y1))):
        bgl.glTexCoord2f(u, v)
        bgl.glVertex2f(x, y)
    bgl.glEnd()
    bgl.glBindTexture(bgl.GL_TEXTURE_2D, 0)
    bgl.glDisable(bgl.GL_TEXTURE_2D)
    return True


def _icone_play(cx, cy, r, cor):
    bgl.glColor4f(cor[0], cor[1], cor[2], 1.0)
    bgl.glBegin(bgl.GL_TRIANGLES)
    bgl.glVertex2f(cx - r * 0.45, cy - r * 0.6)
    bgl.glVertex2f(cx - r * 0.45, cy + r * 0.6)
    bgl.glVertex2f(cx + r * 0.6, cy)
    bgl.glEnd()


def _icone_x(cx, cy, r, cor):
    bgl.glColor4f(cor[0], cor[1], cor[2], 1.0)
    bgl.glLineWidth(max(1.0, 2.0 * rt._escala()))
    bgl.glBegin(bgl.GL_LINES)
    for a, b in (((-r, -r), (r, r)), ((-r, r), (r, -r))):
        bgl.glVertex2f(cx + a[0], cy + a[1])
        bgl.glVertex2f(cx + b[0], cy + b[1])
    bgl.glEnd()
    bgl.glLineWidth(1.0)


# ---------------------------------------------------------------- a janela

def _desenhar():
    if not janela or bpy.context.window.as_pointer() != janela["janela"]:
        return
    caixa = bgl.Buffer(bgl.GL_INT, 4)
    bgl.glGetIntegerv(bgl.GL_SCISSOR_BOX, caixa)
    ligado = bgl.glIsEnabled(bgl.GL_SCISSOR_TEST)
    try:
        bgl.glEnable(bgl.GL_BLEND)
        _desenhar_tudo()
    finally:
        bgl.glScissor(*list(caixa))
        (bgl.glEnable if ligado else bgl.glDisable)(bgl.GL_SCISSOR_TEST)
        bgl.glDisable(bgl.GL_BLEND)
        bgl.glLineWidth(1.0)


def _desenhar_tudo():
    win = bpy.context.window
    e = rt._escala()
    cats, progresso = _dados()
    janela["cat"] = min(janela["cat"], len(cats) - 1)
    alvos = []  # (retângulo, ação, valor) para os cliques
    mx, my = janela.get("mouse", (-1, -1))

    def sobre(r):
        return _dentro(r, mx, my)

    # A moldura da janela (o editor por baixo continua visível, sem escurecer).
    larg, alt = min(1200 * e, win.width - 40 * e), min(720 * e, win.height - 40 * e)
    x0, y0 = int((win.width - larg) / 2), int((win.height - alt) / 2)
    x1, y1 = x0 + larg, y0 + alt
    janela["caixa"] = (x0, y0, x1, y1)
    _ret(x0 - 1, y0 - 1, x1 + 1, y1 + 1, BORDA, raio=11 * e)
    _ret(x0, y0, x1, y1, FUNDO, raio=10 * e)

    topo, rodape, nav, lado = 112 * e, 40 * e, 220 * e, 300 * e
    m0, m1 = y0 + rodape, y1 - topo  # faixa do meio

    # ---- topo
    _ret(x0, m1, x1, y1, PAINEL, raio=10 * e)
    _ret(x0, m1, x1, m1 + 12 * e, PAINEL)
    _ret(x0, m1, x1, m1 + 1, BORDA)
    cy = m1 + topo / 2
    if not _imagem(x0 + 28 * e, cy - 34 * e, x0 + 96 * e, cy + 34 * e):
        _icone_cubo(x0 + 60 * e, cy, 22 * e, DOURADO)
    _txt(x0 + 112 * e, cy + 4 * e, _t("titulo"), TEXTO, 28)
    _txt(x0 + 112 * e, cy - 20 * e, _t("sub"), TEXTO_2, 13)
    total = len(cats[0][1])
    feitos = sum(1 for n, _, _, t, _ in cats[0][1] if _estado_item(progresso, n, t)[0] == "feito")
    bx1 = x1 - 96 * e
    bx0 = bx1 - 240 * e
    _txt(bx0, cy + 8 * e, _t("progresso"), TEXTO_2, 12)
    contagem = "%d %s %d" % (feitos, _t("de"), total)
    _txt(bx1 - _largura(contagem, 12), cy + 8 * e, contagem, TEXTO, 12)
    _ret(bx0, cy - 10 * e, bx1, cy - 2 * e, BORDA, raio=4 * e)
    if total and feitos:
        _ret(bx0, cy - 10 * e, bx0 + (bx1 - bx0) * feitos / total, cy - 2 * e, DOURADO, raio=4 * e)
    fechar = (x1 - 76 * e, cy - 22 * e, x1 - 32 * e, cy + 22 * e)
    if sobre(fechar):
        _ret(*fechar, cor=BORDA, raio=8 * e)
    _icone_x((fechar[0] + fechar[2]) / 2, cy, 7 * e, TEXTO if sobre(fechar) else TEXTO_2)
    alvos.append((fechar, "fechar", None))

    # ---- rodapé: dica e idioma
    _ret(x0, y0, x1, y0 + rodape, LATERAL, raio=10 * e)
    _ret(x0, y0 + rodape - 12 * e, x1, y0 + rodape, LATERAL)
    _ret(x0, y0 + rodape - 1, x1, y0 + rodape, BORDA)
    _txt(x0 + 32 * e, y0 + 14 * e, _t("dica"), TEXTO_3, 12)
    x = x1 - 32 * e
    atual = rt._idioma()
    for codigo in reversed(rt.IDIOMAS):
        r = (x - 40 * e, y0 + 8 * e, x, y0 + rodape - 8 * e)
        escolhido = codigo == atual
        _ret(*r, cor=DOURADO if escolhido else (BORDA if sobre(r) else LATERAL), raio=5 * e)
        _txt(r[0] + 11 * e, r[1] + 7 * e, codigo.upper(), ESCURO if escolhido else TEXTO_2, 11)
        alvos.append((r, "idioma", codigo))
        x -= 46 * e
    # Temas: uma bolinha com a cor de cada um (o escolhido com anel do destaque) e o nome do atual.
    x -= 16 * e
    cy_t = y0 + rodape / 2
    for nome in reversed(list(TEMAS)):
        cores = TEMAS[nome]
        r = (x - 24 * e, cy_t - 12 * e, x, cy_t + 12 * e)
        if nome == _tema.get("nome"):
            _ret(*r, cor=DOURADO, raio=12 * e)
        elif sobre(r):
            _ret(*r, cor=TEXTO_3, raio=12 * e)
        _ret(r[0] + 3 * e, r[1] + 3 * e, r[2] - 3 * e, r[3] - 3 * e, cores["PAINEL"], raio=9 * e)
        _ret(r[0] + 8 * e, r[1] + 8 * e, r[2] - 8 * e, r[3] - 8 * e, cores["DOURADO"], raio=4 * e)
        alvos.append((r, "tema", nome))
        x -= 30 * e
    rotulo = rt._txt(NOMES_TEMA[_tema.get("nome", "claro")])
    _txt(x - _largura(rotulo, 12) + 2 * e, y0 + 14 * e, rotulo, TEXTO_3, 12)

    # ---- categorias (rolam se não couberem)
    _ret(x0, m0, x0 + nav, m1, LATERAL)
    _ret(x0 + nav - 1, m0, x0 + nav, m1, BORDA)
    _txt(x0 + 24 * e, m1 - 34 * e, _t("categorias"), TEXTO_3, 11)
    lista_y1 = m1 - 48 * e
    item_alt = 40 * e
    conteudo = len(cats) * (item_alt + 4 * e)
    janela["rolagem_max"]["nav"] = max(0.0, conteudo - (lista_y1 - m0 - 12 * e))
    janela["rolagem"]["nav"] = min(janela["rolagem"]["nav"], janela["rolagem_max"]["nav"])
    janela["regioes"]["nav"] = (x0, m0, x0 + nav, lista_y1)
    _recortar(x0, m0, x0 + nav, lista_y1)
    y = lista_y1 + janela["rolagem"]["nav"]
    for i, (nome, itens) in enumerate(cats):
        r = (x0 + 12 * e, y - item_alt, x0 + nav - 12 * e, y)
        y -= item_alt + 4 * e
        if r[3] < m0 or r[1] > lista_y1:
            continue
        ativo = i == janela["cat"]
        if ativo or sobre(r):
            _ret(*r, cor=BORDA, alfa=1.0 if ativo else 0.6, raio=8 * e)
        if ativo:
            _ret(r[0], r[1] + 8 * e, r[0] + 3 * e, r[3] - 8 * e, DOURADO)
        _txt(r[0] + 14 * e, r[1] + 14 * e, _cortar(nome, nav - 90 * e, 14), TEXTO if ativo else TEXTO_2, 14)
        n = str(len(itens))
        _txt(r[2] - 12 * e - _largura(n, 12), r[1] + 14 * e, n, TEXTO_3, 12)
        if sobre(janela["regioes"]["nav"]):
            alvos.append((r, "categoria", i))
    bgl.glDisable(bgl.GL_SCISSOR_TEST)

    # ---- detalhes à direita
    nome_cat, itens = cats[janela["cat"]]
    _ret(x1 - lado, m0, x1, m1, PAINEL)
    _ret(x1 - lado, m0, x1 - lado + 1, m1, BORDA)
    escolhido = next((it for it in itens if it[0] == janela.get("tut")), itens[0] if itens else None)
    if escolhido is not None:
        janela["tut"] = escolhido[0]
        _desenhar_detalhes(escolhido, nome_cat, progresso, x1 - lado + 24 * e, m0 + 24 * e, x1 - 24 * e,
                           m1 - 24 * e, alvos, sobre)

    # ---- cartões no meio (3 colunas, rolam)
    gx0, gx1 = x0 + nav + 24 * e, x1 - lado - 24 * e
    gy1 = m1 - 24 * e
    _txt(gx0, gy1 - 20 * e, nome_cat, TEXTO, 20)
    gy1 -= 40 * e
    janela["regioes"]["grade"] = (gx0 - 4 * e, m0, gx1 + 4 * e, gy1)
    if not itens:
        _txt(gx0, gy1 - 30 * e, _t("vazio"), TEXTO_2, 14)
    colunas, vao = 3, 16 * e
    larg_c = (gx1 - gx0 - vao * (colunas - 1)) / colunas
    alt_c = 168 * e
    linhas = (len(itens) + colunas - 1) // colunas
    janela["rolagem_max"]["grade"] = max(0.0, linhas * (alt_c + vao) - vao - (gy1 - m0 - 16 * e))
    janela["rolagem"]["grade"] = min(janela["rolagem"]["grade"], janela["rolagem_max"]["grade"])
    _recortar(gx0 - 4 * e, m0, gx1 + 4 * e, gy1)
    for i, item in enumerate(itens):
        cx0 = gx0 + (i % colunas) * (larg_c + vao)
        cy1 = gy1 - 4 * e - (i // colunas) * (alt_c + vao) + janela["rolagem"]["grade"]
        r = (cx0, cy1 - alt_c, cx0 + larg_c, cy1)
        if r[3] < m0 or r[1] > gy1:
            continue
        _desenhar_cartao(item, i, r, progresso, item[0] == janela["tut"], sobre(r))
        if sobre(janela["regioes"]["grade"]):
            alvos.append((r, "tutorial", item[0]))
    bgl.glDisable(bgl.GL_SCISSOR_TEST)
    if janela["rolagem_max"]["grade"] > 0:  # barra de rolagem fina
        altura = gy1 - m0
        visivel = altura / (altura + janela["rolagem_max"]["grade"])
        h = max(30 * e, altura * visivel)
        topo_b = gy1 - (altura - h) * janela["rolagem"]["grade"] / janela["rolagem_max"]["grade"]
        _ret(gx1 + 10 * e, topo_b - h, gx1 + 14 * e, topo_b, BORDA, raio=2 * e)

    janela["alvos"] = alvos


def _desenhar_cartao(item, indice, r, progresso, escolhido, sobre):
    e = rt._escala()
    nome, titulo, sub, total, _ = item
    situacao, passo = _estado_item(progresso, nome, total)
    borda = DOURADO if escolhido else (TEXTO_3 if sobre else BORDA)
    _moldura(*r, cor=borda, raio=10 * e, espessura=2 * e)
    m = 10 * e
    t0, t1 = r[3] - m - 92 * e, r[3] - m
    if not _imagem(r[0] + m, t0, r[2] - m, t1, rt.miniatura(nome), cobrir=True):
        _ret(r[0] + m, t0, r[2] - m, t1, MINIATURAS[indice % len(MINIATURAS)], raio=6 * e)
        _icone_play((r[0] + r[2]) / 2, (t0 + t1) / 2, 14 * e, (1, 1, 1))
    if situacao == "feito":
        selo, cor = _t("concluido"), VERDE
    elif situacao == "andando":
        selo, cor = "%s %d/%d" % (_t("passo"), passo, total), DOURADO
    else:
        selo, cor = _t("novo"), DOURADO
    ls = _largura(selo, 11) + 16 * e
    _ret(r[2] - m - 8 * e - ls, t0 + 8 * e, r[2] - m - 8 * e, t0 + 28 * e, ESCURO, alfa=0.8, raio=10 * e)
    _txt(r[2] - m - ls, t0 + 14 * e, selo, cor, 11)
    _txt(r[0] + m, t0 - 22 * e, _cortar(titulo, r[2] - r[0] - 2 * m, 14), TEXTO, 14)
    meta = "%d %s" % (total, _t("passos")) + ("  ·  " + sub if sub else "")
    _txt(r[0] + m, t0 - 42 * e, _cortar(meta, r[2] - r[0] - 2 * m, 12), TEXTO_3, 12)


def _desenhar_detalhes(item, nome_cat, progresso, x0, y0, x1, y1, alvos, sobre):
    e = rt._escala()
    nome, titulo, _, total, categoria = item
    situacao, passo = _estado_item(progresso, nome, total)
    if not _imagem(x0, y1 - 150 * e, x1, y1, rt.miniatura(nome), cobrir=True):
        _ret(x0, y1 - 150 * e, x1, y1, MINIATURAS[0], raio=8 * e)
        _icone_play((x0 + x1) / 2, y1 - 75 * e, 24 * e, (1, 1, 1))
    y = y1 - 150 * e - 34 * e
    for linha in _quebrar(titulo, x1 - x0, 20)[:3]:
        _txt(x0, y, linha, TEXTO, 20)
        y -= 26 * e
    meta = "%d %s" % (total, _t("passos")) + ("  ·  " + categoria if categoria else "")
    _txt(x0, y, _cortar(meta, x1 - x0, 13), TEXTO_2, 13)
    y -= 30 * e
    for linha in _quebrar(_resumo(nome), x1 - x0, 14)[:8]:
        _txt(x0, y, linha, TEXTO, 14)
        y -= 21 * e

    # Botões embaixo: o principal sempre; "do início" só para quem parou no meio.
    if situacao == "andando":
        rotulo, passo_ini = rt._txt(TEXTOS["continuar"]) % passo, -1
    elif situacao == "feito":
        rotulo, passo_ini = _t("refazer"), 0
    else:
        rotulo, passo_ini = _t("comecar"), 0
    yb = y0
    if situacao == "andando":
        r2 = (x0, yb, x1, yb + 40 * e)
        _ret(*r2, cor=BORDA if sobre(r2) else LATERAL, raio=8 * e)
        _txt((x0 + x1 - _largura(_t("inicio"), 13)) / 2, yb + 14 * e, _t("inicio"), TEXTO_2, 13)
        alvos.append((r2, "comecar", (nome, 0)))
        yb += 48 * e
    r = (x0, yb, x1, yb + 48 * e)
    _ret(*r, cor=DOURADO, alfa=0.85 if sobre(r) else 1.0, raio=8 * e)
    _txt((x0 + x1 - _largura(rotulo, 15)) / 2, yb + 18 * e, rotulo, ESCURO, 15)
    alvos.append((r, "comecar", (nome, passo_ini)))


# ---------------------------------------------------------------- operador

def _fechar(context):
    if not janela:
        return
    bpy.types.WindowManager.draw_handler_remove(janela["handle"])
    janela.clear()
    rt._redesenhar()


class RANGE_OT_tutorials_window(Operator):
    """Open the Tutorials window: categories, progress and every tutorial in one place"""
    bl_idname = "wm.range_tutorials_window"
    bl_label = "Tutorials Window"

    def invoke(self, context, event):
        _fechar(context)
        if rt.estado:
            rt._parar()  # o cartão do tutorial por baixo da janela confundiria
        self.chave = object()
        _aplicar_tema()
        janela.update(chave=self.chave, janela=context.window.as_pointer(), cat=0, tut=None, alvos=[],
                      rolagem={"nav": 0.0, "grade": 0.0}, rolagem_max={"nav": 0.0, "grade": 0.0},
                      regioes={}, mouse=(event.mouse_x, event.mouse_y),
                      handle=bpy.types.WindowManager.draw_handler_add(_desenhar, ()))
        context.window_manager.modal_handler_add(self)
        rt._redesenhar()
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if janela.get("chave") is not self.chave:
            return {'CANCELLED'}
        if event.type == 'TIMER':
            return {'PASS_THROUGH'}
        janela["mouse"] = (event.mouse_x, event.mouse_y)
        if event.type == 'ESC' and event.value == 'PRESS':
            _fechar(context)
            return {'CANCELLED'}
        if event.type in ('WHEELUPMOUSE', 'WHEELDOWNMOUSE'):
            passo = 60 * rt._escala() * (-1 if event.type == 'WHEELUPMOUSE' else 1)
            for regiao in ("nav", "grade"):
                r = janela["regioes"].get(regiao)
                if r and _dentro(r, event.mouse_x, event.mouse_y):
                    novo = janela["rolagem"][regiao] + passo
                    janela["rolagem"][regiao] = max(0.0, min(novo, janela["rolagem_max"][regiao]))
        elif event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            for r, acao, valor in janela["alvos"]:
                if _dentro(r, event.mouse_x, event.mouse_y):
                    return self.clicar(context, acao, valor)
        rt._redesenhar()
        return {'RUNNING_MODAL'}  # janela modal: o editor por baixo não recebe nada

    def clicar(self, context, acao, valor):
        if acao == "fechar":
            _fechar(context)
            return {'CANCELLED'}
        if acao == "comecar":
            nome, passo = valor
            _fechar(context)
            bpy.ops.wm.range_tutorial_start('INVOKE_DEFAULT', name=nome, step=passo)
            return {'FINISHED'}
        if acao == "categoria":
            janela["cat"], janela["tut"] = valor, None
            janela["rolagem"]["grade"] = 0.0
        elif acao == "tutorial":
            janela["tut"] = valor
        elif acao == "tema":
            _aplicar_tema(valor, gravar=True)
        elif acao == "idioma":
            rt._escolher_idioma(valor)
        rt._redesenhar()
        return {'RUNNING_MODAL'}


def _no_menu(self, context):
    layout = self.layout
    layout.operator_context = 'INVOKE_DEFAULT'
    layout.operator(RANGE_OT_tutorials_window.bl_idname, text="Tutorials Window...", icon='HELP')


def register():
    bpy.utils.register_class(RANGE_OT_tutorials_window)
    bpy.types.INFO_MT_range_tutorials.prepend(_no_menu)


def unregister():
    if janela:
        bpy.types.WindowManager.draw_handler_remove(janela["handle"])
        janela.clear()
    bpy.types.INFO_MT_range_tutorials.remove(_no_menu)
    bpy.utils.unregister_class(RANGE_OT_tutorials_window)
