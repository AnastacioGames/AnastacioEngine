"""Gera stubs .pyi da API do jogo (bge, mathutils, aud, bgl, blf) a partir do catalogo do
autocompletar (source/release/scripts/modules/text_autocomplete_api.json).

Uso (Python do sistema, na raiz do repo, depois de gerar_api_autocomplete.py):
    python tools/autocomplete/gerar_stubs.py

Saida: source/release/scripts/stubs/ (e copia para build/bin/2.79/scripts/stubs).
- O VS Code (Pylance) usa estes arquivos quando ficam em <projeto>/typings: o botao
  "Open in External Editor" copia para la (text_external_editor.py).
- O Jedi do Text Editor usa a pasta direto (text_autocomplete.py), sem por no sys.path:
  'import bge' no editor nao pode virar um pacote vazio.
"""
import ast
import json
import keyword
import os
import re
import shutil
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CATALOGO = os.path.join(RAIZ, "source", "release", "scripts", "modules", "text_autocomplete_api.json")
DESTINO = os.path.join(RAIZ, "source", "release", "scripts", "stubs")
DESTINO_BIN = os.path.join(RAIZ, "build", "bin", "2.79", "scripts", "stubs")

BUILTINS = {"int", "float", "str", "bool", "list", "dict", "tuple", "set", "bytes",
            "BaseException", "Exception", "object"}
# classes que moram nestes modulos tem preferencia quando aparecem em mais de um
PREFERIDOS = ("mathutils", "bge.types", "aud", "bge.texture")
VERSAO = 1

# extras que o catalogo (feito por introspeccao) nao tem: operadores e indexacao
EXTRAS = {
    "EXP_ListValue": [
        "def __getitem__(self, key: int | str) -> _T: ...",
        "def __iter__(self) -> Iterator[_T]: ...",
        "def __len__(self) -> int: ...",
        "def __contains__(self, key: Any) -> bool: ...",
        "def get(self, key: str, default: Any = None) -> _T: ...",
    ],
    "KX_GameObject": [
        "def __getitem__(self, key: str) -> Any: ...",
        "def __setitem__(self, key: str, value: Any) -> None: ...",
        "def __delitem__(self, key: str) -> None: ...",
        "def __contains__(self, key: str) -> bool: ...",
    ],
    # o runtime nao diz o tipo destes (dicionario de eventos por codigo de tecla/botao)
    "KX_PythonKeyboard": [
        "inputs: dict[int, SCA_InputEvent]",
        "activeInputs: dict[int, SCA_InputEvent]",
    ],
    "KX_PythonMouse": [
        "inputs: dict[int, SCA_InputEvent]",
        "activeInputs: dict[int, SCA_InputEvent]",
    ],
    "Vector": [
        "def __init__(self, seq: Any = ...) -> None: ...",
        "def __add__(self, other: Vector) -> Vector: ...",
        "def __sub__(self, other: Vector) -> Vector: ...",
        "def __mul__(self, other: Any) -> Any: ...",
        "def __rmul__(self, other: Any) -> Any: ...",
        "def __matmul__(self, other: Any) -> Any: ...",
        "def __truediv__(self, other: float) -> Vector: ...",
        "def __neg__(self) -> Vector: ...",
        "def __getitem__(self, index: int) -> float: ...",
        "def __setitem__(self, index: int, value: float) -> None: ...",
        "def __iter__(self) -> Iterator[float]: ...",
        "def __len__(self) -> int: ...",
    ],
    "Matrix": [
        "def __init__(self, rows: Any = ...) -> None: ...",
        "def __mul__(self, other: Any) -> Any: ...",
        "def __matmul__(self, other: Any) -> Any: ...",
        "def __getitem__(self, index: int) -> Vector: ...",
        "def __iter__(self) -> Iterator[Vector]: ...",
        "def __len__(self) -> int: ...",
    ],
    "Quaternion": [
        "def __init__(self, seq: Any = ..., angle: float = ...) -> None: ...",
        "def __mul__(self, other: Any) -> Any: ...",
        "def __matmul__(self, other: Any) -> Any: ...",
        "def __getitem__(self, index: int) -> float: ...",
    ],
    "Euler": [
        "def __init__(self, angles: Any = ..., order: str = ...) -> None: ...",
        "def __getitem__(self, index: int) -> float: ...",
        "def __setitem__(self, index: int, value: float) -> None: ...",
    ],
    "Color": [
        "def __init__(self, rgb: Any = ...) -> None: ...",
        "def __getitem__(self, index: int) -> float: ...",
        "def __setitem__(self, index: int, value: float) -> None: ...",
    ],
}


