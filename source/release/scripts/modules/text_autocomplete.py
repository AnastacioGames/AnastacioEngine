# Provedor do autocompletar do Text Editor (chamado pelo C em text_autocomplete.c).
#
# candidatos(linha, coluna_bytes) -> str
#   "SKIP"            : nao sugerir nada (cursor em comentario/string)
#   "OK\n<t><nome>\n" : uma linha por candidato; <t> = cor FMT_TYPE_* do editor
# O C filtra pelo prefixo digitado, entao aqui vai o conjunto INTEIRO do contexto.
#
# A API do jogo (bge) nao existe no editor: os nomes/tipos vem de text_autocomplete_api.json,
# gerado pelo proprio runtime (tools/autocomplete/gerar_api_autocomplete.py). Nada do script
# do usuario e executado nem importado; so modulos ja carregados ou da lista PERMITIDOS.

import builtins
import keyword
import os
import re
import sys

# cores (FMT_TYPE_* de text_format.h)
COR = {"m": "d", "c": "r", "f": "v", "a": "q", "k": "n", "kw": "b"}

ALIAS_MODULO = {
    "Range": "bge", "range": "bge", "GameLogic": "bge.logic", "GameKeys": "bge.events",
    "Rasterizer": "bge.render", "PhysicsConstraints": "bge.constraints", "VideoTexture": "bge.texture",
    "GameTypes": "bge.types",
}

# modulos reais do editor que podem ser introspectados (stdlib sem efeito colateral ao importar)
PERMITIDOS = {
    "math", "cmath", "random", "time", "datetime", "os", "os.path", "sys", "json", "re",
    "collections", "itertools", "functools", "operator", "string", "struct", "copy", "heapq",
    "bisect", "enum", "types", "textwrap", "pathlib", "statistics", "decimal", "fractions",
    "array", "pickle", "csv", "base64", "hashlib", "zlib", "threading", "queue", "weakref",
    "contextlib", "dataclasses", "typing", "abc", "inspect", "traceback", "glob", "shutil",
    "socket", "struct", "uuid",
}

TIPOS_PY = {"str": str, "list": list, "dict": dict, "int": int, "float": float, "bool": bool,
            "tuple": tuple, "set": set, "bytes": bytes}

# nomes de parametro muito comuns em scripts de jogo
PARAM_CONHECIDO = {"cont": "SCA_PythonController", "controller": "SCA_PythonController"}

_catalogo = None
# o que a ultima lista mostrou (para detalhe() do item selecionado)
_ultimo = {"coisa": None, "membros": {}, "ctx": None}


def _api():
    global _catalogo
    if _catalogo is None:
        import json
        caminho = os.path.join(os.path.dirname(__file__), "text_autocomplete_api.json")
        # sem catalogo e erro de verdade: o C mostra o aviso uma vez e cai nas palavras do texto
        with open(caminho, encoding="utf-8") as f:
            _catalogo = json.load(f)
    return _catalogo


# ---------------------------------------------------------------------------
# "coisas" resolvidas: ("mod", "bge.logic") | ("cls", "KX_GameObject") (instancia)
# | ("tipo", "KX_GameObject") (a propria classe) | ("py", objeto python) | ("user", info)

def _membros_classe(nome, visto=None):
    classes = _api()["classes"]
    info = classes.get(nome)
    if not info:
        return {}
    saida = {}
    for base in reversed(info["b"]):
        saida.update(classes.get(base, {}).get("m", {}))
    saida.update(info["m"])
    return saida


def _membros_py(obj):
    saida = {}
    try:
        nomes = dir(obj)
    except Exception:
        return saida
    for nome in nomes:
        if nome.startswith("__"):
            continue
        try:
            valor = getattr(obj, nome)
        except Exception:
            saida[nome] = ["a"]
            continue
        if isinstance(valor, type(sys)):
            saida[nome] = ["m"]
        elif isinstance(valor, type):
            saida[nome] = ["c"]
        elif callable(valor):
            saida[nome] = ["f"]
        elif isinstance(valor, (int, float)) and nome.isupper():
            saida[nome] = ["k"]
        else:
            saida[nome] = ["a"]
    return saida


def _modulo_real(nome):
    """So modulos confiaveis (stdlib da lista ou embutidos em C): dir()/getattr de um modulo
    qualquer ja carregado (add-on, script do usuario) poderia rodar codigo dele."""
    if nome in sys.builtin_module_names and nome in sys.modules:
        return sys.modules[nome]
    if nome in PERMITIDOS:
        try:
            __import__(nome)
            return sys.modules.get(nome)
        except Exception:
            return None
    return None


def _modulo(nome):
    """Nome de modulo (com alias) -> coisa."""
    nome = ALIAS_MODULO.get(nome, nome)
    for alias, alvo in ALIAS_MODULO.items():
        if nome.startswith(alias + "."):
            nome = alvo + nome[len(alias):]
    if nome in _api()["modulos"]:
        return ("mod", nome)
    real = _modulo_real(nome)
    if real is not None:
        return ("py", real)
    return None


def _membros(coisa):
    tipo, valor = coisa[0], coisa[1]
    if tipo == "mod":
        saida = dict(_api()["modulos"].get(valor, {}))
        # submodulos do catalogo (bge.logic dentro de bge)
        for nome in _api()["modulos"]:
            if nome.startswith(valor + ".") and "." not in nome[len(valor) + 1:]:
                saida.setdefault(nome[len(valor) + 1:], ["m"])
        return saida
    if tipo == "cls":
        return _membros_classe(valor)
    if tipo == "tipo":
        return {n: v for n, v in _membros_classe(valor).items() if v[0] in ("f", "k")}
    if tipo == "py":
        return _membros_py(valor)
    if tipo == "user":
        saida = {}
        for base in valor["bases"]:
            saida.update(_membros(base))
        for nome in valor["attrs"]:
            saida.setdefault(nome, ["a"])
        for nome in valor["metodos"]:
            saida[nome] = ["f"]
        return saida
    return {}


def _tipo_para_coisa(tipo, elem=""):
    if not tipo:
        return None
    if tipo in _api()["classes"]:
        return ("cls", tipo, elem)
    if tipo in TIPOS_PY:
        return ("py", TIPOS_PY[tipo], elem)
    return None


