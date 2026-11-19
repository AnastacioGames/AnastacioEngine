# Roda DENTRO do runtime (AnastacioRuntime --server -p despejar_api.py vazio.range).
# Despeja os nomes reais da API do jogo (bge.* e mathutils) num JSON cru; o gerador
# (gerar_api_autocomplete.py) junta com os tipos dos .rst e grava o catalogo final.
import sys
import json
import types
import inspect

import bge
import mathutils

SAIDA = sys.argv[-1]  # ultimo argumento depois de ' - '

MODULOS = [
    "bge", "bge.logic", "bge.render", "bge.events", "bge.constraints", "bge.types",
    "bge.texture", "bge.track", "bge.audio", "bge.application", "bge.network",
    "bge.imgui", "bge.locale", "bge.args",
    "mathutils", "mathutils.geometry", "mathutils.noise", "mathutils.kdtree",
    "mathutils.bvhtree", "mathutils.interpolate", "aud", "bgl", "blf",
]

FUNC_TIPOS = (types.BuiltinFunctionType, types.FunctionType, types.MethodType,
              types.BuiltinMethodType)
DESC_FUNC = (type(str.join), type(dict.__dict__["fromkeys"]))  # method_descriptor, classmethod_descriptor


def resolver(nome):
    obj = sys.modules.get(nome)
    if obj is not None:
        return obj
    pai, _, filho = nome.rpartition(".")
    mod = resolver(pai) if pai else None
    return getattr(mod, filho, None) if mod is not None else None


def doc1(obj):
    """Primeiro paragrafo do docstring, sem a linha '.. method:: x()' do mathutils."""
    d = getattr(obj, "__doc__", None)
    if not isinstance(d, str):
        return ""
    partes = []
    for linha in d.strip().splitlines():
        linha = linha.strip()
        if linha.startswith(".."):
            continue
        if not linha or linha.startswith(":"):
            if partes:
                break
            continue
        partes.append(linha)
    return " ".join(partes)[:400]


def assinatura_doc(obj):
    """'nome(args)' da linha '.. method:: nome(args)' (docstrings do mathutils/bge em C)."""
    d = getattr(obj, "__doc__", None)
    if not isinstance(d, str):
        return ""
    for linha in d.strip().splitlines()[:3]:
        linha = linha.strip()
        if linha.startswith(".. ") and "::" in linha:
            return linha.split("::", 1)[1].strip()[:300]
    return ""


def tipo_doc(obj):
    """Texto de ':type:'/':rtype:' do docstring (mathutils documenta assim)."""
    d = getattr(obj, "__doc__", None)
    if not isinstance(d, str):
        return ""
    for linha in d.splitlines():
        linha = linha.strip()
        if linha.startswith(":rtype:") or linha.startswith(":type:"):
            return linha.split(":", 2)[2].strip()[:200]
    return ""


def membro_de_modulo(valor):
    if isinstance(valor, types.ModuleType):
        return {"k": "m", "t": valor.__name__}
    if isinstance(valor, type):
        return {"k": "c", "t": valor.__name__}
    if isinstance(valor, FUNC_TIPOS):
        return {"k": "f", "d": doc1(valor), "s": assinatura_doc(valor), "tt": tipo_doc(valor)}
    if isinstance(valor, (bool, int, float, str)) and not isinstance(valor, type):
        return {"k": "k", "t": type(valor).__name__}
    return {"k": "a", "t": type(valor).__name__}


classes = {}


def registrar_classe(cls):
    nome = cls.__name__
    if nome in classes:
        return
    info = {"bases": [b.__name__ for b in cls.__mro__[1:] if b is not object],
            "mod": getattr(cls, "__module__", ""), "m": {}}
    classes[nome] = info
    for base in cls.__mro__[1:]:
        if base is not object and isinstance(base, type):
            registrar_classe(base)
    for chave, valor in cls.__dict__.items():
        if chave.startswith("__"):
            continue
        if isinstance(valor, DESC_FUNC) or isinstance(valor, FUNC_TIPOS) or isinstance(valor, (staticmethod, classmethod)):
            info["m"][chave] = {"k": "f", "d": doc1(valor), "s": assinatura_doc(valor), "tt": tipo_doc(valor)}
        elif isinstance(valor, (types.GetSetDescriptorType, types.MemberDescriptorType, property)):
            info["m"][chave] = {"k": "a", "d": doc1(valor), "s": assinatura_doc(valor), "tt": tipo_doc(valor)}
        elif isinstance(valor, (bool, int, float, str)):
            info["m"][chave] = {"k": "k", "t": type(valor).__name__}
        else:
            info["m"][chave] = {"k": "a", "t": type(valor).__name__}


modulos = {}
for nome in MODULOS:
    mod = resolver(nome)
    if not isinstance(mod, types.ModuleType):
        continue
    membros = {}
    for chave in dir(mod):
        if chave.startswith("_"):
            continue
        try:
            valor = getattr(mod, chave)
        except Exception:
            continue
        membros[chave] = membro_de_modulo(valor)
        if isinstance(valor, type):
            registrar_classe(valor)
        elif not isinstance(valor, (types.ModuleType,) + FUNC_TIPOS) and not isinstance(valor, (bool, int, float, str)):
            # instancias (bge.logic.keyboard etc): registra a classe delas
            if type(valor).__module__ not in ("builtins",):
                registrar_classe(type(valor))
    modulos[nome] = membros

with open(SAIDA, "w", encoding="utf-8") as f:
    json.dump({"modulos": modulos, "classes": classes}, f, ensure_ascii=False, indent=0, sort_keys=True)

bge.logic.endGame()
