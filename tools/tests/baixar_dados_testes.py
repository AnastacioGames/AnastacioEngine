#!/usr/bin/env python3
"""Baixa os dados de teste do Blender usados pelo ctest (lib/tests e lib/tests_data).

A pasta lib/ nao vai para o git. Sem estes dados, os testes Python que dependem
deles nao sao registrados (ver source/tests/python/CMakeLists.txt).

Uso (da raiz do repositorio, Windows ou Linux):
    python tools/tests/baixar_dados_testes.py
Depois rode `cmake .` no diretorio de build para registrar os testes.
Arquivos ja existentes sao pulados, entao pode rodar de novo para completar.
"""

import os
import re
import sys
import urllib.parse
import urllib.request

SVN = "https://svn.blender.org/svnroot/bf-blender"

# (url base no SVN, pasta destino relativa ao repo, subpastas)
DOWNLOADS = [
    (SVN + "/tags/blender-2.79-release/lib/tests", "lib/tests",
     ["modeling", "modifier_stack", "io_tests"]),
    # ffmpeg nao existe no tag 2.79; o trunk serve.
    (SVN + "/trunk/lib/tests", "lib/tests_data", ["ffmpeg"]),
]

# O servidor responde 403 para o User-Agent padrao do urllib.
_opener = urllib.request.build_opener()
_opener.addheaders = [("User-Agent", "curl/8.0")]
urllib.request.install_opener(_opener)


def baixar_pasta(url, destino):
    html = urllib.request.urlopen(url, timeout=60).read().decode("utf-8", "replace")
    os.makedirs(destino, exist_ok=True)
    for href in re.findall(r'href="([^"]+)"', html):
        if href.startswith(("..", "http", "/", "?")):
            continue
        nome = urllib.parse.unquote(href.rstrip("/"))
        if "/" in nome or nome in ("", "."):
            continue
        if href.endswith("/"):
            baixar_pasta(url + href, os.path.join(destino, nome))
            continue
        caminho = os.path.join(destino, nome)
        if os.path.exists(caminho):
            continue
        print("  ", os.path.relpath(caminho))
        tmp = caminho + ".part"
        urllib.request.urlretrieve(url + href, tmp)
        os.replace(tmp, caminho)


def main():
    raiz = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    for base, destino, pastas in DOWNLOADS:
        for pasta in pastas:
            print("Baixando", pasta, "->", destino)
            baixar_pasta(base + "/" + pasta + "/", os.path.join(raiz, destino, pasta))
    print("Pronto. Rode `cmake .` no build e depois `ctest`.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