def _passo(coisa, op, arg, ctx):
    """Aplica .attr / () / [] numa coisa."""
    if coisa is None:
        return None
    tipo = coisa[0]
    elem = coisa[2] if len(coisa) > 2 else ""
    if op == "attr":
        if tipo == "mod":
            sub = _modulo(coisa[1] + "." + arg)
            if sub and sub[0] == "mod":
                return sub
            info = _api()["modulos"].get(coisa[1], {}).get(arg)
            if not info:
                return None
            if info[0] == "c":
                return ("tipo", info[1] if len(info) > 1 else arg)
            if info[0] == "f":
                return ("func", info[1] if len(info) > 1 else "", info[2] if len(info) > 2 else "")
            return _tipo_para_coisa(*(info[1:3] if len(info) > 1 else [""]))
        if tipo in ("cls", "tipo"):
            info = _membros_classe(coisa[1]).get(arg)
            if not info:
                return None
            if info[0] == "f":
                return ("func", info[1] if len(info) > 1 else "", info[2] if len(info) > 2 else "")
            return _tipo_para_coisa(*(info[1:3] if len(info) > 1 else [""]))
        if tipo == "py":
            try:
                valor = getattr(coisa[1], arg)
            except Exception:
                return None
            if isinstance(valor, type(sys)) or isinstance(valor, type):
                return ("py", valor)
            if isinstance(coisa[1], type) and callable(valor):
                return None  # metodo de tipo builtin: nao sabemos o retorno
            return None if callable(valor) else ("py", type(valor))
        if tipo == "user":
            for base in coisa[1]["bases"]:
                r = _passo(base, "attr", arg, ctx)
                if r is not None:
                    return r
            return ctx.atributo_self(arg)
        return None
    if op == "call":
        if tipo == "func":
            return _tipo_para_coisa(coisa[1], coisa[2])
        if tipo == "tipo":
            return ("cls", coisa[1])
        if tipo == "py" and isinstance(coisa[1], type):
            return coisa  # str(...) -> str
        return None
    if op == "index":
        if elem:
            return _tipo_para_coisa(elem)
        return None
    return None


# ---------------------------------------------------------------------------
# leitura do texto

RE_IMPORT = re.compile(r"^\s*import\s+(.+)$")
RE_FROM = re.compile(r"^\s*from\s+([\w.]+)\s+import\s+(.+)$")
RE_ATRIB = re.compile(r"^(\s*)([A-Za-z_]\w*)\s*(?::\s*[\w.\[\], ]+)?=(?!=)\s*(.+?)\s*(#.*)?$")
RE_FOR = re.compile(r"^(\s*)for\s+([A-Za-z_]\w*)\s+in\s+(.+?)\s*:\s*(#.*)?$")
RE_CLASSE = re.compile(r"^(\s*)class\s+(\w+)\s*(?:\((.*)\))?\s*:")
RE_DEF = re.compile(r"^(\s*)def\s+(\w+)\s*\((.*)")
RE_SELF_ATTR = re.compile(r"\bself\.([A-Za-z_]\w*)")
RE_IDENT = re.compile(r"[^\W\d]\w*", re.UNICODE)


def _recuo(s):
    return len(s) - len(s.lstrip())


def _parte_codigo(linha):
    """Corta a linha no comentario; devolve (codigo, dentro_de_string_no_fim)."""
    aspas = None
    i = 0
    while i < len(linha):
        c = linha[i]
        if aspas:
            if c == "\\":
                i += 2
                continue
            if linha.startswith(aspas, i):
                i += len(aspas)
                aspas = None
                continue
        else:
            if c == "#":
                return linha[:i], False, True
            if c in "\"'":
                aspas = linha[i:i + 3] if linha[i:i + 3] in ('"""', "'''") else c
                i += len(aspas)
                continue
        i += 1
    return linha, aspas is not None, False


_TRIPLAS = ('"' * 3, "'" * 3)
# comentario | abertura de string tripla | string simples (termina na linha, com escapes)
RE_LEXICO = re.compile("|".join([
    r"#[^\n]*",
    re.escape(_TRIPLAS[0]), re.escape(_TRIPLAS[1]),
    r'"(?:\\.|[^"\\\n])*"?',
    r"'(?:\\.|[^'\\\n])*'?",
]))


def _estado_no_cursor(texto, pos):
    """'codigo', 'string' ou 'comentario' na posicao pos (indice de caractere em texto)."""
    i = 0
    while True:
        m = RE_LEXICO.search(texto, i)
        if not m or m.start() >= pos:
            return "codigo"
        tok = m.group(0)
        if tok in _TRIPLAS:
            j = m.end()
            while True:
                fim = texto.find(tok, j)
                if fim < 0:
                    return "string"
                barras = 0  # \""" nao fecha
                k = fim
                while k > m.end() and texto[k - 1] == "\\":
                    barras += 1
                    k -= 1
                if barras % 2 == 0:
                    break
                j = fim + 1
            if fim + 3 > pos:
                return "string"
            i = fim + 3
            continue
        if tok[0] == "#":
            if m.end() >= pos:
                return "comentario"
        elif len(tok) >= 2 and tok[-1] == tok[0]:
            if m.end() > pos:
                return "string"  # cursor entre as aspas
        elif pos <= m.end():
            return "string"  # aberta ate o fim da linha
        i = m.end()


def _cadeia(expr):
    """'a.b(x)[0].c' -> [('nome','a'),('attr','b'),('call',''),('index',''),('attr','c')] ou None."""
    passos = []
    i = 0
    n = len(expr)
    esperando_nome = True
    while i < n:
        c = expr[i]
        if c.isspace():
            i += 1
            continue
        if esperando_nome:
            m = RE_IDENT.match(expr, i)
            if not m:
                return None
            passos.append(("nome" if not passos else "attr", m.group(0)))
            i = m.end()
            esperando_nome = False
            continue
        if c == ".":
            esperando_nome = True
            i += 1
            continue
        if c in "([":
            fecha = ")" if c == "(" else "]"
            prof = 0
            j = i
            while j < n:
                if expr[j] in "([{":
                    prof += 1
                elif expr[j] in ")]}":
                    prof -= 1
                    if prof == 0:
                        break
                j += 1
            if j >= n or expr[j] != fecha:
                return None
            passos.append(("call" if c == "(" else "index", expr[i + 1:j]))
            i = j + 1
            continue
        return None
    if esperando_nome or not passos:
        return None
    return passos


def _expr_antes_do_ponto(antes):
    """Texto antes do cursor terminando em 'expr.prefixo' -> expr (ou None)."""
    m = re.search(r"\.\s*(\w*)$", antes)
    if not m:
        return None
    fim = m.start()
    i = fim
    prof = 0
    while i > 0:
        c = antes[i - 1]
        if c in ")]":
            prof += 1
        elif c in "([":
            if prof == 0:
                break
            prof -= 1
        elif prof == 0 and not (c.isalnum() or c in "._" or ord(c) > 127):
            break
        i -= 1
    expr = antes[i:fim].strip()
    if not expr or expr[0].isdigit():
        return None
    return expr


_cache_imports = {}