def _ident(nome):
    return nome.isidentifier() and not keyword.iskeyword(nome)


def _doc(texto, params=None, recuo="    "):
    partes = [texto.strip()] if texto and texto.strip() else []
    for nome, desc in sorted((params or {}).items()):
        partes.append(":param %s: %s" % (nome, desc))
    if not partes:
        return []
    corpo = "\n\n".join(partes).replace("\\", "\\\\").replace('"""', '\\"\\"\\"')
    linhas = corpo.split("\n")
    saida = [recuo + '"""' + linhas[0]]
    saida += [(recuo + l) if l else "" for l in linhas[1:]]
    if len(linhas) == 1:
        saida[0] += '"""'
    else:
        saida.append(recuo + '"""')
    return saida


class Gerador:
    def __init__(self, cat):
        self.cat = cat
        self.classes = {k: v for k, v in cat["classes"].items() if k not in BUILTINS and _ident(k)}
        self.modulos = cat["modulos"]
        self.casa = self._casas()

    def _casas(self):
        """classe -> modulo onde ela e definida no stub."""
        achados = {}
        for mod, ents in self.modulos.items():
            for nome, info in ents.items():
                if info[0] != "c" or not _ident(nome):
                    continue
                cls = info[1] if len(info) > 1 and info[1] else nome
                if cls != nome or cls not in self.classes:
                    continue
                achados.setdefault(cls, []).append(mod)
        casa = {}
        for cls, mods in achados.items():
            mods.sort(key=lambda m: (0 if m.startswith(PREFERIDOS) else 1, m))
            casa[cls] = mods[0]
        # classes do catalogo que nenhum modulo lista (bases internas): bge.types
        for cls in self.classes:
            casa.setdefault(cls, "bge.types")
        return casa

    # -- tipos ---------------------------------------------------------------
    def tipo(self, info, precisa, mod):
        t = info[1] if len(info) > 1 else ""
        elem = info[2] if len(info) > 2 else ""
        e = self._nome_tipo(elem, precisa, mod) if elem else ""
        if t == "list" or (not t and elem):
            return "list[%s]" % (e or "Any")
        if t == "EXP_ListValue":
            base = self._nome_tipo(t, precisa, mod)
            return "%s[%s]" % (base, e or "Any")
        return self._nome_tipo(t, precisa, mod) if t else "Any"

    def _nome_tipo(self, t, precisa, mod):
        if t in BUILTINS:
            return t
        if t in self.classes:
            if self.casa[t] != mod:
                precisa.add((self.casa[t], t))
            return t
        return "Any"

    # -- assinaturas ---------------------------------------------------------
    def params(self, sig, nome, metodo):
        """'rayCast(objto, objfrom=None, ...)' -> texto dos parametros do def."""
        corpo = ""
        if sig and "(" in sig and sig.rstrip().endswith(")"):
            corpo = sig[sig.index("(") + 1:sig.rstrip().rindex(")")]
        args = self._args(corpo)
        if args is None:
            args = "*args: Any, **kwargs: Any"
        if metodo:
            args = "self, " + args if args else "self"
        return args

    def _args(self, corpo):
        # [opcional] -> parametro com valor padrao
        limpo, opcionais, prof, atual = [], set(), 0, ""
        for ch in corpo:
            if ch == "[":
                prof += 1
                continue
            if ch == "]":
                prof -= 1
                continue
            limpo.append(ch)
        texto = "".join(limpo)
        prof = 0
        nomes_opc = []
        # quem estava dentro de [] (texto original) fica opcional
        for ch in corpo:
            if ch == "[":
                prof += 1
            elif ch == "]":
                prof -= 1
            elif prof > 0:
                atual += ch
            elif atual:
                nomes_opc.append(atual)
                atual = ""
        if atual:
            nomes_opc.append(atual)
        for pedaco in nomes_opc:
            for p in pedaco.split(","):
                p = p.split("=")[0].strip()
                if p:
                    opcionais.add(p)
        fonte = "def f(%s): pass" % texto
        try:
            arv = ast.parse(fonte)
        except SyntaxError:
            return None
        a = arv.body[0].args
        if a.posonlyargs or a.kwonlyargs:
            return None
        saida = []
        padroes = [None] * (len(a.args) - len(a.defaults)) + list(a.defaults)
        tem_padrao = False
        for arg, padrao in zip(a.args, padroes):
            if not _ident(arg.arg) or arg.arg == "self":
                return None
            if padrao is not None:
                try:
                    ast.literal_eval(padrao)
                    valor = ast.get_source_segment(fonte, padrao)
                except Exception:
                    valor = "..."
                saida.append("%s=%s" % (arg.arg, valor))
                tem_padrao = True
            elif arg.arg in opcionais or tem_padrao:
                saida.append("%s=..." % arg.arg)
                tem_padrao = True
            else:
                saida.append(arg.arg)
        if a.vararg:
            saida.append("*" + a.vararg.arg)
        if a.kwarg:
            saida.append("**" + a.kwarg.arg)
        return ", ".join(saida)

    # -- membros -------------------------------------------------------------
    def membro(self, nome, info, precisa, mod, metodo, recuo):
        tipo = info[0]
        doc = info[4] if len(info) > 4 else ""
        params = info[5] if len(info) > 5 else {}
        if tipo == "f":
            ret = self.tipo(info, precisa, mod) if len(info) > 1 and (info[1] or (len(info) > 2 and info[2])) else "Any"
            linhas = [recuo + "def %s(%s) -> %s:" % (nome, self.params(info[3] if len(info) > 3 else "", nome, metodo), ret)]
            d = _doc(doc, params, recuo + "    ")
            return linhas + (d if d else [recuo + "    ..."])
        if tipo in ("a", "k"):
            t = self.tipo(info, precisa, mod) if len(info) > 1 else "Any"
            if tipo == "k" and t == "Any":
                t = "int"
            return [recuo + "%s: %s" % (nome, t)] + _doc(doc, None, recuo)
        return []

    def classe(self, nome, precisa, mod):
        info = self.classes[nome]
        bases = [b for b in info.get("b", [])[:1] if b in self.classes]
        for b in bases:
            if self.casa[b] != mod:
                precisa.add((self.casa[b], b))
        if nome == "EXP_ListValue":
            bases.append("Generic[_T]")
        linhas = ["class %s%s:" % (nome, "(%s)" % ", ".join(bases) if bases else "")]
        corpo = []
        extras = EXTRAS.get(nome, [])
        nomes_extra = {re.match(r"(?:def\s+)?(\w+)", e).group(1) for e in extras}
        for m, minfo in sorted(info.get("m", {}).items()):
            if not _ident(m) or m in nomes_extra:
                continue
            corpo += self.membro(m, minfo, precisa, mod, True, "    ")
        corpo += ["    " + e for e in extras]
        return linhas + (corpo or ["    ..."]) + [""]

    def ordenar(self, nomes):
        """bases antes das derivadas (no mesmo modulo)."""
        feitos, saida = set(), []

        def visita(n):
            if n in feitos:
                return
            feitos.add(n)
            for b in self.classes[n].get("b", [])[:1]:
                if b in nomes:
                    visita(b)
            saida.append(n)
        for n in sorted(nomes):
            visita(n)
        return saida

    def arquivo(self, mod, pacotes):
        ents = self.modulos.get(mod, {})
        precisa = set()
        corpo = []
        submods = []
        aliases = []
        locais = [c for c, m in self.casa.items() if m == mod]
        for nome, info in sorted(ents.items()):
            if not _ident(nome):
                continue
            if info[0] == "m":
                if (mod + "." + nome) in self.modulos:
                    submods.append(nome)
                continue
            if info[0] == "c":
                cls = info[1] if len(info) > 1 and info[1] else nome
                if cls not in self.classes or cls in locais and cls == nome:
                    continue
                if self.casa.get(cls) != mod:
                    precisa.add((self.casa[cls], cls))
                if cls != nome:
                    aliases.append("%s = %s" % (nome, cls))
                elif self.casa.get(cls) != mod:
                    pass  # reexportado pelo import abaixo
                continue
            corpo += self.membro(nome, info, precisa, mod, False, "")
        classes = []
        for c in self.ordenar(set(locais)):
            classes += self.classe(c, precisa, mod)

        cab = ['"""Stubs gerados de text_autocomplete_api.json (tools/autocomplete/gerar_stubs.py). '
               'Nao edite."""', "from typing import Any, Generic, Iterator, TypeVar", ""]
        for s in submods:
            cab.append("from . import %s as %s" % (s, s) if mod in pacotes else "import %s.%s as %s" % (mod, s, s))
        reexp = sorted({cls for (m, cls) in precisa if m != mod})
        porm = {}
        for m, cls in sorted(precisa):
            if m != mod:
                porm.setdefault(m, set()).add(cls)
        for m, nomes in sorted(porm.items()):
            listados = {n for n, i in ents.items() if i[0] == "c" and n in nomes}
            partes = ["%s as %s" % (n, n) if n in listados else n for n in sorted(nomes)]
            cab.append("from %s import %s" % (m, ", ".join(partes)))
        cab.append("")
        if "EXP_ListValue" in locais:
            cab += ["_T = TypeVar('_T')", ""]
        del reexp
        return "\n".join(cab + classes + corpo + aliases) + "\n"

    def gerar(self, destino):
        if os.path.isdir(destino):
            shutil.rmtree(destino)
        mods = sorted(self.modulos)
        pacotes = {m for m in mods if any(o.startswith(m + ".") for o in mods)}
        for mod in mods:
            partes = mod.split(".")
            if mod in pacotes:
                caminho = os.path.join(destino, *partes, "__init__.pyi")
            else:
                caminho = os.path.join(destino, *partes[:-1], partes[-1] + ".pyi")
            os.makedirs(os.path.dirname(caminho), exist_ok=True)
            with open(caminho, "w", encoding="utf-8", newline="\n") as f:
                f.write(self.arquivo(mod, pacotes))
        with open(os.path.join(destino, "VERSION.txt"), "w", encoding="utf-8", newline="\n") as f:
            f.write("%d %d\n" % (VERSAO, self.cat.get("versao", 0)))


def main():
    with open(CATALOGO, encoding="utf-8") as f:
        cat = json.load(f)
    g = Gerador(cat)
    g.gerar(DESTINO)
    # os stubs precisam ser Python valido
    for pasta, _, arquivos in os.walk(DESTINO):
        for a in arquivos:
            if a.endswith(".pyi"):
                caminho = os.path.join(pasta, a)
                with open(caminho, encoding="utf-8") as f:
                    ast.parse(f.read(), caminho)
    if os.path.isdir(os.path.dirname(DESTINO_BIN)):
        if os.path.isdir(DESTINO_BIN):
            shutil.rmtree(DESTINO_BIN)
        shutil.copytree(DESTINO, DESTINO_BIN)
    print("stubs em", DESTINO)


if __name__ == "__main__":
    sys.exit(main())
