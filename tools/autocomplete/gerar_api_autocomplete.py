"""Gera o catalogo da API usado pelo autocompletar do Text Editor.

Uso (Python do sistema, na raiz do repo):
    python tools/autocomplete/gerar_api_autocomplete.py

1. Cria um .range vazio com o editor em background.
2. Roda o runtime sem janela (--server) com despejar_api.py: nomes REAIS de bge.* e mathutils.
3. Junta com os tipos/assinaturas dos .rst de source/doc/python_api/rst (o runtime nao diz tipos).
4. Grava source/release/scripts/modules/text_autocomplete_api.json (e copia para build/bin).

Rode de novo quando a API do jogo mudar (atributo/metodo novo em C++ ou .rst).
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BIN = os.path.join(RAIZ, "build", "bin")
EDITOR = os.path.join(BIN, "AnastacioEngine.exe" if os.name == "nt" else "AnastacioEngine")
RUNTIME = os.path.join(BIN, "AnastacioRuntime.exe" if os.name == "nt" else "AnastacioRuntime")
RST = os.path.join(RAIZ, "source", "doc", "python_api", "rst")
DESTINO = os.path.join(RAIZ, "source", "release", "scripts", "modules", "text_autocomplete_api.json")
DESTINO_BIN = os.path.join(BIN, "2.79", "scripts", "modules", "text_autocomplete_api.json")

BASICOS = {
    "float": "float", "double": "float", "int": "int", "integer": "int", "bool": "bool",
    "boolean": "bool", "string": "str", "str": "str", "list": "list", "dict": "dict",
    "dictionary": "dict", "tuple": "tuple", "set": "set", "bytes": "bytes",
}
# swizzles do Vector (xxyz, wzyx...): centenas de nomes que so poluem a lista; ficam xy/xyz/xyzw
SWIZZLE = re.compile(r"^(?!xy$|xyz$|xyzw$)[xyzw]{2,4}$")
MATHUTILS = ("Vector", "Matrix", "Euler", "Quaternion", "Color")


def despejar():
    tmp = tempfile.mkdtemp(prefix="autocomplete_")
    cena = os.path.join(tmp, "vazio.range")
    criar = os.path.join(tmp, "criar.py")
    with open(criar, "w", encoding="utf-8") as f:
        f.write("import bpy\nbpy.ops.wm.save_as_mainfile(filepath=%r)\n" % cena)
    subprocess.run([EDITOR, "-b", "--factory-startup", "--python", criar],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
    cru = os.path.join(tmp, "cru.json")
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "despejar_api.py")
    subprocess.run([RUNTIME, "--server", "-p", script, cena, "-", cru],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=180, cwd=tmp)
    if not os.path.exists(cru):
        sys.exit("o runtime nao gerou %s" % cru)
    with open(cru, encoding="utf-8") as f:
        dados = json.load(f)
    shutil.rmtree(tmp, ignore_errors=True)
    return dados


def normalizar_tipo(texto, classes):
    """Texto livre de ':type:' -> (tipo, tipo_do_elemento). Vazio quando nao da para saber."""
    if not texto:
        return "", ""
    achados = [c.split(".")[-1] for c in re.findall(r":class:`~?([\w.]+)`", texto)]
    achados = [c for c in achados if c in classes]
    baixo = texto.lower()
    if achados:
        primeiro = achados[0]
        # "list of :class:`X`" / ":class:`EXP_ListValue` of :class:`X`"
        if primeiro in ("EXP_ListValue", "CListValue") and len(achados) > 1:
            return primeiro, achados[1]
        if re.match(r"\s*(list|sequence|tuple)\b", baixo) and " of " in baixo:
            return "list", primeiro
        return primeiro, ""
    for nome in MATHUTILS:
        if re.match(r"\s*(\d+x\d+\s+)?%s\b" % nome.lower(), baixo):
            return nome, ""
    m = re.match(r"\s*([a-z]+)", baixo)
    if m and m.group(1) in BASICOS:
        return BASICOS[m.group(1)], ""
    return "", ""


RE_PAPEL = re.compile(r":(?:class|data|attr|func|meth|mod|obj|ref|exc|const):`~?([^`<]+?)(?:\s*<[^>]+>)?`")


def limpar_rst(texto):
    """Tira a marcacao rst de uma frase (:class:`X` -> X, ``a`` -> a, **b** -> b)."""
    texto = RE_PAPEL.sub(lambda m: m.group(1), texto)
    texto = texto.replace("``", "").replace("**", "")
    texto = re.sub(r"`([^`]+)`_?", lambda m: m.group(1), texto)
    return re.sub(r"\s+", " ", texto).strip()


def ler_rst():
    """{(dono, nome): {"tt": tipo, "s": assinatura, "d": descricao, "a": {param: descricao}}}."""
    itens = {}
    arquivos = [os.path.join(RST, n) for n in os.listdir(RST) if n.startswith("bge.") and n.endswith(".rst")]
    pasta_tipos = os.path.join(RST, "bge_types")
    arquivos += [os.path.join(pasta_tipos, n) for n in os.listdir(pasta_tipos) if n.endswith(".rst")]
    re_dir = re.compile(r"^(\s*)\.\. (module|class|attribute|data|method|function|classmethod|staticmethod)::\s*([\w.]+)(\(.*\))?")
    re_arg = re.compile(r"^:(?:arg|param)\s+(?:[\w.]+\s+)?(\w+):\s*(.*)$")
    for arq in sorted(arquivos):
        modulo = ""
        classe = ""
        nivel_classe = -1
        atual = None
        recuo_item = 0
        paragrafo = None   # linhas da 1a descricao (None = ja terminou)
        arg_atual = None
        with open(arq, encoding="utf-8") as f:
            for linha in f:
                m = re_dir.match(linha)
                if m:
                    if atual is not None and paragrafo:
                        atual.setdefault("d", limpar_rst(" ".join(paragrafo)))
                    paragrafo, arg_atual = None, None
                    recuo, tipo, nome, args = len(m.group(1)), m.group(2), m.group(3), m.group(4) or ""
                    if tipo == "module":
                        modulo, classe, atual = nome, "", None
                        continue
                    if tipo == "class":
                        classe, nivel_classe, atual = nome.split(".")[-1], recuo, None
                        continue
                    if classe and recuo <= nivel_classe:
                        classe = ""
                    dono = classe or modulo
                    if not dono:
                        atual = None
                        continue
                    atual = itens.setdefault((dono, nome.split(".")[-1]), {})
                    recuo_item = recuo
                    paragrafo = []
                    if args:
                        atual["s"] = nome.split(".")[-1] + args
                    continue
                if atual is None:
                    continue
                s = linha.strip()
                if s and len(linha) - len(linha.lstrip()) <= recuo_item:
                    # saiu do bloco do item (texto da classe/modulo depois dele)
                    if paragrafo:
                        atual.setdefault("d", limpar_rst(" ".join(paragrafo)))
                    atual, paragrafo, arg_atual = None, None, None
                    continue
                if s.startswith(":type:") or s.startswith(":rtype:"):
                    atual.setdefault("tt", s.split(":", 2)[2].strip())
                ma = re_arg.match(s)
                if ma:
                    arg_atual = ma.group(1)
                    if ma.group(2).strip():
                        atual.setdefault("a", {})[arg_atual] = limpar_rst(ma.group(2))
                    else:
                        arg_atual = arg_atual  # descricao vem nas linhas seguintes
                elif arg_atual and s and not s.startswith(":") and not s.startswith(".."):
                    args_d = atual.setdefault("a", {})
                    if arg_atual not in args_d:
                        args_d[arg_atual] = limpar_rst(s.lstrip("*- "))
                    arg_atual = None
                elif s.startswith(":"):
                    arg_atual = None
                if paragrafo is not None:
                    if not s:
                        if paragrafo:
                            atual.setdefault("d", limpar_rst(" ".join(paragrafo)))
                            paragrafo = None
                    elif s.startswith(":") or s.startswith(".."):
                        if paragrafo:
                            atual.setdefault("d", limpar_rst(" ".join(paragrafo)))
                        paragrafo = None
                    else:
                        paragrafo.append(s)
    return itens


def montar(dados, rst):
    classes_cruas = dados["classes"]
    nomes = set(classes_cruas)

    def item(dono, nome, info):
        doc = rst.get((dono, nome), {})
        tipo, elem = info.get("t", ""), ""
        if info["k"] in ("a", "f"):
            # instancia de modulo (bge.logic.keyboard) ja traz o tipo real; senao rst/docstring
            if info["k"] == "f" or not tipo or (tipo not in nomes and tipo not in BASICOS.values()):
                tipo, elem = normalizar_tipo(doc.get("tt") or info.get("tt", ""), nomes)
        sig = doc.get("s", "")
        if not sig and info["k"] == "f":
            d = info.get("s", "")
            m = re.match(r"(?:\.\. \w+:: )?(%s\(.*\))" % re.escape(nome), d)
            sig = m.group(1) if m else ""
        texto = doc.get("d") or info.get("d", "")
        if texto.startswith(nome + "(") or texto.startswith(".. "):
            texto = ""  # docstring de C que so repete a assinatura
        if len(texto) > 320:
            corte = texto.rfind(". ", 0, 320)
            texto = texto[:corte + 1] if corte > 80 else texto[:317] + "..."
        params = doc.get("a", {})
        params = {p: (d if len(d) <= 160 else d[:157] + "...") for p, d in params.items()}
        # [tipo, tipo_do_elemento, assinatura, descricao, {param: descricao}] (vazios do fim saem)
        saida = [info["k"], tipo, elem, sig, texto, params]
        while len(saida) > 1 and not saida[-1]:
            saida.pop()
        return saida

    modulos = {}
    for mod, membros in dados["modulos"].items():
        dono = mod
        modulos[mod] = {n: item(dono, n, i) for n, i in sorted(membros.items())}
    classes = {}
    for nome, info in classes_cruas.items():
        classes[nome] = {"b": info["bases"],
                         "m": {n: item(nome, n, i) for n, i in sorted(info["m"].items())
                               if not SWIZZLE.match(n)}}
    return {"versao": 2, "modulos": modulos, "classes": classes}


def main():
    dados = despejar()
    catalogo = montar(dados, ler_rst())
    texto = json.dumps(catalogo, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    for destino in (DESTINO, DESTINO_BIN):
        if os.path.isdir(os.path.dirname(destino)):
            with open(destino, "w", encoding="utf-8") as f:
                f.write(texto)
            print("gravado", destino, len(texto) // 1024, "KB")
    com_tipo = sum(1 for c in catalogo["classes"].values() for v in c["m"].values() if len(v) > 1 and v[1])
    total = sum(len(c["m"]) for c in catalogo["classes"].values())
    print("classes", len(catalogo["classes"]), "membros", total, "com tipo", com_tipo)


if __name__ == "__main__":
    main()