class _Contexto:
    def __init__(self, linhas, linha_cursor):
        self.linhas = linhas
        self.cursor = linha_cursor
        self.nomes_import = {}   # nome local -> coisa
        self.resolvendo = set()
        # roda a cada tecla: as mesmas linhas de import dao o mesmo resultado
        chave = tuple(l for l in linhas if "import" in l)
        if _cache_imports.get("chave") != chave:
            self._ler_imports(chave)
            _cache_imports.update(chave=chave, nomes=dict(self.nomes_import))
        else:
            self.nomes_import = dict(_cache_imports["nomes"])

    def _ler_imports(self, linhas_import):
        for linha in linhas_import:
            cod = _parte_codigo(linha)[0]
            m = RE_FROM.match(cod)
            if m:
                mod = _modulo(m.group(1))
                itens = m.group(2).strip().strip("()")
                for parte in itens.split(","):
                    parte = parte.strip()
                    if not parte or parte == "*":
                        if parte == "*" and mod:
                            for nome in _membros(mod):
                                self.nomes_import.setdefault(nome, ("de", mod, nome))
                        continue
                    nome, _, alias = parte.partition(" as ")
                    nome, alias = nome.strip(), (alias.strip() or nome.strip())
                    if mod:
                        self.nomes_import[alias] = ("de", mod, nome)
                continue
            m = RE_IMPORT.match(cod)
            if m:
                for parte in m.group(1).split(","):
                    nome, _, alias = parte.strip().partition(" as ")
                    nome = nome.strip()
                    if alias.strip():
                        coisa = _modulo(nome)
                        if coisa:
                            self.nomes_import[alias.strip()] = coisa
                    else:
                        topo = nome.split(".")[0]
                        coisa = _modulo(topo)
                        if coisa:
                            self.nomes_import[topo] = coisa

    def classe_do_cursor(self):
        """(nome, bases_texto, linha_inicio, recuo) da classe que envolve o cursor."""
        recuo_atual = None
        for i in range(min(self.cursor, len(self.linhas) - 1), -1, -1):
            linha = self.linhas[i]
            if not linha.strip():
                continue
            r = _recuo(linha)
            if recuo_atual is None:
                recuo_atual = r
                if i != self.cursor:
                    recuo_atual = r + 1 if linha.rstrip().endswith(":") else r
            m = RE_CLASSE.match(linha)
            if m and r < recuo_atual:
                return m.group(2), m.group(3) or "", i, r
            if r == 0 and i != self.cursor and not RE_CLASSE.match(linha) and recuo_atual > 0 and not linha.lstrip().startswith(("def", "@", "#")):
                return None
        return None

    def coisa_self(self):
        achada = self.classe_do_cursor()
        if not achada:
            return None
        nome, bases_txt, inicio, recuo = achada
        if ("self", inicio) in self.resolvendo:
            return None  # class Foo(self): ... (codigo incompleto) nao pode recursar
        self.resolvendo.add(("self", inicio))
        try:
            bases = []
            for b in bases_txt.split(","):
                b = b.strip()
                if not b or "=" in b:
                    continue
                coisa = self.avaliar(b, inicio)
                if coisa is not None and coisa[0] == "tipo":
                    bases.append(("cls", coisa[1]))
        finally:
            self.resolvendo.discard(("self", inicio))
        attrs, metodos = set(), set()
        for linha in self.linhas[inicio + 1:]:
            if linha.strip() and _recuo(linha) <= recuo:
                break
            md = RE_DEF.match(linha)
            if md:
                metodos.add(md.group(2))
            attrs.update(RE_SELF_ATTR.findall(_parte_codigo(linha)[0]))
        return ("user", {"bases": bases, "attrs": attrs, "metodos": metodos, "inicio": inicio})

    def atributo_self(self, nome):
        """Tipo de self.nome pela atribuicao 'self.nome = expr' na classe."""
        achada = self.classe_do_cursor()
        if not achada:
            return None
        _, _, inicio, recuo = achada
        chave = ("self." + nome, inicio)
        if chave in self.resolvendo:
            return None  # self.alvo = self.alvo.parent
        self.resolvendo.add(chave)
        try:
            padrao = re.compile(r"^\s*self\.%s\s*=(?!=)\s*(.+?)\s*(#.*)?$" % re.escape(nome))
            for i in range(inicio + 1, len(self.linhas)):
                linha = self.linhas[i]
                if linha.strip() and _recuo(linha) <= recuo:
                    break
                m = padrao.match(linha)
                if m:
                    return self.avaliar(m.group(1), i)
            return None
        finally:
            self.resolvendo.discard(chave)

    def nome(self, nome, linha_ref):
        """Resolve um nome solto visto na linha linha_ref."""
        if nome == "self":
            return self.coisa_self()
        chave = (nome, linha_ref)
        if chave in self.resolvendo or len(self.resolvendo) > 12:
            return None
        self.resolvendo.add(chave)
        try:
            # atribuicao mais proxima acima (ou 'for nome in ...')
            for i in range(min(linha_ref, len(self.linhas) - 1), -1, -1):
                cod = _parte_codigo(self.linhas[i])[0]
                m = RE_ATRIB.match(cod)
                if m and m.group(2) == nome:
                    return self.avaliar(m.group(3), i)
                m = RE_FOR.match(cod)
                if m and m.group(2) == nome:
                    coisa = self.avaliar(m.group(3), i)
                    if coisa is not None and len(coisa) > 2 and coisa[2]:
                        return _tipo_para_coisa(coisa[2])
                    return None
                m = RE_DEF.match(cod)
                if m and i < linha_ref:
                    params = [p.strip().split("=")[0].split(":")[0].strip() for p in m.group(3).split(")")[0].split(",")]
                    if nome in params:
                        alvo = PARAM_CONHECIDO.get(nome)
                        return ("cls", alvo) if alvo else None
            if nome in self.nomes_import:
                coisa = self.nomes_import[nome]
                if coisa[0] == "de":
                    _, mod, membro = coisa
                    return _passo(mod, "attr", membro, self)
                return coisa
            if nome in TIPOS_PY:
                return ("py", TIPOS_PY[nome])
            return None
        finally:
            self.resolvendo.discard(chave)

    def avaliar(self, expr, linha_ref):
        expr = expr.strip()
        # literais
        if re.match(r"^[rbuf]*['\"]", expr):
            return ("py", str)
        if expr.startswith("["):
            return ("py", list)
        if expr.startswith("{"):
            return ("py", dict)
        passos = _cadeia(expr)
        if not passos:
            return None
        coisa = self.nome(passos[0][1], linha_ref)
        for op, arg in passos[1:]:
            coisa = _passo(coisa, op, arg, self)
            if coisa is None:
                return None
        return coisa


# ---------------------------------------------------------------------------

def _palavras_documento(linhas, linha_cursor, col):
    palavras = set()
    for i, linha in enumerate(linhas):
        if i == linha_cursor:
            # tira a palavra que esta sendo digitada (senao ela sugere a si mesma)
            linha = re.sub(r"\w+$", "", linha[:col]) + " " + re.sub(r"^\w+", "", linha[col:])
        palavras.update(RE_IDENT.findall(linha))
    return {p for p in palavras if len(p) > 1}


def _formatar(membros, so_publicos=True):
    saida = ["OK"]
    for nome, info in sorted(membros.items(), key=lambda kv: kv[0].lower()):
        if not nome or (so_publicos and nome.startswith("_")):
            continue
        saida.append(COR.get(info[0], "q") + nome)
    return "\n".join(saida)


