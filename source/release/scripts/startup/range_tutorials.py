"""Tutoriais dentro da engine: Help > Tutorials.

Cada tutorial é uma pasta em scripts/tutoriais/<nome>/ com um roteiro.json (o mesmo que gera o
vídeo) e, se houver, a cena inicial inicio.range.  Um cartão por cima da janela (qualquer editor,
qualquer layout) mostra o passo atual; quando o usuário faz o que o passo pede, a checagem fica
verdadeira e o tutorial avança sozinho.

roteiro.json:
  "titulo", "categoria" ("Node Editor/UI Tree" = submenus), "passos": [...]
  textos ("titulo", "texto", "dica") podem ser {"pt": "...", "en": "..."}: vale o idioma da interface.

"checagem" do passo:
  "logica_ligada"                                nome em CHECAGENS (casos que pedem código)
  {"area": "LOGIC_EDITOR"}                       existe uma área desse tipo
  {"modo": "EDIT_MESH"}                          context.mode
  {"objeto": "Cube"} / {"ativo": "Cube"}         objeto existe / é o ativo
  {"expr": "len(D.objects) > 3"}                 Python (C = context, D = bpy.data, bpy); roda como
                                                 um script: só instale tutoriais de quem você confia
  Várias chaves no mesmo dicionário: todas valem.  Sem checagem: o usuário clica em Próximo.

"alvo" do passo = onde clicar, com um quadro piscando:
  {"area": "NODE_EDITOR", "regiao": "HEADER", "botao": "New"}   botão pelo texto, "op:NODE_OT_x" (nome C),
                                                                 "prop:nome", "prop:nome=VALOR" ou "tip:..."
  {"area": "BAIXO", ...}                                         a área de baixo, seja qual for o editor
  {..., "menu": "Node Editor"}                                   item a marcar no menu que o botão abre
  {"no": "Jogar"}                                                nó (texto do Button da UI Tree, nome ou label)
Sem alvo, o contorno vai na área de "destaque" (tipo do editor, ou "BAIXO").
"dica" do passo: aparece no cartão quando o usuário fica parado no passo (DICA_SEGUNDOS).

Para criar um tutorial: Help > Tutorials > Record Tutorial, fazer os cliques e Stop Rec.  Cada
clique vira um passo com o alvo já preenchido; os textos se ajustam no painel Tutorial da 3D View
(clique direito no tutorial > Edit Tutorial).
"""
import json
import os
import re
import shutil
import time
import unicodedata
import zipfile
import zlib

import bgl
import blf
import bpy
from bpy.app.handlers import persistent
from bpy.props import BoolProperty, CollectionProperty, EnumProperty, IntProperty, StringProperty
from bpy.types import Menu, Operator, Panel, PropertyGroup

PASTA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tutoriais")
CENA = "inicio.range"
PAUSA_FEITO = 0.9  # segundos mostrando "feito" antes de avançar
DICA_SEGUNDOS = 20.0  # parado no passo por esse tempo: mostra a dica
LARANJA, VERDE, AMARELO = (1.0, 0.6, 0.2), (0.35, 0.85, 0.4), (1.0, 0.85, 0.35)

estado = {}  # vazio = nenhum tutorial rodando
_lista = None
_pendente = {}  # tutorial a começar depois de abrir a cena inicial


# ---------------------------------------------------------------- textos e idiomas

def _idioma():
    """"pt", "en"... do idioma da interface."""
    sistema = bpy.context.user_preferences.system
    lingua = sistema.language if getattr(sistema, "use_international_fonts", True) else "en_US"
    return "en" if lingua in ("DEFAULT", "") else lingua[:2]


def _txt(valor):
    """Texto de um campo que pode ser {"pt": ..., "en": ...}."""
    if isinstance(valor, dict):
        return valor.get(_idioma()) or valor.get("en") or next(iter(valor.values()), "")
    return valor or ""


def _com_txt(antigo, novo):
    """Grava `novo` no campo, só no idioma atual quando o campo já tem vários idiomas."""
    if isinstance(antigo, dict):
        d = dict(antigo)
        d[_idioma()] = novo
        return d
    return novo


def _nome_pasta(titulo):
    """Pasta nova pelo título (sem acento/espaço), sem pegar uma que já existe."""
    ascii_ = unicodedata.normalize("NFKD", titulo).encode("ascii", "ignore").decode()
    base = re.sub(r"[^a-z0-9]+", "_", ascii_.lower()).strip("_") or "tutorial"
    nome, n = base, 2
    while os.path.exists(os.path.join(PASTA, nome)):
        nome, n = "%s_%d" % (base, n), n + 1
    return nome


def _pasta_valida(nome):
    """Caminho da pasta do tutorial `nome`, ou None (nome com caminho, ou sem roteiro)."""
    if not nome or os.path.basename(nome) != nome or nome in (".", ".."):
        return None
    pasta = os.path.join(PASTA, nome)
    return pasta if os.path.isfile(os.path.join(pasta, "roteiro.json")) else None


def _ler_roteiro(nome):
    with open(os.path.join(PASTA, nome, "roteiro.json"), encoding="utf-8") as f:
        return json.load(f)


def _gravar_roteiro(nome, roteiro):
    with open(os.path.join(PASTA, nome, "roteiro.json"), "w", encoding="utf-8") as f:
        json.dump(roteiro, f, ensure_ascii=False, indent=2)
        f.write("\n")


# ---------------------------------------------------------------- progresso do usuário

def _arquivo_progresso():
    return os.path.join(bpy.utils.user_resource('CONFIG', create=True), "range_tutorials.json")