def _modulos_conhecidos():
    nomes = {n.split(".")[0] for n in _api()["modulos"]}
    nomes.update(ALIAS_MODULO)
    nomes.update(n.split(".")[0] for n in PERMITIDOS)
    nomes.update(n for n in getattr(sys, "stdlib_module_names", ()) if not n.startswith("_"))
    return nomes


def _completar_import(antes):
    m = re.match(r"^\s*from\s+([\w.]+)\s+import\s+(?:\(?\s*)?((?:[\w]+(?:\s+as\s+\w+)?\s*,\s*)*)\w*$", antes)
    if m:
        mod = _modulo(m.group(1))
        return _formatar(_membros(mod)) if mod else "OK"
    m = re.match(r"^\s*(?:import|from)\s+((?:[\w.]+\s*,\s*)*)([\w.]*)$", antes)
    if m:
        alvo = m.group(2)
        if "." in alvo:
            pai = alvo.rpartition(".")[0]
            coisa = _modulo(pai)
            if not coisa:
                return "OK"
            return _formatar({n: v for n, v in _membros(coisa).items() if v[0] == "m"})
        return _formatar({n: ["m"] for n in _modulos_conhecidos()})
    return None


def candidatos_texto(texto, linha_idx, col, caminho=None):
    """Versao testavel: texto inteiro + cursor (linha, coluna em caracteres). caminho: arquivo
    do script (para o Jedi achar os outros modulos da pasta)."""
    _ultimo.update(coisa=None, membros={}, ctx=None)
    linhas = texto.split("\n")
    if linha_idx >= len(linhas):
        return "SKIP"
    linha = linhas[linha_idx]
    antes = linha[:col]
    pos = sum(len(l) + 1 for l in linhas[:linha_idx]) + col
    if _estado_no_cursor(texto, pos) != "codigo":
        return "SKIP"

    r = _completar_import(antes)
    if r is not None:
        return r

    expr = _expr_antes_do_ponto(antes)
    if expr is not None:
        ctx = _Contexto(linhas, linha_idx)
        coisa = ctx.avaliar(expr, linha_idx)
        if coisa is None or coisa[0] == "func":
            # o provedor proprio nao sabe o tipo: o Jedi (inferencia de verdade sobre os stubs)
            # tenta; senao nada de chute (o C mantem a lista fechada)
            prefixo = re.search(r"\w*$", antes).group()
            membros = _jedi_membros(texto, linha_idx, col - len(prefixo), caminho)
            if membros is None:
                return "OK"
            _ultimo.update(coisa=("jedi", membros), membros=membros, ctx=ctx)
            return _formatar(membros)
        membros = _membros(coisa)
        _ultimo.update(coisa=coisa, membros=membros, ctx=ctx)
        return _formatar(membros)

    # palavra solta: palavras-chave, builtins, imports e palavras do documento
    if re.search(r"\d\w*$", antes) and not re.search(r"[^\W\d]\w*$", antes):
        return "SKIP"
    ctx = _Contexto(linhas, linha_idx)
    membros = {}
    for nome in _palavras_documento(linhas, linha_idx, col):
        membros[nome] = ["a"]
    for nome in dir(builtins):
        if not nome.startswith("_"):
            membros[nome] = ["c"] if isinstance(getattr(builtins, nome), type) else ["f"]
    for nome in keyword.kwlist:
        membros[nome] = ["kw"]
    for nome in ("self", "cls"):
        membros.setdefault(nome, ["kw"])
    for nome, coisa in ctx.nomes_import.items():
        membros[nome] = ["m"] if coisa[0] in ("mod", "py") else ["a"]
    _ultimo.update(coisa=None, membros=membros, ctx=ctx)
    return _formatar(membros)


def candidatos(linha_idx, col_bytes):
    """Chamado pelo C com o texto ativo do Text Editor."""
    import bpy
    text = getattr(bpy.context, "edit_text", None)
    if text is None:
        return "SKIP"
    _jedi_aquecer()
    texto = text.as_string()
    linhas = texto.split("\n")
    if linha_idx >= len(linhas):
        return "SKIP"
    col = len(linhas[linha_idx].encode("utf-8")[:col_bytes].decode("utf-8", "ignore"))
    return candidatos_texto(texto, linha_idx, col, _caminho_texto(text))


# ---------------------------------------------------------------------------
# Detalhe do item selecionado na lista, dica de assinatura e diagnosticos.
# Tudo devolve texto simples para o C desenhar; nada executa o script do usuario.

import textwrap

LARGURA_DOC = 76


def _quebrar(texto, largura=LARGURA_DOC, max_linhas=6):
    linhas = textwrap.wrap(" ".join(texto.split()), largura) if texto else []
    if len(linhas) > max_linhas:
        linhas = linhas[:max_linhas]
        linhas[-1] = linhas[-1][:largura - 3].rstrip() + "..."
    return linhas


def _doc_py(valor):
    """(assinatura, descricao) de um objeto python real (builtin/stdlib)."""
    import inspect
    nome = getattr(valor, "__name__", "")
    sig = ""
    if callable(valor):
        try:
            sig = nome + str(inspect.signature(valor))
        except (TypeError, ValueError):
            sig = ""
    doc = getattr(valor, "__doc__", None)
    doc = doc if isinstance(doc, str) else ""
    paragrafos = [p.strip() for p in doc.strip().split("\n\n") if p.strip()]
    if paragrafos and nome and paragrafos[0].startswith(nome + "("):
        # docstring de C comeca com a assinatura: "print(value, ..., sep=' ', ...)"
        if not sig:
            sig = paragrafos[0].splitlines()[0].strip()
        paragrafos = paragrafos[1:]
    if callable(valor) and not sig and nome:
        sig = nome + "(...)"
    return sig, (paragrafos[0] if paragrafos else "")


def _tipo_legivel(info):
    tipo = info[1] if len(info) > 1 else ""
    elem = info[2] if len(info) > 2 else ""
    if elem:
        return "%s of %s" % (tipo or "list", elem)
    return tipo


def _info_catalogo(info, nome):
    """(assinatura, descricao, {param: descricao}) de uma entrada do catalogo."""
    if info[0] == "m":
        return ("module " + (info[1] if len(info) > 1 and info[1] else nome), "", {})
    sig = info[3] if len(info) > 3 else ""
    doc = info[4] if len(info) > 4 else ""
    params = info[5] if len(info) > 5 else {}
    if info[0] == "f":
        if not sig:
            sig = nome + "(...)"
        ret = _tipo_legivel(info)
        if ret:
            sig += " -> " + ret
    else:
        tipo = _tipo_legivel(info)
        sig = nome + (": " + tipo if tipo else "")
    return sig, doc, params


def _info_membro(coisa, nome, ctx=None):
    """Descricao do membro 'nome' de uma coisa resolvida -> (sig, doc, params) ou None."""
    if coisa is None:
        return None
    tipo = coisa[0]
    if tipo == "mod":
        if (coisa[1] + "." + nome) in _api()["modulos"]:
            return ("module " + coisa[1] + "." + nome, "", {})
        info = _api()["modulos"].get(coisa[1], {}).get(nome)
        return _info_catalogo(info, nome) if info else None
    if tipo in ("cls", "tipo"):
        info = _membros_classe(coisa[1]).get(nome)
        return _info_catalogo(info, nome) if info else None
    if tipo == "py":
        try:
            valor = getattr(coisa[1], nome)
        except Exception:
            return None
        if isinstance(valor, type(sys)):
            return ("module " + valor.__name__, "", {})
        sig, doc = _doc_py(valor)
        if not callable(valor):
            sig = nome + ": " + type(valor).__name__
        return (sig, doc, {})
    if tipo == "user":
        if ctx is not None:
            achado = ctx.def_usuario(nome, dentro=coisa[1].get("inicio"))
            if achado:
                return achado
        for base in coisa[1]["bases"]:
            r = _info_membro(base, nome, ctx)
            if r:
                return r
        return None
    return None


def detalhe_texto(nome):
    """Assinatura + descricao do item 'nome' da ultima lista: "OK\\n<assinatura>\\n<doc>...".
    So devolve o que se sabe (nada de chute)."""
    membros = _ultimo["membros"]
    info = membros.get(nome)
    if info is None:
        return "SKIP"
    coisa, ctx = _ultimo["coisa"], _ultimo["ctx"]
    achado = None
    if coisa is not None and coisa[0] == "jedi":
        achado = _jedi_info(info)
    elif coisa is not None:
        achado = _info_membro(coisa, nome, ctx)
    elif ctx is not None and nome in ctx.nomes_import:
        alvo = ctx.nomes_import[nome]
        if alvo[0] == "de":
            achado = _info_membro(alvo[1], alvo[2], ctx)
        elif alvo[0] == "mod":
            achado = ("module " + alvo[1], "", {})
        elif alvo[0] == "py":
            achado = ("module " + getattr(alvo[1], "__name__", nome), _doc_py(alvo[1])[1], {})
    elif ctx is not None and ctx.def_usuario(nome):
        achado = ctx.def_usuario(nome)
    elif info[0] != "kw" and hasattr(builtins, nome):
        sig, doc = _doc_py(getattr(builtins, nome))
        achado = (sig or nome, doc, {})
    if not achado:
        return "SKIP"
    sig, doc, _ = achado
    linhas = [sig] + _quebrar(doc)
    if len(linhas) == 1 and sig == nome:
        return "SKIP"
    return "OK\n" + "\n".join(l.replace("\n", " ") for l in linhas)


def detalhe(nome):
    return detalhe_texto(nome)


# -- assinatura -----------------------------------------------------------------

_T3D = '"' * 3
_T3S = "'" * 3
# comentario | string tripla (ate fechar ou o fim) | string simples | parenteses/virgula
RE_TOKENS_CHAMADA = re.compile("|".join([
    r"#[^\n]*",
    _T3D + r"(?:\\.|[^\\])*?(?:" + _T3D + r"|$)",
    _T3S + r"(?:\\.|[^\\])*?(?:" + _T3S + r"|$)",
    r'"(?:\\.|[^"\\\n])*"?',
    r"'(?:\\.|[^'\\\n])*'?",
    r"[()\[\]{},]",
]), re.S)

PALAVRAS_NAO_CHAMADA = set(keyword.kwlist) - {"True", "False", "None"}


def _chamada_aberta(texto, pos):
    """Parentese de chamada que envolve pos: (indice do '(', virgulas, inicio do argumento atual)."""
    ini = texto.rfind("\n", 0, max(0, pos - 4000)) + 1
    pilha = []
    for m in RE_TOKENS_CHAMADA.finditer(texto, ini, pos):
        tok = m.group(0)
        if tok in ("(", "[", "{"):
            pilha.append([tok, m.start(), 0, m.end()])
        elif tok in (")", "]", "}"):
            if pilha:
                pilha.pop()
        elif tok == ",":
            if pilha:
                pilha[-1][2] += 1
                pilha[-1][3] = m.end()
    if not pilha or pilha[-1][0] != "(":
        return None
    return pilha[-1][1], pilha[-1][2], pilha[-1][3]


def _expr_final(antes):
    """Expressao que termina em antes ('own.applyForce', 'x[0].foo') ou None."""
    antes = antes.rstrip()
    i = len(antes)
    prof = 0
    while i > 0:
        c = antes[i - 1]
        if c in ")]":
            prof += 1
        elif c in "([":
            if prof == 0:
                break
            prof -= 1
        elif prof == 0 and not (c.isalnum() or c in "._" or ord(c) > 127):
            break
        i -= 1
    expr = antes[i:].strip()
    if not expr or expr[0].isdigit() or expr in PALAVRAS_NAO_CHAMADA:
        return None
    return expr


def _params_assinatura(sig):
    """'f(a, b=1[, c])' -> [(inicio, fim, nome)] de cada parametro (spans em sig)."""
    abre = sig.find("(")
    if abre < 0:
        return []
    fecha = sig.rfind(")")
    if fecha < abre:
        fecha = len(sig)
    saida = []
    prof = 0
    aspas = None
    ini = abre + 1
    for i in range(abre + 1, fecha + 1):
        c = sig[i] if i < fecha else ","
        if aspas:
            if c == aspas:
                aspas = None
            continue
        if c in "\"'":
            aspas = c
        elif c in "({":
            prof += 1
        elif c in ")}":
            prof -= 1
        elif c == "," and prof == 0:
            m = re.search(r"\*{0,2}\w+|\.\.\.", sig[ini:i])
            if m:
                saida.append((ini + m.start(), ini + m.end(), m.group(0)))
            ini = i + 1
    return saida


def _dividir_virgulas(texto):
    partes, prof, ini = [], 0, 0
    for i, c in enumerate(texto):
        if c in "([{":
            prof += 1
        elif c in ")]}":
            prof -= 1
        elif c == "," and prof == 0:
            partes.append(texto[ini:i])
            ini = i + 1
    partes.append(texto[ini:])
    return partes


RE_DOCSTRING = re.compile(r"^[rRuU]?(" + _T3D + "|" + _T3S + r"|\"|')(.*)")


def _def_assinatura(linhas, i, nome, tirar_self):
    """Assinatura 'nome(params)' de um def na linha i (pode ocupar varias linhas) + docstring."""
    juntas = linhas[i]
    j = i
    while juntas.count("(") > juntas.count(")") and j + 1 < len(linhas) and j < i + 8:
        j += 1
        juntas += " " + linhas[j].strip()
    m = re.match(r"\s*(?:async\s+)?def\s+\w+\s*\((.*)\)\s*(?:->\s*([^:]+))?:", juntas)
    if m:
        params, ret = m.group(1), (m.group(2) or "").strip()
    else:
        m = re.match(r"\s*(?:async\s+)?def\s+\w+\s*\((.*)", juntas)
        params, ret = (m.group(1) if m else ""), ""
    partes = [p.strip() for p in _dividir_virgulas(params) if p.strip()]
    if tirar_self and partes and partes[0] in ("self", "cls"):
        partes = partes[1:]
    sig = "%s(%s)" % (nome, ", ".join(partes)) + (" -> " + ret if ret else "")
    doc = ""
    k = j + 1
    while k < len(linhas) and not linhas[k].strip():
        k += 1
    if k < len(linhas):
        md = RE_DOCSTRING.match(linhas[k].strip())
        if md:
            aspas, corpo = md.group(1), md.group(2)
            fim = corpo.find(aspas)
            if fim >= 0:
                doc = corpo[:fim]
            else:
                partes_doc = [corpo]
                for extra in linhas[k + 1:k + 8]:
                    e = extra.strip()
                    if aspas in e:
                        partes_doc.append(e[:e.find(aspas)])
                        break
                    if not e:
                        break
                    partes_doc.append(e)
                doc = " ".join(p for p in partes_doc if p)
    return sig, doc.strip()