def _progresso():
    try:
        with open(_arquivo_progresso(), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _marcar_progresso(nome, passo=None, feito=None):
    dados = _progresso()
    item = dados.setdefault(nome, {"passo": 0, "feito": False})
    if passo is not None:
        item["passo"] = passo
    if feito is not None:
        item["feito"] = feito
    try:
        with open(_arquivo_progresso(), "w", encoding="utf-8") as f:
            json.dump(dados, f, indent=1)
    except OSError:
        pass  # sem pasta de configuração: só não lembra


# ---------------------------------------------------------------- checagens

def _arvores_ui(context):
    for area in context.screen.areas:
        if area.type == "NODE_EDITOR" and area.spaces.active.tree_type == "RangeUITree":
            yield area.spaces.active.node_tree


def _botoes_ui(context):
    return [n for t in _arvores_ui(context) if t is not None for n in t.nodes if n.bl_idname == "RangeUIButton"]


def _logica_ligada(context):
    camera = context.scene.camera
    return camera is not None and any(
        c.type == "PYTHON" and c.mode == "MODULE" and c.module == "range_ui_runtime.main"
        for c in camera.game.controllers)


def _botao_ativo(context):
    for arvore in _arvores_ui(context):
        no = arvore.nodes.active if arvore is not None else None
        if no is not None and no.select and no.bl_idname == "RangeUIButton":
            return True
    return False


CHECAGENS = {
    "node_editor": lambda c: any(a.type == "NODE_EDITOR" for a in c.screen.areas),
    "botao_ativo": _botao_ativo,
    "node_editor_ui_tree": lambda c: any(True for _ in _arvores_ui(c)),
    "arvore_criada": lambda c: any(t is not None for t in _arvores_ui(c)),
    "menu_criado": lambda c: bool(_botoes_ui(c)),
    "botao_start": lambda c: any(n.text.strip().lower() == "start" for n in _botoes_ui(c)),
    "logica_ligada": _logica_ligada,
}


def _checagem(passo):
    """Função(context) -> bool do passo, ou None (avanço manual)."""
    c = passo.get("checagem")
    if isinstance(c, str):
        return CHECAGENS.get(c)
    if not isinstance(c, dict) or not c:
        return None
    testes = []
    if "area" in c:
        testes.append(lambda ctx: any(a.type == c["area"] for a in ctx.screen.areas))
    if "modo" in c:
        testes.append(lambda ctx: ctx.mode == c["modo"])
    if "objeto" in c:
        testes.append(lambda ctx: c["objeto"] in bpy.data.objects)
    if "ativo" in c:
        testes.append(lambda ctx: ctx.active_object is not None and ctx.active_object.name == c["ativo"])
    if "expr" in c:
        codigo = compile(c["expr"], "<checagem>", "eval")
        testes.append(lambda ctx: eval(codigo, {"bpy": bpy, "C": ctx, "D": bpy.data}))

    def todas(ctx):
        try:
            return all(teste(ctx) for teste in testes)
        except Exception:  # objeto/área ainda não existe: o passo só não está feito
            return False
    return todas


# ---------------------------------------------------------------- lista e menus

def tutoriais():
    """[(pasta, título, categoria, nº de passos)] dos tutoriais instalados, em ordem de título.

    "categoria" do roteiro.json é um caminho de submenus: "Node Editor/UI Tree"."""
    global _lista
    if _lista is None:
        _lista = []
        for nome in os.listdir(PASTA) if os.path.isdir(PASTA) else ():
            if _pasta_valida(nome) is None:
                continue
            try:
                roteiro = _ler_roteiro(nome)
            except (OSError, ValueError):
                continue  # roteiro quebrado não derruba o menu
            categoria = "/".join(c.strip() for c in _txt(roteiro.get("categoria")).split("/") if c.strip())
            _lista.append((nome, _txt(roteiro.get("titulo")) or nome, categoria, len(roteiro.get("passos", ()))))
        _lista.sort(key=lambda item: item[1].lower())
    return _lista


# Um submenu por categoria, criado a partir dos roteiros (podem ser centenas de tutoriais).
_submenus = []


def _id_submenu(caminho):
    return "INFO_MT_range_tut_%08x" % (zlib.crc32(caminho.encode("utf-8")) & 0xffffffff)


def _item_tutorial(layout, nome, titulo, total, progresso):
    p = progresso.get(nome, {})
    if p.get("feito"):
        texto, icone = titulo, 'FILE_TICK'
    elif p.get("passo", 0) > 0:
        texto, icone = "%s  (%d/%d)" % (titulo, p["passo"] + 1, total), 'PLAY'
    else:
        texto, icone = titulo, 'PLAY'
    layout.operator("wm.range_tutorial_start", text=texto, icon=icone).name = nome


def _desenhar_nivel(layout, caminho):
    """Subcategorias (submenus) e depois os tutoriais desse nível."""
    layout.operator_context = 'INVOKE_DEFAULT'  # o clique tem de chamar invoke (operador modal)
    prefixo = caminho + "/" if caminho else ""
    filhas = sorted({c[len(prefixo):].split("/")[0] for _, _, c, _ in tutoriais()
                     if c.startswith(prefixo) and c != caminho}, key=str.lower)
    for filha in filhas:
        layout.menu(_id_submenu(prefixo + filha), icon='FILE_FOLDER')
    progresso = _progresso()
    for nome, titulo, categoria, total in tutoriais():
        if categoria == caminho:
            _item_tutorial(layout, nome, titulo, total, progresso)


def _desenho_do_nivel(caminho):
    def draw(self, context):  # o registro de Menu exige exatamente (self, context)
        _desenhar_nivel(self.layout, caminho)
    return draw


def _atualizar_menus():
    """(Re)cria os submenus das categorias; chamar depois de mudar a lista de tutoriais."""
    global _lista
    _lista = None
    for cls in _submenus:
        bpy.utils.unregister_class(cls)
    _submenus.clear()
    caminhos = set()
    for _, _, categoria, _ in tutoriais():
        partes = categoria.split("/") if categoria else []
        for i in range(1, len(partes) + 1):
            caminhos.add("/".join(partes[:i]))
    for caminho in sorted(caminhos):
        cls = type(_id_submenu(caminho), (Menu,), {
            "bl_idname": _id_submenu(caminho),
            "bl_label": caminho.split("/")[-1],
            "draw": _desenho_do_nivel(caminho),
        })
        bpy.utils.register_class(cls)
        _submenus.append(cls)


# ---------------------------------------------------------------- estado

def _redesenhar():
    # Qualquer área marcada recompõe a janela inteira, e o desenho do tutorial vem por cima.
    for janela in bpy.context.window_manager.windows:
        if janela.screen.areas:
            janela.screen.areas[0].tag_redraw()
        for area in janela.screen.areas:
            if area.type in ("INFO", "VIEW_3D"):  # aviso de gravação / painel do editor de passos
                area.tag_redraw()


def _parar():
    if "handle" in estado:
        bpy.types.WindowManager.draw_handler_remove(estado["handle"])
    wm = bpy.context.window_manager
    # O timer morre junto com a janela (ou com o window manager, ao carregar arquivo com UI):
    # só remove se os dois ainda são os mesmos.
    if estado and wm.as_pointer() == estado["wm"] and any(j.as_pointer() == estado["janela"] for j in wm.windows):
        wm.event_timer_remove(estado["timer"])
    estado.clear()
    _quadro(None)
    _redesenhar()


def _quadro(alvo):
    """Quadro em volta de um botão, desenhado pela engine (ela é quem sabe onde o botão está)."""
    if hasattr(bpy.types.WindowManager, "ui_highlight_button"):
        # O item do menu aberto fica marcado o passo inteiro (o popup não é redesenhado pelo pisca).
        menu = (estado["roteiro"]["passos"][estado["passo"]].get("alvo") or {}).get("menu", "") if estado else ""
        if alvo:
            bpy.types.WindowManager.ui_highlight_button(alvo[0], alvo[1], alvo[2], menu=menu)
        else:
            bpy.types.WindowManager.ui_highlight_button("VIEW_3D", "WINDOW", "", menu=menu)


def _alvo_botao(context):
    """(tipo da área, região, nome do botão) do passo atual, ou None."""
    alvo = estado["roteiro"]["passos"][estado["passo"]].get("alvo") or {}
    if "botao" not in alvo:
        return None
    return _tipo_area(context.screen, alvo["area"]), alvo["regiao"], alvo["botao"]


def _tipo_area(tela, tipo):
    return min(tela.areas, key=lambda a: (a.y, a.x)).type if tipo == "BAIXO" else tipo


def _ir(delta):
    estado["passo"] += delta
    estado["feito"] = None
    estado["inicio_passo"] = time.time()
    # Voltando, a checagem já é verdadeira: o passo fica parado até o usuário clicar em Próximo.
    estado["manual"] = delta < 0
    if estado["passo"] >= len(estado["roteiro"]["passos"]):
        _marcar_progresso(estado["nome"], passo=0, feito=True)
        _parar()
    else:
        estado["passo"] = max(0, estado["passo"])
        _marcar_progresso(estado["nome"], passo=estado["passo"])
        _quadro(None)  # o quadro do passo anterior some já; o novo vem no próximo tique
        _redesenhar()


@persistent
def _ao_carregar(_):
    if estado:
        _parar()
    if gravacao:  # o timer morreu com a janela antiga; os passos gravados se perdem
        bpy.types.WindowManager.draw_handler_remove(gravacao["handle"])
        if _pasta_valida(gravacao["pasta"]) is None:  # pasta nova, só com a cena inicial
            shutil.rmtree(os.path.join(PASTA, gravacao["pasta"]), ignore_errors=True)
        gravacao.clear()
    if _pendente:
        # Cena inicial aberta: agora começa o tutorial (na janela nova).
        nome, passo = _pendente.pop("nome"), _pendente.pop("passo", 0)
        _pendente.clear()
        janela = bpy.context.window_manager.windows[0]
        bpy.ops.wm.range_tutorial_start({"window": janela, "screen": janela.screen}, 'INVOKE_DEFAULT',
                                        name=nome, step=passo, scene_loaded=True)


# ---------------------------------------------------------------- desenho

def _escala():
    sistema = bpy.context.user_preferences.system
    return sistema.dpi * sistema.pixel_size / 72.0


def _quebrar(texto, largura):
    linhas, atual = [], ""
    for palavra in texto.split():
        teste = (atual + " " + palavra).strip()
        if atual and blf.dimensions(0, teste)[0] > largura:
            linhas.append(atual)
            atual = palavra
        else:
            atual = teste
    return linhas + [atual]


def _retangulo(x0, y0, x1, y1, cor, alfa=1.0):
    bgl.glColor4f(cor[0], cor[1], cor[2], alfa)
    bgl.glRectf(x0, y0, x1, y1)


def _texto(x, y, texto, cor=(1.0, 1.0, 1.0)):
    bgl.glColor4f(cor[0], cor[1], cor[2], 1.0)
    blf.position(0, x, y, 0)
    blf.draw(0, texto)


def _fora():
    """Sem tutorial, ou janela que não é a do tutorial (o modal só recebe os cliques da dele)."""
    return not estado or bpy.context.window.as_pointer() != estado["janela"]


def _contorno(x0, y0, x1, y1):
    bgl.glColor4f(LARANJA[0], LARANJA[1], LARANJA[2], 1.0)
    bgl.glLineWidth(3.0 * _escala())
    bgl.glBegin(bgl.GL_LINE_LOOP)
    for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
        bgl.glVertex2f(x, y)
    bgl.glEnd()
    bgl.glLineWidth(1.0)


def _achar_no(arvore, nome):
    for n in arvore.nodes:
        if n.bl_idname == "RangeUIButton" and n.text == nome:
            return n
    return next((n for n in arvore.nodes if n.name == nome or n.label == nome), None)


def _quadro_no(nome):
    """(x0, y0, x1, y1, região) em pixels da janela do nó com esse nome, em qualquer Node Editor."""
    e = _escala()
    for area in bpy.context.window.screen.areas:
        arvore = area.spaces.active.node_tree if area.type == "NODE_EDITOR" else None
        no = _achar_no(arvore, nome) if arvore is not None else None
        regiao = next((r for r in area.regions if r.type == "WINDOW"), None)
        if no is None or regiao is None:
            continue
        x, y, pai = no.location.x, no.location.y, no.parent
        while pai is not None:
            x, y, pai = x + pai.location.x, y + pai.location.y, pai.parent
        x, y = x * e, y * e
        if no.hide and no.bl_idname.startswith("RangeUI"):
            # Nó recolhido da UI Tree: a prévia do widget ocupa a largura do nó e o bloco vem depois
            # dela, centrado na altura do título.
            x, y = x + no.width * e, y + no.dimensions.y / 2 - 10 * e
        x0, y1 = regiao.view2d.view_to_region(x, y, clip=False)
        x1, y0 = regiao.view2d.view_to_region(x + no.dimensions.x, y - no.dimensions.y, clip=False)
        return (regiao.x + x0 - 4 * e, regiao.y + y0 - 4 * e, regiao.x + x1 + 4 * e, regiao.y + y1 + 4 * e, regiao)
    return None


def _area_alvo(tela, passo):
    """Área onde o passo acontece (para o contorno e para o cartão não cobrir)."""
    alvo = passo.get("alvo") or {}
    if "no" in alvo:
        tipo = "NODE_EDITOR"
    else:
        tipo = _tipo_area(tela, alvo.get("area") or passo.get("destaque") or "")
    return next((a for a in tela.areas if a.type == tipo), None)


def _com_dica(passo):
    """Dica do passo, quando o usuário está parado nele há tempo; senão ""."""
    if estado["feito"] is not None or time.time() - estado.get("inicio_passo", time.time()) < DICA_SEGUNDOS:
        return ""
    return _txt(passo.get("dica"))


def _desenhar():
    if _fora():
        return
    try:
        _desenhar_tudo()
    finally:
        # Os menus e outros desenhos vêm depois: não deixa estado de GL para eles.
        bgl.glDisable(bgl.GL_SCISSOR_TEST)
        bgl.glDisable(bgl.GL_BLEND)
        bgl.glLineWidth(1.0)


def _desenhar_tudo():
    tela = bpy.context.window.screen
    passo = estado["roteiro"]["passos"][estado["passo"]]
    alvo = passo.get("alvo") or {}
    if "no" in alvo:
        quadro = _quadro_no(alvo["no"]) if estado["pisca"] else None
        if quadro:
            # Só dentro da região do editor (o nó pode estar meio fora da tela).
            r = quadro[4]
            bgl.glEnable(bgl.GL_SCISSOR_TEST)
            bgl.glScissor(r.x, r.y, r.width, r.height)
            _contorno(*quadro[:4])
            bgl.glDisable(bgl.GL_SCISSOR_TEST)
    elif "botao" not in alvo and passo.get("destaque"):
        tipo = _tipo_area(tela, passo["destaque"])
        for a in tela.areas:
            if a.type == tipo:
                _contorno(a.x + 2, a.y + 2, a.x + a.width - 2, a.y + a.height - 2)
    _desenhar_cartao(tela, passo)


def _desenhar_cartao(tela, passo):
    janela = bpy.context.window
    e = _escala()
    passos = estado["roteiro"]["passos"]
    feito = estado["feito"] is not None
    cor = VERDE if feito else LARANJA

    margem, alt_botao, alt_linha = 12 * e, 24 * e, 21 * e
    largura = min(560 * e, janela.width - 24 * e)
    blf.size(0, int(15 * e), 72)
    linhas = _quebrar(_txt(passo.get("texto")), largura - 2 * margem)
    dica = _com_dica(passo)
    linhas_dica = _quebrar("Dica: " + dica, largura - 2 * margem) if dica else []
    altura = margem + alt_botao + margem + (len(linhas) + len(linhas_dica)) * alt_linha + 20 * e + margem
    x0 = (janela.width - largura) / 2
    # Embaixo, a não ser que o passo aconteça na metade de baixo da janela: aí vai para cima.
    area = _area_alvo(tela, passo)
    if area is not None and area.y + area.height / 2 < janela.height / 2:
        y0 = janela.height - 34 * e - altura  # abaixo do cabeçalho do topo
    else:
        y0 = 34 * e
    x1, y1 = x0 + largura, y0 + altura

    bgl.glEnable(bgl.GL_BLEND)
    _retangulo(x0, y0, x1, y1, (0.09, 0.09, 0.11), 0.94)
    # Barra de progresso no topo do cartão.
    _retangulo(x0, y1 - 3 * e, x1, y1, (0.3, 0.3, 0.33))
    _retangulo(x0, y1 - 3 * e, x0 + largura * (estado["passo"] + (1 if feito else 0)) / len(passos), y1, cor)

    y = y1 - margem - 13 * e
    blf.size(0, int(11 * e), 72)
    _texto(x0 + margem, y, "TUTORIAL  %d/%d%s" % (estado["passo"] + 1, len(passos), "  -  feito!" if feito else ""), cor)
    blf.size(0, int(15 * e), 72)
    for linha in linhas:
        y -= alt_linha
        _texto(x0 + margem, y, linha)
    for linha in linhas_dica:
        y -= alt_linha
        _texto(x0 + margem, y, linha, AMARELO)

    # Botões clicáveis: o operador modal confere o clique nestes retângulos (pixels da janela).
    blf.size(0, int(12 * e), 72)
    ultimo = estado["passo"] == len(passos) - 1
    automatico = _checagem(passo) is not None and not estado["manual"]
    avancar = "Concluir" if ultimo else ("Pular" if automatico else "Próximo")
    botoes = {}

    def botao(nome, rotulo, x, direita=False, forte=False):
        larg = blf.dimensions(0, rotulo)[0] + 20 * e
        if direita:
            x -= larg
        y_b = y0 + margem
        _retangulo(x, y_b, x + larg, y_b + alt_botao, LARANJA if forte else (0.25, 0.25, 0.28))
        _texto(x + 10 * e, y_b + 8 * e, rotulo, (0.05, 0.05, 0.05) if forte else (0.9, 0.9, 0.9))
        botoes[nome] = (x, y_b, x + larg, y_b + alt_botao)
        return x

    botao("fechar", "Fechar", x0 + margem)
    x = botao("proximo", avancar, x1 - margem, direita=True, forte=not automatico)
    if estado["passo"] > 0:
        botao("voltar", "Voltar", x - 6 * e, direita=True)
    estado["botoes"] = botoes
    bgl.glDisable(bgl.GL_BLEND)


# ---------------------------------------------------------------- tocar

class RANGE_OT_tutorial_start(Operator):
    """Start this tutorial: a card over the window shows each step and advances as you do them"""
    bl_idname = "wm.range_tutorial_start"
    bl_label = "Start Tutorial"

    name = StringProperty()
    step = IntProperty(default=-1, options={'SKIP_SAVE'},
                       description="Step to start at (-1: continue where the user stopped)")
    scene_loaded = BoolProperty(options={'HIDDEN', 'SKIP_SAVE'})

    def invoke(self, context, event):
        if _pasta_valida(self.name) is None:
            self.report({'ERROR'}, "Tutorial not found: " + self.name)
            return {'CANCELLED'}
        if self.step < 0:
            p = _progresso().get(self.name, {})
            self.step = 0 if p.get("feito") else p.get("passo", 0)
        # Do começo, com cena inicial: abre a cena antes (pergunta se há mudanças não salvas).
        if self.step == 0 and not self.scene_loaded and os.path.isfile(os.path.join(PASTA, self.name, CENA)):
            if bpy.data.is_dirty:
                return context.window_manager.invoke_confirm(self, event)
            return self.execute(context)
        return self.comecar(context)

    def execute(self, context):
        # Uma cópia temporária da cena: salvar no tutorial não estraga o original.
        copia = os.path.join(bpy.app.tempdir, "tutorial_" + CENA)
        shutil.copyfile(os.path.join(PASTA, self.name, CENA), copia)
        _pendente.update(nome=self.name, passo=0)
        try:
            bpy.ops.wm.open_mainfile(filepath=copia)
        finally:
            _pendente.clear()  # já usado no load_post; se a abertura falhou, não fica para depois
        return {'FINISHED'}

    def comecar(self, context):
        if estado:
            _parar()  # o operador do tutorial anterior percebe pela chave e termina
        roteiro = _ler_roteiro(self.name)
        if not roteiro.get("passos"):
            self.report({'WARNING'}, "This tutorial has no steps")
            return {'CANCELLED'}
        self.chave = object()
        passo = max(0, min(self.step, len(roteiro["passos"]) - 1))
        handle = bpy.types.WindowManager.draw_handler_add(_desenhar, ())
        estado.update(nome=self.name, roteiro=roteiro, passo=passo, feito=None, manual=False, botoes={},
                      handle=handle, chave=self.chave, pisca=True, inicio_passo=time.time(),
                      wm=context.window_manager.as_pointer(), janela=context.window.as_pointer(),
                      timer=context.window_manager.event_timer_add(0.3, context.window))
        _marcar_progresso(self.name, passo=passo, feito=False)
        context.window_manager.modal_handler_add(self)
        _redesenhar()
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if estado.get("chave") is not self.chave:  # _parar() já limpou tudo
            return {'CANCELLED'}
        # TIMER de qualquer operador chega aqui (o 2.79 não diz de qual timer): vale o relógio.
        if event.type == 'TIMER' and time.time() - estado.get("ultimo", 0.0) > 0.25:
            estado["ultimo"] = time.time()
            self.tique(context)
            if not estado:
                return {'FINISHED'}
        elif event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            for nome, (x0, y0, x1, y1) in estado["botoes"].items():
                if x0 <= event.mouse_x <= x1 and y0 <= event.mouse_y <= y1:
                    if nome == "fechar":
                        _parar()
                    else:
                        _ir(-1 if nome == "voltar" else 1)
                    return {'RUNNING_MODAL'} if estado else {'FINISHED'}
        return {'PASS_THROUGH'}

    def tique(self, context):
        passo = estado["roteiro"]["passos"][estado["passo"]]
        # Pisca o alvo: aceso em dois tiques, apagado em um; com a dica na tela, pisca a cada tique.
        estado["tique"] = estado.get("tique", 0) + 1
        ritmo = 2 if _com_dica(passo) else 3
        estado["pisca"] = estado["tique"] % ritmo != 0 and estado["feito"] is None
        _quadro(_alvo_botao(context) if estado["pisca"] else None)
        _redesenhar()
        if estado["feito"] is not None:
            if time.time() - estado["feito"] > PAUSA_FEITO:
                _ir(1)
        elif not estado["manual"]:
            checagem = _checagem(passo)
            if checagem and checagem(context):
                estado["feito"] = time.time()
                _redesenhar()


class RANGE_OT_tutorial_stop(Operator):
    """Close the running tutorial"""
    bl_idname = "wm.range_tutorial_stop"
    bl_label = "Stop Tutorial"

    @classmethod
    def poll(cls, context):
        return bool(estado)

    def execute(self, context):
        _parar()
        return {'FINISHED'}


class RANGE_OT_tutorial_restart(Operator):
    """Start this tutorial again from the first step"""
    bl_idname = "wm.range_tutorial_restart"
    bl_label = "Restart Tutorial"

    name = StringProperty()

    def invoke(self, context, event):
        # O progresso volta a zero quando o tutorial começa de fato (comecar).
        return bpy.ops.wm.range_tutorial_start('INVOKE_DEFAULT', name=self.name, step=0)


_itens_busca = {"lista": None, "itens": []}  # o 2.79 guarda ponteiros para estes textos


def _busca(self, context):
    lista = tutoriais()
    if _itens_busca["lista"] is not lista:  # só refaz quando a lista de tutoriais mudou
        _itens_busca["lista"] = lista
        _itens_busca["itens"] = [(nome, "%s  -  %s" % (titulo, categoria.replace("/", " > ")) if categoria else titulo, "")
                                 for nome, titulo, categoria, _ in lista]
    return _itens_busca["itens"]


class RANGE_OT_tutorial_search(Operator):
    """Search the tutorials by name"""
    bl_idname = "wm.range_tutorial_search"
    bl_label = "Search Tutorials"
    bl_property = "tutorial"

    tutorial = EnumProperty(items=_busca)

    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        return bpy.ops.wm.range_tutorial_start('INVOKE_DEFAULT', name=self.tutorial)


# ---------------------------------------------------------------- gravação

gravacao = {}  # vazio = não está gravando


def _passo_do_clique(campos):
    """Passo do roteiro a partir de ui_last_click(), ou None para cliques que não contam."""
    _, espaco, regiao, texto, op, prop, dica, _abre = campos
    texto = texto.split("|")[0].strip()  # itens de menu trazem o atalho depois de "|"
    if texto and "|" not in campos[3]:
        botao = texto
    elif op:
        botao = "op:" + op
    elif prop:
        botao = "prop:" + prop  # "context=PARTICLES" nas abas
    elif dica:
        botao = "tip:" + dica
    else:
        return None
    nome = (texto or dica.split(".")[0] or op).rstrip(":")
    return {"texto": "Clique em %s." % nome, "narracao": "", "destaque": espaco,
            "checagem": None, "alvo": {"area": espaco, "regiao": regiao, "botao": botao}}


def _desenhar_gravacao():
    if not gravacao or bpy.context.window.as_pointer() != gravacao["janela"]:
        return
    e = _escala()
    blf.size(0, int(13 * e), 72)
    texto = "Gravando tutorial: %d passos  (Stop Rec no cabeçalho)" % len(gravacao["passos"])
    largura = blf.dimensions(0, texto)[0] + 34 * e
    x0, y0 = (bpy.context.window.width - largura) / 2, 34 * e
    bgl.glEnable(bgl.GL_BLEND)
    _retangulo(x0, y0, x0 + largura, y0 + 28 * e, (0.09, 0.09, 0.11), 0.94)
    _retangulo(x0 + 10 * e, y0 + 9 * e, x0 + 20 * e, y0 + 19 * e, (0.9, 0.2, 0.2))
    _texto(x0 + 26 * e, y0 + 9 * e, texto)
    bgl.glDisable(bgl.GL_BLEND)


class RANGE_OT_tutorial_record(Operator):
    """Record a new tutorial: every button you click becomes a step"""
    bl_idname = "wm.range_tutorial_record"
    bl_label = "Record Tutorial"

    title = StringProperty(name="Name", description="Tutorial name, shown in Help > Tutorials")
    category = StringProperty(name="Category",
                              description="Submenus, like \"Node Editor/UI Tree\". "
                                          "Empty: the editor where most clicks happened")
    save_scene = BoolProperty(name="Save Start Scene", default=True,
                              description="Save the scene as it is now: the tutorial opens it when it starts")

    @classmethod
    def poll(cls, context):
        return not gravacao and not estado and hasattr(bpy.types.WindowManager, "ui_last_click")

    def invoke(self, context, event):
        # Pergunta o nome antes; a gravação começa no OK (execute).
        self.title = ""
        return context.window_manager.invoke_props_dialog(self, width=360)

    def draw(self, context):
        self.layout.prop(self, "title")
        self.layout.prop(self, "category")
        self.layout.prop(self, "save_scene")

    def execute(self, context):
        wm = context.window_manager
        titulo = self.title.strip() or time.strftime("Gravado %d/%m %H:%M")
        nome = _nome_pasta(titulo)
        pasta = os.path.join(PASTA, nome)
        os.makedirs(pasta)
        if self.save_scene:
            # Como a cena está agora, antes do primeiro clique.
            bpy.ops.wm.save_as_mainfile(filepath=os.path.join(pasta, CENA), copy=True)
        gravacao.update(passos=[], titulo=titulo, categoria=self.category.strip(), pasta=nome,
                        ultimo=wm.ui_click_count(), janela=context.window.as_pointer(),
                        handle=bpy.types.WindowManager.draw_handler_add(_desenhar_gravacao, ()),
                        timer=wm.event_timer_add(0.2, context.window))
        wm.modal_handler_add(self)
        _redesenhar()
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if not gravacao:
            return {'FINISHED'}
        if event.type == 'TIMER':
            if self.consumir(context.window_manager):
                _redesenhar()
        return {'PASS_THROUGH'}

    @classmethod
    def consumir(cls, wm):
        """Anota os cliques novos; True se havia algum."""
        total = wm.ui_click_count()
        if total == gravacao["ultimo"]:
            return False
        for n in range(gravacao["ultimo"] + 1, total + 1):
            campos = wm.ui_last_click(index=n).split("\t")
            if len(campos) == 8:  # os mais antigos que 16 cliques num tique se perdem
                cls.anotar(campos)
        gravacao["ultimo"] = total
        return True

    @staticmethod
    def anotar(campos):
        passos = gravacao["passos"]
        if campos[4].startswith("WM_OT_range_tutorial"):
            # Comandos dos tutoriais (Stop Recording): o menu aberto para chegar neles não é passo.
            while passos and passos[-1]["alvo"]["area"] == "INFO" and passos[-1]["alvo"]["botao"] in ("About", "Tutorials"):
                passos.pop()
            gravacao["abriu"] = False
            return
        passo = _passo_do_clique(campos)
        if passo is None:
            return
        no_menu = passo["alvo"]["regiao"] == "TEMPORARY"
        # Botão que abriu um menu e ainda espera o item (o menu pode ter sido fechado sem escolha,
        # ou o mouse passou por outros menus da barra).
        esperando = passos[-1] if passos and gravacao.get("abriu") else None
        if campos[7] == "1":
            if no_menu:
                return  # submenu dentro do menu: o item escolhido depois é o que conta
            if esperando:
                passos.pop()
            passos.append(passo)
            gravacao["abriu"] = True
            return
        gravacao["abriu"] = False
        if no_menu and not esperando:
            # Menu aberto por tecla (Shift+A, W...): não há botão para marcar, só o item.
            passo["texto"] = "No menu, escolha %s." % passo["texto"][len("Clique em "):-1]
        if no_menu and esperando:
            esperando["alvo"]["menu"] = passo["alvo"]["botao"]
            esperando["texto"] = esperando["texto"][:-1] + " e escolha %s." % passo["texto"][len("Clique em "):-1]
            return
        if esperando:
            passos.pop()
        elif passos and passos[-1]["alvo"] == dict(passo["alvo"], menu=passos[-1]["alvo"].get("menu")):
            return  # o botão do menu aplicando o item escolhido (já está no passo)
        passos.append(passo)


class RANGE_OT_tutorial_record_stop(Operator):
    """Stop recording and save the steps as a new tutorial"""
    bl_idname = "wm.range_tutorial_record_stop"
    bl_label = "Stop Recording"

    @classmethod
    def poll(cls, context):
        return bool(gravacao)

    def execute(self, context):
        wm = context.window_manager
        # Cliques depois do último tique; o menu aberto para chegar aqui (Help > Tutorials) não
        # é passo.
        RANGE_OT_tutorial_record.consumir(wm)
        if any(j.as_pointer() == gravacao["janela"] for j in wm.windows):
            wm.event_timer_remove(gravacao["timer"])
        bpy.types.WindowManager.draw_handler_remove(gravacao["handle"])
        passos, titulo, categoria, nome = gravacao["passos"], gravacao["titulo"], gravacao["categoria"], gravacao["pasta"]
        gravacao.clear()
        _redesenhar()
        pasta = os.path.join(PASTA, nome)
        if not passos:
            shutil.rmtree(pasta, ignore_errors=True)
            self.report({'WARNING'}, "Nothing recorded")
            return {'CANCELLED'}
        if not categoria:
            # O editor onde aconteceu a maioria dos cliques, pelo nome que aparece no menu de editores.
            tipos = [p["alvo"]["area"] for p in passos if p["alvo"].get("area")]
            tipo = max(set(tipos), key=tipos.count) if tipos else ""
            itens = bpy.types.Area.bl_rna.properties["type"].enum_items
            categoria = itens[tipo].name if tipo in itens else ""
        _gravar_roteiro(nome, {"titulo": titulo, "categoria": categoria, "passos": passos})
        _atualizar_menus()
        self.report({'INFO'}, "Tutorial saved: " + os.path.join(pasta, "roteiro.json"))
        return {'FINISHED'}


# ---------------------------------------------------------------- editor de passos

class RangeTutorialStep(PropertyGroup):
    text = StringProperty(name="Text")
    hint = StringProperty(name="Hint", description="Shown when the user stays on this step for a while")
    data = StringProperty(options={'HIDDEN'})  # o resto do passo (alvo, checagem...), em JSON


def _editando(context):
    return context.window_manager.range_tutorial_editing


class RANGE_OT_tutorial_edit(Operator):
    """Edit the texts and the order of the steps (panel Tutorial in the 3D View tool shelf)"""
    bl_idname = "wm.range_tutorial_edit"
    bl_label = "Edit Tutorial"

    name = StringProperty()

    def execute(self, context):
        if _pasta_valida(self.name) is None:
            self.report({'ERROR'}, "Tutorial not found: " + self.name)
            return {'CANCELLED'}
        roteiro = _ler_roteiro(self.name)
        wm = context.window_manager
        wm.range_tutorial_editing = self.name
        wm.range_tutorial_title = _txt(roteiro.get("titulo"))
        wm.range_tutorial_category = _txt(roteiro.get("categoria"))
        wm.range_tutorial_steps.clear()
        for passo in roteiro.get("passos", ()):
            item = wm.range_tutorial_steps.add()
            item.text = _txt(passo.get("texto"))
            item.hint = _txt(passo.get("dica"))
            item.data = json.dumps(passo, ensure_ascii=False)
        # Mostra a barra de ferramentas da 3D View, onde fica o painel.
        for area in context.screen.areas:
            if area.type == "VIEW_3D":
                ferramentas = next((r for r in area.regions if r.type == "TOOLS"), None)
                if ferramentas is not None and ferramentas.width <= 1:
                    bpy.ops.view3d.toolshelf({"window": context.window, "screen": context.screen, "area": area,
                                              "region": next(r for r in area.regions if r.type == "WINDOW")})
                area.tag_redraw()
                break
        self.report({'INFO'}, "Editing in 3D View > Tool Shelf > Tutorial")
        return {'FINISHED'}


class RANGE_OT_tutorial_edit_step(Operator):
    """Move, delete or play from this step"""
    bl_idname = "wm.range_tutorial_edit_step"
    bl_label = "Tutorial Step"

    action = EnumProperty(items=(("UP", "Up", ""), ("DOWN", "Down", ""), ("DELETE", "Delete", ""),
                                 ("PLAY", "Play From Here", "Save and play the tutorial from this step")))
    index = IntProperty()

    def execute(self, context):
        passos = context.window_manager.range_tutorial_steps
        i = self.index
        if self.action == "UP" and i > 0:
            passos.move(i, i - 1)
        elif self.action == "DOWN" and i < len(passos) - 1:
            passos.move(i, i + 1)
        elif self.action == "DELETE":
            passos.remove(i)
        elif self.action == "PLAY":
            bpy.ops.wm.range_tutorial_save()
            return bpy.ops.wm.range_tutorial_start('INVOKE_DEFAULT', name=_editando(context), step=i)
        return {'FINISHED'}


class RANGE_OT_tutorial_save(Operator):
    """Save the edited tutorial"""
    bl_idname = "wm.range_tutorial_save"
    bl_label = "Save Tutorial"

    def execute(self, context):
        wm = context.window_manager
        nome = wm.range_tutorial_editing
        if _pasta_valida(nome) is None:
            self.report({'ERROR'}, "Tutorial not found: " + nome)
            return {'CANCELLED'}
        roteiro = _ler_roteiro(nome)
        roteiro["titulo"] = _com_txt(roteiro.get("titulo"), wm.range_tutorial_title.strip() or nome)
        roteiro["categoria"] = _com_txt(roteiro.get("categoria"), wm.range_tutorial_category.strip())
        passos = []
        for item in wm.range_tutorial_steps:
            passo = json.loads(item.data)
            passo["texto"] = _com_txt(passo.get("texto"), item.text)
            if item.hint.strip() or passo.get("dica"):
                passo["dica"] = _com_txt(passo.get("dica"), item.hint.strip())
            passos.append(passo)
        roteiro["passos"] = passos
        if estado and estado.get("nome") == nome:
            _parar()  # tocando a versão antiga: os passos mudaram de lugar
        _gravar_roteiro(nome, roteiro)
        _atualizar_menus()
        self.report({'INFO'}, "Tutorial saved")
        return {'FINISHED'}


class RANGE_OT_tutorial_edit_close(Operator):
    """Close the tutorial editor (unsaved changes are lost)"""
    bl_idname = "wm.range_tutorial_edit_close"
    bl_label = "Close Editor"

    def execute(self, context):
        context.window_manager.range_tutorial_editing = ""
        context.window_manager.range_tutorial_steps.clear()
        return {'FINISHED'}


class VIEW3D_PT_range_tutorial_editor(Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'TOOLS'
    bl_category = "Tutorial"
    bl_label = "Tutorial Editor"

    @classmethod
    def poll(cls, context):
        return bool(_editando(context))

    def draw(self, context):
        wm = context.window_manager
        layout = self.layout
        layout.prop(wm, "range_tutorial_title", text="Name")
        layout.prop(wm, "range_tutorial_category", text="Category")
        for i, item in enumerate(wm.range_tutorial_steps):
            caixa = layout.box()
            linha = caixa.row(align=True)
            linha.label("%d." % (i + 1))
            for acao, icone in (("PLAY", 'PLAY'), ("UP", 'TRIA_UP'), ("DOWN", 'TRIA_DOWN'), ("DELETE", 'X')):
                op = linha.operator(RANGE_OT_tutorial_edit_step.bl_idname, text="", icon=icone)
                op.action, op.index = acao, i
            caixa.prop(item, "text", text="")
            caixa.prop(item, "hint", text="Hint")
        linha = layout.row(align=True)
        linha.operator(RANGE_OT_tutorial_save.bl_idname, icon='FILE_TICK')
        linha.operator(RANGE_OT_tutorial_edit_close.bl_idname, icon='X')


# ---------------------------------------------------------------- apagar, exportar, importar

class RANGE_OT_tutorial_delete(Operator):
    """Delete this tutorial (its folder with the roteiro.json)"""
    bl_idname = "wm.range_tutorial_delete"
    bl_label = "Delete Tutorial"

    name = StringProperty()

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        pasta = _pasta_valida(self.name)  # só uma pasta de tutorial, direto dentro de PASTA
        if pasta is None:
            self.report({'ERROR'}, "Tutorial not found: " + self.name)
            return {'CANCELLED'}
        if estado and estado.get("nome") == self.name:
            _parar()
        if _editando(context) == self.name:
            bpy.ops.wm.range_tutorial_edit_close()
        shutil.rmtree(pasta)
        _atualizar_menus()
        self.report({'INFO'}, "Tutorial deleted: " + self.name)
        return {'FINISHED'}


class RANGE_OT_tutorial_export(Operator):
    """Save this tutorial as a .zip to share it"""
    bl_idname = "wm.range_tutorial_export"
    bl_label = "Export Tutorial"

    name = StringProperty()
    filepath = StringProperty(subtype='FILE_PATH')
    filter_glob = StringProperty(default="*.zip", options={'HIDDEN'})

    def invoke(self, context, event):
        self.filepath = self.name + ".zip"
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        pasta = _pasta_valida(self.name)
        if pasta is None:
            self.report({'ERROR'}, "Tutorial not found: " + self.name)
            return {'CANCELLED'}
        destino = bpy.path.ensure_ext(self.filepath, ".zip")
        with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
            for raiz, _, arquivos in os.walk(pasta):
                for arquivo in arquivos:
                    caminho = os.path.join(raiz, arquivo)
                    z.write(caminho, os.path.join(self.name, os.path.relpath(caminho, pasta)))
        self.report({'INFO'}, "Tutorial exported: " + destino)
        return {'FINISHED'}


class RANGE_OT_tutorial_import(Operator):
    """Install a tutorial from a .zip (made with Export Tutorial)"""
    bl_idname = "wm.range_tutorial_import"
    bl_label = "Import Tutorial"

    filepath = StringProperty(subtype='FILE_PATH')
    filter_glob = StringProperty(default="*.zip", options={'HIDDEN'})

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        try:
            z = zipfile.ZipFile(self.filepath)
        except (OSError, zipfile.BadZipFile) as erro:
            self.report({'ERROR'}, "Not a tutorial .zip: %s" % erro)
            return {'CANCELLED'}
        with z:
            membros = [m for m in z.infolist() if not m.filename.endswith("/")]
            nomes = [m.filename.replace("\\", "/") for m in membros]
            # Nada de caminho absoluto, "..", "." ou nome repetido: o zip só escreve dentro da pasta
            # nova, e cada arquivo uma vez só.
            if not nomes or len(set(n.lower() for n in nomes)) != len(nomes) or any(
                    n.startswith("/") or ":" in n or any(s in ("", ".", "..") for s in n.split("/")) for n in nomes):
                self.report({'ERROR'}, "Invalid tutorial .zip")
                return {'CANCELLED'}
            topo = {n.split("/")[0] for n in nomes}
            prefixo = topo.pop() + "/" if len(topo) == 1 and all("/" in n for n in nomes) else ""
            if prefixo + "roteiro.json" not in nomes:
                self.report({'ERROR'}, "The .zip has no roteiro.json")
                return {'CANCELLED'}
            try:
                roteiro = json.loads(z.read(prefixo + "roteiro.json").decode("utf-8"))
            except ValueError:
                self.report({'ERROR'}, "Broken roteiro.json")
                return {'CANCELLED'}
            nome = _nome_pasta(prefixo.rstrip("/") or _txt(roteiro.get("titulo")) or "tutorial")
            pasta = os.path.join(PASTA, nome)
            for membro, n in zip(membros, nomes):
                destino = os.path.join(pasta, *n[len(prefixo):].split("/"))
                os.makedirs(os.path.dirname(destino), exist_ok=True)
                with z.open(membro) as origem, open(destino, "wb") as saida:
                    shutil.copyfileobj(origem, saida)
        _atualizar_menus()
        self.report({'INFO'}, "Tutorial installed: " + _txt(roteiro.get("titulo")))
        return {'FINISHED'}


# ---------------------------------------------------------------- menus

class INFO_MT_range_tutorials(Menu):
    bl_label = "Tutorials"

    def draw(self, context):
        layout = self.layout
        layout.operator_context = 'INVOKE_DEFAULT'
        layout.operator(RANGE_OT_tutorial_search.bl_idname, text="Search Tutorials...", icon='VIEWZOOM')
        layout.separator()
        _desenhar_nivel(layout, "")
        if estado:
            layout.separator()
            layout.operator(RANGE_OT_tutorial_stop.bl_idname, icon='X')
        layout.separator()
        if gravacao:
            layout.operator(RANGE_OT_tutorial_record_stop.bl_idname, icon='REC')
        else:
            layout.operator(RANGE_OT_tutorial_record.bl_idname, icon='REC')
        layout.operator(RANGE_OT_tutorial_import.bl_idname, text="Import Tutorial...", icon='IMPORT')


def _menu_direito(self, context):
    """Clique direito num tutorial do menu: editar, recomeçar, exportar, apagar."""
    op = getattr(context, "button_operator", None)
    if op is None or op.rna_type.identifier != "WM_OT_range_tutorial_start" or not op.name:
        return
    layout = self.layout
    layout.separator()
    layout.operator_context = 'INVOKE_DEFAULT'
    layout.operator(RANGE_OT_tutorial_restart.bl_idname, icon='FILE_REFRESH').name = op.name
    layout.operator(RANGE_OT_tutorial_edit.bl_idname, icon='TEXT').name = op.name
    layout.operator(RANGE_OT_tutorial_export.bl_idname, text="Export Tutorial...", icon='EXPORT').name = op.name
    layout.operator(RANGE_OT_tutorial_delete.bl_idname, icon='X').name = op.name


def _cabecalho(self, context):
    """Aviso de gravação no cabeçalho de cima, com o botão de parar."""
    if gravacao:
        linha = self.layout.row()
        linha.alert = True
        linha.operator(RANGE_OT_tutorial_record_stop.bl_idname, icon='REC',
                       text="Stop Rec (%d)" % len(gravacao["passos"]))


CLASSES = (RANGE_OT_tutorial_start, RANGE_OT_tutorial_stop, RANGE_OT_tutorial_restart, RANGE_OT_tutorial_search,
           RANGE_OT_tutorial_record, RANGE_OT_tutorial_record_stop, RangeTutorialStep, RANGE_OT_tutorial_edit,
           RANGE_OT_tutorial_edit_step, RANGE_OT_tutorial_save, RANGE_OT_tutorial_edit_close,
           VIEW3D_PT_range_tutorial_editor, RANGE_OT_tutorial_delete, RANGE_OT_tutorial_export,
           RANGE_OT_tutorial_import, INFO_MT_range_tutorials)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    wm = bpy.types.WindowManager
    wm.range_tutorial_editing = StringProperty(options={'HIDDEN'})
    wm.range_tutorial_title = StringProperty(name="Name")
    wm.range_tutorial_category = StringProperty(name="Category", description="Submenus, like \"Node Editor/UI Tree\"")
    wm.range_tutorial_steps = CollectionProperty(type=RangeTutorialStep)
    bpy.app.handlers.load_post.append(_ao_carregar)
    bpy.types.INFO_HT_header.append(_cabecalho)
    bpy.types.WM_MT_button_context.append(_menu_direito)
    _atualizar_menus()


def unregister():
    if estado:
        _parar()
    if gravacao:
        bpy.types.WindowManager.draw_handler_remove(gravacao["handle"])
        gravacao.clear()
    bpy.app.handlers.load_post.remove(_ao_carregar)
    bpy.types.INFO_HT_header.remove(_cabecalho)
    bpy.types.WM_MT_button_context.remove(_menu_direito)
    for cls in _submenus:
        bpy.utils.unregister_class(cls)
    _submenus.clear()
    wm = bpy.types.WindowManager
    del wm.range_tutorial_editing, wm.range_tutorial_title, wm.range_tutorial_category, wm.range_tutorial_steps
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