def _def_usuario(self, nome, dentro=None):
    """def/class 'nome' do proprio texto -> (sig, doc, {}). dentro = linha do 'class' para metodos."""
    linhas = self.linhas
    faixa = range(len(linhas))
    if dentro is not None:
        recuo_classe = _recuo(linhas[dentro])
        fim = dentro + 1
        while fim < len(linhas) and (not linhas[fim].strip() or _recuo(linhas[fim]) > recuo_classe):
            fim += 1
        faixa = range(dentro + 1, fim)
    padrao_def = re.compile(r"^(\s*)(?:async\s+)?def\s+%s\s*\(" % re.escape(nome))
    padrao_cls = re.compile(r"^(\s*)class\s+%s\b" % re.escape(nome))
    for i in faixa:
        m = padrao_def.match(linhas[i])
        if m:
            metodo = dentro is not None or len(m.group(1)) > 0
            sig, doc = _def_assinatura(linhas, i, nome, metodo)
            return sig, doc, {}
        if dentro is None and padrao_cls.match(linhas[i]):
            # construtor: __init__ da classe
            r = self.def_usuario("__init__", dentro=i)
            if r:
                return (nome + r[0][len("__init__"):], r[1], {})
            return (nome + "()", "", {})
    return None


_Contexto.def_usuario = _def_usuario


def _resolver_chamavel(ctx, expr, linha_ref):
    """Expressao do que esta sendo chamado -> (sig, doc, params) ou None."""
    passos = _cadeia(expr)
    if not passos or passos[-1][0] not in ("nome", "attr"):
        return None
    nome = passos[-1][1]
    if len(passos) == 1:
        achado = ctx.def_usuario(nome)
        if achado:
            return achado
        if nome in ctx.nomes_import:
            alvo = ctx.nomes_import[nome]
            if alvo[0] == "de":
                return _info_membro(alvo[1], alvo[2], ctx)
            return None
        if hasattr(builtins, nome):
            valor = getattr(builtins, nome)
            if callable(valor):
                sig, doc = _doc_py(valor)
                return (sig, doc, {})
        return None
    coisa = ctx.nome(passos[0][1], linha_ref)
    for op, arg in passos[1:-1]:
        coisa = _passo(coisa, op, arg, ctx)
        if coisa is None:
            return None
    return _info_membro(coisa, nome, ctx)


def assinatura_texto(texto, linha_idx, col, caminho=None):
    """Dica da chamada em volta do cursor:
    "OK\\n<antes>\\n<parametro atual>\\n<depois>\\n<linhas de descricao>..." ou "SKIP"."""
    linhas = texto.split("\n")
    if linha_idx >= len(linhas):
        return "SKIP"
    pos = sum(len(l) + 1 for l in linhas[:linha_idx]) + col
    if _estado_no_cursor(texto, pos) == "comentario":
        return "SKIP"
    achada = _chamada_aberta(texto, pos)
    if not achada:
        return "SKIP"
    abre, virgulas, ini_arg = achada
    expr = _expr_final(texto[max(0, abre - 300):abre])
    if not expr:
        return "SKIP"
    linha_ref = texto.count("\n", 0, abre)
    ctx = _Contexto(linhas, linha_ref)
    achado = _resolver_chamavel(ctx, expr, linha_ref)
    if not achado:
        achado = _jedi_assinatura(texto, abre, caminho)
    if not achado:
        return "SKIP"
    sig, doc, params_doc = achado
    sig = " ".join(sig.split())
    if "(" not in sig:
        return "SKIP"
    params = _params_assinatura(sig)
    ativo = None
    m = re.match(r"\s*(\w+)\s*=(?!=)", texto[ini_arg:pos])
    if m:
        for p in params:
            if p[2].lstrip("*") == m.group(1):
                ativo = p
    elif virgulas < len(params) and not params[virgulas][2].startswith("**"):
        ativo = params[virgulas]
    if ativo is None and not m:
        # passou do numero de parametros: *args (ou "...") recebe o resto
        for n, p in enumerate(params):
            if (p[2].startswith("*") and not p[2].startswith("**") and n <= virgulas) or p[2] == "...":
                ativo = p
                break
    if ativo:
        antes, atual, depois = sig[:ativo[0]], sig[ativo[0]:ativo[1]], sig[ativo[1]:]
    else:
        antes, atual, depois = sig, "", ""
    descricao = _quebrar(doc, max_linhas=4)
    if ativo and params_doc.get(ativo[2].lstrip("*")):
        nome_p = ativo[2].lstrip("*")
        descricao += _quebrar(nome_p + ": " + params_doc[nome_p], max_linhas=3)
    return "OK\n" + "\n".join([antes, atual, depois] + descricao)


def assinatura(linha_idx, col_bytes):
    """Chamado pelo C com o texto ativo do Text Editor."""
    import bpy
    text = getattr(bpy.context, "edit_text", None)
    if text is None:
        return "SKIP"
    texto = text.as_string()
    linhas = texto.split("\n")
    if linha_idx >= len(linhas):
        return "SKIP"
    col = len(linhas[linha_idx].encode("utf-8")[:col_bytes].decode("utf-8", "ignore"))
    return assinatura_texto(texto, linha_idx, col, _caminho_texto(text))


import threading

# -- diagnosticos -----------------------------------------------------------------

ERROS_PYFLAKES = {
    "UndefinedName", "UndefinedLocal", "UndefinedExport", "DuplicateArgument",
    "ReturnOutsideFunction", "YieldOutsideFunction", "ContinueOutsideLoop", "BreakOutsideLoop",
    "TwoStarredExpressions", "TooManyExpressionsInStarredAssignment", "ImportStarNotPermitted",
    "DefaultExceptNotLast",
}
MAX_DIAGNOSTICOS = 200
# modulos que a engine usa so de estarem importados: sem aviso "imported but unused"
IMPORTS_DA_ENGINE = {"Range"}

# acima disso so a sintaxe: o pyflakes passa de ~150 ms e a checagem roda no desenho do editor
MAX_LINHAS_PYFLAKES = 2500


def _nomes_estrela(texto):
    """Nomes que os 'from X import *' do texto trazem (catalogo/stdlib) e se ha algum desconhecido."""
    nomes = set()
    desconhecido = False
    for m in re.finditer(r"^\s*from\s+([\w.]+)\s+import\s+\*", texto, re.M):
        coisa = _modulo(m.group(1))
        if coisa is None:
            desconhecido = True
            continue
        nomes.update(_membros(coisa))
    return nomes, desconhecido


def diagnosticos_texto(texto, nome="<script>"):
    """Erros de sintaxe (compile) + avisos do pyflakes, sem executar nada:
    "OK\\n<e|w>\\t<linha>\\t<coluna_bytes_inicio>\\t<coluna_bytes_fim>\\t<mensagem>"..."""
    import ast
    import warnings
    linhas = texto.split("\n")
    saida = ["OK"]

    def add(sev, linha, c0, c1, msg):
        if len(saida) > MAX_DIAGNOSTICOS or linha < 0 or linha >= len(linhas):
            return
        corpo = linhas[linha]
        fim_util = len(corpo.rstrip())
        if c0 is None:
            # sem coluna: a linha toda sem o recuo
            c0, c1 = _recuo(corpo), fim_util
        elif c0 >= fim_util:
            # depois do fim (ex.: "expected ':'"): o ultimo caractere visivel
            c0, c1 = max(0, fim_util - 1), fim_util
        if c1 is None or c1 <= c0:
            m = RE_IDENT.match(corpo, c0)
            c1 = m.end() if m else c0 + 1
        c1 = min(c1, len(corpo))
        b0 = len(corpo[:c0].encode("utf-8"))
        b1 = len(corpo[:c1].encode("utf-8"))
        msg = " ".join(str(msg).split())[:200]
        saida.append("%s\t%d\t%d\t%d\t%s" % (sev, linha, b0, b1, msg))

    def erro_sintaxe(e):
        linha = (e.lineno or 1) - 1
        c0 = (e.offset - 1) if e.offset else None
        c1 = None
        if c0 is not None and getattr(e, "end_lineno", None) == e.lineno and getattr(e, "end_offset", None):
            c1 = e.end_offset - 1
        add("e", linha, c0, c1, e.msg)

    with warnings.catch_warnings(record=True) as avisos:
        warnings.simplefilter("always")
        try:
            arvore = ast.parse(texto, nome)
            compile(arvore, nome, "exec", dont_inherit=True)
        except SyntaxError as e:
            erro_sintaxe(e)
            return "\n".join(saida)
        except (ValueError, RecursionError, MemoryError) as e:
            add("e", 0, None, None, str(e))
            return "\n".join(saida)
    for w in avisos:
        if issubclass(w.category, (SyntaxWarning, DeprecationWarning)):
            add("w", (w.lineno or 1) - 1, None, None, str(w.message))

    if len(linhas) > MAX_LINHAS_PYFLAKES:
        return "\n".join(saida)
    try:
        from pyflakes import checker
    except ImportError:
        return "\n".join(saida)
    estrela, estrela_desconhecida = _nomes_estrela(texto)
    try:
        resultado = checker.Checker(arvore, filename=nome, builtins=estrela)
    except Exception:
        return "\n".join(saida)
    for msg in sorted(resultado.messages, key=lambda m: (m.lineno, m.col)):
        tipo = type(msg).__name__
        if tipo == "ImportStarUsed":
            continue  # 'from bge.logic import *' e normal em script de jogo
        if tipo == "ImportStarUsage" and estrela_desconhecida:
            continue  # nao da para saber o que o modulo do usuario exporta
        if tipo == "UnusedImport" and msg.message_args and \
                str(msg.message_args[0]).split(".")[0] in IMPORTS_DA_ENGINE:
            continue  # 'import Range': a engine usa o modulo importado, nao e "sem uso"
        linha = msg.lineno - 1
        corpo = linhas[linha] if 0 <= linha < len(linhas) else ""
        # col do ast e em bytes UTF-8: para caracteres
        c0, c1 = len(corpo.encode("utf-8")[:msg.col].decode("utf-8", "ignore")), None
        alvo = msg.message_args[0] if msg.message_args and isinstance(msg.message_args[0], str) else ""
        for nome_alvo in ((alvo, alvo.rpartition(".")[2]) if alvo else ()):
            # 'bge.logic' imported but unused vem de "from bge import logic": acha o nome na linha
            m = re.compile(r"(?<![\w.])%s(?!\w)" % re.escape(nome_alvo)).search(corpo, max(0, c0))
            if m:
                c0, c1 = m.start(), m.end()
                break
        try:
            texto_msg = msg.message % msg.message_args
        except Exception:
            texto_msg = msg.message
        add("e" if tipo in ERROS_PYFLAKES else "w", linha, c0, c1, texto_msg)
    return "\n".join(saida)


def diagnosticos():
    """Chamado pelo C com o texto ativo do Text Editor."""
    import bpy
    text = getattr(bpy.context, "edit_text", None)
    if text is None:
        return "SKIP"
    _jedi_aquecer()  # um script python aberto: o Jedi carrega enquanto a pessoa le
    texto, nome = text.as_string(), text.name
    chave = (nome, texto)
    pronto = _diag.get("pronto")
    if pronto and pronto[0] == chave:
        return pronto[1]
    if _diag.get("rodando"):
        return "WAIT"  # o C volta a perguntar no proximo timer
    # 70-200 ms de pyflakes: numa thread, a digitacao nao espera (o GIL e solto entre as
    # chamadas do C; o desenho do editor so pega o resultado quando fica pronto)
    _diag["rodando"] = True

    def corpo():
        try:
            r = diagnosticos_texto(texto, nome)
        except Exception:
            r = "OK"
        _diag["pronto"] = (chave, r)
        _diag["rodando"] = False
    threading.Thread(target=corpo, name="text_diagnosticos", daemon=True).start()
    return "WAIT"


_diag = {"pronto": None, "rodando": False}


# -- Jedi (inferencia de verdade) ---------------------------------------------------
# So entra quando o provedor proprio nao resolve a expressao antes do ponto ou a chamada da
# dica de assinatura: variaveis de classes do usuario, retornos de funcoes, imports entre
# scripts da pasta. A API do jogo vem dos stubs gerados (scripts/stubs, tools/autocomplete/
# gerar_stubs.py), que ficam na frente do caminho de busca. Roda no proprio processo
# (InterpreterEnvironment: nada de subprocesso com o exe da engine) e nunca importa o script.

import threading

PASTA_STUBS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "stubs")
JEDI_ESPERA = 0.5  # segundos esperando o aquecimento (ou outra consulta) antes de desistir
JEDI_TIPO = {"module": "m", "class": "c", "function": "f", "keyword": "kw", "path": "m"}

_jedi = {"mod": None, "falhou": False, "env": None, "projetos": {}, "aquecido": False}
# o parser do Jedi nao e thread-safe: toda consulta (e o aquecimento) passa por aqui
_jedi_trava = threading.Lock()


def _jedi_mod():
    """Modulo jedi (carregado uma vez) ou None. Chamar com a trava."""
    if _jedi["falhou"]:
        return None
    if _jedi["mod"] is None:
        try:
            import jedi
            # procurar chamadas da funcao em OUTROS arquivos da pasta (para adivinhar os
            # parametros) varre a pasta inteira: segundos numa pasta grande
            jedi.settings.dynamic_params_for_other_modules = False
            _jedi["env"] = jedi.InterpreterEnvironment()
            _jedi["mod"] = jedi
        except Exception as ex:
            print("Autocomplete: Jedi unavailable:", ex)
            _jedi["falhou"] = True
            return None
    return _jedi["mod"]


def _jedi_projeto(jedi, pasta):
    proj = _jedi["projetos"].get(pasta)
    if proj is None:
        # stubs primeiro (um 'bge' de verdade/falso em site-packages venceria os stubs); a pasta
        # do script para os imports entre scripts
        caminhos = [PASTA_STUBS, pasta] + [
            p for p in sys.path if p and "site-packages" not in p.replace("\\", "/").lower()]
        proj = jedi.Project(pasta, sys_path=caminhos, smart_sys_path=False,
                            load_unsafe_extensions=False)
        if len(_jedi["projetos"]) > 8:
            _jedi["projetos"].clear()
        _jedi["projetos"][pasta] = proj
    return proj


def _jedi_script(texto, caminho):
    """Script do Jedi para o texto, ou None. Chamar com a trava."""
    jedi = _jedi_mod()
    if jedi is None:
        return None
    if not caminho:
        # texto sem arquivo nem .range salvo: uma pasta vazia (a pasta TEMP inteira seria o projeto)
        import tempfile
        pasta = os.path.join(tempfile.gettempdir(), "anastacio_jedi")
        os.makedirs(pasta, exist_ok=True)
        caminho = os.path.join(pasta, "script.py")
    pasta = os.path.dirname(caminho) or "."
    return jedi.Script(texto, path=caminho, project=_jedi_projeto(jedi, pasta),
                       environment=_jedi["env"])


def _jedi_aquecer():
    """Carrega o Jedi e os stubs numa thread (a primeira consulta levaria ~1 s na hora do ponto)."""
    if _jedi["aquecido"]:
        return
    _jedi["aquecido"] = True

    def corpo():
        with _jedi_trava:
            try:
                s = _jedi_script("import bge.types\nbge.types.KX_GameObject.", None)
                if s is not None:
                    s.complete(2, 25)
            except Exception:
                pass
    threading.Thread(target=corpo, name="autocomplete_jedi", daemon=True).start()


def _jedi_membros(texto, linha_idx, col, caminho):
    """Membros depois do ponto pelo Jedi: {nome: [cor, Completion]} ou None."""
    if not _jedi_trava.acquire(timeout=JEDI_ESPERA):
        return None
    try:
        s = _jedi_script(texto, caminho)
        if s is None:
            return None
        saida = {}
        for c in s.complete(linha_idx + 1, col):
            saida[c.name] = [JEDI_TIPO.get(c.type, "a"), c]
        return saida or None
    except Exception:
        return None
    finally:
        _jedi_trava.release()


RE_PARAM_DOC = re.compile(r"^:param\s+(\w+):\s*(.*)$")


def _jedi_doc(doc):
    """docstring dos stubs ("descricao\n\n:param x: ...") -> (descricao, {param: desc})."""
    params = {}
    texto = []
    for linha in (doc or "").splitlines():
        m = RE_PARAM_DOC.match(linha.strip())
        if m:
            params[m.group(1)] = m.group(2)
        else:
            texto.append(linha)
    paragrafos = [p.strip() for p in "\n".join(texto).strip().split("\n\n") if p.strip()]
    return (paragrafos[0] if paragrafos else ""), params


def _jedi_sig_texto(sig):
    texto = sig.to_string()
    if texto.endswith(" -> Any"):
        texto = texto[:-len(" -> Any")]
    return texto


def _jedi_info(info):
    """(assinatura, descricao, params) de um item que veio do Jedi, ou None."""
    comp = info[1] if len(info) > 1 else None
    if comp is None or not _jedi_trava.acquire(timeout=JEDI_ESPERA):
        return None
    try:
        sigs = comp.get_signatures()
        if sigs:
            sig = _jedi_sig_texto(sigs[0])
        elif comp.type == "module":
            sig = "module " + (comp.full_name or comp.name)
        else:
            try:
                dica = comp.get_type_hint()
            except Exception:
                dica = ""
            sig = comp.name + (": " + dica if dica and dica != "Any" else "")
        doc, params = _jedi_doc(comp.docstring(raw=True))
        return sig, doc, params
    except Exception:
        return None
    finally:
        _jedi_trava.release()


def _jedi_assinatura(texto, abre, caminho):
    """Assinatura da chamada aberta em 'abre' (posicao do '(') pelo Jedi, ou None."""
    if not _jedi_trava.acquire(timeout=JEDI_ESPERA):
        return None
    try:
        s = _jedi_script(texto, caminho)
        if s is None:
            return None
        linha = texto.count("\n", 0, abre)
        col = abre - (texto.rfind("\n", 0, abre) + 1) + 1
        sigs = s.get_signatures(linha + 1, col)
        if not sigs:
            return None
        doc, params = _jedi_doc(sigs[0].docstring(raw=True))
        return _jedi_sig_texto(sigs[0]), doc, params
    except Exception:
        return None
    finally:
        _jedi_trava.release()


def _caminho_texto(text):
    """Arquivo do texto (salvo) ou um caminho na pasta do .range com o nome do texto."""
    try:
        import bpy
        if text.filepath and not text.is_in_memory:
            return os.path.normpath(bpy.path.abspath(text.filepath))
        if not bpy.data.filepath:
            return None  # _jedi_script usa uma pasta vazia
        nome = text.name if text.name.endswith(".py") else text.name + ".py"
        return os.path.join(os.path.dirname(bpy.data.filepath), nome)
    except Exception:
        return None


# -- formatar (autopep8) --------------------------------------------------------------

def formatar_texto(texto):
    """PEP 8 pelo autopep8 (sem as mudancas 'agressivas'): (novo, erro)."""
    import warnings
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            compile(texto, "<script>", "exec")
    except SyntaxError as ex:
        return None, "Fix the syntax error first (line %d: %s)" % (ex.lineno or 0, ex.msg)
    except ValueError as ex:
        return None, str(ex)
    import autopep8
    return autopep8.fix_code(texto, options={"max_line_length": 120}), None


def formatar():
    """Chamado pelo operador TEXT_OT_format_code: "OK\n<texto novo>", "SAME" ou "ERR\n<msg>"."""
    import bpy
    text = getattr(bpy.context, "edit_text", None)
    if text is None:
        return "ERR\nNo text"
    texto = text.as_string()
    try:
        novo, erro = formatar_texto(texto)
    except Exception as ex:
        return "ERR\nautopep8 failed: %s" % ex
    if erro:
        return "ERR\n" + erro
    if novo == texto:
        return "SAME"
    return "OK\n" + novo
